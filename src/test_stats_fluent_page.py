"""User-visible company analysis and date selection contracts."""
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

from PySide6.QtCore import QPoint, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QDialog
from qfluentwidgets import Pivot
from qfluentwidgets import IconWidget
from stats_controls import FluentSegmentedControl, StatisticsScrollArea
from stats_tokens import DATA_CATEGORY_COLORS, DATA_COMPANY_COLORS, TEXT_PRIMARY
from statistics_page import StatisticsPage
from test_dashboard_page import session


def _loaded_page():
    app = QApplication.instance() or QApplication([])
    page = StatisticsPage()
    page.set_session(session())
    _wait_snapshot(app, page)
    return page


def _wait_snapshot(app, page):
    deadline = time.monotonic() + 10
    while page.snapshot is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert page.snapshot is not None


def test_default_mode_keeps_two_company_charts_separate_and_filter_fixed():
    page = _loaded_page()
    assert page.analysis_mode == 'default'
    assert page.snapshot.filters.comparison is None
    assert len(page.tab_bar.items) == 3
    assert page.export_target() is page.company_dashboard
    assert page.scroll.parentWidget() is page.data_stack
    assert page.filter_card.parentWidget() is page
    assert set(page.company_dashboard.groups) == {'a', 'b'}
    for company_id, group in page.company_dashboard.groups.items():
        assert len(group.panels) == 4
        assert all({owner for owner, _ in panel.result.series} <= {company_id}
                   for panel in group.panels.values())
    assert not page.company_dashboard.shared_panels
    page.close()


def test_fluent_subtabs_have_icons_and_route_to_existing_content():
    page = _loaded_page()
    assert isinstance(page.tab_bar, Pivot)
    assert list(page.tab_bar.items) == ['company', 'network', 'city']
    assert all(not item.icon().isNull() for item in page.tab_bar.items.values())
    page.tab_bar.setCurrentItem('network')
    assert page.export_target() is page.network_dashboard
    assert page.filter_card.parentWidget() is page
    page.close()


def test_analysis_mode_is_direct_three_button_segment():
    page = _loaded_page()
    assert isinstance(page.analysis_mode_control, FluentSegmentedControl)
    assert not page.analysis_mode_control._subtle
    assert all(isinstance(scroll, StatisticsScrollArea)
               for scroll in (page.scroll, page.network_scroll, page.city_scroll))
    page.analysis_mode_control.setCurrentKey('period')
    _wait_snapshot(QApplication.instance(), page)
    assert page.analysis_mode == 'period'
    assert page.compare_field.isVisibleTo(page)
    page.close()


def test_company_tags_can_remove_one_selection_without_hiding_others():
    page = _loaded_page()
    assert set(page.company_tags) == {'a', 'b'}
    assert all(tag.name_label.accessibleName() == tag.name_label.text()
               for tag in page.company_tags.values())
    page.company_tags['a'].close_button.click()
    assert page.selected_companies() == ('b',)
    assert set(page.company_tags) == {'b'}
    page.close()


def test_companies_mode_uses_one_public_chart_per_metric():
    page = _loaded_page()
    page.analysis_mode_control.setCurrentKey('companies')
    _wait_snapshot(QApplication.instance(), page)
    assert page.snapshot.filters.comparison is None
    assert len(page.company_dashboard.shared_panels) == 4
    cash = page.company_dashboard.shared_panels['cashflow']
    assert {owner for owner, _ in cash.result.series} == {'a', 'b'}
    assert all(not group.panels for group in page.company_dashboard.groups.values())
    page.close()


