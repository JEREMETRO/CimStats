"""Cache behavior and loading handoff for the map query hot path."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication

from map_model import (GroupFunctionCount, MapBuilding, MapRoute, MapSnapshot,
                       MapStop, RouteDirection, SOCIAL_GROUPS)
from map_query import MapQuery


def test_normal_map_worker_prepares_fresh_snapshot_without_disk_cache(monkeypatch, tmp_path):
    import map_geometry
    import map_page

    calls = []
    snapshot = MapSnapshot()

    class Service:
        def __init__(self, cache_dir=None):
            pass

        def load(self, source, cancelled, *, use_disk_cache=True):
            calls.append((source, use_disk_cache, cancelled()))
            return snapshot

    monkeypatch.setattr(map_geometry, 'MapGeometryService', Service)
    worker = map_page.MapWorker(7, tmp_path / 'city.save', tmp_path)
    completed = []
    worker.completed.connect(lambda generation, result: completed.append((generation, result)))
    worker.run()
    assert calls == [(tmp_path / 'city.save', False, False)]
    assert completed == [(7, snapshot)]


def test_capacity_projection_reuses_equal_records_and_keeps_filter_semantics(monkeypatch):
    import map_query

    capacity = tuple(GroupFunctionCount(group, 10 if group == 'BlueCollar' else 0, 0, 0)
                     for group in SOCIAL_GROUPS)
    buildings = tuple(MapBuilding(i, '', '', (float(i), 0., 0.), category='residential', function_capacities=capacity)
                      for i in (1, 2))
    query = MapQuery(MapSnapshot(buildings=buildings))
    original = map_query.building_function_values
    calls = []

    def counted(building, groups):
        calls.append((building.id, groups))
        return original(building, groups)

    monkeypatch.setattr(map_query, 'building_function_values', counted)
    state = {'building_classes': ['BlueCollar'], 'building_emphasis': False}
    first = query.select(state)
    assert len(calls) == 1
    assert [b.id for b in first.snapshot.buildings] == [1, 2]
    assert query.select(dict(state, color_by='company')).building_colors is first.building_colors
    assert len(calls) == 1
    emphasized = query.select(dict(state, building_emphasis=True))
    assert len(calls) == 1
    assert emphasized.building_colors != first.building_colors
    assert query.select({'building_classes': []}).snapshot.buildings == ()
    assert query.select({'building_classes': ['unknown']}).snapshot.buildings == ()


def test_page_keeps_loading_until_current_frame_ready(tmp_path, monkeypatch):
    import map_page

    class FramedCanvas(map_page.MapCanvas):
        frame_ready = Signal()
        render_failed = Signal(str)

    monkeypatch.setattr(map_page, 'MapCanvas', FramedCanvas)
    app = QApplication.instance() or QApplication([])
    page = map_page.MapPage(QSettings(str(tmp_path / 'map.ini'), QSettings.Format.IniFormat))
    page.resize(800, 600)
    page.show()
    app.processEvents()
    page._requested = True
    page.surface.set_loading(True)
    page.set_snapshot(MapSnapshot(buildings=(MapBuilding(1, '', '', (0., 0., 0.)),)))
    assert page.surface.loading.isVisible()
    page.canvas.frame_ready.emit()
    assert page.surface.loading.isHidden()
    page.surface.set_loading(True)
    page._awaiting_frame = True
    errors = []
    page.failed.connect(errors.append)
    page.canvas.render_failed.emit('render failure')
    assert page.surface.loading.isHidden() and errors == ['render failure']
    page.surface.set_loading(True)
    page.set_snapshot(MapSnapshot())
    assert page.surface.loading.isHidden()
    page.close()


def test_direction_distance_and_stops_stay_correct_when_geometry_is_cached():
    down = ((0., 0., 0.), (300., 400., 0.))
    up = ((300., 400., 0.), (300., 400., 600.))
    depot = ((0., 0., 0.), (0., 0., 100.))
    route = MapRoute(7, '7', 7, 'a', 'A', 'bus', (1, 2, 3), (down, up),
                     RouteDirection('roundtrip', terminal_index=1),
                     ((down,), (up,)), (depot,))
    stops = tuple(MapStop(i, str(i), (float(i), 0., 0.)) for i in (1, 2, 3))
    query = MapQuery(MapSnapshot(routes=(route,), stops=stops))
    down_result = query.select({'direction': 'down'})
    up_result = query.select({'direction': 'up', 'deadhead': True})
    assert down_result.mileage_km == 1.
    assert up_result.mileage_km == 1.4
    assert {stop.id for stop in down_result.snapshot.stops} == {1, 2}
    assert {stop.id for stop in up_result.snapshot.stops} == {2, 3}
    assert query.select({'direction': 'down'}).mileage_km == 1.
    building_only = query.select({'direction': 'down', 'building_classes': []})
    assert building_only.snapshot.routes is down_result.snapshot.routes
    assert building_only.snapshot.stops is down_result.snapshot.stops
    assert up_result.snapshot.stops is not down_result.snapshot.stops


def test_page_refreshes_auto_emphasis_and_line_palette_when_they_change(tmp_path):
    import map_page

    app = QApplication.instance() or QApplication([])
    page = map_page.MapPage(QSettings(str(tmp_path / 'options.ini'), QSettings.Format.IniFormat))
    route = MapRoute(7, '7', 7, 'a', 'A', 'bus', (),
                     (((0., 0., 0.), (100., 0., 0.)),), RouteDirection('oneway'))
    page.set_snapshot(MapSnapshot(routes=(route,)))
    assert page.panel_set._options['building_emphasis_effective'] is False
    state = page.panel_set.state()
    state['routes'] = False
    page.apply_state(state)
    assert page.panel_set._options['building_emphasis_effective'] is True
    state['color_by'] = 'line'
    page.apply_state(state)
    assert page.panel_set._options['lines'][0]['color'] == page.query.line_colors[7]
    page.close()


def test_prefetch_result_is_held_until_session_then_reused_without_second_worker(tmp_path, monkeypatch):
    import map_page

    workers = []

    class Worker(QObject):
        completed = Signal(int, object)
        failed = Signal(int, str)
        finished = Signal()

        def __init__(self, generation, source, cache, parent):
            super().__init__(parent)
            self.generation = generation
            self.interrupted = False
            workers.append(self)

        def start(self):
            pass

        def requestInterruption(self):
            self.interrupted = True

        def isRunning(self):
            return not self.interrupted

    monkeypatch.setattr(map_page, 'MapWorker', Worker)
    app = QApplication.instance() or QApplication([])
    page = map_page.MapPage(QSettings(str(tmp_path / 'prefetch.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(page.canvas, 'prepare_frame', lambda: None)
    source = tmp_path / 'city.save'
    snapshot = MapSnapshot(buildings=(MapBuilding(1, '', '', (0., 0., 0.)),))
    page.start_prefetch(source)
    assert len(workers) == 1
    workers[0].completed.emit(workers[0].generation, snapshot)
    assert page.query is None
    assert page._prefetch_snapshot is snapshot
    page.set_session({'save_path': str(source), 'save_key': 'city'})
    assert len(workers) == 1
    assert page.query is not None
    assert page.query.snapshot.buildings == snapshot.buildings
    assert page.canvas._fit_pending
    page.close()


def test_prefetch_inflight_and_failure_do_not_leak_across_saves(tmp_path, monkeypatch):
    import map_page

    workers = []

    class Worker(QObject):
        completed = Signal(int, object)
        failed = Signal(int, str)
        finished = Signal()

        def __init__(self, generation, source, cache, parent):
            super().__init__(parent)
            self.generation = generation
            self.interrupted = False
            workers.append(self)

        def start(self):
            pass

        def requestInterruption(self):
            self.interrupted = True

        def isRunning(self):
            return not self.interrupted

    monkeypatch.setattr(map_page, 'MapWorker', Worker)
    app = QApplication.instance() or QApplication([])
    page = map_page.MapPage(QSettings(str(tmp_path / 'switch.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(page.canvas, 'prepare_frame', lambda: None)
    errors = []
    page.failed.connect(errors.append)
    first, second = tmp_path / 'a.save', tmp_path / 'b.save'
    page.start_prefetch(first)
    page.start_prefetch(second)
    assert workers[0].interrupted
    workers[0].completed.emit(workers[0].generation, MapSnapshot())
    workers[1].failed.emit(workers[1].generation, 'map failure')
    assert page._prefetch_snapshot is None and page._prefetch_error == 'map failure'
    assert errors == []
    page.cancel_prefetch()  # Statistics parse failed or was cancelled.
    assert workers[1].interrupted and page._prefetch_error is None
    page.close()


def test_normal_open_starts_map_prefetch_and_cancel_discards_it(tmp_path, monkeypatch):
    import desktop_app

    class Parser(QObject):
        progress = Signal(int, str)
        log = Signal(str)
        completed = Signal(object)
        failed = Signal(str)
        finished = Signal()

        def __init__(self, path, managed, parent):
            super().__init__(parent)
            self.cancel_requested = False

        def start(self):
            pass

        def isRunning(self):
            return False

        def cancel(self):
            self.cancel_requested = True

        def wait(self, milliseconds):
            return True

    monkeypatch.setattr(desktop_app, 'ParseWorker', Parser)
    monkeypatch.setattr(desktop_app, 'locate_managed', lambda *_: tmp_path)
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda _: None)
    monkeypatch.setattr(desktop_app, 'QSettings',
                        lambda *_: QSettings(str(tmp_path / 'desktop.ini'), QSettings.Format.IniFormat))
    app = QApplication.instance() or QApplication([])
    window = desktop_app.MainWindow()
    started, cancelled = [], []
    monkeypatch.setattr(window.map_page, 'start_prefetch', started.append)
    monkeypatch.setattr(window.map_page, 'cancel_prefetch', lambda: cancelled.append(True))
    source = tmp_path / 'normal.save'
    window.start_parse(source)
    assert started == [source]
    window.cancel_parse()
    assert window.worker.cancel_requested
    assert cancelled == [True]
    window.on_failed('已取消解析')
    assert cancelled == [True, True]
    replacement = tmp_path / 'replacement.save'
    window.start_parse(replacement)
    assert started == [source, replacement]
    stopped = []
    monkeypatch.setattr(window.map_page, 'stop_workers', lambda: stopped.append(True) or True)
    window.close()
    assert stopped == [True]
