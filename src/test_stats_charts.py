import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from math import cos, radians, sin
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget
from PySide6.QtCore import QPointF, QRectF, QSettings, Qt
from PySide6.QtGui import QColor
from PySide6.QtCharts import QBarSeries, QCategoryAxis
from PySide6.QtTest import QTest
from qfluentwidgets import TransparentTogglePushButton, TransparentToolButton
from statistics_model import Bucket, METRICS, Query, Result
from stats_charts import AxisSpec, ChartPanel, _category_color, company_color, nice_axis
from fluent_chart_view import _bar_brush, _period_color
from stats_controls import FluentSegmentedControl
import stats_tokens as tokens


def bucket(day, value):
    start = datetime(2024, 1, day)
    return Bucket(start, start + timedelta(days=1),
                  None if value is None else Decimal(str(value)),
                  value is not None, False, start, None, None, 24)


def result(series, metric='transport-by-type'):
    query = Query(metric, ('a', 'b'), None, datetime(2024, 1, 1),
                  datetime(2024, 1, 4), 'day')
    return Result(query, METRICS[metric], series, {},
                  (query.start, query.end), None)


def app():
    return QApplication.instance() or QApplication([])


def test_axis_has_integer_ticks_zero_anchor_and_full_negative_extent():
    for values in ([0], [0.2, 0.8], [1, 2], [180, 4200], [12000, 46000], [-7, 3]):
        axis = nice_axis(values)
        assert axis.lower * axis.scale <= min(0, *values)
        assert axis.upper * axis.scale >= max(0, *values)
        assert axis.lower < axis.upper
        assert axis.step >= 1
        assert axis.lower % axis.step == axis.upper % axis.step == 0
        assert (axis.upper - axis.lower) / axis.step <= 7
        assert axis.step in (1, 2, 5) or any(axis.step == n * 10**power for n in (1, 2, 5) for power in range(1, 8))


def test_company_color_is_stable_across_selection_order():
    assert company_color('a') == company_color('a')
    assert company_color('a') != company_color('b')
    assert tokens.CHART_BLUE == tokens.COMPANY_COLORS[0]
    assert set(tokens.COMPANY_COLORS).isdisjoint(tokens.CATEGORY_COLORS)


def test_summary_keeps_companies_separate_and_missing_is_dash():
    app()
    panel = ChartPanel('分制式客流', modes=True, default_mode='summary')
    panel.set_result(result({('a', 'bus'): [bucket(1, 2), bucket(2, 3)],
                             ('b', 'bus'): [bucket(1, 8)],
                             ('b', 'tram'): [bucket(1, None)]}), {'a': '甲', 'b': '乙'})
    assert panel.summary_values == {'a': Decimal('5'), 'b': Decimal('8')}
    assert '甲' in panel.summary_label.text() and '乙' in panel.summary_label.text()
    panel.clear()
    assert panel.summary_values == {}
    panel.deleteLater()


def test_modes_preserve_result_and_pie_separates_companies():
    app()
    panel = ChartPanel('分制式客流', modes=True)
    data = result({('a', 'bus'): [bucket(1, 2)], ('a', 'tram'): [bucket(1, 3)],
                   ('b', 'bus'): [bucket(1, 7)]})
    panel.set_result(data, {'a': '甲', 'b': '乙'})
    panel.set_mode('pie')
    assert panel.result is data
    assert len(panel.chart_views) == 2
    assert {heading.text() for heading in panel.company_labels} == {'甲', '乙'}
    panel.set_mode('bar')
    assert len(panel.chart_views) == 2
    assert panel.mode_selector.currentKey() == 'bar'
    panel.deleteLater()


def test_replacing_visible_result_hides_old_views_and_legend_immediately():
    app()
    panel = ChartPanel('客流')
    panel.set_result(result({('a', 'bus'): [bucket(1, 2)],
                             ('b', 'tram'): [bucket(1, 3)]}))
    panel.show()
    app().processEvents()
    old_views = list(panel.chart_views)
    old_buttons = list(panel.legend_buttons.values())
    panel.set_result(result({('a', 'metro'): [bucket(1, 4)]}))
    assert all(not view.isVisible() for view in old_views)
    assert all(not button.isVisible() for button in old_buttons)
    panel.close()


def test_line_has_gap_for_missing_bucket_and_shared_range():
    app()
    panel = ChartPanel('分制式客流')
    panel.set_result(result({('a', 'bus'): [bucket(1, 2), bucket(2, None), bucket(3, 4)]}))
    assert len(panel.chart_views) == 1
    assert len(panel.chart_views[0].chart().series()) == 2
    panel.set_axis_range(0, 10, 2)
    assert panel.axis_spec.lower == 0 and panel.axis_spec.upper == 10
    panel.deleteLater()


def test_time_bar_uses_bars_and_retains_missing_dates(tmp_path):
    app()
    panel = ChartPanel('出行量', default_mode='trend-bar')
    panel.set_result(result({('', '总计'): [bucket(1, 2), bucket(2, None), bucket(3, 4)]}, 'trip-number'))
    chart = panel.chart_views[0].chart()
    assert any(isinstance(series, QBarSeries) for series in chart.series())
    assert chart.axes(Qt.Orientation.Horizontal)[0].categories() == ['01-01', '01-02', '01-03']
    panel.deleteLater()


