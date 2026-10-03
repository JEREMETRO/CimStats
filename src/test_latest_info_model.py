"""Independent arithmetic and scope checks for the latest-information snapshot."""
from copy import deepcopy
from datetime import datetime as D
from decimal import Decimal
import importlib
import importlib.util

import pytest

from statistics_model import QueryCancelled


def build(data, *args, **kwargs):
    # Missing feature is a deliberate assertion failure in the first RED run.
    assert importlib.util.find_spec('latest_info_model') is not None, 'latest-info model is missing'
    return importlib.import_module('latest_info_model').build_latest_info(data, *args, **kwargs)


def history(metric, value, divider=0, company='', hour=0, group='Student', current=False):
    return {'指标': metric, '值': str(value), '分母': str(divider),
            '公司标识': company, '分组': group, '模拟时间': f'2013-05-21 {hour:02}:00:00',
            '当前槽位': str(current)}


def line(key, company, mode, passengers, departures, minutes, km, speed, income, expense):
    return {'key': key, '公司标识': company, '公司名称': '同名公司', '运输制式': mode,
            '线路名称': key, '今日客流': passengers, '当日发班数': departures,
            '行车总时间': minutes, '单程时间': minutes / departures if departures else 0,
            '地图里程': km, '核定速度': speed,
            '每周收入': income, '每周支出': expense, '班次': {}, '班次数据完整': True}


@pytest.fixture
def data():
    first = line('a|bus|1', 'a', '公交', 100, 4, 80, 10, 30, 10, 4)
    first['班次'] = {'周一至周四': [{'time': t} for t in ('00:00', '00:20', '01:00')],
                     '周五': [{'time': t} for t in ('00:00', '01:00')],
                     '未启用': [{'time': t} for t in ('00:00', '23:00')],
                     '运行日未知': [{'time': t} for t in ('00:00', '22:00')]}
    return {'save_key': 'content-id', 'tag': 'save-file', 'simulation_time': '2013-05-21 02:30:00',
            'metadata': {'地图名称': '测试城市', '当前人口数': 12345},
            'companies': [{'公司标识': 'a', '公司名称': '同名公司', '车辆总数': 6,
                           '车队': {'公交': 4, '有轨电车': 2}},
                          {'公司标识': 'b', '公司名称': '同名公司', '车辆总数': 8,
                           '车队': {'公交': 8}}],
            'lines': [first, line('a|tram|2', 'a', '有轨电车', 10, 2, 40, 5, 20, 2, 1),
                      line('b|bus|1', 'b', '公交', 1000, 10, 300, 8, 40, 100, 20)],
            'history': [history('transport-by-type', 100, company='a', group='bus'),
                        history('trip-types', 20, company='a', group='OneZone'),
                        history('transport-by-type', 10, company='b', group='bus'),
                        history('trip-types', 10, company='b', group='OneZone'),
                        history('public-transport', 20, 100), history('public-transport', 90, 300, hour=2, current=True),
                        history('population', 54321)]}


def metrics(snapshot):
    return {value.key: value for value in snapshot.metrics}


def test_selected_company_and_mode_share_one_line_scope(data):
    snapshot = build(data, 'a', '公交')
    assert [r.key for r in snapshot.lines] == ['a|bus|1']
    assert [h.line.key for h in snapshot.highlights] == ['a|bus|1'] * 4
    assert [r.key for r in snapshot.passenger_top10] == ['a|bus|1']
    assert [(r.mode, r.value) for r in snapshot.departure_modes] == [('公交', 4)]
    assert [(r.mode, r.value) for r in snapshot.passenger_modes] == [('公交', 100)]
    assert snapshot.total_departures == 4
    assert [r.key for r in build(data, 'b', '公交').lines] == ['b|bus|1']
    assert snapshot.companies == (('a', '同名公司'), ('b', '同名公司'))
    assert set(snapshot.modes) == {'综合', '公交', '有轨电车'}


def test_original_eleven_metrics_use_line_and_complete_fleet_sources(data):
    values = build(data, 'a', '公交').metrics
    assert [v.key for v in values] == ['line-count', 'fleet', 'drive-minutes', 'turnover',
        'weekly-income', 'weekly-expense', 'profit', 'interval', 'speed',
        'passengers-per-run', 'passengers-per-km', 'public-transport-share', 'transfer-coefficient']
    assert [v.value for v in values[:11]] == [1, 4, 80, 1, 10, 4, 6, 40, 30, 25, Decimal('2.5')]
    all_values = metrics(build(data))
    assert all_values['fleet'].value == 14
    assert all_values['turnover'].value == Decimal(16) / 14
    assert all_values['passengers-per-run'].value == Decimal(1110) / 16
    assert all_values['passengers-per-km'].value == Decimal(1110) / 130
    assert all_values['profit'].value == 87
    assert all_values['drive-minutes'].value == 420
    assert all_values['speed'].value == Decimal(130) / 420 * 60


