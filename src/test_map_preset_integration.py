"""Preset integration behavior: native building hit shapes and function views."""
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest, QSignalSpy
from map_canvas import MapCanvas
from map_model import MapBuilding, MapSnapshot, GroupFunctionCount, SOCIAL_GROUPS
from map_query import MapQuery
from semantic_colors import map_fill, color_for


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
