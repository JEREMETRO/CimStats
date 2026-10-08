"""Background calculations must leave the GUI event loop responsive."""
import time

from PySide6.QtCore import QEventLoop, QTimer


def test_large_latest_information_task_keeps_gui_ticks_and_real_values(qt_application):
    from latest_info_controller import LatestInfoTask

    row = {'指标': 'population', '值': '12345', '分母': '0',
           '公司标识': '', '分组': 'Student', '模拟时间': '2013-05-21 00:00:00'}
    data = {'save_key': 'large', 'simulation_time': '2013-05-21 02:30:00',
            'metadata': {'当前人口数': 12345}, 'history': [row] * 150000}
    task = LatestInfoTask(1, data, ('', '综合'), (), False)
    received, errors, ticks = [], [], [time.monotonic()]
    task.ready.connect(lambda _, result: received.append(result))
    task.failed.connect(lambda _, error: errors.append(error))
    from PySide6.QtWidgets import QLabel
    labels = [QLabel() for _ in range(400)]
    def tick():
        # Qt widget callbacks repeatedly release/reacquire the GIL, as the
        # visible loading animation and destination cards do in the app.
        for label in labels:
            label.setText(str(len(ticks)))
        ticks.append(time.monotonic())
    timer = QTimer(); timer.timeout.connect(tick); timer.start(10)
    task.start()
    deadline = time.monotonic() + 15
    while not received and not errors and time.monotonic() < deadline:
        loop = QEventLoop(); QTimer.singleShot(20, loop.quit); loop.exec()
    task.requestInterruption(); task.wait(3000); timer.stop()
    assert not errors and received
    snapshot, alerts, _ = received[0]
    assert snapshot.population == 12345 and snapshot.total_departures is None
    assert alerts is None
    assert max(b-a for a, b in zip(ticks, ticks[1:])) < .15


def test_cancel_can_interrupt_inside_one_long_route():
    from map_geometry import snapshot_from_data, MapCancelled
    import pytest

    records = [dict(id=i, position=(float(i), 0., 0.)) for i in range(60)]
    data = dict(roads={}, buildings=[], lines=[dict(id=1, stops=records,
                legs=[dict(roads=[]) for _ in records])])
    calls = 0
    def cancelled():
        nonlocal calls
        calls += 1
        return calls >= 8
    with pytest.raises(MapCancelled):
        snapshot_from_data(data, cancelled=cancelled)


def test_large_actual_map_frame_keeps_widget_updates_responsive(qt_application):
    from map_canvas import MapCanvas
    from map_model import MapRoad, MapSnapshot
    from PySide6.QtWidgets import QLabel

    roads = tuple(MapRoad(i, 'road', '', (((0., 0., float(i % 100)),
                   (100., 0., float(i % 100))),)) for i in range(7000))
    snapshot = MapSnapshot(roads=roads, bounds=(0., 0., 100., 100.))
    canvas = MapCanvas(); canvas.resize(500, 400); canvas.set_snapshot(snapshot)
    labels = [QLabel() for _ in range(400)]
    ticks = [time.monotonic()]
    def tick():
        for label in labels:
            label.setText(str(len(ticks)))
        ticks.append(time.monotonic())
    timer = QTimer(); timer.timeout.connect(tick); timer.start(10)
    canvas.prepare_frame()
    deadline = time.monotonic() + 10
    while canvas._frame_key != canvas._render_key() and time.monotonic() < deadline:
        loop = QEventLoop(); QTimer.singleShot(20, loop.quit); loop.exec()
    timer.stop()
    assert canvas._frame_key == canvas._render_key()
    assert canvas._frame_view == (*canvas.center, canvas.zoom)
    assert canvas.snapshot is snapshot and len(canvas.snapshot.roads) == 7000
    assert max(b-a for a, b in zip(ticks, ticks[1:])) < .15
    canvas.close()


