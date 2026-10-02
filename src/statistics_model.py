"""Audited, save-local queries over the game's hourly HistoryData observations."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from calendar import monthrange
from collections import defaultdict


HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class Metric:
    label: str
    scope: str  # city or company
    kind: str  # flow, stock, average, ratio_flow, ratio_stock
    unit: str
    scale: int = 1
    confirmed: bool = True


METRICS = {
    'cashflow': Metric('现金流', 'company', 'flow', '货币', 100),
    'company-value': Metric('公司价值', 'company', 'stock', '货币'),
    'monthly-ticket': Metric('月票使用率', 'company', 'ratio_flow', '%'),
    'satisfaction-speed': Metric('速度满意度', 'company', 'ratio_flow', '评分'),
    'satisfaction-cost': Metric('费用满意度', 'company', 'ratio_flow', '评分'),
    'satisfaction-quality': Metric('质量满意度', 'company', 'ratio_flow', '评分'),
    'reputation': Metric('声誉', 'company', 'ratio_stock', '%'),
    'popularity': Metric('受欢迎程度', 'company', 'ratio_flow', '%'),
    'linecount': Metric('线路数', 'company', 'stock', '条'),
    'stopcount': Metric('站点数', 'company', 'stock', '个'),
    'depotcount': Metric('车库数', 'company', 'stock', '个'),
    'vehicles-running': Metric('平均运行车辆数', 'company', 'average', '辆', 1024),
    'coverage': Metric('覆盖率', 'company', 'ratio_flow', '%'),
    'transport-by-group': Metric('分群体客流', 'company', 'flow', '人次'),
    'transport-by-type': Metric('分制式客流', 'company', 'flow', '人次'),
    'trip-types': Metric('票制／覆盖区数行程', 'company', 'flow', '人次'),
    'transfer-coefficient': Metric('平均换乘系数', 'company', 'coefficient', '倍'),
    'population': Metric('人口', 'city', 'stock', '人'),
    'economy': Metric('经济增长／利率', 'city', 'ratio_stock', '%'),
    'energy-prices': Metric('能源价格（游戏原始值）', 'city', 'stock', '原始值', confirmed=False),
    'public-transport': Metric('公共交通方式占比', 'city', 'ratio_flow', '%'),
    'private-motoring': Metric('私家车方式占比', 'city', 'ratio_flow', '%'),
    'walking': Metric('步行方式占比', 'city', 'ratio_flow', '%'),
    'city-mode-share': Metric('出行方式占比（三方式）', 'city', 'ratio_flow', '%'),
    'trip-number': Metric('出行量', 'city', 'flow', '人次'),
    'traffic-density': Metric('交通密度', 'city', 'ratio_flow', '%'),
}

BOARDS = {
    '公司数据': ('cashflow', 'company-value', 'monthly-ticket', 'satisfaction-speed',
             'satisfaction-cost', 'satisfaction-quality', 'reputation', 'popularity'),
    '服务规模': ('linecount', 'stopcount', 'depotcount', 'vehicles-running', 'coverage'),
    '客流数据': ('transport-by-group', 'transport-by-type', 'trip-types', 'transfer-coefficient'),
    '城市数据': ('population', 'economy', 'energy-prices', 'city-mode-share', 'public-transport',
             'private-motoring', 'walking', 'trip-number', 'traffic-density'),
}

NO_GROUP_TOTAL = frozenset({'economy', 'energy-prices', 'traffic-density', 'stopcount'})


def parse_time(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace(' ', 'T'))


def period_bounds(time: datetime, grain: str) -> tuple[datetime, datetime]:
    hour = time.replace(minute=0, second=0, microsecond=0)
    day = hour.replace(hour=0)
    if grain == 'hour':
        return hour, hour + HOUR
    if grain == 'day':
        return day, day + timedelta(days=1)
    if grain == 'week':
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=7)
    if grain == 'month':
        start = day.replace(day=1)
        end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        return start, end
    raise ValueError(grain)


def shift_month(value: datetime, count: int) -> datetime:
    serial = value.year * 12 + value.month - 1 + count
    year, month0 = divmod(serial, 12)
    month = month0 + 1
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def compare_window(start: datetime, end: datetime, mode: str) -> tuple[datetime, datetime]:
    if mode == 'previous':
        length = end - start
        return start - length, start
    if mode == 'previous_week':
        return start - timedelta(days=7), end - timedelta(days=7)
    if mode == 'previous_month':
        return shift_month(start, -1), shift_month(end, -1)
    raise ValueError(mode)


@dataclass(frozen=True)
class Query:
    metric: str
    companies: tuple[str, ...]
    group: str | None
    start: datetime
    end: datetime
    grain: str
    comparison: tuple[datetime, datetime] | None = None


@dataclass(frozen=True)
class HistoryRow:
    metric: str
    group: str
    company: str
    time: datetime
    value: int
    divider: int
    current: bool
    raw: dict


@dataclass
class Bucket:
    start: datetime
    end: datetime
    value: Decimal | None
    complete: bool
    partial_period: bool
    observed: datetime | None
    numerator: int | None
    denominator: int | None
    effective_hours: int
    raw: list[HistoryRow] = field(default_factory=list)


@dataclass
class Result:
    query: Query
    metric: Metric
    series: dict[tuple[str, str], list[Bucket]]
    comparison: dict[tuple[str, str], list[Bucket]]
    current_window: tuple[datetime, datetime]
    comparison_window: tuple[datetime, datetime] | None


class QueryCancelled(Exception):
    """The caller superseded this query before it finished."""


class HistoryStore:
    def __init__(self, rows: list[dict], simulation_time: datetime):
        self.simulation_time = parse_time(simulation_time)
        self.series: dict[tuple[str, str, str], list[HistoryRow]] = defaultdict(list)
        for raw in rows:
            try:
                time = parse_time(raw['模拟时间'])
                if time > self.simulation_time:
                    continue
                metric = raw['指标']
                company = str(raw.get('公司标识') or raw.get('玩家ID') or raw.get('公司名称') or '')
                record = HistoryRow(metric, str(raw.get('分组', '')), company, time,
                                    int(raw['值']), int(raw.get('分母') or 0),
                                    str(raw.get('当前槽位', '')).lower() == 'true', raw)
                self.series[(metric, company, record.group)].append(record)
            except (ValueError, KeyError):
                continue
        for records in self.series.values():
            records.sort(key=lambda record: record.time)

    def query(self, query: Query, cancelled=None) -> Result:
        if cancelled and cancelled():
            raise QueryCancelled()
        if query.start >= query.end:
            raise ValueError('结束时间必须晚于起始时间')
        if query.group == '__total__' and query.metric in NO_GROUP_TOTAL:
            raise ValueError('该指标的分组不能合计')
        if query.metric == 'transfer-coefficient':
            return self._transfer_query(query, cancelled)
        if query.metric == 'city-mode-share':
            merged, compared = {}, {}
            for name, label in (('public-transport', '公共交通'),
                                ('private-motoring', '私家车'), ('walking', '步行')):
                child = self.query(Query(name, (), query.group, query.start, query.end,
                                         query.grain, query.comparison), cancelled)
                for (_, group), buckets in child.series.items():
                    merged[('', label if group == '总计' else f'{label} · {group}')] = buckets
                for (_, group), buckets in child.comparison.items():
                    compared[('', label if group == '总计' else f'{label} · {group}')] = buckets
            return Result(query, METRICS[query.metric], merged, compared,
                          (query.start, query.end), query.comparison)
        metric = METRICS[query.metric]
        selected = {}
        total_records = defaultdict(list)
        base_records = defaultdict(list)
        for (name, company, group), records in self.series.items():
            if cancelled and cancelled():
                raise QueryCancelled()
            if name != query.metric or (query.group is not None and query.group != '__total__' and group != query.group):
                continue
            if metric.scope == 'company' and query.companies and company not in query.companies:
                continue
            key = ('' if metric.scope == 'city' else company, group)
            is_coverage_base = (name == 'coverage' and
                                str(records[0].raw.get('分组层级', '')) == '总计')
            # City observations do not belong to a company. Never duplicate them.
            if query.group == '__total__':
                (base_records if is_coverage_base else total_records)[key[0]].extend(records)
            elif is_coverage_base and query.group is None:
                continue
            else:
                selected[key] = records
        if query.group == '__total__':
            selected = {(company, '总计'): sorted(base_records.get(company) or
                                                total_records[company], key=lambda r: r.time)
                        for company in total_records.keys() | base_records.keys()}
        current = {key: self._buckets(records, metric, query.start, query.end, query.grain,
                                      query.group == '__total__', cancelled)
                   for key, records in selected.items()}
        comparison = {key: self._buckets(records, metric, *query.comparison, query.grain,
                                         query.group == '__total__', cancelled)
                      for key, records in selected.items()} if query.comparison else {}
        return Result(query, metric, current, comparison, (query.start, query.end), query.comparison)

    def _transfer_query(self, query, cancelled):
        # Both inputs always use every category, regardless of chart visibility.
        children = [self.query(Query(name, query.companies, '__total__', query.start,
                                     query.end, query.grain, query.comparison), cancelled)
                    for name in ('transport-by-type', 'trip-types')]

        def combine(left, right, window):
            combined = {}
            for key in sorted(left.keys() | right.keys()):
                empty = self._buckets([], METRICS['transport-by-type'], *window,
                                      query.grain, cancelled=cancelled)
                buckets = []
                for a, b in zip(left.get(key, empty), right.get(key, empty)):
                    if cancelled and cancelled():
                        raise QueryCancelled()
                    numerator, denominator = a.numerator, b.numerator
                    same_hours = {r.time for r in a.raw} == {r.time for r in b.raw}
                    value = (Decimal(numerator) / denominator
                             if same_hours and numerator is not None and denominator else None)
                    raw = sorted(a.raw + b.raw, key=lambda r: r.time)
                    buckets.append(Bucket(a.start, a.end, value, a.complete and b.complete,
                                          a.partial_period or b.partial_period,
                                          raw[-1].time if raw else None, numerator, denominator,
                                          len({r.time for r in raw}), raw))
                combined[key] = buckets
            return combined

        current = combine(children[0].series, children[1].series, (query.start, query.end))
        compared = (combine(children[0].comparison, children[1].comparison, query.comparison)
                    if query.comparison else {})
        return Result(query, METRICS[query.metric], current, compared,
                      (query.start, query.end), query.comparison)

    def _buckets(self, records, metric, start, end, grain, total=False, cancelled=None):
        result = []
        cursor = start
        while cursor < end:
            if cancelled and cancelled():
                raise QueryCancelled()
            natural_start, natural_end = period_bounds(cursor, grain)
            bucket_end = min(end, natural_end)
            selected = [r for r in records if cursor <= r.time < bucket_end]
            # Current slot may contain live stock or a partial flow. A recorded
            # zero is an observation, while an absent hour is missing.
            expected_hours = int((bucket_end - cursor).total_seconds() // 3600)
            valid_times = {r.time for r in selected if not (r.current and self.simulation_time < r.time + HOUR)}
            groups = {r.group for r in records} if total else set()
            observed_pairs = {(r.time, r.group) for r in selected if r.time in valid_times}
            partial_period = cursor != natural_start or bucket_end != natural_end
            complete = (not partial_period and len(valid_times) == expected_hours
                        and all(cursor + i * HOUR in valid_times for i in range(expected_hours))
                        and (not total or len(observed_pairs) == expected_hours * len(groups)))
            value = numerator = denominator = None
            if selected:
                numerator = sum(r.value for r in selected)
                denominator = sum(r.divider for r in selected)
                if metric.kind == 'flow':
                    value = Decimal(numerator) / metric.scale
                elif metric.kind == 'average':
                    observed_hours = len({r.time for r in selected})
                    value = sum((Decimal(r.value) / metric.scale for r in selected), Decimal(0)) / observed_hours if observed_hours else None
                elif metric.kind == 'ratio_flow':
                    value = Decimal(numerator) * (100 if metric.unit == '%' else 100) / denominator if denominator else None
                elif metric.kind == 'ratio_stock':
                    last_rows = ({r.group: r for r in selected if r.time == selected[-1].time}
                                 if total else {'one': selected[-1]})
                    numerator = sum(r.value for r in last_rows.values())
                    denominator = sum(r.divider for r in last_rows.values())
                    value = Decimal(numerator) * 100 / denominator if denominator else None
                else:
                    last_rows = ({r.group: r for r in selected if r.time == selected[-1].time}
                                 if total else {'one': selected[-1]})
                    numerator = sum(r.value for r in last_rows.values())
                    denominator = sum(r.divider for r in last_rows.values())
                    value = Decimal(numerator) / metric.scale
            result.append(Bucket(cursor, bucket_end, value, complete, partial_period,
                                 selected[-1].time if selected else None, numerator, denominator,
                                 len({r.time for r in selected}), selected))
            cursor = bucket_end
        return result


def calculate_transfer_coefficient(segments, journeys, segment_scope, journey_scope):
    """Definition helper for independently audited counts with matching scope."""
    if segment_scope != journey_scope or journeys is None or journeys <= 0 or segments is None:
        return None
    ratio = segments / journeys
    return ratio, ratio - 1


def summarize_buckets(buckets: list[Bucket], metric: Metric) -> Decimal | None:
    """One interval value, preserving numerator/denominator and hour weights."""
    if metric.kind == 'coefficient':
        observed = [b for b in buckets if b.numerator is not None or b.denominator is not None]
        # Missing inputs cannot silently become zero or disappear from a ratio.
        if any(b.numerator is None or b.denominator is None or
               (b.value is None and (b.denominator != 0 or
                {r.time for r in b.raw if r.metric == 'transport-by-type'} !=
                {r.time for r in b.raw if r.metric == 'trip-types'})) for b in observed):
            return None
        denominator = sum(b.denominator for b in observed)
        return Decimal(sum(b.numerator for b in observed)) / denominator if denominator else None
    if metric.kind == 'ratio_flow':
        observed = [b for b in buckets if b.numerator is not None or b.denominator is not None]
        if any(b.numerator is None or b.denominator is None for b in observed):
            return None
        denominator = sum(b.denominator for b in observed)
        return Decimal(sum(b.numerator for b in observed)) * 100 / denominator if denominator else None
    if metric.kind in ('stock', 'ratio_stock'):
        observed = [b for b in buckets if b.observed is not None]
        return observed[-1].value if observed else None
    valid = [b for b in buckets if b.value is not None]
    if not valid:
        return None
    if metric.kind == 'average':
        hours = sum(b.effective_hours for b in valid)
        return sum((b.value * b.effective_hours for b in valid), Decimal(0)) / hours if hours else None
    return sum((b.value for b in valid), Decimal(0))


@dataclass(frozen=True)
class Alert:
    metric: str
    key: tuple[str, str]
    reason: str
    before: Decimal
    after: Decimal
    start: datetime
    comparison_start: datetime
    end: datetime
    comparison_end: datetime


def alerts_for_result(result: Result, percentage_points=5, relative_percent=20,
                      passenger_absolute=100) -> list[Alert]:
    if (not result.comparison_window or not result.metric.confirmed
            or result.query.metric == 'transfer-coefficient'):
        return []
    if result.current_window[1] - result.current_window[0] != result.comparison_window[1] - result.comparison_window[0]:
        return []
    alerts = []
    for key, current in result.series.items():
        previous = result.comparison.get(key, [])
        if not current or not previous or len(current) != len(previous):
            continue
        if not all(b.complete and b.value is not None for b in current + previous):
            continue
        before, after = summarize_buckets(previous, result.metric), summarize_buckets(current, result.metric)
        if before is None or after is None:
            continue
        reason = ''
        if result.query.metric == 'cashflow' and ((before >= 0 > after) or (before < 0 <= after)):
            reason = '现金流转负' if after < 0 else '现金流转正'
        elif result.query.metric in {'linecount', 'stopcount', 'depotcount'} and after < before:
            reason = '规模缩减'
        elif result.metric.unit == '%' and abs(after - before) >= Decimal(str(percentage_points)):
            reason = '比例明显变化'
        elif result.metric.unit != '%' and before > 0 and after >= 0 and abs(after - before) / before * 100 >= Decimal(str(relative_percent)):
            if result.query.metric not in {'transport-by-group', 'transport-by-type', 'trip-types', 'trip-number'} or abs(after - before) >= passenger_absolute:
                reason = '数值明显变化'
        if reason:
            alerts.append(Alert(result.query.metric, key, reason, before, after,
                                result.current_window[0], result.comparison_window[0],
                                result.current_window[1], result.comparison_window[1]))
    return alerts
