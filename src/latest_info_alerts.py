"""Save-local homepage alerts using the audited dashboard rules."""
from datetime import timedelta

from dashboard_model import DashboardResult, FilterState, build_dashboard
from statistics_model import HistoryStore, parse_time


def default_alert_filters(simulation_time, company_ids: tuple[str, ...]) -> FilterState:
    """Compare yesterday with its preceding day, measured by simulation time.

    Pass every stable company ID for an all-company selection. As in the
    shared dashboard, an empty selection means no company, not every company;
    city-scope observations remain independent of that selection.
    """
    end = parse_time(simulation_time).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=1)
    return FilterState(tuple(company_ids), start, end, 'hour',
                       (start - timedelta(days=1), start))


def build_latest_alerts(store: HistoryStore, filters: FilterState,
                        thresholds=(5, 20, 100), cancelled=None) -> DashboardResult:
    """Reuse dashboard comparability, thresholds, deduplication and cancellation."""
    return build_dashboard(store, filters, thresholds, cancelled)
