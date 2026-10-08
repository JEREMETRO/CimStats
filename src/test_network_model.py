from datetime import datetime as D
from decimal import Decimal

import pytest

from dashboard_model import FilterState, build_dashboard
from statistics_model import HistoryStore, QueryCancelled
from test_statistics_model import row


START, END = D(2024, 1, 2), D(2024, 1, 2, 2)
PREVIOUS = (D(2024, 1, 1), D(2024, 1, 1, 2))
NAMES = {'a': '同名公司', 'b': '同名公司', 'c': '未选公司'}
BASE_KEYS = ('linecount', 'stopcount', 'coverage', 'vehicles-running',
             'transfer-coefficient', 'transport-by-type', 'transport-by-group', 'trip-types')


def history(metric, company, hour, value, *, day=2, group='bus', divider=0):
    record = row(metric, group, D(2024, 1, day, hour), value, divider, company)
    record['公司名称'] = '同名公司'
    return record


def dashboard(rows, ids=('a', 'b'), grain='hour', comparison=PREVIOUS):
    store = HistoryStore(rows, D(2024, 1, 3))
    return build_dashboard(store, FilterState(ids, START, END, grain, comparison))


def value(summary, position):
    if len(summary.values) == 5 and position > 3:
        position -= 1
    return summary.values[position]


def chart(network, key, company=None):
    return next(c for c in network.charts if c.key == key and c.company_id == company)


def test_network_modes_have_fixed_summary_and_chart_contracts():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('transport-by-type', company, 0, amount, day=day)
            for company, amount in [('a', 10), ('b', 30), ('c', 999)] for day in (1, 2)]
    rows += [history('transport-by-group', company, 0, amount, day=day, group='Student')
             for company, amount in [('a', 10), ('b', 30), ('c', 999)] for day in (1, 2)]
    source = dashboard(rows)
    overall = build_network_snapshot(source, NetworkOptions(), NAMES)
    assert overall.filters == source.filters
    assert overall.companies == {'a': '同名公司', 'b': '同名公司'}
    assert len(overall.summaries) == 1
    assert overall.summaries[0].company_id is None
    assert len(overall.summaries[0].values) == 5
    assert 'coverage' not in {item.metric_id for item in overall.summaries[0].values}
    assert tuple(c.key for c in overall.charts) == tuple(key for key in BASE_KEYS if key != 'coverage')
    assert all(c.company_id is None for c in overall.charts)
    assert value(overall.summaries[0], 4).value == Decimal(40)
    assert set(chart(overall, 'transport-by-type').result.series) == {('__selected__', 'bus')}
    assert chart(overall, 'transport-by-type').result.query.companies == ('a', 'b')
    assert chart(overall, 'transport-by-type').result.comparison == {}
    assert source.results['transport-by-type'].comparison

    companies = build_network_snapshot(source, NetworkOptions(mode='companies'), NAMES)
    assert [s.company_id for s in companies.summaries] == ['a', 'b']
    assert tuple(c.key for c in companies.charts) == BASE_KEYS + ('company-passengers',)
    assert {key[0] for key in chart(companies, 'transport-by-type').result.series} == {'a', 'b'}
    shares = chart(companies, 'company-passengers').result
    assert {key[0] for key in shares.series} == {'a', 'b'}
    assert sum(bucket.value for buckets in shares.series.values() for bucket in buckets if bucket.value is not None) == 40
    assert shares.comparison == {}

    period = build_network_snapshot(source, NetworkOptions(mode='period'), NAMES)
    assert [s.company_id for s in period.summaries] == ['a', 'b']
    assert len(period.charts) == 16
    assert tuple(c.key for c in period.charts[:8]) == BASE_KEYS
    for company in ('a', 'b'):
        descriptor = chart(period, 'transport-by-type', company)
        assert descriptor.result.query.companies == (company,)
        assert {key[0] for key in descriptor.result.series} == {company}
        assert {key[0] for key in descriptor.result.comparison} == {company}
        assert descriptor.result.comparison_window == PREVIOUS


