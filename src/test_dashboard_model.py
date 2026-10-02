from datetime import datetime as D, timedelta
from decimal import Decimal
from dataclasses import FrozenInstanceError

import pytest
from statistics_model import (HistoryStore, Query, METRICS, BOARDS, NO_GROUP_TOTAL,
                              QueryCancelled, summarize_buckets, alerts_for_result)
from test_statistics_model import row


def transfer_rows(company='p1'):
    return [row(metric, group, D(2024, 1, 1, h), value, company=company)
            for h, segments, trips in [(0, 10, 0), (1, 20, 10)]
            for metric, group, value in [('transport-by-type', 'bus', segments),
                                         ('trip-types', 'single-line', trips)]]


def coefficient(store, grain='hour', comparison=None):
    return store.query(Query('transfer-coefficient', ('p1',), '__total__',
                            D(2024, 1, 1), D(2024, 1, 1, 2), grain, comparison))


def test_transfer_registered_and_weighted_even_with_zero_hour_denominator():
    store = HistoryStore(transfer_rows(), D(2024, 1, 2))
    assert 'transfer-coefficient' in BOARDS['客流数据']
    for grain in ('hour', 'day', 'week', 'month'):
        result = coefficient(store, grain)
        buckets = result.series[('p1', '总计')]
        assert summarize_buckets(buckets, result.metric) == Decimal(3)
        assert sum(b.numerator for b in buckets) == 30
        assert sum(b.denominator for b in buckets) == 10
        assert len([r for b in buckets for r in b.raw]) == 4
    buckets = coefficient(store).series[('p1', '总计')]
    assert buckets[0].value is None
    assert buckets[0].complete
    assert buckets[1].value == 2


def test_transfer_missing_source_not_zero_or_mismatched_range():
    rows = transfer_rows()[1:]
    store = HistoryStore(rows, D(2024, 1, 2))
    for grain in ('hour', 'day'):
        result = coefficient(store, grain)
        assert summarize_buckets(result.series[('p1', '总计')], result.metric) is None
        assert not result.series[('p1', '总计')][0].complete


def test_transfer_keeps_partial_current_slot_and_unclipped_ratio():
    rows = [row(m, g, D(2024, 1, 1), v, company='p1', current=True)
            for m, g, v in [('transport-by-type', 'bus', 1), ('trip-types', 'one-zone', 4)]]
    result = coefficient(HistoryStore(rows, D(2024, 1, 1, 0, 30)))
    bucket = result.series[('p1', '总计')][0]
    assert bucket.value == Decimal('.25')
    assert not bucket.complete
    assert alerts_for_result(result) == []


def test_default_and_dashboard_contract_company_isolation_and_breakdowns():
    from dashboard_model import FilterState, build_dashboard, default_window
    assert default_window(D(2024, 3, 1, 13)) == (D(2024, 2, 19), D(2024, 2, 26))
    rows = transfer_rows() + transfer_rows('p2')
    rows += [row('cashflow', 'bus', D(2024, 1, 1), -100, company='p1'),
             row('stopcount', 'bus', D(2024, 1, 1), 3, company='p1'),
             row('stopcount', 'tram', D(2024, 1, 1), 4, company='p1'),
             row('population', 'Student', D(2024, 1, 1), 99)]
    store = HistoryStore(rows, D(2024, 1, 2))
    filters = FilterState(('p1', 'p2'), D(2024, 1, 1), D(2024, 1, 1, 2), 'hour')
    with pytest.raises(FrozenInstanceError):
        filters.grain = 'day'
    result = build_dashboard(store, filters)
    expected = {m for board in BOARDS.values() for m in board}
    assert set(result.results) == set(result.breakdowns) == expected
    assert set(result.results['transfer-coefficient'].series) == {('p1', '总计'), ('p2', '总计')}
    assert result.results['cashflow'].series[('p1', '总计')][0].value == -1
    assert set(result.results['stopcount'].series) == {('p1', 'bus'), ('p1', 'tram')}
    assert list(result.results['population'].series) == [('', '总计')]
    for metric in expected:
        assert result.breakdowns[metric].query.group is None
        assert result.results[metric].query.group == (None if metric in NO_GROUP_TOTAL else '__total__')
    empty = build_dashboard(store, FilterState((), filters.start, filters.end, 'hour'))
    assert all(not r.series and not r.comparison for r in empty.results.values() if r.metric.scope == 'company')
    assert empty.results['population'].series


