"""Network chart geometry and public behavior against the agreed descriptor shape."""
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

from PySide6.QtCharts import QBarCategoryAxis, QHorizontalBarSeries, QLineSeries, QPieSeries
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


def test_company_and_category_order_ignores_result_dict_insertion_order():
    app()
    context = ordered_snapshot('companies')
    line = NetworkChartPanel()
    line.set_descriptor(descriptor(
        reversed_series(make_result(companies=('a', 'b'), groups=('总计',))),
        key='linecount', allowed=('line',)), context)
    assert [source[1] for source in line._sources()] == ['a', 'b']
    assert line._legend_keys == ['a', 'b']

    stacks = NetworkChartPanel()
    stacked_data = reversed_series(make_result(
        companies=('a', 'b'), groups=('bus', 'tram')))
    stacks.set_descriptor(descriptor(stacked_data), context)
    assert stacks._group_ids(stacks._sources()) == ['a', 'b']
    assert stacks._category_ids(stacks._sources()) == ['bus', 'tram']
    assert [(segment['company'], segment['category'])
            for segment in stacks.bar_segments if segment['slot'] == 0] == [
                ('a', 'bus'), ('a', 'tram'), ('b', 'bus'), ('b', 'tram')]
    stacks._open_fullscreen()
    clone = stacks._fullscreen_dialog.findChildren(NetworkChartPanel)[0]
    assert clone._group_ids(clone._sources()) == ['a', 'b']
    assert clone._category_ids(clone._sources()) == ['bus', 'tram']
    stacks._fullscreen_dialog.close()

    bars = NetworkChartPanel()
    quantity = reversed_series(make_result(
        'stopcount', companies=('a', 'b'), groups=('bus', 'tram')))
    endpoints = reversed_series(endpoint_result(quantity))
    bars.set_descriptor(descriptor(quantity, key='stopcount', allowed=('bar',),
                                   bar_result=endpoints), context)
    assert bars._group_ids(bars._sources()) == ['a', 'b']
    assert bars._category_ids(bars._sources()) == ['bus', 'tram']

    share = NetworkChartPanel()
    share.set_descriptor(descriptor(
        reversed_series(make_result(companies=('a', 'b'), groups=('总计',))),
        key='company-passengers', allowed=('pie',)), context)
    slices = share.chart_views[0].visuals[0]['slices']
    assert [item['company'] for item in slices] == ['a', 'b']
    assert share._legend_keys == ['a', 'b']
    flipped = ordered_snapshot('companies')
    flipped.filters.companies = ('b', 'a')
    selected = NetworkChartPanel()
    selected.set_descriptor(descriptor(stacked_data), flipped)
    assert selected._group_ids(selected._sources()) == ['b', 'a']
    for panel in (line, stacks, bars, share, selected):
        panel.deleteLater()


def test_overall_time_columns_stack_categories_on_real_time_axis():
    app()
    panel = NetworkChartPanel()
    data = make_result(companies=('a',), groups=('bus', 'tram'))
    panel.set_descriptor(descriptor(data), snapshot('overall'))
    chart = panel.chart_views[0].chart()
    assert chart.axes(Qt.Orientation.Horizontal)[0].categoriesLabels() == ['02-19', '02-20', '02-21']
    assert [part['value'] for part in panel.bar_segments if part['slot'] == 0] == [13, 16]
    same_day = [part for part in panel.bar_segments if part['slot'] == 0]
    assert same_day[0]['group'] == same_day[1]['group'] == '__overall__'
    assert same_day[0]['category'] != same_day[1]['category']
    assert same_day[0]['item'].rect().left() == same_day[1]['item'].rect().left()
    assert panel.axis_spec.upper * panel.axis_spec.scale >= 29
    panel.deleteLater()


