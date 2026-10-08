"""Pure map display queries; filters never mutate geometry or statistical data."""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections import OrderedDict
from math import isfinite, dist
from types import MappingProxyType
from datetime import datetime, timedelta
from map_model import MapSnapshot, SOCIAL_GROUPS, BuildingFunctionValues, building_function_values
from map_visibility import operating_paths, visible_route_stop_ids
from display_rules import display_map_km
from report_model import display_company
from map_line_labels import resolve_line_labels
from semantic_colors import (SOCIAL, category, canonical_key, color_for,
                             company_palette, line_palette, map_fill, building_function_fill,
                             METRIC_SCALES,metric_color,metric_legend)


@dataclass(frozen=True)
class RouteStats:
    passengers: float | None = None
    profit: float | None = None
    average_interval_minutes: float | None = None
    scheduled_departures: int | None = None
    opened_at: str | None = None
    simulated_date: str | None = None
    passenger_source: str | None = None

    @property
    def profit_status(self):
        return 'missing' if self.profit is None else 'profit' if self.profit > 0 else 'loss' if self.profit < 0 else 'zero'


@dataclass(frozen=True)
class MapResult:
    snapshot: MapSnapshot
    route_colors: object
    building_colors: object
    mileage_km: float
    building_emphasis: bool = False

    @property
    def routes(self):
        return self.snapshot.routes


def optional_number(value):
    try:
        result = float(value)
        return result if isfinite(result) else None
    except (TypeError, ValueError):
        return None


def stats_from_session(session, routes):
    by_id = {};lines={}
    day,source=_passenger_context(session)
    for line in session.get('lines', ()):
        raw = line.get('原始字段', {})
        identity = line.get('对象ID', raw.get('对象ID'))
        try:
            identity = int(identity)
        except (ValueError, TypeError):
            continue
        income, expense = optional_number(raw.get('收入_累计')), optional_number(raw.get('支出_累计'))
        # Match the existing weekly smoothing scale without converting missing to zero.
        by_id[identity] = None if income is None or expense is None else (income-expense)/102400
        lines[identity]=line if identity not in lines else None
    result={}
    for route in routes:
        line=lines.get(route.id)
        schedule=_schedule_for_day(line,day)
        opened=None
        if line is not None and line.get('字段可用性',{}).get('开线日期') is not False:
            original=line.get('原始字段',{}).get('开线日期',line.get('开线日期',''))
            try:opened=datetime.fromisoformat(str(original)).isoformat()
            except (TypeError,ValueError):pass
        result[route.id]=RouteStats(_passenger_value(line,source),
            by_id.get(route.id),schedule['average_interval'] if schedule is not None else None,
            schedule['count'] if schedule is not None else None,opened,day.isoformat() if day else None,source)
    return result


def _passenger_context(session):
    """Save clock selects today from 23:00; an unknown clock selects neither."""
    value=(session or {}).get('simulation_time')
    try:moment=datetime.fromisoformat(value)
    except (TypeError,ValueError):return None,None
    # A date-only ISO value confirms the calendar day, but not its saved clock.
    source=None if len(value.strip())<=10 else 'today' if moment.hour>=23 else 'average'
    return moment.date(),source


def _passenger_value(line,source):
    if line is None or source not in ('today','average'):return None
    key='今日客流' if source=='today' else '平均客流'
    raw_key='客流_今日' if source=='today' else '客流_累计'
    available=line.get('字段可用性',{})
    if available.get(key) is False or available.get(raw_key) is False:return None
    raw=line.get('原始字段',{}).get(raw_key)
    number=optional_number(raw) if not isinstance(raw,bool) else None
    if number is None or number<0:return None
    if source=='today':return number
    # Reuse the existing information-page daily average; never parse its display text.
    value=line.get(key)
    if isinstance(value,bool) or not isinstance(value,(int,float)):return None
    average=optional_number(value)
    return average if average is not None and average>=0 else None