def test_speed_weights_plan_distance_and_time_instead_of_cached_speeds(data):
    data['lines'][0]['核定速度'] = 999
    data['lines'][1]['核定速度'] = 999
    values = metrics(build(data, 'a'))
    assert values['speed'].value == 25  # (4*10 + 2*5) / (4*20 + 2*20) * 60
    assert values['speed'].complete
    assert values['drive-minutes'].value == 120


@pytest.mark.parametrize('field,value', [('地图里程', None), ('地图里程', -1),
    ('单程时间', None), ('单程时间', 0), ('单程时间', -1),
    ('当日发班数', None), ('当日发班数', -1)])
def test_speed_uses_same_valid_line_set_for_both_totals(data, field, value):
    data['lines'][0][field] = value
    speed = metrics(build(data, 'a'))['speed']
    assert speed.value == 15  # Only tram: 2*5 km / (2*20 minutes) * 60.
    assert not speed.complete
    assert '1条线路' in speed.reason


def test_speed_respects_measurement_availability_and_real_zero(data):
    data['lines'][0]['字段可用性'] = {'地图里程': False}
    speed = metrics(build(data, 'a'))['speed']
    assert speed.value == 15 and not speed.complete
    data['lines'][0]['字段可用性'] = {'地图里程': True}
    data['lines'][0]['地图里程'] = 0
    speed = metrics(build(data, 'a', '公交'))['speed']
    assert speed.value == 0 and speed.complete
    data['lines'][0]['当日发班数'] = 0
    assert metrics(build(data, 'a', '公交'))['speed'].value is None


def test_drive_minutes_uses_plan_count_and_duration_not_cached_total(data):
    data['lines'][0]['行车总时间'] = 9999
    data['lines'][0]['当日发班数'] = 3
    values = metrics(build(data, 'a'))
    assert values['drive-minutes'].value == 100  # 3*20 + 2*20, not 20+20.
    assert values['drive-minutes'].complete
    data['lines'][0]['班次数据完整'] = False
    values = metrics(build(data, 'a', '公交'))
    assert values['drive-minutes'].value == 60 and not values['drive-minutes'].complete
    assert not values['speed'].complete
    data['lines'][0]['单程时间'] = None
    assert metrics(build(data, 'a', '公交'))['drive-minutes'].value is None
    data['lines'][0]['当日发班数'] = 0
    assert metrics(build(data, 'a', '公交'))['drive-minutes'].value == 0


@pytest.mark.parametrize('field,value', [('单程时间', None), ('单程时间', 0),
    ('单程时间', -1), ('当日发班数', None), ('当日发班数', -1)])
def test_drive_minutes_does_not_pad_missing_or_invalid_plan_inputs(data, field, value):
    data['lines'][0][field] = value
    result = metrics(build(data, 'a', '公交'))['drive-minutes']
    assert result.value is None and not result.complete
    assert '或' not in result.reason


def test_approved_metric_titles_and_business_descriptions(data):
    values = metrics(build(data, 'a', '公交'))
    assert values['profit'].title == '周利润'
    assert values['fleet'].reason == '所选车队该制式的车辆数量'
    assert values['interval'].reason == '所选线路运营时间内的平均间隔'
    assert values['speed'].reason == '所选线路的总运营里程数与计划班次总核定时间之比'
    assert values['turnover'].reason == '当日计划发班总数与车队车辆总数之比，反映平均每辆车每天的计划运行班次数'
    assert values['passengers-per-km'].reason == '当日累计客流与当日计划行驶总里程之比，反映线路车辆运营的乘客周转率，进而反映线路效益'
    for value in values.values():
        assert '旧首页' not in value.reason and '原始' not in value.reason
    assert '平均每位乘客单次行程的乘车次数' in values['transfer-coefficient'].reason
    assert '不随制式筛选' in values['transfer-coefficient'].reason


