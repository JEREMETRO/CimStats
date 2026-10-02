"""Contracts for the read-only line query model; no game runtime is loaded."""
import ast
from copy import deepcopy
from importlib import import_module, util
from pathlib import Path

import pytest

from report_model import date_groups, format_garage, load_session
from display_rules import format_line_name


def prepare(entries, rules=None):
    assert util.find_spec('line_schedule') is not None, 'The schedule query model is missing'
    return import_module('line_schedule').prepare_schedule(entries, rules)


def entry(clock, **metadata):
    return {'time': clock, **metadata}


def test_operating_day_orders_after_midnight_and_keeps_duplicate_metadata():
    rows = [entry('1:30', 发班序号='3'), entry('23:30', 发班序号='2'),
            entry('6:05', 发班序号='1'), entry('23:30', 发班序号='4')]
    original = deepcopy(rows)
    result = prepare(rows)
    assert [(r['time'], r['next_day'], r['发班序号']) for r in result['entries']] == [
        ('06:05', False, '1'), ('23:30', False, '2'), ('23:30', False, '4'), ('01:30', True, '3')]
    assert result['last'] == '次日01:30'
    assert result['count'] == 4
    assert rows == original


def test_three_hour_stoppages_produce_separate_service_segments():
    result = prepare([entry(t) for t in ('06:00', '06:30', '09:30', '10:00')])
    assert not result['all_day']
    assert [s['text'] for s in result['segments']] == ['06:00–06:30', '09:30–10:00']
    assert result['service_text'] == '06:00–06:30；09:30–10:00'
    assert result['average_interval'] == 30


def test_true_service_segment_crosses_five_without_splitting_the_grid_cycle():
    result = prepare([entry(t) for t in ('04:30', '05:30', '06:30')])
    assert [(r['time'], r['next_day']) for r in result['entries']] == [
        ('05:30', False), ('06:30', False), ('04:30', True)]
    assert result['segments'] == [
        {'first': '次日04:30', 'last': '次日06:30', 'count': 3, 'text': '次日04:30–次日06:30'}]
    assert (result['first'], result['last']) == ('次日04:30', '次日06:30')
    assert result['average_interval'] == 60
    assert '网格' in result['first_tooltip']
    assert '连续' in result['last_tooltip']


def test_true_overnight_service_segment_crosses_midnight_and_five_once():
    result = prepare([entry(t) for t in ('23:30', '00:30', '01:30', '03:30', '04:30', '05:30', '06:30')])
    assert len(result['segments']) == 1
    assert result['service_text'] == '23:30–次日06:30'
    assert (result['first'], result['last']) == ('23:30', '次日06:30')
    assert result['segments'][0]['count'] == 7


def test_multiple_true_segments_keep_real_stops_when_one_crosses_five():
    result = prepare([entry(t) for t in ('04:30', '05:30', '06:30', '12:00', '13:00')])
    assert [s['text'] for s in result['segments']] == ['12:00–13:00', '次日04:30–次日06:30']
    assert [s['count'] for s in result['segments']] == [2, 3]
    assert (result['first'], result['last']) == ('12:00', '次日06:30')


def test_five_is_a_real_boundary_only_when_the_preceding_gap_reaches_three_hours():
    result = prepare([entry(t) for t in ('02:00', '05:00', '06:00')])
    assert [s['text'] for s in result['segments']] == ['05:00–06:00', '次日02:00']
    assert not result['all_day']


def test_all_day_uses_circular_gaps_and_the_complete_day_label():
    result = prepare([entry(f'{h:02}:00') for h in range(0, 24, 2)])
    assert result['all_day']
    assert (result['first'], result['last'], result['service_text']) == ('00:00', '24:00', '00:00–24:00')
    assert result['average_interval'] == 120
    assert result['segments'] == [{'first': '00:00', 'last': '24:00', 'count': 12, 'text': '00:00–24:00'}]


