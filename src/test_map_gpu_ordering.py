"""Retained draw ordering preserves saved rank/tile/member order."""
import numpy as np
from map_gpu_geometry import GpuScene,GpuCommand
from map_gpu_renderer import GpuMapRenderer,_road_widths


def test_vectorized_visibility_matches_scalar_saved_order_at_rank_crossovers():
    materials=np.zeros((3,40),dtype=np.float32)
    materials[:,:8]=[(2,3,12,1,4,6,20,4),(2,3,40,1,4,6,8,4),(2,3,12,1,4,6,20,4)]
    materials[:,28]=2
    box=(-20.,-20.,20.,20.);away=(100.,100.,200.,200.)
    commands=[GpuCommand(0,3,'triangles',bounds=box)]
    for rank in (1,4):
        for mid,tile,members in ((0,(1,0),((9,box,20.,0),(2,away,20.,0))),
                                 (1,(0,0),((5,box,20.,1),)),
                                 (2,(1,0),((3,box,1.,2),))):
            commands.append(GpuCommand(mid*3,3,'triangles',bounds=box,
                connection_rank=rank,rank_material=mid,owner_tile=tile,
                original_order=members[0][0],connection_members=members))
    commands.append(GpuCommand(0,3,'triangles',bounds=box))
    vertices=np.zeros((3,16),dtype=np.float32);vertices[:,8]=range(3)
    scene=GpuScene(vertices,materials,tuple(commands),np.repeat(np.arange(3,dtype=np.uint32),3))
    r=GpuMapRenderer.__new__(GpuMapRenderer);r.scene=scene;r._rank_zoom=None
    r._rank_parameters=materials[:,:8].astype(float);r._rank_inverse=np.arange(3)
    r._bounds=np.asarray([c.bounds for c in commands]);r._minimum=np.zeros(len(commands))
    r._maximum=np.full(len(commands),np.inf)
    r._command_rank=np.asarray([c.connection_rank for c in commands])
    r._prepare_ordering()
    for zoom in (.1,.149,.15,.2,.25,1.,16.,100.):
        source=_road_widths(materials[:,:4],zoom);target=_road_widths(materials[:,4:8],zoom)
        ranks=np.where(source<=target,materials[:,3],materials[:,7]).astype(int)
        expected=[commands[0]]
        for rank in (1,4):
            selected=[]
            for c in commands[1:-1]:
                if c.connection_rank!=rank:continue
                valid=[order for order,b,span,mid in c.connection_members
                       if b==box and ranks[mid]==rank and (zoom>=.15 or span*zoom>=1.5)]
                if valid:selected.append((c,min(valid)))
            tile_first={c.owner_tile:min(first for other,first in selected if other.owner_tile==c.owner_tile)
                        for c,_ in selected}
            expected.extend(c for c,_ in sorted(selected,key=lambda item:(tile_first[item[0].owner_tile],item[1])))
        expected.append(commands[-1])
        assert list(r._visible_commands(zoom,box))==expected


def test_cpu_keeps_both_rank_candidates_at_shader_float_width_crossover():
    r=GpuMapRenderer.__new__(GpuMapRenderer);r._rank_zoom=None
    r._rank_parameters=np.asarray([(.65,3.6,20,1,2.1,6.8,8,4)],dtype=np.float32).astype(float)
    r._rank_inverse=np.array([0])
    r._ranks(.171739495)
    assert int(r._material_rank_masks[0])==(1<<1)|(1<<4)
    r._ranks(1.)
    assert int(r._material_rank_masks[0])==1<<4


def test_draw_table_rejects_out_of_buffer_and_negative_ranges():
    from map_gpu_renderer import _draw_command_table
    import pytest
    for command in (GpuCommand(-1,3,'triangles'),GpuCommand(3,6,'triangles'),
                    GpuCommand(0,3,'winding',5,3),GpuCommand(0,3,'bogus')):
        with pytest.raises(ValueError):_draw_command_table([command],6)
    assert _draw_command_table([GpuCommand(0,6,'triangles')],6).shape==(1,7)


