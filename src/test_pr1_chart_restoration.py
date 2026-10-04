"""Requested fullscreen content and PR layout regressions."""
from datetime import datetime
from decimal import Decimal

import pytest
from PySide6.QtCore import QPoint, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QTableWidget

from test_chart_canvas import canvas, line
from chart_canvas import ChartData
from test_stats_charts import bucket, panel, result
from test_network_charts import app, descriptor, endpoint_result, make_result, snapshot
from network_charts import NetworkChartPanel
import stats_tokens as tokens


class PaintRecorder:
    def __init__(self, painter, drawn):
        self.painter = painter
        self.drawn = drawn

    def __getattr__(self, name):
        return getattr(self.painter, name)

    def drawText(self, *args):
        self.drawn.append((str(args[-1]), self.painter.font()))
        return self.painter.drawText(*args)


def fullscreen(mode='trend-bar'):
    widget = panel('客流', modes=True, default_mode=mode)
    widget.set_result(result({('a', 'bus'): [bucket(1, 10)],
                             ('a', 'tram'): [bucket(1, 15)]}), {'a': '甲公司'})
    widget.resize(1440, 960)
    widget.show()
    clone = widget._open_fullscreen()
    dialog = widget._fullscreen_dialog
    QTest.qWait(50)
    return widget, clone, dialog


@pytest.mark.parametrize('mode', ['line', 'trend-bar', 'bar', 'pie'])
def test_fullscreen_restores_company_summary_cards(mode):
    widget, clone, dialog = fullscreen(mode)
    try:
        assert hasattr(clone, 'detail_summary')
        assert clone.detail_summary.isVisible()
        cards = clone.detail_summary.cards
        assert len(cards) == 1 and cards[0]['name'] == '甲公司'
        assert cards[0]['values'] == [('bus', Decimal(10)), ('tram', Decimal(15))]
    finally:
        dialog.close()
        widget.close()


def test_fullscreen_has_no_values_table_or_instruction_banner():
    widget, clone, dialog = fullscreen('line')
    try:
        assert not clone.findChildren(QTableWidget)
        assert not any('滚轮缩放' in label.text() for label in clone.findChildren(QLabel))
    finally:
        dialog.close()
        widget.close()


def test_detailed_stacks_paint_each_segment_and_column_total(monkeypatch):
    widget = canvas(ChartData('bar', ['01-01'], [line([10], 'a', stack='s'),
                                               line([15], 'b', stack='s')]),
                    width=1440, height=600, detailed=True)
    captured = []
    original = widget._paint_value_labels

    def observe(painter, labels):
        return original(PaintRecorder(painter, captured), labels)

    monkeypatch.setattr(widget, '_paint_value_labels', observe)
    widget.grab()
    assert {'10', '15', '25'} <= {text for text, _ in captured}
    assert next(font for text, font in captured if text == '25').pixelSize() == 15
    assert next(font for text, font in captured if text == '25').bold()
    assert next(font for text, font in captured if text == '10').pixelSize() == 13
    widget.close()


@pytest.mark.parametrize('detailed', [False, True])
@pytest.mark.parametrize('count, groups', [(3, 1), (3, 2), (31, 4)])
def test_bars_restore_original_spacing_width_and_axis_font(detailed, count, groups):
    widget = canvas(ChartData('bar', [str(i) for i in range(count)],
                              [line([10] * count, str(i)) for i in range(groups)]),
                    width=1300, height=600, detailed=detailed)
    _, width, gap, band = widget._stack_layout()
    slot = widget.plot_rect().width() / count
    expected_gap = min(24 if detailed else 4, max(.8, slot * .075))
    expected_width = min(48 if detailed else 20,
                         max(.6 if detailed else 2,
                             (slot * (.78 if detailed else .72) - expected_gap * (groups - 1)) / groups))
    assert gap == pytest.approx(expected_gap)
    assert width == pytest.approx(expected_width)
    assert band == pytest.approx(groups * width + (groups - 1) * gap)
    assert widget._font.family() == tokens.FONT_FAMILY
    assert widget._font.pixelSize() == 12
    widget.close()


def test_small_stack_segment_does_not_displace_total(monkeypatch):
    widget = canvas(ChartData('bar', ['01-01'], [line([1000], 'a', stack='s'),
                                               line([1], 'b', stack='s')]),
                    width=960, height=300, detailed=True)
    captured = []
    original = widget._paint_value_labels
    monkeypatch.setattr(widget, '_paint_value_labels',
                        lambda painter, labels: original(PaintRecorder(painter, captured), labels))
    widget.grab()
    assert {'1,000', '1', '1,001'} <= {text for text, _ in captured}
    widget.close()


