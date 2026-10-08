"""Full-city journey counts and paired boardings, independent of company filters."""
from dataclasses import replace
from decimal import Decimal

from statistics_model import Bucket, METRICS, Metric, QueryCancelled, Result

MISSING_CITY = '公共交通行程数据不完整'
MISSING_PAIRS = '客流与出行量缺少完整同期观测'
CITY_JOURNEY_CONTEXT = '全市公共交通行程，跨公司换乘只计一次；不作同期比较'


def _check(cancelled):
    if cancelled and cancelled():
        raise QueryCancelled()


def _hours(rows, expected, cancelled=None):
    """Require exactly one record per serialized category at each instant."""
    by_time = {}
    for index, row in enumerate(rows):
        if index % 256 == 0:
            _check(cancelled)
        by_time.setdefault(row.time, []).append(row)
    return {time: values for time, values in by_time.items()
            if expected and {r.group for r in values} == expected
            and len(values) == len(expected) and all(r.value >= 0 for r in values)}


def city_public_journeys(city: Result, serialized_groups, cancelled=None):
    """Use the original city numerator, never the percentage or divider."""
    expected = set(serialized_groups)
    buckets = []
    for bucket in city.series.get(('', '总计'), ()):
        _check(cancelled)
        valid = _hours(bucket.raw, expected, cancelled)
        raw = [r for r in bucket.raw if r.time in valid and not r.company]
        if len(raw) != sum(map(len, valid.values())):
            raw = []
        numerator = sum(r.value for r in raw) if raw else None
        buckets.append(replace(bucket,
            value=Decimal(numerator) if numerator is not None else None,
            numerator=numerator, denominator=None,
            effective_hours=len({r.time for r in raw}),
            observed=max((r.time for r in raw), default=None),
            complete=bucket.complete and bool(raw) and len(raw) == len(bucket.raw), raw=raw))
    query = replace(city.query, metric='city-public-journeys', companies=(), comparison=None)
    return Result(query, Metric('全市公共交通出行量', 'city', 'flow', '人次'),
                  {('', '总计'): buckets}, {}, city.current_window, None)


def _city_inputs(snapshot):
    source = snapshot.results.get('public-transport')
    breakdown = snapshot.breakdowns.get('public-transport')
    expected = {group for owner, group in breakdown.series if not owner} if breakdown else set()
    window = (snapshot.filters.start, snapshot.filters.end)
    if (not source or source.current_window != window or source.metric.scope != 'city'
            or source.query.metric != 'public-transport' or not expected):
        return None, None, MISSING_CITY
    return source, expected, ''


def overall_journeys(snapshot, cancelled=None):
    city, expected, reason = _city_inputs(snapshot)
    if city is None:
        return None, reason
    result = city_public_journeys(city, expected, cancelled)
    return result, ('' if any(b.numerator is not None for b in result.series[('', '总计')])
                    else MISSING_CITY)


def overall_transfer(snapshot, cancelled=None, *, positive_hours_only=False):
    city, expected, reason = _city_inputs(snapshot)
    if city is None:
        return None, reason
    board = snapshot.city_boardings
    if (board is None or board.query.companies or board.query.metric != 'transport-by-type'
            or board.current_window != city.current_window):
        return None, MISSING_PAIRS
    owners = snapshot.all_company_ids
    categories = {c: {group for owner, group in board.series if owner == c} for c in owners}
    rows = {c: [r for (owner, _), buckets in board.series.items() if owner == c
                for b in buckets for r in b.raw] for c in owners}
    hours = {c: _hours(rows[c], categories[c], cancelled) for c in owners}
    buckets = []
    for template in city.series.get(('', '总计'), ()):
        _check(cancelled)
        public = _hours(template.raw, expected, cancelled)
        valid = {time for time in public
                 if owners and all(time in hours[c] for c in owners)
                 and all(not r.company for r in public[time])
                 and (not positive_hours_only or sum(r.value for r in public[time]) > 0)}
        numerator = (sum(r.value for c in owners for time in valid for r in hours[c][time])
                     if valid else None)
        denominator = sum(r.value for time in valid for r in public[time]) if valid else None
        raw = sorted([r for c in owners for time in valid for r in hours[c][time]]
                     + [r for time in valid for r in public[time]], key=lambda r: r.time)
        complete = (template.complete and len(valid) == len(public) and bool(raw)
                    and all(not r.current for r in raw)
                    and all(set(hours[c]) & {r.time for r in template.raw} == valid for c in owners))
        buckets.append(Bucket(template.start, template.end,
            Decimal(numerator) / denominator if denominator else None,
            complete, template.partial_period, max(valid) if valid else None,
            numerator, denominator, len(valid), raw))
    query = replace(city.query, metric='transfer-coefficient', companies=(), comparison=None)
    result = Result(query, replace(METRICS['transfer-coefficient'], scope='city'), {('', '总计'): buckets}, {},
                    city.current_window, None)
    return result, '' if any(b.numerator is not None for b in buckets) else MISSING_PAIRS
