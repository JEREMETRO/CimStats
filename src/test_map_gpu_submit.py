"""Native command dispatch retains the exact ordered GL state protocol."""
import ctypes
import sys
from pathlib import Path
import numpy as np
import pytest


def test_native_dispatch_matches_independent_winding_and_rank_sequence():
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
    # start/count, winding, cover start/count, rank, shell (index offsets).
    commands=np.array([[3,6,0,0,0,-1,-1],[9,12,1,21,6,1,1],[27,9,1,36,6,1,1],
                       [42,6,0,0,0,4,0]],dtype=np.int64)
    submit(commands,7,8)
    assert [c for c in calls if c[0]==7 and c[1]==7]==[(7,7,-1),(7,7,1),(7,7,4)]
    assert [c for c in calls if c[0]==7 and c[1]==8]==[(7,8,-1),(7,8,1),(7,8,0)]
    assert [c for c in calls if c[0]==0]==[(0,4,6,5125,12),(0,4,12,5125,36),
        (0,4,6,5125,84),(0,4,9,5125,108),(0,4,6,5125,144),(0,4,6,5125,168)]
    assert [c for c in calls if c[0] in (1,2)]==[(1,2960),(2,2960)]
    assert [c for c in calls if c[0]==5]==[(5,0,0,0,0),(5,1,1,1,1)]*2


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