def test_category_bars_leave_room_for_every_label_at_minimum_height():
    app()
    for count in (5, 6):
        groups = [f'group-{index}' for index in range(count)]
        panel = ChartPanel('分类', default_mode='bar')
        data = result({('a', group): [bucket(1, index + 1)]
                       for index, group in enumerate(groups)})
        data.comparison = {key: [bucket(1, index + 2)]
                           for index, key in enumerate(data.series)}
        panel.set_result(data)
        panel.resize(500, 500)
        panel.show()
        app().processEvents()
        view = panel.chart_views[0]
        view.resize(500, view.minimumHeight())
        app().processEvents()
        assert view.chart().plotArea().height() >= count * 24
        panel.close()


def test_mode_selection_persists_without_altering_result(tmp_path):
    app()
    settings = QSettings(str(tmp_path / 'chart.ini'), QSettings.Format.IniFormat)
    panel = ChartPanel('分区', modes=True, settings=settings, settings_key='trip')
    panel.set_mode('pie')
    panel.deleteLater()
    restored = ChartPanel('分区', modes=True, settings=settings, settings_key='trip')
    assert restored.mode == 'pie'
    restored.deleteLater()


def test_mode_picker_is_fluent_and_keeps_mode_data():
    app()
    panel = ChartPanel('分区', modes=True)
    assert isinstance(panel.mode_selector, FluentSegmentedControl)
    assert panel.mode_selector._subtle
    assert list(panel.mode_selector._buttons) == ['summary', 'bar', 'line', 'pie']
    panel.mode_selector.setCurrentKey('bar')
    assert panel.mode == 'bar'
    assert isinstance(panel.fullscreen_button, TransparentToolButton)
    panel.deleteLater()


def test_multi_company_charts_keep_separate_plots_at_compact_height():
    app()
    panel = ChartPanel('分制式客流')
    panel.set_result(result({('a', 'bus'): [bucket(1, 2)], ('b', 'bus'): [bucket(1, 3)]}))
    assert len(panel.chart_views) == 2
    assert all(view.minimumHeight() <= 200 for view in panel.chart_views)
    panel.deleteLater()


def test_narrow_panel_wraps_full_legend_labels_and_keeps_toggle():
    app()
    names = ('BlueCollar', 'WhiteCollar', 'BusinessPeople', 'Pensioner', 'Student', 'Tourist')
    panel = ChartPanel('分群体客流', modes=True)
    panel.set_result(result({('a', group): [bucket(1, 2)] for group in names}, 'transport-by-group'))
    panel.resize(450, 500)
    panel.show()
    app().processEvents()
    assert len(panel.legend_buttons) == 6
    assert panel.legend_layout.itemAtPosition(1, 0) is not None
    assert all('…' not in button.text() for button in panel.legend_buttons.values())
    assert not panel.chart_views[0].chart().legend().isVisible()
    panel.legend_buttons['BlueCollar'].click()
    assert not panel.chart_views[0].chart().series()[0].isVisible()
    panel.close()


def test_many_long_legend_labels_do_not_set_wide_minimum():
    app()
    groups = tuple(f'乘客分类名称很长{i} · 乘车人次' for i in range(9))
    panel = ChartPanel('客流', default_mode='bar')
    panel.set_result(result({('a', group): [bucket(1, i + 1)] for i, group in enumerate(groups)}))
    panel.resize(500, 600)
    panel.show()
    app().processEvents()
    assert panel.minimumSizeHint().width() <= 500
    assert panel.legend_host.minimumSizeHint().width() <= 500
    assert all('…' not in button.text() for button in panel.legend_buttons.values())
    panel.resize(320, 600)
    app().processEvents()
    assert panel.legend_host.minimumSizeHint().width() <= 320
    panel.close()


def test_line_and_time_bar_use_same_period_centres_for_months():
    app()
    dates = [datetime(2024, 1, 1), datetime(2024, 2, 1),
             datetime(2024, 3, 1), datetime(2024, 4, 1)]
    buckets = [Bucket(dates[i], dates[i + 1], Decimal(i + 2), True, False,
                      dates[i], None, None, 24) for i in range(3)]
    query = Query('cashflow', ('a',), '__total__', dates[0], dates[-1], 'month')
    data = Result(query, METRICS['cashflow'], {('a', '总计'): buckets}, {},
                  (dates[0], dates[-1]), None)
    positions = {}
    for mode in ('line', 'trend-bar'):
        panel = ChartPanel('现金流', default_mode=mode)
        panel.resize(700, 320)
        panel.set_result(data)
        panel.show()
        app().processEvents()
        chart = panel.chart_views[0].chart()
        area, series = chart.plotArea(), chart.series()[0]
        xs = ([point.x() for point in series.points()] if mode == 'line' else [0, 1, 2])
        positions[mode] = [(chart.mapToPosition(QPointF(x, 2), series).x() - area.left()) / area.width()
                           for x in xs]
        labels = [axis for axis in chart.axes(Qt.Orientation.Horizontal)
                  if isinstance(axis, QCategoryAxis)]
        assert len(labels) == 1
        assert labels[0].categoriesLabels() == ['01-01', '02-01', '03-01']
        panel.close()
    assert all(abs(a - b) < .002 for a, b in zip(positions['line'], positions['trend-bar']))


