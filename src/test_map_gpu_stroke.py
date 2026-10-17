"""Native stroke topology matches the independent Python tessellator."""
import ctypes
import os
from pathlib import Path
import numpy as np
import pytest


@pytest.fixture(scope='module')
def native_stroke():
    from map_gpu_stroke import NativeStroke
    from map_gpu_submit import local_library
    path=Path(os.environ.get('CIM2_STROKE_TEST_DLL',local_library()))
    if not path.is_file():pytest.skip('Build native stroke helper before native acceptance')
    try:return NativeStroke(path)
    except AttributeError:pytest.skip('Existing native helper has no stroke exports')


def _assert_same(native,points,**kwargs):
    from map_gpu_geometry import _python_stroke
    expected=_python_stroke(points,17,**kwargs)
    actual=native(points,17,**kwargs)
    assert actual is not None
    if isinstance(expected,np.ndarray):
        assert isinstance(actual,np.ndarray) and actual.shape==expected.shape
        assert actual.dtype==np.float32
        return
    rows,indices=actual
    original,original_indices=expected
    np.testing.assert_array_equal(indices,original_indices)
    np.testing.assert_array_equal(rows[:,:2].view(np.uint32),original[:,:2].view(np.uint32))
    np.testing.assert_array_equal(rows[:,[4,5,6,7,8,10,11]],original[:,[4,5,6,7,8,10,11]])
    np.testing.assert_allclose(rows,original,rtol=1e-6,atol=0.)
    assert rows.dtype==np.float32 and indices.dtype==np.uint32
    assert rows.flags.c_contiguous and indices.flags.c_contiguous


@pytest.mark.parametrize('round_caps,dashed',[(True,False),(False,False),(True,True),(False,True)])
@pytest.mark.parametrize('points',[
    [],[[0.,0.]],[[2.,3.],[2.,3.],[2.,3.]],
    [[0.,0.],[1.,2.]],
    [[0.,0.],[0.,0.],[7.,3.],[7.,3.],[7.,9.],[7.,9.]],
    [[0.,0.],[7.,3.],[0.,0.]],
    [[0.,0.],[0.,0.],[7.,3.],[7.,3.],[0.,0.],[0.,0.]],
    [[-0.,-0.],[1e-200,2e-200],[2e-200,-1e-200]],
])
def test_native_stroke_retains_segments_joins_caps_and_arc(native_stroke,points,round_caps,dashed):
    _assert_same(native_stroke,np.asarray(points,dtype=np.float64).reshape(-1,2),round_caps=round_caps,dashed=dashed)


def test_native_stroke_matches_500_varied_paths(native_stroke):
    rng=np.random.default_rng(20261018)
    for index in range(500):
        points=np.cumsum(rng.normal(size=(2+index%51,2))*30,axis=0)
        if index%3==0:points=np.repeat(points,2,axis=0)
        if index%4==0:points=np.concatenate((points,points[:1]))
        _assert_same(native_stroke,points,round_caps=index%2==0,dashed=index%5==0)


@pytest.mark.parametrize('points',[
    [[0.,0.],[float('nan'),1.]],[[0.,0.],[float('inf'),1.]],
    [[1e300,0.],[1e300,1.]],[[0.,0.],[1e39,1.]],
])
def test_native_stroke_nonfinite_or_float_overflow_falls_back(native_stroke,points):
    assert native_stroke(np.asarray(points),2) is None


def test_native_stroke_wrong_shape_and_material_fall_back(native_stroke):
    assert native_stroke(np.zeros((2,3)),1) is None
    assert native_stroke(np.zeros((2,2)),1<<40) is None
    assert native_stroke(np.zeros((2,2)),1.25) is None


def test_native_stroke_cancellation_is_not_swallowed(native_stroke):
    from map_vector import VectorMapCancelled
    with pytest.raises(VectorMapCancelled):
        native_stroke(np.array([[0.,0.],[1.,2.]]),2,cancelled=lambda:True)


def test_stroke_loader_ignores_missing_exports(monkeypatch,tmp_path):
    import map_gpu_stroke as module
    dll=tmp_path/'optional.dll';dll.write_bytes(b'not loaded')
    monkeypatch.setattr(module,'local_library',lambda:dll)
    monkeypatch.setattr(module.ctypes,'CDLL',lambda *args:object())
    assert module.load_stroke() is None