def test_company_mode_uses_archive_capability_and_empty_selection_stays_empty():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('transport-by-type', company, 0, amount)
            for company, amount in [('a', 10), ('b', 30)]]
    one = build_network_snapshot(dashboard(rows, ('a',)), NetworkOptions(mode='companies'), NAMES)
    assert one.options.mode == 'companies'
    assert len(one.summaries) == 1 and len(one.charts) == 9
    assert value(one.summaries[0], 4).value == Decimal(10)
    single = build_network_snapshot(dashboard(rows, ('a',)), NetworkOptions(mode='companies'), {'a': NAMES['a']})
    assert single.options.mode == 'overall'
    empty = build_network_snapshot(dashboard(rows, ()), NetworkOptions(), NAMES)
    assert empty.companies == {}
    assert all(item.value is None for item in empty.summaries[0].values)
    assert all(c.result is None or not c.result.series for c in empty.charts)


def test_stock_total_uses_latest_common_observation_without_mixing_times():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('linecount', 'a', 0, 10), history('linecount', 'b', 0, 20),
            history('linecount', 'b', 1, 30)]
    network = build_network_snapshot(dashboard(rows, grain='day'), NetworkOptions(), NAMES)
    assert value(network.summaries[0], 0).value == Decimal(30)
    total_chart = chart(network, 'linecount').result
    assert total_chart.series[('__selected__', '总计')][0].value == Decimal(30)
    assert total_chart.series[('__selected__', '总计')][0].observed == D(2024, 1, 2)
    assert not total_chart.series[('__selected__', '总计')][0].complete
    assert chart(network, 'linecount').bar_result.series[('__selected__', 'bus')][0].value == Decimal(30)


def test_stock_total_sums_only_same_end_instant_and_preserves_groups():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('linecount', company, 1, amount, group=group)
            for company, group, amount in [('a', 'bus', 10), ('a', 'tram', 3),
                                           ('b', 'bus', 20), ('b', 'tram', 4)]]
    network = build_network_snapshot(dashboard(rows, grain='day'), NetworkOptions(), NAMES)
    assert value(network.summaries[0], 0).value == Decimal(37)
    descriptor = chart(network, 'linecount')
    assert set(descriptor.result.series) == {('__selected__', '总计')}
    assert descriptor.result.series[('__selected__', '总计')][0].value == Decimal(37)
    assert descriptor.bar_result.series[('__selected__', 'bus')][0].value == Decimal(30)
    assert descriptor.bar_result.series[('__selected__', 'tram')][0].value == Decimal(7)


def test_stock_summary_uses_last_valid_common_hour_before_cutoff():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('linecount', 'a', 0, 10), history('linecount', 'b', 0, 20),
            history('linecount', 'b', 1, 30)]
    network = build_network_snapshot(dashboard(rows), NetworkOptions(), NAMES)
    assert [b.value for b in chart(network, 'linecount').result.series[('__selected__', '总计')]] == [
        Decimal(30), None]
    assert value(network.summaries[0], 0).value == Decimal(30)


def test_category_missing_from_one_company_is_not_assumed_zero():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('transport-by-type', 'a', 0, 10, group='bus'),
            history('transport-by-type', 'b', 0, 20, group='tram')]
    network = build_network_snapshot(dashboard(rows), NetworkOptions(), NAMES)
    result = chart(network, 'transport-by-type').result
    assert {group for _, group in result.series} == {'bus', 'tram'}
    assert result.series[('__selected__', 'bus')][0].value is None
    assert result.series[('__selected__', 'tram')][0].value is None


def test_vehicle_total_aligns_hours_before_weighted_average_and_keeps_missing():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('vehicles-running', 'a', 0, 2 * 1024),
            history('vehicles-running', 'a', 1, 4 * 1024),
            history('vehicles-running', 'b', 0, 6 * 1024)]
    network = build_network_snapshot(dashboard(rows, grain='hour'), NetworkOptions(), NAMES)
    vehicles = value(network.summaries[0], 2)
    assert vehicles.value == Decimal(8)  # shared hour: 2 + 6; not mean(a)=3 + mean(b)=6
    assert not vehicles.complete
    buckets = chart(network, 'vehicles-running').result.series[('__selected__', '总计')]
    assert [b.value for b in buckets] == [Decimal(8), None]
    assert [b.effective_hours for b in buckets] == [1, 0]


