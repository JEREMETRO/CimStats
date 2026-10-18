"""Native calendar filtering and the saved query's operating-time summary.

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


_QUERY_DAYS = {'周一至周四': (1,2,3,4), '周一': (1,), '周二': (2,),
               '周三': (3,), '周四': (4,), '周五': (5,), '周六': (6,), '周日': (0,)}


def _group_operating_times(values):
    """Merge equal summaries while retaining complete weekday ranges."""
    if len(set(values)) == 1:
        return values[0]
    groups = {}
    for day in (1,2,3,4,5,6,0):
        groups.setdefault(values[day], []).append(day)
    weekdays = ('周日','周一','周二','周三','周四','周五','周六')
    def label(days):
        if days == [1,2,3,4,5]:return '工作日'
        if days == [6,0]:return '周末'
        runs = []
        for day in days:
            if runs and (runs[-1][-1]+1) % 7 == day:
                runs[-1].append(day)
            else:runs.append([day])
        return '、'.join(weekdays[run[0]] if len(run)==1 else
                        weekdays[run[0]]+'至'+weekdays[run[-1]] for run in runs)
    return '，'.join(label(days)+value for value,days in groups.items())


def _saved_query_operating_time(line):
    """Read the same prepared segments consumed by SchedulePanel.set_line.

    None means this is a legacy report without prepared query groups. A
    present but incomplete query remains unknown; never replace it with
    independently calculated native-template endpoints.
    """
    schedules = (line or {}).get('时刻表')
    if not isinstance(schedules, dict) or not any(day in schedules for day in _QUERY_DAYS):
        return None
    if line.get('运行日未知班次'):
        return '—'
    values = [None]*7
    for group in line.get('日组', schedules):
        if group not in _QUERY_DAYS:continue
        schedule = schedules.get(group)
        if not isinstance(schedule, dict) or schedule.get('data_complete') is not True:
            return '—'
        segments = schedule.get('segments')
        if not isinstance(segments, (list,tuple)):
            return '—'
        if any(not isinstance(segment, dict) or not segment.get('text') for segment in segments):
            return '—'
        value = '、'.join(segment['text'].replace('–','-') for segment in segments)
        if not value:
            if schedule.get('count') != 0:return '—'
            value = '停运'
        for day in _QUERY_DAYS[group]:values[day] = value
    return '—' if any(value is None for value in values) else _group_operating_times(values)


def operating_time_text(session, route_id, *, route=None):
    """Use the saved query summary, including its circular service segments.

    Native metadata is a compatibility fallback for reports lacking prepared
    query groups. Current exports reuse the query's already stored result.
    """
    if route is not None and route.id != route_id:
        return '—'
    saved = _saved_query_operating_time(session_line(session, route_id))
    if saved is not None:
        return saved
    service = route.service if route is not None else service_from_session(session, route_id)
    # Old map snapshots may lack native service entirely; the shared legacy
    # reader can recover it only when the session retained complete metadata.
    if service == RouteService():
        service = service_from_session(session, route_id)
    if service.active is False or service.complete is False:
        return '停运'
    if service.timetables is None:
        return '—'
    windows = [[] for _ in range(7)]  # Sunday is native bit zero.
    for table in service.timetables:
        mask = running_day_mask(table.active_days)
        if mask is not None and not mask & 0x7f:
            continue
        rows = table.departure_ticks
        if rows == ():
            continue
        if (mask is None or rows is None or
                any(optional_integer(t) is None or not 0 <= t < 2*DAY_TICKS for t in rows)):
            return '—'
        first,last = min(rows),max(rows)
        if last-first >= DAY_TICKS:
            return '—'
        for day in range(7):
            if mask & (1 << day):
                windows[day].append((first,last))
    if not any(windows):
        return '停运'
    if service.active is None or service.complete is None:
        return '—'

    def clock(tick):
        day,remainder = divmod(tick,DAY_TICKS)
        minutes = remainder // 600_000_000
        return ('次日' if day else '')+f'{minutes//60:02d}:{minutes%60:02d}'

    def text(spans):
        merged=[]
        for start,end in sorted(spans):
            if merged and start <= merged[-1][1]:
                merged[-1]=(merged[-1][0],max(merged[-1][1],end))
            else:
                merged.append((start,end))
        return '、'.join(f'{clock(a)}-{clock(b)}' for a,b in merged) or '停运'

    values=tuple(text(spans) for spans in windows)
    return _group_operating_times(values)
