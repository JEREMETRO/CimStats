"""Shared dashboard snapshot for presentation, alerts and exports."""
from dataclasses import dataclass, field
from datetime import datetime

from statistics_model import (Alert, BOARDS, METRICS, NO_GROUP_TOTAL, HistoryStore,
                              Query, QueryCancelled, Result, alerts_for_result)
from stats_view_model import preset_window
from card_comparisons import baseline_window


@dataclass(frozen=True)
class FilterState:
    companies: tuple[str, ...]
    start: datetime
    end: datetime
    grain: str = 'day'
    comparison: tuple[datetime, datetime] | None = None


@dataclass
class DashboardResult:
    filters: FilterState
    results: dict[str, Result]
    breakdowns: dict[str, Result]
    alerts: list[Alert]
    card_previous: dict[str, Result] = field(default_factory=dict)
    city_boardings: Result | None = None
    all_company_ids: tuple[str, ...] = ()


def default_window(simulation_time) -> tuple[datetime, datetime]:
    return preset_window(simulation_time, 'previous_full_week')


def build_dashboard(store: HistoryStore, filters: FilterState,
                    thresholds: tuple = (5, 20, 100), cancelled=None) -> DashboardResult:
    results, breakdowns, alerts = {}, {}, []
    seen = set()
    for name in dict.fromkeys(name for board in BOARDS.values() for name in board):
        if cancelled and cancelled():
            raise QueryCancelled()
        metric = METRICS[name]
        def query(group):
            request = Query(name, filters.companies, group, filters.start, filters.end,
                            filters.grain, filters.comparison)
            # HistoryStore's legacy empty tuple means all; the dashboard means none.
            if metric.scope == 'company' and not filters.companies:
                return Result(request, metric, {}, {}, (filters.start, filters.end), filters.comparison)
            return store.query(request, cancelled)

        breakdowns[name] = query(None)
        results[name] = breakdowns[name] if name in NO_GROUP_TOTAL else query('__total__')
        # The three source metrics already contribute these same city alerts.
        if name == 'city-mode-share':
            continue
        for alert in alerts_for_result(results[name], *thresholds):
            if alert not in seen:
                seen.add(alert)
                alerts.append(alert)
    if cancelled and cancelled():
        raise QueryCancelled()
    previous = {}
    start, end = baseline_window(filters.start, filters.end)
    for name, result in results.items():
        if result.metric.scope != 'company':
            continue
        if cancelled and cancelled():
            raise QueryCancelled()
        query = Query(name, filters.companies, result.query.group, start, end, filters.grain)
        previous[name] = (store.query(query, cancelled) if filters.companies else
                          Result(query, result.metric, {}, {}, (start, end), None))
    city_boardings = store.query(Query('transport-by-type', (), None, filters.start,
                                      filters.end, filters.grain), cancelled)
    all_company_ids = tuple(sorted({owner for (name, owner, _) in store.series
                                   if owner and METRICS.get(name) and METRICS[name].scope == 'company'}))
    return DashboardResult(filters, results, breakdowns, alerts, previous, city_boardings, all_company_ids)
