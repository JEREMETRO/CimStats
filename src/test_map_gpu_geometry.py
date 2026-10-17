"""Retained GPU geometry preserves the saved map at arbitrary view scales."""
from dataclasses import replace
import importlib.util
import threading

import numpy as np
import pytest

from map_canvas import MapCanvas, _FrameSurface, road_style
from map_model import (MapBuilding, MapJunction, MapJunctionConnection, MapLane,
                       MapRoad, MapRoute, MapSnapshot, RouteDirection)
from map_vector import VectorMapCancelled, build_vector_map, _lane_polygons


@pytest.fixture(autouse=True)
def _optional_strip_unavailable(monkeypatch):
    import map_gpu_geometry
    monkeypatch.setattr(map_gpu_geometry, '_load_strip', lambda: None, raising=False)


def _compiler():
    assert importlib.util.find_spec('map_gpu_geometry') is not None, 'Retained GPU compiler is missing'
    from map_gpu_geometry import compile_gpu_scene
    return compile_gpu_scene


def _expanded(scene):
    indices = getattr(scene, 'indices', None)
    return scene.vertices if indices is None else scene.vertices[indices]


def _command_rows(scene, command):
    return _expanded(scene)[command.start:command.start+command.count]


def _surface(snapshot, **options):
    canvas = MapCanvas()
    canvas.resize(400, 300)
    canvas.set_snapshot(snapshot)
    canvas.set_options(stops=False, stop_names=False, line_numbers=False, **options)
    surface = _FrameSurface(canvas)
    canvas.close()
    return surface


def _connection_surface():
    source = MapRoad(1, 'road', 'a', (((0., 0., 0.), (20., 0., 0.)),),
                     lanes_a=2, lanes_b=0, road_class='ordinary', width=14.,
                     lanes=(MapLane(0, 0x1000101, 1, -1.5), MapLane(1, 0x1000101, 1, 1.5)))
    target = replace(source, id=2, road_class='avenue', width=20.)
    curve = ((20., 0., 0.), (26., 0., 7.), (34., 0., 0.))
    connection = MapJunctionConnection(4, 1, 2, 0, 1, 0x1000000, (curve,))
    junction = MapJunction(3, (27., 0., 3.), (1, 2), (connection,))
    return _surface(MapSnapshot(roads=(source, target), junctions=(junction,),
                               bounds=(0., 0., 40., 20.)), buildings=False, routes=False)


def test_compiler_retains_world_geometry_and_is_independent_of_center_and_zoom(qt_application):
    road = MapRoad(1, 'r', '', (((1., 0., 2.), (4., 0., 6.), (10., 0., 6.)),),
                   road_class='ordinary', width=12.)
    surface = _surface(MapSnapshot(roads=(road,), bounds=(0., 0., 20., 20.)),
                       buildings=False, routes=False)
    prepared = build_vector_map(surface)
    scene = _compiler()(surface, prepared)
    assert scene.vertices.shape[1] == 16
    assert scene.materials.shape[1] == 40
    for values in (scene.vertices, scene.materials):
        assert values.dtype == np.float32 and values.flags.c_contiguous
        assert not values.flags.writeable
    core = scene.vertices[scene.materials[scene.vertices[:, 8].astype(int), 28] == 0]
    assert set(map(tuple, core[:, :2])) == {(1., -2.), (4., -6.), (10., -6.)}
    assert set(core[:, 9]) == {0., 5., 11.}
    surface.center = (1200., -700.)
    surface.zoom = 13.379
    other = _compiler()(surface, prepared)
    assert np.array_equal(scene.vertices, other.vertices)
    assert np.array_equal(scene.materials, other.materials)
    if scene.indices is not None:
        assert np.array_equal(scene.indices, other.indices)
    assert scene.commands == other.commands