def test_category_palette_is_shared_by_stacks_lines_pies_and_legend():
    app()
    panel = NetworkChartPanel()
    data = make_result(companies=('a',), groups=('bus', 'tram', 'trolley'))
    panel.set_descriptor(descriptor(data, allowed=('trend-bar', 'line', 'pie')),
                         snapshot('overall'))
    expected = {group: panel._category_color(group)
                for group in ('bus', 'tram', 'trolley')}
    assert [color.name() for color in expected.values()] == [
        QColor(value).name() for value in tokens.DATA_CATEGORY_COLORS[:3]]
    assert all(item['color'] == expected[item['category']] for item in panel.bar_segments)
    assert all(panel._legend_color(group) == color for group, color in expected.items())
    category_colors = [QColor(value) for value in tokens.DATA_CATEGORY_COLORS[:6]]
    assert category_colors[0] == QColor(tokens.DATA_COMPANY_COLORS[0])
    assert all(color.hsvSaturationF() > .42 for color in category_colors)
    for left, right in zip(category_colors, category_colors[1:]):
        hue_gap = abs(left.hslHueF() - right.hslHueF())
        assert min(hue_gap, 1 - hue_gap) > .12
        assert abs(left.lightnessF() - right.lightnessF()) > .07
    panel.set_mode('line')
    assert all(visual['color'] == expected[visual['group']] for view in panel.chart_views
               for visual in view.visuals if visual.get('type') == 'line')
    assert all(not visual['area'] for view in panel.chart_views
               for visual in view.visuals if visual.get('type') == 'line')
    panel.set_mode('pie')
    assert all(item['color'] == expected[item['group']] for view in panel.chart_views
               for visual in view.visuals if visual.get('type') == 'network-pie'
               for item in visual['slices'])
    panel.deleteLater()


def test_network_chart_height_budget_allows_compact_six_category_card():
    app()
    panel = NetworkChartPanel()
    data = make_result('stopcount', companies=('a',),
                       groups=('bus', 'tram', 'trolley', 'metro', 'waterbus', 'misc'))
    panel.set_company_palette({'a': tokens.DATA_COMPANY_COLORS[0]})
    panel.set_compact_height(190)
    panel.set_descriptor(descriptor(data, key='stopcount', allowed=('bar',),
                                    bar_result=endpoint_result(data)), snapshot('overall'))
    panel.resize(420, 190)
    panel.show()
    app().processEvents()
    assert panel.height() == 190
    assert panel.chart_views[0].minimumHeight() <= 104
    assert panel.chart_views[0].chart().plotArea().height() >= 45
    assert panel.legend_host.isVisible()
    panel.close()


def test_compact_pie_keeps_plot_and_legend_readable_at_four_column_width():
    app()
    panel = NetworkChartPanel()
    data = make_result(companies=('a',),
                       groups=('bus', 'tram', 'trolley', 'metro', 'waterbus', 'misc'))
    panel.set_compact_height(230)
    panel.set_descriptor(descriptor(data, allowed=('pie',)), snapshot('overall'))
    panel.resize(282, 230)
    panel.show()
    app().processEvents()
    assert panel.width() == 282
    assert panel.chart_views[0].chart().plotArea().height() >= 80
    assert panel.legend_host.isVisible()
    assert panel._layout.indexOf(panel.legend_host) >= 0
    panel.close()


def test_four_column_compact_cards_keep_axes_inside_card_boundary():
    app()
    categories = ('bus', 'tram', 'trolley', 'metro', 'waterbus', 'misc')
    for mode in ('line', 'trend-bar', 'bar', 'pie'):
        panel = NetworkChartPanel()
        data = make_result('stopcount' if mode == 'bar' else
                           'transport-by-type', companies=('a',), groups=categories)
        panel.set_compact_height(230)
        panel.set_descriptor(descriptor(
            data, key='stopcount' if mode == 'bar' else 'transport-by-type',
            allowed=(mode,), bar_result=endpoint_result(data) if mode == 'bar' else None),
            snapshot('overall'))
        panel.resize(282, 230)
        panel.show()
        app().processEvents()
        view = panel.chart_views[0]
        assert view.mapTo(panel, QPoint(0, view.height())).y() <= panel.height() - 3
        assert view.chart().plotArea().height() >= 65
        panel.close()


