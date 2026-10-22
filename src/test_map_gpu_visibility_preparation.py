"""Compile immutable spatial trees in workers; renderer caches remain private."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
import threading

import numpy as np
import pytest

from map_gpu_geometry import GpuScene, _Builder, compile_gpu_layers, compile_gpu_scene
from map_gpu_renderer import GpuMapRenderer
from map_vector import build_vector_map
from test_map_gpu_geometry import _connection_surface


def _renderer(scene):
    r=GpuMapRenderer.__new__(GpuMapRenderer);r.scene=scene;r._commands=scene.commands
    r._rank_zoom=None
    r._rank_parameters=scene.materials[:,:8].astype(float)
    r._rank_inverse=np.arange(len(scene.materials))
    r._bounds=np.asarray([c.bounds for c in scene.commands],float).reshape(-1,4)
    r._minimum=np.asarray([c.min_zoom for c in scene.commands],np.float32)
    r._maximum=np.asarray([c.max_zoom for c in scene.commands],np.float32)
    r._command_rank=np.asarray([c.connection_rank for c in scene.commands])
    r._prepare_ordering()
    return r


def test_compiled_scene_binds_prebuilt_trees_without_building_on_renderer_thread(qt_application,monkeypatch):
    import map_gpu_geometry as geometry
    monkeypatch.setattr(geometry,'_load_strip',lambda:None)
    surface=_connection_surface();prepared=build_vector_map(surface)
    with ThreadPoolExecutor(max_workers=1) as pool:
        scene=pool.submit(compile_gpu_scene,surface,prepared).result()
    assert getattr(scene,'visibility',None) is not None, 'worker must prepare visibility before publishing scene'
    from map_gpu_visibility import BoundsTree
    def forbidden(*args,**kwargs):raise AssertionError('Renderer rebuilt a spatial tree on the GUI thread')
    monkeypatch.setattr(BoundsTree,'build',forbidden)
    renderer=_renderer(scene)
    assert renderer._command_candidates.tree is scene.visibility.command_tree
    assert renderer._member_candidates.tree is scene.visibility.member_tree
    for zoom in (.149,.15,.171739495,.25,1.,16.,100.):
        assert len(renderer._visible_indices(zoom,(-50.,-50.,100.,100.)))>0


def test_layer_compiler_builds_both_trees_on_worker_thread(qt_application,monkeypatch):
    from map_gpu_visibility import BoundsTree
    import map_gpu_geometry as geometry
    monkeypatch.setattr(geometry,'_load_strip',lambda:None)
    surface=_connection_surface();prepared=build_vector_map(surface)
    original=BoundsTree.build;threads=[]
    def record(*args,**kwargs):
        threads.append(threading.get_ident())
        return original(*args,**kwargs)
    monkeypatch.setattr(BoundsTree,'build',record)
    with ThreadPoolExecutor(max_workers=1) as pool:
        layers=pool.submit(compile_gpu_layers,surface,prepared).result()
    assert len(threads)==4 and all(identity!=threading.get_ident() for identity in threads)
    for scene in (layers.base,layers.routes):
        expected=[member[1] for c in scene.commands if c.connection_rank>=0 for member in c.connection_members]
        np.testing.assert_array_equal(scene.visibility.member_tree.boxes,np.asarray(expected,float).reshape(-1,4))
        np.testing.assert_array_equal(scene.visibility.command_tree.boxes,np.asarray([c.bounds for c in scene.commands]).reshape(-1,4))


def test_tree_storage_is_immutable_accounted_and_query_caches_are_not_shared():
    from map_gpu_visibility import BoundsCandidates, BoundsTree
    boxes=np.asarray([(x,y,x+1.,y+1.) for x in range(100) for y in range(100)],float)
    tree=BoundsTree.build(boxes)
    assert isinstance(tree.nodes,tuple)
    arrays=[tree.boxes,tree.all_indices]+[left for _,left,right in tree.nodes if right is None]
    for array in arrays:
        assert not array.flags.writeable
        with pytest.raises(ValueError):array.flat[0]=999
    with pytest.raises(FrozenInstanceError):tree.nodes=()
    assert tree.estimated_bytes>=sum(array.nbytes for array in arrays)
    a=BoundsCandidates(tree);b=BoundsCandidates(tree)
    first=a.query((0.,0.,2.,2.)).copy()
    b.query((90.,90.,92.,92.))
    assert a.tree is b.tree is tree and a._region!=b._region
    assert a._candidates is not b._candidates
    np.testing.assert_array_equal(a.query((0.,0.,2.,2.)),first)
    assert boxes[0,0]==0., 'preparing the tree must never modify caller bounds'


def test_tree_construction_observes_cancellation_during_recursive_partition():
    from map_gpu_visibility import BoundsTree
    checkpoints=[]
    def cancelled():
        checkpoints.append(True)
        return len(checkpoints)>=4
    boxes=np.asarray([(x,0.,x+1.,1.) for x in range(5000)],float)
    with pytest.raises(InterruptedError):BoundsTree.build(boxes,cancelled)
    assert len(checkpoints)==4


def test_cancelled_scene_metadata_is_never_published(qt_application,monkeypatch):
    import map_gpu_visibility as visibility
    import map_gpu_geometry as geometry
    monkeypatch.setattr(geometry,'_load_strip',lambda:None)
    surface=_connection_surface();prepared=build_vector_map(surface)
    calls=[]
    def interrupted(*args,**kwargs):
        calls.append(True)
        raise InterruptedError('cancelled metadata')
    monkeypatch.setattr(visibility.BoundsTree,'build',interrupted)
    with pytest.raises(InterruptedError):compile_gpu_scene(surface,prepared)
    assert calls==[True]


def test_old_four_field_pickle_state_and_explicit_none_keep_legacy_fallback(qt_application,monkeypatch):
    import map_gpu_geometry as geometry
    monkeypatch.setattr(geometry,'_load_strip',lambda:None)
    surface=_connection_surface();prepared=build_vector_map(surface)
    scene=compile_gpu_scene(surface,prepared)
    legacy=GpuScene.__new__(GpuScene)
    # This is the generated dataclass __setstate__ path used by a pickle
    # written before the optional fifth slot existed.
    legacy.__setstate__([scene.vertices,scene.materials,scene.commands,scene.indices])
    explicit_none=GpuScene(scene.vertices,scene.materials,scene.commands,scene.indices)
    assert not hasattr(legacy,'visibility') and explicit_none.visibility is None
    renderers=[_renderer(item) for item in (scene,legacy,explicit_none)]
    for zoom in (.149999999,.15,.2,16.,100.):
        expected=renderers[0]._visible_indices(zoom,(-10.,-20.,100.,30.))
        for renderer in renderers[1:]:
            np.testing.assert_array_equal(renderer._visible_indices(zoom,(-10.,-20.,100.,30.)),expected)


def test_prepared_tree_path_matches_independent_randomized_order_reference():
    from map_gpu_geometry import GpuCommand
    from map_gpu_visibility import SceneVisibility
    from test_map_gpu_candidates import _reference
    rng=np.random.default_rng(89115)
    materials=np.zeros((2,40),np.float32)
    materials[:,:8]=[(.65,3.6,20,1,2.1,6.8,8,4),(2,3,40,1,4,6,8,4)]
    materials[:,28]=2
    commands=[]
    for rank in (-1,1,4,-1,1,4):
        for index in range(90):
            x,y=rng.uniform(-1000,1000,2)
            members=tuple((int(rng.integers(10000)),(a,b,a+60.,b+60.),
                           float(rng.choice([1.,10.,100.])),index%2)
                          for a,b in rng.uniform(-1000,1000,(8,2))) if rank>=0 else ()
            commands.append(GpuCommand(0,3,'triangles',bounds=(x,y,x+80.,y+80.),
                connection_rank=rank,rank_material=index%2,owner_tile=(index%7,index%3),
                connection_members=members,min_zoom=.15 if index%5==0 else 0.,
                max_zoom=.15 if index%5==1 else np.inf))
    scene=GpuScene(np.zeros((3,16),np.float32),materials,tuple(commands),np.arange(3,dtype=np.uint32),
                   SceneVisibility.build(commands))
    first=_renderer(scene);second=_renderer(scene)
    assert first._command_candidates is not second._command_candidates
    assert first._command_candidates.tree is second._command_candidates.tree
    for zoom in (.0001,.14999999,.149999999,.15,.15000001,.171739495,.2,1.,16.,100.):
        for x,y in [(-1000.,-1000.),(-999.,-999.),(0.,0.),(700.,700.),(1e8,1e8)]:
            box=(x,y,x+300.,y+300.)
            assert list(first._visible_indices(zoom,box))==_reference(first,zoom,box)
            # A second renderer may navigate elsewhere without changing the
            # first context's cached candidate membership or derived order.
            second._visible_indices(zoom,(-x,-y,-x+100.,-y+100.))
            assert list(first._visible_indices(zoom,box))==_reference(first,zoom,box)


def _baseline_finish(self):
    """The cf468d8 finish path, before visibility preparation was introduced."""
    from map_gpu_visibility import cull_commands
    vertices=(np.concatenate(self.chunks).astype(np.float32,copy=False) if self.chunks else
              np.empty((0,16),np.float32))
    materials=np.asarray(self.materials,np.float32).reshape(-1,40)
    indices=np.concatenate(self.index_chunks) if self.index_chunks else np.empty(0,np.uint32)
    for values in (vertices,materials,indices):values.setflags(write=False)
    scene=GpuScene(vertices,materials,tuple(self.commands),indices)
    return replace(scene,commands=cull_commands(scene))


@pytest.mark.parametrize('layered',[False,True])
def test_preparation_preserves_baseline_geometry_commands_and_legacy_order(qt_application,monkeypatch,layered):
    import map_gpu_geometry as geometry
    monkeypatch.setattr(geometry,'_load_strip',lambda:None)
    surface=_connection_surface();prepared=build_vector_map(surface)
    compile_scene=compile_gpu_layers if layered else compile_gpu_scene
    actual=compile_scene(surface,prepared)
    monkeypatch.setattr(_Builder,'finish',_baseline_finish)
    baseline=compile_scene(surface,prepared)
    for new,old in ([(actual.base,baseline.base),(actual.routes,baseline.routes)] if layered else [(actual,baseline)]):
        for name in ('vertices','materials','indices'):
            np.testing.assert_array_equal(getattr(new,name),getattr(old,name))
        assert new.commands==old.commands
        assert getattr(new,'visibility',None) is not None and getattr(old,'visibility',None) is None
        before=_renderer(old);after=_renderer(new)
        for zoom in (.0001,.149999999,.15,.171739495,.25,1.,16.,100.):
            for box in ((-50.,-50.,100.,100.),(20.,-3.,27.,1.),(1e8,1e8,1e8+1,1e8+1)):
                np.testing.assert_array_equal(after._visible_indices(zoom,box),before._visible_indices(zoom,box))
