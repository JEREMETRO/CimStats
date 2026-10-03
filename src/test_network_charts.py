"""Network chart cards: descriptor/snapshot -> ChartData, legend and fullscreen."""
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget

from statistics_model import Bucket, METRICS, Query, Result
from network_charts import NetworkChartPanel
from stats_charts import AxisSpec
from stats_controls import FluentSegmentedControl
import stats_tokens as tokens


def app():
    return QApplication.instance() or QApplication([])


def make_result(metric='transport-by-type', companies=('a', 'b'), groups=('bus', 'tram'),
                comparison=False, compare_extra=0, missing=None):
    start = datetime(2024, 2, 19)
    end = start + timedelta(days=3)
    earlier = (start - timedelta(days=3), start + timedelta(days=compare_extra)) if comparison else None
    current, previous = {}, {}
    for company_index, company in enumerate(companies):
        for group_index, group in enumerate(groups):
            key = (company, group)

            def bucket_list(first, count, prior=False):
                output = []
                for index in range(count):
                    date = first + timedelta(days=index)
                    raw = (company_index + 1) * 10 + (group_index + 1) * 3 + index
                    value = None if missing == (company, group, index, prior) else Decimal(raw + (5 if prior else 0))
                    output.append(Bucket(date, date + timedelta(days=1), value,
                                         value is not None, False, date if value is not None else None,
                                         None, None, 24))
                return output

            current[key] = bucket_list(start, 3)
            if comparison:
                previous[key] = bucket_list(earlier[0], 3 + compare_extra, True)
    query = Query(metric, companies, None, start, end, 'day', earlier)
    return Result(query, METRICS[metric], current, previous, (start, end), earlier)


def descriptor(data, key='transport-by-type', allowed=('trend-bar', 'pie'), reason='',
               company_id=None, bar_result=None):
    return SimpleNamespace(key=key, title=METRICS[key].label if key in METRICS else '分公司客流',
                           company_id=company_id, result=data, bar_result=bar_result,
                           allowed_modes=allowed, reason=reason)


def endpoint_result(data):
    return Result(data.query, data.metric,
                  {key: [buckets[-1]] for key, buckets in data.series.items() if buckets},
                  {key: [buckets[-1]] for key, buckets in data.comparison.items() if buckets},
                  data.current_window, data.comparison_window)


def snapshot(mode, comparison_label='环比'):
    return SimpleNamespace(options=SimpleNamespace(mode=mode, comparison_label=comparison_label),
                           companies={'a': '甲公司', 'b': '乙公司'})


def reversed_series(data):
    data.series = dict(reversed(list(data.series.items())))
    data.comparison = dict(reversed(list(data.comparison.items())))
    return data


def ordered_snapshot(mode):
    value = snapshot(mode)
    value.filters = SimpleNamespace(companies=('a', 'b'))
    value.companies = {'b': '乙公司', 'a': '甲公司'}
    return value


def chart(panel, index=0):
    return panel.chart_views[index].data


def test_company_and_category_order_ignores_result_dict_insertion_order():
    app()
    panel = NetworkChartPanel()
    data = reversed_series(make_result())
    panel.set_descriptor(descriptor(data), ordered_snapshot('companies'))
    series = chart(panel).series
    assert [(item.stack, item.key) for item in series] == [
        ('a', 'bus'), ('a', 'tram'), ('b', 'bus'), ('b', 'tram')]
    assert list(panel.legend_buttons) == ['bus', 'tram']
    panel.deleteLater()


def test_overall_time_columns_stack_categories_on_real_time_axis():
    app()
    panel = NetworkChartPanel()
    data = make_result(companies=('a',))
    panel.set_descriptor(descriptor(data), snapshot('overall'))
    data_chart = chart(panel)
    assert data_chart.kind == 'bar'
    assert data_chart.labels == ['02-19', '02-20', '02-21']
    assert len({item.stack for item in data_chart.series}) == 1
    assert [item.values[0] for item in data_chart.series] == [Decimal(13), Decimal(16)]
    panel.deleteLater()