def test_lane_fan_matches_native_margins_at_arbitrary_zoom_and_gradient_projection(qt_application):
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    scene = _compiler()(surface, prepared)
    connection = prepared.connections[0]
    winding = [command for command in scene.commands if command.mode == 'winding'
               and command.connection_rank in (-1, 1)]
    assert len(winding) == 2, 'Both lane fill and shell require a nonzero winding stencil'
    for command in winding:
        rows = _command_rows(scene, command)
        material = scene.materials[int(rows[0, 8])]
        shell = command.shell_pass == 1
        assert command.min_zoom == .15
        assert command.cover_count == 6
        np.testing.assert_allclose(material[24:28], (20., 0., 14., 0.))
        for zoom in (.15, .21371, .45, 1., 16., 100.):
            surface.zoom = zoom
            source, target = [road_style(road, zoom) for road in (connection.source, connection.target)]
            start = surface._lane_margins(connection.source, connection.source_lane, source)
            end = surface._lane_margins(connection.target, connection.target_lane, target)
            polygon = _lane_polygons(connection.templates[0], zoom, start, end, .45)[int(shell)]
            offset = rows[:, 4]*source.width+rows[:, 5]*target.width+rows[:, 6]*zoom+rows[:, 7]*.45*int(shell)
            positions = rows[:, :2]*zoom+rows[:, 2:4]*offset[:, None]
            expected = np.array([(point.x(), point.y()) for point in polygon])
            for point in expected:
                assert np.linalg.norm(positions-point, axis=1).min() < .002


def test_concave_building_triangles_do_not_fill_the_notch(qt_application):
    polygon = ((0., 0., 0.), (6., 0., 0.), (6., 0., 2.),
               (2., 0., 2.), (2., 0., 6.), (0., 0., 6.))
    building = MapBuilding(3, 'b', '', (0., 0., 0.), polygon)
    surface = _surface(MapSnapshot(buildings=(building,), bounds=(0., 0., 10., 10.)),
                       roads=False, routes=False)
    scene = _compiler()(surface, build_vector_map(surface))
    expanded = _expanded(scene)
    core = expanded[scene.materials[expanded[:, 8].astype(int), 28] == 6]
    assert len(core) == 12
    triangles = core[:, :2].reshape(-1, 3, 2)
    cross = lambda a, b: a[0]*b[1]-a[1]*b[0]
    assert sum(abs(cross(b-a, c-a))/2 for a, b, c in triangles) == 20.
    for a, b, c in triangles:
        point = np.array((4., -4.))
        signs = [cross(b-a, point-a), cross(c-b, point-b), cross(a-c, point-c)]
        assert not (all(value >= 0 for value in signs) or all(value <= 0 for value in signs))


def test_dashed_route_phase_uses_saved_world_arc_and_flat_endpoints(qt_application):
    path = ((0., 0., 0.), (3., 0., 4.), (9., 0., 4.))
    route = MapRoute(1, '', 1, 'a', 'a', 'bus', (), (path,),
                     direction=RouteDirection('roundtrip', 1), leg_paths=((path,), (path,)))
    surface = _surface(MapSnapshot(routes=(route,), bounds=(0., 0., 20., 20.)),
                       roads=False, buildings=False)
    surface._route_path_groups = lambda route: (((path,), True),)
    scene = _compiler()(surface, build_vector_map(surface))
    material = scene.materials[scene.materials[:, 28] == 4][0]
    assert tuple(material[38:40]) == (8., 5.)
    assert set(scene.vertices[:, 9]) == {0., 5., 11.}
    assert 2 not in scene.vertices[:, 10], 'Dashed paths must have flat endpoint caps'
    assert 3 in scene.vertices[:, 10], 'Round joins need retained incoming/outgoing tangents'
    joins = scene.vertices[scene.vertices[:, 10] == 3]
    np.testing.assert_allclose(joins[:, 12:16], np.tile((.6, -.8, 1., 0.), (len(joins), 1)), atol=1e-6)


def test_compiler_checks_callable_and_event_cancellation(qt_application):
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    compile_scene = _compiler()
    with pytest.raises(VectorMapCancelled):
        compile_scene(surface, prepared, lambda: True)
    event = threading.Event()
    event.set()
    with pytest.raises(VectorMapCancelled):
        compile_scene(surface, prepared, event)


def test_shell_stencil_does_not_merge_different_target_style_choices(qt_application):
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    first = prepared.connections[0]
    second = replace(first, target=replace(first.target, road_class='pedestrian'))
    prepared = replace(prepared, connections=(first, second))
    scene = _compiler()(surface, prepared)
    shell_covers = [command for command in scene.commands if command.mode == 'winding'
                    and command.connection_rank in (-1, 1)
                    and command.shell_pass == 1
                    and scene.materials[int(_expanded(scene)[command.cover_start, 8]), 28] == 2]
    assert len(shell_covers) == 2, 'Width-dependent source/target shell choices need separate covers'


