"""Network dashboard presentation data derived from one audited dashboard snapshot."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Callable

from dashboard_model import DashboardResult, FilterState
from statistics_model import Bucket, QueryCancelled, Result, summarize_buckets
from stats_view_model import company_result
from display_rules import number_places
from card_comparisons import CardComparison, change, peer_comparisons, baseline_label


BASE_KEYS = ('linecount', 'stopcount', 'coverage', 'vehicles-running',
             'transfer-coefficient', 'transport-by-type', 'transport-by-group', 'trip-types')
SELECTED_KEY = '__selected__'
NO_HISTORY = '暂无数据'
NO_COMPANY = '未选择公司'
NO_DEMAND = '车辆需求数据不完整'


@dataclass(frozen=True)
class NetworkOptions:
    mode: str = 'overall'
    facility: str = 'depotcount'
    vehicle: str = 'average'
    passenger: str = 'transport-by-type'
    comparison_label: str = '环比'


@dataclass(frozen=True)
class NetworkValue:
    metric_id: str
    title: str
    unit: str
    value: Decimal | None
    details: tuple[tuple[str, Decimal | None], ...] = ()
    complete: bool = False
    reason: str = ''
    comparison: CardComparison = CardComparison()
    context: str = ''


@dataclass(frozen=True)
class NetworkSummary:
    company_id: str | None
    title: str
    values: tuple[NetworkValue, ...]


@dataclass(frozen=True)
class NetworkChart:
    key: str
    title: str
    company_id: str | None
    result: Result | None
    allowed_modes: tuple[str, ...]
    reason: str = ''
    bar_result: Result | None = None


@dataclass(frozen=True)
class NetworkSnapshot:
    filters: FilterState
    options: NetworkOptions
    companies: dict[str, str]
    summaries: tuple[NetworkSummary, ...]
    charts: tuple[NetworkChart, ...]


def _check_cancelled(cancelled: Callable[[], bool] | None) -> None:
    if cancelled and cancelled():
        raise QueryCancelled()


def _display_name(company_id: str, companies: dict[str, str]) -> str:
    name = companies.get(company_id, company_id)
    return f'{name} [{company_id}]' if list(companies.values()).count(name) > 1 else name


def _bucket_for_company(buckets: list[Bucket] | None, index: int) -> Bucket | None:
    return buckets[index] if buckets is not None and index < len(buckets) else None


def _merged_bucket(parts: list[Bucket | None], template: Bucket, kind: str, scale: int) -> Bucket:
    present = [part for part in parts if part is not None]
    raw = sorted((record for part in present for record in part.raw), key=lambda r: r.time)
    partial = any(part.partial_period for part in present)
    complete = len(present) == len(parts) and all(part.complete for part in present)
    value = None
    numerator = denominator = None
    observed = None
    hours = 0

    if complete or len(present) == len(parts):
        if kind == 'stock':
            per_company = []
            for part in present:
                groups = {record.group for record in part.raw}
                by_time = {}
                for record in part.raw:
                    by_time.setdefault(record.time, []).append(record)
                per_company.append({time: sum(record.value for record in records)
                                    for time, records in by_time.items()
                                    if {record.group for record in records} == groups})
            shared = set.intersection(*(set(times) for times in per_company)) if per_company else set()
            if len(per_company) == len(parts) and shared:
                observed = max(shared)
                numerator = sum(times[observed] for times in per_company)
                value = Decimal(numerator) / scale
                hours = 1
                if any(record.time > observed for record in raw):
                    complete = False
        elif kind == 'average':
            per_company = []
            for part in present:
                times = {}
                groups = {record.group for record in part.raw}
                for record in part.raw:
                    times.setdefault(record.time, []).append(record)
                per_company.append({time: sum(r.value for r in records)
                                    for time, records in times.items()
                                    if {r.group for r in records} == groups})
            shared = set.intersection(*(set(times) for times in per_company)) if per_company else set()
            if shared:
                observed = max(shared)
                hours = len(shared)
                numerator = sum(sum(times[time] for times in per_company) for time in shared)
                value = Decimal(numerator) / scale / hours
                expected = int((template.end - template.start) / timedelta(hours=1))
                complete = complete and hours == expected
            else:
                complete = False
        elif kind == 'coefficient':
            if all(part.numerator is not None and part.denominator is not None and
                   {r.time for r in part.raw if r.metric == 'transport-by-type'} ==
                   {r.time for r in part.raw if r.metric == 'trip-types'} for part in present):
                numerator = sum(part.numerator for part in present)
                denominator = sum(part.denominator for part in present)
                value = Decimal(numerator) / denominator if denominator else None
                observed = max((part.observed for part in present if part.observed is not None), default=None)
                hours = len({record.time for record in raw})
        elif kind == 'ratio_flow':
            if all(part.numerator is not None and part.denominator is not None for part in present):
                numerator = sum(part.numerator for part in present)
                denominator = sum(part.denominator for part in present)
                value = Decimal(numerator) * 100 / denominator if denominator else None
                observed = max((part.observed for part in present if part.observed is not None), default=None)
                hours = min(part.effective_hours for part in present)
        elif all(part.value is not None for part in present):
            value = sum((part.value for part in present), Decimal(0))
            numerator = (sum(part.numerator for part in present)
                         if all(part.numerator is not None for part in present) else None)
            denominator = (sum(part.denominator for part in present)
                           if all(part.denominator is not None for part in present) else None)
            observed = max((part.observed for part in present if part.observed is not None), default=None)
            hours = min(part.effective_hours for part in present)
    if value is None:
        complete = False
    return Bucket(template.start, template.end, value, complete, partial, observed,
                  numerator, denominator, hours, raw)


def _merge_series(series: dict[tuple[str, str], list[Bucket]], ids: tuple[str, ...],
                  kind: str, scale: int, cancelled) -> dict[tuple[str, str], list[Bucket]]:
    groups = sorted({group for company, group in series if company in ids})
    merged = {}
    for group in groups:
        _check_cancelled(cancelled)
        by_company = [series.get((company, group)) for company in ids]
        template_list = next((buckets for buckets in by_company if buckets), None)
        if template_list is None:
            continue
        merged[(SELECTED_KEY, group)] = [
            _merged_bucket([_bucket_for_company(buckets, index) for buckets in by_company],
                           template, kind, scale)
            for index, template in enumerate(template_list)]
    return merged


def _aggregate_result(result: Result, ids: tuple[str, ...], include_comparison: bool,
                      cancelled) -> Result:
    _check_cancelled(cancelled)
    if len(ids) == 1:
        return company_result(result, ids, include_comparison=include_comparison)
    series = _merge_series(result.series, ids, result.metric.kind, result.metric.scale, cancelled)
    compared = (_merge_series(result.comparison, ids, result.metric.kind,
                              result.metric.scale, cancelled) if include_comparison else {})
    query = replace(result.query, companies=ids,
                    comparison=result.query.comparison if include_comparison else None)
    return Result(query, result.metric, series, compared, result.current_window,
                  result.comparison_window if include_comparison else None)


def _quantity_trend(source: Result, ids: tuple[str, ...], include_comparison: bool) -> Result:
    """Sum each company's categories at matching observed instants for trend lines."""
    def combined(series):
        merged = {}
        for company in ids:
            groups = [buckets for (owner, _), buckets in series.items() if owner == company]
            template = next((buckets for buckets in groups if buckets), None)
            if template is None:
                continue
            merged[(company, '总计')] = [
                _merged_bucket([_bucket_for_company(buckets, index) for buckets in groups],
                               bucket, source.metric.kind, source.metric.scale)
                for index, bucket in enumerate(template)]
        return merged
    query = replace(source.query, companies=ids,
                    comparison=source.query.comparison if include_comparison else None)
    return Result(query, source.metric, combined(source.series),
                  combined(source.comparison) if include_comparison else {},
                  source.current_window,
                  source.comparison_window if include_comparison else None)


