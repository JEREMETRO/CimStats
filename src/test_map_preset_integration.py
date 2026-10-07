"""Preset integration behavior: native building hit shapes and function views."""
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest, QSignalSpy
from map_canvas import MapCanvas
from map_model import MapBuilding, MapSnapshot, GroupFunctionCount, SOCIAL_GROUPS
from map_query import MapQuery
from semantic_colors import map_fill, color_for


def test_network_service_filter_uses_saved_windows_and_intersects_manual_selection():
    from dataclasses import replace
    from map_model import MapRoute, RouteService, ServiceTimetable
    hour = 36_000_000_000
    # Sunday template spills into Monday; 00:30 is its final departure.
    native = ServiceTimetable(1, 23*hour, 24*hour+hour//2, hour//2,
                              (23*hour, 23*hour+hour//2, 24*hour, 24*hour+hour//2))
    route = MapRoute(1, '夜线', 1, 'a', '甲', 'bus', (), (),
                     service=RouteService(True, True, (native,)))
    inactive = replace(route, id=2, service=RouteService(False, True, (native,)))
    unknown = replace(route, id=3, service=RouteService())
    query = MapQuery(MapSnapshot(routes=(route, inactive, unknown)))
    state = {'service_time_mode': 'instant', 'service_start': '2013-05-27T00:30:00'}
    assert [r.id for r in query.select(state).routes] == [1]
    assert not query.select({**state, 'service_start': '2013-05-27T00:30:01'}).routes
    assert not query.select({**state, 'manual_line_ids': [2]}).routes
    assert {r.id for r in query.select({'service_time_mode': 'off'}).routes} == {1, 2, 3}
    options = query.panel_options(state=state)
    matches = {row['id']: row['service_matches'] for row in options['lines']}
    assert matches == {1: True, 2: False, 3: None}
    # A malformed persisted time filter never broadens to all lines silently.
    assert not query.select({**state, 'service_start': 'broken'}).routes


def test_building_click_uses_polygon_not_bounds_and_drag_does_not_select(qt_application):
    canvas = MapCanvas()
    canvas.resize(600, 400)
    building = MapBuilding(42, 'house', '测试建筑', (0., 0., 0.),
                          ((0., 0., 0.), (100., 0., 0.), (0., 0., 100.)))
    canvas.set_snapshot(MapSnapshot(buildings=(building,), bounds=(0., 0., 100., 100.)))
    canvas.show()
    qt_application.processEvents()
    try:
        selected = QSignalSpy(canvas.buildingClicked)
        inside = canvas.world_to_screen((20., 20.)).toPoint()
        outside = canvas.world_to_screen((80., 80.)).toPoint()
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=outside)
        assert selected.count() == 0
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=inside)
        assert selected.count() == 1
        assert selected.at(0)[0] == 42
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=inside)
        QTest.mouseMove(canvas, inside + QPoint(30, 0))
        QTest.mouseMove(canvas, inside)
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=inside)
        assert selected.count() == 1
        canvas.set_options(buildings=False)
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=inside)
        assert selected.count() == 1
    finally:
        canvas.close()


def test_function_views_keep_full_denominator_and_revisit_cache_without_color_leak():
    records = tuple(GroupFunctionCount(g, 20 if g == 'BlueCollar' else 0,
                                      100 if g == 'Student' else 0,
                                      40 if g == 'Tourist' else 0) for g in SOCIAL_GROUPS)
    building = MapBuilding(1, 'house', '', (0., 0., 0.), function_capacities=records)
    query = MapQuery(MapSnapshot(buildings=(building,)))
    base = {'building_emphasis': True, 'building_classes': None}
    home = query.select({**base, 'building_view': 'home'})
    work = query.select({**base, 'building_view': 'work'})
    leisure = query.select({**base, 'building_view': 'leisure'})
    assert home.building_colors[1] == map_fill('usage', 'residential', .234)
    assert work.building_colors[1] == map_fill('usage', 'work', .85)
    assert leisure.building_colors[1] == map_fill('usage', 'commercial', .388)
    assert query.select({**base, 'building_view': 'home'}).building_colors == home.building_colors
    assert query.legend_items({**base, 'building_view': 'home'}) == (
        ('住宅', color_for('usage', 'residential')),)
    # Switching function view cannot rewrite the immutable native capacities.
    assert building.function_capacities == records
