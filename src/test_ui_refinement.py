import sys, time
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from qfluentwidgets import TransparentToolButton
from statistics_page import StatisticsPage
import desktop_app


def test_filter_expander_is_accessible_icon(qt_application):
    page = StatisticsPage()
    assert isinstance(page.expand_filters_button, TransparentToolButton)
    assert page.expand_filters_button.accessibleName() == '收起筛选'
    assert page.expand_filters_button.toolTip()


def test_summary_collapse_keeps_data_and_aligns_companies(qt_application):
    page = StatisticsPage()
    page.resize(1400, 940); page.show()
    page.set_session({'history': [], 'simulation_time': '2013-04-10 23:59:22',
                      'companies': [{'公司标识': 'a', '公司名称': 'A'}, {'公司标识': 'b', '公司名称': 'B'}]})
    deadline = time.monotonic() + 10
    while len(page.company_dashboard.groups) != 2 and time.monotonic() < deadline:
        qt_application.processEvents(); time.sleep(.01)
    board = page.company_dashboard
    snapshot, token = page.snapshot, page.token
    groups = list(board.groups.values())
    panels = [p for g in groups for p in g.panels.values()]
    groups[0].summary_button.click()
    for _ in range(30): qt_application.processEvents()
    assert all(g.kpi_host.isHidden() for g in groups)
    assert all(p.isVisible() for p in panels)
    assert page.snapshot is snapshot and page.token == token
    assert groups[0].chart_host.y() == groups[1].chart_host.y()
    groups[1].summary_button.click()
    for _ in range(30): qt_application.processEvents()
    assert all(not g.kpi_host.isHidden() for g in groups)