def test_large_map_index_preparation_runs_off_gui_thread(qt_application, monkeypatch):
    import threading
    import map_canvas
    from map_model import MapRoad, MapSnapshot

    main = threading.get_ident()
    threads = []
    original = map_canvas._SpatialIndex.__init__
    def observe(self, *args, **kwargs):
        threads.append(threading.get_ident())
        original(self, *args, **kwargs)
    monkeypatch.setattr(map_canvas._SpatialIndex, '__init__', observe)
    roads = tuple(MapRoad(i, 'road', '', (((0., 0., 0.), (100., 0., 100.)),))
                  for i in range(1200))
    canvas = map_canvas.MapCanvas(); canvas.resize(500, 400)
    canvas.set_snapshot(MapSnapshot(roads=roads, bounds=(0., 0., 100., 100.)))
    deadline = time.monotonic()+5
    while canvas._frame_key != canvas._render_key() and time.monotonic() < deadline:
        canvas.prepare_frame()
        loop = QEventLoop(); QTimer.singleShot(20, loop.quit); loop.exec()
    assert canvas._frame_key == canvas._render_key()
    assert threads and all(thread != main for thread in threads)
    assert len(canvas._indexes['roads'].entries) == 1200
    canvas.close()


def _wait_for(predicate, seconds=5):
    deadline = time.monotonic()+seconds
    while not predicate() and time.monotonic() < deadline:
        loop = QEventLoop(); QTimer.singleShot(20, loop.quit); loop.exec()
    assert predicate()


def _large_map(source='A'):
    from map_model import MapRoad, MapSnapshot
    roads = tuple(MapRoad(i, 'road', '', (((0., 0., 0.), (100., 0., 100.)),))
                  for i in range(1200))
    return MapSnapshot(roads=roads, bounds=(0., 0., 100., 100.), source_hash=source)


def _hold_index_job(monkeypatch, fail=False):
    import threading
    import map_canvas
    entered, release = threading.Event(), threading.Event()
    original = map_canvas._prepare_indexes
    def held(snapshot, *args, **kwargs):
        if snapshot.source_hash == 'A' and not kwargs.get('cached_only'):
            entered.set()
            assert release.wait(3)
            if fail:
                raise ValueError('broken geometry')
        return original(snapshot, *args, **kwargs)
    monkeypatch.setattr(map_canvas, '_prepare_indexes', held)
    return entered, release


import pytest


@pytest.mark.parametrize('fail', [False, True])
def test_late_index_job_cannot_replace_new_save_or_enable_old_building_hits(qt_application, monkeypatch, fail):
    from map_canvas import MapCanvas
    from map_model import MapRoad, MapSnapshot
    from PySide6.QtCore import QPointF
    entered, release = _hold_index_job(monkeypatch, fail)
    canvas = MapCanvas(); canvas.resize(500, 400)
    errors = []; canvas.render_failed.connect(errors.append)
    canvas.set_snapshot(_large_map())
    _wait_for(entered.is_set)
    assert canvas.building_at(QPointF(250, 200)) is None
    replacement = MapSnapshot(roads=(MapRoad(9000, 'road', '', (((200., 0., 200.), (300., 0., 300.)),)),),
                              bounds=(200., 200., 300., 300.), source_hash='B')
    canvas.set_snapshot(replacement)
    canvas.prepare_frame()
    release.set()
    _wait_for(lambda: canvas._index_job is None)
    assert canvas.snapshot is replacement
    assert [road.id for road, _ in canvas._indexes['roads'].entries] == [9000]
    assert canvas._frame_key == canvas._render_key()
    assert errors == []
    canvas.close()


def test_empty_save_discards_pending_route_focus_and_old_indices(qt_application, monkeypatch):
    from dataclasses import replace
    from map_canvas import MapCanvas, MapSearchResult
    from map_model import MapRoute, MapSnapshot
    entered, release = _hold_index_job(monkeypatch)
    route = MapRoute(9000, '9', 9, 'a', 'A', 'bus', (),
                     (((20., 0., 30.), (40., 0., 50.)),))
    canvas = MapCanvas(); canvas.resize(500, 400)
    canvas.set_snapshot(replace(_large_map(), routes=(route,)))
    _wait_for(entered.is_set)
    assert canvas.focus_result(MapSearchResult('route', 9000, '9', (20., 30., 40., 50.)))
    empty = MapSnapshot(source_hash='B')
    canvas.set_snapshot(empty)
    canvas.center = (80., 90.)
    canvas.prepare_frame()
    release.set()
    _wait_for(lambda: canvas._index_job is None)
    assert canvas.snapshot is empty and canvas._indexes_ready
    assert all(not index.entries for index in canvas._indexes.values())
    assert canvas.center == (80., 90.) and canvas._highlight is None
    assert canvas._frame_key == canvas._render_key()
    canvas.close()