def test_category_palette_is_shared_by_stacks_lines_pies_and_legend():
    app()
    panel = NetworkChartPanel()
    panel.set_descriptor(descriptor(make_result(companies=('a',)), allowed=('trend-bar', 'line', 'pie')),
                         snapshot('overall'))
    expected = {key: QColor(tokens.DATA_CATEGORY_COLORS[tokens.DATA_CATEGORY_GROUPS.index(key) % 6]).name()
                for key in ('bus', 'tram')}
    assert {item.key: item.color.name() for item in chart(panel).series} == expected
    panel.set_mode('line')
    assert {item.key: item.color.name() for item in chart(panel).series} == expected
    panel.set_mode('pie')
    pie = chart(panel).series[0]
    assert dict(zip(pie.keys, (color.name() for color in pie.colors))) == expected
    panel.deleteLater()


def test_company_time_columns_are_side_by_side_with_stacks_inside_each_company():
    app()
    panel = NetworkChartPanel()
    panel.set_descriptor(descriptor(make_result()), snapshot('companies'))
    stacks = [item.stack for item in chart(panel).series]
    assert stacks == ['a', 'a', 'b', 'b']
    panel.deleteLater()


def test_period_columns_keep_extra_comparison_slots_and_true_dates():
    app()
    panel = NetworkChartPanel()
    data = make_result(companies=('a',), comparison=True, compare_extra=1)
    panel.set_descriptor(descriptor(data, company_id='a'), snapshot('period', '上周同期'))
    data_chart = chart(panel)
    assert len(data_chart.labels) == 4
    previous = [item for item in data_chart.series if item.faded]
    assert previous and all(item.stack == 'comparison' for item in previous)
    assert '上周同期 2024-02-17' in previous[0].notes[1]
    panel.deleteLater()


def test_category_pies_are_separate_per_company_and_share_is_one_pie():
    app()
    panel = NetworkChartPanel()
    panel.set_descriptor(descriptor(make_result()), snapshot('companies'))
    panel.set_mode('pie')
    assert len(panel.chart_views) == 2
    assert [label.text() for label in panel.company_labels] == ['甲公司', '乙公司']
    share = NetworkChartPanel()
    share.set_descriptor(descriptor(make_result(), key='company-passengers'), snapshot('companies'))
    share.set_mode('pie')
    assert len(share.chart_views) == 1
    assert chart(share).series[0].keys == ['a', 'b']
    panel.deleteLater()
    share.deleteLater()


def test_line_has_gap_and_reason_shows_without_fabricated_series():
    app()
    panel = NetworkChartPanel()
    data = make_result(companies=('a',), groups=('总计',), missing=('a', '总计', 1, False))
    panel.set_descriptor(descriptor(data, key='linecount', allowed=('line',)), snapshot('overall'))
    assert chart(panel).series[0].values[1] is None
    panel.set_descriptor(descriptor(data, key='linecount', allowed=('line',), reason='暂无历史记录'),
                         snapshot('overall'))
    assert panel.chart_views == []
    assert panel.placeholder.text() == '暂无历史记录' and not panel.fullscreen_button.isEnabled()
    panel.deleteLater()


def test_legend_toggle_hides_category_series_and_survives_fullscreen():
    app()
    panel = NetworkChartPanel()
    panel.set_descriptor(descriptor(make_result()), snapshot('companies'))
    panel.legend_buttons['bus'].click()
    assert panel.chart_views[0].hidden == {'bus'}
    panel.set_mode('pie')
    assert all(view.hidden == {'bus'} for view in panel.chart_views)
    clone = panel._open_fullscreen()
    assert clone.mode == 'pie' and 'bus' in clone._hidden_categories
    assert clone.descriptor is panel.descriptor
    panel._fullscreen_dialog.close()
    panel.deleteLater()