def test_vehicle_total_uses_aligned_hour_weights_inside_day_bucket():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('vehicles-running', 'a', 0, 2 * 1024),
            history('vehicles-running', 'a', 1, 4 * 1024),
            history('vehicles-running', 'b', 0, 6 * 1024)]
    network = build_network_snapshot(dashboard(rows, grain='day'), NetworkOptions(), NAMES)
    bucket = chart(network, 'vehicles-running').result.series[('__selected__', '总计')][0]
    assert bucket.value == Decimal(8)
    assert bucket.effective_hours == 1
    assert value(network.summaries[0], 2).value == Decimal(8)
    assert not value(network.summaries[0], 2).complete


def test_transfer_coefficient_uses_city_journeys_not_company_marginal_sum():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history(metric, company, 0, count)
            for company, segments, journeys in [('a', 10, 10), ('b', 90, 30)]
            for metric, count in [('transport-by-type', segments), ('trip-types', journeys)]]
    rows.append(row('public-transport', 'Student', START, 25, 100))
    source = dashboard(rows)
    network = build_network_snapshot(source, NetworkOptions(), NAMES)
    coefficient = value(network.summaries[0], 5)
    assert coefficient.value == Decimal(4)  # 100 boardings / 25 unique city journeys.
    bucket = chart(network, 'transfer-coefficient').result.series[('', '总计')][0]
    assert (bucket.numerator, bucket.denominator, bucket.value) == (100, 25, Decimal(4))
    assert bucket.effective_hours == 1


def test_transfer_coefficient_keeps_zero_company_denominator_in_total_numerator():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history(metric, company, 0, count)
            for company, segments, journeys in [('a', 10, 10), ('b', 90, 0)]
            for metric, count in [('transport-by-type', segments), ('trip-types', journeys)]]
    rows.append(row('public-transport', 'Student', START, 10, 100))
    source = dashboard(rows)
    network = build_network_snapshot(source, NetworkOptions(), NAMES)
    coefficient = value(network.summaries[0], 5)
    assert coefficient.value == Decimal(10)  # (10 + 90) / (10 + 0)
    bucket = chart(network, 'transfer-coefficient').result.series[('', '总计')][0]
    assert (bucket.numerator, bucket.denominator, bucket.value) == (100, 10, Decimal(10))


@pytest.mark.parametrize('bad_rows', [
    [history('transport-by-type', 'b', 0, 90)],
    [history('transport-by-type', 'b', 0, 90), history('trip-types', 'b', 1, 30)],
])
def test_transfer_coefficient_does_not_hide_zero_or_missing_denominator(bad_rows):
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('transport-by-type', 'a', 0, 10), history('trip-types', 'a', 0, 10)] + bad_rows
    network = build_network_snapshot(dashboard(rows), NetworkOptions(), NAMES)
    assert value(network.summaries[0], 5).value is None
    assert chart(network, 'transfer-coefficient').result is None
    assert chart(network, 'transfer-coefficient').reason == '公共交通行程数据不完整'


def test_overall_stops_sum_but_coverage_waits_for_a_proven_total_source():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('stopcount', company, 0, number, group=group)
            for company, group, number in [('a', 'bus', 3), ('a', 'tram', 4),
                                           ('b', 'bus', 5), ('b', 'tram', 6),
                                           ('c', 'bus', 1000)]]
    rows += [history('coverage', company, 0, amount, divider=denominator)
             for company, amount, denominator in [('a', 20, 100), ('b', 90, 300)]]
    rows.append(history('coverage', 'c', 0, 999, divider=1))
    network = build_network_snapshot(dashboard(rows, grain='day'), NetworkOptions(facility='stopcount'), NAMES)
    stops = value(network.summaries[0], 1)
    assert stops.metric_id == 'stopcount' and stops.value == Decimal(18)
    assert set(chart(network, 'stopcount').result.series) == {('__selected__', '总计')}
    assert chart(network, 'stopcount').bar_result.series[('__selected__', 'bus')][0].value == Decimal(8)
    assert 'coverage' not in {item.metric_id for item in network.summaries[0].values}
    assert 'coverage' not in {item.key for item in network.charts}
    single = build_network_snapshot(dashboard(rows, ('a',), grain='day'),
                                    NetworkOptions(facility='stopcount'), NAMES)
    assert value(single.summaries[0], 1).value == Decimal(7)
    assert value(single.summaries[0], 3).value == Decimal(20)