def test_dashboard_alerts_all_boards_deduplicate_city_modes_and_cancel():
    from dashboard_model import FilterState, build_dashboard
    rows = [row(metric, group, D(2024, 1, day), value, divider, company)
            for day, value in [(1, 200), (2, 500)]
            for metric, group, divider, company in [('cashflow', 'bus', 0, 'p1'),
                ('linecount', 'bus', 0, 'p1'), ('transport-by-type', 'bus', 0, 'p1'),
                ('trip-types', 'one-zone', 0, 'p1'), ('public-transport', 'Student', 1000, '')]]
    store = HistoryStore(rows, D(2024, 1, 3))
    filters = FilterState(('p1',), D(2024, 1, 2), D(2024, 1, 2, 1), 'hour',
                          (D(2024, 1, 1), D(2024, 1, 1, 1)))
    result = build_dashboard(store, filters)
    assert {a.metric for a in result.alerts} == {'cashflow', 'linecount', 'transport-by-type', 'trip-types', 'public-transport'}
    assert build_dashboard(store, filters, thresholds=(100, 1000, 1000)).alerts == []
    calls = 0
    def cancelled():
        nonlocal calls
        calls += 1
        return calls > 8
    with pytest.raises(QueryCancelled):
        build_dashboard(store, filters, cancelled=cancelled)
    assert calls == 9
    assert build_dashboard(store, filters).filters == filters


def test_transfer_zero_denominator_with_mismatched_hours_stays_missing():
    rows = [row('transport-by-type', 'bus', D(2024, 1, 1), 10, company='p1'),
            row('trip-types', 'one-zone', D(2024, 1, 1, 1), 0, company='p1')]
    result = coefficient(HistoryStore(rows, D(2024, 1, 2)), 'day')
    # A later valid bucket must not conceal the unmatched observations.
    valid = coefficient(HistoryStore(transfer_rows(), D(2024, 1, 2))).series[('p1', '总计')][1]
    assert summarize_buckets(result.series[('p1', '总计')] + [valid], result.metric) is None


def test_real_multiplayer_history_recomputes_totals_without_merging_companies():
    import csv
    from pathlib import Path
    paths = list((Path(__file__).resolve().parents[1] / 'exports').glob('*指标_完整_quicksave*.csv'))
    if not paths:
        pytest.skip('Optional real-save CSV is absent')
    rows = list(csv.DictReader(paths[0].open(encoding='utf-8-sig')))
    times = [D.fromisoformat(r['模拟时间']) for r in rows]
    start, end = min(times), max(times) + timedelta(hours=1)
    store = HistoryStore(rows, end)
    for grain in ('hour', 'day', 'week', 'month'):
        result = store.query(Query('transfer-coefficient', (), '__total__', start, end, grain))
        assert len(result.series) == 2
        for (company, _), buckets in result.series.items():
            totals = {m: sum(r.value for (name, owner, _), records in store.series.items()
                             if name == m and owner == company for r in records)
                      for m in ('transport-by-type', 'transport-by-group', 'trip-types')}
            assert totals['transport-by-type'] == totals['transport-by-group']
            assert summarize_buckets(buckets, result.metric) == Decimal(totals['transport-by-type']) / totals['trip-types']


def test_transfer_comparison_preserved_but_no_directional_alert():
    rows = [row(m, g, D(2024, 1, day), value, company='p1')
            for day, segments in [(1, 10), (2, 50)]
            for m, g, value in [('transport-by-type', 'bus', segments), ('trip-types', 'one-zone', 10)]]
    result = HistoryStore(rows, D(2024, 1, 3)).query(Query(
        'transfer-coefficient', ('p1',), None, D(2024, 1, 2), D(2024, 1, 2, 1), 'hour',
        (D(2024, 1, 1), D(2024, 1, 1, 1))))
    assert result.series[('p1', '总计')][0].value == 5
    assert result.comparison[('p1', '总计')][0].value == 1
    assert alerts_for_result(result) == []


def test_ratio_flow_includes_zero_denominator_numerator_without_filling_missing():
    rows = [row('monthly-ticket', 'Student', D(2024, 1, 1, h), n, d, 'p1')
            for h, n, d in [(0, 10, 0), (1, 20, 10)]]
    store = HistoryStore(rows, D(2024, 1, 2))
    for grain in ('hour', 'day', 'week', 'month'):
        result = store.query(Query('monthly-ticket', ('p1',), '__total__', D(2024, 1, 1), D(2024, 1, 1, 3), grain))
        assert summarize_buckets(result.series[('p1', '总计')], result.metric) == 300
    hour = store.query(Query('monthly-ticket', ('p1',), '__total__', D(2024, 1, 1), D(2024, 1, 1, 3), 'hour'))
    assert hour.series[('p1', '总计')][0].value is None
    assert hour.series[('p1', '总计')][2].numerator is None
    assert summarize_buckets(hour.series[('p1', '总计')][:1], hour.metric) is None