def test_compact_overview_keeps_dense_mode_switch_in_title_row_without_clipping_axis():
    app()
    panel = NetworkChartPanel()
    panel.set_compact_height(230)
    selector = FluentSegmentedControl(panel, compact=True, dense=True)
    selector.addItem('trend-bar', '趋势')
    selector.addItem('pie', '比例')
    panel.set_mode_control(selector)
    data = make_result(companies=('a',),
                       groups=('bus', 'tram', 'trolley', 'metro', 'waterbus', 'misc'))
    panel.set_descriptor(descriptor(data, allowed=('trend-bar', 'pie')),
                         snapshot('overall'))
    panel.title_label.setText('平均运行车辆数')
    panel.resize(282, 230)
    panel.show()
    app().processEvents()
    assert not panel._external_mode_row_host.isVisible()
    assert panel._header_layout.indexOf(selector) >= 0
    assert selector.width() <= 120
    assert panel.title_label.font().pixelSize() <= 14
    assert not panel.title_label.wordWrap()
    assert panel.title_label.height() <= 28
    assert all(panel.legend_layout.itemAtPosition(0, index).widget() is button
               for index, button in enumerate(panel.legend_buttons.values()))
    assert panel.legend_layout.itemAtPosition(1, 0) is None
    assert panel.legend_layout.alignment() & Qt.AlignmentFlag.AlignHCenter
    view = panel.chart_views[0]
    assert view.mapTo(panel, QPoint(0, view.height())).y() <= panel.height() - 3
    assert panel.legend_buttons['tram'].toolTip() == '有轨电车'
    panel.set_mode('pie')
    app().processEvents()
    pie_view = panel.chart_views[0]
    assert pie_view.mapTo(panel, QPoint(0, pie_view.height())).y() <= panel.height() - 3
    panel.close()


def test_compact_vehicle_title_fits_narrow_card_and_restores_on_resize():
    app()
    panel = NetworkChartPanel()
    assert panel._header_layout.itemAt(0).widget() is panel.title_label
    assert not hasattr(panel, 'title_icon')
    data = make_result('vehicles-running', companies=('a',), groups=('bus',))
    item = descriptor(data, key='vehicles-running', allowed=('line',))
    panel.set_compact_height(266)
    panel.set_descriptor(item, snapshot('overall'))
    panel.resize(286, 266)
    panel.show()
    app().processEvents()
    assert panel.title_label.text() == '运行车辆数'
    assert not panel.title_label.wordWrap()
    assert panel.title_label.toolTip() == item.title
    panel.resize(406, 266)
    app().processEvents()
    assert panel.title_label.text() == item.title
    panel.close()


def test_period_switch_stays_in_title_row_on_narrow_card():
    app()
    panel = NetworkChartPanel()
    data = make_result(companies=('a',), groups=('bus', 'tram'))
    panel.set_compact_height(230)
    selector = FluentSegmentedControl(panel, compact=True, dense=True)
    selector.addItem('trend-bar', '趋势')
    selector.addItem('pie', '比例')
    panel.set_mode_control(selector)
    panel.set_descriptor(descriptor(data, allowed=('trend-bar', 'pie'), company_id='a'),
                         snapshot('period'))
    panel.resize(282, 230)
    panel.show()
    app().processEvents()
    assert selector.width() <= 120
    assert panel._header_layout.indexOf(selector) >= 0
    assert not panel._external_mode_row_host.isVisible()
    assert not panel.title_label.wordWrap()
    panel.close()