def test_hourly_time_axes_show_sparse_date_labels():
    app()
    start = datetime(2024, 1, 1)
    buckets = [Bucket(start + timedelta(hours=i), start + timedelta(hours=i + 1),
                      Decimal(i + 1), True, False, start + timedelta(hours=i),
                      None, None, 1) for i in range(168)]
    query = Query('cashflow', ('a',), '__total__', start, start + timedelta(days=7), 'hour')
    data = Result(query, METRICS['cashflow'], {('a', '总计'): buckets}, {},
                  (query.start, query.end), None)
    for mode in ('line', 'trend-bar'):
        panel = ChartPanel('现金流', default_mode=mode)
        panel.resize(700, 320)
        panel.set_result(data)
        panel.show()
        app().processEvents()
        axes = panel.chart_views[0].chart().axes(Qt.Orientation.Horizontal)
        label_axis = next(axis for axis in axes if isinstance(axis, QCategoryAxis))
        assert 4 <= len(label_axis.categoriesLabels()) <= 7
        assert all(' ' in text for text in label_axis.categoriesLabels())
        assert sum(axis.labelsVisible() for axis in axes) == 1
        panel.close()


def test_compact_time_charts_keep_dates_untruncated_and_expand_labels_when_wide():
    app()
    start = datetime(2024, 1, 1)
    buckets = [Bucket(start + timedelta(days=i), start + timedelta(days=i + 1),
                      Decimal(i + 1), True, False, start + timedelta(days=i),
                      None, None, 24) for i in range(7)]
    query = Query('linecount', ('a',), '__total__', start, start + timedelta(days=7), 'day')
    data = Result(query, METRICS['linecount'], {('a', '总计'): buckets}, {},
                  (query.start, query.end), None)
    for mode in ('line', 'trend-bar'):
        panel = ChartPanel('线路数', default_mode=mode)
        panel.resize(290, 300)
        panel.set_result(data)
        panel.show()
        app().processEvents()
        chart = panel.chart_views[0].chart()
        axis = next(axis for axis in chart.axes(Qt.Orientation.Horizontal)
                    if isinstance(axis, QCategoryAxis))
        assert 2 <= len(axis.categoriesLabels()) <= 3
        assert not axis.labelsTruncated()
        panel.resize(700, 300)
        app().processEvents()
        assert len(axis.categoriesLabels()) == 4
        assert not axis.labelsTruncated()
        panel.close()


def test_narrow_hourly_and_cross_year_axes_keep_one_complete_label():
    app()
    for start in (datetime(2024, 1, 1), datetime(2023, 12, 31, 22)):
        buckets = [Bucket(start + timedelta(hours=i), start + timedelta(hours=i + 1),
                          Decimal(i + 1), True, False, start + timedelta(hours=i),
                          None, None, 1) for i in range(8)]
        query = Query('linecount', ('a',), '__total__', start,
                      start + timedelta(hours=8), 'hour')
        data = Result(query, METRICS['linecount'], {('a', '总计'): buckets}, {},
                      (query.start, query.end), None)
        for mode in ('line', 'trend-bar'):
            panel = ChartPanel('线路数', default_mode=mode)
            panel.resize(224, 320)
            panel.set_result(data)
            panel.show()
            app().processEvents()
            chart = panel.chart_views[0].chart()
            axis = next(axis for axis in chart.axes(Qt.Orientation.Horizontal)
                        if isinstance(axis, QCategoryAxis))
            assert len(axis.categoriesLabels()) == 1
            assert not axis.labelsTruncated()
            panel.close()


def test_summary_uses_model_weighted_average():
    app()
    first, second = bucket(1, 10), bucket(2, 20)
    first.effective_hours, second.effective_hours = 1, 3
    panel = ChartPanel('平均运行车辆数', default_mode='summary')
    panel.set_result(result({('a', '总计'): [first, second]}, 'vehicles-running'))
    assert panel.summary_values['a'] == Decimal('17.5')
    panel.deleteLater()


def test_comparison_line_is_visible_and_axis_contains_both_windows():
    app()
    data = result({('a', '总计'): [bucket(1, 2), bucket(2, 3)]})
    data.comparison = {('a', '总计'): [bucket(1, 40), bucket(2, 50)]}
    data.comparison_window = (datetime(2023, 12, 30), datetime(2024, 1, 1))
    panel = ChartPanel('分制式客流')
    panel.set_result(data)
    assert len(panel.chart_views[0].chart().series()) == 2
    assert panel.axis_spec.upper * panel.axis_spec.scale >= 50
    panel.deleteLater()


def test_comparison_time_bars_show_two_sets():
    app()
    data = result({('a', '总计'): [bucket(1, 2), bucket(2, 3)]})
    data.comparison = {('a', '总计'): [bucket(1, 40), bucket(2, 50)]}
    panel = ChartPanel('分制式客流', default_mode='trend-bar')
    panel.set_result(data)
    assert len(panel.chart_views[0].chart().series()[0].barSets()) == 2
    panel.deleteLater()


def test_comparison_category_bars_share_full_axis():
    app()
    data = result({('a', 'bus'): [bucket(1, 2)]})
    data.comparison = {('a', 'bus'): [bucket(1, 50)]}
    panel = ChartPanel('分制式客流', default_mode='bar')
    panel.set_result(data)
    assert len(panel.chart_views[0].chart().series()[0].barSets()) == 2
    assert panel.axis_spec.upper * panel.axis_spec.scale >= 50
    panel.deleteLater()