def test_loading_overlay_estimated_progress_and_failure(qt_application, monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *a: QSettings(str(tmp_path/'prefs.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda s: None)
    monkeypatch.setattr(desktop_app.QMessageBox, 'critical', lambda *a: None)
    window = desktop_app.MainWindow(); window.show()
    window.loading_overlay.begin('读取存档对象')
    window.on_progress(10, '读取存档对象')
    assert window.loading_overlay.isVisible()
    assert window.loading_overlay.percent.text() == '阶段进度：0%'
    window.loading_overlay.update_progress('读取存档对象', 41, estimated=True)
    window.loading_overlay.update_progress('准备图表')
    assert window.loading_overlay.percent.text() == '预计进度：41%'
    assert window.loading_overlay.read.text() == '当前阶段：准备图表'
    window.on_failed('验证失败')
    assert not window.loading_overlay.isVisible()
    assert '验证失败' in window.status_label.text()
    assert window.statusBar().isHidden()


def test_filter_actions_adjacent_and_period_fields_balanced(qt_application):
    from PySide6.QtCore import QPoint
    page = StatisticsPage(); page.resize(1400, 960); page.show()
    page.compare_field.show(); page._layout_signature = None; page.reflow(1400)
    for _ in range(20): qt_application.processEvents()
    fields = page._fields
    positions = [page.toolbar_grid.getItemPosition(page.toolbar_grid.indexOf(f)) for f in fields[:5]]
    assert positions[0] == (0, 0, 1, 1)
    assert positions[1] == (0, 1, 1, 1)
    assert positions[3] == (0, 3, 1, 1)
    confirm = page.confirm_filters_button.mapTo(page.filter_card, QPoint())
    export = page.export_button.mapTo(page.filter_card, QPoint())
    assert page.confirm_filters_button is page.expand_filters_button
    assert confirm.y() == 8
    assert confirm.x() > export.x()
    assert page.confirm_filters_button.height() == page.export_button.height() == 32


def test_network_summary_collapse_preserves_tiles_and_options(qt_application):
    from network_dashboard import NetworkSummaryCard
    from network_model import NetworkSummary, NetworkOptions
    card = NetworkSummaryCard(NetworkSummary(None, '总体', ()), NetworkOptions(), '#1677ff')
    original = card.summary
    card.set_summary_collapsed(True)
    assert card.tile_host.isHidden()
    assert card.summary_button.accessibleName() == '展开数据摘要'
    card.set_summary_collapsed(False)
    assert not card.tile_host.isHidden()
    assert card.summary is original


def test_company_summary_is_a_separate_card_from_charts(qt_application):
    from company_dashboard import CompanyGroup
    group = CompanyGroup('a', 'A', '#1677ff', charts=True)
    assert group.kpi_host.parentWidget() is group.summary_card
    assert group.summary_button.parentWidget() is group.summary_card
    assert group.chart_host.parentWidget() is group
    assert 'background: transparent' in group.styleSheet()


def test_statistics_scroll_content_does_not_paint_gray_background(qt_application):
    page = StatisticsPage()
    for scroll in (page.scroll, page.network_scroll, page.city_scroll):
        assert not scroll.viewport().autoFillBackground()
        assert not scroll.widget().autoFillBackground()


def test_period_filter_reflows_across_two_column_breakpoint(qt_application):
    page = StatisticsPage(); page.compare_field.show()
    page.reflow(1100)
    wide = page.toolbar_grid.getItemPosition(page.toolbar_grid.indexOf(page._fields[0]))
    page.reflow(900)
    narrow = page.toolbar_grid.getItemPosition(page.toolbar_grid.indexOf(page._fields[0]))
    assert wide == (0, 0, 1, 1)
    assert narrow == (0, 0, 1, 1)
    page.reflow(1100)
    assert page.toolbar_grid.getItemPosition(page.toolbar_grid.indexOf(page._fields[0])) == wide


def test_satisfaction_picker_replaces_the_kpi_title(qt_application):
    from company_dashboard import CompanyGroup
    group = CompanyGroup('a', 'A', '#1677ff', charts=True)
    tile = group.kpis['satisfaction-speed']
    assert group.satisfaction_combo.parentWidget() is tile.header_host
    assert tile.isAncestorOf(group.satisfaction_combo)
    assert tile.title.isHidden()
    assert group.satisfaction_toolbar is None
    assert group.satisfaction_combo.accessibleName() == '满意度维度'
    group.show(); qt_application.processEvents()
    assert group.satisfaction_combo.font().pixelSize() == group.kpis['cashflow'].title.font().pixelSize()
    assert group.satisfaction_combo.font().family() == group.kpis['cashflow'].title.font().family()
    from PySide6.QtGui import QPalette
    assert group.satisfaction_combo.palette().color(QPalette.ColorRole.ButtonText) == group.kpis['cashflow'].title.palette().color(QPalette.ColorRole.WindowText)


@pytest.mark.parametrize('mode', ['default', 'companies', 'period'])
@pytest.mark.parametrize('company_count', [1, 2])
@pytest.mark.parametrize('width', [820, 1440])
def test_satisfaction_title_picker_is_consistent_in_all_company_modes(qt_application, mode, company_count, width):
    page = StatisticsPage(); page.resize(width, 960); page.show()
    companies = [{'公司标识': str(i), '公司名称': f'公司{i}'} for i in range(company_count)]
    page.set_session({'history': [], 'simulation_time': '2013-04-10 23:59:22', 'companies': companies})
    page.analysis_mode_control.setCurrentKey(mode)
    deadline = time.monotonic() + 10
    while (page.snapshot is None or len(page.company_dashboard.groups) != company_count) and time.monotonic() < deadline:
        qt_application.processEvents(); time.sleep(.01)
    assert page.snapshot is not None
    assert page.company_toolbar.isHidden()
    assert page.company_dashboard.layout().indexOf(page.company_toolbar) == -1
    snapshot, token = page.snapshot, page.token
    for group in page.company_dashboard.groups.values():
        tile = group.kpis['satisfaction-speed']
        assert group.satisfaction_combo is not None
        assert group.satisfaction_combo.parentWidget() is tile.header_host
        assert tile.title.isHidden()
        assert group.satisfaction_combo.height() == tile.header_host.height() == 28
    first = next(iter(page.company_dashboard.groups.values()))
    first.satisfaction_combo.setCurrentIndex(first.satisfaction_combo.findData('satisfaction-cost'))
    qt_application.processEvents()
    assert page.satisfaction_combo.currentData() == 'satisfaction-cost'
    assert all(group.satisfaction_combo.currentData() == 'satisfaction-cost'
               for group in page.company_dashboard.groups.values())
    assert page.snapshot is snapshot and page.token == token
    page.analysis_mode_control.setCurrentKey('default')
    assert page.satisfaction_combo.currentData() == 'satisfaction-cost'
    page.close()


def test_kpi_icon_and_title_share_vertical_center(qt_application):
    from company_dashboard import KpiCard
    tile=KpiCard('现金流', metric_key='cashflow');tile.resize(220,72);tile.show()
    for _ in range(10):qt_application.processEvents()
    assert abs(tile.icon.geometry().center().y()-tile.title.geometry().center().y())<=1


def test_mica_reapplies_after_native_window_is_shown(qt_application, monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *a: QSettings(str(tmp_path/'mica.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda s: None)
    calls = []
    monkeypatch.setattr(desktop_app.MainWindow, '_enable_mica', lambda self: calls.append(self.isVisible()))
    window = desktop_app.MainWindow(); window.show()
    qt_application.processEvents()
    assert calls[-1] is True
    window.close()


def test_mica_uses_original_light_backdrop(qt_application, monkeypatch, tmp_path):
    import qframelesswindow
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *a: QSettings(str(tmp_path/'mica-alt.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda s: None)
    monkeypatch.setattr(desktop_app.QApplication, 'platformName', lambda: 'windows')
    calls = []
    class FakeEffect:
        def __init__(self, window): pass
        def setMicaEffect(self, hwnd, **options): calls.append(options)
    monkeypatch.setattr(qframelesswindow, 'WindowEffect', FakeEffect)
    window = desktop_app.MainWindow()
    assert calls[-1].get('isAlt') is False
    window.close()


def test_preparing_cancel_invalidates_query_even_before_parse_worker_finishes(qt_application, monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *a: QSettings(str(tmp_path/'cancel.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda s: None)
    window = desktop_app.MainWindow(); window.show()
    class FinishedWorker:
        def cancel(self): pass
        def isRunning(self): return False
    window.worker = FinishedWorker()
    window._awaiting_dashboards = True
    window.loading_overlay.begin('准备图表')
    token = window.statistics_page.token
    window.cancel_parse()
    assert window.statistics_page.token > token
    assert not window._awaiting_dashboards
    assert not window.loading_overlay.isVisible()
    window.worker = None; window.close()


def test_preparing_failure_invalidates_late_query_results(qt_application, monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *a: QSettings(str(tmp_path/'timeout.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda s: None)
    monkeypatch.setattr(desktop_app.QMessageBox, 'critical', lambda *a: None)
    window = desktop_app.MainWindow()
    window._awaiting_dashboards = True
    token = window.statistics_page.token
    window.on_failed('准备图表超时')
    assert window.statistics_page.token > token
    assert window.statistics_page.snapshot is None
    window.close()


def test_structured_progress_updates_estimate_without_showing_raw_json(qt_application, monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *a: QSettings(str(tmp_path/'structured.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda s: None)
    window = desktop_app.MainWindow()
    observed = []
    class Predictor:
        def observe(self, elapsed, details): observed.append(details)
        def update(self, elapsed, rss, stage): return 17
    window._progress_predictor = Predictor()
    window._parse_started = time.monotonic()
    before = window.status_label.text()
    window.on_parse_log('CIM2_PROGRESS {"lines": 7}')
    assert observed == [{'lines': 7}]
    assert window.status_label.text() == before
    assert window.loading_overlay.percent.text() == '预计进度：17%'
    window.on_parse_log('CIM2_PROGRESS invalid')
    assert window.status_label.text() == before
    window._progress_predictor.actual_progress = True
    window.on_parse_log('CIM2_PROGRESS {"event":"progress","phase":"history","done":3,"total":10}')
    assert window.loading_overlay.percent.text() == '阶段进度：17%'
    assert window.loading_overlay.read.text() == '当前阶段：读取历史记录：3/10'
    valid = list(observed)
    window.on_parse_log('CIM2_PROGRESS {"event":"progress","phase":"history","done":11,"total":10}')
    assert observed == valid
    before_read = window.loading_overlay.read.text()
    window.on_parse_log('CIM2_PROGRESS {"event":"progress","phase":"validation","done":0,"total":0}')
    assert observed == valid
    assert window.loading_overlay.read.text() == before_read
    window.on_parse_log('CIM2_PROGRESS {"event":"progress","phase":"validation","done":0,"total":2}')
    assert observed[-1]['done'] == 0 and observed[-1]['total'] == 2
    assert window.loading_overlay.read.text() == '当前阶段：校验输出：0/2'
    window.on_parse_log('CIM2_PROGRESS {"event":"progress","phase":"validation","done":2,"total":2}')
    assert observed[-1]['done'] == 2 and observed[-1]['total'] == 2
    assert window.loading_overlay.read.text() == '当前阶段：校验输出：2/2'
    assert window.status_label.text() == before
    window.close()


def test_filter_heights_action_widths_and_no_extra_status_row(qt_application, monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *a: QSettings(str(tmp_path/'sizes.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda s: None)
    window = desktop_app.MainWindow(); window.show(); window.navigate(2)
    qt_application.processEvents()
    page = window.statistics_page
    assert {control.height() for control in (page.company_selector, page.range_combo, page.grain_combo,
            page.mode_host, page.analysis_mode_control, page.network_mode_control)} == {36}
    assert page.export_button.width() == window.stats_open_button.width()
    assert window.status_label.isHidden()
    assert window.content_layout.indexOf(window.status_label) == -1
    window.close()


def test_parse_completion_waits_for_dashboard_readiness(qt_application, monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *a: QSettings(str(tmp_path/'ready.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda s: None)
    window = desktop_app.MainWindow(); window.show()
    window.loading_overlay.begin('读取存档')
    window.on_progress(100, '解析完成')
    assert window.loading_overlay.percent.text() != '100%'
    data = {'history': [], 'simulation_time': '2013-04-10 23:59:22',
            'save_path': 'ready.save', 'companies': [{'公司标识': 'a', '公司名称': 'A'}]}
    window.on_completed(data)
    window.worker_finished()
    assert window.loading_overlay.isVisible()
    deadline = time.monotonic() + 10
    while window.loading_overlay.isVisible() and time.monotonic() < deadline:
        qt_application.processEvents(); time.sleep(.01)
    assert window.statistics_page.snapshot is not None
    assert window.statistics_page.network_snapshot is not None
    assert not window.loading_overlay.isVisible()
    window.close()
