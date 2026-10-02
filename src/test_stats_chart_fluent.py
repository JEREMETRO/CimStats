"""Public Fluent chart behavior, using real QtCharts series offscreen."""
import os
import sys
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

from PySide6.QtCore import QPointF, Qt
from PySide6.QtCharts import QAreaSeries, QBarSeries, QLineSeries
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QAbstractButton

from statistics_model import Bucket, METRICS, Query, Result
from stats_charts import AxisSpec, ChartPanel
import stats_tokens as tokens


def app():
    return QApplication.instance() or QApplication([])


def test_chart_header_has_no_metric_picker_and_keeps_fullscreen_action():
    app()
    panel = ChartPanel('公司价值')
    assert not hasattr(panel, 'metric_menu_button')
    assert not any(button.toolTip() == '选择图表指标' for button in panel.findChildren(QAbstractButton))
    assert panel.fullscreen_button.accessibleName() == '全屏查看图表'
    panel.deleteLater()

def test_narrow_combined_card_moves_legend_below_title():
    app()
    panel = ChartPanel('公司价值')
    panel.set_result(result(current=(2, 3, 4), companies=('a', 'b')),
                     {'a': '甲公司', 'b': '乙公司'})
    panel.resize(400, 470)
    panel.show()
    app().processEvents()
    assert not panel._legend_in_header
    assert panel._layout.indexOf(panel.legend_host) == 1
    assert panel.title_label.width() > 150
    panel.close()


def result(metric='company-value', current=(2, None, 4), comparison=(), companies=('a',)):
    start = datetime(2024, 1, 1)

    def buckets(values, first):
        return [Bucket(first + timedelta(days=i), first + timedelta(days=i + 1),
                       None if value is None else Decimal(value), value is not None,
                       False, first + timedelta(days=i), None, None, 24)
                for i, value in enumerate(values)]

    query = Query(metric, companies, '__total__', start, start + timedelta(days=3), 'day',
                  (start - timedelta(days=3), start) if comparison else None)
    series = {(company, '总计'): buckets(current, start) for company in companies}
    earlier = {(company, '总计'): buckets(comparison, start - timedelta(days=3))
               for company in companies} if comparison else {}
    return Result(query, METRICS[metric], series, earlier,
                  (query.start, query.end), query.comparison)


def test_company_palette_drives_line_bars_and_legend():
    app()
    data = result(current=(2, 3, 4), companies=('a', 'b'))
    panel = ChartPanel('公司价值')
    panel.set_company_palette({'a': tokens.COMPANY_COLORS[0],
                               'b': tokens.COMPANY_COLORS[1]})
    panel.set_result(data, {'a': '甲', 'b': '乙'})
    colors = [series.pen().color().name() for series in panel.chart_views[0].chart().series()]
    assert colors == [tokens.COMPANY_COLORS[0].lower(), tokens.COMPANY_COLORS[1].lower()]
    assert panel.legend_buttons['b'].icon().pixmap(12, 12).toImage().pixelColor(6, 6).name() == tokens.COMPANY_COLORS[1].lower()
    panel.set_mode('trend-bar')
    bars = panel.chart_views[0].chart().series()[0].barSets()
    assert all(bar.brush().color().alpha() == 0 for bar in bars)
    assert [item['color'].name() for item in panel.chart_views[0].visuals[0]['sets']] == colors
    panel.deleteLater()


def test_area_retains_missing_gap_and_translucent_company_fill():
    app()
    panel = ChartPanel('公司价值', default_mode='area')
    panel.set_company_palette({'a': '#1677FF'})
    panel.set_result(result())
    areas = [s for s in panel.chart_views[0].chart().series() if isinstance(s, QAreaSeries)]
    assert len(areas) == 2
    assert [len(s.upperSeries().points()) for s in areas] == [1, 1]
    assert areas[0].brush().color().alphaF() < .2
    assert panel.axis_spec.lower <= 0
    panel.deleteLater()


