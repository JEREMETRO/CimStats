"""Vehicle chart modes share aligned hourly observations and interval weights."""
from datetime import datetime as D
from decimal import Decimal

import pytest

from dashboard_model import FilterState, build_dashboard
from network_model import NetworkOptions, build_network_snapshot
from statistics_model import HistoryStore, summarize_buckets
from test_network_model import NAMES, chart, history


def vehicle_chart(rows, *, grain='day', ids=('a',), mode='overall',
                  start=D(2024, 1, 1), end=D(2024, 1, 4), comparison=None):
    source = build_dashboard(HistoryStore(rows, D(2024, 3, 1)),
                             FilterState(ids, start, end, grain, comparison))
    state = build_network_snapshot(source, NetworkOptions(mode=mode), NAMES)
    return chart(state, 'vehicles-running', ids[0] if mode == 'period' else None)


@pytest.mark.parametrize('grain', ['hour', 'day', 'week', 'month'])
def test_distribution_uses_effective_hour_weights_across_whole_window(grain):
    # First day has two observations (including a real zero), second has one.
    # Mean = (0 + 6 + 12) / 3 = 6; mean of daily means would incorrectly be 7.5.
    rows = [history('vehicles-running', 'a', hour, amount * 1024, day=day)
            for day, hour, amount in [(1, 0, 0), (1, 1, 6), (2, 0, 12)]]
    item = vehicle_chart(rows, grain=grain)
    bar = item.bar_result.series[('a', 'bus')][0]
    assert (bar.value, bar.effective_hours) == (Decimal(6), 3)
    assert (bar.start, bar.end) == (D(2024, 1, 1), D(2024, 1, 4))
    assert not bar.complete
    assert summarize_buckets(item.result.series[('a', '总计')], item.result.metric) == 6


@pytest.mark.parametrize('mode', ['overall', 'companies', 'period'])
def test_categories_use_common_hours_without_turning_missing_into_zero(mode):
    rows = [history('vehicles-running', 'a', hour, amount * 1024, day=1, group=group)
            for group, hour, amount in [('bus', 0, 2), ('bus', 1, 100), ('tram', 0, 6)]]
    item = vehicle_chart(rows, mode=mode, comparison=(D(2023, 12, 31), D(2024, 1, 1)))
    bars = item.bar_result.series
    assert bars[('a', 'bus')][0].value == 2
    assert bars[('a', 'tram')][0].value == 6
    assert all(bucket.effective_hours == 1 and not bucket.complete
               for buckets in bars.values() for bucket in buckets)
    assert summarize_buckets(item.result.series[('a', '总计')], item.result.metric) == 8


def test_overall_aligns_companies_and_categories_before_averaging():
    rows = [history('vehicles-running', owner, hour, amount * 1024, day=1, group=group)
            for owner, group, hour, amount in [
                ('a', 'bus', 0, 2), ('a', 'tram', 0, 3),
                ('b', 'bus', 0, 5), ('b', 'tram', 0, 7),
                ('a', 'bus', 1, 100), ('a', 'tram', 1, 100),
                ('b', 'bus', 1, 100)]]
    item = vehicle_chart(rows, ids=('a', 'b'))
    assert item.bar_result.series[('__selected__', 'bus')][0].value == 7
    assert item.bar_result.series[('__selected__', 'tram')][0].value == 10
    assert summarize_buckets(item.result.series[('__selected__', '总计')], item.result.metric) == 17


def test_no_common_category_hour_is_missing_and_preserves_observations():
    rows = [history('vehicles-running', 'a', 0, 0, day=1, group='bus'),
            history('vehicles-running', 'a', 1, 4 * 1024, day=1, group='tram')]
    item = vehicle_chart(rows)
    assert all(bucket.value is None and bucket.effective_hours == 0 and bucket.raw
               for buckets in item.bar_result.series.values() for bucket in buckets)
    assert all(bucket.value is None for bucket in item.result.series[('a', '总计')])


def test_absent_company_is_missing_instead_of_partial_total():
    item = vehicle_chart([history('vehicles-running', 'a', 0, 0, day=1)], ids=('a', 'b'))
    bucket = item.bar_result.series[('__selected__', 'bus')][0]
    assert bucket.value is None and bucket.effective_hours == 0


def test_period_averages_each_window_without_using_outside_observations():
    rows = [history('vehicles-running', 'a', hour, amount * 1024, day=day)
            for day, hour, amount in [(1, 0, 2), (1, 1, 4), (2, 0, 0), (2, 1, 8),
                                      (2, 2, 999), (3, 0, 999)]]
    item = vehicle_chart(rows, mode='period', start=D(2024, 1, 2), end=D(2024, 1, 2, 2),
                         comparison=(D(2024, 1, 1), D(2024, 1, 1, 2)))
    current = item.bar_result.series[('a', 'bus')][0]
    previous = item.bar_result.comparison[('a', 'bus')][0]
    assert (current.value, previous.value) == (Decimal(4), Decimal(3))
    assert current.complete and previous.complete
    assert current.effective_hours == previous.effective_hours == 2
