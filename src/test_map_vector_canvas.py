"""Vector preparation, navigation and export through the existing canvas facade."""
from PySide6.QtGui import QImage, QPainter
from map_canvas import MapCanvas, _FrameSurface
from map_model import MapRoad, MapSnapshot


def _snapshot(identity='vector-source'):
    road=MapRoad(1,'street','ordinary',(((0.,0.,0.),(100.,0.,100.)),),
                 width=12., road_class='ordinary', lanes_a=1, lanes_b=1)
    return MapSnapshot(roads=(road,),bounds=(0.,0.,100.,100.),source_hash=identity)


def test_canvas_reuses_world_vectors_across_pan_and_zoom(qt_application):
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_snapshot(_snapshot());canvas.prepare_frame()
    assert canvas._vector_prepared is not None
    prepared=canvas._vector_prepared
    canvas.center=(55.,45.);canvas._changed();canvas.prepare_frame()
    canvas.zoom_in();canvas.prepare_frame()
    assert canvas._vector_prepared is prepared
    canvas.close()


def test_detached_frame_uses_same_vector_painter_as_live_map(qt_application):
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_snapshot(_snapshot());canvas.prepare_frame()
    surface=_FrameSurface(canvas)
    assert surface._vector_prepared is canvas._vector_prepared and surface._vector_prepared is not None
    image=QImage(surface.width(),surface.height(),QImage.Format.Format_ARGB32_Premultiplied)
    painter=QPainter(image)
    surface._paint(painter,overlays=False);painter.end()
    point=surface.world_to_screen((50.,50.)).toPoint()
    assert image.pixelColor(point).red()>240  # Actual road fill, independent of a GL context.
    canvas.close()


def test_new_query_invalidates_vector_data_and_export_until_ready(qt_application):
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_snapshot(_snapshot());canvas.prepare_frame()
    before=canvas._vector_prepared
    assert canvas.can_export()
    canvas.set_options(roads=False)
    assert not canvas.can_export()
    canvas.prepare_frame()
    assert canvas._vector_prepared is not before
    assert canvas.can_export()
    canvas.close()


def test_late_vector_result_cannot_overwrite_current_save(qt_application):
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_snapshot(_snapshot('old'));canvas.prepare_frame()
    old_data,old_surface=canvas._vector_prepared,_FrameSurface(canvas)
    old_key=canvas._revision
    canvas.set_snapshot(_snapshot('new'));canvas.prepare_frame()
    current=canvas._vector_prepared
    canvas._vectors_completed(old_key,old_data,old_surface)
    assert canvas.snapshot.source_hash=='new' and canvas._vector_prepared is current
    canvas.close()


def test_missing_gl_context_falls_back_without_any_paintgl_callback(qt_application, monkeypatch):
    from PySide6.QtGui import QShowEvent
    from map_canvas import QTimer
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_snapshot(_snapshot());canvas.prepare_frame()
    class MissingContext:
        hidden=False
        def isValid(self):return False
        def hide(self):self.hidden=True
        def update(self):pass
    viewport=MissingContext();canvas._vector_viewport=viewport
    callbacks=[]
    monkeypatch.setattr(QTimer,'singleShot',lambda delay,callback:callbacks.append(callback))
    monkeypatch.setattr(canvas,'isVisible',lambda:True)
    canvas.showEvent(QShowEvent())
    assert callbacks
    callbacks[-1]()
    assert viewport.hidden and canvas._vector_gl_failed
    image=QImage(400,300,QImage.Format.Format_ARGB32_Premultiplied)
    painter=QPainter(image);canvas._paint_vectors(painter,overlays=True);painter.end()
    canvas._vector_presented(canvas._render_key(),(*canvas.center,canvas.zoom))
    assert image.pixelColor(200,150).red()>240 and canvas.can_export()
    canvas.close()


def test_late_preview_failure_does_not_disable_current_vector_export(qt_application):
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_snapshot(_snapshot());canvas.prepare_frame()
    key,view=canvas._render_key(),(*canvas.center,canvas.zoom)
    canvas._vector_presented(key,view)
    failures=[];canvas.render_failed.connect(failures.append)
    canvas._frame_failed(key,view,'Late hidden preview failure')
    assert not failures and canvas.can_export()
    canvas.close()


def test_cancelled_vector_worker_completes_quietly_without_partial_geometry(qt_application):
    from map_canvas import _VectorJob
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(_snapshot())
    job=_VectorJob(_FrameSurface(canvas),canvas._revision)
    results=[];failures=[]
    job.signals.completed.connect(lambda key,data,surface:results.append((key,data)))
    job.signals.failed.connect(lambda key,message:failures.append(message))
    job.cancel();job.run()
    assert results==[(canvas._revision,None)] and not failures
    canvas.close()


def test_old_vector_preparation_failure_keeps_current_query_exportable(qt_application):
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_snapshot(_snapshot('old'));old_key=canvas._revision
    canvas.set_snapshot(_snapshot('new'));canvas.prepare_frame()
    prepared=canvas._vector_prepared
    failures=[];canvas.render_failed.connect(failures.append)
    canvas._vectors_failed(old_key,'Obsolete preparation failed')
    assert canvas._vector_prepared is prepared and canvas.can_export() and not failures
    canvas.close()


def test_native_vector_viewport_requests_multisample_antialiasing(qt_application):
    from map_vector_canvas import VectorMapViewport
    canvas=MapCanvas()
    viewport=VectorMapViewport(canvas)
    assert viewport.format().samples() >= 4
    viewport.close();canvas.close()


