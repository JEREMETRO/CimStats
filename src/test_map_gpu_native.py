"""Native retained-buffer acceptance; run with QT_QPA_PLATFORM=windows."""
import time
import pytest
import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from map_canvas import MapCanvas
from map_model import MapRoad, MapSnapshot


def _ready(app, canvas):
    limit=time.monotonic()+10
    while not canvas.can_export() and time.monotonic()<limit:
        app.processEvents()
    assert canvas.can_export()


def test_navigation_retains_gpu_buffers_for_new_views(qt_application):
    if QApplication.platformName() in ('offscreen','minimal'):
        pytest.skip('Native GL context required')
    canvas=MapCanvas();canvas.resize(400,300)
    road=MapRoad(1,'street','ordinary',(((0.,0.,0.),(100.,0.,100.)),),
                 width=12.,road_class='ordinary',lanes_a=1,lanes_b=1)
    canvas.set_snapshot(MapSnapshot(roads=(road,),bounds=(0.,0.,100.,100.)))
    canvas.set_options(stops=False,stop_names=False,line_numbers=False)
    canvas.show();_ready(qt_application,canvas)
    renderer=getattr(canvas._vector_viewport,'_gpu_renderer',None)
    assert renderer is not None, 'Navigation still replays CPU paths'
    scene=renderer.scene;buffer_id=renderer.vertex_buffer.bufferId()
    uploads=renderer.uploaded_bytes
    for step in range(20):
        canvas._zoom(1.013,QPointF(163,127))
        canvas.center=(canvas.center[0]+.5,canvas.center[1]-.25)
        canvas._changed(interactive=True);_ready(qt_application,canvas)
        assert renderer.scene is scene
        assert renderer.vertex_buffer.bufferId()==buffer_id
        assert renderer.uploaded_bytes==uploads
    image=canvas._vector_viewport.grabFramebuffer()
    assert not image.isNull()
    assert not canvas._vector_gl_failed, canvas._vector_gl_error
    point=canvas.world_to_screen((50.,50.))
    ratio=canvas.devicePixelRatioF()
    assert image.pixelColor(round(point.x()*ratio),round(point.y()*ratio)).name()=='#ffffff'
    canvas.close()


def test_gpu_antialiasing_keeps_opaque_frame_and_matches_widget_composition(qt_application):
    if QApplication.platformName() in ('offscreen','minimal'):
        pytest.skip('Native GL context required')
    from PySide6.QtGui import QImage
    canvas=MapCanvas();canvas.resize(400,300)
    road=MapRoad(1,'street','ordinary',(((5.,0.,13.),(95.,0.,78.)),),
                 width=12.,road_class='ordinary',lanes_a=1,lanes_b=1)
    canvas.set_snapshot(MapSnapshot(roads=(road,),bounds=(0.,0.,100.,100.)))
    canvas.set_options(stops=False,stop_names=False,line_numbers=False)
    canvas.show();_ready(qt_application,canvas)
    assert not canvas._vector_gl_failed,canvas._vector_gl_error
    parent=canvas.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    direct=canvas._vector_viewport.grabFramebuffer().convertToFormat(QImage.Format.Format_RGBA8888)
    a=np.frombuffer(parent.constBits(),dtype=np.uint8).reshape(parent.height(),parent.width(),4)
    b=np.frombuffer(direct.constBits(),dtype=np.uint8).reshape(direct.height(),direct.width(),4)
    assert np.all(b[:,:,3]==255),'Opaque map contains partially transparent antialiased pixels'
    assert np.array_equal(a[:,:,:3],b[:,:,:3]),'Composited map differs from its native frame'
    canvas.close()


def test_hidden_cpu_preview_is_not_ready_while_native_geometry_is_pending(qt_application):
    from PySide6.QtGui import QImage
    canvas=MapCanvas();canvas.resize(400,300)
    road=MapRoad(1,'street','ordinary',(((0.,0.,0.),(100.,0.,100.)),))
    canvas.snapshot=MapSnapshot(roads=(road,),bounds=(0.,0.,100.,100.))
    # This test exercises readiness without requiring a real GL context.
    original=canvas._vector_viewport
    canvas._vector_viewport=object()
    canvas._frame=QImage(400,300,QImage.Format.Format_ARGB32_Premultiplied)
    canvas._frame_key=canvas._render_key();canvas._frame_view=(*canvas.center,canvas.zoom)
    try:
        assert not canvas.can_export()
        canvas._gpu_scene=object();canvas._gpu_key=canvas._revision
        assert canvas.can_export()
    finally:
        canvas._vector_viewport=original;canvas.close()


def test_certified_strip_matches_independent_winding_at_multiple_scales(qt_application,monkeypatch):
    if QApplication.platformName() in ('offscreen','minimal'):
        pytest.skip('Native GL context required')
    from PySide6.QtGui import QImage
    import map_gpu_geometry as geometry
    from map_canvas import _FrameSurface
    from test_map_gpu_geometry import _connection_surface
    source=_connection_surface()
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_snapshot(source.snapshot)
    canvas.set_options(routes=False,stops=False,stop_names=False,line_numbers=False)
    canvas.center=(50.,50.);canvas.show();_ready(qt_application,canvas)
    fast=canvas._gpu_scene
    assert any(c.mode=='triangles' and c.min_zoom>=.15 and c.connection_rank>=0
               for c in fast.base.commands),'Native pair proof was not exercised'
    monkeypatch.setattr(geometry,'_load_strip',lambda:None)
    fallback=geometry.compile_gpu_layers(_FrameSurface(canvas),canvas._vector_prepared)
    assert any(c.mode=='winding' for c in fallback.base.commands)
    viewport=canvas._vector_viewport
    for zoom in (.149,.151,.25,1.,16.,100.):
        images=[]
        for scene in (fast,fallback):
            canvas._gpu_scene=scene;canvas.zoom=zoom
            canvas._vector_presented_key=None;canvas._vector_presented_view=None
            viewport._painted_stamp=None;canvas._changed();_ready(qt_application,canvas)
            im=viewport.grabFramebuffer().convertToFormat(QImage.Format.Format_RGBA8888)
            images.append(np.frombuffer(im.constBits(),dtype=np.uint8).reshape(im.height(),im.width(),4).copy())
        assert np.all(images[0][:,:,3]==255) and np.all(images[1][:,:,3]==255)
        difference=np.max(abs(images[0][:,:,:3].astype(int)-images[1][:,:,:3].astype(int)),axis=2)
        assert np.mean(difference>2)<.001,(zoom,float(np.mean(difference>2)))
    canvas.close()
