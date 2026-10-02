from datetime import datetime as D
from decimal import Decimal
import csv
import sys
from pathlib import Path
import pytest

from statistics_model import (
    HistoryStore, Query, compare_window, period_bounds, calculate_transfer_coefficient,
    alerts_for_result, summarize_buckets, QueryCancelled,
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from report_model import load_session


def row(metric, group, hour, value, divider=0, company='', current=False):
    return {'指标': metric, '分组': group, '模拟时间': hour.strftime('%Y-%m-%d %H:%M:%S'),
            '值': str(value), '分母': str(divider), '公司标识': company,
            '公司名称': company, '当前槽位': str(current)}


def test_natural_periods_and_calendar_compare():
    assert period_bounds(D(2024, 2, 29, 18), 'week') == (D(2024, 2, 26), D(2024, 3, 4))
    assert period_bounds(D(2024, 2, 29, 18), 'month') == (D(2024, 2, 1), D(2024, 3, 1))
    assert compare_window(D(2024, 3, 31, 8), D(2024, 4, 2, 8), 'previous_month') == (
        D(2024, 2, 29, 8), D(2024, 3, 2, 8))
    assert period_bounds(D(2023, 12, 31, 23), 'week') == (D(2023, 12, 25), D(2024, 1, 1))
    assert period_bounds(D(2023, 12, 31, 23), 'month') == (D(2023, 12, 1), D(2024, 1, 1))


def test_flow_sum_ratio_weight_and_stock_end():
    rows = [row('trip-number', 'Student', D(2024, 1, 1, h), v) for h, v in [(0, 3), (1, 5)]]
    rows += [row('monthly-ticket', 'Student', D(2024, 1, 1, h), n, d)
             for h, n, d in [(0, 1, 2), (1, 8, 10)]]
    rows += [row('linecount', 'bus', D(2024, 1, 1, h), v, company='p1')
             for h, v in [(0, 2), (1, 4)]]
    store = HistoryStore(rows, D(2024, 1, 1, 2))
    q = lambda metric, company=(): store.query(Query(metric, company, None, D(2024, 1, 1), D(2024, 1, 1, 2), 'day'))
    assert q('trip-number').series[('', 'Student')][0].value == 8
    assert q('monthly-ticket').series[('', 'Student')][0].value == 75
    assert q('linecount', ('p1',)).series[('p1', 'bus')][0].value == 4


def test_company_value_history_is_already_in_currency_units():
    store = HistoryStore([row('company-value', group, D(2013, 4, 10, 23), value, company='p1')
                          for group, value in [('net-cash', 10000000), ('infra-value', 1000000),
                                               ('vehicles-value', 400000), ('business-value', 652183)]],
                         D(2013, 4, 10, 23, 59))
    result = store.query(Query('company-value', ('p1',), '__total__',
                               D(2013, 4, 10, 23), D(2013, 4, 11), 'hour'))
    assert result.series[('p1', '总计')][0].value == 12052183


def test_partial_current_hour_average_and_flow_rate_are_grain_invariant():
    rows = [row('vehicles-running', 'bus', D(2024, 1, 1, 0), 1024, company='p1'),
            row('vehicles-running', 'bus', D(2024, 1, 1, 1), 9216, company='p1', current=True),
            row('cashflow', 'bus', D(2024, 1, 1, 0), 100, company='p1'),
            row('cashflow', 'bus', D(2024, 1, 1, 1), 900, company='p1', current=True)]
    store = HistoryStore(rows, D(2024, 1, 1, 1, 30))
    for metric, expected in [('vehicles-running', Decimal(5)), ('cashflow', Decimal(10))]:
        query = lambda grain: Query(metric, ('p1',), None, D(2024, 1, 1), D(2024, 1, 1, 2), grain)
        by_hour = store.query(query('hour')).series[('p1', 'bus')]
        by_day = store.query(query('day')).series[('p1', 'bus')]
        assert summarize_buckets(by_hour, store.query(query('hour')).metric) == expected
        assert summarize_buckets(by_day, store.query(query('day')).metric) == expected
        assert sum(b.effective_hours for b in by_hour) == sum(b.effective_hours for b in by_day) == 2
        assert all(not b.complete for b in by_day)


def test_company_total_sums_modes_without_merging_companies():
    rows = [row('cashflow', mode, D(2024, 1, 1), value, company=company)
            for company, mode, value in [('p1', 'bus', 100), ('p1', 'tram', -30), ('p2', 'bus', 500)]]
    result = HistoryStore(rows, D(2024, 1, 1, 1)).query(
        Query('cashflow', ('p1', 'p2'), '__total__', D(2024, 1, 1), D(2024, 1, 1, 1), 'hour'))
    assert result.series[('p1', '总计')][0].value == Decimal('0.7')
    assert result.series[('p2', '总计')][0].value == Decimal('5')


def test_coverage_any_group_is_company_total_without_double_counting_categories():
    at = D(2024, 1, 1)
    rows = [row('coverage', group, at, value, divider, company)
            for company, group, value, divider in (
                ('p1', 'WhiteCollar', 30, 50), ('p1', 'Student', 20, 50),
                ('p2', 'WhiteCollar', 40, 50), ('p2', 'Student', 30, 50))]
    rows.extend({**row('coverage', '任意', at, value, 100, company), '分组层级': '总计'}
                for company, value in (('p1', 50), ('p2', 70)))
    store = HistoryStore(rows, D(2024, 1, 1, 1))
    total = store.query(Query('coverage', ('p1', 'p2'), '__total__',
                              at, D(2024, 1, 1, 1), 'hour'))
    assert total.series[('p1', '总计')][0].value == 50
    assert total.series[('p1', '总计')][0].numerator == 50
    assert total.series[('p2', '总计')][0].value == 70
    assert total.series[('p2', '总计')][0].denominator == 100
    categories = store.query(Query('coverage', ('p1', 'p2'), None,
                                   at, D(2024, 1, 1, 1), 'hour'))
    assert {group for _, group in categories.series} == {'WhiteCollar', 'Student'}


def test_missing_zero_negative_and_company_isolation():
    rows = [row('cashflow', 'bus', D(2024, 1, 1, 0), 0, company='p1'),
            row('cashflow', 'bus', D(2024, 1, 1, 0), 500, company='p2'),
            row('satisfaction-speed', 'Student', D(2024, 1, 1, 0), -50, 100, company='p1')]
    store = HistoryStore(rows, D(2024, 1, 1, 2))
    query = Query('cashflow', ('p1', 'p2'), None, D(2024, 1, 1), D(2024, 1, 1, 2), 'hour')
    result = store.query(query)
    assert result.series[('p1', 'bus')][0].value == 0
    assert result.series[('p2', 'bus')][0].value == 5
    assert result.series[('p1', 'bus')][1].value is None
    assert store.query(Query('satisfaction-speed', ('p1',), None, query.start, query.end, 'hour')).series[('p1', 'Student')][0].value == -50


def test_recorded_cycle_values_are_summed_even_after_counter_reset():
    rows = [row('trip-number', 'Student', D(2024, 1, 1, 0), 100),
            row('trip-number', 'Student', D(2024, 1, 1, 1), 2)]
    result = HistoryStore(rows, D(2024, 1, 1, 2)).query(
        Query('trip-number', (), None, D(2024, 1, 1), D(2024, 1, 1, 2), 'day'))
    assert result.series[('', 'Student')][0].value == 102


def test_zero_divider_is_not_zero_ratio():
    rows = [row('monthly-ticket', 'Student', D(2024, 1, 1), 0, 0, 'p1')]
    bucket = HistoryStore(rows, D(2024, 1, 1, 1)).query(
        Query('monthly-ticket', ('p1',), None, D(2024, 1, 1), D(2024, 1, 1, 1), 'hour')).series[('p1', 'Student')][0]
    assert bucket.value is None
    assert bucket.numerator == 0


def test_future_and_partial_current_slot():
    rows = [row('trip-number', 'Student', D(2024, 1, 1, 0), 7),
            row('trip-number', 'Student', D(2024, 1, 1, 1), 4, current=True),
            row('trip-number', 'Student', D(2024, 1, 1, 2), 900)]
    store = HistoryStore(rows, D(2024, 1, 1, 1, 30))
    result = store.query(Query('trip-number', (), None, D(2024, 1, 1), D(2024, 1, 1, 3), 'hour'))
    buckets = result.series[('', 'Student')]
    assert [b.value for b in buckets] == [7, 4, None]
    assert [b.complete for b in buckets] == [True, False, False]


def test_transfer_requires_same_scope_and_nonzero_denominator():
    assert calculate_transfer_coefficient(300, 200, 'city', 'city') == (1.5, 0.5)
    assert calculate_transfer_coefficient(300, 0, 'city', 'city') is None
    assert calculate_transfer_coefficient(300, 200, 'p1', 'city') is None


def test_alert_suppression_and_cross_zero():
    rows = [row('cashflow', 'bus', D(2024, 1, 1, 0), 500, company='p1'),
            row('cashflow', 'bus', D(2024, 1, 2, 0), -100, company='p1')]
    store = HistoryStore(rows, D(2024, 1, 3))
    result = store.query(Query('cashflow', ('p1',), None, D(2024, 1, 2), D(2024, 1, 2, 1), 'hour',
                               (D(2024, 1, 1), D(2024, 1, 1, 1))))
    assert any('转负' in a.reason for a in alerts_for_result(result))
    assert alerts_for_result(result)[0].metric == 'cashflow'


def test_ratio_alert_reweights_across_hours_instead_of_summing_percentages():
    rows = [row('monthly-ticket', 'Student', D(2024, 1, 1, 0), 1, 2, 'p1'),
            row('monthly-ticket', 'Student', D(2024, 1, 1, 1), 90, 100, 'p1'),
            row('monthly-ticket', 'Student', D(2024, 1, 2, 0), 0, 2, 'p1'),
            row('monthly-ticket', 'Student', D(2024, 1, 2, 1), 90, 100, 'p1')]
    store = HistoryStore(rows, D(2024, 1, 3))
    result = store.query(Query('monthly-ticket', ('p1',), None, D(2024, 1, 2), D(2024, 1, 2, 2),
                               'hour', (D(2024, 1, 1), D(2024, 1, 1, 2))))
    assert alerts_for_result(result, percentage_points=5) == []
    assert summarize_buckets(result.comparison[('p1', 'Student')], result.metric) == Decimal(91) * 100 / 102


def test_ratio_alert_uses_only_percentage_point_threshold():
    rows = [row('monthly-ticket', 'Student', D(2024, 1, 1), 1, 100, 'p1'),
            row('monthly-ticket', 'Student', D(2024, 1, 2), 2, 100, 'p1')]
    result = HistoryStore(rows, D(2024, 1, 3)).query(
        Query('monthly-ticket', ('p1',), None, D(2024, 1, 2), D(2024, 1, 2, 1), 'hour',
              (D(2024, 1, 1), D(2024, 1, 1, 1))))
    assert alerts_for_result(result, percentage_points=5) == []
    assert len(alerts_for_result(result, percentage_points=1)) == 1


def test_superseded_query_exits_before_aggregating():
    store = HistoryStore([row('cashflow', 'bus', D(2024, 1, 1), 100, company='p1')], D(2024, 1, 2))
    with pytest.raises(QueryCancelled):
        store.query(Query('cashflow', ('p1',), None, D(2024, 1, 1), D(2024, 1, 2), 'hour'),
                    cancelled=lambda: True)


def test_partial_window_suppresses_threshold_at_boundary():
    rows = [row('trip-number', 'Student', D(2024, 1, 1), 100),
            row('trip-number', 'Student', D(2024, 1, 2), 120)]
    store = HistoryStore(rows, D(2024, 1, 3))
    whole = store.query(Query('trip-number', (), None, D(2024, 1, 2), D(2024, 1, 2, 1),
                              'hour', (D(2024, 1, 1), D(2024, 1, 1, 1))))
    assert len(alerts_for_result(whole, relative_percent=20, passenger_absolute=20)) == 1
    partial = store.query(Query('trip-number', (), None, D(2024, 1, 2), D(2024, 1, 2, 2),
                                'hour', (D(2024, 1, 1), D(2024, 1, 1, 2))))
    assert alerts_for_result(partial, relative_percent=20, passenger_absolute=20) == []


def test_session_keeps_full_history_and_stable_owner(tmp_path):
    def write(stem, rows):
        path = tmp_path / f'{stem}_fixture.csv'
        with path.open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    write('CIM2_公司信息', [{'公司名称': 'same', '玩家ID': 'a', '公司序号': '0'},
                             {'公司名称': 'same', '玩家ID': 'b', '公司序号': '1'}])
    write('CIM2_城市历史元数据', [{'模拟当前时间': '2024-01-01 02:00:00', '模拟开始': '2024-01-01 00:00:00'}])
    write('CIM2_城市历史指标_完整', [row('cashflow', 'bus', D(2024, 1, 1), 100, company='a'),
                                       row('cashflow', 'tram', D(2024, 1, 1), 200, company='b')])
    session = load_session(tmp_path, 'fixture')
    assert len(session['history']) == 2
    assert {x['公司标识'] for x in session['history']} == {'a', 'b'}
    assert [x['公司标识'] for x in session['companies']] == ['a', 'b']
    assert {x['分组'] for x in session['trends']} == {'bus', 'tram'}


def test_city_modes_keep_three_independent_unormalized_series():
    rows = [row(metric, 'Student', D(2024, 1, 1), value, 100)
            for metric, value in [('public-transport', 20), ('private-motoring', 30), ('walking', 40)]]
    store = HistoryStore(rows, D(2024, 1, 1, 1))
    result = store.query(Query('city-mode-share', ('irrelevant-company',), '__total__',
                               D(2024, 1, 1), D(2024, 1, 1, 1), 'hour'))
    assert sorted(b[0].value for b in result.series.values()) == [20, 30, 40]


@pytest.mark.parametrize('metric', ['economy', 'energy-prices', 'traffic-density', 'stopcount'])
def test_incompatible_groups_cannot_be_totaled(metric):
    store = HistoryStore([], D(2024, 1, 1, 1))
    with pytest.raises(ValueError, match='分组'):
        store.query(Query(metric, (), '__total__', D(2024, 1, 1), D(2024, 1, 1, 1), 'hour'))