def test_period_legend_uses_the_selected_company_color():
    app()
    palette = {'a': tokens.DATA_COMPANY_COLORS[0], 'b': tokens.DATA_COMPANY_COLORS[1]}
    for company in ('a', 'b'):
        panel = NetworkChartPanel()
        panel.set_company_palette(palette)
        data = make_result(companies=(company,), groups=('bus',), comparison=True)
        panel.set_descriptor(descriptor(data, allowed=('line',), company_id=company),
                             snapshot('period'))
        color = QColor(palette[company])
        for key in ('current', 'comparison'):
            assert panel._legend_key_color(key) == color
            icon = panel.legend_buttons[key].icon().pixmap(12, 12).toImage()
            assert icon.pixelColor(6, 6) == color
        assert all(visual['color'] == color and visual['area']
                   for view in panel.chart_views for visual in view.visuals
                   if visual.get('type') == 'line')
        panel.deleteLater()


def test_single_category_period_does_not_repeat_the_legend_in_compact_card():
    app()
    panel = NetworkChartPanel()
    panel.set_compact_height(180)
    data = make_result('linecount', companies=('a',), groups=('总计',),
                       comparison=True)
    panel.set_descriptor(descriptor(data, key='linecount', allowed=('line',),
                                    company_id='a'), snapshot('period'))
    panel.resize(550, 180)
    panel.show()
    app().processEvents()
    assert panel._legend_keys == ['current', 'comparison']
    assert not panel.period_label.isVisible()
    assert panel._header_layout.indexOf(panel.legend_host) >= 0
    assert panel.chart_views[0].chart().plotArea().height() >= 80
    panel.close()


def test_compact_category_period_uses_one_legend_row_and_inline_positions():
    app()
    panel = NetworkChartPanel()
    panel.set_compact_height(180)
    selector = FluentSegmentedControl(panel, compact=True, dense=True)
    selector.addItem('trend-bar', '趋势')
    selector.addItem('pie', '比例')
    panel.set_mode_control(selector)
    data = make_result('transport-by-type', companies=('a',),
                       groups=('bus', 'tram', 'trolley', 'metro', 'waterbus', 'misc'),
                       comparison=True)
    panel.set_descriptor(descriptor(data, key='transport-by-type',
                                    allowed=('trend-bar', 'pie'), company_id='a'),
                         snapshot('period'))
    panel.resize(400, 180)
    panel.show()
    app().processEvents()
    assert panel.legend_layout.itemAtPosition(0, 5) is not None
    assert panel._header_layout.indexOf(panel.period_label) >= 0
    assert '本期' in panel.period_label.text() and '环比' in panel.period_label.text()
    assert panel.chart_views[0].chart().plotArea().height() >= 70
    panel.legend_buttons['bus'].click()
    assert panel.legend_buttons['bus'].width() == 43
    panel.resize(340, 180)
    app().processEvents()
    assert panel.width() == 340
    assert panel.legend_layout.itemAtPosition(0, 5) is not None
    assert panel.legend_layout.itemAtPosition(1, 0) is None
    assert panel._header_layout.indexOf(panel.period_label) < 0
    assert panel.legend_buttons['bus'].width() == 43
    panel.close()


def test_hover_tooltip_uses_the_series_category_color(monkeypatch):
    app()
    panel = NetworkChartPanel()
    data = make_result(companies=('a',), groups=('bus', 'tram'))
    panel.set_descriptor(descriptor(data), snapshot('overall'))
    captured = []
    monkeypatch.setattr('stats_charts.QToolTip.showText',
                        lambda *args: captured.append(args[1]))
    segment = next(item for item in panel.bar_segments if item['category'] == 'tram')
    panel._fluent_hover(dict(segment, type='network-hit'))
    assert captured and 'color:#f5a653' in captured[0]
    assert '●' in captured[0] and '有轨电车' in captured[0]
    panel.deleteLater()


