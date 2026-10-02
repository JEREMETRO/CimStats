"""Pure date and company selection helpers for statistics presentation."""
from dataclasses import replace
from datetime import datetime, timedelta

from statistics_model import Result, compare_window, parse_time


def preset_window(simulation_time, preset: str) -> tuple[datetime, datetime]:
    """Return the last complete calendar week or day in simulation time."""
    day = parse_time(simulation_time).replace(hour=0, minute=0, second=0, microsecond=0)
    if preset == 'previous_full_week':
        end = day - timedelta(days=day.weekday())
        return end - timedelta(days=7), end
    if preset == 'previous_full_day':
        return day - timedelta(days=1), day
    raise ValueError(preset)


def resolve_comparison(start: datetime, end: datetime, preset: str,
                       custom: tuple[datetime, datetime] | None = None) -> tuple[datetime, datetime]:
    """Resolve a comparison interval, preserving custom interval length."""
    if start >= end:
        raise ValueError('结束时间必须晚于起始时间')
    if preset == 'custom':
        if custom is None or len(custom) != 2:
            raise ValueError('自定义对比区间不能为空')
        comparison = custom
    else:
        comparison = compare_window(start, end, preset)
    if comparison[0] >= comparison[1]:
        raise ValueError('对比结束时间必须晚于起始时间')
    return comparison


def company_result(result: Result, company_ids: tuple[str, ...], *,
                   include_comparison: bool = True) -> Result:
    """Select series by company identity without altering source data."""
    selected = set(company_ids)
    series = {key: list(buckets) for key, buckets in result.series.items() if key[0] in selected}
    comparison = ({key: list(buckets) for key, buckets in result.comparison.items()
                   if key[0] in selected} if include_comparison else {})
    query = replace(result.query, companies=company_ids,
                    comparison=result.query.comparison if include_comparison else None)
    return Result(query, result.metric, series, comparison, result.current_window,
                  result.comparison_window if include_comparison else None)
