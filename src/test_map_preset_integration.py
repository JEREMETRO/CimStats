"""Preset integration behavior: native building hit shapes and function views."""
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest, QSignalSpy
from map_canvas import MapCanvas
from map_model import MapBuilding, MapSnapshot, GroupFunctionCount, SOCIAL_GROUPS
from map_query import MapQuery
from semantic_colors import map_fill, color_for
import pytest


def test_network_summary_tracks_effective_query_without_erasing_selection(qt_application, tmp_path):
    from PySide6.QtCore import QSettings
    from map_page import MapPage
    from map_model import MapRoute, RouteService, ServiceTimetable
    hour = 36_000_000_000
    path = (((0., 0., 0.), (100., 0., 0.)),)
    service = RouteService(True, True, (ServiceTimetable(127, 8*hour, 10*hour, hour,
                                                       (8*hour, 9*hour, 10*hour)),))
    routes = (MapRoute(1, '日线', 1, 'a', '甲', 'bus', (), path, service=service),
              MapRoute(2, '晚线', 2, 'b', '乙', 'bus', (), path))
    page = MapPage(QSettings(str(tmp_path/'counts.ini'), QSettings.Format.IniFormat))
    page.set_session({'save_key': 'A', 'simulation_time': '2013-05-23T09:00:00'})
    page.set_snapshot(MapSnapshot(routes=routes))
    page.resize(1440, 960); page.show(); qt_application.processEvents()
    panel = page.panel_set

    def assert_count(count):
        assert panel.selection_summary.text() == f'已选 {count} / 共 2'
        assert f'已选 {count} 条' in page.status.text()
        assert len(page.result.routes) == count

    try:
        assert_count(2)
        panel.filter_sections['service'].set_expanded(True)
        QTest.mouseClick(panel.controls['service_time_mode'].buttons['instant'], Qt.MouseButton.LeftButton)
        assert_count(2)
        QTest.mouseClick(panel.filter_apply_buttons['service'],Qt.MouseButton.LeftButton)
        assert_count(1)
        assert panel.state()['manual_line_ids'] == {1, 2}
        page.set_preset('planning'); page.set_preset('network')
        assert_count(1)
        panel.filter_sections['service'].set_expanded(True)
        QTest.mouseClick(panel.controls['service_time_mode'].buttons['off'], Qt.MouseButton.LeftButton)
        QTest.mouseClick(panel.filter_apply_buttons['service'],Qt.MouseButton.LeftButton)
        panel.filter_sections['company_ids'].set_expanded(True)
        companies = panel.group_lists['company_ids']
        companies.setCurrentItem(next(companies.item(i) for i in range(companies.count())
                                      if companies.item(i).data(Qt.ItemDataRole.UserRole) == 'a'))
        QTest.keyClick(companies, Qt.Key.Key_Space)
        QTest.mouseClick(panel.filter_apply_buttons['company_ids'],Qt.MouseButton.LeftButton)
        assert_count(1)
        assert panel.state()['manual_line_ids'] == {1, 2}
        panel.filter_sections['manual_line_ids'].set_expanded(True)
        QTest.mouseClick(panel.manual_none, Qt.MouseButton.LeftButton)
        QTest.mouseClick(panel.filter_apply_buttons['manual_line_ids'],Qt.MouseButton.LeftButton)
        assert_count(0)
        assert panel.state()['manual_line_ids'] == {1}  # Bulk action only affects current candidates.
        QTest.mouseClick(panel.reset_filters, Qt.MouseButton.LeftButton)
        panel.filter_sections['manual_line_ids'].set_expanded(True)
        QTest.mouseClick(panel.manual_none, Qt.MouseButton.LeftButton)
        QTest.mouseClick(panel.filter_apply_buttons['manual_line_ids'],Qt.MouseButton.LeftButton)
        assert_count(0)
        page.set_preset('single'); page.set_preset('network')
        assert_count(0)
        assert panel.state()['manual_line_ids'] == set()
        page.set_session({'save_key': 'B'})
        assert panel.selection_summary.text().startswith('已选 0 /')
    finally:
        page.close()


def test_preset_revisit_reuses_immutable_layer_indexes(qt_application, tmp_path):
    from PySide6.QtCore import QSettings
    from map_page import MapPage
    from map_model import MapRoute
    route = MapRoute(1, 'A', 1, 'a', '甲', 'bus', (), (((0., 0., 0.), (100., 0., 0.)),))
    building = MapBuilding(2, 'house', '', (10., 0., 10.), ((0., 0., 0.), (20., 0., 0.), (0., 0., 20.)))
    page = MapPage(QSettings(str(tmp_path/'index.ini'), QSettings.Format.IniFormat))
    page.set_session({'save_key': 'A'})
    page.set_snapshot(MapSnapshot(routes=(route,), buildings=(building,), source_hash='A'))
    try:
        page.show_route(1, page.save_token)
        indexes = {}
        for preset in ('single', 'network', 'planning'):
            page.set_preset(preset)
            indexes[preset] = dict(page.canvas._indexes)
        for preset in ('single', 'network', 'planning'):
            page.set_preset(preset)
            assert all(page.canvas._indexes[key] is index for key, index in indexes[preset].items())
    finally:
        page.close()