def test_company_time_columns_are_side_by_side_with_stacks_inside_each_company():
    app()
    panel = NetworkChartPanel()
    panel.set_company_palette({'a': '#1677FF', 'b': '#00A67A'})
    panel.set_descriptor(descriptor(make_result()), snapshot('companies'))
    app().processEvents()
    first_day = [part for part in panel.bar_segments if part['slot'] == 0]
    assert {part['group'] for part in first_day} == {'a', 'b'}
    a = [part for part in first_day if part['group'] == 'a']
    b = [part for part in first_day if part['group'] == 'b']
    assert a[0]['item'].rect().left() == a[1]['item'].rect().left()
    assert a[0]['item'].rect().left() < b[0]['item'].rect().left()
    assert '甲公司' in a[0]['item'].toolTip() and '公交' in a[0]['item'].toolTip()
    before = [part['value'] for part in panel.bar_segments]
    panel.legend_buttons['bus'].click()
    assert all(not part['item'].isVisible() for part in panel.bar_segments if part['category'] == 'bus')
    assert [part['value'] for part in panel.bar_segments] == before
    panel.deleteLater()


def test_period_columns_keep_extra_comparison_slots_and_true_dates():
    app()
    panel = NetworkChartPanel()
    data = make_result(companies=('a',), comparison=True, compare_extra=2)
    panel.set_descriptor(descriptor(data, company_id='a'), snapshot('period', '上周同期'))
    chart = panel.chart_views[0].chart()
    assert len(chart.axes(Qt.Orientation.Horizontal)[0].categoriesLabels()) == 5
    last = next(part for part in panel.bar_segments
                if part['slot'] == 4 and part['group'] == 'comparison' and part['category'] == 'bus')
    assert '2024-02-20' in last['item'].toolTip()
    assert '上周同期' in last['item'].toolTip()
    assert not any(part['slot'] == 4 and part['group'] == 'current' for part in panel.bar_segments)
    panel.deleteLater()


def test_category_pies_are_separate_per_company_or_period_and_share_is_one_pie():
    app()
    panel = NetworkChartPanel()
    data = make_result()
    panel.set_descriptor(descriptor(data), snapshot('companies'))
    panel.set_mode('pie')
    assert len(panel.chart_views) == 2
    pies = [view.chart().series()[0] for view in panel.chart_views]
    assert all(isinstance(pie, QPieSeries) and pie.count() == 2 for pie in pies)
    first_total = sum(piece.value() for piece in pies[0].slices())
    panel.legend_buttons['bus'].click()
    assert sum(piece.value() for piece in pies[0].slices()) == first_total
    assert pies[0].slices()[0].brush().color().alpha() == 0
    period_data = make_result(companies=('a',), comparison=True)
    panel.set_descriptor(descriptor(period_data, company_id='a'), snapshot('period'))
    panel.set_mode('pie')
    assert len(panel.chart_views) == 2
    shares = make_result(metric='transport-by-type', groups=('总计',))
    panel.set_descriptor(descriptor(shares, key='company-passengers'), snapshot('companies'))
    panel.set_mode('pie')
    assert len(panel.chart_views) == 1
    assert panel.chart_views[0].chart().series()[0].count() == 2
    tooltips = [part['tooltip'] for part in panel.chart_views[0].visuals[0]['slices']]
    assert all('shares' not in tip and '本期' not in tip for tip in tooltips)
    assert '甲公司' in tooltips[0] and tooltips[0].count('甲公司') == 1
    panel.deleteLater()


def test_stopcount_horizontal_bars_align_same_category_across_companies():
    app()
    panel = NetworkChartPanel()
    data = make_result(metric='stopcount')
    panel.set_descriptor(descriptor(data, key='stopcount', allowed=('bar', 'line'),
                                    bar_result=endpoint_result(data)),
                         snapshot('companies'))
    chart = panel.chart_views[0].chart()
    bars = next(series for series in chart.series() if isinstance(series, QHorizontalBarSeries))
    assert [bar.count() for bar in bars.barSets()] == [2, 2]
    assert chart.axes(Qt.Orientation.Vertical)[0].categories() == ['公交', '有轨电车']
    # QtCharts geometry stays transparent; the Fluent painter owns visible hues.
    visible = panel.chart_views[0].visuals[0]['sets']
    assert visible[0]['colors'] != visible[1]['colors']
    # Category hue stays recognizable while company shades differ.
    assert all(abs(left.hsvHueF() - right.hsvHueF()) < .02
               for left, right in zip(visible[0]['colors'], visible[1]['colors']))
    assert [item['company'] for item in visible] == ['a', 'b']
    panel.set_mode('line')
    assert '━ 甲公司' in panel.period_label.text()
    assert '┄ 乙公司' in panel.period_label.text()
    panel.deleteLater()