def test_single_category_company_legend_toggles_company_columns():
    app()
    panel = NetworkChartPanel()
    panel.set_descriptor(descriptor(make_result(groups=('总计',))), snapshot('companies'))
    assert set(panel.legend_buttons) == {'a', 'b'}
    panel.legend_buttons['a'].click()
    assert panel.chart_views[0].hidden == {'a'}
    assert [item.key for item in panel.chart_views[0].visible_series()] == ['b']
    panel.deleteLater()


def test_dashboard_mode_control_mounts_in_the_title_row():
    app()
    panel = NetworkChartPanel()
    control = FluentSegmentedControl()
    panel.set_mode_control(control)
    assert control.parentWidget() is panel
    assert panel._mode_slot.indexOf(control) >= 0
    panel.deleteLater()


def test_company_quantity_trend_uses_total_series_and_endpoint_bars_use_breakdown():
    app()
    panel = NetworkChartPanel()
    trend = make_result(metric='stopcount', groups=('总计',))
    bars = endpoint_result(make_result(metric='stopcount'))
    bars.series[('a', 'bus')][0].observed = datetime(2024, 2, 21, 18)
    bars.series[('a', 'bus')][0].complete = False
    panel.set_descriptor(descriptor(trend, key='stopcount', allowed=('line', 'bar'), bar_result=bars),
                         snapshot('companies'))
    lines = chart(panel).series
    assert [item.key for item in lines] == ['a', 'b']
    assert [item.color.name() for item in lines] == [panel._company_color('a').name(),
                                                     panel._company_color('b').name()]
    assert all(len(item.values) == 3 and not item.dashed for item in lines)
    panel.set_mode('bar')
    assert panel.result is bars
    data_chart = chart(panel)
    assert data_chart.kind == 'hbar' and data_chart.labels == ['公交', '有轨电车']
    assert data_chart.series[0].values == [Decimal(15), Decimal(18)]
    assert '数据不完整' in data_chart.series[0].notes[0]
    panel.deleteLater()


def test_endpoint_bar_does_not_use_observation_at_or_after_cutoff():
    app()
    panel = NetworkChartPanel()
    trend = make_result(metric='stopcount', companies=('a',), groups=('总计',))
    bars = endpoint_result(make_result(metric='stopcount', companies=('a',)))
    bars.series[('a', 'bus')][0].observed = bars.current_window[1]
    panel.set_descriptor(descriptor(trend, key='stopcount', allowed=('bar', 'line'), bar_result=bars),
                         snapshot('overall'))
    assert chart(panel).series[0].values[0] is None
    panel.deleteLater()


def test_company_total_line_legend_disambiguates_duplicate_company_names():
    app()
    panel = NetworkChartPanel()
    state = snapshot('companies')
    state.companies = {'a': '同名公司', 'b': '同名公司'}
    panel.set_descriptor(descriptor(make_result(metric='stopcount', groups=('总计',)), key='stopcount',
                                    allowed=('line', 'bar')), state)
    assert {chip.text() for chip in panel.legend_buttons.values()} == {'同名公司 [a]', '同名公司 [b]'}
    panel.deleteLater()


def test_bar_mode_never_averages_history_or_uses_trend_as_breakdown():
    app()
    panel = NetworkChartPanel()
    trend = make_result(metric='vehicles-running', groups=('总计',))
    full_history = make_result(metric='vehicles-running', groups=('bus', 'tram'))
    panel.set_descriptor(descriptor(trend, key='vehicles-running', allowed=('line', 'bar'),
                                    bar_result=full_history), snapshot('companies'))
    panel.set_mode('bar')
    assert not panel.chart_views[0].has_values()
    panel.set_descriptor(descriptor(trend, key='vehicles-running', allowed=('line', 'bar')),
                         snapshot('companies'))
    panel.set_mode('bar')
    assert panel.chart_views == []
    panel.set_descriptor(descriptor(trend, key='vehicles-running', allowed=('line', 'bar'),
                                    bar_result=endpoint_result(full_history)), snapshot('companies'))
    panel.set_mode('bar')
    assert chart(panel).series[0].values == [Decimal(15), Decimal(18)]
    panel.deleteLater()


