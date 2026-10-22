"""Conservative candidates must reduce work without changing draw order."""
import math
import numpy as np
from map_gpu_geometry import GpuCommand, GpuScene
from map_gpu_renderer import GpuMapRenderer


def _renderer(commands, materials):
    r=GpuMapRenderer.__new__(GpuMapRenderer)
    count=max((max(c.start+c.count,c.cover_start+c.cover_count) for c in commands),default=0)
    r.scene=GpuScene(np.zeros((count,16),np.float32),materials,tuple(commands),np.arange(count,dtype=np.uint32))
    r._commands=r.scene.commands
    r._rank_zoom=None
    r._rank_parameters=materials[:,:8].astype(float);r._rank_inverse=np.arange(len(materials))
    r._bounds=np.asarray([c.bounds for c in commands],dtype=float).reshape(-1,4)
    r._minimum=np.asarray([c.min_zoom for c in commands],np.float32)
    r._maximum=np.asarray([c.max_zoom for c in commands],np.float32)
    r._command_rank=np.asarray([c.connection_rank for c in commands])
    r._prepare_ordering()
    return r


def test_candidate_neighborhood_is_bounded_reused_and_conservative():
    from map_gpu_visibility import BoundsCandidates
    boxes=np.array([(x,y,x+2,y+2) for x in range(-1000,1000,10) for y in range(-1000,1000,10)],float)
    index=BoundsCandidates(boxes)
    first=index.query((-10.,-10.,10.,10.))
    assert len(first)<len(boxes)//100
    second=index.query((-9.,-9.,11.,11.))
    assert first is second
    for bounds in ((-10.,-10.,10.,10.),(-9.,-9.,11.,11.),(998.,998.,1000.,1000.),
                   (-1e8,-1e8,1e8,1e8),(0.,0.,0.,0.),(5000.,5000.,6000.,6000.)):
        candidates=index.query(bounds)
        exact=np.flatnonzero((boxes[:,0]<=bounds[2])&(boxes[:,2]>=bounds[0])&
                             (boxes[:,1]<=bounds[3])&(boxes[:,3]>=bounds[1]))
        assert set(exact).issubset(candidates)
    assert len(index.query((-1.,-1.,1.,1.)))<len(boxes)//100


def test_collinear_point_bounds_still_prune_distant_candidates():
    from map_gpu_visibility import BoundsCandidates
    boxes=np.array([(x,0.,x,0.) for x in range(10000)],float)
    index=BoundsCandidates(boxes)
    assert set(index.query((.5,-1.,1.5,1.)))=={1}
    assert len(index.query((-100.,10.,20000.,20.)))==0


def test_context_destruction_releases_candidate_cache_lifetime():
    import gc
    import weakref
    from types import SimpleNamespace
    r=_renderer([GpuCommand(0,3,'triangles')],np.empty((0,40),np.float32))
    candidate=weakref.ref(r._command_candidates)
    r._routes_renderer=None;r.texture=None
    resource=SimpleNamespace(destroy=lambda:None)
    r.vertex_buffer=r.index_buffer=r.vertex_array=resource
    r.destroy();gc.collect()
    assert candidate() is None


def test_offscreen_command_member_still_controls_visible_tile_order():
    materials=np.zeros((1,40),np.float32)
    materials[0,:8]=(2,3,12,1,4,6,20,4);materials[0,28]=2
    near=(0.,0.,10.,10.);far=(1000.,1000.,1010.,1010.)
    commands=[GpuCommand(0,3,'triangles',bounds=far,connection_rank=1,rank_material=0,
                        owner_tile=(0,0),connection_members=((1,near,100.,0),)),
              GpuCommand(0,3,'triangles',bounds=near,connection_rank=1,rank_material=0,
                        owner_tile=(1,0),connection_members=((5,near,100.,0),)),
              GpuCommand(0,3,'triangles',bounds=near,connection_rank=1,rank_material=0,
                        owner_tile=(0,0),connection_members=((10,near,100.,0),))]
    assert list(_renderer(commands,materials)._visible_indices(.1,near))==[2,1]


def _overlap(a,b):
    return a[0]<=b[2] and a[2]>=b[0] and a[1]<=b[3] and a[3]>=b[1]


def _width(p,z):
    w=p[0]+(p[1]-p[0])*max(0.,min(1.,(z-.1)/.35))
    if z>.45:w=p[1]*min(2.2,math.sqrt(z/.45))
    t=max(0.,min(1.,(z-.1)/.15));t=t*t*(3.-2.*t)
    return w*(1.-t)+p[2]*z*t if p[2]>0 and p[3]<5.5 else w


def _reference(r,zoom,bounds):
    z=float(np.float32(zoom));first={};tile={};maximum=np.iinfo(np.int64).max
    for i,c in enumerate(r.scene.commands):
        if c.connection_rank<0:first[i]=i;continue
        orders=[]
        for order,box,span,mid in c.connection_members:
            p=r.scene.materials[mid,:8].astype(float);a=_width(p[:4],z);b=_width(p[4:],z)
            tolerance=64*np.finfo(np.float32).eps*(1+abs(a)+abs(b)+abs(p[2]*z)+abs(p[6]*z))
            ranks=(int(p[3]),int(p[7])) if abs(a-b)<=tolerance else (int(p[3] if a<=b else p[7]),)
            s=span*z
            if (_overlap(box,bounds) and c.connection_rank in ranks and
                    (z>=.15 or s+32*np.finfo(np.float32).eps*(1+abs(s))>=1.5)):
                orders.append(order)
        first[i]=min(orders,default=maximum)
        group=int(r._tile_groups[i]);tile[group]=min(tile.get(group,maximum),first[i])
    selected=[i for i,c in enumerate(r.scene.commands) if _overlap(c.bounds,bounds) and
              np.float32(c.min_zoom)<=z<np.float32(c.max_zoom) and
              (c.connection_rank<0 or first[i]!=maximum)]
    return sorted(selected,key=lambda i:(int(r._blocks[i]),
                  0 if r.scene.commands[i].connection_rank<0 else tile[int(r._tile_groups[i])],first[i],i))


def test_candidates_recompute_member_and_tile_order_for_every_view_and_zoom():
    rng=np.random.default_rng(97531)
    materials=np.zeros((4,40),np.float32)
    materials[:,:8]=[(2,3,12,1,4,6,20,4),(2,3,40,1,4,6,8,4),
                       (.65,3.6,20,1,2.1,6.8,8,4),(2,3,12,1,4,6,20,4)]
    materials[:,28]=2
    commands=[]
    for rank in (-1,1,4,-1,1,4):
        for i in range(90):
            x,y=rng.uniform(-500,500,2);box=(x,y,x+80,y+80)
            members=tuple((int(rng.integers(2000)),(a,b,a+50,b+50),float(rng.choice([1.,10.,100.])),i%4)
                          for a,b in rng.uniform(-500,500,(5,2))) if rank>=0 else ()
            commands.append(GpuCommand(0,3,'triangles',bounds=box,connection_rank=rank,
                rank_material=i%4,owner_tile=(i%7,i%3),connection_members=members,
                min_zoom=.15 if i%5==0 else 0.,max_zoom=.15 if i%5==1 else math.inf))
    r=_renderer(commands,materials)
    for z in (.0001,.14999999,.149999999,.15,.15000001,.171739495,.2,.25,1.,16.,100.):
        for x,y in [(-200.,-200.),(-199.,-199.),(0.,0.),(400.,400.),(-1e8,-1e8)]:
            bounds=(x,y,x+250.,y+250.)
            assert list(r._visible_indices(z,bounds))==_reference(r,z,bounds)
