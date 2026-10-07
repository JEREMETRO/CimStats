from dataclasses import replace
from PySide6.QtGui import QImage, QPainter
from map_canvas import MapCanvas
from map_model import MapSnapshot, MapRoute


def test_offscreen_route_fragments_do_not_reach_polygon_or_label_work(qt_application, monkeypatch):
    near=((0.,0.,0.),(10.,0.,0.))
    far=tuple(((10000.+i,0.,0.),(10001.+i,0.,0.)) for i in range(100))
    route=MapRoute(1,'Line',1,'a','A','bus',(),(near,*far))
    canvas=MapCanvas();canvas.resize(500,400)
    canvas.set_snapshot(MapSnapshot(routes=(route,),bounds=(0.,0.,11000.,100.)))
    canvas.center=(0.,0.);canvas.zoom=1.
    original=canvas._polyline
    seen=[]
    def record(path,offset=0.):
        seen.append(path)
        return original(path,offset)
    monkeypatch.setattr(canvas,'_polyline',record)
    image=QImage(canvas.size(),QImage.Format.Format_ARGB32_Premultiplied)
    painter=QPainter(image);canvas._paint(painter);painter.end()
    assert len(seen)<10
    assert canvas.snapshot.routes[0].paths==route.paths
    canvas.close()


def test_pan_reuses_base_geometry_but_new_options_invalidate_it(qt_application, monkeypatch):
    from map_canvas import _MapDrawing
    canvas=MapCanvas();canvas.resize(400,300)
    calls=[]
    original=_MapDrawing._paint_base
    def record(self,painter):
        calls.append(self.center)
        return original(self,painter)
    monkeypatch.setattr(_MapDrawing,'_paint_base',record)
    def render():
        image=QImage(canvas.size(),QImage.Format.Format_ARGB32_Premultiplied)
        painter=QPainter(image);canvas._paint(painter);painter.end()
    render()
    canvas.center=(canvas.center[0]+10,canvas.center[1]);render()
    assert len(calls)==1
    canvas.set_options(roads=False);render()
    assert len(calls)==2
    canvas.close()


def test_large_frame_render_does_not_block_ui_and_drops_stale_options(qt_application, monkeypatch):
    import time
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest
    from map_model import MapRoad
    from map_canvas import _MapDrawing
    canvas=MapCanvas();canvas.resize(400,300)
    roads=tuple(MapRoad(i,'road','',(((0.,0.,0.),(10.,0.,0.)),)) for i in range(1001))
    original=_MapDrawing._paint
    def slow(self,painter,overlays=True):
        time.sleep(.2)
        return original(self,painter,overlays)
    monkeypatch.setattr(_MapDrawing,'_paint',slow)
    canvas.set_snapshot(MapSnapshot(roads=roads,bounds=(0.,0.,100.,100.)))
    ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start(10)
    canvas.show();qt_application.processEvents()
    canvas.set_options(roads=False)
    deadline=time.monotonic()+3
    while time.monotonic()<deadline and (canvas._frame_key is None or canvas._frame_key[0]!=canvas._revision):
        QTest.qWait(10)
    timer.stop()
    assert len(ticks)>=8
    assert max(b-a for a,b in zip(ticks,ticks[1:]))<.15
    assert canvas._frame_key[0]==canvas._revision
    canvas.close()


def test_finished_image_can_be_discarded_after_ui_signal_teardown(qt_application):
    from map_canvas import _FrameSurface,_FrameJob
    from shiboken6 import delete
    canvas=MapCanvas();canvas.resize(200,150)
    job=_FrameJob(_FrameSurface(canvas),canvas._render_key(),(*canvas.center,canvas.zoom))
    delete(job.signals)
    job.run()
    canvas.close()


def test_hidden_page_prewarms_at_actual_stack_size(qt_application,tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QStackedWidget,QWidget
    from map_page import MapPage
    from map_model import MapRoad
    stack=QStackedWidget();stack.resize(1200,800)
    stack.addWidget(QWidget())
    page=MapPage(QSettings(str(tmp_path/'warm.ini'),QSettings.Format.IniFormat))
    stack.addWidget(page);stack.show();qt_application.processEvents()
    page._requested=True
    road=MapRoad(1,'road','',(((0.,0.,0.),(100.,0.,100.)),))
    page._loaded(page._generation,MapSnapshot(roads=(road,),bounds=(0.,0.,100.,100.)))
    assert page.canvas.width()>700
    before=(page.canvas._frame_key,page.canvas._frame_view)
    stack.setCurrentWidget(page);qt_application.processEvents()
    assert (page.canvas._frame_key,page.canvas._frame_view)==before
    stack.close()


def test_page_does_not_override_geometry_service_persistent_cache(qt_application,tmp_path):
    from PySide6.QtCore import QSettings
    from map_page import MapPage
    page=MapPage(QSettings(str(tmp_path/'cache.ini'),QSettings.Format.IniFormat))
    assert page.cache_dir is None
    page.close()