def test_backward_lane_and_sidewalk_outer_edge_keep_native_coefficients(qt_application):
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    connection = prepared.connections[0]
    lanes = (MapLane(0, 0x1000201, 1, -2.), MapLane(1, 0x1000201, 1, 2.),
             MapLane(2, 0x10000, 0, -7.), MapLane(3, 0x10000, 0, 7.))
    road = replace(connection.source, lanes=lanes, sidewalk_left=4., sidewalk_right=6., width=24.)
    prepared = replace(prepared, connections=(replace(connection, source=road, target=road,
                                                      source_lane=0, target_lane=1),))
    scene = _compiler()(surface, prepared)
    command = next(command for command in scene.commands if command.mode == 'winding')
    rows = _command_rows(scene, command)
    # Reverse source lane outer edge: +2/24 * width -2*z; target reverse
    # outer edge: -10/24 * width +2*z. Both need sign and edge reversal.
    for zoom in (.16, .4137, 16.):
        surface.zoom = zoom
        style = road_style(road, zoom)
        start = surface._lane_margins(road, 0, style)
        end = surface._lane_margins(road, 1, style)
        expected = _lane_polygons(connection.templates[0], zoom, start, end, .45)[1]
        offset = (rows[:, 4]+rows[:, 5])*style.width+rows[:, 6]*zoom+rows[:, 7]*.45
        points = rows[:, :2]*zoom+rows[:, 2:4]*offset[:, None]
        for point in expected:
            assert np.linalg.norm(points-(point.x(), point.y()), axis=1).min() < .002


def test_self_crossing_building_uses_nonzero_winding_and_outline(qt_application):
    polygon = ((0., 0., 0.), (6., 0., 6.), (0., 0., 6.), (6., 0., 0.))
    building = MapBuilding(3, 'b', '', (0., 0., 0.), polygon)
    surface = _surface(MapSnapshot(buildings=(building,), bounds=(0., 0., 10., 10.)),
                       roads=False, routes=False)
    scene = _compiler()(surface, build_vector_map(surface))
    winding = [command for command in scene.commands if command.mode == 'winding']
    assert len(winding) == 1 and winding[0].cover_count == 6
    assert np.any(scene.materials[:, 28] == 7)


def test_closed_route_has_closure_join_without_endpoint_caps(qt_application):
    path = ((0., 0., 0.), (5., 0., 0.), (5., 0., 5.), (0., 0., 0.))
    route = MapRoute(1, '', 1, 'a', 'a', 'bus', (), (path,))
    surface = _surface(MapSnapshot(routes=(route,), bounds=(0., 0., 20., 20.)),
                       roads=False, buildings=False)
    scene = _compiler()(surface, build_vector_map(surface))
    assert 2 not in scene.vertices[:, 10]
    expanded = _expanded(scene)
    joins = expanded[expanded[:, 10] == 3]
    assert len(joins) == 18
    assert (0., 0.) in set(map(tuple, joins[:, :2]))


def test_road_bridge_tunnel_masks_keep_layer_passes_and_dash_period(qt_application):
    paths = tuple(((0., 0., z), (20., 0., z)) for z in (0., 10., 20.))
    road = MapRoad(1, 'r', '', paths, lanes_a=1, lanes_b=1, road_class='ordinary',
                   bridge_masks=(0, 0, 1), tunnel_masks=(1, 0, 0))
    surface = _surface(MapSnapshot(roads=(road,), bounds=(0., 0., 20., 20.)),
                       buildings=False, routes=False)
    scene = _compiler()(surface, build_vector_map(surface))
    seen = []
    for command in scene.commands:
        for row in _command_rows(scene, command)[::3]:
            material = scene.materials[int(row[8])]
            key = (int(material[37]), int(material[28])+command.shell_pass)
            if not seen or seen[-1] != key:
                seen.append(key)
    assert seen == [(0, 1), (0, 0), (1, 1), (1, 0), (2, 1), (2, 0)]
    tunnel_shell = scene.materials[(scene.materials[:, 28] == 0) & (scene.materials[:, 36] == 1)]
    np.testing.assert_array_equal(tunnel_shell[:, 38:40], [[6., 4.]])


