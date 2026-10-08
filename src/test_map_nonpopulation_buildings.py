"""Non-population buildings follow the building layer, not social selections."""
from copy import deepcopy

import pytest

from map_model import GroupFunctionCount, MapBuilding, MapSnapshot, SOCIAL_GROUPS
from map_query import MapQuery


def buildings():
    capacity = tuple(GroupFunctionCount(group, 100 if group == 'BlueCollar' else 0,
                                       50 if group == 'Student' else 0,
                                       25 if group == 'Tourist' else 0)
                     for group in SOCIAL_GROUPS)
    return (
        MapBuilding(1, 'depot', '', (0., 0., 0.), category='transport'),
        MapBuilding(2, 'landmark', '', (1., 0., 0.), category='special'),
        MapBuilding(3, 'unclassified', '', (2., 0., 0.), category='unknown'),
        MapBuilding(4, 'unclassified-capacity', '', (3., 0., 0.), category='unknown',
                    function_capacities=capacity),
        MapBuilding(5, 'house', '', (4., 0., 0.), category='residential',
                    function_capacities=capacity),
    )


@pytest.mark.parametrize('view', ['combined', 'home', 'work', 'leisure'])
@pytest.mark.parametrize('selected', [[], ['WhiteCollar'], ['unknown'], ['transport', 'special']])
def test_nonpopulation_buildings_survive_empty_or_legacy_social_selection(view, selected):
    source = MapSnapshot(buildings=buildings())
    original = deepcopy(source)
    query = MapQuery(source)
    result = query.select({'buildings': True, 'building_classes': selected, 'building_view': view})
    assert [building.id for building in result.snapshot.buildings] == [1, 2, 3, 4]
    assert source == original
    assert all(result.snapshot.buildings[index] is source.buildings[index] for index in range(4))


@pytest.mark.parametrize('selected', [None, [], list(SOCIAL_GROUPS)])
def test_building_layer_off_hides_every_building_without_mutating_source(selected):
    source = MapSnapshot(buildings=buildings())
    query = MapQuery(source)
    visible = query.select({'buildings': True, 'building_classes': selected})
    hidden = query.select({'buildings': False, 'building_classes': selected})
    assert hidden.snapshot.buildings == ()
    assert dict(hidden.building_colors) == {}
    assert query.select({'buildings': True, 'building_classes': selected}).snapshot.buildings == visible.snapshot.buildings
    assert len(source.buildings) == 5


def test_social_options_contain_only_population_groups_from_population_buildings():
    source = MapSnapshot(buildings=buildings())
    query = MapQuery(source)
    options = query.panel_options(state={'building_classes': []})
    assert [item['id'] for item in options['building_classes']] == ['BlueCollar', 'Student', 'Tourist']
    only_nonpopulation = MapQuery(MapSnapshot(buildings=source.buildings[:4]))
    assert only_nonpopulation.panel_options()['building_classes'] == []


def test_nonpopulation_category_does_not_depend_on_missing_or_zero_population():
    from dataclasses import replace
    from map_model import GroupCount
    from semantic_colors import is_non_social_building
    source = buildings()
    assert [is_non_social_building(building) for building in source] == [True, True, True, True, False]
    assert is_non_social_building(replace(source[3], combined_groups=(GroupCount('BlueCollar', 9),)))
    assert not is_non_social_building(replace(source[4], function_capacities=(), combined_groups=()))


@pytest.mark.parametrize('view', ['combined', 'home', 'work', 'leisure'])
def test_unknown_building_keeps_native_function_color_across_social_selection(view):
    # Its full native denominator is 100. Selections must not turn known
    # capacities into a zero or missing record just to keep the object visible.
    query = MapQuery(MapSnapshot(buildings=buildings()))
    full = query.select({'building_classes': None, 'building_view': view, 'building_emphasis': True})
    filtered = query.select({'building_classes': [], 'building_view': view, 'building_emphasis': True})
    assert filtered.building_colors[4] == full.building_colors[4]
    assert 3 in filtered.building_colors
    assert filtered.building_colors[3] == full.building_colors[3]


def test_social_selection_still_controls_population_buildings():
    query = MapQuery(MapSnapshot(buildings=buildings()))
    empty = query.select({'building_classes': []})
    blue = query.select({'building_classes': ['BlueCollar']})
    assert [building.id for building in empty.snapshot.buildings] == [1, 2, 3, 4]
    assert [building.id for building in blue.snapshot.buildings] == [1, 2, 3, 4, 5]


def test_zero_capacity_and_missing_capacity_remain_distinct_when_always_visible():
    zero = tuple(GroupFunctionCount(group, 0, 0, 0) for group in SOCIAL_GROUPS)
    source = MapSnapshot(buildings=(
        MapBuilding(1, '', '', (0., 0., 0.), category='unknown', function_capacities=zero),
        MapBuilding(2, '', '', (1., 0., 0.), category='unknown'),
    ))
    result = MapQuery(source).select({'building_classes': [], 'building_emphasis': True})
    assert [building.id for building in result.snapshot.buildings] == [1, 2]
    assert result.building_colors[1] != result.building_colors[2]
    assert source.buildings[0].function_capacities == zero
    assert source.buildings[1].function_capacities == ()


@pytest.mark.parametrize('view, functional_labels', [
    ('combined', {'住宅', '工作', '商业', '商业／工作混合'}),
    ('home', {'住宅'}), ('work', {'工作'}), ('leisure', {'商业'}),
])
def test_legend_uses_full_unknown_function_data_when_social_groups_are_empty(view, functional_labels):
    query = MapQuery(MapSnapshot(buildings=buildings()))
    names = {name for name, color in query.legend_items({'building_classes': [], 'building_view': view})}
    assert functional_labels <= names
    assert {'交通建筑', '特殊建筑', '未分类'} <= names