def test_category_bar_axis_names_each_group_and_toggle_preserves_result():
    app()
    data = result({('a', 'bus'): [bucket(1, 2)], ('a', 'tram'): [bucket(1, 3)]})
    data.comparison = {('a', 'bus'): [bucket(1, 4)], ('a', 'tram'): [bucket(1, 5)]}
    panel = ChartPanel('分制式客流', default_mode='bar')
    panel.set_result(data)
    chart = panel.chart_views[0].chart()
    assert not panel.legend_buttons['bus'].icon().isNull()
    assert chart.axes(Qt.Orientation.Vertical)[0].categories() == ['公交', '有轨电车']
    assert not chart.legend().isVisible()
    assert panel.legend_buttons['bus'].isVisible() or not panel.isVisible()
    current, previous = chart.series()[0].barSets()
    assert [current.at(i) for i in range(current.count())] == [2, 3]
    assert [previous.at(i) for i in range(previous.count())] == [4, 5]
    panel.legend_buttons['bus'].click()
    assert current.at(0) == previous.at(0) == 0
    assert panel.result is data
    panel.legend_buttons['bus'].click()
    assert current.at(0) == 2 and previous.at(0) == 4
    panel.deleteLater()


def test_fluent_time_marks_include_real_zero_skip_missing_and_keep_original_hover_value(monkeypatch):
    app()
    data = result({('a', 'bus'): [bucket(1, 10), bucket(2, None),
                                  bucket(3, -3), bucket(4, 0)]}, 'cashflow')
    panel = ChartPanel('现金流', default_mode='trend-bar')
    panel.set_result(data)
    panel.resize(700, 320)
    panel.show()
    app().processEvents()
    view = panel.chart_views[0]
    view.grab()
    hits = [(region, item) for region, item in view._hit_regions
            if item['type'] == 'time-hit']
    assert [item['bucket'].value for _, item in hits] == [Decimal(10), Decimal(-3), Decimal(0)]
    assert all(region.width() <= 20 for region, _ in hits)
    assert view.chart().series()[0].barSets()[0].brush().color().alpha() == 0
    captured = []
    monkeypatch.setattr('stats_charts.QToolTip.showText',
                        lambda *args: captured.append(args[1]))
    negative = next(region for region, item in hits if item['bucket'].value < 0)
    QTest.mouseMove(view.viewport(), view.mapFromScene(negative.center()))
    app().processEvents()
    assert captured and '-3' in captured[-1]
    panel.close()


def test_fluent_horizontal_comparison_and_pie_hover_use_visible_marks(monkeypatch):
    app()
    data = result({('a', 'bus'): [bucket(1, 2)],
                   ('a', 'tram'): [bucket(1, 3)]})
    data.comparison = {('a', 'bus'): [bucket(1, 4)],
                       ('a', 'tram'): [bucket(1, 5)]}
    data.comparison_window = (datetime(2023, 12, 29), datetime(2024, 1, 1))
    panel = ChartPanel('客流', default_mode='bar')
    panel.set_result(data)
    panel.resize(700, 350)
    panel.show()
    app().processEvents()
    view = panel.chart_views[0]
    view.grab()
    assert len(view._hit_regions) == 4
    panel.legend_buttons['bus'].click()
    view.grab()
    assert len(view._hit_regions) == 2
    panel.legend_buttons['bus'].click()
    panel.set_mode('pie')
    app().processEvents()
    view = panel.chart_views[0]
    view.grab()
    visual = view.visuals[0]
    first = visual['slices'][0]
    assert first['percent'] == 40
    angle = radians(first['start_angle'] + first['span_angle'] / 2)
    radius = (first['inner_radius'] + first['outer_radius']) / 2
    point = QPointF(first['center'].x() + cos(angle) * radius,
                    first['center'].y() - sin(angle) * radius)
    captured = []
    monkeypatch.setattr('stats_charts.QToolTip.showText',
                        lambda *args: captured.append(args[1]))
    QTest.mouseMove(view.viewport(), view.mapFromScene(point))
    app().processEvents()
    assert captured and '40.0%' in captured[-1]
    panel.close()


def test_fluent_empty_state_distinguishes_missing_from_observed_zero():
    app()
    panel = ChartPanel('现金流', default_mode='trend-bar')
    panel.set_result(result({('a', 'bus'): [bucket(1, None), bucket(2, None)]},
                            'cashflow'))
    assert panel.chart_views[0].visuals[0]['type'] == 'empty'
    assert all(not axis.isVisible() for axis in panel.chart_views[0].chart().axes())
    panel.set_result(result({('a', 'bus'): [bucket(1, 0), bucket(2, 0)]},
                            'cashflow'))
    assert panel.chart_views[0].visuals[0]['type'] == 'time-bars'
    assert all(axis.isVisible() for axis in panel.chart_views[0].chart().axes())
    panel.deleteLater()


