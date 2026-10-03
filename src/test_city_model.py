from datetime import datetime as D
from decimal import Decimal
import pytest
from dashboard_model import FilterState
from statistics_model import HistoryStore, QueryCancelled
from test_statistics_model import row


def build(rows, grain='hour', companies=('a',)):
    from city_model import build_city_snapshot
    return build_city_snapshot(HistoryStore(rows, D(2024, 1, 4)),
        FilterState(companies, D(2024, 1, 2), D(2024, 1, 2, 3), grain,
                    (D(2024, 1, 1), D(2024, 1, 1, 3))))


def r(metric, group, hour, n, d=0, owner=''):
    return row(metric, group, D(2024, 1, 2, hour), n, d, owner)


def test_city_rejects_company_history_and_uses_last_complete_population_observation():
    data = [r('population', g, h, v) for g, h, v in
            [('A', 0, 10), ('B', 0, 20), ('A', 1, 50), ('B', 1, 60), ('A', 2, 99)]]
    data += [r('population', 'A', 2, 9000, owner='a')]
    snap = build(data)
    assert snap.filters.companies == () and snap.filters.comparison is None
    assert snap.kpis['population'].value == 110
    assert snap.kpis['population'].observed == D(2024, 1, 2, 1)
    assert snap.charts['population'].series[('', '总计')][-1].value is None


def test_trips_sum_and_time_uses_own_weights_not_group_mean_or_trip_count():
    data = [r('trip-number', 'A', 0, 100), r('trip-number', 'A', 1, 200),
            r('trip-time', 'A', 0, 100, 10), r('trip-time', 'B', 0, 90, 1),
            r('trip-time', 'A', 1, 200, 20), r('trip-time', 'B', 1, 50, 1)]
    for grain in ('hour', 'day', 'week', 'month'):
        snap = build(data, grain)
        assert snap.kpis['trip-number'].value == 300
        assert snap.kpis['trip-number'].unit == '次'
        assert snap.kpis['trip-time'].value == Decimal(440) / 32
        assert snap.charts['trip-time'].metric.unit == '分钟'


def test_density_peak_preserves_hour_and_zero_across_grains():
    data = [r('traffic-density', 'Road', 0, 90, 100),
            r('traffic-density', 'Road', 1, 10, 100), r('traffic-density', 'Track', 0, 0, 100)]
    for grain in ('hour', 'day', 'week', 'month'):
        snap = build(data, grain)
        peaks = snap.kpis['traffic-density'].details
        assert peaks[0].value == Decimal('90')
        assert peaks[0].unit == '%'
        assert peaks[0].observed == D(2024, 1, 2)
        assert peaks[1].value == 0


def test_mode_pie_common_denominator_once_and_no_forced_normalization():
    rows = [r(name, 'A', 0, n, 10) for name, n in
            [('walking', 5), ('public-transport', 3), ('private-motoring', 2)]]
    snap = build(rows)
    assert snap.pie_valid and snap.pie_denominator == 10
    assert [v.value for v in snap.kpis['city-mode-share'].details] == [50, 30, 20]
    bad = build(rows[:-1] + [r('private-motoring', 'A', 0, 2, 20)])
    assert not bad.pie_valid and bad.pie_reason == '统计范围不一致，饼图不可用'
    assert bad.charts['city-mode-share'].series[('', '私家车')][0].value == 10
    assert build(rows[:-1]).pie_reason == '数据不完整，饼图不可用'
    assert snap.kpis['city-mode-share'].reason == ''
    incomplete = build(rows[:-1] + [r('private-motoring', 'A', 0, 1, 10)])
    assert incomplete.pie_reason == '数据不完整，饼图不可用'


def test_energy_scaled_once_economy_negative_and_missing_weights_unavailable():
    snap = build([r('energy-prices', 'electricity', 0, 50), r('energy-prices', 'fuel', 0, 145),
                  r('economy', 'growth', 0, -2559, 10000), r('trip-time', 'A', 0, 10, 0)])
    assert snap.charts['energy-prices'].series[('', '电力')][0].value == Decimal('.5')
    assert snap.charts['energy-prices'].series[('', '柴油')][0].raw[0].value == 145
    assert snap.charts['economy'].series[('', '经济增长率')][0].value == Decimal('-25.59')
    assert snap.kpis['trip-time'].value is None
    assert snap.kpis['trip-time'].reason


def test_city_cancellation():
    from city_model import build_city_snapshot
    with pytest.raises(QueryCancelled):
        build_city_snapshot(HistoryStore([], D(2024, 1, 4)),
            FilterState((), D(2024, 1, 2), D(2024, 1, 3)), lambda: True)
