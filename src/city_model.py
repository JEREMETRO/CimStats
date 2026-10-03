"""Save-local city observations; company filters never enter this snapshot."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from dashboard_model import FilterState
from statistics_model import Bucket, HistoryStore, Metric, Query, QueryCancelled, Result, period_bounds
from card_comparisons import CardComparison, change, baseline_window, baseline_label

MODES = (('walking', '步行'), ('public-transport', '公共交通'), ('private-motoring', '私家车'))
CHART_KEYS = ('population', 'trip-number', 'city-mode-share', 'trip-time', 'economy', 'energy-prices')
METRICS = {
    'population': Metric('人口变化', 'city', 'stock', '人'),
    'trip-number': Metric('出行量', 'city', 'flow', '次'),
    'city-mode-share': Metric('交通方式分担率', 'city', 'ratio_flow', '%'),
    'trip-time': Metric('出行时间', 'city', 'weighted', '分钟'),
    'economy': Metric('经济增长与利率', 'city', 'ratio_stock', '%'),
    'energy-prices': Metric('能源价格', 'city', 'stock', '货币', 100),
}


@dataclass(frozen=True)
class CityValue:
    title: str
    value: Decimal | None = None
    unit: str = ''
    observed: datetime | None = None
    complete: bool = False
    reason: str = ''
    details: tuple['CityValue', ...] = ()
    comparison: CardComparison = CardComparison()


@dataclass
class CitySnapshot:
    filters: FilterState
    charts: dict[str, Result]
    kpis: dict[str, CityValue]
    pie_valid: bool
    pie_reason: str
    pie_denominator: int
    pie_counts: dict[str, int]
    pie_result: Result
    source: str = '无公司归属城市历史；同刻完整原始分类汇总'


def _check(cancelled):
    if cancelled and cancelled():
        raise QueryCancelled()


def _groups(store, metric, filters, cancelled):
    groups = defaultdict(list)
    for (name, owner, group), rows in store.series.items():
        _check(cancelled)
        if name == metric and not owner:
            groups[group].extend(r for r in rows if filters.start <= r.time < filters.end)
    return dict(groups)


def _aligned(groups):
    """A total exists only where every serialized category has an observation."""
    by_time = defaultdict(dict)
    base = {}
    categories = set()
    for group, rows in groups.items():
        if any(r.raw.get('分组层级') == '总计' for r in rows):
            for r in rows:
                base[r.time] = [r]
            continue
        categories.add(group)
        for r in rows:
            by_time[r.time][group] = r
    complete = {time: list(entries.values()) for time, entries in by_time.items()
                if categories and set(entries) == categories}
    complete.update(base)
    return [(time, rows) for time, rows in sorted(complete.items())]


def _observations(rows):
    by_time = defaultdict(list)
    for r in rows:
        by_time[r.time].append(r)
    return sorted(by_time.items())


def _buckets(observations, metric, filters, simulation_time, cancelled):
    output = []
    cursor = filters.start
    while cursor < filters.end:
        _check(cancelled)
        natural_start, natural_end = period_bounds(cursor, filters.grain)
        end = min(filters.end, natural_end)
        selected = [(t, rows) for t, rows in observations if cursor <= t < end]
        raw = [r for _, rows in selected for r in rows]
        numerator = denominator = None
        value = None
        observed = None
        if selected:
            observed = selected[-1][0]
            source = selected[-1][1] if metric.kind in ('stock', 'ratio_stock') else raw
            numerator = sum(r.value for r in source)
            denominator = sum(r.divider for r in source)
            if metric.kind in ('weighted', 'ratio_flow', 'ratio_stock'):
                # A positive numerator without its actual weight is not a valid mean.
                invalid = any(r.divider < 0 or (r.divider == 0 and r.value != 0) for r in source)
                if denominator > 0 and not invalid:
                    value = Decimal(numerator) / denominator * (100 if metric.unit == '%' else 1)
            else:
                value = Decimal(numerator) / metric.scale
        times = {t for t, rows in selected if not any(
            r.current and simulation_time < r.time + timedelta(hours=1) for r in rows)}
        expected = int((end - cursor).total_seconds() // 3600)
        partial = cursor != natural_start or end != natural_end
        complete = not partial and len(times) == expected and all(
            cursor + timedelta(hours=i) in times for i in range(expected))
        output.append(Bucket(cursor, end, value, complete, partial, observed,
                             numerator, denominator, len(selected), raw))
        cursor = end
    return output


def _result(key, series, filters, simulation_time, cancelled, metric=None):
    definition = metric or METRICS[key]
    return Result(Query(key, (), None, filters.start, filters.end, filters.grain), definition,
        {('', group): _buckets(obs, definition, filters, simulation_time, cancelled)
         for group, obs in series.items()}, {}, (filters.start, filters.end), None)


def city_summary(buckets, metric):
    if metric.kind in ('stock', 'ratio_stock'):
        valid = [b for b in buckets if b.value is not None]
        return valid[-1].value if valid else None
    if metric.kind in ('weighted', 'ratio_flow'):
        observed = [b for b in buckets if b.observed is not None]
        if any(b.value is None and (b.numerator or b.denominator) for b in observed):
            return None
        denominator = sum(b.denominator or 0 for b in observed)
        return (Decimal(sum(b.numerator or 0 for b in observed)) / denominator *
                (100 if metric.unit == '%' else 1)) if denominator > 0 else None
    valid = [b.value for b in buckets if b.value is not None]
    return sum(valid, Decimal(0)) if valid else None


def build_city_snapshot(store: HistoryStore, filters: FilterState, cancelled=None, *, _comparisons=True):
    _check(cancelled)
    filters = replace(filters, companies=(), comparison=None)
    charts, kpis = {}, {}
    groups = {key: _groups(store, key, filters, cancelled) for key in
              ('population', 'trip-number', 'trip-time', 'economy', 'energy-prices',
               'traffic-density', *(key for key, _ in MODES))}
    for key in ('population', 'trip-number', 'trip-time'):
        series = {'总计' if key != 'trip-time' else '平均': _aligned(groups[key])}
        if key == 'trip-time':
            series.update({g: _observations(rows) for g, rows in groups[key].items()
                           if not any(r.raw.get('分组层级') == '总计' for r in rows)})
        charts[key] = result = _result(key, series, filters, store.simulation_time, cancelled)
        buckets = next(iter(result.series.values()))
        value = city_summary(buckets, result.metric)
        valid = [b for b in buckets if b.value is not None]
        title = {'population': '人口', 'trip-number': '出行量', 'trip-time': '平均出行时间'}[key]
        reason = ('窗口最后有效全市观测' if key == 'population' else
                  '所选时段累计' if key == 'trip-number' else
                  '')
        if value is None:
            reason = '缺少有效观测' if key != 'trip-time' else '缺少有效时间分母，平均不可计算'
        kpis[key] = CityValue(title, value, result.metric.unit,
            valid[-1].observed if valid else None, bool(buckets) and all(b.complete for b in buckets), reason)

    mode_series, details, counts = {}, [], {}
    for key, name in MODES:
        observations = _aligned(groups[key])
        result = _result('city-mode-share', {name: observations}, filters, store.simulation_time, cancelled)
        buckets = result.series[('', name)]
        mode_series[('', name)] = buckets
        details.append(CityValue(name, city_summary(buckets, result.metric), '%',
            buckets[-1].observed if buckets else None, all(b.complete for b in buckets)))
        counts[name] = sum(r.value for _, rows in observations for r in rows)
    charts['city-mode-share'] = Result(Query('city-mode-share', (), None, filters.start,
        filters.end, filters.grain), METRICS['city-mode-share'], mode_series, {},
        (filters.start, filters.end), None)
    # Validate source membership, not rounded ratios, and count each common denominator once.
    signatures = []
    for key, _ in MODES:
        signatures.append({(r.time, g): r for g, rows in groups[key].items() for r in rows
                           if r.raw.get('分组层级') != '总计'})
    membership = set(signatures[0])
    valid_pie = bool(membership) and all(set(s) == membership for s in signatures)
    pie_reason = '数据不完整，饼图不可用' if not valid_pie else ''
    denominator = 0
    if valid_pie:
        for identity in sorted(membership):
            _check(cancelled)
            rows = [s[identity] for s in signatures]
            d = rows[0].divider
            if d < 0 or any(r.divider != d or r.value < 0 for r in rows) or sum(r.value for r in rows) != d:
                valid_pie = False
                pie_reason = ('统计范围不一致，饼图不可用' if any(r.divider != d for r in rows)
                              else '数据不完整，饼图不可用')
                break
            denominator += d
        # No silently omitted category/hour in any total observation.
        expected_groups = set(groups[MODES[0][0]])
        for t in {time for time, _ in membership}:
            if {g for time, g in membership if time == t} != expected_groups:
                valid_pie = False
                pie_reason = '数据不完整，饼图不可用'
    valid_pie = valid_pie and denominator > 0
    reason = '' if valid_pie else pie_reason or '数据不完整，饼图不可用'
    kpis['city-mode-share'] = CityValue('交通方式分担率', unit='%', details=tuple(details),
        complete=all(d.complete for d in details), reason='')
    # The pie uses a single window bucket per mode, after source-level validation.
    pie_series = {}
    for key, name in MODES:
        source = [r for rows in groups[key].values() for r in rows]
        amount = counts[name]
        pie_series[('', name)] = [Bucket(filters.start, filters.end,
            Decimal(amount) * 100 / denominator if valid_pie else None,
            all(d.complete for d in details), True, max((r.time for r in source), default=None),
            amount, denominator if valid_pie else None, len({r.time for r in source}), source)]
    pie_result = replace(charts['city-mode-share'], series=pie_series)

    for key, aliases in (('economy', {'growth': '经济增长率', 'interests': '利率'}),
                         ('energy-prices', {'electricity': '电力', 'fuel': '柴油'})):
        charts[key] = _result(key, {aliases[g]: _observations(rows) for g, rows in groups[key].items()
                                  if g in aliases}, filters, store.simulation_time, cancelled)
    peaks = []
    for group, name in (('Road', '道路峰值'), ('Track', '轨道峰值')):
        rows = groups['traffic-density'].get(group, [])
        valid = [r for r in rows if r.divider > 0]
        peak = max(valid, key=lambda r: Decimal(r.value) / r.divider, default=None)
        peaks.append(CityValue(name, Decimal(peak.value) * 100 / peak.divider if peak else None,
            '%', peak.time if peak else None, False,
            '' if peak else '缺少有效观测'))
    kpis['traffic-density'] = CityValue('最大交通密度', details=tuple(peaks), reason='统计时间内最高小时交通密度')
    if _comparisons:
        start, end = baseline_window(filters.start, filters.end)
        previous = build_city_snapshot(store, replace(filters, start=start, end=end, comparison=None),
                                       cancelled, _comparisons=False)
        for key, model in tuple(kpis.items()):
            before = previous.kpis[key]
            def compare(current, baseline):
                return change(current.value, baseline.value, current.unit,
                    baseline_label(filters.start, filters.end),
                    current_window=(filters.start, filters.end), previous_window=(start, end),
                    partial=not current.complete or not baseline.complete)
            details = tuple(replace(detail, comparison=compare(detail, prior))
                            for detail, prior in zip(model.details, before.details))
            kpis[key] = replace(model, details=details, comparison=compare(model, before))
    _check(cancelled)
    return CitySnapshot(filters, charts, kpis, valid_pie, reason, denominator if valid_pie else 0,
                        counts, pie_result)
