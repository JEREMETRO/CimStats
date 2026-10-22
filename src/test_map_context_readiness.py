"""A released GL frame cannot authorize export before a fresh presentation."""
from types import SimpleNamespace
import time
import pytest
from PySide6.QtWidgets import QApplication
from map_canvas import MapCanvas
from map_model import MapRoad, MapSnapshot
from map_vector_canvas import VectorMapViewport


def test_release_invalidates_presentation_without_dropping_prepared_data(qt_application):
    canvas = MapCanvas()
    canvas.resize(400, 300)
    original = canvas._vector_viewport
    canvas._vector_viewport = SimpleNamespace(canvas=canvas, _gpu_renderer=None, _painted_stamp=object())
    canvas.snapshot = MapSnapshot(roads=(MapRoad(1, '', '', (((0.,0.,0.), (100.,0.,100.)),)),))
    canvas._gpu_scene = scene = object()
    canvas._vector_prepared = prepared = object()
    canvas._gpu_key = canvas._vector_key = canvas._revision
    try:
        canvas._vector_presented(canvas._render_key(), (*canvas.center, canvas.zoom))
        assert canvas.can_export()
        VectorMapViewport._release_gpu(canvas._vector_viewport)
        assert not canvas.can_export()
        assert canvas.is_prepared()
        assert canvas._gpu_scene is scene and canvas._vector_prepared is prepared
    finally:
        canvas._vector_viewport = original
        canvas.close()


def test_native_resource_recreation_repaints_identical_frame(qt_application):
    if QApplication.platformName() in ('offscreen', 'minimal'):
        pytest.skip('Native GL context required')
    canvas = MapCanvas()
    canvas.resize(400, 300)
    canvas.set_snapshot(MapSnapshot(roads=(MapRoad(1, '', '', (((0.,0.,0.), (100.,0.,100.)),),
        width=12., road_class='ordinary'),), bounds=(0.,0.,100.,100.)))
    canvas.show()
    def ready():
        end = time.monotonic() + 10
        while not canvas.can_export() and time.monotonic() < end:
            qt_application.processEvents()
        assert canvas.can_export(), canvas._vector_gl_error
    try:
        ready()
        viewport = canvas._vector_viewport
        before = viewport.grabFramebuffer()
        scene = canvas._gpu_scene
        viewport._release_gpu()
        assert not canvas.can_export()
        viewport.update()
        ready()
        assert canvas._gpu_scene is scene
        assert viewport.grabFramebuffer() == before
    finally:
        canvas.close()