def test_all_day_matrix_starts_at_midnight_and_has_no_next_day_cells():
    result = prepare([entry(f'{h:02}:00', 发班序号=str(h)) for h in range(22, -1, -2)])
    assert [r['time'] for r in result['entries']] == [
        '00:00', '02:00', '04:00', '06:00', '08:00', '10:00',
        '12:00', '14:00', '16:00', '18:00', '20:00', '22:00']
    assert all(not r['next_day'] for r in result['entries'])
    assert all(r['display_time'] == r['time'] for r in result['entries'])
    assert result['entries'][0]['operating_seconds'] == 0
    assert result['entries'][0]['发班序号'] == '0'


def test_non_all_day_matrix_retains_five_hour_cutoff():
    result = prepare([entry(t) for t in ('00:00', '01:00', '06:00', '07:00')])
    assert not result['all_day']
    assert [(r['time'], r['next_day']) for r in result['entries']] == [
        ('06:00', False), ('07:00', False), ('00:00', True), ('01:00', True)]


def test_exact_three_hour_gap_is_not_all_day():
    result = prepare([entry(f'{h:02}:00') for h in range(0, 24, 3)])
    assert not result['all_day']
    assert len(result['segments']) == 8
    assert result['average_interval'] is None


def test_tick_seconds_win_over_rounded_display_clock():
    result = prepare([entry('06:00', 发班_tick='216300000000'),
                      entry('06:01', 发班_tick='217200000000')])
    assert [r['time'] for r in result['entries']] == ['06:00', '06:02']
    assert result['average_interval'] == 1.5
    assert result['average_interval_text'] == '1m30s'


def test_duplicates_count_as_simultaneous_departures_in_average():
    result = prepare([entry(t) for t in ('06:00', '06:00', '06:30')])
    assert result['count'] == 3
    assert result['average_interval'] == 15


@pytest.mark.parametrize('rows,count', [([], 0), ([entry('06:00')], 1), ([entry('bad')], 1)])
def test_insufficient_and_invalid_times_do_not_invent_intervals(rows, count):
    result = prepare(rows)
    assert result['count'] == count
    assert result['average_interval'] is None
    assert result['average_interval_text'] == '—'
    assert not result['all_day']


def test_invalid_departure_stays_visible_with_its_original_clock_diagnostic():
    result = prepare([entry('bad', 发班序号='9'), entry('06:00')])
    assert result['count'] == 2
    bad = result['entries'][-1]
    assert (bad['time'], bad['display_time'], bad['time_valid']) == ('—', '—', False)
    assert bad['original_time'] == 'bad'
    assert 'bad' in bad['diagnostic']
    assert bad['发班序号'] == '9'
    assert '无法解析' in result['average_interval_tooltip']


def test_unconfirmed_periods_stay_unavailable_even_with_many_departures():
    result = prepare([entry(f'{h:02}:00') for h in range(24)], {})
    for period in ('peak', 'offpeak', 'night'):
        assert result[period] == '—'
        assert '未确认' in result[f'{period}_tooltip']


def test_confirmed_periods_use_local_pairs_and_cross_midnight_rules():
    rows = [entry(t) for t in ('07:00', '07:10', '08:00', '08:20', '22:30', '23:00', '00:00')]
    result = prepare(rows, {'peak': [('07:00', '07:30')],
                            'offpeak': [('08:00', '08:30')], 'night': [('22:00', '01:00')]})
    assert (result['peak'], result['offpeak'], result['night']) == ('10m0s', '20m0s', '45m0s')
    assert '07:00–07:30' in result['peak_tooltip']


def test_periods_do_not_connect_separate_peak_windows():
    result = prepare([entry(t) for t in ('07:00', '07:10', '08:00', '08:30')],
                     {'peak': [('07:00', '07:20'), ('08:00', '08:40')]})
    assert result['peak'] == '20m0s'


def test_morning_and_evening_peak_means_are_separate_and_legacy_peak_survives():
    result = prepare([entry(t) for t in ('07:30', '07:40', '07:50', '17:00', '17:20', '17:40')])
    assert result['morning_peak'] == '10m0s'
    assert result['evening_peak'] == '20m0s'
    assert result['peak'] == '15m0s'
    assert '07:30–09:30' in result['morning_peak_tooltip']
    assert '17:00–19:30' in result['evening_peak_tooltip']