def test_hover_offset_broadcasts_real_position_and_programmatic_link_does_not_echo():
    app()
    panel = ChartPanel('公司价值')
    panel.set_result(result(current=(2, 3, 4)))
    spy = QSignalSpy(panel.hover_offset_changed)
    series = next(s for s in panel.chart_views[0].chart().series() if isinstance(s, QLineSeries))
    series.hovered.emit(QPointF(1, 3), True)
    assert spy.count() == 1
    assert spy.at(0)[0] == 86400.0
    panel.set_hover_offset(86400.0)
    assert spy.count() == 1
    assert panel.hovered_bucket is panel.result.series[('a', '总计')][1]
    panel.set_hover_offset(None)
    assert panel.hovered_bucket is None
    assert spy.count() == 1
    panel.deleteLater()


def test_comparison_hover_keeps_original_date_and_period_text(monkeypatch):
    app()
    panel = ChartPanel('公司价值')
    panel.set_result(result(current=(2, 3, 4), comparison=(5, 6, 7)), {'a': '甲'})
    captured = []
    monkeypatch.setattr('stats_charts.QToolTip.showText', lambda *args: captured.append(args[1]))
    series = panel.chart_views[0].chart().series()[1]
    series.hovered.emit(QPointF(0, 5), True)
    assert '对比' in captured[-1]
    assert '2023-12-29' in captured[-1]
    assert '公司价值' in captured[-1] and '货币' in captured[-1]
    panel.deleteLater()


def test_time_bar_hover_links_by_relative_slot_without_mutating_missing_values():
    app()
    panel = ChartPanel('现金流', default_mode='trend-bar')
    data = result(metric='cashflow', current=(2, None, 4), comparison=(5, 6, 7, 8))
    panel.set_result(data)
    spy = QSignalSpy(panel.hover_offset_changed)
    chart = panel.chart_views[0].chart()
    bars = chart.series()[0].barSets()
    bars[1].hovered.emit(True, 3)
    assert spy.count() == 1 and spy.at(0)[0] == 3 * 86400.0
    assert panel.hovered_bucket is data.comparison[('a', '总计')][3]
    bars[0].hovered.emit(True, 1)
    assert spy.count() == 1  # Missing is not an observed zero.
    assert data.series[('a', '总计')][1].value is None
    panel.set_hover_offset(None)
    assert spy.count() == 1
    panel.deleteLater()


def test_local_comparison_hover_highlights_the_compared_bucket():
    app()
    panel = ChartPanel('现金流', default_mode='trend-bar')
    data = result(metric='cashflow', current=(2, 3, 4), comparison=(5, 6, 7))
    panel.set_result(data)
    comparison_set = panel.chart_views[0].chart().series()[0].barSets()[1]
    comparison_set.hovered.emit(True, 1)
    assert panel.hovered_bucket is data.comparison[('a', '总计')][1]
    panel.deleteLater()


def test_area_can_rebuild_and_switch_modes_without_dangling_qt_series():
    app()
    panel = ChartPanel('公司价值', default_mode='area')
    data = result(comparison=(5, 6, 7))
    for _ in range(3):
        panel.set_result(data)
        assert len(panel.chart_views[0].chart().series()) == 3
        panel.set_mode('line')
        panel.set_mode('area')
        app().processEvents()
    assert len(panel.chart_views[0].chart().series()) == 3
    panel.close()


def test_area_can_be_initial_mode_with_segmented_control():
    app()
    panel = ChartPanel('公司价值', modes=True, default_mode='area')
    panel.set_result(result())
    assert panel.mode == 'area'
    assert panel.mode_selector.currentKey() == 'area'
    assert all(isinstance(series, QAreaSeries)
               for series in panel.chart_views[0].chart().series())
    panel.deleteLater()


def test_mode_options_limit_visible_segments_and_dynamic_metric_changes():
    app()
    panel = ChartPanel('公司价值', modes=True, default_mode='area')
    panel.set_mode_options(('line', 'area'))
    assert panel.mode == 'area'
    assert list(panel.mode_selector._buttons) == ['line', 'area']
    with pytest.raises(ValueError):
        panel.set_mode('pie')
    with pytest.raises(ValueError):
        panel.set_mode_options(())
    assert panel.mode == 'area'
    panel.set_mode_options(('trend-bar',))
    assert panel.mode == 'trend-bar'
    assert panel.mode_selector is None
    with pytest.raises(ValueError):
        panel.set_mode('line')
    panel.set_mode_options(('line', 'area'))
    assert panel.mode == 'line'
    assert list(panel.mode_selector._buttons) == ['line', 'area']
    panel.deleteLater()