def test_missing_operation_reasons_identify_actual_source(data):
    data['lines'][0]['地图里程'] = None
    data['lines'][0]['每周收入'] = None
    values = metrics(build(data, 'a', '公交'))
    assert '地图里程缺失' in values['passengers-per-km'].reason
    assert '周收入缺失' in values['profit'].reason
    assert '缺少有效来源、有效相邻间隔或正分母' not in values['profit'].reason


def test_report_model_normalized_duration_and_distance_feed_home_metrics(tmp_path, monkeypatch):
    from test_line_schedule import session_fixture
    session = session_fixture(tmp_path, monkeypatch, departures=[
        {'发班时间': '06:00', '时刻表_运行日掩码': '2'},
        {'发班时间': '07:00', '时刻表_运行日掩码': '2'},
    ], line_extra={'地图里程': '5120000'})
    row = session['lines'][0]
    assert row['单程时间'] == 60  # 36,000,000,000 ticks = 60 minutes.
    assert row['行车总时间'] == 120
    assert row['地图里程'] == 10  # Existing map scale already includes x2.
    values = metrics(build(session))
    assert values['drive-minutes'].value == 120
    assert values['speed'].value == 10  # 20 km / 120 min * 60, no second x2.


def test_four_extremes_and_top10_use_real_filtered_lines(data):
    snapshot = build(data)
    assert [h.line.key for h in snapshot.highlights] == ['b|bus|1', 'a|tram|2', 'b|bus|1', 'a|tram|2']
    assert [h.title for h in snapshot.highlights] == ['当日最大客流线路', '当日最小客流线路', '当日最多班次线路', '当日最少班次线路']
    assert [r.key for r in snapshot.passenger_top10] == ['b|bus|1', 'a|bus|1', 'a|tram|2']
    assert snapshot.lines[0].passengers_per_departure == 25
    assert snapshot.lines[0].passengers_per_vehicle_km == Decimal('2.5')


def test_top10_retains_ten_rows_without_other_or_zero_padding(data):
    data['lines'] = [line(f'a|bus|{i}', 'a', '公交', i, i, i, 1, 20, 1, 0) for i in range(12)]
    snapshot = build(data, 'a')
    assert [r.passengers for r in snapshot.passenger_top10] == list(range(11, 1, -1))
    assert len(snapshot.lines) == 12
    assert snapshot.total_departures == 66


def test_overall_transfer_uses_combined_counts(data):
    all_value = metrics(build(data))['transfer-coefficient']
    assert all_value.value == Decimal(110) / 30
    assert metrics(build(data, 'a'))['transfer-coefficient'].value == 5
    assert metrics(build(data, 'b'))['transfer-coefficient'].value == 1
    selected_mode = metrics(build(data, 'a', '有轨电车'))['transfer-coefficient']
    assert selected_mode.value == 5
    assert '制式' in selected_mode.reason and '公司' in selected_mode.scope


def test_city_share_ignores_company_and_mode_filters(data):
    for company, mode in [('', '综合'), ('a', '公交'), ('b', '有轨电车')]:
        value = metrics(build(data, company, mode))['public-transport-share']
        assert value.value == Decimal('27.5')  # 110 / 400, not average(20%, 30%).
        assert '全市' in value.scope
        assert not value.complete


def test_missing_hour_and_zero_denominator_stay_missing(data):
    data['history'] = [history('transport-by-type', 0, company='a', group='bus'),
                       history('transport-by-type', 7, company='a', hour=2, group='bus', current=True),
                       history('trip-types', 0, company='a', group='OneZone'),
                       history('trip-types', 0, company='a', hour=2, group='OneZone', current=True),
                       history('public-transport', 9, 0)]
    snapshot = build(data, 'a', '公交')
    buckets = next(iter(snapshot.trend.series.values()))
    assert [b.value for b in buckets] == [0, None, 7]
    assert metrics(snapshot)['transfer-coefficient'].value is None
    assert metrics(snapshot)['public-transport-share'].value is None
    assert not buckets[-1].complete


def test_today_history_stops_at_simulation_clock(data):
    data['history'] += [history('transport-by-type', 9999, company='a', hour=3, group='bus'),
                        {**history('public-transport', 9999, 10000), '模拟时间': '2013-05-20 23:00:00'}]
    snapshot = build(data, 'a', '公交')
    assert snapshot.simulation_time == D(2013, 5, 21, 2, 30)
    buckets = next(iter(snapshot.trend.series.values()))
    assert [b.start for b in buckets] == [D(2013, 5, 21, h) for h in range(3)]
    assert snapshot.trend.current_window == (D(2013, 5, 21), D(2013, 5, 21, 2, 30))
    assert buckets[-1].end == D(2013, 5, 21, 2, 30)
    assert buckets[0].value == 100
    assert metrics(snapshot)['public-transport-share'].value == Decimal('27.5')


