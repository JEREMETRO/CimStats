"""A-04: auto ranges use the painted stack and readable tick spacing."""
from datetime import datetime
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'frontend'), str(ROOT / 'src')]

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from chart_canvas import AxisSpec, ChartCanvas, ChartData, Series, nice_ticks, _tick_text
from dashboard_model import FilterState, build_dashboard
from network_charts import NetworkChartPanel
from network_model import NetworkOptions, build_network_snapshot
from report_model import load_session
from statistics_model import HistoryStore
from test_ui_audit_tooltip_units import tooltip_theme

SAVE = Path('D:/test/CimStats/jobs/c60207891e1d4b36ba0b89026b830dcc')
OUT = ROOT / 'jobs/ui-audit-20261007/axis-evidence'


def real_network():
    session = load_session(SAVE, '秋山市n6 (4)_运行时')
    names = {str(company['公司标识']): company['公司名称'] for company in session['companies']}
    store = HistoryStore(session['history'], session['simulation_time'])
    filters = FilterState(tuple(names), datetime(2013, 5, 13), datetime(2013, 5, 20))
    snapshot = build_dashboard(store, filters)
    return build_network_snapshot(snapshot, NetworkOptions(), names, lines=session['lines'])


def make_canvas(data, size=(400, 190), detailed=False):
    canvas = ChartCanvas(detailed=detailed); canvas.resize(*size); canvas.set_data(data)
    canvas.show(); QApplication.processEvents(); canvas.grab()
    return canvas


def test_sparse_ticks_do_not_double_a_fifty_two_unit_range():
    lower, upper, step = nice_ticks(0, 52.01, 3)
    assert lower == 0
    assert 52.01 <= upper <= 65
    assert (upper - lower) / step + 1 <= 3


def test_very_large_nice_grid_does_not_exceed_decimal_remainder_precision():
    lower, upper, step = nice_ticks(0, 1e40, 4, min_step=.01)
    assert lower == 0
    assert upper >= 1e40
    assert (upper - lower) / step + 1 <= 4


@pytest.mark.parametrize('height', [140, 160, 190, 260, 540])
def test_small_stacked_canvas_uses_its_full_peak_without_excess_headroom(height):
    data = ChartData('bar', ['a', 'b'], [
        Series('bus', '公交', QColor('blue'), [460000, 480000], stack='current'),
        Series('tram', '有轨', QColor('orange'), [50000, 60000], stack='current'),
        Series('old', '上周同期', QColor('green'), [530000, 520000], stack='previous', faded=True),
        Series('missing', '缺失', QColor('red'), [None, None], stack='current'),
    ], unit='人次')
    original = [list(series.values) for series in data.series]
    canvas = make_canvas(data, (400, height), detailed=height == 540)
    try:
        assert canvas.axis.lower == 0
        assert 540000 <= canvas.axis.upper * canvas.axis.scale <= 675000
        ticks = canvas._ticks()
        labels = [_tick_text(tick, canvas.axis.step) for tick in ticks]
        assert len(labels) == len(set(labels))
        assert canvas.plot_rect().height() / (len(ticks) - 1) >= canvas._metrics().height() + 7
        assert [series.values for series in data.series] == original
        assert canvas.hidden == set()
    finally:
        canvas.close()


@pytest.fixture(scope='module')
def network():
    if not SAVE.is_dir():
        pytest.skip('A-04 read-only real archive is unavailable')
    return real_network()


@pytest.mark.parametrize('key', ['transport-by-type', 'transport-by-group', 'trip-types'])
@pytest.mark.parametrize('size,detailed', [((228, 140), False), ((400, 190), False),
                                         ((480, 260), False), ((960, 540), True)])
def test_screenshot_network_stacks_use_the_observed_peak(network, key, size, detailed):
    descriptor = next(chart for chart in network.charts if chart.key == key)
    panel = NetworkChartPanel(); panel.set_descriptor(descriptor, network)
    canvas = make_canvas(panel.chart_views[0].data, size, detailed)
    try:
        assert canvas.data.kind == 'bar'
        peak = max(canvas._value_range_values())
        assert peak > 0
        assert canvas.axis.lower == 0
        assert peak <= canvas.axis.upper * canvas.axis.scale <= peak * 1.3
        assert descriptor.result is panel.result
    finally:
        canvas.close(); panel.close()


