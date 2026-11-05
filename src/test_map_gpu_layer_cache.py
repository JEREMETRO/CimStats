"""The last successful base layer belongs to one save and geometry selection."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from map_canvas import MapCanvas
from map_model import MapBuilding, MapJunction, MapRoad, MapRoute, MapSnapshot, MapStop


def test_stale_gpu_failure_resumes_the_current_query(qt_application, monkeypatch):
    canvas = MapCanvas()
    calls = []
    monkeypatch.setattr(canvas, 'prepare_frame', lambda: calls.append(canvas._revision))
    canvas._revision = 2
    canvas._gpu_job = SimpleNamespace(key=1)
    canvas._gpu_failed(1, 'old query failed')
    assert canvas._gpu_job is None
    assert calls == [2]
    assert not canvas._vector_gl_failed
    canvas.close()


def test_closed_canvas_ignores_stale_gpu_failure(qt_application, monkeypatch):
    canvas = MapCanvas()
    calls = []
    monkeypatch.setattr(canvas, 'prepare_frame', lambda: calls.append(True))
    canvas.close()
    canvas._gpu_job = SimpleNamespace(key=1)
    canvas._gpu_failed(1, 'closed query failed')
    assert calls == []


@pytest.fixture
def cached_canvas(qt_application, monkeypatch):
    import map_gpu_geometry
    path = ((0., 0., 0.), (100., 0., 0.))
    road = MapRoad(1, 'road', 'Road', (path,), lanes_a=1, lanes_b=1)
    building = MapBuilding(2, 'building', 'Building', (20., 0., 20.),
                          ((10., 0., 10.), (30., 0., 10.), (30., 0., 30.)))
    route = MapRoute(3, '3', 3, 'a', 'Company', 'bus', (5,), (path,))
    snapshot = MapSnapshot(roads=(road,), buildings=(building,), routes=(route,),
                           stops=(MapStop(5, 'Stop', (0., 0., 0.)),),
                           junctions=(MapJunction(4, (0., 0., 0.), (1,), ()),),
                           source_hash='save-a', asset_signature='assets-a')
    calls = []
    def compile_layers(surface, prepared, cancelled=None, base=None):
        layers = SimpleNamespace(base=object() if base is None else base, routes=object())
        calls.append((base, layers))
        return layers
    monkeypatch.setattr(map_gpu_geometry, 'compile_gpu_layers', compile_layers, raising=False)
    # The old entry point makes the missing cache behavior fail on a reused
    # base assertion, rather than on an interface that is being added in parallel.
    monkeypatch.setattr(map_gpu_geometry, 'compile_gpu_scene', compile_layers)
    canvas = MapCanvas()
    canvas.resize(400, 300)
    monkeypatch.setattr(canvas, 'prepare_frame', lambda: None)
    canvas.set_snapshot(snapshot)
    def compile_current():
        assert canvas._prepare_vectors()
        assert canvas._prepare_gpu()
        return canvas._gpu_scene
    scene = compile_current()
    yield SimpleNamespace(canvas=canvas, snapshot=snapshot, calls=calls,
                          compile=compile_current, scene=scene)
    canvas._vector_viewport = None
    canvas.close()


@pytest.mark.parametrize('options', [
    {'routes': False}, {'direction': 'up'}, {'deadhead': True},
    {'route_colors': {3: '#123456'}}, {'mode_widths': {'bus': 5.}},
    {'layer_modes': {'tram'}}, {'distinguish_directions': True},
])
def test_route_display_changes_recompile_routes_with_the_last_base(cached_canvas, options):
    item = cached_canvas
    item.canvas.set_options(**options)
    changed = item.compile()
    assert changed is not item.scene and changed.routes is not item.scene.routes
    assert item.calls[-1][0] is item.scene.base
    assert changed.base is item.scene.base


def test_new_route_query_reuses_base_despite_new_routes_and_stops(cached_canvas):
    item = cached_canvas
    item.canvas.set_snapshot(replace(item.snapshot, routes=(), stops=()))
    assert item.compile().base is item.scene.base
    assert item.calls[-1][0] is item.scene.base


@pytest.mark.parametrize('options', [
    {'roads': False}, {'road_levels': {'express'}}, {'buildings': False},
    {'building_classes': {'Student'}}, {'building_uses': {'work'}},
    {'building_colors': {2: '#123456'}},
])
def test_base_display_changes_compile_a_new_base(cached_canvas, options):
    item = cached_canvas
    item.canvas.set_options(**options)
    assert item.compile().base is not item.scene.base
    assert item.calls[-1][0] is None


@pytest.mark.parametrize('field', ['roads', 'junctions', 'buildings'])
def test_new_base_data_container_is_not_confused_with_equal_old_data(cached_canvas, field):
    item = cached_canvas
    # Identity matters even when the immutable records compare equal.
    values = tuple(list(getattr(item.snapshot, field)))
    assert values is not getattr(item.snapshot, field)
    item.canvas.set_snapshot(replace(item.snapshot, **{field: values}))
    assert item.compile().base is not item.scene.base
    assert item.calls[-1][0] is None


@pytest.mark.parametrize('identity', [{'source_hash': 'save-b'}, {'asset_signature': 'assets-b'}])
def test_save_or_assets_replacement_releases_old_gpu_values_before_compiling(cached_canvas, identity):
    item = cached_canvas
    released = []
    item.canvas._vector_viewport = SimpleNamespace(_release_gpu=lambda: released.append(True))
    item.canvas.set_snapshot(replace(item.snapshot, **identity))
    assert released == [True]
    assert item.canvas._gpu_scene is None and item.canvas._gpu_annotations is None
    assert item.canvas._gpu_key is None and item.canvas._gpu_base_signature is None
    assert item.canvas._gpu_base_sources == ()
    assert item.compile().base is not item.scene.base
    assert item.calls[-1][0] is None


def test_empty_snapshot_releases_the_one_retained_base(cached_canvas):
    item = cached_canvas
    released = []
    item.canvas._vector_viewport = SimpleNamespace(_release_gpu=lambda: released.append(True))
    item.canvas.set_snapshot(MapSnapshot())
    assert released == [True]
    assert item.canvas._gpu_scene is None and item.canvas._gpu_annotations is None
    assert item.canvas._gpu_key is None and item.canvas._gpu_base_signature is None
    assert item.canvas._gpu_base_sources == ()


def test_completed_base_holds_its_source_containers_to_prevent_identity_reuse(cached_canvas):
    item = cached_canvas
    sources = item.canvas._gpu_base_sources
    assert len(sources) == 3
    assert all(actual is expected for actual, expected in zip(sources,
        (item.snapshot.roads, item.snapshot.junctions, item.snapshot.buildings)))
    item.canvas.set_snapshot(replace(item.snapshot, routes=()))
    assert item.canvas._gpu_base_sources is sources


def test_cancelled_older_job_never_overwrites_the_published_base(cached_canvas, monkeypatch):
    import map_canvas
    item = cached_canvas
    signature = item.canvas._gpu_base_signature
    queued = []
    pool = SimpleNamespace(start=queued.append)
    monkeypatch.setattr(map_canvas.QThreadPool, 'globalInstance', lambda: pool)
    item.canvas.set_options(direction='up')
    assert item.canvas._prepare_vectors()
    item.canvas._async_render = True
    assert not item.canvas._prepare_gpu()
    job = queued[-1]
    item.canvas.set_options(direction='down')
    assert job.cancelled.is_set()
    obsolete = SimpleNamespace(base=object(), routes=object())
    item.canvas._gpu_completed(job.key, (obsolete, object()), job.surface)
    assert item.canvas._gpu_scene is item.scene
    assert item.canvas._gpu_base_signature == signature
    assert item.canvas._gpu_base_sources[0] is item.snapshot.roads
    item.canvas._async_render = False
    assert item.compile().base is item.scene.base


def test_cancelled_job_uses_layers_api_and_never_publishes_partial_values(cached_canvas):
    from map_canvas import _FrameSurface, _GpuJob
    item = cached_canvas
    surface = _FrameSurface(item.canvas)
    job = _GpuJob(surface, 7, item.canvas._vector_prepared, base=item.scene.base)
    completed = []
    job.signals.completed.connect(lambda *values: completed.append(values))
    job.cancel()
    job.run()
    assert item.calls[-1][0] is item.scene.base
    assert len(completed) == 1 and completed[0][1] is None


def test_older_save_completion_cannot_repopulate_or_replace_current_base(cached_canvas):
    from map_canvas import _FrameSurface
    item = cached_canvas
    canvas = item.canvas
    old_key = canvas._revision
    old_surface = _FrameSurface(canvas)
    old_surface._gpu_base_signature = canvas._gpu_base_signature
    old_annotations = canvas._gpu_annotations
    canvas.set_snapshot(replace(item.snapshot, source_hash='save-b'))
    canvas._gpu_completed(old_key, (item.scene, old_annotations), old_surface)
    assert canvas._gpu_scene is None and canvas._gpu_base_signature is None
    current = item.compile()
    signature = canvas._gpu_base_signature
    canvas._gpu_completed(old_key, (item.scene, old_annotations), old_surface)
    assert canvas._gpu_scene is current
    assert canvas._gpu_base_signature == signature


def test_canvas_reuses_the_real_compiler_base_layer(qt_application, monkeypatch):
    from map_gpu_geometry import GpuLayers
    path = ((0., 0., 0.), (100., 0., 0.))
    road = MapRoad(1, 'road', 'Road', (path,), lanes_a=1, lanes_b=1)
    route = MapRoute(3, '3', 3, 'a', 'Company', 'bus', (), (path,))
    canvas = MapCanvas()
    canvas.resize(400, 300)
    monkeypatch.setattr(canvas, 'prepare_frame', lambda: None)
    canvas.set_snapshot(MapSnapshot(roads=(road,), routes=(route,), source_hash='save-a'))
    try:
        assert canvas._prepare_vectors() and canvas._prepare_gpu()
        first = canvas._gpu_scene
        assert isinstance(first, GpuLayers)
        assert len(first.base.vertices) and len(first.routes.vertices)
        canvas.set_options(route_colors={3: '#123456'})
        assert canvas._prepare_vectors() and canvas._prepare_gpu()
        assert canvas._gpu_scene.base is first.base
        assert canvas._gpu_scene.routes is not first.routes
        canvas.set_options(roads=False)
        assert canvas._prepare_vectors() and canvas._prepare_gpu()
        assert canvas._gpu_scene.base is not first.base
        assert not len(canvas._gpu_scene.base.vertices)
    finally:
        canvas.close()