def test_trend_selected_mode_and_company_are_not_line_snapshot_counts(data):
    data['history'].append(history('transport-by-type', 15, company='a', group='tram'))
    snapshot = build(data, 'a', '有轨电车')
    assert next(iter(snapshot.trend.series.values()))[0].value == 15
    assert snapshot.passenger_modes[0].value == 10
    assert next(iter(build(data, 'a').trend.series.values()))[0].value == 115


def test_combined_trend_breaks_on_missing_company_hour(data):
    data['history'].append(history('transport-by-type', 25, company='a', hour=1, group='bus'))
    buckets = next(iter(build(data).trend.series.values()))
    assert [b.value for b in buckets] == [110, None, None]


def test_overall_trend_breaks_on_missing_serialized_mode_category(data):
    data['history'] += [history('transport-by-type', 15, company='a', group='tram'),
                        history('transport-by-type', 25, company='a', hour=1, group='bus')]
    buckets = next(iter(build(data, 'a').trend.series.values()))
    assert [b.value for b in buckets] == [115, None, None]
    selected = next(iter(build(data, 'a', '公交').trend.series.values()))
    assert [b.value for b in selected] == [100, 25, None]


def test_missing_city_label_population_and_clock_are_not_invented(data):
    data['metadata'] = {}
    data['history'] = []
    data.pop('simulation_time')
    snapshot = build(data)
    assert snapshot.city_name == '未提供城市名称'
    assert snapshot.population is None
    assert snapshot.simulation_time is None
    assert snapshot.trend is None
    assert snapshot.session_key == 'content-id'
    assert snapshot.save_name == '未提供存档名称'
    assert metrics(snapshot)['public-transport-share'].value is None


def test_population_uses_last_valid_city_observation_and_keeps_real_zero(data):
    data['metadata'] = {}
    data['history'] += [history('population', 17, hour=1), history('population', 0, hour=2),
                        history('population', 999, hour=3)]
    assert build(data).population == 0
    data['metadata']['当前人口数'] = 0
    assert build(data).population == 0


def test_empty_scope_does_not_pad_lines_or_invent_zero_operations(data):
    snapshot = build(data, 'unknown-company', '公交')
    assert snapshot.lines == snapshot.passenger_top10 == ()
    assert all(h.line is None for h in snapshot.highlights)
    assert snapshot.departure_modes == snapshot.passenger_modes == ()
    assert snapshot.total_departures is None
    assert all(v.value is None for v in snapshot.metrics if v.key not in ('line-count', 'public-transport-share'))
    assert metrics(snapshot)['line-count'].value == 0


def test_zero_fleet_departures_and_distance_do_not_create_zero_ratios(data):
    data['companies'][0]['车辆总数'] = 0
    data['lines'] = [line('zero', 'a', '公交', 0, 0, 0, 0, 0, 0, 0)]
    snapshot = build(data, 'a')
    values = metrics(snapshot)
    assert values['fleet'].value == values['weekly-income'].value == values['drive-minutes'].value == 0
    for key in ('turnover', 'interval', 'speed', 'passengers-per-run', 'passengers-per-km'):
        assert values[key].value is None
    assert snapshot.lines[0].passengers == 0
    assert snapshot.lines[0].passengers_per_departure is None


def test_missing_line_measurement_is_not_zero(data):
    data['lines'][0]['地图里程'] = 0
    data['lines'][0]['字段可用性'] = {'地图里程': False}
    data['lines'][0].pop('每周收入')
    snapshot = build(data, 'a', '公交')
    assert metrics(snapshot)['passengers-per-km'].value is None
    assert metrics(snapshot)['weekly-income'].value is None
    assert metrics(snapshot)['profit'].value is None


def test_unmatched_transfer_hours_and_missing_company_inputs_are_not_silently_dropped(data):
    data['history'] = [history('transport-by-type', 100, company='a', group='bus'),
                       history('trip-types', 20, company='a', hour=1, group='OneZone')]
    assert metrics(build(data, 'a'))['transfer-coefficient'].value is None
    assert metrics(build(data))['transfer-coefficient'].value is None