def test_line_mode_has_light_area_and_negative_hover_without_joining_missing(monkeypatch):
    app()
    data = result({('a', 'bus'): [bucket(1, 10), bucket(2, -5),
                                  bucket(3, None), bucket(4, 3)]}, 'cashflow')
    panel = ChartPanel('现金流验证', default_mode='line')
    panel.set_result(data)
    panel.resize(700, 320)
    panel.show()
    app().processEvents()
    view = panel.chart_views[0]
    view.grab()
    visuals = [visual for visual in view.visuals if visual['type'] == 'line']
    assert len(visuals) == 2
    assert all(visual['area'] for visual in visuals)
    assert panel.axis_spec.lower < 0 < panel.axis_spec.upper
    captured = []
    monkeypatch.setattr('stats_charts.QToolTip.showText',
                        lambda *args: captured.append(args[1]))
    negative = next(region for region, hit in view._hit_regions
                    if hit['type'] == 'time-hit' and hit['bucket'].value == -5)
    QTest.mouseMove(view.viewport(), view.mapFromScene(negative.center()))
    app().processEvents()
    assert captured and '-5' in captured[-1]
    panel.close()


def test_line_comparison_has_compact_period_key_without_duplicate_markers():
    app()
    data = result({('a', 'bus'): [bucket(1, 2)]})
    data.comparison = {('a', 'bus'): [bucket(1, 3)]}
    panel = ChartPanel('分制式客流')
    panel.set_result(data)
    panel.show()
    app().processEvents()
    assert panel.period_label.isVisible()
    assert '本期' in panel.period_label.text() and '对比' in panel.period_label.text()
    assert not panel.chart_views[0].chart().legend().isVisible()
    panel.deleteLater()


def test_260px_bar_uses_spaced_integer_ticks_and_wrapped_company_name():
    app()
    long_name = '滨海市公共交通运营公司第一分公司 [p1]'
    panel = ChartPanel('分制式站点数', default_mode='bar')
    panel.set_result(result({('a', 'bus'): [bucket(1, 33)],
                             ('a', 'tram'): [bucket(1, 66)],
                             ('a', 'metro'): [bucket(1, 99)]}, 'stopcount'), {'a': long_name})
    panel.resize(260, 410)
    panel.show()
    app().processEvents()
    axis = panel.chart_views[0].chart().axes(Qt.Orientation.Horizontal)[0]
    assert (axis.max() - axis.min()) / axis.tickInterval() + 1 <= 4
    assert panel.company_labels[0].text() == long_name
    assert panel.company_labels[0].wordWrap()
    assert panel.chart_views[0].chart().title() == ''
    panel.close()


def test_narrow_bar_never_truncates_long_transport_category_labels():
    app()
    groups = ('bus', 'tram', 'trolley', 'waterbus')
    panel = ChartPanel('分制式站点数', default_mode='bar')
    panel.set_result(result({('a', group): [bucket(1, 30 + index * 10)]
                             for index, group in enumerate(groups)}, 'stopcount'),
                     {'a': '滨海市公共交通运营公司 [p1]'})
    panel.resize(250, 350)
    panel.show()
    app().processEvents()
    axis = panel.chart_views[0].chart().axes(Qt.Orientation.Vertical)[0]
    assert axis.categories() == ['公交', '有轨电车', '无轨电车', '水上巴士']
    assert not axis.truncateLabels()
    panel.close()


def test_signed_axis_survives_tiny_transient_plot_and_repeated_resize():
    app()
    panel = ChartPanel('现金流', default_mode='bar')
    panel.set_result(result({('a', 'net-cash'): [bucket(1, -200)],
                             ('a', 'business-value'): [bucket(1, 300)]}, 'cashflow'))
    panel.resize(260, 350)
    panel.show()
    app().processEvents()
    chart = panel.chart_views[0].chart()
    chart.setPlotArea(QRectF(0, 0, 70, 100))
    panel._adapt_axes()
    axis = chart.axes(Qt.Orientation.Horizontal)[0]
    assert axis.min() <= -200 <= 0 <= 300 <= axis.max()
    for width in (260, 360, 260, 360):
        panel.resize(width, 350)
        app().processEvents()
        assert axis.min() <= -200 <= 0 <= 300 <= axis.max()
        assert axis.max() - axis.min() < 10000
    panel.close()


def test_large_axis_step_can_grow_past_fixed_power_range():
    app()
    panel = ChartPanel('现金流', default_mode='bar')
    panel.set_result(result({('a', 'net-cash'): [bucket(1, 10**24)]}, 'cashflow'))
    panel.resize(260, 320)
    panel.show()
    app().processEvents()
    chart = panel.chart_views[0].chart()
    chart.setPlotArea(QRectF(0, 0, 70, 100))
    panel._adapt_axes()
    axis = chart.axes(Qt.Orientation.Horizontal)[0]
    assert panel.axis_spec.upper * panel.axis_spec.scale >= 10**24
    panel.close()


def test_total_trend_line_compares_companies_in_one_shared_axis():
    app()
    data = result({('a', '总计'): [bucket(1, 2), bucket(2, 3)],
                   ('b', '总计'): [bucket(1, 40), bucket(2, 50)]}, 'linecount')
    data.comparison = {('a', '总计'): [bucket(1, 4), bucket(2, 5)],
                       ('b', '总计'): [bucket(1, 60), bucket(2, 70)]}
    panel = ChartPanel('线路数')
    panel.set_result(data, {'a': '甲公司', 'b': '乙公司'})
    assert len(panel.chart_views) == 1
    series = panel.chart_views[0].chart().series()
    assert len(series) == 4
    assert [point.y() for point in series[0].points()] == [2, 3]
    assert [point.y() for point in series[2].points()] == [40, 50]
    assert panel.axis_spec.upper * panel.axis_spec.scale >= 70
    assert {button.text() for button in panel.legend_buttons.values()} == {'甲公司', '乙公司'}
    panel.deleteLater()