def test_filter_can_collapse_and_expand_without_changing_selection_or_query(monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    app = QApplication.instance() or QApplication([])
    page = _loaded_page()
    page.resize(1200, 800)
    page.show()
    app.processEvents()
    original_height = page.filter_card.height()
    original_companies = page.selected_companies()
    original_names = [action.text() for action in page.company_menu.actions()
                      if action.isChecked()]
    original_mode = page.analysis_mode
    original_token = page.token
    collapse_started = time.monotonic()
    page.confirm_filters_button.click()
    QTest.qWait(105)
    assert 0 < page.filter_card.height() < original_height, (page.filter_card.height(), original_height,
                                                              page._filter_animating,
                                                              round((time.monotonic()-collapse_started)*1000,1))
    QTest.qWait(130)
    app.processEvents()
    assert page.filter_card.height() < original_height
    assert page.compact_filter_bar.isVisible()
    assert page.expand_filters_button.isVisible()
    assert not page.toolbar_host.isVisible()
    assert all(name in page.compact_filter_summary.text() for name in original_names)
    expand_started = time.monotonic()
    page.expand_filters_button.click()
    QTest.qWait(100)
    assert page.filter_card.height() < original_height, dict(height=page.filter_card.height(),
        original=original_height,elapsed_ms=round((time.monotonic()-expand_started)*1000,1),
        animation_ms=page._filter_animation.currentTime() if page._filter_animation else 'finished')
    QTest.qWait(200)
    app.processEvents()
    assert page.filter_card.height() == original_height
    assert page.toolbar_host.isVisible()
    assert page.selected_companies() == original_companies
    assert page.analysis_mode == original_mode and page.token == original_token
    page.close()


def test_company_comparison_chart_height_survives_repeated_reflow():
    page = _loaded_page()
    page.analysis_mode_control.setCurrentKey('companies')
    _wait_snapshot(QApplication.instance(), page)
    dashboard = page.company_dashboard
    dashboard.reflow(1154, 746)
    dashboard.reflow(1154, 746)
    assert all(panel.height() <= 230 and panel.minimumHeight() == panel.height()
               for panel in dashboard.shared_panels.values())
    dashboard.reflow(2288, 1202)
    dashboard.reflow(2288, 1202)
    assert all(panel.height() >= 400 and panel.minimumHeight() == panel.height()
               for panel in dashboard.shared_panels.values())
    page.close()


def test_company_cards_release_and_restore_height_budget_across_column_changes():
    app = QApplication.instance() or QApplication([])
    page = _loaded_page()
    for mode, wide in (('default', 1154), ('companies', 1154)):
        page.analysis_mode_control.setCurrentKey(mode)
        _wait_snapshot(app, page)
        dashboard = page.company_dashboard
        for width in (wide, 600, wide, 600):
            dashboard.reflow(width, 746)
            app.processEvents()
            panels = (list(dashboard.shared_panels.values()) if mode == 'companies' else
                      [panel for group in dashboard.groups.values() for panel in group.panels.values()])
            assert panels
            if width == 600:
                assert all(panel._compact_height is None and panel.minimumHeight() >= 300
                           and panel.maximumHeight() == 16777215 for panel in panels)
            else:
                assert all(panel._compact_height is not None and
                           panel.minimumHeight() == panel.maximumHeight() for panel in panels)
    page.close()


def test_company_color_and_same_metric_hover_are_shared_between_columns():
    page = _loaded_page()
    left = page.company_dashboard.groups['a'].panels['cashflow']
    right = page.company_dashboard.groups['b'].panels['cashflow']
    assert page._company_palette == {'a': DATA_COMPANY_COLORS[0],
                                     'b': DATA_COMPANY_COLORS[1]}
    assert left._company_color('a').name() == page._company_palette['a'].lower()
    assert right._company_color('b').name() == page._company_palette['b'].lower()
    assert left._category_palette == DATA_CATEGORY_COLORS
    seen = []
    original = right.set_hover_offset
    right.set_hover_offset = lambda offset: (seen.append(offset), original(offset))
    left.hover_offset_changed.emit(3600.0)
    assert seen == [3600.0]
    page.close()


def test_kpi_uses_icon_number_and_model_unit_as_distinct_levels():
    page = _loaded_page()
    tile = page.company_dashboard.groups['a'].kpis['cashflow']
    assert isinstance(tile.icon, IconWidget)
    assert 16 <= tile.icon.size().width() <= 20
    assert tile.value.text() == '207,312'
    assert tile.unit.text() == '货币'
    assert tile.height() >= 80
    green = page._company_palette['b']
    other_group = page.company_dashboard.groups['b']
    assert green in other_group.color_dot.styleSheet()
    assert other_group.kpis['cashflow'].color == green
    assert TEXT_PRIMARY in other_group.kpis['cashflow'].value.styleSheet()
    page.close()


def test_fixed_company_metrics_have_no_extra_picker_and_keep_correct_modes():
    page = _loaded_page()
    assert not hasattr(page, 'metric_menus')
    assert page.metric_slots == ('cashflow', 'company-value', 'popularity', 'monthly-ticket')
    for group in page.company_dashboard.groups.values():
        assert set(group.panels) == set(page.metric_slots)
        for key, panel in group.panels.items():
            assert not hasattr(panel, 'metric_menu_button')
            assert panel._allowed_modes == (('trend-bar',) if key == 'cashflow' else ('line',))
            assert panel.mode_selector is None
            assert panel.result.query.metric == key
    page.close()

def test_company_card_rejects_legacy_area_preference_after_refresh(tmp_path):
    settings = QSettings(str(tmp_path / 'legacy.ini'), QSettings.Format.IniFormat)
    settings.setValue('statistics/chart_style', 'area')
    settings.setValue('statistics/view/company-value', 'area')
    app = QApplication.instance() or QApplication([])
    page = StatisticsPage(settings)
    page.set_session(session())
    _wait_snapshot(app, page)
    panel = page.company_dashboard.groups['a'].panels['company-value']
    assert panel.mode == 'line'
    assert panel.mode_selector is None
    page._render_company()
    assert page.company_dashboard.groups['a'].panels['company-value'].mode == 'line'
    page.close()


def test_satisfaction_picker_is_between_kpis_and_charts_and_synced():
    page = _loaded_page()
    page.show()
    QApplication.processEvents()
    left = page.company_dashboard.groups['a']
    right = page.company_dashboard.groups['b']
    picker_y = left.satisfaction_combo.mapTo(left, QPoint(0, 0)).y()
    assert left.kpi_host.y() < picker_y < left.chart_host.y()
    right.satisfaction_combo.setCurrentIndex(right.satisfaction_combo.findData('satisfaction-cost'))
    assert page.satisfaction_combo.currentData() == 'satisfaction-cost'
    assert page.company_dashboard.groups['a'].kpis['satisfaction-speed'].title.text() == '费用满意度'
    page.close()


def test_empty_alerts_do_not_take_company_chart_space(tmp_path):
    app = QApplication.instance() or QApplication([])
    page = StatisticsPage(QSettings(str(tmp_path / 'empty-alerts.ini'), QSettings.Format.IniFormat))
    page.set_session(session())
    _wait_snapshot(app, page)
    assert not page.snapshot.alerts
    from stats_alerts import AlertsPanel
    assert not page.findChildren(AlertsPanel)
    assert not hasattr(page, 'alerts_host')
    page.close()


def test_period_mode_filters_each_company_and_queries_previous_interval():
    page = _loaded_page()
    page.analysis_mode_control.setCurrentKey('period')
    _wait_snapshot(QApplication.instance(), page)
    assert page.snapshot.filters.comparison == (datetime(2024, 1, 1), datetime(2024, 1, 8))
    assert page.compare_field.isVisibleTo(page)
    for company_id, group in page.company_dashboard.groups.items():
        assert all({owner for owner, _ in panel.result.series} <= {company_id}
                   and {owner for owner, _ in panel.result.comparison} <= {company_id}
                   for panel in group.panels.values())
    page.close()


def test_previous_complete_day_uses_simulation_date():
    page = _loaded_page()
    page.range_combo.setCurrentIndex(page.range_combo.findData('previous_full_day'))
    _wait_snapshot(QApplication.instance(), page)
    assert page.snapshot.filters.start == datetime(2024, 1, 14)
    assert page.snapshot.filters.end == datetime(2024, 1, 15)
    page.close()


def test_single_company_four_charts_fit_primary_window_without_vertical_scroll():
    app = QApplication.instance() or QApplication([])
    data = session()
    data['companies'] = data['companies'][:1]
    page = StatisticsPage()
    page.resize(1600, 1000)
    page.show()
    page.set_session(data)
    _wait_snapshot(app, page)
    app.processEvents()
    assert page.scroll.verticalScrollBar().maximum() == 0
    page.close()


def test_narrow_two_company_content_has_no_horizontal_scroll():
    app = QApplication.instance() or QApplication([])
    page = StatisticsPage()
    page.resize(840, 560)
    page.show()
    page.set_session(session())
    _wait_snapshot(app, page)
    app.processEvents()
    assert page.scroll.horizontalScrollBar().maximum() == 0
    page.close()


def test_tabs_route_export_target_without_changing_snapshot():
    page = _loaded_page()
    snapshot = page.snapshot
    page.tab_bar.setCurrentItem('network')
    assert page.export_target() is page.network_dashboard
    page.tab_bar.setCurrentItem('city')
    assert page.export_target() is page.city_host
    assert page.snapshot is snapshot
    page.close()


def test_calendar_picker_includes_end_day_and_rejects_reverse_range():
    from stats_range_picker import RangePicker
    QApplication.instance() or QApplication([])
    picker = RangePicker(datetime(2024, 2, 19), datetime(2024, 2, 26))
    picker.start_edit.setDateTime(datetime(2024, 2, 19))
    picker.end_edit.setDateTime(datetime(2024, 2, 25))
    assert picker.selected_range() == (datetime(2024, 2, 19), datetime(2024, 2, 26))
    picker.start_edit.setDateTime(datetime(2024, 2, 28))
    assert picker.selected_range() is None
    assert not picker.apply_button.isEnabled()
    picker.close()


def test_calendar_picker_places_start_and_end_side_by_side():
    from stats_range_picker import RangePicker
    app = QApplication.instance() or QApplication([])
    picker = RangePicker(datetime(2024, 2, 19), datetime(2024, 2, 26))
    picker.show()
    app.processEvents()
    assert picker.start_edit.y() == picker.end_edit.y()
    assert picker.apply_button.isVisibleTo(picker)
    picker.close()


def test_timed_calendar_picker_uses_exact_exclusive_end():
    from stats_range_picker import RangePicker
    QApplication.instance() or QApplication([])
    picker = RangePicker(datetime(2024, 2, 19, 7, 30), datetime(2024, 2, 20, 9, 15))
    assert picker.time_toggle.isChecked()
    assert picker.selected_range() == (datetime(2024, 2, 19, 7, 30),
                                       datetime(2024, 2, 20, 9, 15))
    picker.close()


def test_threshold_dialog_uses_fluent_actions(monkeypatch, tmp_path):
    from qfluentwidgets import PrimaryPushButton, PushButton
    QApplication.instance() or QApplication([])
    from frontend.latest_info_alerts import LatestInfoAlertsPanel
    page = LatestInfoAlertsPanel(QSettings(str(tmp_path / 'threshold.ini'), QSettings.Format.IniFormat))
    dialogs = []
    monkeypatch.setattr(QDialog, 'exec', lambda dialog: dialogs.append(dialog) or QDialog.DialogCode.Rejected)
    page._show_thresholds()
    assert len(dialogs) == 1
    assert len(dialogs[0].findChildren(PrimaryPushButton)) == 1
    assert len(dialogs[0].findChildren(PushButton)) >= 2
    page.close()


def test_statistics_shell_has_file_header_and_live_actions(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    import desktop_app
    from PySide6.QtCore import QSettings
    from report_model import load_session
    monkeypatch.setattr(desktop_app, 'QSettings',
                        lambda *_: QSettings(str(tmp_path / 'shell.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    window = desktop_app.MainWindow()
    data = load_session(Path(__file__).resolve().parents[1] / 'exports', '望春市_test_运行时')
    data.update(history=[], save_path='测试存档.save', save_key='stats-header')
    window.on_completed(data)
    window.navigate(2)
    window.show()
    app.processEvents()
    # The shared header shows the save, opens files and carries every export.
    assert window.header.isVisibleTo(window) and window.header.title.text() == '统计数据'
    assert window.header.save_chip.name.accessibleName() == '测试存档.save'
    assert window.header.save_chip.name.toolTip() == ''
    assert window.header.open_button.isVisibleTo(window)
    assert window.header.export_button.isEnabled()
    window._refresh_exports()
    assert 'stats-report' in window.header.export_actions
    window.close()


def test_statistics_header_and_pivot_share_wide_row_but_wrap_on_narrow_window(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    import desktop_app
    from PySide6.QtCore import QSettings
    monkeypatch.setattr(desktop_app, 'QSettings',
                        lambda *_: QSettings(str(tmp_path / 'responsive.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    window = desktop_app.MainWindow()
    window.navigate(2)
    window.resize(1440, 960)
    window.show()
    app.processEvents()
    tabs = window.statistics_page.tab_bar
    for size in ((1440, 960), (980, 680), (2560, 1440)):
        window.resize(*size)
        app.processEvents()
        assert window.header.isAncestorOf(tabs) and tabs.isVisibleTo(window)
        if size[0] < 1000:
            assert window.header._stacked_tabs
            assert window.header.height() == 106
        else:
            assert not window.header._stacked_tabs
            assert window.header.height() == 64
    window.close()


def test_filter_padding_tracks_page_width_without_shrinking_controls():
    QApplication.instance() or QApplication([])
    page = StatisticsPage()
    control_minimum = page.range_combo.minimumHeight()
    page.reflow(1208)
    assert page.filter_layout.contentsMargins().top() == 10
    assert page.filter_layout.spacing() == 6
    page.reflow(2328)
    assert page.filter_layout.contentsMargins().top() >= 16
    assert page.range_combo.minimumHeight() == control_minimum
    page.close()
