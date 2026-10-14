"""The prepared map replays saved metre geometry at changing view scales."""
from dataclasses import replace
import math
import pytest

from PySide6.QtGui import QImage, QPainter

from map_canvas import MAP_BACKGROUND, MapCanvas, _FrameSurface
from map_model import (MapBuilding, MapJunction, MapJunctionConnection, MapRoad,
                       MapLane, MapRoute, MapSnapshot, MapStop, RouteDirection)
from map_vector import VectorMapCancelled, build_vector_map, paint_vector_map, _visible_connections
import map_vector


def _surface(qt_application, snapshot, **options):
    canvas = MapCanvas()
    canvas.resize(400, 300)
    canvas.set_snapshot(snapshot)
    canvas.center = (50., 50.)
    canvas.zoom = 1.
    canvas.set_options(routes=False, stops=False, stop_names=False, line_numbers=False, **options)
    surface = _FrameSurface(canvas)
    canvas.close()
    return surface


def _image(surface, prepared):
    image = QImage(surface._size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(MAP_BACKGROUND)
    painter = QPainter(image)
    try:
        paint_vector_map(painter, surface, prepared, overlays=False)
    finally:
        painter.end()
    return image


def test_prepared_building_replays_at_new_zoom_without_losing_saved_vertices(qt_application):
    polygon = ((65., 0., 42.), (85., 0., 42.), (85., 0., 58.), (65., 0., 58.))
    surface = _surface(qt_application, MapSnapshot(buildings=(
        MapBuilding(3, 'house', 'x', (75., 0., 50.), polygon),
    ), bounds=(0., 0., 100., 100.)), roads=False,
        building_colors={3: '#bb6644'})
    prepared = build_vector_map(surface)
    assert _image(surface, prepared).pixelColor(225, 150).name() == '#bb6644'
    surface.zoom = 2.
    image = _image(surface, prepared)
    assert image.pixelColor(250, 150).name() == '#bb6644'
    assert image.pixelColor(225, 150).name() == MAP_BACKGROUND.lower()


def test_road_width_recomputes_at_each_zoom_and_keeps_per_path_bridge_mask(qt_application):
    lower = ((10., 0., 50.), (90., 0., 50.))
    upper = ((50., 5., 10.), (50., 5., 90.))
    road = MapRoad(1, 'road', 'x', (lower, upper), lanes_a=1, lanes_b=1,
                   road_class='ordinary', width=12., bridge_masks=(0, 1))
    surface = _surface(qt_application, MapSnapshot(roads=(road,), bounds=(0., 0., 100., 100.)),
                       buildings=False)
    prepared = build_vector_map(surface)
    surface.zoom = .1
    small = _image(surface, prepared)
    surface.zoom = 2.
    large = _image(surface, prepared)
    center = surface.world_to_screen((30., 0., 50.)).toPoint()
    assert large.pixelColor(center.x(), center.y()+7).name() != MAP_BACKGROUND.lower()
    assert small.pixelColor(198, 150).name() != MAP_BACKGROUND.lower()


def test_saved_junction_curve_does_not_invent_a_center_gap_fill(qt_application):
    left = MapRoad(1, 'road', 'left', (((0., 0., 50.), (40., 0., 50.)),),
                   lanes_a=1, lanes_b=1, road_class='ordinary')
    right = replace(left, id=2, paths=(((60., 0., 50.), (100., 0., 50.)),))
    curve = ((40., 0., 50.), (45., 0., 55.), (55., 0., 55.), (60., 0., 50.))
    junction = MapJunction(3, (50., 0., 50.), (1, 2),
                           (MapJunctionConnection(4, 1, 2, 0, 0, 1, (curve,)),))
    surface = _surface(qt_application, MapSnapshot(roads=(left, right), junctions=(junction,),
                                                     bounds=(0., 0., 100., 100.)), buildings=False)
    prepared = build_vector_map(surface)
    image = _image(surface, prepared)
    saved = surface.world_to_screen((50., 55.)).toPoint()
    gap = surface.world_to_screen((50., 50.)).toPoint()
    assert image.pixelColor(saved).name() != MAP_BACKGROUND.lower()
    assert image.pixelColor(gap).name() == MAP_BACKGROUND.lower()


def test_overview_connection_lod_filters_before_lane_materialization(qt_application):
    road = MapRoad(1, 'road', 'source', (((0., 0., 50.), (45., 0., 50.)),),
                   lanes_a=1, lanes_b=1, road_class='ordinary')
    target = replace(road, id=2, paths=(((55., 0., 50.), (100., 0., 50.)),))
    curve = ((45., 0., 50.), (50., 0., 52.), (55., 0., 50.))
    junction = MapJunction(3, (50., 0., 50.), (1, 2),
                           (MapJunctionConnection(4, 1, 2, 0, 0, 1, (curve,)),))
    surface = _surface(qt_application, MapSnapshot(roads=(road, target), junctions=(junction,),
                                                     bounds=(0., 0., 100., 100.)), buildings=False)
    prepared = build_vector_map(surface)
    surface.zoom = .1
    assert len(tuple(_visible_connections(prepared, surface._viewport_bounds(), surface.zoom))) == 0
    surface.zoom = .2
    assert len(tuple(_visible_connections(prepared, surface._viewport_bounds(), surface.zoom))) == 1


def test_overview_uses_saved_turn_stroke_then_detail_uses_lane_surface(qt_application):
    from map_canvas import road_style
    source = MapRoad(1, 'road', 'left', (((10., 0., 50.), (40., 0., 50.)),),
                     lanes_a=2, lanes_b=0, road_class='ordinary', width=14.,
                     lanes=(MapLane(0, 0x1000101, 1, -1.5),
                            MapLane(1, 0x1000101, 1, 1.5)))
    target = replace(source, id=2, paths=(((60., 0., 50.), (90., 0., 50.)),))
    curve = ((40., 0., 50.), (50., 0., 55.), (60., 0., 50.))
    junction = MapJunction(3, (50., 0., 50.), (1, 2),
                           (MapJunctionConnection(4, 1, 2, 0, 0, 0x1000000, (curve,)),))
    surface = _surface(qt_application, MapSnapshot(roads=(source, target), junctions=(junction,),
                                                     bounds=(0., 0., 100., 100.)), buildings=False)
    prepared = build_vector_map(surface)
    surface.zoom = .1
    overview = map_vector._connection_paints(surface, prepared, surface._viewport_bounds(),
                                             road_style)[1][0]
    assert overview.edge is None
    assert len(overview.core) == len(curve)
    surface.zoom = .2
    detail = map_vector._connection_paints(surface, prepared, surface._viewport_bounds(),
                                           road_style)[1][0]
    assert detail.edge is not None
    assert len(detail.core) == 2*len(curve)


def test_bulk_lane_templates_preserve_each_saved_curve_normal_and_arc(qt_application):
    from map_vector import _bulk_lane_templates, _lane_template
    import numpy as np
    curves = (((0., 0., 0.), (3., 0., 4.), (6., 0., 4.)),
              ((10., 0., 10.), (10., 0., 10.), (10., 0., 15.)))
    bulk = _bulk_lane_templates(curves)
    assert len(bulk) == len(curves)
    for points, template in zip(curves, bulk):
        reference = _lane_template(points)
        assert not template.screen_base.flags.writeable
        assert not template.normals.flags.writeable
        assert not template.fractions.flags.writeable
        assert np.allclose(template.screen_base, reference.screen_base)
        assert np.allclose(template.normals, reference.normals)
        assert np.allclose(template.fractions, reference.fractions)


def test_prepared_route_respects_direction_width_and_visible_stops(qt_application):
    down = ((10., 0., 45.), (90., 0., 45.))
    up = ((90., 0., 55.), (10., 0., 55.))
    route = MapRoute(7, 'line', 7, 'company', 'company', 'bus', (1, 3, 2),
                     (down, up), RouteDirection('roundtrip', 1), ((down,), (up,)))
    snapshot = MapSnapshot(routes=(route,), stops=(MapStop(1, 'down', down[0]),
                                                       MapStop(2, 'up', up[0]),
                                                       MapStop(3, 'terminal', down[-1])),
                           bounds=(0., 0., 100., 100.))
    surface = _surface(qt_application, snapshot, roads=False, buildings=False)
    surface.options.update(routes=True, stops=True, direction='down', mode_widths={'bus': 8.},
                           route_colors={7: '#2266ff'})
    prepared = build_vector_map(surface)
    image = _image(surface, prepared)
    assert image.pixelColor(200, 152).name() == '#2266ff'
    assert image.pixelColor(200, 145).name() == MAP_BACKGROUND.lower()
    assert image.pixelColor(surface.world_to_screen(down[0]).toPoint()).name() == '#ffffff'
    assert image.pixelColor(surface.world_to_screen(up[0]).toPoint()).name() == MAP_BACKGROUND.lower()
    surface.options['direction'] = 'up'
    image = _image(surface, prepared)
    assert image.pixelColor(200, 145).name() == '#2266ff'
    assert image.pixelColor(200, 155).name() == MAP_BACKGROUND.lower()


def test_unknown_road_level_is_drawn_and_can_be_filtered(qt_application):
    road = MapRoad(8, 'unclassified', 'unknown', (((20., 0., 50.), (80., 0., 50.)),),
                   lanes_a=4, lanes_b=4, road_class='unknown')
    snapshot = MapSnapshot(roads=(road,), bounds=(0., 0., 100., 100.))
    surface = _surface(qt_application, snapshot, buildings=False)
    image = _image(surface, build_vector_map(surface))
    assert image.pixelColor(200, 150).name() != MAP_BACKGROUND.lower()
    surface.options['road_levels'] = {'express'}
    image = _image(surface, build_vector_map(surface))
    assert image.pixelColor(200, 150).name() == MAP_BACKGROUND.lower()


def test_cancelled_preparation_does_not_publish_a_partial_template(qt_application):
    road = MapRoad(8, 'road', 'x', (((20., 0., 50.), (80., 0., 50.)),))
    surface = _surface(qt_application, MapSnapshot(roads=(road,), bounds=(0., 0., 100., 100.)))
    with pytest.raises(VectorMapCancelled):
        build_vector_map(surface, cancelled=lambda: True)


def test_bridge_stays_above_ground_street_at_crossing(qt_application):
    ground = MapRoad(1, 'road', 'ground', (((10., 0., 50.), (90., 0., 50.)),),
                     lanes_a=1, lanes_b=1, road_class='ordinary')
    bridge = MapRoad(2, 'road', 'bridge', (((50., 5., 10.), (50., 5., 90.)),),
                     lanes_a=2, lanes_b=2, road_class='expressway', bridge=True)
    surface = _surface(qt_application, MapSnapshot(roads=(ground, bridge),
                                                   bounds=(0., 0., 100., 100.)), buildings=False)
    image = _image(surface, build_vector_map(surface))
    assert image.pixelColor(200, 150).name() == '#f7e4ab'


def test_reverse_shared_route_overlaps_on_exact_saved_geometry(qt_application):
    path = ((10., 0., 50.), (90., 0., 50.))
    reverse = tuple(reversed(path))
    route = MapRoute(7, 'line', 7, 'company', 'company', 'bus', (),
                     (path, reverse), RouteDirection('roundtrip', 1),
                     ((path,), (reverse,)))
    surface = _surface(qt_application, MapSnapshot(routes=(route,),
                                                   bounds=(0., 0., 100., 100.)),
                       roads=False, buildings=False)
    surface.options.update(routes=True, distinguish_directions=True,
                           mode_widths={'bus': 5.}, route_colors={7: '#2266ff'})
    image = _image(surface, build_vector_map(surface))
    assert all(image.pixelColor(x,150).name() == '#2266ff' for x in range(175,226))
    assert all(image.pixelColor(x,154).name() == MAP_BACKGROUND.lower() for x in range(175,226))


def test_shared_route_colour_follows_last_painted_query_priority(qt_application):
    path=((10.,0.,50.),(90.,0.,50.))
    routes=tuple(MapRoute(i,str(i),i,'c','c','bus',(),(path,)) for i in range(3))
    surface=_surface(qt_application,MapSnapshot(routes=routes,bounds=(0.,0.,100.,100.)),
                     roads=False,buildings=False)
    surface.options.update(routes=True,route_colors={0:'#ee3366',1:'#2266ff',2:'#ee3366'})
    assert _image(surface,build_vector_map(surface)).pixelColor(200,150).name() == '#ee3366'


def test_distinct_saved_up_leg_keeps_dash_pattern_without_artificial_offset(qt_application):
    path=((10.,0.,50.),(90.,0.,50.))
    up=((90.,0.,55.),(10.,0.,55.))
    route=MapRoute(7,'line',7,'c','c','bus',(),(path,up),
                   RouteDirection('roundtrip',1),((path,),(up,)))
    surface=_surface(qt_application,MapSnapshot(routes=(route,),bounds=(0.,0.,100.,100.)),
                     roads=False,buildings=False)
    surface.options.update(routes=True,distinguish_directions=True,
                           mode_widths={'bus':3.},route_colors={7:'#2266ff'})
    image=_image(surface,build_vector_map(surface))
    colours=[image.pixelColor(x,145).name() for x in range(175,226)]
    assert '#2266ff' in colours and MAP_BACKGROUND.lower() in colours
    assert all(image.pixelColor(x,150).name() == '#2266ff' for x in range(175,226))


def test_cached_route_outline_keeps_reference_dash_and_offset_pixels(qt_application):
    path = ((10., 0., 50.), (45., 0., 55.), (90., 0., 50.))
    reverse = tuple(reversed(path))
    route = MapRoute(7, 'line', 7, 'company', 'company', 'bus', (),
                     (path, reverse), RouteDirection('roundtrip', 1),
                     ((path,), (reverse,)))
    surface = _surface(qt_application, MapSnapshot(routes=(route,),
                                                   bounds=(0., 0., 100., 100.)),
                       roads=False, buildings=False)
    surface.options.update(routes=True, distinguish_directions=True,
                           mode_widths={'bus': 5.}, route_colors={7: '#2266ff'})
    vector = _image(surface, build_vector_map(surface))
    reference = QImage(surface._size, QImage.Format.Format_ARGB32_Premultiplied)
    reference.fill(MAP_BACKGROUND)
    painter = QPainter(reference)
    surface._paint(painter, overlays=False)
    painter.end()
    import numpy as np
    actual = np.frombuffer(vector.bits(), dtype=np.uint8).reshape(300, 400, 4)
    expected = np.frombuffer(reference.bits(), dtype=np.uint8).reshape(300, 400, 4)
    difference = np.max(np.abs(actual.astype(np.int16)-expected.astype(np.int16)), axis=2)
    assert np.count_nonzero(difference) == 0, (np.count_nonzero(difference), difference.max())


def test_connection_fill_transitions_between_actual_road_styles(qt_application):
    source = MapRoad(1, 'road', 'express', (((10., 0., 50.), (30., 0., 50.)),),
                     lanes_a=1, lanes_b=1, road_class='expressway', width=14.)
    target = replace(source, id=2, road_class='ordinary',
                     paths=(((70., 0., 50.), (90., 0., 50.)),))
    curve = ((30., 0., 50.), (70., 0., 50.))
    junction = MapJunction(3, (50., 0., 50.), (1, 2),
                           (MapJunctionConnection(4, 1, 2, 0, 0, 0x1000000, (curve,)),))
    surface = _surface(qt_application, MapSnapshot(roads=(source, target), junctions=(junction,),
                                                     bounds=(0., 0., 100., 100.)), buildings=False)
    image = _image(surface, build_vector_map(surface))
    left = image.pixelColor(surface.world_to_screen((40., 50.)).toPoint())
    right = image.pixelColor(surface.world_to_screen((60., 50.)).toPoint())
    assert left.blue() < 220
    assert right.blue() > 220


@pytest.mark.parametrize('backward', [False, True])
def test_saved_lane_surfaces_meet_the_observed_road_edges(qt_application, backward):
    lanes = (MapLane(0, 0x1000101, 1, 1.5),
             MapLane(1, 0x1000201 if backward else 0x1000101, 1, -1.5))
    road = MapRoad(1, 'road', 'left', (((10., 0., 50.), (40., 0., 50.)),),
                   lanes_a=2, lanes_b=0, road_class='ordinary', width=14., lanes=lanes)
    other = replace(road, id=2, paths=(((60., 0., 50.), (90., 0., 50.)),))
    curves = []
    for i, z in enumerate((48.5, 51.5)):
        curve = ((40., 0., z), (50., 0., z), (60., 0., z))
        reverse = backward and i == 1
        curves.append(MapJunctionConnection(10+i, 2 if reverse else 1, 1 if reverse else 2,
                                            i, i, 0x1000000,
                                            (tuple(reversed(curve)) if reverse else curve,)))
    junction = MapJunction(3, (50., 0., 50.), (1, 2), tuple(curves))
    surface = _surface(qt_application, MapSnapshot(roads=(road, other), junctions=(junction,),
                                                     bounds=(0., 0., 100., 100.)), buildings=False)
    image = _image(surface, build_vector_map(surface))
    assert all(image.pixelColor(surface.world_to_screen((50., z)).toPoint()).red() > 245
               for z in range(44, 57))
    assert image.pixelColor(surface.world_to_screen((50., 59.)).toPoint()).name() == MAP_BACKGROUND.lower()


def test_building_area_threshold_is_per_footprint_within_a_colour_batch(qt_application):
    def square(identity, cx, side):
        half = side/2
        return MapBuilding(identity, 'house', str(identity), (cx, 0., 50.),
                           ((cx-half, 0., 50.-half), (cx+half, 0., 50.-half),
                            (cx+half, 0., 50.+half), (cx-half, 0., 50.+half)))
    surface = _surface(qt_application, MapSnapshot(buildings=(square(1, 100., 10.),
                                                               square(2, 200., math.sqrt(120.))),
                                                     bounds=(0., 0., 300., 100.)), roads=False)
    surface.center = (150., 50.)
    surface.zoom = .085
    image = _image(surface, build_vector_map(surface))
    assert image.pixelColor(surface.world_to_screen((100., 50.)).toPoint()).name() == MAP_BACKGROUND.lower()
    assert image.pixelColor(surface.world_to_screen((200., 50.)).toPoint()).name() != MAP_BACKGROUND.lower()


def test_road_crossing_tile_boundary_paints_once(qt_application):
    def render(cx):
        road = MapRoad(1, 'road', 'street', (((cx-50., 0., 50.), (cx+50., 0., 50.)),),
                       lanes_a=1, lanes_b=1, road_class='ordinary')
        surface = _surface(qt_application, MapSnapshot(roads=(road,),
                                                       bounds=(cx-100., 0., cx+100., 100.)), buildings=False)
        surface.center = (cx, 50.)
        surface.zoom = 1.
        image = _image(surface, build_vector_map(surface))
        return [image.pixelColor(x, y).rgba() for x in range(180, 221) for y in range(145, 156)]
    assert render(512.) == render(256.)


def test_saved_connection_crossing_tile_boundary_paints_once(qt_application):
    def render(cx):
        source = MapRoad(1, 'road', 'source', (((cx-90., 0., 50.), (cx-30., 0., 50.)),),
                         lanes_a=1, lanes_b=1, road_class='ordinary')
        target = replace(source, id=2,
                         paths=(((cx+30., 0., 50.), (cx+90., 0., 50.)),))
        curve = ((cx-30., 0., 50.), (cx-10., 0., 55.),
                 (cx+10., 0., 55.), (cx+30., 0., 50.))
        junction = MapJunction(3, (cx, 0., 50.), (1, 2),
                               (MapJunctionConnection(4, 1, 2, 0, 0, 0x1000000, (curve,)),))
        surface = _surface(qt_application,
                           MapSnapshot(roads=(source, target), junctions=(junction,),
                                       bounds=(cx-100., 0., cx+100., 100.)), buildings=False)
        surface.center = (cx, 50.)
        image = _image(surface, build_vector_map(surface))
        return image.bits().tobytes()
    assert render(512.) == render(256.)


def test_adjacent_saved_bridge_fragments_keep_the_corner_join(qt_application):
    road = MapRoad(1, 'road', 'bridge',
                   (((10., 0., 50.), (50., 0., 50.)),
                    ((50., 0., 50.), (50., 0., 90.))),
                   lanes_a=1, lanes_b=1, road_class='ordinary', bridge=True)
    surface = _surface(qt_application, MapSnapshot(roads=(road,),
                                                   bounds=(0., 0., 100., 100.)), buildings=False)
    vector = _image(surface, build_vector_map(surface))
    reference = QImage(surface._size, QImage.Format.Format_ARGB32_Premultiplied)
    reference.fill(MAP_BACKGROUND)
    painter = QPainter(reference)
    surface._paint_base(painter)
    painter.end()
    corner = surface.world_to_screen((50., 50.)).toPoint()
    actual = [vector.pixelColor(corner.x()+dx, corner.y()+dy).rgba()
              for dx in range(-5, 6) for dy in range(-5, 6)]
    expected = [reference.pixelColor(corner.x()+dx, corner.y()+dy).rgba()
                for dx in range(-5, 6) for dy in range(-5, 6)]
    assert actual == expected


def test_overview_culls_each_short_road_even_beside_a_long_batch_member(qt_application):
    short = MapRoad(1, 'road', 'short', (((20., 0., 50.), (25., 0., 50.)),),
                    lanes_a=1, lanes_b=1, road_class='ordinary')
    long = replace(short, id=2, name='long', paths=(((100., 0., 50.), (200., 0., 50.)),))
    def render(roads):
        surface = _surface(qt_application, MapSnapshot(roads=roads,
                                                       bounds=(0., 0., 250., 100.)), buildings=False)
        surface.center = (100., 50.)
        surface.zoom = .1
        image = _image(surface, build_vector_map(surface))
        return image.bits().tobytes()
    assert render((short, long)) == render((long,))


def test_connection_vectors_replay_on_pan_and_keep_only_two_zooms(qt_application):
    source = MapRoad(1, 'road', 'left', (((10., 0., 50.), (30., 0., 50.)),),
                     lanes_a=1, lanes_b=1, road_class='expressway', width=12.)
    target = replace(source, id=2, road_class='ordinary',
                     paths=(((70., 0., 50.), (90., 0., 50.)),))
    curve = ((30., 0., 50.), (45., 0., 55.), (55., 0., 55.), (70., 0., 50.))
    junction = MapJunction(3, (50., 0., 50.), (1, 2),
                           (MapJunctionConnection(4, 1, 2, 0, 0, 0x1000000, (curve,)),))
    surface = _surface(qt_application, MapSnapshot(roads=(source, target), junctions=(junction,),
                                                     bounds=(0., 0., 100., 100.)), buildings=False)
    prepared = build_vector_map(surface)
    first = next(value for key, value in surface._vector_connection_cache[1.].items()
                 if isinstance(key, int))
    surface.center = (60., 50.)
    panned = _image(surface, prepared)
    assert panned.pixelColor(surface.world_to_screen((50., 55.)).toPoint()).name() != MAP_BACKGROUND.lower()
    assert next(value for key, value in surface._vector_connection_cache[1.].items()
                if isinstance(key, int)) is first
    surface.zoom = 2.
    zoomed = _image(surface, prepared)
    assert zoomed.pixelColor(surface.world_to_screen((50., 55.)).toPoint()).name() != MAP_BACKGROUND.lower()
    surface.zoom = 3.
    _image(surface, prepared)
    assert len(surface._vector_connection_cache) == 2
    assert 1. not in surface._vector_connection_cache


def test_wheel_zoom_round_trip_reuses_nearly_equal_vector_materials(qt_application):
    source = MapRoad(1, 'road', 'left', (((10., 0., 50.), (40., 0., 50.)),),
                     lanes_a=1, lanes_b=1, road_class='ordinary')
    target = replace(source, id=2, paths=(((60., 0., 50.), (90., 0., 50.)),))
    curve = ((40., 0., 50.), (50., 0., 55.), (60., 0., 50.))
    junction = MapJunction(3, (50., 0., 50.), (1, 2),
                           (MapJunctionConnection(4, 1, 2, 0, 0, 0x1000000, (curve,)),))
    surface = _surface(qt_application, MapSnapshot(roads=(source, target), junctions=(junction,),
                                                     bounds=(0., 0., 100., 100.)), buildings=False)
    prepared = build_vector_map(surface)
    first = surface._vector_connection_cache[1.]
    surface.zoom = 2.
    _image(surface, prepared)
    surface.zoom = 1.00000000000001
    _image(surface, prepared)
    assert len(surface._vector_connection_cache) == 2
    assert surface._vector_connection_cache[1.] is first


def test_same_zoom_pan_reuses_compiled_saved_lane_paths(qt_application, monkeypatch):
    source = MapRoad(1, 'road', 'source', (((10., 0., 50.), (40., 0., 50.)),),
                     lanes_a=1, lanes_b=1, road_class='ordinary')
    target = replace(source, id=2, paths=(((60., 0., 50.), (90., 0., 50.)),))
    curve = ((40., 0., 50.), (48., 0., 55.), (60., 0., 50.))
    junction = MapJunction(3, (50., 0., 50.), (1, 2),
                           (MapJunctionConnection(4, 1, 2, 0, 0, 0x1000000, (curve,)),))
    surface = _surface(qt_application, MapSnapshot(roads=(source, target), junctions=(junction,),
                                                     bounds=(0., 0., 100., 100.)), buildings=False)
    prepared = build_vector_map(surface)
    original = map_vector._connection_runs
    calls = []
    def counted(*args):
        calls.append(1)
        return original(*args)
    monkeypatch.setattr(map_vector, '_connection_runs', counted)
    first = _image(surface, prepared)
    assert calls
    surface.center = (60., 50.)
    second = _image(surface, prepared)
    assert len(calls) == 2  # shell and fill were compiled only once
    assert first.pixelColor(200, 145) == second.pixelColor(190, 145)


def test_connections_share_per_zoom_road_styles_and_lane_margins(qt_application, monkeypatch):
    from map_canvas import road_style
    from map_vector import _connection_paints
    source = MapRoad(1, 'road', 'source', (((10., 0., 50.), (40., 0., 50.)),),
                     lanes_a=1, lanes_b=1, road_class='ordinary')
    target = replace(source, id=2, paths=(((60., 0., 50.), (90., 0., 50.)),))
    curves = (((40., 0., 49.), (50., 0., 50.), (60., 0., 49.)),
              ((40., 0., 51.), (50., 0., 52.), (60., 0., 51.)))
    junction = MapJunction(3, (50., 0., 50.), (1, 2),
                           tuple(MapJunctionConnection(4+i, 1, 2, 0, 0, 0x1000000, (curve,))
                                 for i, curve in enumerate(curves)))
    surface = _surface(qt_application, MapSnapshot(roads=(source, target), junctions=(junction,),
                                                     bounds=(0., 0., 100., 100.)), buildings=False)
    prepared = build_vector_map(surface)
    surface.zoom = 2.
    calls = {'style': 0, 'margin': 0}
    original_margin = surface._lane_margins
    def counted_style(*args):
        calls['style'] += 1
        return road_style(*args)
    def counted_margin(*args):
        calls['margin'] += 1
        return original_margin(*args)
    monkeypatch.setattr(surface, '_lane_margins', counted_margin)
    _connection_paints(surface, prepared, surface._viewport_bounds(), counted_style)
    assert calls == {'style': 2, 'margin': 2}


def test_same_zoom_pan_reuses_screen_width_route_offset(qt_application, monkeypatch):
    path = ((10., 0., 50.), (45., 0., 55.), (90., 0., 50.))
    route = MapRoute(7, 'line', 7, 'company', 'company', 'bus', (), (path,),
                     RouteDirection('unknown'))
    surface = _surface(qt_application, MapSnapshot(routes=(route,), bounds=(0., 0., 100., 100.)),
                       roads=False, buildings=False)
    surface.options.update(routes=True, route_colors={7: '#2266ff'})
    prepared = build_vector_map(surface)
    original = surface._polyline
    calls = []
    def counted(*args):
        calls.append(1)
        return original(*args)
    monkeypatch.setattr(surface, '_polyline', counted)
    first = _image(surface, prepared)
    assert calls
    surface.center = (60., 50.)
    second = _image(surface, prepared)
    assert len(calls) == 1
    assert first.pixelColor(200, 145) == second.pixelColor(190, 145)


def test_pan_across_route_bounds_reuses_the_query_route_plan(qt_application):
    near=MapRoute(1,'near',1,'a','a','bus',(),(((10.,0.,50.),(90.,0.,50.)),))
    far=replace(near,id=2,name='far',paths=(((1010.,0.,50.),(1090.,0.,50.)),))
    surface=_surface(qt_application,MapSnapshot(routes=(near,far),bounds=(0.,0.,1100.,100.)),
                     roads=False,buildings=False)
    surface.options.update(routes=True,route_colors={1:'#2266ff',2:'#dd4422'})
    prepared=build_vector_map(surface)
    assert _image(surface,prepared).pixelColor(200,150).name()=='#2266ff'
    plan=next(iter(surface._vector_route_plans.values()))
    surface.center=(1050.,50.)
    assert _image(surface,prepared).pixelColor(200,150).name()=='#dd4422'
    assert len(surface._vector_route_plans)==1
    assert next(iter(surface._vector_route_plans.values())) is plan