def test_total_time_bars_group_companies_without_summing_values():
    app()
    data = result({('a', '总计'): [bucket(1, 2), bucket(2, 3)],
                   ('b', '总计'): [bucket(1, 40), bucket(2, 50)]}, 'cashflow')
    data.comparison = {('a', '总计'): [bucket(1, 4), bucket(2, 5)],
                       ('b', '总计'): [bucket(1, 60), bucket(2, 70)]}
    panel = ChartPanel('现金流', default_mode='trend-bar')
    panel.set_result(data, {'a': '甲公司', 'b': '乙公司'})
    assert len(panel.chart_views) == 1
    bars = panel.chart_views[0].chart().series()[0].barSets()
    assert len(bars) == 4
    assert [[bar.at(i) for i in range(bar.count())] for bar in bars] == [
        [2, 3, 0], [4, 5, 0], [40, 50, 0], [60, 70, 0]]
    assert {button.text() for button in panel.legend_buttons.values()} == {'甲公司', '乙公司'}
    panel.deleteLater()


def test_tooltips_use_approved_metric_label_not_model_explanation(monkeypatch):
    app()
    panel = ChartPanel('分制式站点数', default_mode='bar')
    data = result({('a', 'tram'): [bucket(1, 3)]}, 'stopcount')
    panel.set_result(data, {'a': '甲公司'})
    captured = []
    monkeypatch.setattr('stats_charts.QToolTip.showText', lambda *args: captured.append(args[1]))
    panel._tooltip('a', 'tram', data.series[('a', 'tram')][0])
    panel._total_tooltip('a', 'tram', Decimal(3), data.current_window)
    assert all('站点数' in item for item in captured)
    assert all('游戏历史口径' not in item for item in captured)
    assert all('本期' not in item for item in captured)
    panel.deleteLater()


def test_line_time_axis_uses_full_query_window_even_with_missing_buckets():
    app()
    late = result({('a', '总计'): [bucket(1, None), bucket(2, None), bucket(3, 5)]}, 'linecount')
    early = result({('a', '总计'): [bucket(1, 2), bucket(2, None), bucket(3, None)]}, 'linecount')
    panels = [ChartPanel('线路数') for _ in range(2)]
    for panel, data in zip(panels, (late, early)):
        panel.set_result(data)
    axes = [panel.chart_views[0].chart().axes(Qt.Orientation.Horizontal)[0] for panel in panels]
    assert axes[0].min() == axes[1].min() == -.5
    assert axes[0].max() == axes[1].max() == 2.5
    assert axes[0].categoriesLabels() == axes[1].categoriesLabels() == ['01-01', '01-02', '01-03']
    for panel in panels:
        panel.deleteLater()


def test_set_axis_spec_preserves_scale_unit_and_can_reset():
    app()
    panel = ChartPanel('分制式客流')
    panel.set_result(result({('a', 'bus'): [bucket(1, 12000)]}))
    panel.set_axis_spec(AxisSpec(0, 20, 5, 1000, '千'))
    axis = panel.chart_views[0].chart().axes(Qt.Orientation.Vertical)[0]
    assert axis.max() == 20 and axis.tickInterval() == 5
    assert not axis.truncateLabels()
    assert axis.titleText() == '千人次'
    assert panel.chart_views[0].chart().series()[0].points()[0].y() == 12
    panel.set_axis_spec(None)
    assert panel.axis_spec.scale != 1000
    panel.deleteLater()


def test_period_company_value_panels_keep_one_shared_axis_after_layout():
    app()
    host = QWidget()
    layout = QHBoxLayout(host)
    panels = [ChartPanel('公司价值') for _ in range(2)]
    spec = nice_axis([Decimal(100), Decimal(460)])
    for company, value, panel in zip(('a', 'b'), (100, 460), panels):
        panel.set_result(result({(company, '总计'): [bucket(1, value)]}, 'company-value'))
        panel.set_axis_spec(spec)
        layout.addWidget(panel)
    host.resize(900, 360)
    host.show()
    app().processEvents()
    for panel in panels:
        axis = panel.chart_views[0].chart().axes(Qt.Orientation.Vertical)[0]
        assert (axis.min(), axis.max(), axis.tickInterval()) == (
            spec.lower, spec.upper, spec.step)
        assert all(visual['axis'] == spec for visual in panel.chart_views[0].visuals)
    host.close()


def test_hidden_pie_category_hides_label_and_tooltip_without_changing_weight(monkeypatch):
    app()
    panel = ChartPanel('分制式客流', default_mode='pie')
    panel.set_result(result({('a', 'bus'): [bucket(1, 3)], ('a', 'tram'): [bucket(1, 1)]}))
    pie = panel.chart_views[0].chart().series()[0]
    captured = []
    monkeypatch.setattr('stats_charts.QToolTip.showText', lambda *args: captured.append(args[1]))
    panel.legend_buttons['bus'].click()
    assert not pie.slices()[0].isLabelVisible()
    pie.slices()[0].hovered.emit(True)
    assert captured == []
    assert [slice_.value() for slice_ in pie.slices()] == [3, 1]
    panel.deleteLater()