def test_company_coverage_keeps_hourly_chart_values():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('coverage', company, hour, numerator, divider=denominator)
            for company, hour, numerator, denominator in
            [('a', 0, 20, 100), ('b', 0, 90, 300),
             ('a', 1, 40, 100), ('b', 1, 120, 300)]]
    network = build_network_snapshot(dashboard(rows), NetworkOptions(mode='companies'), NAMES)
    descriptor = chart(network, 'coverage')
    assert descriptor.result is not None
    assert descriptor.reason == ''
    assert [bucket.value for bucket in descriptor.result.series[('a', '总计')]] == [
        Decimal(20), Decimal(40)]
    assert [bucket.value for bucket in descriptor.result.series[('b', '总计')]] == [
        Decimal(30), Decimal(40)]
    assert [value(summary, 3).value for summary in network.summaries] == [Decimal(30), Decimal(35)]


def test_coverage_curves_use_each_company_any_total_not_six_category_lines():
    from network_model import NetworkOptions, build_network_snapshot

    groups = ('WhiteCollar', 'BlueCollar', 'Pensioner',
              'BusinessPeople', 'Student', 'Tourist')
    rows = []
    for day in (1, 2):
        for company, numerator in (('a', 60), ('b', 70)):
            for group in groups:
                rows.append(history('coverage', company, 0, numerator // 6,
                                    day=day, group=group, divider=20))
            base = history('coverage', company, 0, numerator,
                           day=day, group='任意', divider=120)
            base['分组层级'] = '总计'
            rows.append(base)
    source = dashboard(rows)
    for mode in ('overall', 'companies'):
        network = build_network_snapshot(source, NetworkOptions(mode=mode), NAMES)
        if mode == 'overall':
            assert 'coverage' not in {item.metric_id for item in network.summaries[0].values}
            assert 'coverage' not in {item.key for item in network.charts}
        else:
            result = chart(network, 'coverage').result
            assert set(result.series) == {('a', '总计'), ('b', '总计')}
            assert [result.series[(company, '总计')][0].value for company in ('a', 'b')] == [50, Decimal(70) * 100 / 120]
            assert [value(summary, 3).value for summary in network.summaries] == [50, Decimal(70) * 100 / 120]
    period = build_network_snapshot(source, NetworkOptions(mode='period'), NAMES)
    for company in ('a', 'b'):
        result = chart(period, 'coverage', company).result
        assert set(result.series) == {(company, '总计')}
        assert set(result.comparison) == {(company, '总计')}


def test_summary_average_and_coefficient_use_last_day_while_trends_keep_range():
    from network_model import NetworkOptions, build_network_snapshot

    rows = []
    for day, vehicles, coverage, segments, journeys in [
        (1, 100, 10, 10, 10), (2, 4, 60, 90, 30),
    ]:
        rows += [history('vehicles-running', 'a', 0, vehicles * 1024, day=day),
                 history('coverage', 'a', 0, coverage, day=day, divider=100),
                 history('transport-by-type', 'a', 0, segments, day=day),
                 history('trip-types', 'a', 0, journeys, day=day)]
        rows.append(row('public-transport', 'Student', D(2024, 1, day), journeys, 100))
    source = build_dashboard(HistoryStore(rows, D(2024, 1, 3)), FilterState(
        ('a',), D(2024, 1, 1), D(2024, 1, 3), 'day'))
    network = build_network_snapshot(source, NetworkOptions(), NAMES)
    assert value(network.summaries[0], 2).value == Decimal(4)
    assert value(network.summaries[0], 3).value == Decimal(60)
    assert value(network.summaries[0], 5).value == Decimal(3)
    assert [bucket.value for bucket in chart(network, 'vehicles-running').result.series[('a', '总计')]] == [
        Decimal(100), Decimal(4)]


def test_last_day_summary_does_not_fall_back_to_earlier_day():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('vehicles-running', 'a', 0, 7 * 1024, day=1),
            history('coverage', 'a', 0, 80, day=1, divider=100),
            history('transport-by-type', 'a', 0, 30, day=1),
            history('trip-types', 'a', 0, 10, day=1)]
    source = build_dashboard(HistoryStore(rows, D(2024, 1, 3)), FilterState(
        ('a',), D(2024, 1, 1), D(2024, 1, 3), 'day'))
    network = build_network_snapshot(source, NetworkOptions(), NAMES)
    assert all(value(network.summaries[0], index).value is None for index in (2, 3, 5))
    assert value(network.summaries[0], 4).value == Decimal(30)


