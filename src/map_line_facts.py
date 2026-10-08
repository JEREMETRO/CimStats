"""Immutable whole-line facts and selected real three-dimensional geometry."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import dist, isfinite
from line_schedule import optional_integer, running_day_mask
from map_service_time import DAY_TICKS, session_line, session_departures
from map_visibility import operating_paths
from display_rules import display_map_km

@dataclass(frozen=True, slots=True)
class LineFacts:
    route_id: int
    approved_duration_ticks: int | None = None
    today_passengers: int | None = None
    scheduled_departures: int | None = None
    simulated_date: date | None = None
    complete: bool = False

@dataclass(frozen=True, slots=True)
class GeometryLengths:
    operating_km: float | None
    deadhead_km: float | None
    total_km: float | None


def _nonnegative(value):
    result = optional_integer(value)
    return result if result is not None and result >= 0 else None


def line_facts(session, route_id) -> LineFacts:
    """Use recomputed full-line duration and native today counter, never halve.

    Count the full simulated calendar day's scheduled rows, including previous
    template-day departures saved beyond midnight. A saved zero stays zero.
    """
    try:
        day = datetime.fromisoformat((session or {})['simulation_time']).date()
    except (KeyError, TypeError, ValueError):
        day = None
    line = session_line(session, route_id)
    raw = line.get('原始字段', {}) if line else {}
    duration = _nonnegative(raw.get('单程时间_tick'))
    passengers = _nonnegative(raw.get('客流_今日'))
    rows = session_departures(line)
    count = 0 if day is not None and rows is not None else None
    if count is not None:
        for row in rows:
            mask = running_day_mask(row.get('运行日掩码', row.get('时刻表_运行日掩码')))
            if mask is not None and not mask & 0x7f:
                continue
            tick = _nonnegative(row.get('发班_tick'))
            if mask is None or tick is None or tick >= 2*DAY_TICKS:
                count = None
                break
            anchor = day - timedelta(days=tick // DAY_TICKS)
            count += bool(mask & (1 << ((anchor.weekday()+1) % 7)))
    return LineFacts(route_id, duration, passengers, count, day,
                     all(v is not None for v in (duration, passengers, count, day)))


def _length(paths, *, empty_unknown=False):
    if not paths:
        return None if empty_unknown else 0.
    total = 0.
    for path in paths:
        if len(path) < 2 or any(len(p) != 3 or not all(isfinite(v) for v in p) for p in path):
            return None
        total += sum(dist(a,b) for a,b in zip(path,path[1:]))
    return total / 1000


def geometry_lengths(route, direction='up', include_deadhead=False) -> GeometryLengths:
    """Displayed operating kilometres plus only real saved depot paths.

    Both/whole show both actual legs; non-roundtrip routes retain full service.
    Apply the information page's shared map scale after measuring geometry.
    This conversion never changes the saved paths or allocates depot travel.
    """
    if direction not in ('up','down','both','whole'):
        raise ValueError('Unknown operating direction')
    operating = display_map_km(_length(operating_paths(route, 'whole' if direction=='both' else direction), empty_unknown=True))
    deadhead = display_map_km(_length(route.depot_paths)) if include_deadhead else 0.
    total = operating+deadhead if operating is not None and deadhead is not None else None
    return GeometryLengths(operating,deadhead,total)
