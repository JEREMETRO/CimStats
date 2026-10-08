"""One visible name policy over the complete save, independent of filters."""
from types import MappingProxyType


def test_unique_names_use_mode_and_name_without_company_or_object_id():
    from map_line_labels import resolve_line_labels
    from map_model import MapRoute
    routes = (MapRoute(10, '1', 1, 'a', "jeremylin2005's Company", 'bus', (), ()),
              MapRoute(11, '1', 1, 'b', '另一个公司', 'tram', (), ()))
    assert resolve_line_labels(routes) == {10: '公交1路', 11: '有轨电车1路'}
    assert routes[0].name == '1' and routes[0].company_id == 'a'


def test_cross_company_duplicate_names_get_shared_company_display_names():
    from map_line_labels import resolve_line_labels
    routes = ({'id': 1, 'name': '1路', 'mode': 'bus', 'company_id': 'a',
               'company_name': "jeremylin2005's Company"},
              {'id': 2, 'name': '1路', 'mode': '公交', 'company_id': 'b', 'company_name': '东城交通'},
              {'id': 3, 'name': '2路', 'mode': '公交', 'company_id': 'b', 'company_name': '东城交通'})
    labels = resolve_line_labels(routes)
    assert labels == {1: '八连交通集团公交1路', 2: '东城交通公交1路', 3: '公交2路'}
    from map_model import MapRoute, MapSnapshot
    from map_query import MapQuery
    query = MapQuery(MapSnapshot(routes=tuple(
        MapRoute(row['id'], row['name'], 1, row['company_id'], row['company_name'], row['mode'], (), ())
        for row in routes)))
    filtered = query.panel_options(state={'manual_line_ids': {1}})
    assert {row['id']: row['display_label'] for row in filtered['lines']} == labels
    assert [route.id for route in query.select({'manual_line_ids': {1}}).routes] == [1]


def test_same_owner_and_prefixed_mode_do_not_create_duplicate_prefixes():
    from map_line_labels import resolve_line_labels
    routes = (MappingProxyType({'id': 1, 'name': '地铁101号线', 'mode': 'metro',
                                'company_id': 'same', 'company_name': '公司'}),
              {'id': 2, 'name': '地铁101号线', 'mode': '地铁', 'company_id': 'same',
               'company_name': '公司'})
    assert resolve_line_labels(routes) == {1: '地铁101号线', 2: '地铁101号线'}


def test_native_custom_name_starting_with_mode_still_uses_original_number_formatter():
    from map_line_labels import resolve_line_labels
    from map_model import MapRoute
    route = MapRoute(8, '公交', 8, 'a', '公司', 'bus', (), ())
    assert resolve_line_labels((route,))[8] == '公交8路公交'