def test_connections_reference_shared_vertices_in_each_possible_width_dependent_rank(qt_application):
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    connection = prepared.connections[0]
    source = replace(connection.source, width=100.)
    target = replace(connection.target, track=True)
    prepared = replace(prepared, connections=(replace(connection, source=source, target=target),))
    scene = _compiler()(surface, prepared)
    commands = [command for command in scene.commands if command.mode == 'winding']
    assert len(commands) == 4
    assert len({command.start for command in commands}) == 1
    for shell_pass in (1, 0):
        references = [command for command in commands if command.shell_pass == shell_pass]
        assert [command.connection_rank for command in references] == [1, 6]
        assert len({command.cover_start for command in references}) == 1
        assert all(command.rank_material >= 0 for command in references)
    assert road_style(source, .1).width < road_style(target, .1).width
    assert road_style(source, 1.).width > road_style(target, 1.).width


def test_cancellation_interrupts_one_long_route_before_finishing_its_vertices(qt_application):
    path = tuple((float(i), 0., float(i % 7)) for i in range(10000))
    route = MapRoute(1, '', 1, 'a', 'a', 'bus', (), (path,))
    surface = _surface(MapSnapshot(routes=(route,), bounds=(0., 0., 10000., 10.)),
                       roads=False, buildings=False)
    prepared = build_vector_map(surface)
    checks = 0

    def cancelled():
        nonlocal checks
        checks += 1
        return checks == 30

    with pytest.raises(VectorMapCancelled):
        _compiler()(surface, prepared, cancelled)


def test_connection_metadata_preserves_rank_and_view_dependent_tile_first_order(qt_application):
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    original = prepared.connections[0]
    first = replace(original, source=replace(original.source, width=100.),
                    target=replace(original.target, track=True), owner_tile=(0, 0))
    second = replace(original, owner_tile=(1, 0))
    third = replace(original, owner_tile=(0, 0))
    prepared = replace(prepared, connections=(first, second, third))
    scene = _compiler()(surface, prepared)
    commands = [command for command in scene.commands if command.connection_rank == 1]
    assert all(command.rank_material >= 0 or len(command.connection_members) > 1 for command in commands)
    members = {order: (command.owner_tile, bounds) for command in commands
               for order, bounds, span, material in command.connection_members if span == original.span}
    assert {order: tile for order, (tile, _) in members.items()} == {0: (0, 0), 1: (1, 0), 2: (0, 0)}
    assert all(bounds[1] == -original.bounds[3] and bounds[3] == -original.bounds[1]
               for _, bounds in members.values())


def test_ordinary_geometry_clears_connection_metadata_at_phase_boundaries(qt_application):
    from map_gpu_geometry import _Builder, _roads, _routes
    surface = _connection_surface()
    route = MapRoute(1, '', 1, 'a', 'a', 'bus', (),
                     (((0., 0., 0.), (10., 0., 10.)),))
    prepared = replace(build_vector_map(surface), routes=(route,), connections=())
    surface.options['routes'] = True
    for phase in (lambda builder: _roads(builder, prepared),
                  lambda builder: _routes(builder, surface, prepared)):
        builder = _Builder(None)
        builder.owner_tile = (9, 9)
        builder.connection_member = (7, (0., 0., 10., 10.), 20.)
        phase(builder)
        assert builder.commands
        assert all(command.owner_tile is None and command.connection_members == ()
                   and command.original_order == -1 for command in builder.commands)
        assert builder.owner_tile is None and builder.connection_member is None


def test_complete_scene_ordinary_commands_have_no_connection_metadata(qt_application):
    surface = _connection_surface()
    route = MapRoute(1, '', 1, 'a', 'a', 'bus', (),
                     (((0., 0., 0.), (10., 0., 10.)),))
    prepared = replace(build_vector_map(surface), routes=(route,))
    surface.options['routes'] = True
    scene = _compiler()(surface, prepared)
    ordinary = [command for command in scene.commands if command.connection_rank < 0]
    assert ordinary
    assert all(command.owner_tile is None and command.connection_members == ()
               and command.original_order == -1 for command in ordinary)