@pytest.mark.parametrize('metric', ['linecount', 'stopcount'])
def test_company_quantity_trend_is_one_total_line_and_bar_uses_latest_categories(metric):
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history(metric, company, 0, amount, day=day, group=group)
            for day, company, group, amount in [
                (1, 'a', 'bus', 2), (1, 'a', 'tram', 3),
                (1, 'b', 'bus', 5), (1, 'b', 'tram', 7),
                (2, 'a', 'bus', 11), (2, 'a', 'tram', 13),
                (2, 'b', 'bus', 17), (2, 'b', 'tram', 19),
            ]]
    source = build_dashboard(HistoryStore(rows, D(2024, 1, 3)), FilterState(
        ('a', 'b'), D(2024, 1, 1), D(2024, 1, 3), 'day'))
    network = build_network_snapshot(source, NetworkOptions(mode='companies'), NAMES)
    descriptor = chart(network, metric)
    assert set(descriptor.result.series) == {('a', '总计'), ('b', '总计')}
    assert [bucket.value for bucket in descriptor.result.series[('a', '总计')]] == [5, 24]
    assert [bucket.value for bucket in descriptor.result.series[('b', '总计')]] == [12, 36]
    assert descriptor.bar_result is not None
    assert descriptor.bar_result.series[('a', 'bus')][0].value == 11
    assert descriptor.bar_result.series[('a', 'bus')][0].observed == D(2024, 1, 2)
    assert descriptor.bar_result.series[('b', 'tram')][0].value == 19


def test_period_quantity_bar_uses_each_window_end_and_excludes_later_values():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('linecount', 'a', hour, amount, day=day)
            for day, hour, amount in [(1, 0, 10), (1, 1, 20),
                                      (2, 0, 30), (2, 1, 40), (2, 2, 999)]]
    network = build_network_snapshot(dashboard(rows, ('a',)),
                                     NetworkOptions(mode='period'), NAMES)
    descriptor = chart(network, 'linecount', 'a')
    current = descriptor.bar_result.series[('a', 'bus')][0]
    compared = descriptor.bar_result.comparison[('a', 'bus')][0]
    assert (current.value, current.observed) == (Decimal(40), D(2024, 1, 2, 1))
    assert (compared.value, compared.observed) == (Decimal(20), D(2024, 1, 1, 1))
    assert [bucket.value for bucket in descriptor.result.series[('a', '总计')]] == [30, 40]


def test_quantity_bar_marks_category_with_older_endpoint_incomplete():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('linecount', 'a', 0, 10, group='bus'),
            history('linecount', 'a', 1, 12, group='bus'),
            history('linecount', 'a', 0, 4, group='tram')]
    descriptor = chart(build_network_snapshot(dashboard(rows, ('a',)),
                                              NetworkOptions(), NAMES), 'linecount')
    bus = descriptor.bar_result.series[('a', 'bus')][0]
    tram = descriptor.bar_result.series[('a', 'tram')][0]
    assert (bus.value, bus.observed, bus.complete) == (12, D(2024, 1, 2, 1), True)
    assert (tram.value, tram.observed, tram.complete) == (4, D(2024, 1, 2), False)


def test_vehicle_bar_uses_last_observed_hour_not_interval_average():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('vehicles-running', 'a', 0, 2 * 1024),
            history('vehicles-running', 'a', 1, 8 * 1024)]
    network = build_network_snapshot(dashboard(rows, ('a',), grain='day'),
                                     NetworkOptions(), NAMES)
    descriptor = chart(network, 'vehicles-running')
    assert descriptor.result.series[('a', '总计')][0].value == Decimal(5)
    assert descriptor.bar_result.series[('a', 'bus')][0].value == Decimal(8)
    assert descriptor.bar_result.series[('a', 'bus')][0].observed == D(2024, 1, 2, 1)