def test_retained_triangle_chunks_keep_exact_index_order_and_physical_margins():
    from map_gpu_renderer import _cull_commands
    vertices=np.zeros((24,16),dtype=np.float32)
    vertices[:12,:2]=[(0.,0.)]*12;vertices[12:,:2]=[(1000.,2000.)]*12
    materials=np.zeros((1,40),dtype=np.float32);materials[0,2]=100.
    scene=GpuScene(vertices,materials,(GpuCommand(0,24,'triangles',bounds=(-100.,-100.,1100.,2100.)),),
                   np.arange(24,dtype=np.uint32))
    chunks=_cull_commands(scene,12)
    assert [(c.start,c.count) for c in chunks]==[(0,12),(12,12)]
    assert chunks[0].bounds==(-50.,-50.,50.,50.)
    assert chunks[1].bounds==(950.,1950.,1050.,2050.)
    winding=GpuCommand(0,12,'winding',12,6,bounds=(0.,0.,10.,10.))
    assert _cull_commands(GpuScene(vertices,materials,(winding,),scene.indices),3)==(winding,)


def test_lod_boundary_uses_the_same_float32_zoom_as_shader():
    commands=(GpuCommand(0,3,'triangles',max_zoom=.15),GpuCommand(3,3,'triangles',min_zoom=.15))
    r=GpuMapRenderer.__new__(GpuMapRenderer)
    r.scene=GpuScene(np.zeros((6,16),np.float32),np.empty((0,40),np.float32),commands,np.arange(6,dtype=np.uint32))
    r._bounds=np.zeros((2,4));r._minimum=np.array([0.,.15])
    r._maximum=np.array([.15,np.inf]);r._command_rank=np.array([-1,-1])
    r._prepare_ordering()
    assert list(r._visible_commands(.149999999,(-1.,-1.,1.,1.)))==[commands[1]]


def test_python_fallback_and_reused_native_rows_keep_identical_command_ranges(monkeypatch):
    from types import SimpleNamespace
    from shiboken6 import VoidPtr
    import map_gpu_renderer as module
    from test_map_gpu_candidates import _renderer
    commands=(GpuCommand(0,3,'triangles'),GpuCommand(3,3,'winding',6,3),
              GpuCommand(9,3,'triangles'))
    r=_renderer(commands,np.empty((0,40),np.float32))
    class GL:
        def __init__(self):self.draws=[]
        def glDrawElements(self,mode,count,kind,offset):self.draws.append((int(offset)//4,count))
        def __getattr__(self,name):return lambda *a:None
    gl=GL();resource=GL()
    monkeypatch.setattr(module,'QOpenGLContext',SimpleNamespace(currentContext=lambda:
                        SimpleNamespace(functions=lambda:gl)))
    r.vertex_array=r.vertex_buffer=r.index_buffer=r.texture=r.program=resource
    r.upload=lambda scene:None;r._texture_width=1024;r._screen_margin=40.
    r._uniforms={key:i for i,key in enumerate(('materials','materialTextureWidth','center',
                'viewport','zoom','connectionRank','shellPass'))}
    r._draw_offsets={i:VoidPtr(i*4) for i in (0,3,6,9)}
    r._draw_table=module._draw_command_table(commands,12)
    r._submitter=None
    r.paint(r.scene,(0.,0.),1.,100,100,1.)
    assert gl.draws==[(0,3),(3,3),(6,3),(9,3)]
    received=[]
    r._submitter=lambda rows,*locations:received.append((rows.copy(),rows.ctypes.data))
    for center in ((0.,0.),(1.,1.)):
        r.paint(r.scene,center,1.,100,100,1.)
    expected=[[0,3,0,0,0,-1,-1],[3,3,1,6,3,-1,-1],[9,3,0,0,0,-1,-1]]
    assert received[0][0].tolist()==received[1][0].tolist()==expected
    assert received[0][1]==received[1][1]