def test_indexed_scene_retains_each_unique_row_once_with_exact_primitive_order():
    from map_gpu_geometry import _Builder
    builder = _Builder(None)
    rows = np.zeros((6, 16), dtype=np.float32)
    rows[:, :2] = [(0., 0.), (2., 0.), (2., 2.), (0., 0.), (2., 2.), (0., 2.)]
    builder.triangles(rows, (0., 0., 2., 2.))
    scene = builder.finish()
    assert getattr(scene, 'indices', None) is not None, 'GPU scene still duplicates triangle vertices'
    assert len(scene.vertices) == 4 and len(scene.indices) == 6
    assert scene.indices.dtype == np.uint32 and not scene.indices.flags.writeable
    np.testing.assert_array_equal(scene.vertices[scene.indices], rows)
    assert scene.commands[0].start == 0 and scene.commands[0].count == 6


def test_convex_shortcut_keeps_ear_order_and_rejects_twice_winding_star():
    from map_gpu_geometry import _triangulate
    points = np.array([(0., 0.), (2., 0.), (3., 1.), (2., 3.), (0., 2.)])
    np.testing.assert_array_equal(_triangulate(points, None), points[[4, 0, 1, 4, 1, 2, 2, 3, 4]])
    angles = np.arange(5)*2*np.pi/5
    star = np.column_stack((np.cos(angles), np.sin(angles)))[[0, 2, 4, 1, 3]]
    assert _triangulate(star, None) is None


def test_unproved_independent_contours_never_share_winding_stencil(qt_application):
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    first = prepared.connections[0]
    first = replace(first, target=replace(first.target, road_class='ordinary'))
    second = replace(first, source=replace(first.source, width=30.),
                     target=replace(first.target, width=40.))
    scene = _compiler()(surface, replace(prepared, connections=(first, second)))
    commands = [command for command in scene.commands if command.mode == 'winding']
    assert len(commands) == 4, 'Independent signed windings can cancel and need independent covers'
    for command in commands:
        assert command.rank_material >= 0 and len(command.connection_members) == 1


def test_road_core_and_shell_reuse_index_ranges_and_canonical_material(qt_application):
    road = MapRoad(1, 'road', '', (((0., 0., 0.), (10., 0., 0.), (10., 0., 10.)),),
                   lanes_a=1, lanes_b=1, road_class='ordinary', width=12.)
    surface = _surface(MapSnapshot(roads=(road,), bounds=(0., 0., 20., 20.)),
                       buildings=False, routes=False)
    scene = _compiler()(surface, build_vector_map(surface))
    assert [command.shell_pass for command in scene.commands] == [1, 0]
    assert len({(command.start, command.count) for command in scene.commands}) == 1
    assert set(scene.materials[:, 28]) == {0.}
    assert len(scene.indices) == 30 and len(scene.vertices) == 20


def test_roads_and_connection_strokes_and_lane_fan_are_built_only_once(qt_application, monkeypatch):
    import map_gpu_geometry
    calls = dict(stroke=0, lane=0)
    stroke, lane = map_gpu_geometry._stroke, map_gpu_geometry._lane_fan

    def count_stroke(*args, **kwargs):
        calls['stroke'] += 1
        return stroke(*args, **kwargs)

    def count_lane(*args, **kwargs):
        calls['lane'] += 1
        return lane(*args, **kwargs)

    monkeypatch.setattr(map_gpu_geometry, '_stroke', count_stroke)
    monkeypatch.setattr(map_gpu_geometry, '_lane_fan', count_lane)
    surface = _connection_surface()
    scene = _compiler()(surface, build_vector_map(surface))
    assert calls == dict(stroke=3, lane=1)
    winding = [command for command in scene.commands if command.mode == 'winding']
    assert len({(command.start, command.count, command.cover_start) for command in winding}) == 1
    assert all(command.shell_pass in (0, 1) for command in winding)


def test_tunnel_topology_with_round_core_caps_keeps_separate_stroke_ranges(qt_application):
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    connection = replace(prepared.connections[0], layer=1, tunnel=True)
    scene = _compiler()(surface, replace(prepared, connections=(connection,)))
    overview = [command for command in scene.commands if command.connection_rank == 1 and command.max_zoom == .15]
    assert [command.shell_pass for command in overview] == [1, 0]
    assert overview[0].start != overview[1].start
    assert 2 not in _command_rows(scene, overview[0])[:, 10]
    assert 2 in _command_rows(scene, overview[1])[:, 10]


