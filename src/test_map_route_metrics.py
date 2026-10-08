"""Direction metrics use saved segment counts and arrival offsets, never rendered lengths."""
from dataclasses import replace
from importlib import import_module, util

import pytest
from map_model import MapRoute, RouteDirection

TICKS = 600_000_000


def metrics(*args, **kwargs):
    assert util.find_spec('map_route_metrics') is not None, 'direction metric API is missing'
    return import_module('map_route_metrics').selected_route_metrics(*args, **kwargs)


def route(**changes):
    fields = dict(id=1, name='Test', number=1, company_id='a', company_name='A', mode='bus',
        stop_ids=(1,2,3,4), paths=(((0.,0.,0.),(9999.,0.,0.)),),
        direction=RouteDirection('roundtrip',2),
        leg_paths=((((0.,0.,0.),(1.,0.,0.)),),)*3,
        leg_map_length_units=(100*1024,200*1024,300*1024),
        depot_map_length_units=(10*1024,20*1024),
        stop_arrival_offsets_ticks=(0,12*TICKS,32*TICKS,58*TICKS))
    fields.update(changes)
    return MapRoute(**fields)


def test_directions_are_additive_using_original_native_map_length_scope():
    r=route()
    down=metrics(r,'down');up=metrics(r,'up');whole=metrics(r,'whole',whole_duration_minutes=65)
    assert down.length_km == .6 and up.length_km == .6
    assert down.length_km+up.length_km == whole.length_km == 1.2
    assert down.duration_minutes == 32 and up.duration_minutes == 26
    assert down.speed_kmh == pytest.approx(.6/32*60)
    assert whole.duration_minutes == 65
    with_depot=[metrics(r,d,True,whole_duration_minutes=65) for d in ('down','up','whole')]
    assert with_depot[0].deadhead_km == .02 and with_depot[1].deadhead_km == .04
    assert with_depot[0].length_km+with_depot[1].length_km == pytest.approx(with_depot[2].length_km)
    assert with_depot[2].length_km == pytest.approx(1.26)
    assert with_depot[0].duration_minutes == 32  # Depot switch only changes length scope.
    assert with_depot[0].speed_kmh == down.speed_kmh
    assert with_depot[1].speed_kmh == up.speed_kmh


def test_saved_business_terminal_index_is_used_not_geometric_midpoint_or_half_time():
    r=route(direction=RouteDirection('roundtrip',1))
    assert metrics(r,'down').duration_minutes == 12
    assert metrics(r,'up').duration_minutes == 46


@pytest.mark.parametrize('offsets', [(), (0,None,32*TICKS,58*TICKS), (0,12*TICKS),
                                       (0,40*TICKS,32*TICKS,58*TICKS), (0,0,0,0), (-1,0,32*TICKS,58*TICKS)])
def test_unusable_saved_arrival_offsets_never_fall_back_to_full_line_duration(offsets):
    value=metrics(route(stop_arrival_offsets_ticks=offsets),'down',whole_duration_minutes=99)
    assert value.duration_minutes is None and value.speed_kmh is None
    assert value.length_km == .6


def test_unknown_segment_is_missing_but_known_zero_length_is_zero():
    assert metrics(route(leg_map_length_units=(100*1024,None,300*1024)),'down').length_km is None
    assert metrics(route(leg_map_length_units=(0,0,300*1024)),'down').length_km == 0
    assert metrics(route(depot_map_length_units=(None,20*1024)),'down',True).length_km is None
    assert metrics(route(depot_map_length_units=(None,20*1024)),'down').length_km == .6


def test_old_cache_never_uses_drawn_geometry_or_whole_fallback_for_single_direction():
    r=route(leg_map_length_units=(),stop_arrival_offsets_ticks=())
    old=metrics(r,'whole',whole_duration_minutes=65,whole_length_km=1.26)
    assert old.length_km == 1.26 and old.duration_minutes == 65
    selected=metrics(r,'up',whole_duration_minutes=65,whole_length_km=1.26)
    assert selected.length_km is None and selected.duration_minutes is None


@pytest.mark.parametrize('kind', ['circular','one_way','ring','oneway'])
def test_nonsplit_routes_keep_effective_whole_and_full_line_time(kind):
    value=metrics(route(direction=RouteDirection(kind)),'up',whole_duration_minutes=65)
    assert value.effective_direction == 'whole' and value.length_km == 1.2
    assert value.duration_minutes == 65


def test_roundtrip_without_known_terminal_cannot_invent_a_single_direction():
    value=metrics(route(direction=RouteDirection('roundtrip')),'up',whole_duration_minutes=65)
    assert value.length_km is None and value.duration_minutes is None


def test_unknown_classification_matches_rendering_whole_and_preserves_full_line_time():
    value=metrics(route(direction=RouteDirection()),'up',whole_duration_minutes=65)
    assert value.effective_direction == 'whole' and value.duration_minutes == 65


def test_whole_speed_uses_full_line_length_and_time_even_when_depot_display_is_off():
    a=metrics(route(),'whole',False,whole_duration_minutes=55,whole_length_km=17.5701640625)
    b=metrics(route(),'whole',True,whole_duration_minutes=55,whole_length_km=17.5701640625)
    assert a.speed_kmh == b.speed_kmh == pytest.approx(17.5701640625/55*60)


def test_integer_native_partition_retains_repeated_road_counts_and_avoids_rounding():
    r=route(leg_map_length_units=(1001,1001,1001))
    a=metrics(r,'down');b=metrics(r,'up');all_value=metrics(r)
    assert a.operating_km == 2002/1024/1000*2
    assert a.operating_km+b.operating_km == pytest.approx(all_value.operating_km)
    assert all_value.operating_km == 3003/1024/1000*2


def test_saved_metrics_do_not_depend_on_rendered_geometry_availability():
    r=route(leg_paths=(),paths=())
    assert metrics(r,'down').length_km == .6
    assert metrics(r,'up').length_km == .6


def test_native_length_extractor_matches_original_final_entry_exclusion_without_dedup():
    assert util.find_spec('map_route_metrics') is not None
    function=import_module('map_route_metrics').saved_leg_map_length
    road={'m_length':1234}
    path=[{'m_road':road},{'m_road':road},{'m_road':{'m_length':9999}}]
    assert function(path,lambda obj,key:obj.get(key),list) == 2468
    assert function(None,lambda obj,key:obj.get(key),list) is None


def test_extraction_preserves_stop_occurrence_offsets_depot_partition_and_cache_roundtrip():
    from dataclasses import asdict
    import json
    from map_geometry import snapshot_from_data, _decode_snapshot, SCHEMA_VERSION
    # Same physical stop appears twice, with distinct cumulative arrival times.
    stops=[dict(id=i,name='',position=[index*10,0,0],arrival_offset_ticks=offset*TICKS)
           for index,(i,offset) in enumerate(((99,0),(1,0),(2,12),(1,32)))]
    raw=dict(roads={},buildings=[dict(id=99,kind='DepotData',position=[0,0,0])],
             lines=[dict(id=1,stops=stops,legs=[dict(roads=[],map_length_units=v)
                                              for v in (10,100,200,20)])])
    snapshot=snapshot_from_data(raw)
    r=snapshot.routes[0]
    assert r.stop_ids == (1,2,1)
    assert r.stop_arrival_offsets_ticks == (0,12*TICKS,32*TICKS)
    assert r.leg_map_length_units == (100,200) and r.depot_map_length_units == (10,20)
    restored=_decode_snapshot(json.loads(json.dumps(asdict(snapshot))))
    assert restored == snapshot and restored.schema_version == SCHEMA_VERSION == 12
