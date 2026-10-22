"""Native command dispatch retains the exact ordered GL state protocol."""
import ctypes
import sys
from pathlib import Path
import numpy as np
import pytest


def _dispatch(commands):
    if sys.platform!='win32':pytest.skip('Windows native helper')
    from map_gpu_submit import NativeSubmitter,local_library
    path=local_library()
    if not path.is_file():pytest.skip('Build native helper before native acceptance')
    calls=[];callbacks=[]
    signatures=((None,ctypes.c_uint,ctypes.c_int,ctypes.c_uint,ctypes.c_void_p),
                (None,ctypes.c_uint),(None,ctypes.c_uint),
                (None,ctypes.c_uint,ctypes.c_int,ctypes.c_uint),
                (None,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint),
                (None,ctypes.c_ubyte,ctypes.c_ubyte,ctypes.c_ubyte,ctypes.c_ubyte),
                (None,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint),
                (None,ctypes.c_int,ctypes.c_int))
    for index,signature in enumerate(signatures):
        def record(*args,index=index):calls.append((index,*args))
        callbacks.append(ctypes.WINFUNCTYPE(*signature)(record))
    pointers=[ctypes.cast(f,ctypes.c_void_p).value for f in callbacks]
    submit=NativeSubmitter(path,pointers)
    submit(commands,7,8)
    return calls


def test_native_dispatch_matches_independent_winding_and_rank_sequence():
    # start/count, winding, cover start/count, rank, shell (index offsets).
    commands=np.array([[3,6,0,0,0,-1,-1],[9,12,1,21,6,1,1],[27,9,1,36,6,1,1],
                       [42,6,0,0,0,4,0]],dtype=np.int64)
    calls=_dispatch(commands)
    assert [c for c in calls if c[0]==7 and c[1]==7]==[(7,7,-1),(7,7,1),(7,7,4)]
    assert [c for c in calls if c[0]==7 and c[1]==8]==[(7,8,-1),(7,8,1),(7,8,0)]
    assert [c for c in calls if c[0]==0]==[(0,4,6,5125,12),(0,4,12,5125,36),
        (0,4,6,5125,84),(0,4,9,5125,108),(0,4,6,5125,144),(0,4,6,5125,168)]
    assert [c for c in calls if c[0] in (1,2)]==[(1,2960),(2,2960)]
    assert [c for c in calls if c[0]==5]==[(5,0,0,0,0),(5,1,1,1,1)]*2


def test_native_batches_only_complete_contiguous_triangles_with_identical_state():
    commands=np.array([[0,3,0,0,0,-1,-1],[3,6,0,0,0,-1,-1],
        [9,3,0,0,0,1,-1],[12,3,0,0,0,1,0],[15,3,1,18,3,1,0],
        [21,3,0,0,0,1,0],[24,4,0,0,0,1,0],[28,2,0,0,0,1,0],
        [30,3,0,0,0,1,0],[40,3,0,0,0,1,0]],np.int64)
    calls=_dispatch(commands)
    draws=[(c[4]//4 if c[4] else 0,c[2]) for c in calls if c[0]==0]
    assert draws==[(0,9),(9,3),(12,3),(15,3),(18,3),(21,3),(24,4),(28,2),(30,3),(40,3)]
    # Expand submitted triangle ranges independently: no partial primitives may
    # join the next original call, and winding fill/cover stay separate.
    assert [tuple(range(start+i,start+i+3)) for start,count in draws for i in range(0,count-2,3)]==[
        (0,1,2),(3,4,5),(6,7,8),(9,10,11),(12,13,14),(15,16,17),(18,19,20),
        (21,22,23),(24,25,26),(30,31,32),(40,41,42)]
    assert [c for c in calls if c[0] in (1,2)]==[(1,2960),(2,2960)]


def test_native_batch_never_overflows_gl_signed_count():
    commands=np.array([[0,2147483646,0,0,0,-1,-1],
                       [2147483646,3,0,0,0,-1,-1]],np.int64)
    assert [c[2] for c in _dispatch(commands) if c[0]==0]==[2147483646,3]


def test_native_randomized_batches_preserve_primitive_order_and_winding_state():
    rng=np.random.default_rng(77491);commands=[];start=0
    for _ in range(500):
        count=int(rng.choice([0,1,2,3,4,6,9,12]))
        winding=int(rng.random()<.15);rank=int(rng.choice([-1,1,4]));shell=int(rng.choice([-1,0,1]))
        if commands and rng.random()<.6:rank,shell=commands[-1][5:7]
        if rng.random()<.2:start+=3
        commands.append([start,count,winding,start+count,6 if winding else 0,rank,shell])
        start+=count+(6 if winding else 0)
    expected=[]
    for start,count,winding,cover,cover_count,rank,shell in commands:
        for offset,size,stencil,func,color in ([(start,count,True,0x207,False),
                                              (cover,cover_count,True,0x205,True)] if winding else
                                             [(start,count,False,None,True)]):
            expected.extend((rank,shell,stencil,func,color,(offset+i,offset+i+1,offset+i+2))
                            for i in range(0,size-2,3))
    actual=[];rank=shell=None;stencil=False;func=None;color=True
    for call in _dispatch(np.asarray(commands,np.int64)):
        if call[0]==7:
            if call[1]==7:rank=call[2]
            else:shell=call[2]
        elif call[0] in (1,2):stencil=call[0]==1
        elif call[0]==3:func=call[1]
        elif call[0]==5:color=bool(call[1])
        elif call[0]==0:
            offset=(call[4] or 0)//4
            actual.extend((rank,shell,stencil,func if stencil else None,color,
                           (offset+i,offset+i+1,offset+i+2)) for i in range(0,call[2]-2,3))
    assert actual==expected


def test_native_dispatch_rejects_invalid_buffers_before_calling_gl():
    if sys.platform!='win32':pytest.skip('Windows native helper')
    from map_gpu_submit import NativeSubmitter,local_library
    if not local_library().is_file():pytest.skip('Native helper not built')
    with pytest.raises(ValueError):NativeSubmitter(local_library(),[0]*8)


def test_submission_loader_ignores_missing_exports(monkeypatch,tmp_path):
    import map_gpu_submit as module
    dll=tmp_path/'optional.dll';dll.write_bytes(b'not loaded')
    monkeypatch.setattr(module,'local_library',lambda:dll)
    monkeypatch.setattr(module.ctypes,'CDLL',lambda *args:object())
    class Context:
        def getProcAddress(self,name):return 1
    assert module.load_submitter(Context()) is None