def _schedule_for_day(line,day):
    """Confirm one natural simulated day before using prepare_schedule's minutes."""
    from map_service_time import session_departures,DAY_TICKS
    from line_schedule import optional_integer,running_day_mask,prepare_schedule
    if line is None or day is None or line.get('班次数据完整') is False:return None
    entries=session_departures(line)
    if entries is None:return None
    selected=[]
    for row in entries:
        mask=running_day_mask(row.get('运行日掩码',row.get('时刻表_运行日掩码')))
        if mask is not None and not mask & 0x7f:continue
        tick=optional_integer(row.get('发班_tick'))
        if mask is None or tick is None or tick<0 or tick>=2*DAY_TICKS:return None
        anchor=day-timedelta(days=tick//DAY_TICKS)
        if mask & (1<<((anchor.weekday()+1)%7)):
            selected.append(dict(row,发班_tick=tick%DAY_TICKS))
    prepared=prepare_schedule(selected)
    return prepared if prepared['data_complete'] else None


def _selected(state, key, value):
    selection = state.get(key)
    return selection is None or str(value) in {str(item) for item in selection}


def _function_view(values, view):
    if view not in ('home', 'work', 'leisure'):
        return values
    return BuildingFunctionValues(*(getattr(values, role) if role == view else 0
                                    for role in ('home', 'work', 'leisure')),
                                  values.denominator)


class MapQuery:
    def __init__(self, snapshot, stats=None, *, company_ids=()):
        # Waterbus saves do not expose usable operational route geometry.
        # Exclude only the map feature; retain the original statistics/session.
        self.snapshot = replace(snapshot, routes=tuple(route for route in snapshot.routes
                                if canonical_key('mode',route.mode) != 'waterbus'))
        self.stats = dict(stats or {})
        dates={value.simulated_date for value in self.stats.values() if value.simulated_date}
        self._simulated_date=next(iter(dates)) if len(dates)==1 else ''
        sources={value.passenger_source for value in self.stats.values()}
        self._passenger_source=next(iter(sources)) if len(sources)==1 else None
        self.line_labels = resolve_line_labels(self.snapshot.routes)
        self._company_names = {}
        self.line_colors = line_palette(route.id for route in snapshot.routes)
        self.company_colors = company_palette({str(identity) for identity in company_ids}
                                              | {route.company_id for route in snapshot.routes})
        # Capacity records are immutable for a loaded save. A filter can revisit
        # the same group selection repeatedly while only route styling changes.
        self._building_cache = OrderedDict()
        self._capacity_values = {}
        self._base_options = None
        self._route_geometry = {}
        self._depot_lengths = {}
        self._route_selections = OrderedDict()
        self._stop_selections = OrderedDict()
        self._service_selections = OrderedDict()

    def _services_for(self, state):
        mode = state.get('service_time_mode', 'off')
        if mode == 'off':
            return None
        key = (mode, state.get('service_start'), state.get('service_end') if mode == 'range' else None)
        def evaluate():
            from map_service_time import route_operates
            try:
                if mode not in ('instant', 'range'):
                    raise ValueError('Unknown service time mode')
                start = datetime.fromisoformat(key[1])
                end = datetime.fromisoformat(key[2]) if mode == 'range' else None
                return {route.id: route_operates({}, route.id, start, end, route=route)
                        for route in self.snapshot.routes}
            except (TypeError, ValueError):
                return {route.id: None for route in self.snapshot.routes}
        return self._selection(self._service_selections, key, evaluate)

    @staticmethod
    def _selection(cache, key, make):
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        records = make()
        cache[key] = records
        if len(cache) > 16:
            cache.popitem(last=False)
        return records

    def _geometry_for(self, route, direction):
        key = (route.id, direction)
        geometry = self._route_geometry.get(key)
        if geometry is None:
            paths = operating_paths(route, direction)
            drawable = any(a[0] != b[0] or a[2] != b[2]
                           for path in paths for a, b in zip(path, path[1:]))
            length = sum(dist(a, b) for path in paths for a, b in zip(path, path[1:]))
            geometry = (drawable, length, visible_route_stop_ids(route, direction))
            self._route_geometry[key] = geometry
        return geometry

    def _depot_length(self, route):
        length = self._depot_lengths.get(route.id)
        if length is None:
            length = sum(dist(a, b) for path in route.depot_paths for a, b in zip(path, path[1:]))
            self._depot_lengths[route.id] = length
        return length

    def _buildings_for(self, selected, emphasis, view='combined'):
        groups = None if selected is None else tuple(g for g in SOCIAL_GROUPS if g in selected)
        key = (view, groups, bool(emphasis), None if selected is None else
               frozenset(g for g in selected if g in ('transport', 'special', 'unknown')))
        if key in self._building_cache:
            self._building_cache.move_to_end(key)
            return self._building_cache[key]
        buildings, colors = [], {}
        capacity_colors = {}
        for building in self.snapshot.buildings:
            if building.category in ('transport', 'special'):
                if selected is not None and building.category not in selected:
                    continue
                color = map_fill('usage', building.category, .65 if emphasis else .20)
            else:
                capacities = building.function_capacities
                cached = capacity_colors.get(capacities)
                if cached is None:
                    value_key = (capacities, groups)
                    values = self._capacity_values.get(value_key)
                    if values is None:
                        values = building_function_values(building, groups)
                        self._capacity_values[value_key] = values
                    included = ((selected is None or 'unknown' in selected) if values.denominator is None
                                else selected is None or any(v is not None and v > 0
                                                             for v in (values.home, values.work, values.leisure)))
                    cached = (included, building_function_fill(_function_view(values, view), bool(emphasis)) if included else None)
                    capacity_colors[capacities] = cached
                included, color = cached
                if not included:
                    continue
            buildings.append(building)
            colors[building.id] = color
        result = (tuple(buildings), MappingProxyType(colors))
        self._building_cache[key] = result
        if len(self._building_cache) > 8:
            self._building_cache.popitem(last=False)
        return result

    def route_color(self, route, state):
        mode = state.get('color_by', 'mode')
        if mode in METRIC_SCALES:
            data=self.stats.get(route.id,RouteStats())
            return metric_color(mode,data.average_interval_minutes if mode=='interval' else data.passengers)
        if mode == 'company':
            return self.company_colors[route.company_id]
        if mode == 'profit':
            return color_for('profit', self.stats.get(route.id, RouteStats()).profit_status)
        if mode == 'line':
            return self.line_colors[route.id]
        return color_for('mode', route.mode)

    def select(self, state):
        routes = []
        service_matches = self._services_for(state)
        for route in self.snapshot.routes:
            if service_matches is not None and service_matches[route.id] is not True:
                continue
            data = self.stats.get(route.id, RouteStats())
            if not _selected(state, 'manual_line_ids', route.id):
                continue
            if not _selected(state, 'company_ids', route.company_id):
                continue
            if not _selected(state, 'modes', canonical_key('mode', route.mode)):
                continue
            if not _selected(state, 'profit_statuses', data.profit_status):
                continue
            minimum, maximum = optional_number(state.get('passenger_min')), optional_number(state.get('passenger_max'))
            if (minimum is not None or maximum is not None) and data.passengers is None:
                continue
            if minimum is not None and data.passengers < minimum:
                continue
            if maximum is not None and data.passengers > maximum:
                continue
            routes.append(route)
        priority = state.get('priority_by', 'passengers')
        order = {str(value): index for index, value in enumerate(state.get(
            'mode_order' if priority == 'mode' else 'company_order', ()))}
        def rank(route):
            passenger = self.stats.get(route.id, RouteStats()).passengers
            amount = (passenger if state.get('passenger_desc', True) else -passenger) if passenger is not None else float('-inf')
            group = canonical_key('mode', route.mode) if priority == 'mode' else route.company_id
            top = -order.get(str(group), len(order)) if priority != 'passengers' else 0
            return top, amount, -route.number, -route.id
        routes.sort(key=rank)
        route_ids = tuple(route.id for route in routes)
        routes = self._selection(self._route_selections, route_ids, lambda: tuple(routes))
        emphasis = state.get('building_emphasis')
        direction = state.get('direction', 'whole')
        visible_routes = [route for route in routes if state.get('routes', True)
                          and _selected(state, 'layer_modes', canonical_key('mode', route.mode))]
        if emphasis is None:
            emphasis = not any(self._geometry_for(route, direction)[0] for route in visible_routes)
        buildings, building_colors = self._buildings_for(state.get('building_classes'), emphasis,
                                                        state.get('building_view', 'combined'))
        # Display offsets and colouring never enter distance calculations.
        length = 0.
        visible_stop_ids = set()
        for route in visible_routes:
            _, route_length, route_stops = self._geometry_for(route, direction)
            length += route_length
            if state.get('deadhead', False):
                length += self._depot_length(route)
            visible_stop_ids.update(route_stops)
        stops = self._selection(self._stop_selections, frozenset(visible_stop_ids),
                                lambda: tuple(stop for stop in self.snapshot.stops if stop.id in visible_stop_ids))
        return MapResult(replace(self.snapshot, routes=routes, buildings=buildings, stops=stops),
                         MappingProxyType({route.id: self.route_color(route,state) for route in routes}),
                         building_colors, display_map_km(length/1000.), bool(emphasis))

    def legend_items(self, state, result=None):
        result = result or self.select(state)
        routes = [r for r in result.routes if state.get('routes',True) and _selected(state,'layer_modes',canonical_key('mode',r.mode))]
        if not routes:
            if not state.get('buildings',True):
                return ()
            keys=set()
            selected=state.get('building_classes')
            groups=None if selected is None else [g for g in SOCIAL_GROUPS if g in selected]
            for building in result.snapshot.buildings:
                if building.category in ('transport','special'):
                    keys.add(building.category)
                    continue
                values=_function_view(building_function_values(building,groups),
                                      state.get('building_view', 'combined'))
                if values.denominator is None or values.denominator==0:
                    keys.add('unknown')
                    continue
                if values.home:keys.add('residential')
                if values.work:keys.add('work')
                if values.leisure:keys.add('commercial')
                if values.work and values.leisure:keys.add('mixed')
            return tuple((category('usage',key).name,color_for('usage',key)) for key in
                         ('residential','work','commercial','mixed','transport','special','unknown') if key in keys)
        if state.get('color_by') == 'line':
            return ()
        mode = state.get('color_by','mode')
        if mode in METRIC_SCALES:
            return metric_legend(mode,self._simulated_date,
                                 self._passenger_source if mode=='passengers' else None)
        if mode == 'profit':
            from semantic_colors import PROFIT
            return tuple((item.name,item.color) for item in PROFIT)
        if mode == 'company':
            names = {r.company_id:display_company(self._company_names.get(str(r.company_id),r.company_name)) for r in routes}
            return tuple((name,self.company_colors[key]) for key,name in sorted(names.items()))
        modes = sorted({canonical_key('mode',r.mode) for r in routes})
        return tuple((category('mode',key).name,color_for('mode',key)) for key in modes)

    def panel_options(self, session=None, state=None, result=None):
        state = state or {}
        if session is not None:
            names = {str(company['公司标识']):display_company(company.get('公司名称',''))
                     for company in session.get('companies',())
                     if company.get('公司标识') is not None}
            if names != self._company_names:
                self._company_names = names
                self.line_labels = resolve_line_labels(self.snapshot.routes, company_names=names)
        if self._base_options is None:
            modes = sorted({canonical_key('mode', route.mode) for route in self.snapshot.routes})
            companies = {route.company_id: display_company(route.company_name) for route in self.snapshot.routes}
            present_groups = {entry.group for b in self.snapshot.buildings
                              for entry in b.function_capacities
                              if any(v is not None and v>0 for v in (entry.home,entry.work,entry.leisure))}
            known_order = [entry.key for entry in SOCIAL]
            groups = [key for key in known_order if key in present_groups]
            groups += sorted(present_groups - set(known_order) - {'unknown'})
            groups += ['transport', 'special', 'unknown']
            def entries(domain, keys):
                return [{'id': key, 'name': category(domain,key).name, 'color': color_for(domain,key)} for key in keys]
            self._base_options = {
                'modes': entries('mode', modes),
                'companies': [{'id': key, 'name': name, 'color': self.company_colors[key]}
                              for key,name in sorted(companies.items())],
                'building_classes': [dict(id=key, name=category('usage' if key in ('transport','special','unknown') else 'social',key).name,
                                          color=color_for('usage' if key in ('transport','special','unknown') else 'social',key))
                                     for key in dict.fromkeys(groups)],
                'building_uses': entries('usage', sorted({b.category for b in self.snapshot.buildings})),
            }
        if session is not None:
            day,self._passenger_source=_passenger_context(session)
            self._simulated_date=day.isoformat() if day else ''
        date=self._simulated_date
        # Callers populate mutable controls; keep each response independent.
        base = {key: [dict(item) for item in entries] for key, entries in self._base_options.items()}
        for company in base['companies']:
            company['name'] = self._company_names.get(str(company['id']),company['name'])
        service_matches = self._services_for(state)
        return {**base,
                'simulated_datetime': (session or {}).get('simulation_time'),
                'building_emphasis_effective': (result or self.select(state)).building_emphasis,
                'lines': [{'id':route.id,'name':route.name,'display_label':self.line_labels[route.id],
                           'number':route.number,'mode':canonical_key('mode',route.mode),
                           'company_id':route.company_id,
                           'company_name':display_company(self._company_names.get(str(route.company_id),route.company_name)),
                           'passengers':self.stats.get(route.id,RouteStats()).passengers,
                           'opened_at':self.stats.get(route.id,RouteStats()).opened_at,
                           'scheduled_departures':self.stats.get(route.id,RouteStats()).scheduled_departures,
                           'profit':self.stats.get(route.id,RouteStats()).profit_status,
                           'service_matches': True if service_matches is None else service_matches[route.id],
                           'color':self.route_color(route,state)} for route in self.snapshot.routes],
                'passenger_date':date,'passenger_source':self._passenger_source,
                'passenger_label':{'today':'今日客流','average':'平均客流'}.get(self._passenger_source,'客流')}