def test_mode_options_apply_to_fullscreen_copy():
    app()
    panel = ChartPanel('公司价值', allowed_modes=('line', 'area'), default_mode='area')
    panel.set_result(result(current=(2, 3, 4), companies=('a', 'b')))
    panel.legend_buttons['b'].click()
    panel.fullscreen_button.click()
    clone = panel._fullscreen_dialog.findChild(ChartPanel)
    assert clone.mode == 'area'
    assert list(clone.mode_selector._buttons) == ['line', 'area']
    assert 'b' in clone._hidden_groups
    panel._fullscreen_dialog.close()
    panel.deleteLater()


def test_compact_company_card_keeps_readable_plot_and_inline_mode_on_wide_card():
    app()
    panel = ChartPanel('公司价值', allowed_modes=('line', 'area'))
    panel.set_result(result(current=(2, 3, 4)))
    panel.set_compact_layout(True)
    panel.resize(700, 255)
    panel.show()
    app().processEvents()
    assert panel._mode_in_header
    assert panel.mode_selector.isVisible()
    assert panel.chart_views[0].minimumHeight() <= 195
    assert panel.chart_views[0].chart().plotArea().height() >= 145
    assert panel.minimumSizeHint().height() <= 255
    assert panel.sizeHint().height() == 247
    panel.fullscreen_button.click()
    clone = panel._fullscreen_dialog.findChild(ChartPanel)
    assert clone.chart_views[0].minimumHeight() >= 210
    panel._fullscreen_dialog.close()
    panel.set_compact_layout(False)
    assert panel.chart_views[0].minimumHeight() >= 210
    assert not panel._mode_in_header
    panel.close()


def test_compact_cashflow_and_narrow_selector_keep_axes_visible():
    app()
    cash = ChartPanel('现金流', default_mode='trend-bar', allowed_modes=('trend-bar',))
    cash.set_result(result(metric='cashflow', current=(2, 3, 4)))
    cash.set_compact_layout(True)
    cash.resize(700, 247)
    cash.show()
    app().processEvents()
    assert cash.minimumSizeHint().height() <= 247
    assert cash.chart_views[0].chart().plotArea().height() >= 145
    cash.close()

    narrow = ChartPanel('公司价值', allowed_modes=('line', 'area'))
    narrow.set_result(result(current=(2, 3, 4)))
    narrow.set_compact_layout(True)
    narrow.resize(350, 280)
    narrow.show()
    app().processEvents()
    assert not narrow._mode_in_header
    assert narrow.mode_selector.isVisible()
    assert narrow.chart_views[0].chart().plotArea().height() >= 145
    narrow.close()


def test_area_hover_uses_rendered_slot_and_comparison_keeps_true_date(monkeypatch):
    app()
    panel = ChartPanel('公司价值', default_mode='area')
    panel.set_result(result(comparison=(5, 6, 7)))
    spy = QSignalSpy(panel.hover_offset_changed)
    captured = []
    monkeypatch.setattr('stats_charts.QToolTip.showText', lambda *args: captured.append(args[1]))
    comparison_area = panel.chart_views[0].chart().series()[-1]
    comparison_area.hovered.emit(QPointF(2, 7), True)
    assert spy.at(0)[0] == 2 * 86400.0
    assert '对比' in captured[-1] and '2023-12-31' in captured[-1]
    comparison_area.hovered.emit(QPointF(2, 7), False)
    assert spy.at(1)[0] is None
    panel.deleteLater()


def test_fullscreen_opens_independent_chart_with_same_result_and_axis():
    app()
    panel = ChartPanel('公司价值')
    data = result(current=(2, 3, 4))
    panel.set_result(data)
    panel.set_axis_spec(AxisSpec(0, 10, 2))
    panel.fullscreen_button.click()
    dialog = panel._fullscreen_dialog
    clone = dialog.findChild(ChartPanel)
    assert dialog.isVisible() and clone is not panel
    assert clone.result is data and clone.axis_spec == panel.axis_spec
    assert len(clone.chart_views) == 1
    dialog.close()
    panel.deleteLater()
