"""ChartPanel: Result -> ChartData mapping, modes, legend, hover linking, fullscreen."""
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from statistics_model import Bucket, METRICS, Query, Result
from stats_charts import AxisSpec, ChartPanel, _category_color, company_color, nice_axis
from stats_controls import FluentSegmentedControl
import stats_tokens as tokens


def bucket(day, value, month=1):
    start = datetime(2024, month, day)
    return Bucket(start, start + timedelta(days=1),
                  None if value is None else Decimal(str(value)),
                  value is not None, False, start, None, None, 24)


def result(series, metric='transport-by-type', comparison=None, comparison_window=None):
    query = Query(metric, ('a', 'b'), None, datetime(2024, 1, 1), datetime(2024, 1, 4), 'day',
                  comparison_window)
    return Result(query, METRICS[metric], series, comparison or {}, (query.start, query.end), comparison_window)


def app():
    return QApplication.instance() or QApplication([])


def panel(*args, **kwargs):
    app()
    widget = ChartPanel(*args, **kwargs)
    widget.resize(520, 320)
    return widget


def test_axis_has_integer_ticks_zero_anchor_and_full_negative_extent():
    for values in ([0], [0.2, 0.8], [1, 2], [180, 4200], [12000, 46000], [-7, 3]):
        axis = nice_axis(values)
        assert axis.lower * axis.scale <= min(0, *values)
        assert axis.upper * axis.scale >= max(0, *values)
        assert axis.lower < axis.upper and axis.step >= 1
        assert (axis.upper - axis.lower) / axis.step <= 7


def test_company_and_category_colors_are_stable():
    assert company_color('a') == company_color('a')
    assert company_color('a') != company_color('b')
    assert tokens.CHART_BLUE == tokens.COMPANY_COLORS[0]
    groups = ('BlueCollar', 'WhiteCollar', 'BusinessPeople', 'Pensioner', 'Student', 'Tourist')
    assert len({_category_color(group).name() for group in groups}) == len(groups)


def test_summary_keeps_companies_separate_and_missing_is_dash():
    widget = panel('客流', default_mode='summary')
    widget.set_result(result({('a', 'bus'): [bucket(1, 5)], ('b', 'bus'): [bucket(1, None)]}),
                      {'a': '甲', 'b': '乙'})
    text = widget.summary_label.text()
    assert '甲  5' in text and '乙  —' in text
    assert widget.chart_host.isHidden()


def test_line_mode_maps_buckets_to_slots_with_gaps_and_full_window():
    data = result({('a', 'bus'): [bucket(1, 1), bucket(2, None), bucket(3, 3)]})
    widget = panel('客流', default_mode='line')
    widget.set_result(data)
    chart = widget.chart_views[0].data
    assert chart.kind == 'line'
    assert chart.labels == ['01-01', '01-02', '01-03']
    assert chart.titles[0].startswith('2024-01-01')
    assert chart.series[0].values == [Decimal(1), None, Decimal(3)]


def test_time_bar_and_category_bar_and_pie_modes_build_the_right_kinds():
    data = result({('a', 'bus'): [bucket(1, 2), bucket(2, 3), bucket(3, 4)],
                   ('a', 'tram'): [bucket(1, 1), bucket(2, 1), bucket(3, 1)]})
    widget = panel('客流', modes=True, default_mode='trend-bar')
    widget.set_result(data)
    assert widget.chart_views[0].data.kind == 'bar'
    widget.set_mode('bar')
    hbar = widget.chart_views[0].data
    assert hbar.kind == 'hbar' and hbar.labels == ['公交', '有轨电车']
    assert hbar.series[0].values == [Decimal(9), Decimal(3)]
    widget.set_mode('pie')
    donut = widget.chart_views[0].data
    assert donut.kind == 'donut' and donut.series[0].keys == ['bus', 'tram']
    assert widget.result is data


def test_multi_company_categories_get_one_canvas_per_company_with_captions():
    data = result({('a', 'bus'): [bucket(1, 1)], ('a', 'tram'): [bucket(1, 2)],
                   ('b', 'bus'): [bucket(1, 3)], ('b', 'tram'): [bucket(1, 4)]})
    widget = panel('客流', default_mode='line')
    widget.set_result(data, {'a': '甲', 'b': '乙'})
    assert len(widget.chart_views) == 2
    assert [label.text() for label in widget.company_labels] == ['甲', '乙']


def test_company_totals_share_one_canvas_and_legend_names_companies():
    data = result({('a', '总计'): [bucket(1, 1), bucket(2, 2)], ('b', '总计'): [bucket(1, 3), bucket(2, 4)]})
    widget = panel('客流', default_mode='line')
    widget.set_company_palette({'a': '#112233', 'b': '#445566'})
    widget.set_result(data, {'a': '甲', 'b': '乙'})
    assert len(widget.chart_views) == 1
    assert [item.key for item in widget.chart_views[0].data.series] == ['a', 'b']
    assert widget.chart_views[0].data.series[0].color == QColor('#112233')
    assert {key: chip.text() for key, chip in widget.legend_buttons.items()} == {'a': '甲', 'b': '乙'}