@pytest.mark.parametrize('clock,period,morning,evening', [
    ('00:00', 'night', False, False), ('05:30', 'offpeak', False, False),
    ('07:29:59', 'offpeak', False, False), ('07:30', 'morning_peak', True, False),
    ('09:30', 'offpeak', False, False), ('17:00', 'evening_peak', False, True),
    ('19:30', 'offpeak', False, False),
])
def test_entry_period_classification_uses_central_half_open_rules(clock, period, morning, evening):
    row = prepare([entry(clock)])['entries'][0]
    assert row['period'] == period
    assert row['morning_peak'] is morning
    assert row['evening_peak'] is evening


def test_entry_period_classification_uses_tick_seconds_not_rounded_clock():
    result = prepare([entry('07:30', 发班_tick='269999999999'),
                      entry('07:29', 发班_tick='270000000000')])
    assert [r['period'] for r in result['entries']] == ['offpeak', 'morning_peak']


def test_unconfirmed_period_rules_do_not_invent_morning_or_evening_classifications():
    result = prepare([entry('07:30'), entry('07:40')], {})
    assert (result['morning_peak'], result['evening_peak']) == ('—', '—')
    assert all(r['period'] == 'unknown' for r in result['entries'])
    assert all(not r['morning_peak'] and not r['evening_peak'] for r in result['entries'])


def test_absent_period_departures_report_no_defined_mean_instead_of_a_generic_failure():
    result = prepare([entry(t) for t in ('07:35', '08:05', '08:35', '09:05')])
    assert result['evening_peak'] == '—'
    assert '没有发班记录' not in result['evening_peak_tooltip']
    assert '17:00–19:30' in result['evening_peak_tooltip']
    assert result['period_diagnostics']['evening_peak'] == {
        'status': 'no_departures', 'departure_count': 0, 'window_departure_counts': [0],
        'interval_count': 0}


def test_period_diagnostics_distinguish_one_departure_from_stoppage_only_pairs():
    one = prepare([entry('07:35')])
    stopped = prepare([entry('10:00'), entry('13:00')])
    assert one['period_diagnostics']['morning_peak']['status'] == 'insufficient_departures'
    assert stopped['period_diagnostics']['offpeak']['status'] == 'stoppage_only'
    assert '180' in stopped['offpeak_tooltip']


def test_real_cache_peak_values_and_all_day_order_use_actual_tick_departures():
    folder = Path(__file__).resolve().parents[1] / 'exports'
    if not (folder / 'CIM2_线路客流_完整导出_望春市_test_运行时.csv').exists():
        pytest.skip('Optional real CSV regression fixture is absent')
    session = load_session(folder, '望春市_test_运行时')
    line = next(l for l in session['lines'] if l['key'] == '76561198845688243|有轨电车|1')
    result = line['时刻表']['周一至周四']
    # Actual CSV: morning has 16 departures from 07:30 to 09:25, 115/15 minutes.
    # Evening has 15 from 17:00 to 19:15, 135/14 minutes; union has 29 intervals.
    assert (result['morning_peak'], result['evening_peak'], result['peak']) == ('7m40s', '9m39s', '8m37s')
    assert result['count'] == 93
    assert result['all_day']
    assert result['entries'][0]['time'] == '00:00'
    assert not any(r['next_day'] for r in result['entries'])
    assert all(line['字段可用性'].values())
    assert line['平均车辆需求数'] is not None


