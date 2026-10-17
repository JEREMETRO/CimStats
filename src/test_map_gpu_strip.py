"""A native True must retain the independent scalar interval certificate."""
import ctypes
import os
from pathlib import Path
import pytest
from functools import lru_cache
import math
import numpy as np

_EPS=np.finfo(np.float32).eps


def _out(lo,hi):
    return np.nextafter(lo,-np.inf),np.nextafter(hi,np.inf)


def _add(a,b):return _out(a[0]+b[0],a[1]+b[1])
def _sub(a,b):return _out(a[0]-b[1],a[1]-b[0])
def _mul(a,b):
    p=a[0]*b[0];q=a[0]*b[1];r=a[1]*b[0];s=a[1]*b[1]
    return _out(np.minimum(np.minimum(p,q),np.minimum(r,s)),
                np.maximum(np.maximum(p,q),np.maximum(r,s)))


@lru_cache(maxsize=4096)
def _width_bounds(p,lo,hi):
    overview,detail,physical,rank=p
    if physical>0 and rank<5.5 and lo>=.25:
        return physical,physical
    if hi<=.45:
        # Symbolic width / zoom is A/zoom+B on this branch.
        a=overview-(detail-overview)*.10/.35;b=(detail-overview)/.35
        values=(a/lo+b,a/hi+b)
    elif lo>=.45:
        # Both sqrt(z)/z and the capped 1/z branch decrease.
        values=(detail*min(2.2,math.sqrt(lo/.45))/lo,
                detail*min(2.2,math.sqrt(hi/.45))/hi)
    else:
        return None
    symbolic=_out(min(values),max(values))
    if not(physical>0 and rank<5.5):return symbolic
    a=max(0.,min(1.,(lo-.10)/.15));b=max(0.,min(1.,(hi-.10)/.15))
    blend=_out(a*a*(3-2*a),b*b*(3-2*b))
    return _add(_mul(symbolic,_sub((1.,1.),blend)),
                _mul((physical,physical),blend))


@lru_cache(maxsize=128)
def _topology(n):
    left=np.arange(n-1);right=2*n-1-left
    triangles=np.vstack((np.column_stack((left,left+1,right-1)),
                          np.column_stack((left,right-1,right))))
    a,b=np.triu_indices(2*n,k=2)
    keep=~((a==0)&(b==2*n-1))
    return triangles,a[keep],b[keep]


def _linear(base,coefficients,ranges,error):
    lo=base.copy();hi=base.copy()
    for index,(lower,upper) in enumerate(ranges):
        c=coefficients[...,index]
        low,high=_out(np.minimum(c*lower,c*upper),np.maximum(c*lower,c*upper))
        lo,hi=_add((lo,hi),(low,high))
    return _out(lo-error,hi+error)


def _cross_bounds(a,b):
    return _sub(_mul((a[0][...,0],a[1][...,0]),(b[0][...,1],b[1][...,1])),
                _mul((a[0][...,1],a[1][...,1]),(b[0][...,0],b[1][...,0])))