def test_time_bar_hover_uses_original_comparison_date(monkeypatch):
    app()
    data = result({('a', 'bus'): [bucket(1, 2)]})
    previous = bucket(1, 5)
    previous.start = datetime(2023, 12, 25)
    data.comparison = {('a', 'bus'): [previous]}
    panel = ChartPanel('分制式客流', default_mode='trend-bar')
    panel.set_result(data, {'a': '甲'})
    captured = []
    monkeypatch.setattr('stats_charts.QToolTip.showText', lambda *args: captured.append(args[1]))
    panel.chart_views[0].chart().series()[0].barSets()[1].hovered.emit(True, 0)
    assert '2023-12-25' in captured[-1]
    assert '5' in captured[-1]
    panel.deleteLater()


def test_legend_click_hides_all_segments_without_changing_totals():
    app()
    panel = ChartPanel('分制式客流', modes=True)
    data = result({('a', 'bus'): [bucket(1, 2), bucket(2, None), bucket(3, 4)]})
    panel.set_result(data)
    series = panel.chart_views[0].chart().series()
    panel.chart_views[0].chart().legend().markers(series[0])[0].clicked.emit()
    assert all(not item.isVisible() for item in series)
    assert panel.result is data
    panel.set_mode('summary')
    assert panel.summary_values['a'] == Decimal('6')
    panel.deleteLater()


def test_pie_legend_keeps_slice_values_and_category_total():
    app()
    panel = ChartPanel('分制式客流', default_mode='pie')
    panel.set_result(result({('a', 'bus'): [bucket(1, 2)], ('a', 'tram'): [bucket(1, 3)]}))
    chart = panel.chart_views[0].chart()
    pie = chart.series()[0]
    total = sum(piece.value() for piece in pie.slices())
    chart.legend().markers(pie)[0].clicked.emit()
    assert sum(piece.value() for piece in pie.slices()) == total == 5
    assert len(pie.slices()) == 2
    assert pie.slices()[0].brush().color().alpha() == 0
    panel.deleteLater()


def test_chart_uses_available_chinese_font_for_title_legend_and_axes():
    app()
    panel = ChartPanel('分制式客流')
    panel.set_result(result({('a', 'bus'): [bucket(1, 2)]}))
    from stats_charts import _FONT_ID
    assert _FONT_ID >= 0
    chart = panel.chart_views[0].chart()
    assert chart.titleFont().family() == 'Microsoft YaHei UI'
    assert chart.legend().font().family() == 'Microsoft YaHei UI'
    assert all(axis.labelsFont().family() == 'Microsoft YaHei UI' for axis in chart.axes())
    from stats_typography import emphasis_families
    assert tuple(panel.title_label.font().families()) == emphasis_families(panel.title_label.font().pixelSize())
    assert all(isinstance(button, TransparentTogglePushButton) and
               button.font().family() == 'Microsoft YaHei UI'
               for button in panel.legend_buttons.values())
    assert tuple(panel.summary_label.font().families()) == emphasis_families(panel.summary_label.font().pixelSize())
    assert '"Microsoft YaHei UI"' in panel.summary_label.styleSheet()
    mode_panel = ChartPanel('模式', modes=True)
    assert all(button.font().family() == 'Microsoft YaHei UI'
               for button in mode_panel.mode_selector._buttons.values())
    mode_panel.deleteLater()
    panel.deleteLater()


def test_longer_comparison_window_keeps_all_buckets_and_aligned_positions():
    app()
    data = result({('a', 'bus'): [bucket(1, 2), bucket(2, 3)]})
    data.comparison = {('a', 'bus'): [bucket(1, 10), bucket(2, 20), bucket(3, 30), bucket(4, 40)]}
    panel = ChartPanel('分制式客流')
    panel.set_result(data)
    series = panel.chart_views[0].chart().series()
    assert len(series[1].points()) == 4
    assert series[1].points()[0].x() == series[0].points()[0].x()
    assert series[1].points()[-1].x() > series[0].points()[-1].x()
    panel.set_mode('trend-bar')
    chart = panel.chart_views[0].chart()
    assert len(chart.axes(Qt.Orientation.Horizontal)[0].categories()) == 4
    assert chart.series()[0].barSets()[1].count() == 4
    panel.deleteLater()


def test_common_passenger_categories_have_distinct_colors():
    for groups in (('BlueCollar', 'WhiteCollar', 'BusinessPeople', 'Pensioner', 'Student', 'Tourist'),
                   ('bus', 'tram', 'trolley', 'metro', 'waterbus')):
        assert len({_category_color(group).name() for group in groups}) == len(groups)