@pytest.mark.parametrize('clocks,period,want', [
    (('05:20', '05:30', '05:40'), 'offpeak', '10m0s'),
    (('07:20', '07:30', '07:45'), 'peak', '15m0s'),
    (('09:20', '09:30', '09:40'), 'offpeak', '10m0s'),
    (('17:00', '17:10'), 'peak', '10m0s'),
    (('19:20', '19:30', '19:45'), 'offpeak', '15m0s'),
    (('00:00', '00:10'), 'night', '10m0s'),
])
def test_confirmed_default_periods_assign_boundaries_to_starting_range(clocks, period, want):
    result = prepare([entry(t) for t in clocks])
    assert result[period] == want
    assert '07:30–09:30' in result['peak_tooltip']
    assert '17:00–19:30' in result['peak_tooltip']
    assert '00:00–05:30' in result['night_tooltip']


def test_partial_masks_are_individual_days():
    assert date_groups(2 | 8 | 32 | 1) == ['周一', '周三', '周五', '周日']
    assert date_groups(30) == ['周一至周四']
    assert date_groups(0) == ['未启用']


def session_fixture(tmp_path, monkeypatch, *, departures, timetables=(), line_extra=None):
    base = {'玩家ID': 'p1', '公司名称': 'same', '公司序号': '0', '线路类型': 'bus', '线路号': '12'}
    fixtures = {
        'CIM2_公司信息': [{'玩家ID': 'p1', '公司序号': '0', '公司名称': 'same'}],
        'CIM2_线路客流_完整导出': [{**base, '单程时间_tick': '36000000000', **(line_extra or {})}],
        'CIM2_发班信息_完整导出': [{**base, **r} for r in timetables],
        'CIM2_发班记录_完整导出': [{**base, **r} for r in departures],
        'CIM2_城市历史元数据': [{'模拟当前时间': '2024-01-01 12:00:00'}],
    }
    monkeypatch.setattr('report_model.read_csv', lambda folder, stem, tag: deepcopy(fixtures.get(stem, [])))
    return load_session(tmp_path, 'fixture')


def test_different_weekday_schedules_split_without_losing_provenance(tmp_path, monkeypatch):
    result = session_fixture(tmp_path, monkeypatch, departures=[
        {'发班时间': '06:00:30', '发班_tick': '216300000000', '时刻表_运行日掩码': '30',
         '时刻表_首选车型': '3', '时刻表序号': '7', '发班序号': '2'},
        {'发班时间': '06:10:30', '发班_tick': '222300000000', '时刻表_运行日掩码': '2',
         '时刻表_首选车型': '', '时刻表序号': '8', '发班序号': '3'},
    ])
    line = result['lines'][0]
    assert line['日组'] == ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    assert [len(line['班次'][day]) for day in line['日组']] == [2, 1, 1, 1, 0, 0, 0]
    original = line['班次']['周一'][0]
    assert (original['发班_tick'], original['时刻表序号'], original['发班序号']) == ('216300000000', '7', '2')
    assert original['发班时间'] == '06:00:30'
    assert original['vehicle_code'] == '大'
    assert line['班次']['周一'][1]['vehicle_code'] == '?'
    assert line['平均间隔'] == '10m0s'
    assert line['当日发班数'] == 2
    assert '2024-01-01' in line['平均间隔Tooltip']
    assert line['时刻表']['周二']['average_interval'] is None
    assert line['平均间隔'] == '10m0s'


def test_identical_weekdays_keep_legacy_four_groups(tmp_path, monkeypatch):
    result = session_fixture(tmp_path, monkeypatch, departures=[
        {'发班时间': '06:00', '时刻表_运行日掩码': '30', '时刻表_首选车型': '0'},
    ])
    line = result['lines'][0]
    assert line['日组'] == ['周一至周四', '周五', '周六', '周日']
    assert line['班次']['周一至周四'][0]['vehicle_code'] == '任'
    assert line['周一至周四发班数量'] == 1


def test_timetable_join_controls_current_day_and_vehicle_size(tmp_path, monkeypatch):
    result = session_fixture(tmp_path, monkeypatch,
        departures=[{'发班时间': '06:00', '时刻表序号': '1', '时刻表_运行日掩码': '4', '时刻表_首选车型': '0'},
                    {'发班时间': '06:30', '时刻表序号': '1', '时刻表_运行日掩码': '4'}],
        timetables=[{'时刻表序号': '1', '运行日掩码': '2', '首选车型': '2'}])
    line = result['lines'][0]
    assert line['当日发班数'] == 2
    assert line['班次']['周一'][0]['vehicle_code'] == '中'
    assert line['平均间隔'] == '30m0s'


