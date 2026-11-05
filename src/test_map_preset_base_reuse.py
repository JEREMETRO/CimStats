"""Equivalent preset building selections share the retained GPU base."""
import pytest
from map_canvas import MapCanvas, ROAD_STYLES
from map_model import GroupFunctionCount, MapBuilding, MapRoad, MapSnapshot, SOCIAL_GROUPS
from map_query import MapQuery


def buildings():
    return tuple(MapBuilding(index, 'home', '', (float(index), 0., 0.),
                            ((0., 0., 0.), (10., 0., 0.), (10., 0., 10.)),
                            category='residential',
                            function_capacities=tuple(GroupFunctionCount(key, 10 if key == group else 0, 0, 0)
                                                      for key in SOCIAL_GROUPS))
                 for index, group in ((1, 'BlueCollar'), (2, 'Student')))


@pytest.mark.parametrize('explicit_road_levels', [False, True])
def test_equivalent_full_building_selections_reuse_compiled_base(qt_application, monkeypatch, explicit_road_levels):
    path = ((0., 0., 0.), (100., 0., 0.))
    source = MapSnapshot(buildings=buildings(),
                         roads=(MapRoad(5, 'road', '', (path,), lanes_a=1, lanes_b=1),),
                         source_hash='preset-cache', asset_signature='assets')
    query = MapQuery(source)
    canvas = MapCanvas()
    canvas.resize(400, 300)
    monkeypatch.setattr(canvas, 'prepare_frame', lambda: None)
    try:
        bases = []
        for selection in (list(SOCIAL_GROUPS), None, list(SOCIAL_GROUPS)):
            result = query.select({'building_classes': selection, 'building_emphasis': False})
            assert [building.id for building in result.snapshot.buildings] == [1, 2]
            canvas.set_snapshot(result.snapshot)
            levels = set(ROAD_STYLES) if explicit_road_levels and selection is not None else None
            canvas.set_options(building_colors=result.building_colors, road_levels=levels)
            assert canvas._prepare_vectors()
            assert canvas._prepare_gpu()
            bases.append(canvas._gpu_scene.base)
        assert bases[0] is bases[1] is bases[2], 'Equivalent full selections must retain the compiled base'
    finally:
        canvas.close()


def test_explicit_social_selection_still_excludes_unknown_population():
    unknown = MapBuilding(3, 'unknown-home', '', (3., 0., 0.), category='residential')
    source = MapSnapshot(buildings=(*buildings(), unknown))
    query = MapQuery(source)
    common = {'building_emphasis': False}
    explicit = query.select(dict(common, building_classes=list(SOCIAL_GROUPS)))
    unrestricted = query.select(dict(common, building_classes=None))
    subset = query.select(dict(common, building_classes=['Student']))
    assert [b.id for b in explicit.snapshot.buildings] == [1, 2]
    assert [b.id for b in unrestricted.snapshot.buildings] == [1, 2, 3]
    assert [b.id for b in subset.snapshot.buildings] == [2]
    assert set(explicit.building_colors) == {1, 2}
    assert set(unrestricted.building_colors) == {1, 2, 3}
