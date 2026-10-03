"""Qt-free latest-information snapshot over normalized save-local observations.

Operating cards use normalized line durations, planned departures and fleet counts.
Historical cards and the hourly trend use HistoryData, not line snapshot totals.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import PureWindowsPath

from city_model import build_city_snapshot
from company_labels import company_selection_name
from dashboard_model import FilterState
from display_rules import display_mode
from map_name_source import resolve_session_map_name
from network_model import _aggregate_result, _quantity_trend
from statistics_model import METRICS, HistoryStore, Query, QueryCancelled, Result, parse_time

Number = Decimal | float | int | None


@dataclass(frozen=True)
class InfoValue:
    key: str
    title: str
    value: Number
    unit: str = ''
    scope: str = ''
    reason: str = ''
    complete: bool = True


@dataclass(frozen=True)
class LineSummary:
    key: str
    name: str
    mode: str
    company_id: str
    passengers: Number
    departures: Number
    passengers_per_departure: Number
    passengers_per_vehicle_km: Number


@dataclass(frozen=True)
class LineHighlight:
    title: str
    line: LineSummary | None


@dataclass(frozen=True)
class ModeCount:
    mode: str
    value: Number


@dataclass(frozen=True)
class LatestInfoSnapshot:
    session_key: str
    company_id: str
    mode: str
    city_name: str
    simulation_time: datetime | None
    population: Number
    save_name: str
    companies: tuple[tuple[str, str], ...]
    modes: tuple[str, ...]
    metrics: tuple[InfoValue, ...]
    highlights: tuple[LineHighlight, ...]
    lines: tuple[LineSummary, ...]
    passenger_top10: tuple[LineSummary, ...]
    passenger_modes: tuple[ModeCount, ...]
    departure_modes: tuple[ModeCount, ...]
    total_departures: Number
    trend: Result | None
    scope_text: str
    city_source: str = ''
    city_raw_reference: str = ''
    city_raw_name: str = ''
    city_internal_id: str = ''
    city_name_reason: str = ''
    company_trend: Result | None = None


def _check(cancelled):
    if cancelled and cancelled():
        raise QueryCancelled()


def _number(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _sum(values):
    values = list(values)
    return sum(values, Decimal(0)) if values and all(v is not None for v in values) else None


def _ratio(numerator, denominator):
    return numerator / denominator if numerator is not None and denominator is not None and denominator > 0 else None


def _measurement(row, field):
    if (row.get('字段可用性') or {}).get(field) is False:
        return None
    return _number(row.get(field))


def _vehicle_km(row):
    departures, distance = _number(row.get('当日发班数')), _measurement(row, '地图里程')
    return departures * distance if departures is not None and distance is not None else None


def _planned_speed(rows, cancelled):
    """Weight distance and duration by the same valid planned departures."""
    distance_total = minutes_total = Decimal(0)
    exclusions = {}
    for row in rows:
        _check(cancelled)
        departures = _number(row.get('当日发班数'))
        if departures == 0:
            continue
        distance = _measurement(row, '地图里程')
        duration = _measurement(row, '单程时间')
        if departures is None or departures < 0:
            problem = '计划班次数缺失' if departures is None else '计划班次数为负值'
        elif distance is None or distance < 0:
            problem = '地图里程缺失' if distance is None else '地图里程为负值'
        elif duration is None or duration <= 0:
            problem = '核定周转时间缺失' if duration is None else '核定周转时间不大于零'
        else:
            distance_total += departures * distance
            minutes_total += departures * duration
            continue
        exclusions[problem] = exclusions.get(problem, 0) + 1
    value = _ratio(distance_total, minutes_total)
    reason = ''.join(f'；{count}条线路{problem}，未计入里程和时间' for problem, count in exclusions.items())
    if value is None and not exclusions:
        reason += '；所选线路没有正数计划班次' if rows else '；未选中线路'
    return value * 60 if value is not None else None, not exclusions, reason


def _planned_minutes(row):
    departures = _number(row.get('当日发班数'))
    if departures is None or departures < 0:
        return None
    if departures == 0:
        return Decimal(0)
    duration = _measurement(row, '单程时间')
    return departures * duration if duration is not None and duration > 0 else None


def _missing_operation_reason(key, rows, fleet, passenger, departures, vehicle_km, income, expense):
    if key == 'fleet':
        return '车队车辆数量缺失'
    if not rows:
        return '未选中线路'
    if key == 'drive-minutes':
        if any(_number(r.get('当日发班数')) is None for r in rows):
            return '当日计划班次数缺失'
        if any(_number(r.get('当日发班数')) < 0 for r in rows):
            return '当日计划班次数为负值'
        return '线路核定周转时间缺失' if any(_measurement(r, '单程时间') is None for r in rows) else '线路核定周转时间不大于零'
    if key in ('weekly-income', 'weekly-expense', 'profit'):
        fields = {'weekly-income': [('周收入', income)], 'weekly-expense': [('周支出', expense)],
                  'profit': [('周收入', income), ('周支出', expense)]}
        return '、'.join(f'{name}缺失' for name, value in fields[key] if value is None)
    if key == 'interval':
        return '所选线路已启用且运行日已知的日组内没有有效相邻班次'
    if key == 'turnover' and (fleet is None or fleet <= 0):
        return '车队车辆数量缺失' if fleet is None else '车队车辆数量不大于零'
    if key in ('passengers-per-run', 'passengers-per-km') and passenger is None:
        return '当日累计客流缺失'
    if departures is None:
        return '当日计划班次数缺失'
    if key == 'passengers-per-km':
        return '地图里程缺失' if vehicle_km is None else '当日计划行驶总里程不大于零'
    return '当日计划班次数不大于零'


def _owner(row, companies):
    """Legacy names are usable only when they identify exactly one company."""
    explicit = str(row.get('公司标识') or row.get('玩家ID') or '')
    if explicit:
        return explicit
    name = str(row.get('公司名称') or '')
    matching = [identity for identity, title in companies if name and title == name]
    return matching[0] if len(matching) == 1 else ''


def _simulation_time(data):
    metadata = data.get('metadata') or {}
    candidate = data.get('simulation_time')
    if not candidate and metadata.get('当前日期'):
        candidate = f"{metadata['当前日期']} {metadata.get('当前时间') or '00:00:00'}"
    try:
        return parse_time(candidate) if candidate else None
    except (ValueError, TypeError):
        return None


def _interval(rows, cancelled):
    intervals = []
    for row in rows:
        _check(cancelled)
        for group, entries in (row.get('班次') or {}).items():
            if group in ('未启用', '运行日未知'):
                continue
            times = []
            for entry in entries:
                try:
                    hour, minute = map(int, str(entry.get('time', '')).split(':', 1))
                    if 0 <= hour < 24 and 0 <= minute < 60:
                        times.append(hour * 60 + minute)
                except (TypeError, ValueError):
                    continue
            times.sort()
            intervals.extend(Decimal(b - a) for a, b in zip(times, times[1:]) if b > a)
    return _ratio(_sum(intervals), Decimal(len(intervals)))


def _history(data, now, companies, cancelled):
    normalized = []
    for row in data.get('history') or []:
        _check(cancelled)
        copy = dict(row)
        if row.get('指标') == 'transport-by-type':
            copy['分组'] = display_mode(row.get('分组', ''))
        # Do not allow an ambiguous display name to enter a company query.
        if row.get('公司标识') or row.get('玩家ID') or row.get('公司名称'):
            copy['公司标识'] = _owner(row, companies) or '__unresolved__'
        normalized.append(copy)
    return HistoryStore(normalized, now)


def _transfer_value(store, ids, start, end, cancelled):
    """Sum safe paired hours per company, never partial-category daily totals."""
    source = store.query(Query('transfer-coefficient', ids, '__total__', start, end, 'hour'), cancelled)
    numerator = denominator = 0
    complete = True
    missing_company = False
    excluded = 0
    problems = set()
    for company in ids:
        _check(cancelled)
        categories = {metric: {group for name, owner, group in store.series
                               if name == metric and owner == company}
                      for metric in ('transport-by-type', 'trip-types')}
        buckets = source.series.get((company, '总计'), [])
        hours = 0
        for bucket in buckets:
            _check(cancelled)
            # HistoryStore pairs observation times. Additionally verify each
            # metric's whole serialized category set at every observed instant.
            valid = (bucket.value is not None and bucket.numerator is not None and
                     bucket.numerator >= 0 and bucket.denominator is not None and bucket.denominator > 0)
            for metric, expected in categories.items():
                by_time = {}
                for row in bucket.raw:
                    if row.metric == metric:
                        by_time.setdefault(row.time, set()).add(row.group)
                if not expected or not by_time or any(groups != expected for groups in by_time.values()):
                    valid = False
                    problems.add('客流类别不完整' if metric == 'transport-by-type' else '分区出行类别不完整')
            if valid:
                numerator += bucket.numerator
                denominator += bucket.denominator
                hours += 1
            elif bucket.raw:
                excluded += 1
                if bucket.denominator is not None and bucket.denominator <= 0:
                    problems.add('分区出行量不大于零')
                if bucket.numerator is not None and bucket.numerator < 0:
                    problems.add('客流为负值')
                if bucket.numerator is None or bucket.denominator is None:
                    problems.add('客流与分区出行量缺少同期配对观测')
            else:
                problems.add('部分时段没有观测')
            if valid and not bucket.complete:
                problems.add('有效小时观测尚未完整')
            complete = complete and valid and bucket.complete
        if not hours:
            missing_company = True
            complete = False
    value = None if missing_company else _ratio(Decimal(numerator), Decimal(denominator))
    reason = ('；仅累计客流与出行量类别完整且同期配对的有效小时'
              f'；排除{excluded}个观测小时') if excluded else ''
    if problems:
        reason += '；' + '；'.join(sorted(problems))
    if missing_company:
        reason += '；有公司没有客流与出行量类别完整且同期配对的有效小时，换乘系数不可计算'
    return value, complete and value is not None, reason


def build_latest_info(data: dict, company_id: str = '', mode: str = '综合', *, cancelled=None) -> LatestInfoSnapshot:
    _check(cancelled)
    company_id, mode = str(company_id or ''), display_mode(mode or '综合')
    source_companies = data.get('companies') or []
    companies = tuple((str(c.get('公司标识') or c.get('玩家ID') or f'company-index:{index}'),
                       str(c.get('公司名称') or '未命名公司')) for index, c in enumerate(source_companies))
    ids = (company_id,) if company_id else tuple(identity for identity, _ in companies)
    scoped_companies = [c for c, (identity, _) in zip(source_companies, companies) if identity in ids]
    all_rows = data.get('lines') or []
    rows = []
    for row in all_rows:
        _check(cancelled)
        if _owner(row, companies) in ids and (mode == '综合' or display_mode(row.get('运输制式')) == mode):
            rows.append(row)
    company_scope = company_selection_name(companies, ids)
    line_scope = f'公司：{company_scope}    {mode}'
    now = _simulation_time(data)
    metadata = data.get('metadata') or {}
    city_info = resolve_session_map_name(data)
    store = _history(data, now, companies, cancelled) if now else None

    present_modes = dict.fromkeys(display_mode(r.get('运输制式')) for r in all_rows if r.get('运输制式'))
    for company in source_companies:
        for name, count in (company.get('车队') or {}).items():
            if _number(count) is not None and _number(count) > 0:
                present_modes[display_mode(name)] = None
        for name in company.get('非零制式') or []:
            present_modes[display_mode(name)] = None
    if store:
        for metric, _, group in store.series:
            if metric == 'transport-by-type' and group:
                present_modes[group] = None
    present_modes.pop('综合', None)
    modes = ('综合', *present_modes)

    summaries = tuple(LineSummary(str(r.get('key') or ''), str(r.get('线路名称') or ''),
        display_mode(r.get('运输制式')), _owner(r, companies), _number(r.get('今日客流')),
        _number(r.get('当日发班数')), _ratio(_number(r.get('今日客流')), _number(r.get('当日发班数'))),
        _ratio(_number(r.get('今日客流')), _vehicle_km(r))) for r in rows)
    passenger = _sum(s.passengers for s in summaries)
    departures = _sum(s.departures for s in summaries)
    minutes = _sum(_planned_minutes(r) for r in rows)
    vehicle_km = _sum(_vehicle_km(r) for r in rows)
    fleet = _sum(_number(c.get('车辆总数')) if mode == '综合' else
                 _number((c.get('车队') or {}).get(mode)) for c in scoped_companies)
    income = _sum(_number(r.get('每周收入')) for r in rows)
    expense = _sum(_number(r.get('每周支出')) for r in rows)
    speed, speed_complete, speed_reason = _planned_speed(rows, cancelled)
    values = (len(rows), fleet, minutes, _ratio(departures, fleet), income, expense,
              income - expense if income is not None and expense is not None else None,
              _interval(rows, cancelled), speed,
              _ratio(passenger, departures), _ratio(passenger, vehicle_km))
    definitions = (
        ('line-count', '线路总数', '条', '所选线路的数量'),
        ('fleet', '车辆总数', '辆', '所选车队的车辆总数' if mode == '综合' else '所选车队该制式的车辆数量'),
        ('drive-minutes', '行车总时间', '分钟', '所选线路当日计划班次的核定周转时间之和'),
        ('turnover', '车辆周转率', '班/辆/天', '当日计划发班总数与车队车辆总数之比，反映平均每辆车每天的计划运行班次数'),
        ('weekly-income', '每周收入', '货币', '所选线路的周收入'),
        ('weekly-expense', '每周支出', '货币', '所选线路的周支出'),
        ('profit', '周利润', '货币', '所选线路的周利润'),
        ('interval', '平均间隔', '分钟', '所选线路运营时间内的平均间隔'),
        ('speed', '平均核定速度', 'km/h', '所选线路的总运营里程数与计划班次总核定时间之比'),
        ('passengers-per-run', '平均单班人次', '人次/班', '当日累计客流与当日计划发班总数之比'),
        ('passengers-per-km', '平均车公里人次', '人次/车公里', '当日累计客流与当日计划行驶总里程之比，反映线路车辆运营的乘客周转率，进而反映线路效益'),
    )
    schedule_complete = all(r.get('班次数据完整', True) and not r.get('运行日未知班次') for r in rows)
    metrics = []
    for value, (key, title, unit, reason) in zip(values, definitions):
        _check(cancelled)
        complete = value is not None
        if key == 'speed':
            complete = complete and speed_complete
            reason += speed_reason
        if key in ('drive-minutes', 'turnover', 'speed', 'passengers-per-run', 'passengers-per-km') and not schedule_complete:
            complete = False
            if any(r.get('运行日未知班次') for r in rows):
                reason += '；部分班次运行日未知，仅含已确认班次'
            if any(not r.get('班次数据完整', True) for r in rows):
                reason += '；班次数据不完整'
        if value is None and key != 'speed':
            reason += '；' + _missing_operation_reason(key, rows, fleet, passenger, departures, vehicle_km, income, expense)
        metrics.append(InfoValue(key, title, value, unit, line_scope, reason, complete))

    trend = company_trend = None
    share = coefficient = None
    share_complete = coefficient_complete = False
    day_scope = f"模拟当日 {now:%Y-%m-%d} 00:00 至 {now:%H:%M:%S}" if now else '缺少模拟时间'
    share_reason = '全市公共交通有效历史计数 ÷ 对应历史总体计数 × 100；缺小时不补零，当前小时可能为部分观测'
    coefficient_reason = '所选公司当日总客流与总分区出行量之比，即平均每位乘客单次行程的乘车次数'
    if mode != '综合':
        coefficient_reason += '；历史分区出行量缺少对应制式分母，保持所选公司全部制式范围，不随制式筛选'
    population = _number(metadata.get('当前人口数'))
    if now and now > now.replace(hour=0, minute=0, second=0, microsecond=0):
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        filters = FilterState(ids, start, now, 'hour')
        city = build_city_snapshot(store, filters, cancelled, _comparisons=False)
        city_share = next(d for d in city.kpis['city-mode-share'].details if d.title == '公共交通')
        share, share_complete = city_share.value, city_share.complete
        if population is None:
            population = city.kpis['population'].value
        if ids:
            source = store.query(Query('transport-by-type', ids, None if mode == '综合' else mode,
                                       start, now, 'hour'), cancelled)
            if mode == '综合':
                # Keep a gap when one of a company's serialized categories is
                # missing instead of presenting a partial category sum as total.
                source = _quantity_trend(source, ids, False)
            company_trend = source
            trend = _aggregate_result(source, ids, False, cancelled)
            # Category-safe count pairs are accumulated for each company first;
            # companies need not have identical valid observation hours.
            coefficient, coefficient_complete, pairing_reason = _transfer_value(store, ids, start, now, cancelled)
            coefficient_reason += pairing_reason
    if share is None:
        share_reason += '；缺少模拟时间' if now is None else ('；模拟当日尚无观测时段' if now == now.replace(hour=0, minute=0, second=0, microsecond=0) else '；当日公共交通占比观测不足，无法计算')
    if coefficient is None:
        if now is None:
            coefficient_reason += '；缺少模拟时间'
        elif now == now.replace(hour=0, minute=0, second=0, microsecond=0):
            coefficient_reason += '；模拟当日尚无观测时段'
    metrics.extend((InfoValue('public-transport-share', '公共交通分担率', share, '%',
                             f'全市 · {day_scope}', share_reason, share_complete),
                    InfoValue('transfer-coefficient', METRICS['transfer-coefficient'].label, coefficient, '倍',
                              f'公司：{company_scope}    全部制式    {day_scope}',
                              coefficient_reason, coefficient_complete)))
    def highlight(title, field, maximum):
        valid = [s for s in summaries if getattr(s, field) is not None]
        selected = (max if maximum else min)(valid, key=lambda s: getattr(s, field), default=None)
        return LineHighlight(title, selected)
    highlights = (highlight('当日最大客流线路', 'passengers', True),
                  highlight('当日最小客流线路', 'passengers', False),
                  highlight('当日最多班次线路', 'departures', True),
                  highlight('当日最少班次线路', 'departures', False))
    top = tuple(sorted((s for s in summaries if s.passengers is not None), key=lambda s: s.passengers, reverse=True)[:10])
    line_modes = tuple(dict.fromkeys(s.mode for s in summaries))
    passenger_modes = tuple(ModeCount(m, _sum(s.passengers for s in summaries if s.mode == m)) for m in line_modes)
    departure_modes = tuple(ModeCount(m, _sum(s.departures for s in summaries if s.mode == m)) for m in line_modes)
    save_path = str(data.get('save_path') or '').strip()
    save_name = (PureWindowsPath(save_path).name if save_path else '') or str(data.get('save_name') or '').strip()
    _check(cancelled)
    return LatestInfoSnapshot(str(data.get('save_key') or data.get('session_key') or ''), company_id, mode,
        city_info.display_name, now, population,
        save_name or '未提供存档名称', companies, modes, tuple(metrics), highlights,
        summaries, top, passenger_modes, departure_modes, departures, trend,
        f'{line_scope}；线路今日客流与全日计划班次来自存档快照；历史趋势与新增指标：{day_scope}；公共交通分担率保持全市范围',
        city_source=city_info.source, city_raw_reference=city_info.raw_reference,
        city_raw_name=city_info.raw_map_name, city_internal_id=city_info.internal_id,
        city_name_reason=city_info.reason, company_trend=company_trend)