def test_opposite_signed_lane_contours_have_independent_stencil_covers(qt_application):
    from map_vector import _lane_template
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    original = prepared.connections[0]
    template = _lane_template(((20., 0., 0.), (27., 0., 0.), (34., 0., 0.)))
    first = replace(original, target=replace(original.target, road_class='ordinary'), target_lane=0,
                    templates=(template,))
    normals = -template.normals
    normals.setflags(write=False)
    second = replace(first, templates=(replace(template, normals=normals),))
    scene = _compiler()(surface, replace(prepared, connections=(first, second)))
    core = [command for command in scene.commands if command.mode == 'winding' and command.shell_pass == 0]
    assert len(core) == 2 and len({command.cover_start for command in core}) == 2
    source, target = road_style(first.source, 1.), road_style(first.target, 1.)
    signs = []
    for command in core:
        rows = _command_rows(scene, command)
        offsets = rows[:, 4]*source.width+rows[:, 5]*target.width+rows[:, 6]
        points = (rows[:, :2]+rows[:, 2:4]*offsets[:, None]).reshape(-1, 3, 2)
        area = sum((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]) for a, b, c in points)
        signs.append(np.sign(area))
    assert signs == [1., -1.], 'Combining these independent fans would cancel their overlap'


def test_gpu_layers_reuse_base_identity_when_route_presentation_changes(qt_application, monkeypatch):
    from map_gpu_geometry import compile_gpu_layers
    import map_gpu_geometry
    surface = _connection_surface()
    route = MapRoute(1, '', 1, 'a', 'a', 'bus', (), (((0., 0., 0.), (10., 0., 10.)),))
    prepared = replace(build_vector_map(surface), routes=(route,))
    surface.options.update(routes=True, route_colors={1: '#2266ff'})
    first = compile_gpu_layers(surface, prepared)
    assert set(first.base.materials[:, 28]) <= {0., 2., 6., 7., 8.}
    assert set(first.routes.materials[:, 28]) == {4.}

    def unexpected_rebuild(*args, **kwargs):
        raise AssertionError('A supplied base must not rebuild road geometry')

    monkeypatch.setattr(map_gpu_geometry, '_roads', unexpected_rebuild)
    surface.options['route_colors'] = {1: '#dd4422'}
    second = compile_gpu_layers(surface, prepared, base=first.base)
    assert second.base is first.base
    assert not np.array_equal(first.routes.materials, second.routes.materials)
    assert not second.routes.vertices.flags.writeable and not second.routes.indices.flags.writeable
    assert all(command.shell_pass == -1 for command in second.routes.commands)


def test_gpu_layers_check_cancellation_before_reusing_base(qt_application):
    from map_gpu_geometry import compile_gpu_layers
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    first = compile_gpu_layers(surface, prepared)
    with pytest.raises(VectorMapCancelled):
        compile_gpu_layers(surface, prepared, lambda: True, base=first.base)


def test_optional_pair_proof_runs_once_and_keeps_original_strip_rows(qt_application, monkeypatch):
    import map_gpu_geometry
    seen = []

    def prove(rows, material, cancelled=None):
        assert rows.dtype == material.dtype == np.float32
        assert np.all(np.abs(rows[:, 7]) == .5) and material[28] == 2
        seen.append(rows.copy())
        return True

    monkeypatch.setattr(map_gpu_geometry, '_load_strip', lambda: prove)
    surface = _connection_surface()
    scene = _compiler()(surface, build_vector_map(surface))
    detail = [command for command in scene.commands if command.min_zoom == .15 and command.connection_rank == 1]
    assert len(seen) == 1 and [command.mode for command in detail] == ['triangles', 'triangles']
    assert [command.shell_pass for command in detail] == [1, 0]
    assert len({(command.start, command.count) for command in detail}) == 1
    for command in detail:
        assert command.cover_count == 0
        np.testing.assert_array_equal(_command_rows(scene, command),
                                      seen[0][[0, 1, 4, 0, 4, 5, 1, 2, 3, 1, 3, 4]])