def test_transfer_sums_each_company_valid_hours_without_discarding_unshared_hours(data):
    # Company a has two matched observation hours, company b has one. Both
    # count pairs are valid; restricting to shared hours would lose 100/20.
    data['history'] += [history('transport-by-type', 100, company='a', hour=1, group='bus'),
                        history('trip-types', 20, company='a', hour=1, group='OneZone')]
    value = metrics(build(data))['transfer-coefficient']
    assert value.value == Decimal(210) / 50
    assert not value.complete


def test_transfer_excludes_hour_with_missing_serialized_mode_category(data):
    data['history'] = [history('transport-by-type', 100, company='a', group='bus'),
                       history('transport-by-type', 20, company='a', group='tram'),
                       history('trip-types', 30, company='a', group='OneZone'),
                       history('transport-by-type', 100, company='a', hour=1, group='bus'),
                       history('trip-types', 30, company='a', hour=1, group='OneZone')]
    snapshot = build(data, 'a')
    value = metrics(snapshot)['transfer-coefficient']
    assert value.value == 4  # Only the complete, matched 120 / 30 at 00:00.
    assert not value.complete
    assert '完整' in value.reason and '排除' in value.reason
    assert [b.value for b in next(iter(snapshot.trend.series.values()))] == [120, None, None]


def test_transfer_keeps_company_specific_complete_paired_hours(data):
    data['history'] = [history('transport-by-type', 100, company='a', group='bus'),
                       history('transport-by-type', 20, company='a', group='tram'),
                       history('trip-types', 30, company='a', group='OneZone'),
                       history('transport-by-type', 100, company='a', hour=1, group='bus'),
                       history('trip-types', 30, company='a', hour=1, group='OneZone'),
                       history('transport-by-type', 80, company='b', hour=1, group='bus'),
                       history('trip-types', 20, company='b', hour=1, group='OneZone')]
    value = metrics(build(data))['transfer-coefficient']
    assert value.value == 4  # (a's 120 + b's 80) / (a's 30 + b's 20).
    assert not value.complete


def test_transfer_returns_missing_when_no_complete_mode_hour_can_be_paired(data):
    data['history'] = [history('transport-by-type', 100, company='a', group='bus'),
                       history('transport-by-type', 20, company='a', group='tram'),
                       history('transport-by-type', 100, company='a', hour=1, group='bus'),
                       history('trip-types', 30, company='a', hour=1, group='OneZone')]
    assert metrics(build(data, 'a'))['transfer-coefficient'].value is None


def test_transfer_excludes_hour_with_missing_serialized_journey_category(data):
    data['history'] = [history('transport-by-type', 120, company='a', group='bus'),
                       history('trip-types', 20, company='a', group='OneZone'),
                       history('trip-types', 10, company='a', group='TwoZones'),
                       history('transport-by-type', 100, company='a', hour=1, group='bus'),
                       history('trip-types', 20, company='a', hour=1, group='OneZone')]
    assert metrics(build(data, 'a'))['transfer-coefficient'].value == 4


def test_transfer_preserves_missing_entire_company_and_recorded_zero(data):
    data['history'] = [history('transport-by-type', 0, company='a', group='bus'),
                       history('trip-types', 20, company='a', group='OneZone')]
    assert metrics(build(data, 'a'))['transfer-coefficient'].value == 0
    assert metrics(build(data))['transfer-coefficient'].value is None


def test_city_share_does_not_turn_invalid_weight_into_valid_daily_ratio(data):
    data['history'] = [history('public-transport', 10, 0),
                       history('public-transport', 20, 100, hour=1)]
    assert metrics(build(data))['public-transport-share'].value is None


def test_all_modes_include_observed_history_and_real_fleet_even_without_lines(data):
    data['companies'][0]['车队']['地铁'] = 2
    data['history'].append(history('transport-by-type', 0, company='a', group='waterbus'))
    assert set(build(data).modes) == {'综合', '公交', '有轨电车', '地铁', '水上巴士'}


def test_builder_is_read_only_and_cancellable(data):
    before = deepcopy(data)
    build(data)
    assert data == before
    with pytest.raises(QueryCancelled):
        build(data, cancelled=lambda: True)


@pytest.mark.parametrize('save_path', ['D:/存档/秋山市n6 (2).save', r'D:\存档\秋山市n6 (2).save'])
def test_actual_unicode_windows_save_path_supplies_save_basename(data, save_path):
    data['save_path'] = save_path
    data['tag'] = '秋山市n6 (2)_运行时'
    data.pop('save_name', None)
    assert build(data).save_name == '秋山市n6 (2).save'