def test_current_cpu_vector_failure_invalidates_previous_success(qt_application, monkeypatch):
    import map_canvas
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_snapshot(_snapshot());canvas.prepare_frame()
    class MissingContext:
        def update(self):pass
    canvas._vector_viewport=MissingContext();canvas._vector_gl_failed=True
    monkeypatch.setattr(canvas,'isVisible',lambda:True)
    canvas._vector_presented(canvas._render_key(),(*canvas.center,canvas.zoom))
    assert canvas.can_export()
    class Painter:
        def __init__(self,device):pass
        def end(self):pass
    monkeypatch.setattr(map_canvas,'QPainter',Painter)
    def fail(*args,**kwargs):raise RuntimeError('Current CPU vector paint failed')
    failures=[];canvas.render_failed.connect(failures.append)
    monkeypatch.setattr(canvas,'_paint_vectors',fail)
    canvas.paintEvent(None)
    available=canvas.can_export()
    canvas.close()
    assert failures==['Current CPU vector paint failed']
    assert not available


def test_measured_road_width_changes_continuously_at_detail_threshold():
    from map_canvas import road_style
    road=_snapshot().roads[0]
    before=road_style(road,.2499).width
    after=road_style(road,.2501).width
    assert abs(after-before)<.01
    widths=[road_style(road,i/1000).width for i in range(10,1001)]
    assert all(b>=a for a,b in zip(widths,widths[1:]))


def test_unchanged_options_leave_current_vectors_and_export_ready(qt_application):
    canvas=MapCanvas();canvas.resize(400,300)
    try:
        canvas.set_snapshot(_snapshot());canvas.prepare_frame()
        prepared,key=canvas._vector_prepared,canvas._render_key()
        canvas.set_options(**canvas.options)
        assert canvas._render_key()==key
        assert canvas._vector_prepared is prepared and canvas.can_export()
    finally:canvas.close()


def test_presentation_changes_reuse_geometry_and_update_live_options(qt_application):
    canvas=MapCanvas();canvas.resize(400,300)
    try:
        canvas.set_snapshot(_snapshot());canvas.prepare_frame()
        prepared=canvas._vector_prepared
        canvas.set_options(stop_names=False,route_colors={7:'#123456'},legend_external=True)
        assert not canvas.can_export()
        canvas.prepare_frame()
        assert canvas.can_export() and canvas._vector_prepared is prepared
        assert not canvas._vector_surface.options['stop_names']
        assert canvas._vector_surface.options['route_colors']=={7:'#123456'}
    finally:canvas.close()


def test_native_retained_frame_skips_replay_but_invalidates_on_view_or_fbo(qt_application,monkeypatch):
    from types import SimpleNamespace
    import map_vector_canvas
    from map_vector_canvas import VectorMapViewport
    paints=[];presented=[]
    canvas=SimpleNamespace(_index_closed=False,_revision=1,_vector_key=1,
        _vector_prepared=object(),_gpu_key=1,_gpu_scene=object(),center=(1.,2.),zoom=1.,
        width=lambda:400,height=lambda:300,
        _render_key=lambda:(1,400,300,1.,'font',None),
        _paint_gpu_annotations=lambda painter:None,
        _vector_presented=lambda *a:presented.append(a))
    viewport=SimpleNamespace(canvas=canvas,_painted_stamp=None,_context_generation=1,
        defaultFramebufferObject=lambda:9,devicePixelRatioF=lambda:1.,
        _gpu_renderer=SimpleNamespace(paint=lambda *a:paints.append(True)))
    class Painter:
        def __init__(self,device):pass
        def isActive(self):return True
        def beginNativePainting(self):pass
        def endNativePainting(self):pass
        def end(self):pass
    monkeypatch.setattr(map_vector_canvas,'QPainter',Painter)
    VectorMapViewport.paintGL(viewport);VectorMapViewport.paintGL(viewport)
    assert len(paints)==1 and len(presented)==2
    canvas.center=(2.,2.);VectorMapViewport.paintGL(viewport)
    viewport.defaultFramebufferObject=lambda:10
    VectorMapViewport.paintGL(viewport)
    viewport._context_generation+=1;VectorMapViewport.paintGL(viewport)
    assert len(paints)==4


def test_hidden_prepared_frame_transfers_strokes_to_first_live_vector_paint(qt_application,monkeypatch):
    from map_canvas import _FrameJob
    from map_model import MapRoute
    import map_vector
    route=MapRoute(7,'7',7,'a','A','bus',(),(((0.,0.,0.),(50.,0.,30.),(100.,0.,0.)),))
    canvas=MapCanvas();canvas.resize(400,300)
    try:
        canvas.set_snapshot(MapSnapshot(routes=(route,),bounds=(0.,0.,100.,100.)))
        assert canvas._prepare_vectors()
        key,view=canvas._render_key(),(*canvas.center,canvas.zoom)
        job=_FrameJob(_FrameSurface(canvas),key,view)
        completed=[]
        job.signals.completed.connect(lambda *args:completed.append(args))
        job.run()
        assert completed
        canvas._frame_completed(*completed[0])
        def unexpected_compile():
            raise AssertionError('First live paint rebuilt a stroke already prepared in the hidden frame')
        monkeypatch.setattr(map_vector,'QPainterPathStroker',unexpected_compile)
        image=QImage(400,300,QImage.Format.Format_ARGB32_Premultiplied)
        painter=QPainter(image)
        try:canvas._paint_vectors(painter,overlays=False)
        finally:painter.end()
    finally:canvas.close()