def _certify_band(base,coeff,ranges,error,triangles,pair_a,pair_b):
    def difference(a,b):
        # Subtract coefficient vectors before interval evaluation, retaining
        # the correlation of a common width function at nearby vertices.
        return _linear(base[a]-base[b],coeff[a]-coeff[b],ranges,error[a]+error[b])
    cross=_cross_bounds(difference(triangles[:,1],triangles[:,0]),
                        difference(triangles[:,2],triangles[:,0]))
    if not(np.all(cross[0]>0) or np.all(cross[1]<0)):return False
    lower,upper=_linear(base,coeff,ranges,error)
    end=np.roll(np.arange(len(base)),-1)
    elo=np.minimum(lower,lower[end]);ehi=np.maximum(upper,upper[end])
    separated=np.any((ehi[pair_a]<elo[pair_b])|(ehi[pair_b]<elo[pair_a]),axis=1)
    a=pair_a[~separated];b=pair_b[~separated]
    if len(a):
        ab=difference(end[a],a);cd=difference(end[b],b)
        x=_cross_bounds(ab,difference(b,a));y=_cross_bounds(ab,difference(end[b],a))
        same=((x[0]>0)&(y[0]>0))|((x[1]<0)&(y[1]<0))
        x=_cross_bounds(cd,difference(a,b));y=_cross_bounds(cd,difference(end[a],b))
        same|=((x[0]>0)&(y[0]>0))|((x[1]<0)&(y[1]<0))
        if not np.all(same):return False
    # Adjacent edges may be collinear in the forward direction, but cannot
    # fold back over one another. Include the closing edges in this check.
    previous=np.roll(np.arange(len(base)),1)
    incoming=difference(np.arange(len(base)),previous)
    outgoing=difference(end,np.arange(len(base)))
    turn=_cross_bounds(incoming,outgoing)
    dot=_add(_mul((incoming[0][:,0],incoming[1][:,0]),(outgoing[0][:,0],outgoing[1][:,0])),
             _mul((incoming[0][:,1],incoming[1][:,1]),(outgoing[0][:,1],outgoing[1][:,1])))
    return bool(np.all((turn[0]>0)|(turn[1]<0)|(dot[0]>0)))