def test_actual_save_path_takes_priority_over_explicit_display_name(data):
    data['save_path'] = 'D:/存档/秋山市n6 (2).save'
    data['save_name'] = '旧存档.save'
    assert build(data).save_name == '秋山市n6 (2).save'


def test_explicit_save_name_remains_usable_without_source_path(data):
    data['save_name'] = '明确名称.save'
    assert build(data).save_name == '明确名称.save'


def test_export_tag_is_not_presented_as_actual_save_filename(data):
    data['tag'] = '秋山市n6 (2)_运行时'
    data.pop('save_name', None)
    data.pop('save_path', None)
    assert build(data).save_name == '未提供存档名称'


def test_save_header_controls_city_display_and_preserves_trace(data, tmp_path):
    from test_map_name_source import header
    save = tmp_path / '秋山市n6 (2).save'
    save.write_bytes(header(':273831404:Eixeia1.1'))
    data['save_path'] = str(save)
    data['metadata']['地图名称'] = '秋山市n6 (2)'
    snapshot = build(data)
    assert snapshot.city_name == 'Eixeia'
    assert snapshot.city_raw_reference == ':273831404:Eixeia1.1'
    assert snapshot.city_raw_name == 'Eixeia1.1'
    assert snapshot.city_internal_id == '273831404'
    assert snapshot.city_source == 'save-header:m_originalMapName'


def test_legacy_unmarked_city_name_is_missing_without_supported_save_header(data):
    data['metadata']['地图名称'] = 'quicksave.76561198362520556-76561198845688243'
    assert build(data).city_name == '未提供城市名称'


def test_reliable_original_metadata_city_is_standardized_without_a_save_path(data):
    data['metadata'].update({'地图原始引用': ':185668233:Budapest, HU 2.0',
                             '地图名称来源': 'save-header:m_originalMapName'})
    snapshot = build(data)
    assert snapshot.city_name == 'Budapest'
    assert snapshot.city_raw_reference == ':185668233:Budapest, HU 2.0'
    assert snapshot.city_source == 'metadata:save-header:m_originalMapName'


def test_map_source_revision_does_not_change_thirteen_business_metrics(data, tmp_path):
    from test_map_name_source import header
    before = build(data, 'a', '公交')
    save = tmp_path / '错误文件名.save'
    save.write_bytes(header(':180250842:Ljubljana'))
    data['save_path'] = str(save)
    after = build(data, 'a', '公交')
    assert after.city_name == 'Ljubljana'
    assert after.metrics == before.metrics
    assert after.lines == before.lines
    assert after.highlights == before.highlights
    assert after.passenger_top10 == before.passenger_top10
    assert after.total_departures == before.total_departures


def test_company_trend_preserves_each_real_company_hour_without_other_company_mask(data):
    data['history'].append(history('transport-by-type', 25, company='a', hour=1, group='bus'))
    snapshot = build(data)
    assert snapshot.company_trend.query.companies == ('a', 'b')
    assert set(snapshot.company_trend.series) == {('a', '总计'), ('b', '总计')}
    assert [b.value for b in snapshot.company_trend.series[('a', '总计')]] == [100, 25, None]
    assert [b.value for b in snapshot.company_trend.series[('b', '总计')]] == [10, None, None]
    assert [b.value for b in next(iter(snapshot.trend.series.values()))] == [110, None, None]


def test_single_company_trend_and_specific_mode_keep_real_scope_and_category_gaps(data):
    data['history'] += [history('transport-by-type', 15, company='a', group='tram'),
                        history('transport-by-type', 25, company='a', hour=1, group='bus')]
    snapshot = build(data, 'a')
    assert set(snapshot.company_trend.series) == {('a', '总计')}
    assert [b.value for b in snapshot.company_trend.series[('a', '总计')]] == [115, None, None]
    selected = build(data, 'a', '公交').company_trend
    assert set(selected.series) == {('a', '公交')}
    assert [b.value for b in selected.series[('a', '公交')]] == [100, 25, None]


def test_company_trend_stops_at_simulation_clock_and_remains_missing_without_clock(data):
    data['history'].append(history('transport-by-type', 9999, company='a', hour=3, group='bus'))
    snapshot = build(data, 'a')
    assert [b.start.hour for b in next(iter(snapshot.company_trend.series.values()))] == [0, 1, 2]
    assert snapshot.company_trend.current_window[1] == D(2013, 5, 21, 2, 30)
    data.pop('simulation_time')
    assert build(data).company_trend is None