@pytest.mark.parametrize('values, text, count', [([1000, 1, 1, 1, 1, 1], '1', 5),
                                                ([0, 0, 0, 0, 0, 0], '0', 0)])
def test_tiny_segments_keep_labels_and_all_zero_stacks_have_none(values, text, count, monkeypatch):
    widget = canvas(ChartData('bar', ['01-01'],
                              [line([value], str(i), stack='s') for i, value in enumerate(values)]),
                    width=960, height=300, detailed=True)
    captured = []
    original = widget._paint_value_labels
    monkeypatch.setattr(widget, '_paint_value_labels',
                        lambda painter, labels: original(PaintRecorder(painter, captured), labels))
    widget.grab()
    assert [value for value, _ in captured].count(text) == count
    widget.close()


@pytest.mark.parametrize('values, expected', [([-10], {'-10'}),
                                             ([10, -20], {'10', '-20', '-10'})])
def test_short_signed_bar_canvas_keeps_segment_and_total_labels(values, expected, monkeypatch):
    widget = canvas(ChartData('bar', ['01-01'],
                              [line([value], str(i), stack='s') for i, value in enumerate(values)]),
                    width=960, height=180, detailed=True)
    captured = []
    original = widget._paint_value_labels
    monkeypatch.setattr(widget, '_paint_value_labels',
                        lambda painter, labels: original(PaintRecorder(painter, captured), labels))
    widget.grab()
    assert expected <= {text for text, _ in captured}
    widget.close()


def test_vertical_bars_restore_round_baseline_and_relief():
    widget = canvas(ChartData('bar', ['01-01'], [line([10])]), width=800, height=500)
    image = widget.grab().toImage()
    _, width, _, _ = widget._stack_layout()
    center, top, bottom = widget._slot_center(0), widget._y(10), widget._y(0)
    corner = image.pixelColor(round(center - width / 2 + 1), round(bottom - 1))
    assert corner.blue() - corner.red() < 70
    high = image.pixelColor(round(center), round(top + 20))
    low = image.pixelColor(round(center), round(bottom - 20))
    assert high.blue() < low.blue()
    widget.close()


@pytest.mark.parametrize('values, expected', [([0, 15], {'15'}),
                                             ([10, None], {'10', '—'})])
def test_stack_labels_distinguish_zero_from_missing(values, expected, monkeypatch):
    widget = canvas(ChartData('bar', ['01-01'], [line([values[0]], 'a', stack='s'),
                                               line([values[1]], 'b', stack='s')]),
                    width=1440, height=600, detailed=True)
    captured = []
    original = widget._paint_value_labels

    def observe(painter, labels):
        return original(PaintRecorder(painter, captured), labels)

    monkeypatch.setattr(widget, '_paint_value_labels', observe)
    widget.grab()
    assert expected <= {text for text, _ in captured}
    if 0 in values:
        assert '0' not in {text for text, _ in captured}
    widget.close()


def test_horizontal_bars_restore_value_font_and_round_baseline(monkeypatch):
    widget = canvas(ChartData('hbar', ['公交'], [line([11])]), width=800, height=500, detailed=True)
    captured = []
    original = widget._paint_hbar
    monkeypatch.setattr(widget, '_paint_hbar', lambda painter: original(PaintRecorder(painter, captured)))
    image = widget.grab().toImage()
    assert next(font for text, font in captured if text == '11').pixelSize() == 13
    plot = widget.plot_rect()
    corner = image.pixelColor(round(widget._x(0) + 1), round(plot.center().y() - 6))
    assert corner.blue() - corner.red() < 70
    widget.close()