def scalar_pair(rows,material):
    rows=np.asarray(rows,dtype=np.float32);m=np.asarray(material,dtype=np.float32)
    if len(rows)<4 or len(rows)%2 or not np.isfinite(rows).all() or not np.isfinite(m[:8]).all():return False
    p=tuple(map(float,m[:4]));q=tuple(map(float,m[4:8]))
    if not(p[2]>0 and q[2]>0 and p[3]<5.5 and q[3]<5.5):return False
    transition=np.linspace(.15,.25,9)
    bands=tuple(zip(transition[:-1],transition[1:]))+((.25,100.),)
    triangles,a,b=_topology(len(rows)//2)
    for shell in (False,True):
        values=rows.astype(float).copy()
        if not shell:values[:,7]=0
        normal=values[:,2:4]
        coeff=normal[:,:,None]*values[:,None,[4,5,7]]
        original_magnitude=np.abs(coeff).copy()
        offset=normal*values[:,6,None];base=values[:,:2]+offset
        fixed=np.abs(values[:,:2])+np.abs(offset)
        if p==q:coeff[:,:,0]+=coeff[:,:,1];coeff[:,:,1]=0
        for lo,hi in bands:
            ranges=(_width_bounds(p,lo,hi),_width_bounds(q,lo,hi),_out(.45/hi,.45/lo))
            # Shader mix/dot intermediates are evaluated before geometric
            # correlation is applied. Neither cancellation may shrink this
            # rounding budget to the much smaller final mathematical value.
            width_magnitude=[abs(p[0])/lo+2.2*abs(p[1])/lo+abs(p[2])+max(map(abs,ranges[0])),
                             abs(q[0])/lo+2.2*abs(q[1])/lo+abs(q[2])+max(map(abs,ranges[1])),
                             max(map(abs,ranges[2]))]
            magnitude=fixed+sum(original_magnitude[:,:,i]*width_magnitude[i] for i in range(3))
            error=64*_EPS*(1+magnitude)
            if not _certify_band(base,coeff,ranges,error,triangles,a,b):return False
    return True


@pytest.fixture(scope='module')
def native_strip():
    from map_gpu_strip import NativeStrip
    from map_gpu_submit import local_library
    path=Path(os.environ.get('CIM2_STRIP_TEST_DLL',local_library()))
    if not path.is_file():pytest.skip('Build strip helper for native acceptance')
    try:return NativeStrip(path)
    except AttributeError:pytest.skip('Existing helper has no strip exports')


def straight(count=3):
    rows=np.zeros((2*count,16),np.float32)
    points=np.column_stack((np.linspace(0,100,count),np.zeros(count)))
    rows[:count,:2]=points;rows[count:,:2]=points[::-1]
    rows[:,3]=1;rows[:count,4]=-.5;rows[count:,4]=.5
    rows[:count,7]=-.5;rows[count:,7]=.5
    m=np.zeros(40,np.float32);m[:8]=(2,3,2,1,2,3,2,1);m[31]=np.inf
    return rows,m


def test_straight_pair_is_proved_with_legal_infinite_zoom(native_strip):
    rows,m=straight();before=rows.copy();material=m.copy()
    assert scalar_pair(rows,m)
    assert native_strip(rows,m)
    np.testing.assert_array_equal(rows,before);np.testing.assert_array_equal(m,material)


def test_equal_width_merges_full_vector_coefficients(native_strip):
    rows,m=straight()
    rows[:3,4]=-100;rows[:3,5]=99.5
    rows[3:,4]=100;rows[3:,5]=-99.5
    assert scalar_pair(rows,m)
    assert native_strip(rows,m)


@pytest.mark.parametrize('backend',['native','scalar'])
def test_equal_width_shader_cancellation_retains_original_error_terms(native_strip,backend):
    rows,m=straight()
    rows[:,:2]=((0,0),(10,0),(20,0),(20,0),(10,0),(0,0))
    amplitude=np.array((10000000,10000003,10000000),np.float32)
    rows[:3,4]=-amplitude;rows[:3,5]=amplitude-1
    rows[3:,4]=-.5;rows[3:,5]=0
    # A valid non-FMA shader evaluation exhibits mixed triangle orientation.
    # The exact mathematical width has no problem: the lost cancellation
    # terms must remain in the shader's float32 error budget.
    zoom=np.float32(.839);width=np.float32(2)*zoom
    displacement=rows[:,4]*width+rows[:,5]*width
    screen=rows[:,:2]*zoom+rows[:,2:4]*displacement[:,None]
    triangles,_,_=_topology(3)
    a=screen[triangles[:,1]]-screen[triangles[:,0]]
    b=screen[triangles[:,2]]-screen[triangles[:,0]]
    area=a[:,0]*b[:,1]-a[:,1]*b[:,0]
    assert np.any(area<0) and np.any(area>0)
    assert not (native_strip(rows,m) if backend=='native' else scalar_pair(rows,m))


def test_shell_must_be_proved_independently_of_core(native_strip):
    rows,m=straight();core=rows.copy();core[:,7]=0
    assert scalar_pair(core,m) and native_strip(core,m)
    rows[:3,7]=2;rows[3:,7]=-2
    # The core remains simple, but the shell collapses inside [.25,100].
    assert not scalar_pair(rows,m)
    assert not native_strip(rows,m)


@pytest.mark.parametrize('count',[2,32])
def test_vertex_limits_and_reversed_winding(native_strip,count):
    rows,m=straight(count)
    assert native_strip(rows,m) and scalar_pair(rows,m)
    assert native_strip(rows[::-1],m) and scalar_pair(rows[::-1],m)


@pytest.mark.parametrize('value',[np.nan,np.inf,-np.inf,np.finfo(np.float32).max])
def test_nonfinite_and_extreme_geometry_parameters(native_strip,value):
    rows,m=straight();m[0]=value
    assert not native_strip(rows,m)
    rows,m=straight();rows[0,2]=value
    assert not native_strip(rows,m)


def test_smallest_width_and_unresolvable_coordinates_fall_back(native_strip):
    rows,m=straight();m[[0,1,2,4,5,6]]=np.nextafter(np.float32(0),np.float32(1))
    assert not native_strip(rows,m)
    rows,m=straight();rows[:,:2]+=np.float32(1e7)
    assert not native_strip(rows,m)


@pytest.mark.parametrize('change',['crossed','duplicate','folded','collapsed','nan','huge','rank','physical','odd','overlimit'])
def test_uncertain_or_outside_domain_retains_winding(native_strip,change):
    rows,m=straight()
    if change=='crossed':rows[[3,5]]=rows[[5,3]]
    elif change=='duplicate':rows[1]=rows[0]
    elif change=='folded':rows[1,:2]=(110,0)
    elif change=='collapsed':rows[:,:2]+=np.float32(1e8)
    elif change=='nan':rows[0,15]=np.nan
    elif change=='huge':rows[0,0]=np.finfo(np.float32).max
    elif change=='rank':m[3]=5.5
    elif change=='physical':m[6]=0
    elif change=='odd':rows=rows[:-1]
    elif change=='overlimit':rows,m=straight(33)
    assert not native_strip(rows,m)


def test_500_varied_contours_never_exceed_scalar_certificate(native_strip):
    rng=np.random.default_rng(20261018);accepted=0
    for i in range(500):
        rows,m=straight(2+i%13)
        n=len(rows)//2
        rows[:n,1]=np.cumsum(rng.normal(0,.7,n));rows[n:,1]=rows[:n,1][::-1]
        angle=rng.uniform(-np.pi,np.pi);rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        rows[:,:2]=rows[:,:2]@rotation;rows[:,2:4]=rows[:,2:4]@rotation
        fraction=np.linspace(0,1,n).astype(np.float32)
        rows[:,5]=rows[:,4]*np.r_[fraction,fraction[::-1]];rows[:,4]-=rows[:,5]
        if i%3:m[4:8]=(2.5,4,3,2)
        if i%7==0:rows[[0,n]]=rows[[n,0]]
        result=native_strip(rows,m)
        if result:assert scalar_pair(rows,m);accepted+=1
    assert accepted>250


def test_loader_missing_export_and_invalid_abi_are_optional(monkeypatch,tmp_path):
    import map_gpu_strip as module
    dll=tmp_path/'optional.dll';dll.write_bytes(b'not loaded')
    monkeypatch.setattr(module,'local_library',lambda:dll)
    monkeypatch.setattr(module.ctypes,'CDLL',lambda *args:object())
    assert module.load_strip() is None
    class Function:
        def __call__(self):return 99
    class Library:map_strip_abi=Function()
    monkeypatch.setattr(module.ctypes,'CDLL',lambda *args:Library())
    assert module.load_strip() is None


def test_invalid_shapes_and_cancellation(native_strip):
    from map_vector import VectorMapCancelled
    rows,m=straight()
    assert not native_strip(rows[:,:15],m)
    assert not native_strip(rows,m[:39])
    with pytest.raises(VectorMapCancelled):native_strip(rows,m,cancelled=lambda:True)
    calls=[]
    def cancelled():calls.append(1);return len(calls)>1
    with pytest.raises(VectorMapCancelled):native_strip(rows,m,cancelled=cancelled)


def test_raw_c_capacity_and_null_guards(native_strip):
    rows,m=straight();scratch=np.empty((64,32),np.float64)
    fn=native_strip._pair
    assert fn(0,len(rows),m.ctypes.data,scratch.ctypes.data,scratch.nbytes)==0
    assert fn(rows.ctypes.data,len(rows),0,scratch.ctypes.data,scratch.nbytes)==0
    assert fn(rows.ctypes.data,len(rows),m.ctypes.data,0,scratch.nbytes)==0
    assert fn(rows.ctypes.data,len(rows),m.ctypes.data,scratch.ctypes.data,1)==0
    assert fn(rows.ctypes.data,len(rows),m.ctypes.data,scratch.ctypes.data+1,scratch.nbytes-1)==0
    assert fn(rows.ctypes.data+1,len(rows),m.ctypes.data,scratch.ctypes.data,scratch.nbytes)==0
    assert fn(rows.ctypes.data,len(rows),m.ctypes.data+1,scratch.ctypes.data,scratch.nbytes)==0
    assert fn(rows.ctypes.data,ctypes.c_size_t(-1).value,m.ctypes.data,scratch.ctypes.data,scratch.nbytes)==0
    assert fn(rows.ctypes.data,len(rows),m.ctypes.data,rows.ctypes.data,scratch.nbytes)==0
    before=rows.copy();material=m.copy()
    assert fn(rows.ctypes.data,len(rows),m.ctypes.data,m.ctypes.data,scratch.nbytes)==0
    np.testing.assert_array_equal(rows,before);np.testing.assert_array_equal(m,material)
    scratch.fill(12345)
    assert fn(rows.ctypes.data,len(rows),m.ctypes.data,scratch.ctypes.data,scratch.nbytes)==1
    # C receives the required capacity but must not write beyond this contour.
    np.testing.assert_array_equal(scratch[len(rows):],12345)
