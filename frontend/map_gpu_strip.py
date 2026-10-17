"""Optional conservative proof of a shared core/shell lane triangle strip."""
from __future__ import annotations
import ctypes
import sys
from pathlib import Path
import numpy as np
from map_gpu_submit import local_library
from map_vector import _check


class NativeStrip:
    def __init__(self,path):
        self._library=ctypes.CDLL(str(Path(path).resolve()))
        abi=self._library.map_strip_abi
        abi.argtypes=();abi.restype=ctypes.c_int
        if abi()!=1:raise ValueError('Unsupported native strip ABI')
        self._pair=self._library.map_strip_pair
        self._pair.argtypes=(ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,
                             ctypes.c_void_p,ctypes.c_size_t)
        self._pair.restype=ctypes.c_int

    def __call__(self,rows,material,cancelled=None):
        _check(cancelled)
        try:
            # Stable private inputs while ctypes releases the GIL. Scratch is
            # owned here, never retained or allocated by the native helper.
            rows=np.array(rows,dtype=np.float32,order='C',copy=True)
            material=np.array(material,dtype=np.float32,order='C',copy=True)
            if (rows.ndim!=2 or rows.shape[1]!=16 or len(rows)<4 or
                    len(rows)>64 or len(rows)%2 or material.shape!=(40,)):
                return False
            scratch=np.empty((len(rows),32),dtype=np.float64)
            result=self._pair(rows.ctypes.data,len(rows),material.ctypes.data,
                              scratch.ctypes.data,scratch.nbytes)==1
        except (ValueError,TypeError,OverflowError,MemoryError,OSError):
            return False
        _check(cancelled)
        return result


def load_strip():
    if sys.platform!='win32':return None
    try:
        path=local_library()
        return NativeStrip(path) if path.is_file() else None
    except (OSError,ValueError,TypeError,AttributeError):
        return None
