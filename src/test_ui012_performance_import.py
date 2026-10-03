"""Regression evidence for bounded queries, reusable surfaces and input recovery."""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'frontend')]
from statistics_model import HistoryStore, METRICS, QueryCancelled


def test_history_index_can_be_cancelled_during_construction():
    rows = [{'模拟时间': '2024-01-01 00:00:00', '指标': 'population', '值': '1'}] * 10000
    calls = 0
    def cancelled():
        nonlocal calls
        calls += 1
        return calls >= 3
    with pytest.raises(QueryCancelled):
        HistoryStore(rows, datetime(2024, 1, 2), cancelled=cancelled)
    assert calls == 3


def test_hour_query_visits_each_history_record_once():
    start = datetime(2024, 1, 1)
    store = HistoryStore([{'模拟时间': start + timedelta(hours=i), '指标': 'transport-by-type',
                           '公司标识': 'a', '分组': 'bus', '值': str(i)} for i in range(720)],
                         start + timedelta(hours=721))
    class Counted(list):
        visits = 0
        def __iter__(self):
            for row in super().__iter__():
                self.visits += 1
                yield row
    rows = Counted(store.series[('transport-by-type', 'a', 'bus')])
    result = store._buckets(rows, METRICS['transport-by-type'], start,
                            start + timedelta(hours=720), 'hour')
    assert [bucket.value for bucket in result] == list(range(720))
    assert rows.visits <= 720


def test_save_import_uses_native_dialog_only(monkeypatch, qt_application):
    import desktop_app
    from PySide6.QtWidgets import QFileDialog
    calls = []
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args, **kwargs: (calls.append((args, kwargs)) or ('', '')))
    owner = SimpleNamespace(start_parse=lambda path: pytest.fail('cancel must not parse'))
    desktop_app.MainWindow.open_dialog(owner)
    assert len(calls) == 1
    options = calls[0][0][5] if len(calls[0][0]) > 5 else calls[0][1].get('options', QFileDialog.Option(0))
    assert not options & QFileDialog.Option.DontUseNativeDialog
    from window_chrome import FluentFileDialog
    other = []
    monkeypatch.setattr(FluentFileDialog, '_choose', lambda *args: (other.append(args) or ('', '')))
    FluentFileDialog.getOpenFileName(filter='所有文件 (*)')
    FluentFileDialog.getSaveFileName(filter='Excel (*.xlsx)')
    FluentFileDialog.getExistingDirectory()
    assert len(other) == 3 and len(calls) == 1


def test_prepared_history_reaches_statistics_without_reindex(monkeypatch, qt_application):
    import statistics_page
    page = statistics_page.StatisticsPage()
    store = HistoryStore([], datetime(2024, 1, 2))
    monkeypatch.setattr(statistics_page, 'HistoryStore', lambda *a, **k: pytest.fail('UI thread reindexed history'))
    try:
        page.set_session({'simulation_time': '2024-01-02 00:00:00', 'companies': [], '_history_store': store})
        assert page.store is store
    finally:
        page.close()


def test_mouse_transparent_cover_does_not_own_touch(qt_application):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget
    from touch_input import install_touch_input
    install_touch_input(qt_application)
    cover = QWidget()
    cover.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    cover.show(); qt_application.processEvents()
    assert not cover.testAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
    cover.close()