def test_missing_current_vehicle_demand_does_not_disable_average_history():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('vehicles-running', 'a', 0, 2 * 1024),
            history('vehicles-running', 'a', 1, 9 * 1024)]
    network = build_network_snapshot(dashboard(rows, ('a',)), NetworkOptions(vehicle='maximum'), NAMES)
    maximum = value(network.summaries[0], 2)
    assert maximum.value is None and maximum.reason
    assert chart(network, 'vehicles-running').result is not None
    assert not chart(network, 'vehicles-running').reason
    assert [b.value for b in chart(network, 'vehicles-running').result.series[('a', '总计')]] == [2, 9]


def test_summary_switches_keep_six_positions_and_separate_flow_metrics():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history(metric, 'a', 0, count)
            for metric, count in [('depotcount', 4), ('vehicles-running', 2 * 1024),
                                  ('transport-by-type', 100), ('trip-types', 80)]]
    rows.append(row('public-transport', 'Student', START, 60, 100))
    network = build_network_snapshot(dashboard(rows, ('a',)),
                                     NetworkOptions(passenger='trip-types'), NAMES)
    summary = network.summaries[0]
    assert tuple(item.metric_id for item in summary.values) == (
        'linecount', 'depotcount', 'vehicles-running', 'coverage', 'trip-types',
        'transfer-coefficient')
    assert summary.values[1].value == 4
    assert summary.values[4].value == 60
    assert chart(network, 'transport-by-type').result.series
    assert chart(network, 'trip-types').result.series


def test_company_share_is_unavailable_when_selected_company_has_no_history():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('transport-by-type', 'a', 0, 100)]
    network = build_network_snapshot(dashboard(rows), NetworkOptions(mode='companies'), NAMES)
    shares = chart(network, 'company-passengers')
    assert shares.result is None
    assert shares.reason


def test_company_share_uses_only_hours_with_all_selected_company_values():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('transport-by-type', 'a', 0, 10),
            history('transport-by-type', 'a', 1, 20),
            history('transport-by-type', 'b', 0, 30)]
    source = dashboard(rows)
    network = build_network_snapshot(source, NetworkOptions(mode='companies'), NAMES)
    shares = chart(network, 'company-passengers')
    assert shares.result is not None
    assert [b.value for b in shares.result.series[('a', '总计')]] == [10, None]
    assert [b.value for b in shares.result.series[('b', '总计')]] == [30, None]
    assert shares.reason
    assert source.results['transport-by-type'].series[('a', '总计')][1].value == 20


def test_company_share_rejects_history_only_in_comparison_window():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('transport-by-type', 'a', 0, 10),
            history('transport-by-type', 'b', 0, 30, day=1)]
    network = build_network_snapshot(dashboard(rows), NetworkOptions(mode='companies'), NAMES)
    shares = chart(network, 'company-passengers')
    assert shares.result is None
    assert shares.reason


def test_period_without_comparison_reports_missing_period_without_inventing_it():
    from network_model import NetworkOptions, build_network_snapshot

    rows = [history('linecount', 'a', 0, 5)]
    network = build_network_snapshot(dashboard(rows, ('a',), comparison=None),
                                     NetworkOptions(mode='period'), NAMES)
    descriptor = chart(network, 'linecount', 'a')
    assert descriptor.result.query.comparison is None
    assert descriptor.result.comparison == {}
    assert descriptor.reason


def test_chart_capabilities_reflect_grain_without_removing_cards():
    from network_model import NetworkOptions, build_network_snapshot

    network = build_network_snapshot(dashboard([]), NetworkOptions(), NAMES)
    assert chart(network, 'linecount').allowed_modes == ('bar',)
    assert chart(network, 'stopcount').allowed_modes == ('bar',)
    assert 'coverage' not in {item.key for item in network.charts}
    for key in ('transport-by-type', 'transport-by-group', 'trip-types'):
        assert chart(network, key).allowed_modes == ('trend-bar', 'pie')
    daily = build_network_snapshot(dashboard([], ('a',), grain='day'), NetworkOptions(), NAMES)
    assert chart(daily, 'linecount').allowed_modes == ('line', 'bar')
    assert chart(daily, 'coverage').allowed_modes == ('line',)


def test_build_network_snapshot_observes_cancellation():
    from network_model import NetworkOptions, build_network_snapshot

    calls = 0
    def cancelled():
        nonlocal calls
        calls += 1
        return calls > 3

    with pytest.raises(QueryCancelled):
        build_network_snapshot(dashboard([]), NetworkOptions(), NAMES, cancelled)
    assert calls == 4
