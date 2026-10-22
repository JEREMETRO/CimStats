"""Native map draws must not inherit a painter's stale clipping stencil."""
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest


@pytest.mark.parametrize('native',[False,True])
def test_ordinary_map_is_visible_with_preexisting_painter_stencil(monkeypatch,native):
    import map_gpu_renderer as module
    from map_gpu_geometry import GpuCommand
    stencil=0x0B90
    enabled={stencil}
    accepted=[]
    gl=Mock()
    gl.glEnable.side_effect=enabled.add
    gl.glDisable.side_effect=enabled.discard
    # A preceding painter clip selected stencil value1. The map clears it to0;
    # ordinary triangles must still be accepted by its own render pass.
    gl.glDrawElements.side_effect=lambda *args:accepted.append(stencil not in enabled)
    monkeypatch.setattr(module,'QOpenGLContext',SimpleNamespace(
        currentContext=lambda:SimpleNamespace(functions=lambda:gl)))
    renderer=module.GpuMapRenderer.__new__(module.GpuMapRenderer)
    renderer.upload=lambda scene:None
    renderer._visible_indices=lambda *args:np.array([0],dtype=np.int64)
    renderer._screen_margin=40.
    renderer._texture_width=1
    renderer._uniforms={name:i for i,name in enumerate(('materials','materialTextureWidth',
        'center','viewport','zoom','connectionRank','shellPass'))}
    renderer.vertex_array=Mock();renderer.vertex_buffer=Mock();renderer.index_buffer=Mock()
    renderer.program=Mock();renderer.texture=Mock()
    renderer._submitter=None
    renderer._draw_offsets={0:None}
    renderer._commands=(GpuCommand(0,3,'triangles',bounds=(0.,0.,100.,100.)),)
    if native:
        renderer._draw_table=np.array([[0,3,0,0,0,-1,-1]],dtype=np.int64)
        renderer._submit_rows=np.empty((1,7),dtype=np.int64)
        renderer._submitter=lambda rows,*args:gl.glDrawElements(4,int(rows[0,1]),0x1405,None)
    renderer.paint(SimpleNamespace(),(50.,50.),1.,400,300,1.)
    assert accepted==[True], 'Painter clipping rejected the ordinary map triangles'


def test_native_map_ignores_a_preexisting_stencil_clip(qt_application,monkeypatch):
    import time
    from PySide6.QtGui import QOpenGLContext
    from PySide6.QtWidgets import QApplication
    if QApplication.platformName()!='windows':pytest.skip('Requires native Windows GL')
    from map_canvas import MapCanvas
    from map_model import MapRoad,MapSnapshot
    from map_gpu_renderer import GpuMapRenderer
    from stats_style import initialize_theme
    from startup_bootstrap import _dispose_window
    initialize_theme(qt_application)
    original=GpuMapRenderer.paint
    def clipped(self,*args,**kwargs):
        gl=QOpenGLContext.currentContext().functions()
        gl.glEnable(0x0B90)
        gl.glStencilFunc(0x0202,1,0xff)  # EQUAL1; the map's clear sets it to0
        gl.glStencilOp(0x1E00,0x1E00,0x1E00)
        return original(self,*args,**kwargs)
    monkeypatch.setattr(GpuMapRenderer,'paint',clipped)
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_options(stops=False,stop_names=False,line_numbers=False)
    road=MapRoad(1,'street','ordinary',(((0.,0.,0.),(100.,0.,100.)),),
                 width=12.,road_class='ordinary',lanes_a=1,lanes_b=1)
    canvas.set_snapshot(MapSnapshot(roads=(road,),bounds=(0.,0.,100.,100.)))
    try:
        canvas.show();deadline=time.monotonic()+15
        while not canvas.can_export() and time.monotonic()<deadline:qt_application.processEvents()
        assert canvas.can_export(),canvas._vector_gl_error
        image=canvas._vector_viewport.grabFramebuffer()
        point=canvas.world_to_screen((50.,50.));ratio=canvas.devicePixelRatioF()
        assert image.pixelColor(round(point.x()*ratio),round(point.y()*ratio)).name()=='#ffffff'
    finally:_dispose_window(canvas)



def test_native_test_cleanup_releases_renderer_before_deleting_context(qt_application):
    from PySide6.QtGui import QOpenGLContext
    from PySide6.QtWidgets import QApplication
    if QApplication.platformName()!='windows':pytest.skip('Requires native Windows GL')
    from conftest import clean_qt_test_windows
    from map_canvas import MapCanvas
    from startup_bootstrap import _dispose_window
    from shiboken6 import isValid
    cleanup=clean_qt_test_windows.__wrapped__(qt_application)
    next(cleanup)
    canvas=MapCanvas();canvas.resize(400,300);canvas.show();qt_application.processEvents()
    viewport=canvas._vector_viewport
    released=[]
    class OwnedRenderer:
        def destroy(self):released.append(QOpenGLContext.currentContext() is viewport.context())
    viewport._gpu_renderer=OwnedRenderer()
    try:
        with pytest.raises(StopIteration):next(cleanup)
        assert not isValid(canvas) and not isValid(viewport)
        assert released==[True], 'Test deleted the context before releasing its renderer'
    finally:
        if isValid(canvas):_dispose_window(canvas)
