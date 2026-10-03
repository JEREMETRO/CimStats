import os
import pytest
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QSettings
from qfluentwidgets import CardWidget, CheckableMenu, ComboBox as FluentComboBox, NavigationInterface, PrimaryPushButton, SwitchButton
from statistics_page import StatisticsPage
from stats_style import initialize_theme


def _wait_home(window):
    from test_latest_info_integration import wait_for
    assert QApplication.instance().platformName() == 'offscreen'
    wait_for(QApplication.instance(), lambda: window.latest_info_controller.snapshot is not None)


def _page(monkeypatch):
    return StatisticsPage


def test_theme_initializes_light_fluent_app():
    app = QApplication.instance() or QApplication([])
    initialize_theme(app)
    from PySide6.QtGui import QFontInfo
    from qfluentwidgets import qconfig
    from qfluentwidgets import isDarkTheme
    from qfluentwidgets import themeColor
    assert not isDarkTheme()
    assert QFontInfo(app.font()).family() == 'Microsoft YaHei UI'
    assert qconfig.get(qconfig.fontFamilies) == ['Microsoft YaHei UI']
    assert themeColor().name() == '#0067c0'
    assert app.font().pixelSize() == 14


def test_company_groups_reflow_at_content_breakpoints(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    page = _page(monkeypatch)(QSettings(str(tmp_path / 'groups.ini'), QSettings.Format.IniFormat))
    assert isinstance(page.boards[0], CardWidget)
    assert isinstance(page.grain_combo, FluentComboBox)
    from stats_alerts import AlertsPanel
    assert not page.findChildren(AlertsPanel)
    assert isinstance(page.export_button, PrimaryPushButton)
    assert isinstance(page.company_menu, CheckableMenu)
    assert not hasattr(page, 'alerts_host')
    page.set_session({'history': [], 'simulation_time': '2024-01-15 10:30:00',
                      'companies': [{'公司标识': 'a', '公司名称': 'A'},
                                    {'公司标识': 'b', '公司名称': 'B'}]})
    app = QApplication.instance()
    deadline = time.monotonic() + 10
    while page.snapshot is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert page.snapshot is not None
    for width, expected_columns in ((1450, 2), (1100, 2), (680, 1), (1450, 2)):
        page.reflow(width)
        page.company_dashboard.reflow(width - 40, 0)
        groups = list(page.company_dashboard.groups.values())
        assert page.company_dashboard.group_grid.getItemPosition(
            page.company_dashboard.group_grid.indexOf(groups[1]))[1] == expected_columns - 1
        assert page.filter_card.parentWidget() is page
    page.close()


def test_company_default_distributes_chart_height_from_visible_viewport(monkeypatch):
    app = QApplication.instance() or QApplication([])
    page = StatisticsPage()
    page.set_session({'history': [], 'simulation_time': '2024-01-15 10:30:00',
                      'companies': [{'公司标识': 'a', '公司名称': 'A'},
                                    {'公司标识': 'b', '公司名称': 'B'}]})
    deadline = time.monotonic() + 10
    while len(page.company_dashboard.groups) != 2 and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert len(page.company_dashboard.groups) == 2
    page.company_dashboard.reflow(1168, 734)
    assert all(group.height() <= 734 for group in page.company_dashboard.groups.values())
    expanded_heights = [panel.minimumHeight()
                        for group in page.company_dashboard.groups.values()
                        for panel in group.panels.values()]
    assert len(set(expanded_heights)) == 1
    assert 0 < expanded_heights[0] < 734 // 2
    page.company_dashboard.reflow(1168, 600)
    assert all(group.height() <= 600 for group in page.company_dashboard.groups.values())
    assert all(0 < panel.minimumHeight() < expanded_heights[0]
               for group in page.company_dashboard.groups.values()
               for panel in group.panels.values())
    page.close()


def test_range_summary_and_calendar_dialog_do_not_overflow():
    app = QApplication.instance() or QApplication([])
    page = StatisticsPage()
    page.set_session({'history': [], 'simulation_time': '2024-01-10 12:00:00', 'companies': []})
    for width in (740, 1200):
        page.resize(width, 900)
        page.show()
        app.processEvents()
        assert '2024-01-01 00:00' in page.range_summary.text()
        assert '2024-01-08 00:00' in page.range_summary.text()
        assert page.scroll.horizontalScrollBar().maximum() == 0
    page.close()


def test_overview_flow_tracks_sidebar_width_without_window_resize(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    import desktop_app
    from PySide6.QtCore import QPoint
    monkeypatch.setattr(desktop_app, 'QSettings',
                        lambda *args: QSettings(str(tmp_path / 'sidebar.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    window = desktop_app.MainWindow()
    window.resize(1200, 900)
    window.show()
    from qfluentwidgets import (ComboBox, DropDownPushButton, LineEdit, TableWidget,
                                TabWidget)
    from PySide6.QtGui import QFontInfo
    assert isinstance(window.company_combo, ComboBox)
    assert isinstance(window.mode_combo, ComboBox)
    assert isinstance(window.query, LineEdit)
    assert isinstance(window.line_company, ComboBox)
    assert isinstance(window.line_mode, ComboBox)
    assert isinstance(window.line_table, TableWidget)
    from line_schedule_view import SchedulePanel
    assert isinstance(window.schedule_panel, SchedulePanel)
    assert isinstance(window.line_columns_button, DropDownPushButton)
    assert isinstance(window.fact_menu_button, DropDownPushButton)
    from stats_typography import emphasis_families
    allowed = set(emphasis_families(12) + emphasis_families(16) + emphasis_families(24))
    assert all(QFontInfo(child.font()).family() in allowed
               for child in window.findChildren(QWidget) if child.isVisible())
    for collapsed in (True, False, True):
        window.set_sidebar_collapsed(collapsed)
        for _ in range(5):
            app.processEvents()
        page = window.latest_info_page
        assert len(page.metric_cards) == 13 and len(page.highlights) == 4
        bottom = max(card.mapTo(page.board, QPoint()).y() + card.height()
                     for card in (*page.metric_cards.values(), *page.highlights))
        top = page.trend.mapTo(page.board, QPoint()).y()
        assert top >= bottom
        assert page.scroll.horizontalScrollBar().maximum() == 0
    window.close()


def test_line_details_scroll_and_tabs_replace_cleanly(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    import desktop_app
    from report_model import DAY_GROUPS, load_session
    monkeypatch.setattr(desktop_app, 'QSettings',
                        lambda *args: QSettings(str(tmp_path / 'lines.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    window = desktop_app.MainWindow()
    data = load_session(Path(__file__).resolve().parents[1] / 'exports', '望春市_test_运行时')
    if not data['lines']:
        pytest.skip('Local exported-save fixture is unavailable')
    data.update(history=[], save_path='lines.save', save_key='lines')
    window.on_completed(data)
    window.resize(1600, 900)
    window.show()
    window.navigate(1)
    window.line_clicked(0, 0)
    for _ in range(5):
        app.processEvents()
    previous_cards = list(window.fact_cards)
    window.show_line(window._selected_line)
    for _ in range(5): app.processEvents()
    assert window.schedule_panel.day_groups == tuple(window._selected_line.get('日组', window._selected_line['班次']))
    assert all(card.isHidden() for card in previous_cards)
    assert len(window.fact_cards) == 9
    for width, height in ((1600, 900), (1024, 768), (920, 680)):
        window.resize(width, height)
        for _ in range(5): app.processEvents()
        for button in (window.export_line_button, window.export_company_button):
            assert button.visibleRegion().boundingRect().size() == button.size()
        assert all(not card.isHidden() for card in window.fact_cards)
        assert all(card.height() == 86 for card in window.fact_cards)
        assert len(window.schedule_panel.matrix.entries) == window.schedule_panel.summary['count']
    window.close()


def test_long_duplicate_company_names_wrap_without_horizontal_overflow():
    app = QApplication.instance() or QApplication([])
    initialize_theme(app)
    name = '滨海市特别长的公共交通运营集团有限公司城市服务事业部'
    companies = [{'公司标识': '76561198362520556', '公司名称': name},
                 {'公司标识': '76561198845688243', '公司名称': name}]
    page = StatisticsPage()
    page.resize(1512, 803)
    page.show()
    page.set_session({'history': [], 'simulation_time': '2024-01-15 10:30:00',
                      'companies': companies})
    deadline = time.monotonic() + 10
    while page.snapshot is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert page.snapshot is not None
    app.processEvents()
    groups = list(page.company_dashboard.groups.values())
    assert len(groups) == 2
    assert all(name in group.name_label.toolTip() for group in groups)
    assert all('765611' in group.full_name for group in groups)
    assert page.scroll.widget().width() <= page.scroll.viewport().width()
    page.close()


def test_session_selects_all_and_rejects_old_result(monkeypatch):
    app = QApplication.instance() or QApplication([])
    Page = _page(monkeypatch)
    page = Page()
    page.set_session({'history': [], 'simulation_time': '2024-01-10 12:00:00',
                      'companies': [{'公司标识': 'a', '公司名称': '同名'},
                                    {'公司标识': 'b', '公司名称': '同名'}]})
    assert page.selected_companies() == ('a', 'b')
    assert page._range_window == (datetime(2024, 1, 1), datetime(2024, 1, 8))
    assert page.compare_combo.currentData() == 'previous'
    old = page.token
    page.clear_session()
    page._receive(old, SimpleNamespace(results={}, breakdowns={}, alerts=[]))
    assert page.snapshot is None
    assert not page.export_button.isEnabled()
    page.close()


def test_export_signal_and_threshold_query(monkeypatch):
    QApplication.instance() or QApplication([])
    page = _page(monkeypatch)()
    requested = []
    page.export_requested.connect(lambda: requested.append(True))
    page.export_button.click()
    assert requested == []
    page.set_session({'history': [], 'simulation_time': '2024-01-10 12:00:00', 'companies': []})
    page._receive(page.token, SimpleNamespace(results={}, breakdowns={}, alerts=[]))
    page.export_button.click()
    assert requested == [True]
    page.set_thresholds((4, 18, 90))
    assert page.thresholds == (4, 18, 90)
    page.close()


def test_filter_change_invalidates_snapshot_before_debounce(monkeypatch):
    QApplication.instance() or QApplication([])
    page = _page(monkeypatch)()
    page.set_session({'history': [], 'simulation_time': '2024-01-10 12:00:00', 'companies': []})
    snapshot = SimpleNamespace(results={}, breakdowns={}, alerts=[])
    page._receive(page.token, snapshot)
    old = page.token
    page.grain_combo.setCurrentIndex(0)
    assert page.token > old
    assert page.snapshot is None
    assert not page.export_button.isEnabled()
    page._receive(old, snapshot)
    assert page.snapshot is None
    page.close()


def test_tile_formats_units_and_keeps_coefficient_two_decimals(monkeypatch):
    QApplication.instance() or QApplication([])
    page = _page(monkeypatch)()
    from statistics_model import Bucket, Metric, Result, Query
    start, end = datetime(2024, 1, 3), datetime(2024, 1, 4)
    bucket = Bucket(start, end, __import__('decimal').Decimal('7'), True, False, end, 7, 0, 24)
    result = Result(Query('linecount', ('a',), '__total__', start, end, 'day'),
                    Metric('线路数', 'company', 'stock', '条'), {('a', '__total__'): [bucket]}, {}, (start, end), None)
    page._tile_value(page.service_tiles['linecount'], result, {'a': 'A'})
    assert page.service_tiles['linecount'].value.text() == '7 条'
    coefficient = Result(result.query, Metric('平均换乘系数', 'company', 'coefficient', ''),
                         {('a', '__total__'): [Bucket(start, end, __import__('decimal').Decimal('2.5'), True, False, end, 5, 2, 24)]}, {}, (start, end), None)
    page._tile_value(page.transfer_tile, coefficient, {'a': 'A'}, coefficient=True)
    assert page.transfer_tile.value.text() == '2.50'
    page.close()


def test_threshold_preferences_survive_page_recreation(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / 'prefs.ini'), QSettings.Format.IniFormat)
    Page = _page(monkeypatch)
    page = Page(settings)
    page.set_thresholds((3, 15, 75))
    page.close()
    again = Page(settings)
    assert again.thresholds == (3, 15, 75)
    again.close()


def test_satisfaction_and_city_metric_preferences_survive_recreation(tmp_path):
    QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / 'choices.ini'), QSettings.Format.IniFormat)
    page = StatisticsPage(settings)
    page.satisfaction_combo.setCurrentIndex(page.satisfaction_combo.findData('satisfaction-cost'))
    page.city_dashboard.set_curves(('平均', 'WhiteCollar'))
    page.close()
    again = StatisticsPage(settings)
    assert again.satisfaction_combo.currentData() == 'satisfaction-cost'
    assert again.city_dashboard.selected_curves == ('平均', 'WhiteCollar')
    again.set_session({'history': [], 'simulation_time': '2024-01-15 10:30:00',
                       'companies': [{'公司标识': 'a', '公司名称': 'A'}]})
    deadline = time.monotonic() + 10
    while again.snapshot is None and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(.01)
    assert again.company_dashboard.groups['a'].kpis['satisfaction-speed'].title.text() == '费用满意度'
    again.satisfaction_combo.setCurrentIndex(again.satisfaction_combo.findData('satisfaction-quality'))
    assert again.company_dashboard.groups['a'].kpis['satisfaction-speed'].title.text() == '质量满意度'
    again.close()


def test_same_metric_charts_share_actual_axis_range_and_scale(tmp_path):
    app = QApplication.instance() or QApplication([])
    from test_dashboard_page import session
    from datetime import timedelta
    data = session()
    base = datetime(2024, 1, 1)
    for hour in range(336):
        for owner in ('a', 'b'):
            data['history'].append({'指标': 'company-value', '分组': 'net-cash',
                '公司标识': owner, '模拟时间': str(base + timedelta(hours=hour)),
                '值': str(1_000_000 + hour * 1_000), '分母': '0', '当前槽位': 'False'})
    page = StatisticsPage(QSettings(str(tmp_path / 'axis.ini'), QSettings.Format.IniFormat))
    page.set_session(data)
    deadline = time.monotonic() + 10
    while page.snapshot is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert page.snapshot is not None
    left = page.company_dashboard.groups['a'].panels['company-value']
    right = page.company_dashboard.groups['b'].panels['company-value']
    assert left.axis_spec == right.axis_spec
    assert left.axis_spec.scale > 1
    page.close()


def test_tiles_preserve_selected_company_and_city_group_when_values_are_missing():
    QApplication.instance() or QApplication([])
    from decimal import Decimal
    from statistics_model import Bucket, METRICS, Query, Result
    page = StatisticsPage()
    page.companies = [{'公司标识': 'a', '公司名称': 'A'},
                      {'公司标识': 'b', '公司名称': 'B'}]
    page._short_ids = {'a': '1', 'b': '2'}
    start, end = datetime(2024, 1, 3), datetime(2024, 1, 4)
    def bucket(value):
        return Bucket(start, end, value, True, False, end, None, None, 24)
    cash = Result(Query('cashflow', ('a', 'b'), '__total__', start, end, 'day'),
                  METRICS['cashflow'], {('a', '总计'): [bucket(Decimal('10'))]},
                  {}, (start, end), None)
    from company_dashboard import KpiCard
    first = KpiCard('现金流')
    second = KpiCard('现金流')
    first.set_result(cash, 'a')
    second.set_result(cash, 'b')
    assert first.value.text() == '10'
    assert first.unit.text() == '货币'
    assert second.value.text() == '—'

    from test_city_model import build, r
    city = build([r('economy', 'growth', 0, 0, 0)])
    page.city_dashboard.set_snapshot(city)
    assert page.city_tiles['population'].model.value is None
    assert set(page.city_trends['economy'].result.series) == {('', '经济增长率')}
    assert all(bucket.value is None for rows in page.city_trends['economy'].result.series.values() for bucket in rows)
    page.close()


def test_station_categories_keep_missing_rows_for_each_selected_company():
    QApplication.instance() or QApplication([])
    from decimal import Decimal
    from PySide6.QtWidgets import QLabel
    from statistics_model import Bucket, METRICS, Query, Result
    page = StatisticsPage()
    page._short_ids = {'a': '1', 'b': '2'}
    start, end = datetime(2024, 1, 3), datetime(2024, 1, 4)
    def bucket(value):
        return Bucket(start, end, value, True, False, end, None, None, 24)
    station = Result(Query('stopcount', ('a', 'b'), None, start, end, 'day'),
                     METRICS['stopcount'], {('a', 'bus'): [bucket(Decimal('4'))],
                                            ('b', 'bus'): [bucket(None)]},
                     {}, (start, end), None)
    tile = page.service_tiles['stopcount']
    page._stopcount_value(tile, station)
    assert [item.text() for item in tile.category_host.findChildren(QLabel)] == [
        '公交', '● 1', '4 个', '● 2', '—']
    page.close()


def test_city_mode_share_uses_three_total_modes_in_tile_and_chart():
    QApplication.instance() or QApplication([])
    from decimal import Decimal
    from test_city_model import build, r
    page = StatisticsPage()
    page.city_snapshot = build([r(name, 'A', 0, amount, 10) for name, amount in
        [('walking', 5), ('public-transport', 3), ('private-motoring', 2)]])
    page.snapshot = SimpleNamespace(results={}, breakdowns={})
    page._render_snapshot()
    tile = page.city_tiles['city-mode-share']
    assert [detail.title for detail in tile.model.details] == ['步行', '公共交通', '私家车']
    assert [detail.value for detail in tile.model.details] == [Decimal(50), Decimal(30), Decimal(20)]
    assert page.mode_panel.result is page.city_snapshot.pie_result
    assert len(page.mode_panel.result.series) == 3
    page.close()


def test_invalid_custom_window_clears_old_snapshot(monkeypatch):
    QApplication.instance() or QApplication([])
    page = _page(monkeypatch)()
    page.set_session({'history': [], 'simulation_time': '2024-01-10 12:00:00', 'companies': []})
    page._receive(page.token, SimpleNamespace(results={}, breakdowns={}, alerts=[]))
    page.analysis_mode = 'period'
    page.comparison_preset = 'custom'
    page._custom_comparison = (datetime(2024, 1, 4), datetime(2024, 1, 3))
    page._submit_query()
    assert page.snapshot is None
    assert not page.export_button.isEnabled()
    assert not page.workers
    page.close()


def test_main_window_sidebar_collapses_and_persists(monkeypatch, tmp_path):
    QApplication.instance() or QApplication([])
    _page(monkeypatch)
    existing = sys.modules.get('desktop_app')
    import desktop_app
    settings = QSettings(str(tmp_path / 'shell.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *_: settings)
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    window = desktop_app.MainWindow()
    assert isinstance(window.sidebar, NavigationInterface)
    assert [button.text() for button in window.nav_buttons] == ['最新信息', '线路查询', '统计数据']
    window.set_sidebar_collapsed(True)
    assert window.sidebar.width() < 100
    assert window._sidebar_collapsed
    window.close()
    another = desktop_app.MainWindow()
    assert another.sidebar.width() < 100
    another.show()
    another.set_sidebar_collapsed(False)
    QApplication.processEvents()
    assert another.sidebar.width() > 100
    another.close()
    if existing is None:
        sys.modules.pop('desktop_app', None)


def test_other_pages_filter_duplicate_names_by_stable_company_id(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    import desktop_app
    from report_model import load_session
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *_: QSettings(str(tmp_path / 'shell.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    data = load_session(Path(__file__).resolve().parents[1] / 'exports', '望春市_test_运行时')
    if not data['lines']:
        pytest.skip('Local exported-save fixture is unavailable')
    original = data['companies'][0]
    first_id = str(original['公司标识'])
    second_id = 'another-id'
    duplicate = dict(original, 公司标识=second_id)
    second_line = dict(data['lines'][0], 公司标识=second_id, key='other-line')
    data['companies'] = [original, duplicate]
    data['lines'] = [data['lines'][0], second_line]
    data.update(history=[], save_path='duplicate.save', save_key='duplicate')
    window = desktop_app.MainWindow()
    window.on_completed(data)
    window.company_combo.setCurrentIndex(1)
    _wait_home(window)
    assert window.company_combo.currentData() == first_id
    assert window.latest_info_page.metric_cards['line-count'].value.text() == '1'
    window.company_combo.setCurrentIndex(2)
    _wait_home(window)
    assert window.company_combo.currentData() == second_id
    assert window.latest_info_page.metric_cards['line-count'].value.text() == '1'
    window.line_company.setCurrentIndex(2)
    assert [row['公司标识'] for row in window.filtered_lines()] == [second_id]
    window.close()


def test_other_pages_reflow_and_scroll_at_narrow_width(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    import desktop_app
    from report_model import load_session
    settings = QSettings(str(tmp_path / 'narrow.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *_: settings)
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    window = desktop_app.MainWindow()
    data = load_session(Path(__file__).resolve().parents[1] / 'exports', '望春市_test_运行时')
    if not data['lines']:
        pytest.skip('Local exported-save fixture is unavailable')
    data.update(history=[], save_path='narrow.save', save_key='narrow')
    window.on_completed(data)
    _wait_home(window)
    window.resize(920, 680)
    window.show()
    app.processEvents()
    assert window.sidebar.width() < 100
    window.navigate(0)
    assert window.latest_info_page.scroll.verticalScrollBar().maximum() > 0
    assert len(window.latest_info_page.metric_cards) == 13
    # Structure is the default view; ranking rows are created on selection.
    passengers = window.latest_info_page.passengers
    assert passengers.capture_state()['view'] == 'structure'
    assert passengers.visible_mode_rows()
    passengers.show_ranking()
    assert passengers.visible_ranking_rows()
    window.navigate(1)
    window.line_clicked(0, 0)
    for _ in range(5): app.processEvents()
    assert window._selected_line is not None
    assert window.lines_page.right_scroll.verticalScrollBar().maximum() > 0
    assert window.lines_page.left.width() == 260
    window.close()