def test_route_bounds_follow_changed_stop_positions_without_reusing_stale_index(qt_application):
    from map_model import MapRoute, MapStop
    route = MapRoute(1, 'A', 1, 'a', '甲', 'bus', (3,), ())
    routes = (route,)
    canvas = MapCanvas()
    try:
        first = MapSnapshot(routes=routes, stops=(MapStop(3, 'S', (1., 0., 1.)),))
        second = MapSnapshot(routes=routes, stops=(MapStop(3, 'S', (50., 0., 50.)),))
        canvas.set_snapshot(first)
        old = canvas._indexes['routes']
        canvas.set_snapshot(second)
        assert canvas._boxes['routes'][1] == (50., 50., 50., 50.)
        assert canvas._indexes['routes'] is not old
    finally:
        canvas.close()


def test_inflight_frame_keeps_original_indexes_after_eviction_and_clear(qt_application):
    from dataclasses import replace
    from map_canvas import _FrameSurface
    building = MapBuilding(2, 'house', '', (10., 0., 10.))
    initial = MapSnapshot(buildings=(building,), source_hash='A', bounds=(0., 0., 100., 100.))
    canvas = MapCanvas()
    try:
        canvas.set_snapshot(initial)
        frame = _FrameSurface(canvas)
        old_index, old_boxes = frame._indexes['buildings'], dict(frame._boxes['buildings'])
        for i in range(1, 6):
            current = replace(initial, buildings=(replace(building, position=(20.*i, 0., 20.*i)),))
            canvas.set_snapshot(current)
        assert len(canvas._index_cache['buildings']) <= 4
        last_index = canvas._indexes['buildings']
        canvas.set_snapshot(replace(current, bounds=(0., 0., 1000., 1000.)))
        assert canvas._indexes['buildings'] is not last_index
        canvas.set_snapshot(MapSnapshot())
        assert all(not items and not dependencies
                   for layer in canvas._index_cache.values()
                   for items, dependencies, _, _ in layer.values())
        assert frame._indexes['buildings'] is old_index
        assert frame._boxes['buildings'] == old_boxes
        assert list(old_index.query((0., 0., 15., 15.))) == [building]
    finally:
        canvas.close()


@pytest.mark.parametrize('paths', [(), (((0., 0., 0.), (0., 10., 0.)),)])
def test_visible_search_and_detail_reject_unusable_geometry(qt_application, tmp_path, paths):
    from PySide6.QtCore import QSettings
    from map_page import MapPage
    from map_model import MapRoute
    route = MapRoute(9, 'No geometry', 9, 'a', '甲', 'bus', (), paths)
    page = MapPage(QSettings(str(tmp_path/'unusable.ini'), QSettings.Format.IniFormat))
    page.set_session({'save_key': 'A'})
    page.set_snapshot(MapSnapshot(routes=(route,)))
    try:
        page.surface.search.setText('No geometry')
        page.surface._search()
        item = page.surface.results.item(0)
        assert item.data(Qt.ItemDataRole.UserRole).id == 9
        assert not item.flags() & Qt.ItemFlag.ItemIsEnabled
        assert not page._focus_search(item.data(Qt.ItemDataRole.UserRole))
        assert not page.show_route(9, page.save_token)
        assert page.preset == 'network'
        page.set_session({'save_key': 'B'})
        assert page.show_route(9, page.save_token)
        page.set_snapshot(MapSnapshot(routes=(route,)))
        assert page.presets.state('single')['query']['route_id'] is None
        assert not page.result.routes
    finally:
        page.close()


def test_surface_search_from_filtered_network_opens_single_without_changing_network(qt_application, tmp_path):
    from PySide6.QtCore import QSettings
    from map_page import MapPage
    from map_model import MapRoute
    route = MapRoute(7, 'Central', 7, 'a', '甲', 'bus', (),
                     (((0., 0., 0.), (100., 0., 0.)),))
    page = MapPage(QSettings(str(tmp_path/'search.ini'), QSettings.Format.IniFormat))
    page.set_session({'save_key': 'A'})
    page.set_snapshot(MapSnapshot(routes=(route,)))
    page.apply_state({**page.panel_set.state(), 'manual_line_ids': []})
    try:
        matches = page.search('Central')
        assert [match.id for match in matches] == [7]
        page._focus_search(matches[0])
        assert page.preset == 'single'
        assert [r.id for r in page.result.routes] == [7]
        assert page.presets.state('network')['query']['manual_line_ids'] == set()
    finally:
        page.close()


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


def test_line_navigation_never_paints_its_rectangular_bounds(qt_application):
    from PySide6.QtGui import QImage, QPainter
    from map_model import MapRoute
    canvas = MapCanvas()
    canvas.resize(500, 400)
    route = MapRoute(7, 'Diagonal', 7, 'a', '甲', 'bus', (),
                     (((0., 0., 0.), (100., 0., 100.)),))
    canvas.set_snapshot(MapSnapshot(routes=(route,), bounds=(0., 0., 100., 100.)))
    canvas.focus_result(canvas.search('Diagonal')[0])
    def rendered():
        image = QImage(canvas.size(), QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        canvas._paint(painter)
        painter.end()
        return image
    try:
        focused = rendered()
        canvas._highlight = None
        assert focused == rendered()
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
