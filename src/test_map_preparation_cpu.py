"""Background work is useful only for the current scene and current device."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QImage, QPainter

from map_canvas import MapCanvas, _FrameJob, _FrameSurface
from map_model import MapRoad, MapRoute, MapSnapshot


def snapshot(source='a'):
    path=((0.,0.,0.),(100.,0.,100.))
    return MapSnapshot(roads=(MapRoad(1,'road','Road',(path,),lanes_a=1,lanes_b=1),),
        routes=(MapRoute(3,'3',3,'a','A','bus',(),(path,)),),
        bounds=(0.,0.,100.,100.),source_hash=source)


class Viewport:
    def update(self):pass
    def hide(self):pass
    def _release_gpu(self):pass


def test_hidden_viable_gpu_prepares_data_without_software_preview(qt_application,monkeypatch):
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot())
    canvas._vector_viewport=Viewport()
    try:
        canvas.prepare_frame()
        assert canvas._gpu_scene is not None
        assert canvas._frame is None
        assert canvas.is_prepared()
        assert not canvas.can_export()
        canvas._vector_presented(canvas._render_key(),(*canvas.center,canvas.zoom))
        assert canvas.can_export()
    finally:canvas.close()


def test_hidden_gpu_failure_prepares_cpu_frame_on_demand(qt_application,monkeypatch):
    import map_gpu_geometry
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot())
    canvas._vector_viewport=Viewport()
    def fail(*args,**kwargs):raise RuntimeError('device failed')
    monkeypatch.setattr(map_gpu_geometry,'compile_gpu_layers',fail)
    try:
        canvas.prepare_frame()
        assert canvas._vector_gl_failed and canvas._frame is not None
        assert canvas.is_prepared() and canvas.can_export()
        monkeypatch.setattr(canvas,'isVisible',lambda:True)
        assert not canvas.can_export()
        canvas._vector_presented(canvas._render_key(),(*canvas.center,canvas.zoom))
        assert canvas.can_export()
    finally:canvas.close()


def test_frame_worker_cancellation_interrupts_real_paint_and_publishes_no_image(qt_application):
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot());canvas._prepare_vectors()
    surface=_FrameSurface(canvas);job=_FrameJob(surface,canvas._render_key(),(*canvas.center,canvas.zoom))
    completed=[];failed=[];work=[]
    job.signals.completed.connect(lambda *args:completed.append(args))
    job.signals.failed.connect(lambda *args:failed.append(args))
    cooperate=surface._cooperate
    def checkpoint():
        work.append(len(work))
        if len(work)==3:job.cancel()
        cooperate()
    surface._cooperate=checkpoint
    try:
        job.run()
        assert work==[0,1,2]
        assert len(completed)==1 and completed[0][2] is None and not failed
    finally:canvas.close()


def test_navigation_and_requery_cancel_stale_software_work(qt_application,monkeypatch):
    import map_canvas
    queued=[]
    monkeypatch.setattr(map_canvas.QThreadPool,'globalInstance',lambda:SimpleNamespace(start=queued.append))
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot());canvas._prepare_vectors()
    canvas._async_render=True
    try:
        canvas.prepare_frame();first=canvas._frame_job
        canvas.center=(60.,50.);canvas._changed()
        assert first.cancelled.is_set()
        first.run();qt_application.processEvents()
        second=canvas._frame_job
        assert second is not None and second is not first
        canvas.set_options(roads=False)
        assert second.cancelled.is_set()
        canvas.close()
        assert second.cancelled.is_set()
    finally:canvas.close()


def test_cancelled_or_closed_preview_cannot_publish_partial_frame(qt_application,monkeypatch):
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot());canvas._prepare_vectors()
    surface=_FrameSurface(canvas);key=canvas._render_key();view=(*canvas.center,canvas.zoom)
    try:
        monkeypatch.setattr(canvas,'prepare_frame',lambda:None)
        canvas._frame_completed(key,view,None,surface)
        assert canvas._frame is None and not canvas.can_export()
        canvas.close()
        canvas._frame_completed(key,view,QImage(1,1,QImage.Format.Format_ARGB32),surface)
        assert canvas._frame is None
    finally:canvas.close()


def test_recent_scene_reuses_exact_variant_and_invalidates_source_options(qt_application,monkeypatch):
    canvas=MapCanvas();canvas.resize(400,300);data=snapshot();canvas.set_snapshot(data)
    monkeypatch.setattr(canvas,'prepare_frame',lambda:None)
    def compile_current():
        assert canvas._prepare_vectors() and canvas._prepare_gpu()
        return canvas._gpu_scene
    try:
        whole=compile_current()
        canvas.set_options(direction='up');up=compile_current()
        canvas.set_options(direction='whole');assert compile_current() is whole
        canvas.set_options(direction='up');assert compile_current() is up
        canvas.set_options(route_colors={3:'#123456'});coloured=compile_current()
        assert coloured is not up and coloured.base is up.base
        canvas.set_options(route_colors={});assert compile_current() is up
        canvas.set_options(roads=False);hidden=compile_current()
        canvas.set_options(roads=True);assert compile_current() is up
        assert hidden.base is not whole.base
        canvas.set_snapshot(replace(data,source_hash='b'));assert compile_current() is not up
        assert len(canvas._scene_variants)==1
    finally:canvas.close()


def test_scene_cache_counts_shared_base_once_and_enforces_byte_and_entry_limits():
    import numpy as np
    from map_gpu_geometry import GpuScene,GpuLayers
    from map_scene_cache import SceneVariantCache
    base=GpuScene(np.zeros((10,2)),np.zeros((2,4)),())
    route1=GpuScene(np.zeros((3,2)),np.zeros((1,4)),())
    route2=GpuScene(np.zeros((4,2)),np.zeros((1,4)),())
    first=GpuLayers(base,route1);second=GpuLayers(base,route2)
    cache=SceneVariantCache(byte_budget=100000,max_entries=2)
    cache.put('a',first);one=cache.retained_bytes
    cache.put('b',second);shared=cache.retained_bytes
    independent=SceneVariantCache(byte_budget=100000,max_entries=2)
    independent.put('b',second)
    assert one<shared<one+independent.retained_bytes
    assert cache.get('a') is first
    cache.put('c',GpuLayers(base,route1))
    assert cache.get('b') is None and len(cache)==2
    budget=max(one,independent.retained_bytes)
    limited=SceneVariantCache(byte_budget=budget,max_entries=8)
    limited.put('a',first);limited.put('b',second)
    assert limited.retained_bytes<=budget
    assert limited.get('a') is None
    limited.clear();assert limited.retained_bytes==0 and len(limited)==0


def test_frame_surface_detaches_mutable_option_values_before_worker_starts(qt_application):
    canvas=MapCanvas();canvas.set_options(route_colors={3:'#123456'},layer_modes={'bus'})
    surface=_FrameSurface(canvas)
    try:
        canvas.options['route_colors'][3]='#654321'
        canvas.options['layer_modes'].add('tram')
        assert surface.options['route_colors']=={3:'#123456'}
        assert surface.options['layer_modes']=={'bus'}
    finally:canvas.close()


def test_delayed_gpu_failure_schedules_only_one_fallback_and_current_presentation(qt_application,monkeypatch):
    import map_canvas
    queued=[]
    monkeypatch.setattr(map_canvas.QThreadPool,'globalInstance',lambda:SimpleNamespace(start=queued.append))
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot());canvas._prepare_vectors()
    canvas._vector_viewport=Viewport();canvas._async_render=True
    ready=[];canvas.frame_ready.connect(lambda:ready.append(canvas.can_export()))
    try:
        canvas.prepare_frame();canvas.prepare_frame()
        assert len(queued)==1 and canvas._frame_job is None
        job=queued[0];canvas._gpu_failed(job.key,'GPU unavailable')
        canvas.prepare_frame();canvas.prepare_frame()
        assert len(queued)==2 and isinstance(queued[1],_FrameJob)
        assert not canvas.is_prepared() and not canvas.can_export()
        queued[1].run()
        assert canvas.is_prepared() and canvas.can_export() and ready==[True]
        monkeypatch.setattr(canvas,'isVisible',lambda:True)
        assert not canvas.can_export()
        canvas._vector_presented(canvas._render_key(),(*canvas.center,canvas.zoom))
        assert canvas.can_export()
    finally:canvas.close()


def test_hidden_gpu_ready_does_not_enable_export_on_reveal_until_presented(qt_application,monkeypatch):
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot())
    canvas._vector_viewport=Viewport();ready=[];canvas.frame_ready.connect(lambda:ready.append(canvas.can_export()))
    try:
        canvas.prepare_frame()
        assert ready==[False] and canvas.is_prepared()
        monkeypatch.setattr(canvas,'isVisible',lambda:True)
        canvas.prepare_frame()
        assert ready==[False] and not canvas.can_export()
        canvas._vector_presented(canvas._render_key(),(*canvas.center,canvas.zoom))
        assert ready==[False,True] and canvas.can_export()
        canvas.center=(60.,50.);canvas._changed()
        assert canvas.is_prepared() and not canvas.can_export()
    finally:canvas.close()


@pytest.mark.parametrize('field',['roads','buildings','stops','routes','junctions','bounds','asset_signature'])
def test_scene_cache_invalidates_every_data_container_and_asset_identity(qt_application,monkeypatch,field):
    from map_model import MapBuilding,MapJunction,MapStop
    data=snapshot()
    data=replace(data,buildings=(MapBuilding(5,'b','B',(0.,0.,0.),((0.,0.,0.),(3.,0.,0.),(0.,0.,3.))),),
                 stops=(MapStop(6,'S',(1.,0.,1.)),),junctions=(MapJunction(7,(0.,0.,0.),(),()),))
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(data)
    monkeypatch.setattr(canvas,'prepare_frame',lambda:None)
    def compile_current():
        assert canvas._prepare_vectors() and canvas._prepare_gpu()
        return canvas._gpu_scene
    try:
        first=compile_current()
        value=('other-assets' if field=='asset_signature' else (0.,0.,101.,101.) if field=='bounds'
               else tuple(list(getattr(data,field))))
        canvas.set_snapshot(replace(data,**{field:value}))
        assert compile_current() is not first
        canvas.set_snapshot(data)
        restored=compile_current()
        assert (restored is first)==(field!='asset_signature')
    finally:canvas.close()


def test_scene_cache_restores_data_without_old_annotation_font_or_presentation_state(qt_application,monkeypatch):
    from PySide6.QtGui import QFont
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot())
    monkeypatch.setattr(canvas,'prepare_frame',lambda:None)
    def compile_current():
        assert canvas._prepare_vectors() and canvas._prepare_gpu()
        return canvas._gpu_scene
    try:
        first=compile_current();annotations=canvas._gpu_annotations
        canvas._vector_presented(canvas._render_key(),(*canvas.center,canvas.zoom))
        canvas.set_options(direction='up');compile_current()
        canvas.setFont(QFont('Arial',19));canvas.resize(600,400)
        canvas.set_options(direction='whole');assert compile_current() is first
        assert canvas._gpu_annotations is not annotations
        assert canvas._vector_presented_key is None and not canvas.can_export()
        image=QImage(600,400,QImage.Format.Format_ARGB32_Premultiplied)
        painter=QPainter(image)
        try:canvas._paint_gpu_annotations(painter)
        finally:painter.end()
        assert canvas._vector_surface.font().toString()==canvas.font().toString()
        canvas._vector_viewport=Viewport()
        canvas._vector_viewport._release_gpu()
        assert canvas._prepare_gpu() and canvas._gpu_scene is first
        assert not canvas.can_export()
    finally:canvas.close()


def test_accounting_owner_table_stays_small_for_long_paths_and_reuses_source_summaries():
    import numpy as np
    from map_gpu_geometry import GpuScene,GpuLayers
    from map_scene_cache import retained_resources
    route=MapRoute(3,'3',3,'a','A','bus',(),(tuple((float(i),0.,float(i)) for i in range(10000)),))
    empty=GpuScene(np.empty((0,2)),np.empty((0,4)),())
    sources=((route,),)
    value=(GpuLayers(empty,empty),None,sources)
    first=retained_resources(value)
    assert len(first)==2
    checkpoints=[]
    second=retained_resources(value,lambda:checkpoints.append(True),known=first)
    assert second==first and checkpoints==[]
    assert sum(size for _,size in first.values())>10000*100


def test_scene_cache_accounts_full_numpy_backing_buffers_and_rejects_oversize():
    import numpy as np
    from map_gpu_geometry import GpuScene,GpuLayers
    from map_scene_cache import SceneVariantCache
    backing=np.zeros(100000,dtype=np.float64)
    scene=GpuScene(backing[:10],np.empty((0,4)),())
    cache=SceneVariantCache(byte_budget=100000)
    cache.put('oversized',GpuLayers(scene,scene))
    assert len(cache)==0 and cache.retained_bytes==0


def test_frame_error_after_cancellation_is_quiet_and_does_not_fail_current_gpu(qt_application):
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot());canvas._prepare_vectors()
    surface=_FrameSurface(canvas);job=_FrameJob(surface,canvas._render_key(),(*canvas.center,canvas.zoom))
    completed=[];failed=[]
    job.signals.completed.connect(lambda *args:completed.append(args))
    job.signals.failed.connect(lambda *args:failed.append(args))
    def interrupted_device(painter,overlays=False):
        job.cancel()
        raise RuntimeError('obsolete paint device')
    surface._paint=interrupted_device
    try:
        job.run()
        assert len(completed)==1 and completed[0][2] is None
        assert not failed
    finally:canvas.close()


@pytest.mark.parametrize('zoom',[.149,.15,.251,1.,16.,100.])
def test_cooperative_worker_matches_real_synchronous_vector_pixels(qt_application,zoom):
    from map_model import MapBuilding
    canvas=MapCanvas();canvas.resize(400,300)
    data=replace(snapshot(),buildings=(MapBuilding(5,'b','B',(40.,0.,40.),
                 ((20.,0.,20.),(60.,0.,20.),(60.,0.,60.),(20.,0.,60.))),))
    canvas.set_snapshot(data);canvas.zoom=zoom;canvas._prepare_vectors()
    expected=QImage(400,300,QImage.Format.Format_ARGB32_Premultiplied)
    painter=QPainter(expected)
    try:_FrameSurface(canvas)._paint(painter,overlays=False)
    finally:painter.end()
    job=_FrameJob(_FrameSurface(canvas),canvas._render_key(),(*canvas.center,canvas.zoom))
    results=[];job.signals.completed.connect(lambda *args:results.append(args[2]))
    try:
        job.run()
        assert len(results)==1 and results[0] is not None
        assert bytes(results[0].constBits())==bytes(expected.constBits())
    finally:canvas.close()


def test_integer_saved_xyz_paths_are_counted_by_length_without_visiting_each_point():
    import numpy as np
    from map_gpu_geometry import GpuScene,GpuLayers
    from map_scene_cache import retained_resources
    route=MapRoute(3,'3',3,'a','A','bus',(),(tuple((i,0,float(i)) for i in range(10000)),))
    empty=GpuScene(np.empty((0,2)),np.empty((0,4)),())
    checkpoints=[]
    resources=retained_resources((GpuLayers(empty,empty),None,((route,),)),
                                  lambda:checkpoints.append(True))
    assert len(resources)==2 and len(checkpoints)<200
    assert sum(size for _,size in resources.values())>10000*100


def test_old_view_completion_does_not_replace_frame_or_clear_newer_worker(qt_application,monkeypatch):
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot());canvas._prepare_vectors()
    old_surface=_FrameSurface(canvas);key=canvas._render_key();view=(*canvas.center,canvas.zoom)
    canvas.center=(60.,50.);canvas._changed()
    newer=_FrameJob(_FrameSurface(canvas),canvas._render_key(),(*canvas.center,canvas.zoom))
    canvas._frame_job=newer
    monkeypatch.setattr(canvas,'prepare_frame',lambda:None)
    try:
        canvas._frame_completed(key,view,QImage(400,300,QImage.Format.Format_ARGB32),old_surface)
        assert canvas._frame is None and canvas._frame_job is newer
        canvas._frame_failed(key,view,'obsolete failure')
        assert canvas._frame_job is newer and canvas._failed_frame_key is None
    finally:canvas.close()


def test_optional_cache_estimation_failure_keeps_valid_gpu_scene_ready(qt_application,monkeypatch):
    import map_canvas
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot())
    monkeypatch.setattr(canvas,'prepare_frame',lambda:None)
    def fail(*args,**kwargs):raise RuntimeError('optional cache size unavailable')
    monkeypatch.setattr(map_canvas,'retained_resources',fail)
    failures=[];canvas.render_failed.connect(failures.append)
    try:
        assert canvas._prepare_vectors() and canvas._prepare_gpu()
        assert canvas._gpu_scene is not None and canvas._gpu_key==canvas._revision
        assert not canvas._vector_gl_failed and not failures
        assert len(canvas._scene_variants)==0
    finally:canvas.close()


def test_optional_cache_admission_failure_keeps_valid_gpu_scene_ready(qt_application,monkeypatch):
    canvas=MapCanvas();canvas.resize(400,300);canvas.set_snapshot(snapshot())
    monkeypatch.setattr(canvas,'prepare_frame',lambda:None)
    def fail(*args,**kwargs):raise RuntimeError('optional cache admission unavailable')
    monkeypatch.setattr(canvas._scene_variants,'put',fail)
    try:
        assert canvas._prepare_vectors() and canvas._prepare_gpu()
        assert canvas._gpu_scene is not None and canvas._gpu_key==canvas._revision
        assert not canvas._vector_gl_failed
    finally:canvas.close()


def test_real_page_query_proxy_options_prepare_a_complete_frame(qt_application,tmp_path):
    from collections.abc import Mapping
    from types import MappingProxyType
    from PySide6.QtCore import QSettings
    from map_page import MapPage
    page=MapPage(QSettings(str(tmp_path/'proxy-query.ini'),QSettings.Format.IniFormat))
    page.resize(960,680)
    try:
        page.set_snapshot(snapshot())
        assert isinstance(page.canvas.options['route_colors'],MappingProxyType)
        assert isinstance(page.canvas.options['building_colors'],Mapping)
        page.canvas.prepare_frame()
        assert page.canvas.can_export()
    finally:page.close()


def test_worker_option_clone_handles_nested_proxy_containers_colors_and_metric_legend(qt_application):
    from types import MappingProxyType
    from PySide6.QtGui import QColor
    from semantic_colors import MetricLegend
    color=QColor.fromRgbF(.12345,.23456,.34567,.45678)
    original_rgba=color.getRgbF()
    values=[color,{'bus'},('fixed',frozenset({'tram'}))]
    nested={'list':values}
    colors={3:'#123456'}
    canvas=MapCanvas()
    legend=MetricLegend('passengers','2026-10-22','today')
    canvas.set_options(route_colors=MappingProxyType(colors),
        mode_widths=MappingProxyType({'bus':7.,'nested':MappingProxyType(nested)}),legend_items=legend)
    try:
        surface=_FrameSurface(canvas)
        colors[3]='#654321';values[1].add('metro');values.append('late')
        color.setBlueF(.8)
        copied=surface.options['mode_widths']['nested']['list']
        assert len(copied)==3 and copied[1]=={'bus'}
        assert copied[0].getRgbF()==original_rgba
        assert copied[2]==('fixed',frozenset({'tram'}))
        assert isinstance(copied[2],tuple) and isinstance(copied[2][1],frozenset)
        assert surface.options['route_colors']=={3:'#123456'}
        assert surface.options['legend_items']==legend
    finally:canvas.close()


def test_real_query_proxy_options_keep_live_detached_keys_and_recent_scene_identity(qt_application,tmp_path,monkeypatch):
    from PySide6.QtCore import QSettings
    from map_canvas import _scene_variant_key
    from map_page import MapPage
    page=MapPage(QSettings(str(tmp_path/'proxy-cache.ini'),QSettings.Format.IniFormat))
    page.resize(960,680)
    try:
        page.set_snapshot(snapshot());canvas=page.canvas
        monkeypatch.setattr(canvas,'prepare_frame',lambda:None)
        surface=_FrameSurface(canvas)
        assert _scene_variant_key(canvas.snapshot,canvas.options)==_scene_variant_key(surface.snapshot,surface.options)
        assert canvas._prepare_vectors() and canvas._prepare_gpu()
        whole=canvas._gpu_scene
        canvas.set_options(direction='up')
        assert canvas._prepare_vectors() and canvas._prepare_gpu()
        canvas.set_options(direction='whole')
        assert canvas._prepare_vectors() and canvas._prepare_gpu()
        assert canvas._gpu_scene is whole
    finally:page.close()

def test_scene_cache_charges_worker_visibility_summary_without_traversing_tree(monkeypatch):
    import numpy as np
    from dataclasses import replace
    from types import SimpleNamespace
    from map_gpu_geometry import GpuScene, GpuLayers
    from map_scene_cache import retained_resources, SceneVariantCache
    empty=GpuScene(np.empty((0,2)),np.empty((0,4)),())
    baseline=retained_resources(GpuLayers(empty,empty))
    tree_bytes=2*1024*1024
    prepared=replace(empty,visibility=SimpleNamespace(estimated_bytes=tree_bytes))
    checkpoints=[]
    actual=retained_resources(GpuLayers(prepared,prepared),lambda:checkpoints.append(True))
    assert sum(size for _,size in actual.values())==sum(size for _,size in baseline.values())+tree_bytes
    assert len(actual)==1 and len(checkpoints)<3
    cache=SceneVariantCache(byte_budget=tree_bytes//2)
    cache.put('oversize-tree',GpuLayers(prepared,prepared))
    assert not len(cache) and cache.retained_bytes==0