def test_company_refresh_reuses_controls_and_clears_old_values(qt_application):
    from test_dashboard_page import session
    from dashboard_model import FilterState, build_dashboard
    from company_dashboard import CompanyDashboard, DEFAULT_SLOTS
    data = session()
    store = HistoryStore(data['history'], datetime(2024, 1, 15, 12))
    snapshot = build_dashboard(store, FilterState(('a', 'b'), datetime(2024, 1, 8), datetime(2024, 1, 15), 'day'))
    dashboard = CompanyDashboard()
    args = (snapshot, ('a', 'b'), {'a': 'A', 'b': 'B'}, {'a': '#123456', 'b': '#234567'},
            'default', 'satisfaction-speed', DEFAULT_SLOTS)
    dashboard.render(*args)
    groups = dict(dashboard.groups)
    panels = dict(groups['a'].panels)
    dashboard.render(*args)
    assert dashboard.groups == groups
    assert groups['a'].panels == panels
    assert dashboard.groups['a'].kpis['cashflow'].value.text() != '—'
    dashboard.clear()
    assert not dashboard.groups
    dashboard.close()
    dashboard.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_startup_stages_yield_to_events_and_keep_window_identity(monkeypatch, qt_application):
    from desktop_app import MainWindow
    from PySide6.QtCore import QTimer, QEventLoop
    from PySide6.QtTest import QTest
    window = MainWindow(defer_startup=True)
    original = int(window.winId())
    order = []
    errors = []
    from PySide6.QtCore import QMimeData, QPoint, QUrl
    from PySide6.QtGui import QDragEnterEvent
    from PySide6.QtCore import Qt
    stages = []
    for name in ('_prepare_content', '_build_shell', 'build_overview', 'build_lines', '_build_statistics', '_finish_ui'):
        step = getattr(window, name)
        def checked_step(callback=step, stage=name):
            callback()
            stages.append(stage)
            assert not window.acceptDrops()
            mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile('D:/missing.save')])
            drag = QDragEnterEvent(QPoint(50, 100), Qt.DropAction.CopyAction, mime,
                                   Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            qt_application.sendEvent(window, drag)
            assert not drag.isAccepted()
            QTest.keyClick(window, Qt.Key.Key_Tab)
            focused = qt_application.focusWidget()
            assert focused is None or window.titleBar.isAncestorOf(focused)
        monkeypatch.setattr(window, name, checked_step)
    loop = QEventLoop()
    def ready():
        order.append('ready')
        loop.quit()
    window.initialize_content_async(ready, lambda exc: (errors.append(exc), loop.quit()))
    QTimer.singleShot(0, lambda: order.append('responsive'))
    QTimer.singleShot(15000, loop.quit)
    loop.exec()
    assert not errors, errors
    assert order.index('responsive') < order.index('ready')
    assert window._content_ready and int(window.winId()) == original
    assert window.pages.count() == 3
    assert len(stages) == 6 and window.acceptDrops()
    window.close()


def test_opening_network_tab_reuses_current_query(monkeypatch, qt_application):
    from test_stats_fluent_page import _loaded_page
    import statistics_page
    page = _loaded_page()
    try:
        assert page.network_snapshot is not None
        network = page.network_snapshot
        monkeypatch.setattr(statistics_page, 'NetworkModelTask', lambda *a, **k: pytest.fail('duplicate network query'))
        page.tab_bar.setCurrentItem('network')
        assert page.network_snapshot is network
        assert page.network_dashboard.snapshot is network
    finally:
        page.close()


def test_actual_parse_progress_does_not_poll_process_tree(monkeypatch):
    import desktop_app
    from parse_progress import ParseProgressEstimator
    monkeypatch.setattr(desktop_app.psutil, 'Process', lambda *_: pytest.fail('actual progress does not use RSS'))
    owner = SimpleNamespace(_progress_predictor=ParseProgressEstimator(),
                            worker=SimpleNamespace(cancel_requested=False, process=SimpleNamespace(pid=123)),
                            _parse_started=0, _parse_stage=10, _parse_stage_text='读取',
                            loading_overlay=SimpleNamespace(update_progress=lambda *a, **k: None))
    desktop_app.MainWindow._update_estimated_progress(owner)


def test_parser_delivers_large_session_without_qvariant_deep_copy(qt_application, tmp_path):
    """The immutable completed session must cross threads as one Python object."""
    from desktop_app import ParseWorker
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    import time
    payload = {'history': [{'模拟时间': '2024-01-01 00:00:00', '值': str(i)} for i in range(5000)]}
    class ReadyParser(ParseWorker):
        def run(self):
            self.completed.emit(payload)
    parser = ReadyParser(tmp_path / 'sample.save', tmp_path)
    received = []
    parser.completed.connect(received.append, Qt.ConnectionType.QueuedConnection)
    parser.start()
    deadline = time.monotonic() + 5
    while not received and time.monotonic() < deadline:
        QTest.qWait(10)
    parser.wait(5000)
    assert len(received) == 1
    assert received[0] is payload
    assert received[0]['history'] is payload['history']