def _quantity_bar(source: Result, ids: tuple[str, ...], mode: str) -> Result:
    """One latest observed value per category, within each requested period."""
    def at_end(series, window):
        output = {}
        groups = sorted({group for company, group in series if company in ids})
        owners = (SELECTED_KEY,) if mode == 'overall' and len(ids) > 1 else ids
        for owner in owners:
            selected_ids = ids if owner == SELECTED_KEY else (owner,)
            for group in groups:
                by_company = []
                for company in selected_ids:
                    records = [record for bucket in series.get((company, group), ())
                               for record in bucket.raw if window[0] <= record.time < window[1]]
                    by_company.append({record.time: record for record in records})
                common = set.intersection(*(set(records) for records in by_company)) if by_company else set()
                latest = max(common) if common else None
                records = [company[latest] for company in by_company] if latest is not None else []
                raw = sorted(records, key=lambda record: record.time)
                value = (Decimal(sum(record.value for record in raw)) / source.metric.scale
                         if len(raw) == len(selected_ids) else None)
                output[(owner, group)] = [Bucket(latest or window[0],
                                                 latest + timedelta(hours=1) if latest else window[1],
                                                 value, value is not None and all(not record.current for record in raw),
                                                 False, latest,
                                                 sum(record.value for record in raw) if raw else None,
                                                 None, 1 if latest else 0, raw)]
            latest_for_owner = max((output[(owner, group)][0].observed for group in groups
                                    if output[(owner, group)][0].observed is not None), default=None)
            for group in groups:
                bucket = output[(owner, group)][0]
                if latest_for_owner is not None and bucket.observed != latest_for_owner:
                    output[(owner, group)] = [replace(bucket, complete=False)]
        return output
    include_comparison = mode == 'period'
    query = replace(source.query, companies=ids,
                    comparison=source.query.comparison if include_comparison else None)
    return Result(query, source.metric, at_end(source.series, source.current_window),
                  at_end(source.comparison, source.comparison_window)
                  if include_comparison and source.comparison_window else {},
                  source.current_window,
                  source.comparison_window if include_comparison else None)