def test_line_has_gap_and_reasons_show_without_fabricated_series():
    app()
    panel = NetworkChartPanel()
    data = make_result(metric='linecount', companies=('a',), groups=('总计',),
                       missing=('a', '总计', 1, False))
    panel.set_descriptor(descriptor(data, key='linecount', allowed=('line', 'bar')),
                         snapshot('overall'))
    assert len([series for series in panel.chart_views[0].chart().series()
                if isinstance(series, QLineSeries)]) == 2
    panel.set_descriptor(descriptor(data, key='vehicles-running', allowed=('line', 'bar'),
                                    reason='缺少瞬时峰值历史'), snapshot('overall'))
    assert panel.chart_views == []
    assert '缺少瞬时峰值历史' in panel.placeholder.text()
    panel.clear()
    assert panel.chart_views == []
    panel.deleteLater()


def test_fullscreen_preserves_descriptor_mode_and_legend_state():
    app()
    panel = NetworkChartPanel()
    data = make_result()
    panel.set_descriptor(descriptor(data), snapshot('companies'))
    panel.set_mode('pie')
    panel.legend_buttons['bus'].click()
    panel.fullscreen_button.click()
    dialog = panel._fullscreen_dialog
    clone = dialog.findChild(NetworkChartPanel)
    assert dialog.isVisible() and clone.mode == 'pie'
    assert clone.descriptor.result is data
    assert 'bus' in clone._hidden_categories
    dialog.close()
    panel.deleteLater()


def test_single_category_company_legend_hides_only_its_column():
    app()
    panel = NetworkChartPanel()
    data = make_result(groups=('总计',))
    panel.set_descriptor(descriptor(data), snapshot('companies'))
    assert set(panel.legend_buttons) == {'a', 'b'}
    panel.legend_buttons['a'].click()
    assert all(not item['item'].isVisible() for item in panel.bar_segments
               if item['group'] == 'a')
    assert all(item['item'].isVisible() for item in panel.bar_segments
               if item['group'] == 'b')
    panel.deleteLater()


def test_visible_fluent_marks_render_and_dashboard_control_mounts_in_header():
    app()
    panel = NetworkChartPanel()
    control = QWidget()
    panel.set_mode_control(control)
    assert control.parent() is panel
    assert panel._header_layout.indexOf(control) >= 0
    panel.set_descriptor(descriptor(make_result(companies=('a',))), snapshot('overall'))
    panel.resize(500, 290)
    panel.show()
    app().processEvents()
    assert not panel.grab().isNull()
    assert all(part['rect'].width() > 0 for part in panel.bar_segments)
    panel.close()


def test_overall_nonaggregatable_coverage_keeps_company_identity():
    app()
    panel = NetworkChartPanel()
    data = make_result(metric='coverage', groups=('总计',))
    panel.set_descriptor(descriptor(data, key='coverage', allowed=('line',)),
                         snapshot('overall'))
    visuals = panel.chart_views[0].visuals
    assert {item['key'] for item in visuals} == {'a', 'b'}
    assert {item['color'].name() for item in visuals} == {
        panel._company_color('a').name(), panel._company_color('b').name()}
    assert set(panel.legend_buttons) == {'a', 'b'}
    assert panel.period_label.isHidden()
    assert '本期' not in panel._tip('a', '总计', data.series[('a', '总计')][0])
    panel.deleteLater()


