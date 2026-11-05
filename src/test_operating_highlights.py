"""Latest-info extrema rank service for the simulation day without pruning data."""
from copy import deepcopy

from openpyxl import load_workbook
import pytest

from latest_info_exports import build_share_summary, export_latest_info_xlsx
from latest_info_model import build_latest_info


def line(key, passengers, departures, *, company='a', mode='公交'):
    return {'key': key, '线路名称': key, '公司标识': company, '运输制式': mode,
            '今日客流': passengers, '当日发班数': departures, '单程时间': 20,
            '地图里程': 10, '每周收入': 8, '每周支出': 3,
            '班次数据完整': True, '班次': {}}


def session(rows):
    return {'save_key': 'operating-day', 'simulation_time': '2024-01-01 12:00:00',
            'companies': [{'公司标识': identity, '公司名称': '同名公司', '车辆总数': 4,
                           '车队': {'公交': 3, '有轨电车': 1}} for identity in ('a', 'b')],
            'lines': rows, 'history': []}


def highlight_keys(snapshot):
    return [highlight.line.key if highlight.line else None for highlight in snapshot.highlights]


@pytest.mark.parametrize('idle_passengers', [0, 9999, None])
def test_zero_departure_line_cannot_win_any_highlight(idle_passengers):
    data = session([line('idle', idle_passengers, 0),
                    line('busy', 100, 4), line('quiet', 10, 2)])
    snapshot = build_latest_info(data)
    assert highlight_keys(snapshot) == ['busy', 'quiet', 'busy', 'quiet']


def test_positive_service_with_zero_passengers_stays_eligible():
    snapshot = build_latest_info(session([line('idle', 9999, 0),
                                         line('empty-service', 0, 1)]))
    assert highlight_keys(snapshot) == ['empty-service'] * 4
    assert snapshot.highlights[0].line.passengers == 0


@pytest.mark.parametrize('missing_count', [None, '', 'bad', 'NaN', 'absent'])
@pytest.mark.parametrize('passengers,want', [
    (999, ['unknown', 'known', 'known', 'known']),
    (0, ['known', 'unknown', 'known', 'known']),
])
def test_missing_departures_remain_unknown_and_keep_passenger_eligibility(missing_count, passengers, want):
    unknown = line('unknown', passengers, missing_count)
    if missing_count == 'absent':
        unknown.pop('当日发班数')
    snapshot = build_latest_info(session([unknown, line('known', 100, 2)]))
    assert snapshot.lines[0].departures is None
    assert snapshot.total_departures is None
    assert snapshot.lines[0].passengers_per_departure is None
    assert highlight_keys(snapshot) == want


def test_unknown_departures_have_empty_departure_extrema_and_blank_export_values(tmp_path):
    snapshot = build_latest_info(session([line('unknown', 0, None)]))
    assert highlight_keys(snapshot) == ['unknown', 'unknown', None, None]
    path = tmp_path / 'unknown.xlsx'
    export_latest_info_xlsx(snapshot, None, path)
    workbook = load_workbook(path, data_only=True)
    extrema = list(workbook['线路极值'].values)[1:]
    assert extrema[0][6:8] == (0, None)
    assert extrema[1][6:8] == (0, None)
    assert extrema[2][1:] == (None,) * 9
    assert extrema[3][1:] == (None,) * 9
    assert '客流 0 人次；班次 — 次' in build_share_summary(snapshot)