@pytest.mark.parametrize('width, height', [(960, 680), (1100, 800), (1440, 960)])
def test_statistics_header_has_no_overlap_at_supported_sizes(width, height, tmp_path, monkeypatch):
    app()
    import desktop_app
    from test_dashboard_page import session
    settings = QSettings(str(tmp_path / 'header.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *_: settings)
    window = desktop_app.MainWindow()
    window.statistics_page.set_session(session())
    window.navigate(2)
    window.resize(width, height)
    window.show()
    QTest.qWait(100)
    tabs = window.stats_tabs
    save = window.header.save_chip
    tabs_right = tabs.mapTo(window.header, QPoint()).x() + tabs.width()
    save_left = save.mapTo(window.header, QPoint()).x()
    assert tabs_right <= save_left or tabs.mapTo(window.header, QPoint()).y() >= save.y() + save.height()
    assert window.header.rect().contains(save.geometry())
    window.close()


@pytest.mark.parametrize('mode', ['overall', 'companies', 'period'])
def test_compact_network_canvas_stays_inside_card(mode):
    app()
    widget = NetworkChartPanel()
    widget.set_descriptor(descriptor(make_result(companies=('a',), comparison=mode == 'period')), snapshot(mode))
    widget.resize(640, 320)
    widget.set_compact_height(190)
    widget.show()
    QTest.qWait(50)
    for view in widget.chart_views:
        top = view.mapTo(widget, QPoint()).y()
        assert top >= 0 and top + view.height() <= widget.height()
    widget.close()


def test_hiding_every_network_bar_category_keeps_empty_selection():
    app()
    data = make_result(companies=('a',))
    widget = NetworkChartPanel()
    widget.set_descriptor(descriptor(data, key='linecount', allowed=('bar',),
                                     bar_result=endpoint_result(data)), snapshot('overall'))
    for key in tuple(widget.legend_buttons):
        widget.legend_buttons[key].click()
    assert widget._hidden_categories == {'bus', 'tram'}
    assert not widget.chart_views[0].has_values()
    assert set(widget.legend_buttons) == {'bus', 'tram'}
    widget.close()


def test_company_stack_colors_and_swatch_legend_restore_previous_distinction():
    app()
    widget = NetworkChartPanel()
    widget.set_descriptor(descriptor(make_result()), snapshot('companies'))
    series = widget.chart_views[0].data.series
    assert series[0].color != series[2].color
    assert series[1].color != series[3].color
    assert [entry['company'] for entry in widget.company_legend_entries] == ['a', 'b']
    assert widget.company_legend_entries[0]['colors']['bus'] == series[0].color
    assert widget.company_legend_entries[1]['colors']['bus'] == series[2].color
    widget.close()


def test_single_company_bar_legend_uses_its_actual_shaded_colors():
    app()
    data = make_result(companies=('b',))
    widget = NetworkChartPanel()
    widget.set_descriptor(descriptor(data, key='linecount', allowed=('bar',), bar_result=endpoint_result(data)),
                          snapshot('overall'))
    bars = widget.chart_views[0].data.series[0]
    assert [widget.legend_buttons[key]._color for key in ('bus', 'tram')] == bars.colors
    widget.close()


@pytest.mark.parametrize('mode', ['companies', 'period'])
def test_six_category_compact_charts_keep_plot_and_date_labels_in_bounds(mode):
    app()
    data = make_result(companies=('a',) if mode == 'period' else ('a', 'b'),
                       groups=('bus', 'tram', 'trolley', 'metro', 'waterbus', 'misc'),
                       comparison=mode == 'period')
    widget = NetworkChartPanel()
    widget.set_descriptor(descriptor(data), snapshot(mode))
    widget.set_compact_height(190)
    widget.resize(400, 190)
    widget.show()
    QTest.qWait(100)
    view = widget.chart_views[0]
    view.grab()
    plot = view.plot_rect()
    assert plot.bottom() + view._metrics().height() + 6 <= view.height()
    assert plot.height() >= 20
    widget.close()


def test_actual_period_descriptors_keep_two_columns_per_company():
    from network_model import NetworkOptions, build_network_snapshot
    from test_network_model import dashboard, history, NAMES
    rows = [history('transport-by-type', company, hour, amount, day=day, group=category)
            for company, amount in [('a', 10), ('b', 20)]
            for category in ('bus', 'tram') for day in (1, 2) for hour in (0, 1)]
    model = build_network_snapshot(dashboard(rows), NetworkOptions(mode='period', comparison_label='上周同期'), NAMES)
    for item in model.charts:
        if item.key != 'transport-by-type':
            continue
        widget = NetworkChartPanel()
        widget.set_descriptor(item, model)
        assert {series.stack for series in widget.chart_views[0].data.series} == {'current', 'comparison'}
        assert not widget.period_label.isVisible()
        assert [entry['name'] for entry in widget.series_legend_entries] == ['本期', '上周同期']
        assert all(owner == item.company_id for owner, _ in widget.result.series)
        clone = widget._open_fullscreen()
        assert len(clone.detail_summary.cards) == 2
        assert {card['company'] for card in clone.detail_summary.cards} == {item.company_id}
        widget._fullscreen_dialog.close()
        widget.close()


@pytest.mark.parametrize('mode', ['line', 'trend-bar', 'bar', 'pie'])
def test_network_period_uses_same_swatch_component_as_company_comparison(mode):
    from ui_kit import SeriesLegend
    app()
    data = make_result(companies=('a',), comparison=True)
    widget = NetworkChartPanel()
    widget.set_descriptor(descriptor(data, key='linecount' if mode == 'bar' else 'transport-by-type',
                                     allowed=(mode,), bar_result=endpoint_result(data)), snapshot('period', '上周同期'))
    assert not widget.period_label.isVisible()
    assert [entry['name'] for entry in widget.series_legend_entries] == ['本期', '上周同期']
    assert all(isinstance(entry['widget'], SeriesLegend) for entry in widget.series_legend_entries)
    current, previous = widget.series_legend_entries
    assert all(color.alphaF() == pytest.approx(1) for color in current['colors'])
    assert all(color.alphaF() == pytest.approx(tokens.CHART_COMPARISON_OPACITY, abs=.001)
               for color in previous['colors'])
    clone = widget._open_fullscreen()
    assert [entry['name'] for entry in clone.series_legend_entries] == ['本期', '上周同期']
    widget._fullscreen_dialog.close()
    widget.close()


@pytest.mark.parametrize('kind', ['company', 'latest'])
def test_shared_company_identity_legends_use_color_columns_and_keep_toggle(kind):
    from latest_info_page import TodayTrendPanel
    from ui_kit import SeriesLegend
    app()
    widget = (TodayTrendPanel('客流', allowed_modes=('line',)) if kind == 'latest' else panel('现金流'))
    data = result({('a', '__total__'): [bucket(1, 10)], ('b', '__total__'): [bucket(1, 20)]}, metric='cashflow')
    widget.set_result(data, {'a': '甲公司', 'b': '乙公司'})
    assert all(isinstance(chip, SeriesLegend) for chip in widget.legend_buttons.values())
    assert [entry['name'] for entry in widget.series_legend_entries] == ['甲公司', '乙公司']
    widget.legend_buttons['b'].click()
    assert widget._hidden_groups == {'b'}
    assert not widget.legend_buttons['b'].isChecked()
    assert widget.result is data
    clone = widget._open_fullscreen()
    assert all(isinstance(chip, SeriesLegend) for chip in clone.legend_buttons.values())
    assert not clone.legend_buttons['b'].isChecked()
    widget._fullscreen_dialog.close()
    widget.close()


@pytest.mark.parametrize('kind, mode', [('company', 'line'), ('company', 'area'),
                                      ('company', 'trend-bar'), ('company', 'bar'),
                                      ('city', 'line'), ('city', 'trend-bar'), ('latest', 'line')])
def test_shared_period_legend_is_inherited_by_all_time_chart_panels(kind, mode):
    from city_dashboard import CityChartPanel
    from latest_info_page import TodayTrendPanel
    from ui_kit import SeriesLegend
    app()
    widget = (CityChartPanel('population') if kind == 'city' else
              TodayTrendPanel('客流', allowed_modes=('line',)) if kind == 'latest' else panel('客流'))
    widget.set_mode(mode)
    data = result({('a', 'bus'): [bucket(1, 10)]}, comparison={('a', 'bus'): [bucket(1, 5)]},
                  comparison_window=(datetime(2023, 12, 29), datetime(2024, 1, 1)))
    widget.set_result(data, {'a': '甲公司'})
    assert [entry['key'] for entry in widget.series_legend_entries] == ['current', 'comparison']
    assert all(isinstance(entry['widget'], SeriesLegend) for entry in widget.series_legend_entries)
    assert widget.series_legend_entries[1]['colors'][0].alphaF() == pytest.approx(.45, abs=.001)
    assert not widget.period_label.isVisible()
    clone = widget._open_fullscreen()
    assert [entry['key'] for entry in clone.series_legend_entries] == ['current', 'comparison']
    assert clone.series_legend_entries[1]['colors'] == widget.series_legend_entries[1]['colors']
    widget._fullscreen_dialog.close()
    widget.close()


@pytest.mark.parametrize('mode', ['line', 'trend-bar'])
def test_single_category_period_has_only_two_shared_checkable_identity_items(mode):
    from ui_kit import SeriesLegend
    app()
    widget = NetworkChartPanel()
    widget.set_descriptor(descriptor(make_result(companies=('a',), groups=('bus',), comparison=True),
                                     allowed=(mode,)), snapshot('period', '上周同期'))
    assert widget.legend_host.flow.count() == 2
    assert set(widget.legend_buttons) == {'current', 'comparison'}
    assert all(isinstance(chip, SeriesLegend) for chip in widget.legend_buttons.values())
    assert widget.legend_buttons['comparison'].colors[0].alphaF() == pytest.approx(.45, abs=.001)
    widget.legend_buttons['comparison'].click()
    assert [series.key for series in widget.chart_views[0].visible_series()] == ['current']
    widget.close()


@pytest.mark.parametrize('mode', ['line', 'trend-bar', 'bar'])
def test_single_category_company_comparison_uses_shared_identity_component(mode):
    from ui_kit import SeriesLegend
    app()
    widget = NetworkChartPanel()
    data = make_result(groups=('bus',))
    widget.set_descriptor(descriptor(data, key='linecount' if mode == 'bar' else 'transport-by-type',
                                     allowed=(mode,), bar_result=endpoint_result(data)), snapshot('companies'))
    assert widget.legend_host.flow.count() == 2
    assert len(widget.series_legend_entries) == 2
    assert all(isinstance(entry['widget'], SeriesLegend) for entry in widget.series_legend_entries)
    widget.close()


@pytest.mark.parametrize('preset', ['previous', 'previous_week', 'previous_month', 'custom'])
def test_company_page_passes_selected_period_name_to_normal_and_enlarged_charts(tmp_path, preset):
    from dataclasses import replace
    from dashboard_model import build_dashboard
    from statistics_model import HistoryStore
    from stats_text import label
    from test_dashboard_page import loaded, session
    page = loaded(tmp_path)
    filters = replace(page.snapshot.filters, comparison=(datetime(2024, 1, 1), datetime(2024, 1, 8)))
    page.snapshot = build_dashboard(HistoryStore(session()['history'], session()['simulation_time']), filters)
    page.analysis_mode = 'period'
    page.comparison_preset = preset
    page._render_company()
    widget = page.company_dashboard.groups['a'].panels['cashflow']
    expected = label(preset)
    assert [entry['name'] for entry in widget.series_legend_entries] == ['本期', expected]
    clone = widget._open_fullscreen()
    assert [entry['name'] for entry in clone.series_legend_entries] == ['本期', expected]
    assert any(expected in caption.text() for caption in clone.detail_summary.findChildren(QLabel))
    widget._fullscreen_dialog.close()
    page.close()


def test_shared_categories_stay_hidden_when_switching_from_line_to_bar():
    widget = panel('客流')
    data = result({('a', 'bus'): [bucket(1, 10)], ('a', 'tram'): [bucket(1, 15)]})
    widget.set_result(data)
    for chip in tuple(widget.legend_buttons.values()):
        chip.click()
    widget.set_mode('bar')
    assert not widget.chart_views[0].has_values()
    assert widget.result is data
    widget.close()


@pytest.mark.parametrize('mode', ['companies', 'period'])
def test_long_identity_names_keep_compact_chart_plot_readable(mode):
    app()
    data = make_result(companies=('a',) if mode == 'period' else ('a', 'b'),
                       groups=('bus', 'tram', 'trolley', 'metro', 'waterbus', 'misc'),
                       comparison=mode == 'period')
    state = snapshot(mode, '自定义对比周期包含较长的日期范围说明')
    state.companies = {'a': '第一家公共交通运营公司的完整中文名称',
                       'b': '第二家公共交通运营公司的完整中文名称'}
    widget = NetworkChartPanel()
    widget.set_descriptor(descriptor(data), state)
    widget.set_compact_height(190)
    widget.resize(400, 190)
    widget.show()
    QTest.qWait(100)
    view = widget.chart_views[0]
    assert view.plot_rect().height() >= 20
    assert view.plot_rect().bottom() + view._metrics().height() + 6 <= view.height()
    assert all(entry['widget'].width() <= 140 for entry in widget.series_legend_entries)
    for entry in widget.series_legend_entries:
        # The short current-period label is already visible; long company and
        # custom comparison identities still need their complete hover text.
        assert entry['widget'].toolTip() == ('' if entry['name'] == '本期' else entry['name'])
    widget.close()


def test_compact_height_updates_already_rendered_shared_legends_and_restores_them():
    widget = panel('现金流')
    widget.set_result(result({('a', '__total__'): [bucket(1, 10)],
                              ('b', '__total__'): [bucket(1, 20)]}, metric='cashflow'))
    assert all(entry['widget'].sizeHint().height() == 22 for entry in widget.series_legend_entries)
    widget.set_compact_height(190)
    assert all(entry['widget'].sizeHint().height() == 18 for entry in widget.series_legend_entries)
    widget.clear_compact_height()
    assert all(entry['widget'].sizeHint().height() == 22 for entry in widget.series_legend_entries)
    widget.close()