def _last_day_result(result: Result) -> Result:
    """Re-bucket already queried observations for the final calendar day only."""
    window_start, window_end = result.current_window
    last_day = (window_end - timedelta(microseconds=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    start = max(window_start, last_day)
    metric = result.metric
    series = {}
    expected_hours = int((window_end - start) / timedelta(hours=1))
    for key, buckets in result.series.items():
        raw = sorted((record for bucket in buckets for record in bucket.raw
                      if start <= record.time < window_end), key=lambda record: record.time)
        times = {record.time for record in raw}
        numerator = denominator = None
        value = None
        if raw:
            if metric.kind == 'average':
                groups = {record.group for bucket in buckets for record in bucket.raw}
                by_time = {}
                for record in raw:
                    by_time.setdefault(record.time, []).append(record)
                aligned = [records for records in by_time.values()
                           if {record.group for record in records} == groups]
                if aligned:
                    numerator = sum(record.value for records in aligned for record in records)
                    value = Decimal(numerator) / metric.scale / len(aligned)
            elif metric.kind == 'ratio_flow':
                numerator = sum(record.value for record in raw)
                denominator = sum(record.divider for record in raw)
                value = Decimal(numerator) * 100 / denominator if denominator else None
            elif metric.kind == 'coefficient':
                segments = [record for record in raw if record.metric == 'transport-by-type']
                journeys = [record for record in raw if record.metric == 'trip-types']
                if ({record.time for record in segments} == {record.time for record in journeys}
                        and segments and journeys):
                    numerator = sum(record.value for record in segments)
                    denominator = sum(record.value for record in journeys)
                    value = Decimal(numerator) / denominator if denominator else None
        complete = (value is not None and expected_hours > 0 and len(times) == expected_hours
                    and start == last_day and window_end == last_day + timedelta(days=1)
                    and all(bucket.complete for bucket in buckets if bucket.raw))
        series[key] = [Bucket(start, window_end, value, complete,
                              start != last_day or window_end != last_day + timedelta(days=1),
                              raw[-1].time if raw else None, numerator, denominator,
                              len(times), raw)]
    return Result(replace(result.query, start=start, end=window_end,
                          comparison=None), metric, series, {},
                  (start, window_end), None)


def _numeric_value(metric_id: str, title: str, result: Result) -> NetworkValue:
    buckets = [bucket for series in result.series.values() for bucket in series]
    if not buckets:
        return NetworkValue(metric_id, title, result.metric.unit, None, reason=NO_HISTORY)
    metric = result.metric
    if metric.kind == 'stock':
        ids = result.query.companies
        records = [record for bucket in buckets for record in bucket.raw]
        groups = {record.group for record in records}
        by_identity = {}
        for record in records:
            by_identity.setdefault((record.company, record.group), {})[record.time] = record
        required = [(company, group) for company in ids for group in groups]
        shared = (set.intersection(*(set(by_identity.get(key, {})) for key in required))
                  if required else set())
        latest = max(shared) if shared else None
        amount = (Decimal(sum(by_identity[key][latest].value for key in required)) / metric.scale
                  if latest is not None else None)
    else:
        amount = summarize_buckets(buckets, metric)
    complete = bool(amount is not None and all(bucket.complete for bucket in buckets))
    reason = ('数据不完整' if any(bucket.raw for bucket in buckets) else NO_HISTORY)
    return NetworkValue(metric_id, title, metric.unit, amount, complete=complete,
                        reason=reason if amount is None else ('数据不完整' if not complete else ''))


def _vehicle_demand(ids: tuple[str, ...], lines) -> NetworkValue:
    total = Decimal(0)
    reason = NO_COMPANY if not ids else NO_DEMAND if lines is None else ''
    if not reason:
        for line in lines:
            if str(line.get('公司标识')) not in ids:
                continue
            try:
                amount = Decimal(str(line.get('理论最大车辆需求数')))
                if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
                    raise ValueError('invalid demand')
            except (InvalidOperation, ValueError, TypeError):
                reason = NO_DEMAND
                break
            total += amount
    return NetworkValue('vehicles-running', '车辆', '辆',
                        None if reason else total, complete=not reason,
                        reason=reason, comparison=CardComparison(text=''))


def _summary(snapshot: DashboardResult, ids: tuple[str, ...],
             companies: dict[str, str], options: NetworkOptions, cancelled, lines=None) -> NetworkSummary:
    _check_cancelled(cancelled)
    def total(metric_id: str) -> Result:
        source = snapshot.results[metric_id]
        if metric_id in ('vehicles-running', 'coverage', 'transfer-coefficient'):
            source = _last_day_result(source)
        return _aggregate_result(source, ids, False, cancelled)

    line_count = total('linecount')
    facility = total(options.facility)
    vehicles = total('vehicles-running')
    coverage = total('coverage')
    passengers = total(options.passenger)
    coefficient = total('transfer-coefficient')
    values = [
        _numeric_value('linecount', line_count.metric.label, line_count),
        _numeric_value(options.facility, facility.metric.label, facility),
        (_vehicle_demand(ids, lines) if options.vehicle == 'maximum'
         else _numeric_value('vehicles-running', '车辆', vehicles)),
        (NetworkValue('coverage', coverage.metric.label, coverage.metric.unit,
                      None, reason=NO_HISTORY)
         if options.mode == 'overall' and len(ids) > 1 else
         _numeric_value('coverage', coverage.metric.label, coverage)),
        _numeric_value(options.passenger, '客流' if options.passenger == 'transport-by-type' else '出行量', passengers),
        _numeric_value('transfer-coefficient', coefficient.metric.label, coefficient),
    ]
    return NetworkSummary(ids[0] if len(ids) == 1 and options.mode != 'overall' else None,
                          _display_name(ids[0], companies) if len(ids) == 1 and options.mode != 'overall'
                          else '总体', tuple(values))


def _allowed_modes(key: str, grain: str) -> tuple[str, ...]:
    if key in ('linecount', 'stopcount'):
        return ('bar',) if grain == 'hour' else ('line', 'bar')
    if key in ('coverage', 'transfer-coefficient'):
        return ('line',)
    if key == 'vehicles-running':
        return ('line', 'bar')
    return ('trend-bar', 'pie')


def _chart_result(snapshot: DashboardResult, key: str, ids: tuple[str, ...],
                  options: NetworkOptions, cancelled) -> tuple[Result | None, str]:
    if not ids:
        return None, NO_COMPANY
    source = (snapshot.results['transport-by-type'] if key == 'company-passengers'
              else snapshot.results[key] if key in ('linecount', 'vehicles-running',
                                                   'coverage', 'transfer-coefficient')
              else snapshot.breakdowns[key])
    include_comparison = options.mode == 'period'
    if key == 'stopcount':
        source = _quantity_trend(source, ids, include_comparison)
    if (options.mode in ('companies', 'period') or key == 'company-passengers' or
            (key == 'coverage' and len(ids) > 1)):
        result = company_result(source, ids, include_comparison=include_comparison)
    else:
        result = _aggregate_result(source, ids, include_comparison, cancelled)
    if not result.series:
        return result, NO_HISTORY
    if key == 'company-passengers':
        by_company = [result.series.get((company, '总计'), []) for company in ids]
        if any(not any(bucket.value is not None for bucket in buckets) for buckets in by_company):
            return None, '客流数据不完整'
        count = max(len(buckets) for buckets in by_company)
        shared = {index for index in range(count)
                  if all(index < len(buckets) and buckets[index].value is not None
                         for buckets in by_company)}
        if not shared:
            return None, '客流数据不完整'
        if len(shared) < count:
            masked = {company_key: [bucket if index in shared else replace(
                bucket, value=None, complete=False, numerator=None, denominator=None)
                                    for index, bucket in enumerate(buckets)]
                      for company_key, buckets in result.series.items()}
            return replace(result, series=masked), '部分时段数据不完整'
    if options.mode == 'period' and result.comparison_window is None:
        return result, '请选择对比周期'
    buckets = [bucket for series in result.series.values() for bucket in series]
    if buckets and all(bucket.value is None for bucket in buckets):
        return result, '数据不完整' if any(bucket.raw for bucket in buckets) else NO_HISTORY
    return result, ''


def build_network_snapshot(snapshot: DashboardResult, options: NetworkOptions,
                           companies: dict[str, str], cancelled=None, *, lines=None) -> NetworkSnapshot:
    """Build network summaries and chart descriptors from the same dashboard query."""
    _check_cancelled(cancelled)
    if options.mode not in ('overall', 'companies', 'period'):
        raise ValueError(options.mode)
    if options.facility not in ('depotcount', 'stopcount'):
        raise ValueError(options.facility)
    if options.vehicle not in ('average', 'maximum'):
        raise ValueError(options.vehicle)
    if options.passenger not in ('transport-by-type', 'trip-types'):
        raise ValueError(options.passenger)
    ids = tuple(dict.fromkeys(snapshot.filters.companies))
    if options.mode == 'companies' and len(companies) < 2:
        options = replace(options, mode='overall')
    hide_joint_coverage = options.mode == 'overall' and len(ids) > 1
    names = {company: companies.get(company, company) for company in ids}
    summary_ids = (tuple([company]) for company in ids) if options.mode != 'overall' else (ids,)
    summaries = tuple(_summary(snapshot, selected, names, options, cancelled, lines)
                      for selected in summary_ids)
    if options.mode == 'companies':
        enriched = []
        for summary in summaries:
            values = []
            for value in summary.values:
                amounts = {item.company_id: next(v.value for v in item.values if v.metric_id == value.metric_id)
                           for item in summaries}
                window = (None if options.vehicle == 'maximum' and value.metric_id == 'vehicles-running'
                          else (snapshot.filters.start, snapshot.filters.end))
                comparison = peer_comparisons(amounts, names, value.unit,
                    window, value_places=number_places(value.metric_id))[summary.company_id]
                values.append(replace(value, comparison=comparison))
            enriched.append(replace(summary, values=tuple(values)))
        summaries = tuple(enriched)
    else:
        period = options.mode == 'period'
        baseline_results = ({key: replace(result, series=result.comparison, comparison={},
            current_window=result.comparison_window or result.current_window, comparison_window=None,
            query=replace(result.query, start=(result.comparison_window or result.current_window)[0],
                          end=(result.comparison_window or result.current_window)[1], comparison=None))
            for key, result in snapshot.results.items()} if period else snapshot.card_previous)
        if baseline_results:
            first = next(iter(baseline_results.values()))
            baseline_snapshot = DashboardResult(replace(snapshot.filters, start=first.current_window[0],
                end=first.current_window[1], comparison=None), baseline_results, baseline_results, [])
            enriched = []
            for summary in summaries:
                selected = (summary.company_id,) if summary.company_id else ids
                before = _summary(baseline_snapshot, selected, names, options, cancelled)
                values = []
                for value, previous in zip(summary.values, before.values):
                    if options.vehicle == 'maximum' and value.metric_id == 'vehicles-running':
                        values.append(value)
                        continue
                    comparison = change(value.value, previous.value, value.unit,
                        '较同比区间' if period else baseline_label(snapshot.filters.start, snapshot.filters.end),
                        current_window=(snapshot.filters.start, snapshot.filters.end),
                        previous_window=first.current_window,
                        partial=not value.complete or not previous.complete,
                        value_places=number_places(value.metric_id))
                    values.append(replace(value, comparison=comparison))
                enriched.append(replace(summary, values=tuple(values)))
            summaries = tuple(enriched)
    if hide_joint_coverage:
        summaries = tuple(replace(summary, values=tuple(
            value for value in summary.values if value.metric_id != 'coverage'))
                          for summary in summaries)
    keys = tuple(key for key in BASE_KEYS if not (hide_joint_coverage and key == 'coverage'))
    keys += (('company-passengers',) if options.mode == 'companies' else ())
    chart_ids = tuple((company,) for company in ids) if options.mode == 'period' else (ids,)
    charts = []
    for selected in chart_ids:
        for key in keys:
            _check_cancelled(cancelled)
            result, reason = _chart_result(snapshot, key, selected, options, cancelled)
            bar_result = (_quantity_bar(snapshot.breakdowns[key], selected, options.mode)
                          if key in ('linecount', 'stopcount', 'vehicles-running') and
                          result is not None else None)
            title = ('分公司客流' if key == 'company-passengers' else
                     '分区出行量' if key == 'trip-types' else
                     snapshot.results[key].metric.label)
            charts.append(NetworkChart(key, title,
                                       selected[0] if options.mode == 'period' else None,
                                       result, _allowed_modes(key, snapshot.filters.grain),
                                       reason, bar_result))
    return NetworkSnapshot(snapshot.filters, options, names, summaries, tuple(charts))