def test_native_fill_rejects_capacity_without_writing(native_stroke):
    points=np.array([[0.,0.],[1.,2.],[3.,1.]],dtype=np.float64)
    rows=np.full((1,16),123.,dtype=np.float32)
    indices=np.full(1,456,dtype=np.uint32)
    result=native_stroke._fill(points.ctypes.data,len(points),2,1,0,
        rows.ctypes.data,len(rows),indices.ctypes.data,len(indices))
    assert result!=0
    np.testing.assert_array_equal(rows,123.)
    np.testing.assert_array_equal(indices,456)



@pytest.mark.parametrize('row_short,index_short',[(True,False),(False,True)])
def test_native_fill_validates_each_capacity_before_writing(native_stroke,row_short,index_short):
    points=np.array([[0.,0.],[1.,2.],[3.,1.]],dtype=np.float64)
    row_count,index_count=ctypes.c_size_t(),ctypes.c_size_t()
    assert native_stroke._count(points.ctypes.data,len(points),2,1,0,
        ctypes.byref(row_count),ctypes.byref(index_count))==0
    rows=np.full((row_count.value,16),123.,dtype=np.float32)
    indices=np.full(index_count.value,456,dtype=np.uint32)
    result=native_stroke._fill(points.ctypes.data,len(points),2,1,0,
        rows.ctypes.data,len(rows)-int(row_short),indices.ctypes.data,len(indices)-int(index_short))
    assert result!=0
    np.testing.assert_array_equal(rows,123.)
    np.testing.assert_array_equal(indices,456)


def test_native_fill_rejects_late_nonfinite_point_without_partial_output(native_stroke):
    points=np.array([[0.,0.],[1.,2.],[float('nan'),1.]],dtype=np.float64)
    rows=np.full((100,16),123.,dtype=np.float32)
    indices=np.full(200,456,dtype=np.uint32)
    assert native_stroke._fill(points.ctypes.data,len(points),2,1,0,
        rows.ctypes.data,len(rows),indices.ctypes.data,len(indices))!=0
    np.testing.assert_array_equal(rows,123.)
    np.testing.assert_array_equal(indices,456)


def test_native_count_rejects_integer_and_flag_ranges_before_reading(native_stroke):
    points=np.zeros((2,2),dtype=np.float64)
    for count,material,round_caps,dashed in ((ctypes.c_size_t(-1).value,0,1,0),(2,-1,1,0),(2,0,2,0),(2,0,1,2)):
        rows,indices=ctypes.c_size_t(123),ctypes.c_size_t(456)
        assert native_stroke._count(points.ctypes.data,count,material,round_caps,dashed,
            ctypes.byref(rows),ctypes.byref(indices))!=0
        assert rows.value==123 and indices.value==456


def test_native_stroke_handles_strided_reversed_input_and_smallest_segments(native_stroke):
    points=np.array([[0.,-0.],[2.,3.],[2.,3.],[0.,-0.],[2.,3.]],dtype=np.float64)
    _assert_same(native_stroke,points[::-1],dashed=True)
    tiny=np.nextafter(0.,1.)
    _assert_same(native_stroke,np.array([[0.,0.],[tiny,tiny],[0.,0.]]))


@pytest.mark.parametrize('material',[0,np.int64(1234567),2147483647])
def test_native_stroke_material_cast_matches_python(native_stroke,material):
    from map_gpu_geometry import _python_stroke
    points=np.array([[0.,0.],[2.,3.]],dtype=np.float64)
    expected=_python_stroke(points,material)
    actual=native_stroke(points,material)
    assert actual is not None
    np.testing.assert_array_equal(actual[0],expected[0])
    np.testing.assert_array_equal(actual[1],expected[1])


def test_stroke_loader_rejects_independent_unknown_abi(monkeypatch,tmp_path):
    import map_gpu_stroke as module
    dll=tmp_path/'optional.dll';dll.write_bytes(b'not loaded')
    class Unsupported:
        @staticmethod
        def map_stroke_abi():return 2
    monkeypatch.setattr(module,'local_library',lambda:dll)
    monkeypatch.setattr(module.ctypes,'CDLL',lambda *args:Unsupported())
    assert module.load_stroke() is None
