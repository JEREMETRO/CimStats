"""Context-local native draw submission, with the Python path as fallback."""
from pathlib import Path
import ctypes
import sys
import numpy as np

_NAMES=('glDrawElements','glEnable','glDisable','glStencilFunc',
        'glStencilOpSeparate','glColorMask','glStencilOp','glUniform1i')


def local_library():
    if getattr(sys,'frozen',False):return Path(sys._MEIPASS)/'map_gpu_submit.dll'
    return Path(__file__).resolve().parents[1]/'build/native/map_gpu_submit.dll'


class NativeSubmitter:
    def __init__(self,path,pointers):
        if len(pointers)!=8 or not all(pointers):raise ValueError('Incomplete current-context GL functions')
        self._library=ctypes.CDLL(str(Path(path).resolve()))
        self._library.map_submit_abi.restype=ctypes.c_int
        if self._library.map_submit_abi()!=2:raise ValueError('Unsupported native map ABI')
        self._functions=(ctypes.c_size_t*8)(*pointers)
        self._submit=self._library.map_submit
        self._submit.argtypes=(ctypes.c_void_p,ctypes.c_size_t,
                               ctypes.POINTER(ctypes.c_size_t),ctypes.c_int,ctypes.c_int)
        self._submit.restype=ctypes.c_int

    def __call__(self,commands,rank_location,shell_location):
        if commands.dtype!=np.int64 or commands.ndim!=2 or commands.shape[1]!=7 or not commands.flags.c_contiguous:
            raise ValueError('Native command table must be contiguous int64[N,7]')
        result=self._submit(commands.ctypes.data,len(commands),self._functions,rank_location,shell_location)
        if result:raise ValueError(f'Invalid native map command table ({result})')


def load_submitter(context):
    if sys.platform!='win32' or not local_library().is_file():return None
    try:
        pointers=[int(context.getProcAddress(name.encode('ascii'))) for name in _NAMES]
        return NativeSubmitter(local_library(),pointers)
    except (OSError,ValueError,TypeError,AttributeError):
        return None