def test_legend_toggle_hides_series_without_changing_result():
    data = result({('a', 'bus'): [bucket(1, 2)], ('a', 'tram'): [bucket(1, 1)]})
    widget = panel('客流', default_mode='line')
    widget.set_result(data)
    widget.legend_buttons['tram'].click()
    assert widget.chart_views[0].hidden == {'tram'}
    assert not widget.legend_buttons['tram'].isChecked()
    assert widget.result is data
    widget.legend_buttons['tram'].click()
    assert widget.chart_views[0].hidden == set()


def test_comparison_series_are_dashed_faded_and_share_the_key():
    current = {('a', 'bus'): [bucket(8, 2), bucket(9, 3)]}
    previous = {('a', 'bus'): [bucket(1, 1), bucket(2, 4)]}
    data = result(current, comparison=previous,
                  comparison_window=(datetime(2024, 1, 1), datetime(2024, 1, 3)))
    widget = panel('客流', default_mode='line')
    widget.set_result(data)
    series = widget.chart_views[0].data.series
    assert [item.faded for item in series] == [False, True]
    assert series[1].dashed and series[0].key == series[1].key
    assert '2024-01-02' in series[1].notes[1]
    assert widget.period_label.isHidden()
    assert [entry['key'] for entry in widget.series_legend_entries] == ['current', 'comparison']


def test_mode_selection_persists_and_labels_can_be_overridden(tmp_path):
    settings = QSettings(str(tmp_path / 'chart.ini'), QSettings.Format.IniFormat)
    widget = panel('客流', modes=True, default_mode='line', settings=settings, settings_key='chart/mode')
    assert isinstance(widget.mode_selector, FluentSegmentedControl)
    widget.set_mode('pie')
    assert settings.value('chart/mode') == 'pie'
    again = panel('客流', modes=True, default_mode='line', settings=settings, settings_key='chart/mode')
    assert again.mode == 'pie'
    again.set_mode_options(('line', 'trend-bar'))
    assert again.mode == 'line'
    # Both options read “趋势” by default: a switch with identical labels is hidden.
    assert again.mode_selector is None
    again.set_mode_labels({'line': '折线', 'trend-bar': '柱状'})
    assert again.mode_selector is not None


def test_shared_axis_spec_reaches_every_canvas_and_can_reset():
    data = result({('a', 'bus'): [bucket(1, 1)], ('b', 'bus'): [bucket(1, 2)], ('b', 'tram'): [bucket(1, 2)]})
    widget = panel('客流', default_mode='line')
    widget.set_result(data)
    spec = AxisSpec(0, 50, 10, 1, '')
    widget.set_axis_spec(spec)
    assert all(canvas.axis_override is spec for canvas in widget.chart_views)
    widget.set_axis_spec(None)
    assert all(canvas.axis_override is None for canvas in widget.chart_views)


def test_hover_offset_links_panels_by_relative_time():
    data = result({('a', 'bus'): [bucket(1, 1), bucket(2, 2), bucket(3, 3)]})
    first, second = panel('一', default_mode='line'), panel('二', default_mode='line')
    first.set_result(data)
    second.set_result(data)
    first.hover_offset_changed.connect(second.set_hover_offset)
    first._canvas_hover(first.chart_views[0], 2)
    assert second.chart_views[0]._linked == 2
    first._canvas_hover(first.chart_views[0], None)
    assert second.chart_views[0]._linked is None


def test_replacing_or_clearing_result_removes_old_canvases():
    widget = panel('客流', default_mode='line')
    widget.set_result(result({('a', 'bus'): [bucket(1, 1)], ('a', 'tram'): [bucket(1, 1)]}))
    old = list(widget.chart_views)
    widget.clear()
    assert widget.chart_views == [] and not any(canvas.isVisibleTo(widget) for canvas in old)
    assert widget.legend_host.isHidden() and not widget.fullscreen_button.isEnabled()


def test_fullscreen_clone_keeps_mode_hidden_groups_and_returns_changes():
    data = result({('a', 'bus'): [bucket(1, 2)], ('a', 'tram'): [bucket(1, 1)]})
    widget = panel('客流', modes=True, default_mode='line')
    widget.set_result(data)
    widget.legend_buttons['bus'].click()
    clone = widget._open_fullscreen()
    assert clone.mode == 'line' and clone._hidden_groups == {'bus'}
    assert clone.chart_views[0].detailed
    assert clone.detail_summary.cards[0]['values'] == [('bus', Decimal(2)), ('tram', Decimal(1))]
    clone.legend_buttons['tram'].click()
    widget._fullscreen_dialog.close()
    assert widget._hidden_groups == {'bus', 'tram'}


def test_compact_height_is_validated_and_released():
    widget = panel('客流')
    try:
        widget.set_compact_height(100)
    except ValueError:
        pass
    else:
        raise AssertionError('tiny compact height must be rejected')
    widget.set_compact_height(240)
    assert widget.height() == 240 or widget.maximumHeight() == 240
    widget.clear_compact_height()
    assert widget.maximumHeight() > 1000