def test_period_endpoint_bars_keep_each_periods_real_observation_time():
    app()
    panel = NetworkChartPanel()
    trend = make_result(metric='stopcount', companies=('a',), groups=('总计',), comparison=True)
    bars = endpoint_result(make_result(metric='stopcount', companies=('a',), comparison=True))
    current, previous = bars.series[('a', 'bus')][0], bars.comparison[('a', 'bus')][0]
    current.observed = datetime(2024, 2, 21, 18)
    previous.observed = datetime(2024, 2, 18, 17)
    panel.set_descriptor(descriptor(trend, key='stopcount', allowed=('line', 'bar'), company_id='a',
                                    bar_result=bars), snapshot('period', '上周同期'))
    panel.set_mode('bar')
    series = chart(panel).series
    assert series[0].values[0] == current.value and series[1].values[0] == previous.value
    assert [item.name for item in series] == ['本期', '上周同期']
    assert series[1].faded
    panel.deleteLater()


def test_fullscreen_endpoint_bar_keeps_bar_result_and_shared_axis():
    app()
    panel = NetworkChartPanel()
    trend = make_result(metric='stopcount', companies=('a',), groups=('总计',))
    bars = endpoint_result(make_result(metric='stopcount', companies=('a',)))
    panel.set_descriptor(descriptor(trend, key='stopcount', allowed=('line', 'bar'), bar_result=bars),
                         snapshot('overall'))
    panel.set_mode('bar')
    panel.set_axis_spec(AxisSpec(0, 100, 20))
    clone = panel._open_fullscreen()
    assert clone.mode == 'bar' and clone.result is bars
    assert clone.axis_spec == AxisSpec(0, 100, 20)
    assert clone._mode_slot.count() == 1
    panel._fullscreen_dialog.close()
    panel.deleteLater()


def test_selected_companies_series_has_public_identity_in_legend():
    app()
    panel = NetworkChartPanel()
    data = make_result(metric='coverage', companies=('__selected__', 'a'), groups=('总计',))
    panel.set_descriptor(descriptor(data, key='coverage', allowed=('line',)), snapshot('overall'))
    assert panel.legend_buttons['__selected__'].text() == '甲公司、乙公司合计'
    assert all('__selected__' not in item.name for item in chart(panel).series)
    panel.deleteLater()


def test_single_company_overall_and_enlarged_summary_use_selected_name():
    from chart_details import summary_cards
    app()
    panel = NetworkChartPanel()
    names = {'a': '任意公司甲', 'b': '任意公司乙'}
    state = snapshot('overall')
    state.companies = names
    state.filters = SimpleNamespace(companies=('b',))
    data = make_result(companies=('b',))
    panel.set_descriptor(descriptor(data), state)
    assert panel._group_name('__overall__') == '任意公司乙'
    assert panel._display_company('__selected__') == '任意公司乙'
    data.series = {('__selected__', category): buckets for (_, category), buckets in data.series.items()}
    assert summary_cards(data, names)[0]['name'] == '任意公司乙'
    state.filters.companies = ('a', 'b')
    assert panel._display_company('__selected__') == '任意公司甲、任意公司乙合计'
    panel.deleteLater()


def test_shared_axis_override_controls_line_horizontal_and_stacked_charts():
    app()
    spec = AxisSpec(0, 100, 20)
    for metric, allowed, groups in (('linecount', ('line', 'bar'), ('总计',)),
                                    ('transport-by-type', ('trend-bar', 'pie'), ('bus', 'tram'))):
        panel = NetworkChartPanel()
        panel.set_descriptor(descriptor(make_result(metric=metric, companies=('a',), groups=groups), key=metric,
                                        allowed=allowed), snapshot('overall'))
        panel.set_axis_spec(spec)
        assert all(view.axis_override is spec for view in panel.chart_views)
        panel.deleteLater()
