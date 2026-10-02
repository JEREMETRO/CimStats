"""Integration regressions for replacement dashboard; removed tables are not retained."""
import os
import sys
import time
import pytest
from datetime import datetime as D, timedelta
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtCore import QSettings, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QLabel
from statistics_page import StatisticsPage


def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def qt_lifecycle():
    application = app()
    yield
    # Delete QtCharts while their Python wrappers and Qt event loop are alive.
    for widget in application.topLevelWidgets():
        if isinstance(widget, StatisticsPage):
            widget.close()
            widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()


def session():
    start = D(2024, 1, 1)
    rows = []
    for hour in range(336):
        for owner in ('a', 'b'):
            for metric, group, value in [('cashflow', 'bus', 123400),
                                          ('transport-by-type', 'bus', 30),
                                          ('transport-by-group', 'Student', 30),
                                          ('trip-types', 'one-zone', 10)]:
                rows.append({'指标': metric, '分组': group, '公司标识': owner,
                             '模拟时间': str(start + timedelta(hours=hour)),
                             '值': str(value), '分母': '0', '当前槽位': 'False'})
    return {'history': rows, 'simulation_time': '2024-01-15 12:00:00',
            'companies': [{'公司标识': 'a', '公司名称': '同名'}, {'公司标识': 'b', '公司名称': '同名'}],
            'save_key': 'fixture'}


def loaded(tmp_path):
    app()
    page = StatisticsPage(QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat))
    page.set_session(session())
    deadline = time.monotonic() + 10
    while page.snapshot is None and time.monotonic() < deadline:
        app().processEvents()
        time.sleep(.01)
    assert page.snapshot is not None
    return page


def test_three_tabs_default_complete_week_and_all_companies(tmp_path):
    page = loaded(tmp_path)
    assert len(page.tab_bar.items) == 3
    assert len(page.boards) == 3
    assert page.snapshot.filters.companies == ('a', 'b')
    assert page.snapshot.filters.start == D(2024, 1, 8)
    assert page.snapshot.filters.end == D(2024, 1, 15)
    assert page.snapshot.filters.comparison is None
    assert page.snapshot.filters.grain == 'day'
    assert all('[' in action.text() for action in page.company_menu.actions())
    assert not hasattr(page, 'raw_table')
    assert not hasattr(page, 'table')
    page.close()


def test_change_invalidates_result_before_debounce_and_clear_rejects_old_token(tmp_path):
    page = loaded(tmp_path)
    snapshot, token = page.snapshot, page.token
    page.schedule_query()
    assert page.token != token
    assert page.snapshot is None
    assert not page.export_button.isEnabled()
    page._receive(token, snapshot)
    assert page.snapshot is None
    page.clear_session()
    page._receive(page.token - 1, snapshot)
    assert page.snapshot is None
    assert all(panel.result is None for panel in page.passenger_panels.values())
    page.close()


def test_invalid_window_clears_charts_and_alert_snapshot(tmp_path):
    page = loaded(tmp_path)
    seen = []
    page.snapshot_changed.connect(seen.append)
    page.range_preset = 'custom'
    page._custom_window = (D(2024, 1, 16), D(2024, 1, 15))
    page._range_window = page._custom_window
    page._submit_query()
    assert page.snapshot is None
    assert not page.export_button.isEnabled()
    assert all(panel.result is None for panel in page.passenger_panels.values())
    assert seen and seen[-1] is None
    page.close()


def test_three_independent_passenger_modes_and_coefficient(tmp_path):
    page = loaded(tmp_path)
    assert [p.mode for p in page.passenger_panels.values()] == ['line', 'pie', 'bar']
    for panel in page.passenger_panels.values():
        original = panel.result
        for mode in ('summary', 'bar', 'line', 'pie'):
            panel.set_mode(mode)
            assert panel.result is original
        panel.set_mode('summary')
    assert page.passenger_panels['transport-by-type'].summary_values['a'] == 5040
    assert page.passenger_panels['trip-types'].summary_values['a'] == 1680
    assert '3.00' in page.transfer_tile.value.text()
    page.close()


def test_company_selection_none_does_not_restore_all(tmp_path):
    page = loaded(tmp_path)
    for action in page.company_menu.actions():
        action.setChecked(False)
    page._submit_query()
    deadline = time.monotonic() + 10
    while page.snapshot is None and time.monotonic() < deadline:
        app().processEvents()
        time.sleep(.01)
    assert page.snapshot is not None
    assert not page.snapshot.results['cashflow'].series
    page.close()


def test_no_explanatory_labels_and_only_custom_comparison_inputs(tmp_path):
    page = loaded(tmp_path)
    assert page.compare_field.isHidden()
    assert not hasattr(page, 'compare_start')
    banned = ('口径', '字段不足', '建议', '无法可靠', '不强制', '已记录部分', '原始小时', '聚合明细')
    assert not [(w.text(), word) for w in page.findChildren(QLabel) for word in banned if word in w.text()]
    page.analysis_mode_control.setCurrentKey('period')
    assert not page.compare_field.isHidden()
    page.close()


def test_close_stops_pending_workers(tmp_path):
    page = loaded(tmp_path)
    page.schedule_query()
    page._submit_query()
    workers = list(page.workers)
    page.close()
    assert all(not worker.isRunning() for worker in workers)