def test_export_during_pending_index_does_not_write_previous_save(qt_application, monkeypatch, tmp_path):
    from map_canvas import MapCanvas
    entered, release = _hold_index_job(monkeypatch)
    canvas = MapCanvas(); canvas.resize(500, 400)
    canvas.set_snapshot(_large_map())
    _wait_for(entered.is_set)
    target = tmp_path/'map.png'
    try:
        assert canvas.export_image(target) is False
        assert not target.exists()
    finally:
        release.set()
        _wait_for(lambda: canvas._index_job is None)
        canvas.close()


def test_synchronous_gui_map_export_never_uses_background_cpu_pause(qt_application, monkeypatch, tmp_path):
    import map_canvas
    from map_model import MapRoad, MapSnapshot
    class BackgroundOnlyBudget:
        def __call__(self):
            raise AssertionError('GUI must not wait for a background CPU budget')
    monkeypatch.setattr(map_canvas, 'CooperativeCancellation', BackgroundOnlyBudget)
    canvas = map_canvas.MapCanvas(); canvas.resize(500, 400)
    canvas.set_snapshot(MapSnapshot(roads=(MapRoad(1, 'road', '',
                        (((0., 0., 0.), (100., 0., 100.)),)),), bounds=(0., 0., 100., 100.)))
    assert canvas.export_image(tmp_path/'map.png')
    canvas.close()


def test_current_index_failure_reports_once_and_new_save_can_retry(qt_application, monkeypatch):
    from map_canvas import MapCanvas
    entered, release = _hold_index_job(monkeypatch, True)
    canvas = MapCanvas(); canvas.resize(500, 400)
    errors = []; canvas.render_failed.connect(errors.append)
    canvas.set_snapshot(_large_map())
    _wait_for(entered.is_set)
    release.set()
    _wait_for(lambda: canvas._index_job is None)
    canvas.prepare_frame()
    assert errors == ['broken geometry'] and canvas._index_job is None
    canvas.set_snapshot(_large_map('C'))
    _wait_for(lambda: canvas._frame_key == canvas._render_key())
    assert canvas._indexes_ready
    canvas.close()


def test_close_discards_inflight_index_and_does_not_prepare_frame(qt_application, monkeypatch):
    from map_canvas import MapCanvas
    entered, release = _hold_index_job(monkeypatch)
    canvas = MapCanvas(); canvas.resize(500, 400)
    canvas.set_snapshot(_large_map())
    _wait_for(entered.is_set)
    canvas.close()
    release.set()
    _wait_for(lambda: canvas._index_job is None)
    assert canvas._frame is None and not canvas._indexes_ready
    assert canvas._indexes == {}


def test_pending_indexes_render_latest_modes_viewport_and_queued_route_focus(qt_application, monkeypatch):
    from dataclasses import replace
    from map_canvas import MapCanvas, MapSearchResult, MAP_BACKGROUND
    from map_model import MapRoute
    entered, release = _hold_index_job(monkeypatch)
    route = MapRoute(9000, '9', 9, 'a', 'A', 'bus', (),
                     (((20., 0., 30.), (40., 0., 50.)),))
    snapshot = replace(_large_map(), routes=(route,))
    canvas = MapCanvas(); canvas.resize(500, 400)
    canvas.set_snapshot(snapshot)
    _wait_for(entered.is_set)
    assert canvas.focus_result(MapSearchResult('route', 9000, '9', snapshot.bounds))
    canvas.set_options(roads=False, routes=False, buildings=False, stops=False, line_numbers=False)
    canvas.resize(700, 500)
    release.set()
    _wait_for(lambda: canvas._frame_key == canvas._render_key())
    assert canvas.center == (30., 40.)
    assert canvas._frame_view == (*canvas.center, canvas.zoom)
    assert canvas._frame.width() == round(700*canvas.devicePixelRatioF())
    assert canvas._frame.pixelColor(50, 50).name() == MAP_BACKGROUND.lower()
    assert canvas.snapshot.routes == (route,)
    canvas.close()