def test_all_zero_service_yields_four_empty_highlights_without_pruning_other_data(tmp_path):
    data = session([line('idle-high', 100, 0), line('idle-zero', 0, 0)])
    original = deepcopy(data)
    snapshot = build_latest_info(data, 'a')
    assert highlight_keys(snapshot) == [None] * 4
    assert [row.key for row in snapshot.lines] == ['idle-high', 'idle-zero']
    assert [row.key for row in snapshot.passenger_top10] == ['idle-high', 'idle-zero']
    assert [(row.mode, row.value) for row in snapshot.passenger_modes] == [('公交', 100)]
    assert [(row.mode, row.value) for row in snapshot.departure_modes] == [('公交', 0)]
    assert snapshot.total_departures == 0
    metrics = {metric.key: metric.value for metric in snapshot.metrics}
    assert metrics['line-count'] == 2
    assert metrics['weekly-income'] == 16
    assert metrics['weekly-expense'] == 6
    assert metrics['profit'] == 10
    assert data == original

    summary = build_share_summary(snapshot)
    for highlight in snapshot.highlights:
        assert f'{highlight.title}：—' in summary
    path = tmp_path / 'nonoperating.xlsx'
    export_latest_info_xlsx(snapshot, None, path)
    workbook = load_workbook(path, data_only=True)
    assert list(workbook['线路极值'].values)[1:] == [
        (highlight.title, *([None] * 9)) for highlight in snapshot.highlights]
    assert [row[1] for row in list(workbook['客流前十'].values)[1:]] == ['idle-high', 'idle-zero']
    assert [row[7] for row in list(workbook['客流前十'].values)[1:]] == [0, 0]
    assert list(workbook['班次分类'].values)[1][:2] == ('公交', 0)


def test_operating_highlights_respect_company_identity_and_mode():
    data = session([line('a-idle', 9999, 0), line('a-bus', 10, 2),
                    line('a-tram', 20, 3, mode='有轨电车'),
                    line('b-bus', 100, 8, company='b')])
    assert highlight_keys(build_latest_info(data, 'a', '公交')) == ['a-bus'] * 4
    assert highlight_keys(build_latest_info(data, 'b', '公交')) == ['b-bus'] * 4
    assert highlight_keys(build_latest_info(data, 'a', '有轨电车')) == ['a-tram'] * 4
    assert highlight_keys(build_latest_info(data, 'b', '有轨电车')) == [None] * 4


@pytest.mark.parametrize('day,active_key,counts', [
    ('2024-01-01', 'p1|公交|1', [1, 0]),
    ('2024-01-02', 'p1|公交|2', [0, 1]),
])
def test_highlight_service_follows_normalized_simulation_weekday(tmp_path, monkeypatch, day, active_key, counts):
    from report_model import load_session

    base = {'玩家ID': 'p1', '公司名称': 'same', '公司序号': '0', '线路类型': 'bus'}
    fixtures = {
        'CIM2_公司信息': [{'玩家ID': 'p1', '公司序号': '0', '公司名称': 'same'}],
        'CIM2_线路客流_完整导出': [
            {**base, '线路号': str(number), '单程时间_tick': '36000000000', '今日客流': '0'}
            for number in (1, 2)],
        'CIM2_发班记录_完整导出': [
            {**base, '线路号': str(number), '发班时间': '06:00', '时刻表_运行日掩码': str(mask)}
            for number, mask in ((1, 2), (2, 4))],
        'CIM2_城市历史元数据': [{'模拟当前时间': f'{day} 12:00:00'}],
    }
    monkeypatch.setattr('report_model.read_csv',
                        lambda folder, stem, tag: deepcopy(fixtures.get(stem, [])))
    data = load_session(tmp_path, 'fixture')
    assert [row['当日发班数'] for row in data['lines']] == counts
    snapshot = build_latest_info(data)
    assert highlight_keys(snapshot) == [active_key] * 4
    assert len(snapshot.lines) == 2


def test_xlsx_and_share_use_same_filtered_highlights_and_keep_top10(tmp_path):
    snapshot = build_latest_info(session([line('idle', 9999, 0),
                                         line('busy', 100, 4), line('quiet', 10, 2)]))
    assert highlight_keys(snapshot) == ['busy', 'quiet', 'busy', 'quiet']
    path = tmp_path / 'operating.xlsx'
    export_latest_info_xlsx(snapshot, None, path)
    workbook = load_workbook(path, data_only=True)
    assert [row[1] for row in list(workbook['线路极值'].values)[1:]] == ['busy', 'quiet', 'busy', 'quiet']
    assert [row[1] for row in list(workbook['客流前十'].values)[1:]] == ['idle', 'busy', 'quiet']
    share = build_share_summary(snapshot)
    for title, name in zip(('当日最大客流线路', '当日最小客流线路', '当日最多班次线路', '当日最少班次线路'),
                           ('busy', 'quiet', 'busy', 'quiet')):
        assert f'{title}：{name}；' in share