@pytest.mark.parametrize('raw,expected', [('2560', 2.5), ('0', 0.005859375), ('', 0.005859375)])
def test_weekly_vehicle_average_uses_cache_or_game_fixed_point_slots(tmp_path, monkeypatch, raw, expected):
    result = session_fixture(tmp_path, monkeypatch,
        departures=[{'发班时间': '06:00', '时刻表_运行日掩码': '2'}],
        line_extra={'平均车辆需求数_缓存_fixed': raw})
    line = result['lines'][0]
    assert line['平均车辆需求数'] == expected
    assert '周平均' in line['平均车辆需求数Tooltip']
    assert line['原始字段']['平均车辆需求数_缓存_fixed'] == raw


def test_vehicle_average_missing_duration_is_unavailable(tmp_path, monkeypatch):
    result = session_fixture(tmp_path, monkeypatch, departures=[
        {'发班时间': '06:00', '时刻表_运行日掩码': '2'}], line_extra={'单程时间_tick': ''})
    assert result['lines'][0]['平均车辆需求数'] is None


@pytest.mark.parametrize('mask', [None, '', 'bad', '1.5', '2147483648', '-2147483649'])
@pytest.mark.parametrize('cached', ['', '0'])
def test_unknown_running_days_stay_accessible_and_do_not_invent_zero_demand(tmp_path, monkeypatch, mask, cached):
    dep = {'发班时间': '06:00:30', '发班_tick': '216300000000',
           '时刻表序号': '7', '发班序号': '3', '时刻表_首选车型': '2'}
    if mask is not None:
        dep['时刻表_运行日掩码'] = mask
    result = session_fixture(tmp_path, monkeypatch, departures=[dep],
                             line_extra={'平均车辆需求数_缓存_fixed': cached})
    line = result['lines'][0]
    assert line['平均车辆需求数'] is None
    assert '运行日' in line['平均车辆需求数Tooltip']
    assert line['日组'][-1] == '运行日未知'
    assert line['运行日未知班次'] == line['班次']['运行日未知']
    assert len(line['运行日未知班次']) == 1
    assert not line['班次数据完整']
    bad = line['运行日未知班次'][0]
    assert bad['运行日掩码'] is None
    assert (bad['发班_tick'], bad['时刻表序号'], bad['发班序号']) == ('216300000000', '7', '3')
    assert bad['vehicle_code'] == '中'
    assert '运行日' in bad['diagnostic']
    assert line['班次诊断']
    assert all(not line['班次'][day] for day in line['日组'] if day != '运行日未知')
    assert line['时刻表']['运行日未知']['average_interval'] is None
    assert line['时刻表']['运行日未知']['first'] == '—'


def test_unknown_day_records_cannot_be_assumed_to_share_a_service_day(tmp_path, monkeypatch):
    result = session_fixture(tmp_path, monkeypatch, departures=[
        {'发班时间': '06:00', '发班序号': '1'}, {'发班时间': '06:30', '发班序号': '2'},
        {'发班时间': '07:00', '时刻表_运行日掩码': '2'},
        {'发班时间': '07:10', '时刻表_运行日掩码': '2'},
    ], line_extra={'平均车辆需求数_缓存_fixed': '0'})
    line = result['lines'][0]
    assert len(line['班次']['周一']) == 2
    assert len(line['班次']['运行日未知']) == 2
    unknown = line['时刻表']['运行日未知']
    assert unknown['count'] == 2
    assert unknown['average_interval'] is None
    assert unknown['segments'] == []
    assert line['平均间隔'] == '—'
    assert '2班' in line['平均间隔Tooltip']
    assert line['平均车辆需求数'] is None


