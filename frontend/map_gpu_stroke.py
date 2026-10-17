"""Optional CPU stroke tessellation; unavailable/invalid inputs use Python."""
from __future__ import annotations
import ctypes
import operator
import sys
from pathlib import Path
import numpy as np
from map_gpu_submit import local_library
from map_vector import _check


class NativeStroke:
    def __init__(self,path):
        self._library=ctypes.CDLL(str(Path(path).resolve()))
        abi=self._library.map_stroke_abi
        abi.argtypes=();abi.restype=ctypes.c_int
        if abi()!=1:raise ValueError('Unsupported native stroke ABI')
        self._count=self._library.map_stroke_count
        self._count.argtypes=(ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int,
            ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t))
        self._count.restype=ctypes.c_int
        self._fill=self._library.map_stroke_fill
        self._fill.argtypes=(ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int,ctypes.c_int,
            ctypes.c_int,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t)
        self._fill.restype=ctypes.c_int

    def __call__(self,points,material,*,round_caps=True,dashed=False,cancelled=None):
        _check(cancelled)
        try:
            material=operator.index(material)
            if not 0<=material<=2147483647:return None
            # The two C calls see a private, stable, aligned input even if the
            # caller owns a writable view and another Python thread is active.
            points=np.array(points,dtype=np.float64,order='C',copy=True)
            if points.ndim!=2 or points.shape[1]!=2:return None
            flags=int(bool(round_caps)),int(bool(dashed))
            row_count,index_count=ctypes.c_size_t(),ctypes.c_size_t()
            if self._count(points.ctypes.data,len(points),material,*flags,
                           ctypes.byref(row_count),ctypes.byref(index_count)):
                return None
            rows=np.empty((row_count.value,16),dtype=np.float32)
            if row_count.value:
                indices=np.empty(index_count.value,dtype=np.uint32)
                if self._fill(points.ctypes.data,len(points),material,*flags,
                              rows.ctypes.data,len(rows),indices.ctypes.data,len(indices)):
                    return None
                result=rows,indices
            else:result=rows
        except (ValueError,TypeError,OverflowError,MemoryError,OSError):
            return None
        _check(cancelled)
        return result


def load_stroke():
    if sys.platform!='win32':return None
    try:
        path=local_library()
        return NativeStroke(path) if path.is_file() else None
    except (OSError,ValueError,TypeError,AttributeError):
        return None