@pytest.mark.parametrize('values', [[0, 0], [100, 100], [-100, -100], [-5, 3],
                                    [-.002, .001], [1000000000001, 1000000000002]])
def test_zero_constant_signed_and_tiny_auto_ranges_preserve_precision(values):
    canvas = make_canvas(ChartData('line', ['a', 'b'], [Series('a', '实际值', QColor('blue'), values)]))
    try:
        assert canvas.axis.lower * canvas.axis.scale <= min(values)
        assert canvas.axis.upper * canvas.axis.scale >= max(values)
        labels = [_tick_text(tick, canvas.axis.step) for tick in canvas._ticks()]
        assert len(labels) == len(set(labels))
        assert all(len(label.partition('.')[2]) <= 2 for label in labels)
        assert canvas.data.series[0].values == values
    finally:
        canvas.close()


def test_signed_stacks_and_comparison_period_are_fully_inside_the_auto_axis():
    data = ChartData('bar', ['a', 'b'], [
        Series('income', '收入', QColor('blue'), [12, 18], stack='current'),
        Series('other-income', '其他收入', QColor('green'), [4, 7], stack='current'),
        Series('cost', '成本', QColor('red'), [-9, -11], stack='current'),
        Series('other-cost', '其他成本', QColor('orange'), [-5, -9], stack='current'),
        Series('comparison', '上周同期', QColor('purple'), [30, -25], stack='previous', faded=True),
    ])
    canvas = make_canvas(data, (400, 140))
    try:
        assert canvas.axis.lower <= -25
        assert canvas.axis.upper >= 30
        assert 0 in canvas._ticks()
        assert all(canvas.plot_rect().top() <= canvas._y(value) <= canvas.plot_rect().bottom()
                   for value in [-25, -20, -14, 16, 25, 30])
    finally:
        canvas.close()


@pytest.mark.parametrize('kind', ['line', 'bar', 'hbar'])
def test_shared_explicit_axis_keeps_identity_and_coordinates_after_resize(kind):
    canvas = make_canvas(ChartData(kind, ['a', 'b'], [Series('a', '实际值', QColor('blue'), [1, 2])]))
    spec = AxisSpec(-2, 4, 2)
    try:
        canvas.set_axis(spec); canvas.grab()
        assert canvas.axis is spec
        canvas.resize(480, 260); canvas.grab()
        assert canvas.axis is spec
        assert canvas._ticks() == [-2, 0, 2, 4]
        assert canvas.data.series[0].values == [1, 2]
    finally:
        canvas.close()


def evidence(label='after'):
    app = QApplication.instance() or QApplication([])
    from stats_style import initialize_theme
    initialize_theme(app)
    OUT.mkdir(parents=True, exist_ok=True)
    dpr = app.primaryScreen().devicePixelRatio()
    tag = str(dpr).replace('.', '_')
    network = real_network()
    records = []
    for key in ('transport-by-type', 'transport-by-group', 'trip-types'):
        descriptor = next(chart for chart in network.charts if chart.key == key)
        panel = NetworkChartPanel(); panel.set_descriptor(descriptor, network)
        for mode, size, detailed in [('screenshot', (228, 140), False), ('compact', (400, 190), False),
                                      ('normal', (480, 260), False), ('detail', (960, 540), True)]:
            canvas = make_canvas(panel.chart_views[0].data, size, detailed)
            assert canvas.grab().save(str(OUT / f'{label}-{key}-{mode}-dpr{tag}.png'))
            records.append(dict(key=key, title=descriptor.title, mode=mode, size=size,
                                dpr=canvas.devicePixelRatioF(), plot=canvas.plot_rect().getRect(),
                                observed_peak=max(canvas._value_range_values()),
                                axis=vars(canvas.axis), ticks=canvas._ticks(),
                                labels=[_tick_text(tick, canvas.axis.step) for tick in canvas._ticks()]))
            canvas.close()
        panel.close()
    (OUT / f'{label}-dpr{tag}.json').write_text(json.dumps(dict(source=str(SAVE), records=records),
        ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'A-04 offscreen {label} evidence rendered at DPR {dpr}: {OUT}')


if __name__ == '__main__':
    evidence(sys.argv[1] if len(sys.argv) > 1 else 'after')
