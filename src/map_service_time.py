"""Native timetable calendar queries, independent of display heuristics.

Day bit 0 is Sunday. Serialized departure ticks stay unfolded across midnight;
their running-day mask belongs to the template's starting calendar day.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from map_model import RouteService, ServiceTimetable
from line_schedule import optional_integer, running_day_mask

DAY_TICKS = 864_000_000_000


def session_line(session, route_id):
    matches = [line for line in (session or {}).get('lines', ())
               if optional_integer(line.get('对象ID', line.get('原始字段', {}).get('对象ID'))) == route_id]
    return matches[0] if len(matches) == 1 else None


def session_departures(line):
    """Original rows once by native table/row identity, never by clock value."""
    if line is None or '时刻表' not in line:
        return None
    entries = []; seen = set()
    schedules = line.get('时刻表')
    if not isinstance(schedules, dict):
        return None
    for schedule in schedules.values():
        for row in schedule.get('entries', ()):
            key = (row.get('时刻表序号'), row.get('发班序号'))
            if None not in key and '' not in key:
                if key in seen:
                    continue
                seen.add(key)
            entries.append(row)
    for row in line.get('运行日未知班次', ()):
        key = (row.get('时刻表序号'), row.get('发班序号'))
        if None not in key and '' not in key:
            if key in seen:
                continue
            seen.add(key)
        entries.append(row)
    # A missing export must not masquerade as zero scheduled rows.
    raw = line.get('原始字段', {})
    if not entries and optional_integer(raw.get('时刻表数')) not in (None, 0):
        return None
    return entries


def _native_bool(value):
    if value is True or value is False:
        return value
    return None


def service_from_session(session, route_id):
    """Compatibility only: join original template metadata retained on rows.

    Legacy reports omit active/complete flags and empty templates. Such a
    report can supply scheduled counts but cannot prove operating service.
    The route's native RouteService is the preferred source for filtering.
    """
    line = session_line(session, route_id)
    if line is None:
        return RouteService()
    raw = line.get('原始字段', {})
    active = _native_bool(raw.get('m_active'))
    complete = _native_bool(raw.get('m_complete'))
    entries = session_departures(line)
    if entries is None:
        return RouteService(active, complete)
    tables = {}
    for row in entries:
        key = row.get('时刻表序号')
        template = row.get('时刻表原始字段')
        if key is None or not template:
            return RouteService(active, complete)
        if key not in tables:
            tables[key] = [template, []]
        tables[key][1].append(optional_integer(row.get('发班_tick')))
    return RouteService(active, complete, tuple(ServiceTimetable(
        running_day_mask(template.get('运行日掩码')),
        optional_integer(template.get('开始_tick')), optional_integer(template.get('结束_tick')),
        optional_integer(template.get('间隔_tick')), tuple(rows)) for template, rows in tables.values()))


def _query_tick(value):
    midnight = value.replace(hour=0, minute=0, second=0, microsecond=0)
    delta = value - midnight
    return (value.date().toordinal()-1)*DAY_TICKS + delta.seconds*10_000_000 + delta.microseconds*10


def _table_operates(table, start, end):
    mask = running_day_mask(table.active_days)
    if mask is not None and not mask & 0x7f:
        return False
    rows = table.departure_ticks
    if rows is None:
        return None
    if not rows:
        return False
    if mask is None or any(optional_integer(t) is None or not 0 <= t < 2*DAY_TICKS for t in rows):
        return None
    # Each native template is one continuous window. Do not join templates
    # across shutdown gaps or infer gaps from a presentation threshold.
    first, last = min(rows), max(rows)
    if last - first >= DAY_TICKS:
        return None
    lower = _query_tick(start)
    upper = _query_tick(end) if end is not None else None
    # Native rows span at most today/next day. A weekly pattern needs at most
    # nine anchors even when a caller requests a very long simulated range.
    anchor = start.date().toordinal()-2
    final = min((end or start).date().toordinal()-1, anchor+8)
    for ordinal in range(max(0, anchor), final+1):
        day = datetime.fromordinal(ordinal+1)
        if not mask & (1 << ((day.weekday()+1) % 7)):
            continue
        a, b = ordinal*DAY_TICKS+first, ordinal*DAY_TICKS+last
        if upper is None:
            if a <= lower <= b:
                return True
        elif (a < upper and b > lower) or lower <= b < upper:
            return True
    return False


def route_operates(session, route_id, start: datetime, end: datetime | None = None, *, route=None) -> bool | None:
    """Any actual window intersects [start,end); None end is an instant.

    A terminal departure is included at its exact instant, with no extension
    for an in-flight vehicle. Missing flags/templates/rows remain unknown.
    """
    if not isinstance(start, datetime) or (end is not None and not isinstance(end, datetime)):
        raise ValueError('Service query requires simulated datetimes')
    if start.tzinfo is not None or (end is not None and end.tzinfo is not None):
        raise ValueError('Simulated datetimes must be timezone-naive')
    if end is not None and end <= start:
        raise ValueError('Service range must have end after start')
    if route is not None and route.id != route_id:
        return None
    service = route.service if route is not None else service_from_session(session, route_id)
    if service.active is False or service.complete is False:
        return False
    if service.timetables is None:
        return None
    results = [_table_operates(t, start, end) for t in service.timetables]
    if all(r is False for r in results):
        return False
    if service.active is None or service.complete is None:
        return None
    return True if any(r is True for r in results) else None
