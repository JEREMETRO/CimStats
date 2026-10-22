"""Hot compiler command copies retain all rendering metadata."""
from dataclasses import replace
import numpy as np
import pytest
from map_gpu_geometry import GpuCommand, _Builder


@pytest.mark.parametrize('mode', ['triangles', 'winding'])
@pytest.mark.parametrize('member', [None, (41, (1., 2., 3., 4.), 19., 0)])
def test_mesh_reference_preserves_non_owner_fields(mode, member):
    source = GpuCommand(12, 18, mode, 99, 6, (-1., -2., 3., 4.), .15, 17.,
                        3, 7, (10, 20), 9, ((9, (), 2, 3),), 0)
    builder = _Builder(None)
    builder.owner_tile = (30, 40)
    builder.connection_member = member
    builder.shell_pass = 1
    result = builder.reference(source)
    expected = replace(source, owner_tile=(30, 40), shell_pass=1,
                       original_order=41 if member else -1,
                       connection_members=(member,) if member else ())
    assert result == expected
    assert builder.commands == [expected]


@pytest.mark.parametrize('matching_material', [True, False])
def test_merge_preserves_metadata_bounds_member_order_and_material_rank(matching_material):
    a = (8, (0., 0., 9., 9.), 4., 0)
    b = (2, (1., 1., 8., 8.), 5., 1)
    first = GpuCommand(12, 18, 'triangles', 99, 6, (0., 0., 9., 9.), .15, 17.,
                       -1, 0, (10, 20), 8, (a,), 1)
    second = replace(first, start=30, count=12, bounds=(-1., 2., 11., 7.),
                     rank_material=1, original_order=2, connection_members=(a, b))
    builder = _Builder(None)
    builder.materials = [np.zeros(40), np.zeros(40)]
    if not matching_material:
        builder.materials[1][0] = 1
    builder.commands = [first]
    assert builder._record_triangle(second) == second
    assert builder.commands == [replace(first, count=30, bounds=(-1., 0., 11., 9.),
                                        rank_material=0 if matching_material else -1,
                                        connection_members=(a, b))]