def test_optional_pair_proof_failure_keeps_independent_winding(qt_application, monkeypatch):
    import map_gpu_geometry

    def uncertain(*args, **kwargs):
        raise RuntimeError('Optional helper ABI unavailable')

    monkeypatch.setattr(map_gpu_geometry, '_load_strip', lambda: uncertain)
    surface = _connection_surface()
    scene = _compiler()(surface, build_vector_map(surface))
    detail = [command for command in scene.commands if command.min_zoom == .15 and command.connection_rank == 1]
    assert [command.mode for command in detail] == ['winding', 'winding']


def test_optional_pair_proof_declines_more_than_64_boundary_rows(qt_application, monkeypatch):
    import map_gpu_geometry
    from map_vector import _lane_template

    def unexpected(*args, **kwargs):
        raise AssertionError('Large contours must bypass the bounded native proof')

    monkeypatch.setattr(map_gpu_geometry, '_load_strip', lambda: unexpected)
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    template = _lane_template(tuple((float(i), 0., 0.) for i in range(33)))
    connection = replace(prepared.connections[0], templates=(template,))
    scene = _compiler()(surface, replace(prepared, connections=(connection,)))
    assert any(command.mode == 'winding' for command in scene.commands)


def test_optional_pair_proof_checks_cancellation_before_acceptance(qt_application, monkeypatch):
    import map_gpu_geometry
    event = threading.Event()

    def prove(rows, material, cancelled=None):
        event.set()
        return True

    monkeypatch.setattr(map_gpu_geometry, '_load_strip', lambda: prove)
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    with pytest.raises(VectorMapCancelled):
        _compiler()(surface, prepared, event)


def test_optional_strip_batches_and_fallback_keep_shared_pass_order(qt_application, monkeypatch):
    import map_gpu_geometry
    calls = []

    def prove(rows, material, cancelled=None):
        calls.append(float(material[2]))
        return material[2] < 40.

    monkeypatch.setattr(map_gpu_geometry, '_load_strip', lambda: prove)
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    first = prepared.connections[0]
    connections = (first, replace(first, source=replace(first.source, width=30.)),
                   replace(first, source=replace(first.source, width=50.)))
    scene = _compiler()(surface, replace(prepared, connections=connections))
    assert calls == [14., 30., 50.]
    passes = []
    for shell_pass in (1, 0):
        detail = [command for command in scene.commands if command.min_zoom == .15
                  and command.connection_rank == 1 and command.shell_pass == shell_pass]
        assert [command.mode for command in detail] == ['triangles', 'winding']
        assert [[member[0] for member in command.connection_members] for command in detail] == [[0, 1], [2]]
        assert detail[0].rank_material == -1 and detail[0].count == 24
        passes.append([(command.start, command.count, command.cover_start) for command in detail])
    assert passes[0] == passes[1], 'Cached leaf ranges must not replay an already merged neighbour'


def test_native_optional_pair_proof_selects_shared_strip_for_straight_lane(qt_application, monkeypatch):
    import os
    import map_gpu_geometry
    from map_vector import _lane_template
    module = pytest.importorskip('map_gpu_strip')
    test_library = os.environ.get('CIM2_STRIP_TEST_DLL')
    native = module.NativeStrip(test_library) if test_library else module.load_strip()
    if native is None:
        pytest.skip('Optional native strip helper is unavailable')
    accepted = []

    def prove(rows, material, cancelled=None):
        result = native(rows, material, cancelled=cancelled)
        accepted.append(result)
        return result

    monkeypatch.setattr(map_gpu_geometry, '_load_strip', lambda: prove)
    surface = _connection_surface()
    prepared = build_vector_map(surface)
    first = prepared.connections[0]
    template = _lane_template(((20., 0., 0.), (30., 0., 0.), (40., 0., 0.)))
    connection = replace(first, target=replace(first.source, id=2), target_lane=0, templates=(template,))
    scene = _compiler()(surface, replace(prepared, connections=(connection,)))
    assert accepted == [True]
    detail = [command for command in scene.commands if command.min_zoom == .15]
    assert [command.mode for command in detail] == ['triangles', 'triangles']
    assert [command.shell_pass for command in detail] == [1, 0]
    assert len({(command.start, command.count) for command in detail}) == 1