def test_load_session_duplicate_names_use_identity_for_every_join(tmp_path, monkeypatch):
    from report_model import load_session
    fixtures = {'CIM2_公司信息': [{'公司名称': 'same', '玩家ID': p, '公司序号': str(i)} for i,p in enumerate(('a','b'))]}
    for stem in ('CIM2_线路客流_完整导出', 'CIM2_公司车型数据', 'CIM2_发班信息_完整导出',
                 'CIM2_发班记录_完整导出', 'CIM2_线路站点客流分布_当前', 'CIM2_配车信息_完整导出'):
        fixtures[stem] = [{'公司名称':'same', '公司序号':str(i), '线路类型':'bus', '车型类型':'bus',
            '线路号':'1', '客流_今日':str(v), '收入累计':str(v*100), '时刻表序号':'0', '运行日掩码':'127',
            '发班时间':f'0{i+1}:00', '站点客流_今日':str(v), '车辆客流_今日':str(v)} for i,v in enumerate((10,20))]
    fixtures['CIM2_城市历史指标_完整'] = [dict(row('cashflow','bus',D(2024,1,1),100), 公司名称='same', 公司序号='0'),
        dict(row('cashflow','bus',D(2024,1,1),200), 公司名称='same', 玩家ID='b', 公司序号='0'),
        dict(row('cashflow','bus',D(2024,1,1),900), 公司名称='same')]
    monkeypatch.setattr('report_model.read_csv', lambda folder,stem,tag: fixtures.get(stem,[]))
    session = load_session(tmp_path, 'fixture')
    assert [(c['公司标识'],c['线路数'],c['总客流']) for c in session['companies']] == [('a',1,10),('b',1,20)]
    assert len({l['key'] for l in session['lines']}) == 2
    for c,l,v in zip(session['companies'],session['lines'],(10,20)):
        assert l['公司标识'] == c['公司标识']
        assert l['原始公司名称'] == c['原始公司名称'] == 'same'
        assert c['财务汇总']['每周收入'] == v
        assert c['客流排行']['综合'][0]['value'] == v
        assert l['站点客流'][0]['今日客流'] == v
        assert l['车辆'][0]['今日客流'] == v
        assert len(l['班次']['周一至周四']) == 1
    assert [r['公司标识'] for r in session['history'][:2]] == ['a','b']
    assert session['history'][2]['公司标识'] not in ('a','b')


@pytest.mark.parametrize('folder,tag,expected', [
    ('D:/test/CIM2_SaveStats/jobs/frozen-秋山市n4', '秋山市n4_运行时', {'76561198845688243':'3.1513'}),
    ('D:/test/CIM2_SaveStats/exports', 'quicksave.76561198362520556-76561198845688243_运行时',
     {'76561198362520556':'2.6771','76561198845688243':'2.4776'})])
def test_real_load_session_dashboard_identity_chain(folder, tag, expected):
    from pathlib import Path
    from report_model import load_session
    from dashboard_model import FilterState, build_dashboard
    if not (Path(folder) / f'CIM2_公司信息_{tag}.csv').exists():
        pytest.skip('Optional frozen real-save fixture is absent')
    session = load_session(Path(folder), tag)
    store = HistoryStore(session['history'], session['simulation_time'])
    start = min(r.time for records in store.series.values() for r in records)
    # Frozen single metadata is newer than its exported history. The audited
    # reference range ends before that history's current slot, not today's UI default.
    end = min(r.time for (metric, _, _), records in store.series.items()
              if metric in ('transport-by-type', 'trip-types') for r in records if r.current)
    for grain in ('hour','day','week','month'):
        snapshot = build_dashboard(store, FilterState(tuple(c['公司标识'] for c in session['companies']),start,end,grain))
        result = snapshot.results['transfer-coefficient']
        assert set(k[0] for k in result.series) == set(expected)
        for company, value in expected.items():
            assert summarize_buckets(result.series[(company,'总计')],result.metric).quantize(Decimal('.0001')) == Decimal(value)
            group = snapshot.results['transport-by-group']
            mode = snapshot.results['transport-by-type']
            assert summarize_buckets(group.series[(company,'总计')],group.metric) == summarize_buckets(mode.series[(company,'总计')],mode.metric)
            assert snapshot.results['cashflow'].series[(company,'总计')]


@pytest.mark.parametrize('metric,divider,expected', [('linecount',0,10), ('reputation',100,10)])
def test_stock_total_uses_one_observation_time_across_grains(metric, divider, expected):
    rows = [row(metric, g, D(2024,1,1,h),v,divider,'p1')
            for g,h,v in [('bus',0,5),('bus',1,10),('tram',0,100)]]
    store = HistoryStore(rows,D(2024,1,2))
    for grain in ('hour','day','week','month'):
        result = store.query(Query(metric,('p1',),'__total__',D(2024,1,1),D(2024,1,1,2),grain))
        assert summarize_buckets(result.series[('p1','总计')],result.metric) == expected
        assert not result.series[('p1','总计')][-1].complete


def test_ratio_stock_final_zero_denominator_does_not_reuse_earlier_ratio():
    rows = [row('reputation','bus',D(2024,1,1,h),n,d,'p1') for h,n,d in [(0,10,100),(1,20,0)]]
    store = HistoryStore(rows,D(2024,1,2))
    for grain in ('hour','day','week','month'):
        result = store.query(Query('reputation',('p1',),'__total__',D(2024,1,1),D(2024,1,1,2),grain))
        assert summarize_buckets(result.series[('p1','总计')],result.metric) is None