def test_explicit_disabled_mask_is_distinct_from_unknown_days(tmp_path, monkeypatch):
    result = session_fixture(tmp_path, monkeypatch, departures=[
        {'发班时间': '06:00', '时刻表_运行日掩码': '0'}],
        line_extra={'平均车辆需求数_缓存_fixed': '0'})
    line = result['lines'][0]
    assert line['平均车辆需求数'] == 0
    assert line['运行日未知班次'] == []
    assert len(line['班次']['未启用']) == 1
    assert line['班次数据完整']


@pytest.mark.parametrize('mask', ['255', '-1'])
def test_game_int32_masks_preserve_high_bits_and_all_seven_weekdays(tmp_path, monkeypatch, mask):
    # Original TimeTable.m_activeDays is Int32; CalculateNeededVehicles tests bits 0..6.
    line = session_fixture(tmp_path, monkeypatch, departures=[
        {'发班时间': '06:00', '时刻表_运行日掩码': mask}])['lines'][0]
    assert line['日组'] == ['周一至周四', '周五', '周六', '周日']
    assert [len(line['班次'][day]) for day in line['日组']] == [1, 1, 1, 1]
    assert all(line['班次'][day][0]['运行日掩码'] == int(mask) for day in line['日组'])
    assert line['运行日未知班次'] == []
    assert line['当日发班数'] == 1
    # Seven one-hour departures occupy 84 five-minute slots; floor(84*1024/2016)=42.
    assert line['平均车辆需求数'] == 42 / 1024


@pytest.mark.parametrize('mask', ['130', '-2147483646'])
def test_game_int32_high_bits_do_not_add_other_weekdays(tmp_path, monkeypatch, mask):
    line = session_fixture(tmp_path, monkeypatch, departures=[
        {'发班时间': '06:00', '时刻表_运行日掩码': mask}])['lines'][0]
    assert line['日组'] == ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    assert [len(line['班次'][day]) for day in line['日组']] == [1, 0, 0, 0, 0, 0, 0]
    assert line['班次']['周一'][0]['运行日掩码'] == int(mask)
    assert line['运行日未知班次'] == []
    assert line['平均车辆需求数'] == 6 / 1024


@pytest.mark.parametrize('mask', ['128', '-2147483648'])
def test_game_int32_high_only_masks_preserve_records_without_weekday_service(tmp_path, monkeypatch, mask):
    line = session_fixture(tmp_path, monkeypatch, departures=[
        {'发班时间': '06:00', '时刻表_运行日掩码': mask}],
        line_extra={'单程时间_tick': '', '平均车辆需求数_缓存_fixed': '0'})['lines'][0]
    assert date_groups(int(mask)) == ['未启用']
    assert len(line['班次']['未启用']) == 1
    assert line['班次']['未启用'][0]['运行日掩码'] == int(mask)
    assert line['运行日未知班次'] == []
    assert line['当日发班数'] == 0
    assert line['平均车辆需求数'] == 0


def test_confirmed_positive_vehicle_cache_survives_unknown_day_metadata(tmp_path, monkeypatch):
    result = session_fixture(tmp_path, monkeypatch, departures=[{'发班时间': '06:00'}],
                             line_extra={'平均车辆需求数_缓存_fixed': '2560'})
    line = result['lines'][0]
    assert line['平均车辆需求数'] == 2.5
    assert not line['班次数据完整']
    assert '运行日' in line['平均车辆需求数Tooltip']


def test_missing_line_measurements_expose_unavailability_and_keep_legacy_zeros(tmp_path, monkeypatch):
    result = session_fixture(tmp_path, monkeypatch, departures=[])
    line = result['lines'][0]
    assert line['字段可用性'] == {'地图里程': False, '折算里程': False, '站点数': False}
    assert (line['地图里程'], line['折算里程'], line['站点数']) == (0, 0, 0)


def test_confirmed_zero_line_measurements_are_available(tmp_path, monkeypatch):
    result = session_fixture(tmp_path, monkeypatch, departures=[],
        line_extra={'地图里程': '0', '折算里程': '0', '站点数': '0'})
    line = result['lines'][0]
    assert line['字段可用性'] == {'地图里程': True, '折算里程': True, '站点数': True}
    assert (line['地图里程'], line['折算里程'], line['站点数']) == (0, 0, 0)