def test_company_quantity_trend_uses_total_series_and_endpoint_bars_use_breakdown():
    app()
    panel = NetworkChartPanel()
    trend = make_result(metric='stopcount', groups=('总计',))
    bars = endpoint_result(make_result(metric='stopcount'))
    bars.series[('a', 'bus')][0].observed = datetime(2024, 2, 21, 18)
    bars.series[('a', 'bus')][0].complete = False
    panel.set_descriptor(descriptor(trend, key='stopcount', allowed=('line', 'bar'),
                                    bar_result=bars), snapshot('companies'))
    lines = panel.chart_views[0].visuals
    assert len(lines) == 2
    assert {item['group'] for item in lines} == {'总计'}
    assert {item['company'] for item in lines} == {'a', 'b'}
    assert all(len(item['points']) == 3 for item in lines)
    assert {item['color'].name() for item in lines} == {
        panel._company_color('a').name(), panel._company_color('b').name()}
    assert all(item['line_style'] is None for item in lines)
    panel.set_mode('bar')
    assert panel.result is bars
    visual = panel.chart_views[0].visuals[0]
    assert visual['names'] == ['bus', 'tram']
    assert visual['sets'][0]['raw_values'] == [Decimal(15), Decimal(18)]
    assert '2024-02-21 18:00' in visual['sets'][0]['tooltips'][0]
    assert '不完整' in visual['sets'][0]['tooltips'][0]
    panel.deleteLater()


def test_endpoint_bar_does_not_use_observation_at_or_after_cutoff():
    app()
    panel = NetworkChartPanel()
    trend = make_result(metric='stopcount', companies=('a',), groups=('总计',))
    bars = endpoint_result(make_result(metric='stopcount', companies=('a',)))
    bars.series[('a', 'bus')][0].observed = bars.current_window[1]
    panel.set_descriptor(descriptor(trend, key='stopcount', allowed=('bar', 'line'),
                                    bar_result=bars), snapshot('overall'))
    visual = panel.chart_views[0].visuals[0]
    assert visual['sets'][0]['raw_values'][0] is None
    assert visual['sets'][0]['tooltips'][0] == ''
    panel.deleteLater()


def test_company_total_line_legend_disambiguates_duplicate_company_names():
    app()
    panel = NetworkChartPanel()
    trend = make_result(metric='stopcount', groups=('总计',))
    state = snapshot('companies')
    state.companies = {'a': '同名公司', 'b': '同名公司'}
    panel.set_descriptor(descriptor(trend, key='stopcount',
                                    allowed=('line', 'bar')), state)
    assert {button.text() for button in panel.legend_buttons.values()} == {
        '同名公司 (a)', '同名公司 (b)'}
    panel.deleteLater()


def test_bar_mode_never_averages_history_or_uses_trend_as_breakdown():
    app()
    panel = NetworkChartPanel()
    trend = make_result(metric='vehicles-running', groups=('总计',))
    full_history = make_result(metric='vehicles-running', groups=('bus', 'tram'))
    panel.set_descriptor(descriptor(trend, key='vehicles-running',
                                    allowed=('line', 'bar'), bar_result=full_history),
                         snapshot('companies'))
    panel.set_mode('bar')
    assert panel.chart_views == [] or all(
        visual['type'] == 'empty' for view in panel.chart_views for visual in view.visuals)
    panel.set_descriptor(descriptor(trend, key='vehicles-running',
                                    allowed=('line', 'bar')), snapshot('companies'))
    panel.set_mode('bar')
    assert panel.chart_views == []
    selected = endpoint_result(full_history)
    panel.set_descriptor(descriptor(trend, key='vehicles-running',
                                    allowed=('line', 'bar'), bar_result=selected),
                         snapshot('companies'))
    panel.set_mode('bar')
    assert panel.chart_views[0].visuals[0]['sets'][0]['raw_values'] == [
        Decimal(15), Decimal(18)]
    panel.deleteLater()