def test_company_category_palette_is_opt_in_and_keeps_hover_and_legend_in_sync():
    app()
    data = result({('a', 'bus'): [bucket(1, 2)], ('a', 'tram'): [bucket(1, 3)]})
    city = ChartPanel('城市分类')
    city.set_result(data)
    assert city._category_color('bus') == _category_color('bus')
    company = ChartPanel('公司分类')
    company.set_category_palette(tokens.DATA_CATEGORY_COLORS)
    company.set_result(data)
    for group in ('bus', 'tram'):
        color = QColor(tokens.DATA_CATEGORY_COLORS[('bus', 'tram').index(group)])
        assert company._category_color(group) == color
        assert company._legend_color(group) == color
        assert all(target['color'] == color for target in company._hover_targets
                   if target['group'] == group)
        assert all(visual['color'] == color for view in company.chart_views
                   for visual in view.visuals
                   if visual.get('type') == 'line' and visual.get('group') == group)
    company._open_fullscreen()
    clone = next(child for child in company._fullscreen_dialog.findChildren(ChartPanel)
                 if child is not company)
    assert clone._category_color('bus') == company._category_color('bus')
    company._fullscreen_dialog.close()
    city.deleteLater()
    company.deleteLater()


def test_mode_labels_have_consistent_defaults_and_overrides_keep_mode_keys():
    app()
    city = ChartPanel('城市图', allowed_modes=('line', 'bar', 'pie'))
    company = ChartPanel('公司图', allowed_modes=('line', 'bar', 'pie'))
    assert city.mode_selector._buttons['line'].text() == '趋势'
    company.set_mode_labels({'line': '趋势', 'bar': '分布', 'pie': '比例'})
    assert {key: button.text() for key, button in company.mode_selector._buttons.items()} == {
        'line': '趋势', 'bar': '分布', 'pie': '比例'}
    company.set_mode('bar')
    assert company.mode_selector.currentKey() == 'bar'
    assert company.mode == 'bar'
    company.set_mode_labels(None)
    assert company.mode_selector._buttons['bar'].text() == city.mode_selector._buttons['bar'].text()
    city.deleteLater()
    company.deleteLater()


def test_company_chart_compact_height_retains_plot_at_two_company_card_size():
    app()
    panel = ChartPanel('公司趋势', allowed_modes=('line',))
    panel.set_compact_height(200)
    panel.set_company_palette({'a': tokens.DATA_COMPANY_COLORS[0],
                               'b': tokens.DATA_COMPANY_COLORS[1]})
    panel.set_result(result({('a', '总计'): [bucket(1, 10), bucket(2, 12)],
                             ('b', '总计'): [bucket(1, 20), bucket(2, 22)]}))
    panel.resize(390, 200)
    panel.show()
    app().processEvents()
    assert panel.height() == 200
    assert panel.chart_views[0].minimumHeight() <= 106
    assert panel.chart_views[0].chart().plotArea().height() >= 50
    panel.close()


def test_company_chart_compact_height_at_narrow_company_column():
    app()
    panel = ChartPanel('公司价值', allowed_modes=('line',))
    panel.set_compact_height(200)
    panel.set_result(result({('b', '总计'): [bucket(1, 20), bucket(2, 22)]}))
    panel.resize(263, 200)
    panel.show()
    app().processEvents()
    assert panel.chart_views[0].chart().plotArea().width() >= 160
    assert panel.chart_views[0].chart().plotArea().height() >= 50
    panel.close()


def test_company_tooltip_dot_uses_the_line_color(monkeypatch):
    app()
    panel = ChartPanel('公司价值', allowed_modes=('line',))
    panel.set_company_palette({'b': tokens.DATA_COMPANY_COLORS[1]})
    data = result({('b', '总计'): [bucket(1, 20)]})
    panel.set_result(data)
    captured = []
    monkeypatch.setattr('stats_charts.QToolTip.showText',
                        lambda *args: captured.append(args[1]))
    panel._tooltip('b', '总计', data.series[('b', '总计')][0])
    assert captured and 'color:#00a67a' in captured[0] and '●' in captured[0]
    panel.deleteLater()


def test_vertical_and_horizontal_bars_use_subtle_identity_preserving_gradient():
    color = QColor(tokens.DATA_CATEGORY_COLORS[0])
    bounds = QRectF(10, 20, 16, 80)
    for horizontal in (False, True):
        brush = _bar_brush(color, bounds, horizontal)
        gradient = brush.gradient()
        leading, trailing = [stop[1] for stop in gradient.stops()]
        assert trailing.name() == color.name()
        assert leading.alphaF() == trailing.alphaF() == 1
        assert abs(leading.hsvHueF() - trailing.hsvHueF()) < .01
        assert leading.valueF() < trailing.valueF()
        assert (gradient.start().y() == gradient.finalStop().y()) == horizontal
        comparison_brush = _bar_brush(_period_color(color, True), bounds, horizontal)
        compared = comparison_brush.gradient()
        assert compared.stops()[-1][1].alphaF() < trailing.alphaF()


def test_pie_shows_company_local_percentages():
    app()
    panel = ChartPanel('分制式客流', default_mode='pie')
    panel.set_result(result({('a', 'bus'): [bucket(1, 2)], ('a', 'tram'): [bucket(1, 3)],
                             ('b', 'bus'): [bucket(1, 1)], ('b', 'tram'): [bucket(1, 3)]}))
    first, second = (view.chart().series()[0] for view in panel.chart_views)
    assert [slice_.label() for slice_ in first.slices()] == ['公交 40.0%', '有轨电车 60.0%']
    assert [slice_.label() for slice_ in second.slices()] == ['公交 25.0%', '有轨电车 75.0%']
    panel.deleteLater()
