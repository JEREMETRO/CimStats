"""Completed-trip duration summaries use arrival counts as their weights."""
from datetime import datetime as D, timedelta
from decimal import Decimal

import pytest

from chart_details import summary_cards
from city_model import build_city_snapshot
from dashboard_model import FilterState
from statistics_model import HistoryStore, summarize_buckets
from test_statistics_model import row


def snapshot(rows, *, start=D(2024, 1, 1), end=D(2024, 1, 3),
             grain='day', comparison=None):
    return build_city_snapshot(HistoryStore(rows, D(2024, 2, 1)),
        FilterState((), start, end, grain, comparison))


def detail_average(result, index=0):
    return dict(summary_cards(result, {})[index]['values'])['平均']


@pytest.mark.parametrize('grain', ['hour', 'day', 'week', 'month'])
def test_trip_time_detail_weights_completed_journeys_across_buckets(grain):
    rows = [row('trip-time', 'WhiteCollar', D(2024, 1, 1), 60, 2),
            row('trip-time', 'WhiteCollar', D(2024, 1, 2), 300, 3)]
    state = snapshot(rows, grain=grain)
    result = state.charts['trip-time']
    # 360 elapsed minutes / 5 completed trips; daily means 30 + 100 are not additive.
    assert state.kpis['trip-time'].value == Decimal(72)
    assert detail_average(result) == Decimal(72)
    assert summarize_buckets(result.series[('', '平均')], result.metric) == Decimal(72)


@pytest.mark.parametrize(('grain', 'observed_buckets'), [
    ('hour', [(30, 60, 2, 1), (100, 300, 3, 1), (16, 80, 5, 1)]),
    ('day', [(72, 360, 5, 2), (16, 80, 5, 1)]),
    ('week', [(44, 440, 10, 3)]),
    ('month', [(44, 440, 10, 3)]),
])
def test_trip_time_curve_points_weight_all_observations_in_each_bucket(grain, observed_buckets):
    state = snapshot([
        row('trip-time', 'WhiteCollar', D(2024, 1, 1), 60, 2),
        row('trip-time', 'WhiteCollar', D(2024, 1, 1, 23), 300, 3),
        row('trip-time', 'WhiteCollar', D(2024, 1, 2, 12), 80, 5),
    ], grain=grain)
    result = state.charts['trip-time']
    for group in ('平均', 'WhiteCollar'):
        buckets = result.series[('', group)]
        assert [(b.value, b.numerator, b.denominator, b.effective_hours)
                for b in buckets if b.value is not None] == observed_buckets


def test_seven_day_duration_summary_uses_arrivals_instead_of_summing_day_means():
    # Native hourly records aggregated into daily numerator/denominator pairs,
    # from Eixeia's [2013-05-20, 2013-05-27) history. No private save required.
    pairs = [(8664359, 248753), (8603207, 253349), (8602299, 254440),
             (9054097, 253225), (10945158, 306312), (9181875, 231009),
             (8893659, 224880)]
    start = D(2013, 5, 20)
    rows = [row('trip-time', 'WhiteCollar', start + timedelta(days=i), n, d)
            for i, (n, d) in enumerate(pairs)]
    state = snapshot(rows, start=start, end=D(2013, 5, 27))
    expected = Decimal(63944654) / 1771968
    assert state.kpis['trip-time'].value == expected
    assert detail_average(state.charts['trip-time']) == expected  # Previously 253.38035 minutes.


@pytest.mark.parametrize('numerator,denominator,expected', [
    (0, 2, Decimal(12)),       # Real zero-minute arrivals retain their weight.
    (0, 0, Decimal(20)),       # No arrivals contributes neither minutes nor trips.
    (60, 0, None),            # Duration without its arrival count is invalid.
    (60, -1, None),           # A negative arrival count is invalid.
])
def test_trip_time_summary_distinguishes_zero_weight_and_invalid_pair(numerator, denominator, expected):
    state = snapshot([row('trip-time', 'WhiteCollar', D(2024, 1, 1), numerator, denominator),
                      row('trip-time', 'WhiteCollar', D(2024, 1, 2), 60, 3)])
    assert state.kpis['trip-time'].value == expected
    assert detail_average(state.charts['trip-time']) == expected


def test_trip_time_missing_window_does_not_borrow_outside_observations():
    state = snapshot([row('trip-time', 'WhiteCollar', D(2023, 12, 31, 23), 100, 2),
                      row('trip-time', 'WhiteCollar', D(2024, 1, 3), 900, 3)])
    result = state.charts['trip-time']
    assert state.kpis['trip-time'].value is None
    assert detail_average(result) is None
    assert [b.start for b in result.series[('', '平均')]] == [D(2024, 1, 1), D(2024, 1, 2)]
    assert all(b.value is None and not b.raw and not b.complete
               for b in result.series[('', '平均')])


def test_trip_time_period_summaries_keep_each_actual_window_and_missing_hours():
    state = snapshot([
        row('trip-time', 'WhiteCollar', D(2024, 1, 1), 60, 2),
        row('trip-time', 'WhiteCollar', D(2024, 1, 2), 300, 3),
        row('trip-time', 'WhiteCollar', D(2023, 12, 30), 50, 5),
        row('trip-time', 'WhiteCollar', D(2024, 1, 3), 9999, 1),
    ], comparison=(D(2023, 12, 30), D(2023, 12, 31)))
    result = state.charts['trip-time']
    cards = summary_cards(result, {})
    assert (detail_average(result), detail_average(result, 1)) == (Decimal(72), Decimal(10))
    assert [card['window'] for card in cards] == [
        (D(2024, 1, 1), D(2024, 1, 3)), (D(2023, 12, 30), D(2023, 12, 31))]
    assert all(not b.complete for b in result.series[('', '平均')])
    assert len(result.comparison[('', '平均')]) == 1
