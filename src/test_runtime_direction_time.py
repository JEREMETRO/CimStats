"""Shared runtime timing helpers, without importing the CLR extraction process."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


def runtime_helpers():
    source = Path(__file__).with_name('extract_runtime_data.py').read_text(encoding='utf8')
    tree = ast.parse(source)
    names = {'simulation_frame_time_span', 'recompute_runtime_leg_duration_ticks', 'recompute_runtime_line_values',
             'can_stop_here_serialized'}
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(selected) == len(names), 'runtime timing helper is missing'
    from line_duration import vehicle_duration_ticks
    scope = dict(field=lambda obj, key: obj.get(key) if obj is not None else None,
                 array_values=lambda values: list(values) if values is not None else [],
                 VEHICLE_TYPE_PARAMS={'公交': (3300, 12)}, FLAGS=0,
                 System=SimpleNamespace(Int32=int), vehicle_duration_ticks=vehicle_duration_ticks,
                 calculate_segment_length_sum=lambda line: sum(line.distances),
                 duration_segment_distance=lambda line, index: line.distances[index],
                 path_length_from_vehicle_route=lambda line: sum(line.distances),
                 timetable_needed_vehicles=lambda line, duration: 0)
    exec(compile(ast.Module(body=selected, type_ignores=[]), '<runtime timing helpers>', 'exec'), scope)
    return scope


class NativeLine:
    def __init__(self, stops, distances, *, method=True):
        self.stops = stops
        self.distances = distances
        self.method = method

    def get(self, name):
        return self.stops if name == 'm_stops' else None

    def GetType(self):
        def invoke(_, arguments):
            value = self.distances[arguments[0]]
            if isinstance(value, Exception):
                raise value
            return value
        methods = [SimpleNamespace(Name='CalculateSegmentLength', Invoke=invoke)] if self.method else []
        return SimpleNamespace(GetMethods=lambda _: methods)


def stops(count=4):
    return [dict(m_stop=dict(m_lineCount=1, m_prefabObject=None,
                             m_position=dict(x=i, y=0, z=0)),
                 m_pathDirty=False, m_path=[object(), object()]) for i in range(count)]


def test_vehicle_duration_divides_each_distance_before_multiplying_frame_span():
    from line_duration import vehicle_duration_ticks
    # Each 200-unit leg truncates to zero frames; summing distances first would yield one.
    assert sum(vehicle_duration_ticks(200, 3300, 12, 0, 313061) for _ in range(2)) == 0
    assert vehicle_duration_ticks(3300, 3300, 12, 1, 313061) == 230412896


@pytest.mark.parametrize('frames,start,now,expected', [
    (100, 1000, 31307100, 313061), (0, 0, 1, 350000),
    (100, None, 100, 350000), (100, 0, None, 350000), (10, 10, 0, 1),
])
def test_frame_span_uses_simulation_clock_with_existing_default(frames, start, now, expected):
    span = runtime_helpers()['simulation_frame_time_span']
    clock = lambda ticks: None if ticks is None else SimpleNamespace(Ticks=ticks)
    root = dict(m_simulationFrame=frames, m_simulationStart=clock(start), m_simulationTime=clock(now))
    assert span(root) == expected


def test_native_leg_indices_keep_depot_and_source_dwell_without_slot_rounding():
    helper = runtime_helpers()['recompute_runtime_leg_duration_ticks']
    records = stops()
    records[2]['m_stop']['m_lineCount'] = 0  # Waypoint has no dwell.
    result = helper(NativeLine(records, [3300, 6600, 9900, 13200]), '公交', 313061)
    assert result == (5008976, 235421872, 15026928, 245439824)
    assert sum(result[1:-1]) == 250448800  # Only the two operating edges.


@pytest.mark.parametrize('waypoint,expected', [(False, 230412896), (True, 5008976),
                                              (None, None), (0, None), ('false', None)])
def test_bound_prefab_uses_native_boolean_waypoint_and_preserves_unknowns(waypoint, expected):
    helper = runtime_helpers()['recompute_runtime_leg_duration_ticks']
    records = stops(2)
    records[1]['m_stop']['m_prefabObject'] = dict(m_waypoint=waypoint)
    # Bound prefab is authoritative even if the saved line-count heuristic disagrees.
    records[1]['m_stop']['m_lineCount'] = 0
    assert helper(NativeLine(records, [3300, 3300]), '公交', 313061)[1] == expected


@pytest.mark.parametrize('prefab,count,expected', [(None, 1, True), (None, 0, False),
                                                (None, None, None), ({}, 1, None),
                                                ({'m_waypoint': False}, 0, True),
                                                ({'m_waypoint': True}, 1, False)])
def test_stoppability_prefab_and_unbound_fallback_match_native_evidence(prefab, count, expected):
    helper = runtime_helpers()['can_stop_here_serialized']
    assert helper(dict(m_prefabObject=prefab, m_lineCount=count)) is expected


@pytest.mark.parametrize('flags,count,stoppable,ticks', [
    ({'station': True}, 1, False, 5008976),
    ({'station': False}, 0, True, 230412896),
    ({}, 0, False, 5008976),
    ({}, 1, True, 230412896),
    ({'station': None}, None, None, None),
    ({}, None, None, None),
])
def test_explicit_waypoint_evidence_overrides_uninitialized_prefab_default(flags, count, stoppable, ticks):
    helpers = runtime_helpers()
    records = stops(2)
    source = records[1]['m_stop']
    source['m_prefabObject'] = dict(m_id='station', m_waypoint=False)
    source['m_lineCount'] = count
    assert helpers['can_stop_here_serialized'](source, waypoint_flags=flags) is stoppable
    value = helpers['recompute_runtime_leg_duration_ticks'](
        NativeLine(records, [3300, 3300]), '公交', 313061, waypoint_flags=flags)
    assert value[1] == ticks


@pytest.mark.parametrize('waypoint,ticks', [(False, 9_000_000_000), (True, 6_000_000_000),
                                         (None, 6_000_000_000)])
def test_whole_line_uses_bound_stop_dwell_and_preserves_missing_metadata_behavior(waypoint, ticks):
    helper = runtime_helpers()['recompute_runtime_line_values']
    records = stops(2)
    records[1]['m_stop']['m_prefabObject'] = dict(m_waypoint=waypoint)
    assert helper(NativeLine(records, [1_700_000, 1_700_000]), '公交', 350000)[1] == ticks


@pytest.mark.parametrize('failure', ['unknown_mode', 'missing_method', 'dirty', 'unknown_dirty',
                                    'missing_stop', 'empty_path', 'missing_position',
                                    'missing_dwell_source', 'native_error', 'native_negative'])
def test_incomplete_native_timing_stays_unknown_instead_of_becoming_zero(failure):
    helper = runtime_helpers()['recompute_runtime_leg_duration_ticks']
    records = stops()
    distances = [3300, 6600, 9900, 13200]
    mode = '未知' if failure == 'unknown_mode' else '公交'
    if failure == 'dirty': records[1]['m_pathDirty'] = True
    if failure == 'unknown_dirty': records[1].pop('m_pathDirty')
    if failure == 'missing_stop': records[1]['m_stop'] = None
    if failure == 'empty_path': records[1]['m_path'] = []
    if failure == 'missing_position':
        records[1]['m_path'] = None
        records[1]['m_stop']['m_position'] = None
    if failure == 'missing_dwell_source': records[1]['m_stop'].pop('m_lineCount')
    if failure == 'native_error': distances[1] = ValueError('invalid path')
    if failure == 'native_negative': distances[1] = -1
    result = helper(NativeLine(records, distances, method=failure != 'missing_method'), mode, 313061)
    assert result[1] is None


def test_known_zero_native_distance_and_nonstopping_waypoint_remain_zero():
    helper = runtime_helpers()['recompute_runtime_leg_duration_ticks']
    records = stops(2)
    records[1]['m_stop']['m_lineCount'] = 0
    assert helper(NativeLine(records, [0, 0]), '公交', 313061, stops=records) == (0, 0)


def test_native_no_path_branch_requires_both_positions_and_uses_native_distance():
    helper = runtime_helpers()['recompute_runtime_leg_duration_ticks']
    records = stops(2)
    records[0]['m_path'] = None
    assert helper(NativeLine(records, [3300, 3300]), '公交', 313061)[0] == 5008976
    records[1]['m_stop']['m_position'].pop('z')
    assert helper(NativeLine(records, [3300, 3300]), '公交', 313061)[0] is None


@pytest.mark.parametrize('span', [None, 0, -1, True])
def test_unusable_frame_span_cannot_produce_direction_time(span):
    helper = runtime_helpers()['recompute_runtime_leg_duration_ticks']
    assert helper(NativeLine(stops(2), [3300, 3300]), '公交', span) == (None, None)


@pytest.mark.parametrize('mode', ['公交', '未知'])
def test_whole_line_keeps_existing_minimum_slot_rounding_and_unknown_mode_default(mode):
    helper = runtime_helpers()['recompute_runtime_line_values']
    assert helper(NativeLine(stops(2), [3300, 3300]), mode, 313061) == (6600, 6_000_000_000, 0)