def test_period_endpoint_bars_keep_each_periods_real_observation_time():
    app()
    panel = NetworkChartPanel()
    trend = make_result(metric='stopcount', companies=('a',), groups=('总计',),
                        comparison=True)
    bars = endpoint_result(make_result(metric='stopcount', companies=('a',),
                                       comparison=True))
    current = bars.series[('a', 'bus')][0]
    previous = bars.comparison[('a', 'bus')][0]
    current.observed = datetime(2024, 2, 21, 18)
    previous.observed = datetime(2024, 2, 18, 17)
    panel.set_descriptor(descriptor(trend, key='stopcount', allowed=('line', 'bar'),
                                    company_id='a', bar_result=bars),
                         snapshot('period', '上周同期'))
    panel.set_mode('bar')
    sets = panel.chart_views[0].visuals[0]['sets']
    assert sets[0]['raw_values'][0] == current.value
    assert sets[1]['raw_values'][0] == previous.value
    assert '2024-02-21 18:00' in sets[0]['tooltips'][0]
    assert '2024-02-18 17:00' in sets[1]['tooltips'][0]
    assert '上周同期' in sets[1]['tooltips'][0]
    panel.deleteLater()


def test_fullscreen_endpoint_bar_keeps_bar_result_and_shared_axis():
    app()
    panel = NetworkChartPanel()
    trend = make_result(metric='stopcount', companies=('a',), groups=('总计',))
    bars = endpoint_result(make_result(metric='stopcount', companies=('a',)))
    panel.set_descriptor(descriptor(trend, key='stopcount', allowed=('line', 'bar'),
                                    bar_result=bars), snapshot('overall'))
    panel.set_mode('bar')
    panel.set_axis_spec(AxisSpec(0, 100, 20))
    panel.fullscreen_button.click()
    clone = panel._fullscreen_dialog.findChild(NetworkChartPanel)
    assert clone.mode == 'bar' and clone.result is bars
    assert clone.axis_spec == AxisSpec(0, 100, 20)
    panel._fullscreen_dialog.close()
    panel.deleteLater()


def test_future_selected_coverage_series_has_public_identity_in_legend():
    app()
    panel = NetworkChartPanel()
    data = make_result(metric='coverage', companies=('__selected__', 'a'),
                       groups=('总计',))
    panel.set_descriptor(descriptor(data, key='coverage', allowed=('line',)),
                         snapshot('overall'))
    assert panel.legend_buttons['__selected__'].text() == '已选公司'
    assert panel._group_name('__selected__') == '已选公司'
    assert '__selected__' not in panel._tip('__selected__', '总计',
                                            data.series[('__selected__', '总计')][0])
    panel.deleteLater()


def test_shared_axis_override_controls_network_line_horizontal_and_stacked_marks():
    app()
    spec = AxisSpec(0, 100, 20)
    cases = (
        ('linecount', ('line', 'bar'), 'line', ('总计',)),
        ('stopcount', ('bar', 'line'), 'bar', ('bus', 'tram')),
        ('transport-by-type', ('trend-bar', 'pie'), 'trend-bar', ('bus', 'tram')),
    )
    for metric, allowed, mode, groups in cases:
        panel = NetworkChartPanel()
        data = make_result(metric=metric, companies=('a',), groups=groups,
                           comparison=True)
        panel.set_descriptor(descriptor(data, key=metric, allowed=allowed,
                                        company_id='a',
                                        bar_result=endpoint_result(data) if mode == 'bar' else None),
                             snapshot('period'))
        panel.set_mode(mode)
        panel.set_axis_spec(spec)
        if mode == 'line':
            assert panel._legend_keys == ['current', 'comparison']
            assert panel.period_label.text() == ''
        panel.resize(480, 300)
        panel.show()
        app().processEvents()
        orientation = (Qt.Orientation.Horizontal if mode == 'bar' else
                       Qt.Orientation.Vertical)
        axes = panel.chart_views[0].chart().axes(orientation)
        assert any(axis.min() == 0 and axis.max() == 100 and
                   axis.tickInterval() == 20 for axis in axes)
        assert all(not axis.truncateLabels() for axis in axes)
        assert panel.axis_spec == spec
        assert all(visual['axis'] == spec for visual in panel.chart_views[0].visuals)
        panel.close()