@pytest.mark.parametrize('raw', [None, '', ' ', 'bad', 'nan', 'inf', '-1'])
def test_invalid_line_measurements_are_marked_unavailable(tmp_path, monkeypatch, raw):
    result = session_fixture(tmp_path, monkeypatch, departures=[],
        line_extra={'地图里程': raw, '折算里程': raw, '站点数': raw})
    line = result['lines'][0]
    assert line['字段可用性'] == {'地图里程': False, '折算里程': False, '站点数': False}


def test_available_measurements_keep_existing_conversion_and_legacy_length_fallback(tmp_path, monkeypatch):
    result = session_fixture(tmp_path, monkeypatch, departures=[],
        line_extra={'地图里程': '1024000', '线路长度': '1024000', '站点数': '17'})
    line = result['lines'][0]
    assert line['字段可用性'] == {'地图里程': True, '折算里程': True, '站点数': True}
    assert (line['地图里程'], line['折算里程'], line['站点数']) == (2, 1, 17)


def test_fractional_stop_counts_are_invalid_without_changing_legacy_conversion(tmp_path, monkeypatch):
    result = session_fixture(tmp_path, monkeypatch, departures=[],
        line_extra={'地图里程': '1.5', '站点数': '1.5'})
    line = result['lines'][0]
    assert line['字段可用性']['地图里程']
    assert not line['字段可用性']['站点数']
    assert line['站点数'] == 1


@pytest.mark.parametrize('number,name,want', [
    (12, '101-E', '101E'), (12, '12-A', '12A'),
    (812, 'E', '812E'), (502, 'E', '502E'), (12, 'e', '12e'),
    (812, '812路-E', '812E'), (502, '502路E', '502E'),
    (12, '机场', '12路机场'), (12, '东', '12路东'),
    (12, 'AB', '12路AB'), (12, 'Ｅ', '12路Ｅ'),
    (12, '101快线', '101快线'), (12, '812路E延线', '812路E延线'),
    (12, '1', '1路'), (12, '1路', '1路'),
])
def test_single_letter_route_suffix_is_compact_and_other_rules_survive(number, name, want):
    assert format_line_name(number, name) == want


@pytest.mark.parametrize('raw,want', [('东北电车厂', '六进公交东北电车厂'), ('车库2', '六进公交车库2'),
                                    ('六进公交东北电车厂', '六进公交东北电车厂'),
                                    ('2', '六进公交有轨电车车库2'), ('0', ''), (None, ''),
                                    ('未知', ''), ('Unknown', ''), ('null', '')])
def test_garage_preserves_named_depots_and_blanks_unknown(raw, want):
    assert format_garage('六进公交', '有轨电车', raw) == want


def test_runtime_row_appends_average_cache_and_depot_name_without_loading_runtime():
    tree = ast.parse(Path(__file__).with_name('extract_runtime_data.py').read_text(encoding='utf-8'))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    call = next(n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name) and n.func.value.id == 'line_rows' and n.func.attr == 'append')
    namespace = dict(field=lambda obj, name: (obj or {}).get(name),
                     line={'m_vehiclesNeededAvg': 2560}, depot={'m_number': 3, 'm_name': '东北电车厂'},
                     owner_index=0, owner_id='p1', owner_name='same', mode='有轨电车', number=12,
                     datetime_text=lambda value: '', duration_text=lambda value: '',
                     vehicles=[], timetables=[], stops=[], runtime_top=4, map_length=1,
                     runtime_length=2, runtime_duration=36000000000, identity=99)
    row = eval(compile(ast.Expression(call.args[0]), '<line-export>', 'eval'), namespace)
    assert row['平均车辆需求数_缓存_fixed'] == 2560
    assert row['线路车库名称'] == '东北电车厂'
    assert row['线路车库'] == 3
