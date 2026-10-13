"""Check the vector viewport inside the normal QWidget composition tree."""
import os
import time

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMainWindow

from map_canvas import MapCanvas
from map_model import MapRoute, MapSnapshot


def test_vector_parent_does_not_claim_to_paint_every_pixel(qt_application):
    canvas = MapCanvas()
    opaque = canvas.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
    canvas.close()
    assert not opaque


def _pixels(image):
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return np.frombuffer(image.bits(), np.uint8).reshape(
        image.height(), image.bytesPerLine() // 4, 4)[:, :image.width(), :3].copy()


def test_native_parent_capture_matches_vector_framebuffer(qt_application, tmp_path):
    if QApplication.platformName() != 'windows':
        pytest.skip('Requires the native Windows OpenGL compositor')
    from stats_style import initialize_theme
    initialize_theme(qt_application)
    window = QMainWindow()
    canvas = MapCanvas()
    window.setCentralWidget(canvas)
    window.resize(480, 400)
    route = MapRoute(1, 'route', 1, 'a', 'a', 'bus', (),
                     (((0., 0., 0.), (100., 0., 100.)),))
    canvas.set_options(roads=False, buildings=False, stops=False,
                       stop_names=False, line_numbers=False)
    canvas.set_snapshot(MapSnapshot(routes=(route,), bounds=(0., 0., 100., 100.)))
    try:
        window.show()
        for case in ('first', 'zoom', 'pan', 'resize', 'restore'):
            if case == 'zoom':
                canvas.zoom *= 1.25
            elif case == 'pan':
                canvas.center = (canvas.center[0]+5, canvas.center[1]-3)
            elif case == 'resize':
                window.resize(520, 420)
            elif case == 'restore':
                window.hide()
                qt_application.processEvents()
                window.show()
            qt_application.processEvents()
            canvas._changed(interactive=True)
            deadline = time.monotonic() + 15
            while not canvas.can_export():
                assert time.monotonic() < deadline, 'Native frame never became current'
                qt_application.processEvents()
                time.sleep(.002)
            # Capture the ancestor first: a framebuffer readback must not
            # prepare or repair the pixels that QWidget.grab() will validate.
            captured = window.grab().toImage()
            framebuffer = canvas._vector_viewport.grabFramebuffer()
            captured.save(str(tmp_path / ('window-' + case + '.png')))
            framebuffer.save(str(tmp_path / ('framebuffer-' + case + '.png')))
            actual, expected = _pixels(captured), _pixels(framebuffer)
            assert actual.shape == expected.shape
            from package_smoke import _map_composition_mismatch
            mismatch = _map_composition_mismatch(actual, expected)
            assert np.count_nonzero(mismatch) / mismatch.size < .001
            assert np.any(np.max(expected, axis=2) - np.min(expected, axis=2) > 80)
    finally:
        window.close()
        qt_application.processEvents()


def test_native_capture_accepts_saved_road_filling_maximum_zoom_view(qt_application,tmp_path):
    if QApplication.platformName() != 'windows':
        pytest.skip('Requires native OpenGL framebuffer capture')
    from map_model import MapRoad
    from package_smoke import _map_vector_capture
    canvas=MapCanvas();canvas.resize(480,400)
    path=((-100.,0.,0.),(100.,0.,0.))
    canvas.set_snapshot(MapSnapshot(roads=(MapRoad(1,'road','asset',(path,),width=12.,
                                   lanes_a=1,lanes_b=1,road_class='ordinary'),),
                                   bounds=(-100.,-100.,100.,100.)))
    canvas.set_options(routes=False,buildings=False,stops=False,line_numbers=False,stop_names=False)
    canvas.show();qt_application.processEvents()
    canvas.center=(0.,0.);canvas.zoom=100.;canvas._changed()
    try:
        deadline=time.monotonic()+15
        while not canvas.can_export():
            assert time.monotonic()<deadline
            qt_application.processEvents();time.sleep(.002)
        result=_map_vector_capture(canvas,tmp_path,'maximum-filled-road')
        assert result['background_samples']==0 and result['geometry_samples']>0
    finally:
        canvas.close();qt_application.processEvents()
