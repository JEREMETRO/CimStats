"""The QPainter chart engine: axes, label thinning, hover, hidden series, zoom."""
import os
import sys
from decimal import Decimal
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import QApplication

from chart_canvas import (AxisSpec, ChartCanvas, ChartData, Series, auto_axis, format_value, nice_ticks,
                          _tick_text)


def app():
    return QApplication.instance() or QApplication([])


def canvas(data, width=480, height=260, **kwargs):
    app()
    widget = ChartCanvas(**kwargs)
    widget.resize(width, height)
    widget.set_data(data)
    widget.grab()
    return widget


def line(values, key='a', **kwargs):
    return Series(key=key, name=key.upper(), color=QColor('#1677FF'), values=values, **kwargs)


def move(widget, x, y):
    point = QPointF(x, y)
    event = QMouseEvent(QMouseEvent.Type.MouseMove, point, widget.mapToGlobal(point.toPoint()),
                        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    widget.mouseMoveEvent(event)


@pytest.mark.parametrize('low, high', [(0, 1), (0.2, 0.8), (180, 4200), (-7, 3), (14.72, 14.77), (0, 46000)])
def test_nice_ticks_cover_range_with_round_steps(low, high):
    lower, upper, step = nice_ticks(low, high, 6)
    assert lower <= low and upper >= high
    assert round((upper - lower) / step) + 1 <= 6
    mantissa = step / 10 ** (len(str(int(step))) - 1) if step >= 1 else round(step * 10 ** 6) / 10 ** (
        len(str(round(step * 10 ** 6))) - 1)
    assert round(mantissa, 6) in (1, 2, 2.5, 3, 4, 5, 6)


def test_bars_start_at_zero_and_flat_lines_get_a_readable_padded_range():
    bars = auto_axis([147214, 147740], zero=True)
    assert bars.lower == 0 and bars.scale == 10000 and bars.unit_suffix == '万'
    flat = auto_axis([147214, 147740], zero=False)
    assert flat.lower > 0 and flat.upper * flat.scale >= 147740
    assert flat.lower * flat.scale <= 147214


def test_tick_labels_keep_the_decimals_their_step_needs():
    assert _tick_text(72.5, 2.5) == '72.5'
    assert _tick_text(14.75, 0.05) == '14.75'
    assert _tick_text(40000, 10000) == '40,000'


def test_value_formatting_is_exact_and_grouped():
    assert format_value(Decimal('1228735.55')) == '1,228,735.55'
    assert format_value(Decimal('73')) == '73'
    assert format_value(None) == '—'


def test_line_plot_reserves_caption_row_above_ticks_and_hover_reports_slot():
    data = ChartData('line', [f'05-{day}' for day in range(13, 20)],
                     [line([Decimal(147000 + day * 70) for day in range(7)])], unit='人')
    widget = canvas(data)
    assert widget.axis.unit_suffix == '万'
    assert widget.plot_rect().top() >= widget.fontMetrics().height() * 1.5
    seen = []
    widget.hover_changed.connect(seen.append)
    plot = widget.plot_rect()
    move(widget, plot.left() + plot.width() * 3.5 / 7, plot.center().y())
    assert seen == [3]
    move(widget, 1, 1)
    assert seen == [3, None]


def test_missing_values_break_lines_and_empty_data_shows_message():
    widget = canvas(ChartData('line', ['a', 'b', 'c'], [line([1, None, 3])]))
    assert widget.has_values()
    empty = canvas(ChartData('line', ['a', 'b'], [line([None, None])], empty_text='暂无可用数据'))
    assert not empty.has_values()
    assert empty.accessibleName() == '暂无可用数据'


def test_hidden_series_are_excluded_from_axis_and_tooltip():
    data = ChartData('bar', ['x', 'y'], [line([10, 20], 'small'), line([1000, 2000], 'large')])
    widget = canvas(data)
    assert widget.axis.upper * widget.axis.scale >= 2000
    widget.set_hidden({'large'})
    widget.grab()
    assert widget.axis.upper * widget.axis.scale < 100
    assert [row[1] for row in widget._tooltip_rows(1)] == ['SMALL']


def test_stacked_bars_sum_only_within_a_stack():
    data = ChartData('bar', ['x'], [line([10], 'a', stack='s1'), line([15], 'b', stack='s1'),
                                    line([40], 'c', stack='s2')])
    widget = canvas(data)
    assert widget.axis.upper * widget.axis.scale >= 40
    assert widget.axis.upper * widget.axis.scale < 65


def test_shared_axis_override_wins_over_auto_range():
    spec = AxisSpec(0, 100, 20)
    widget = canvas(ChartData('line', ['a', 'b'], [line([1, 2])]))
    widget.set_axis(spec)
    widget.grab()
    assert widget.axis is spec


def test_x_labels_thin_out_on_narrow_canvas():
    labels = [f'2024-01-{day:02d}' for day in range(1, 32)]
    widget = canvas(ChartData('line', labels, [line(list(range(31)))]), width=300)
    assert widget.slot_count() == 31
    plot = widget.plot_rect()
    assert plot.width() / 31 < widget.fontMetrics().horizontalAdvance(labels[0])


def test_donut_slices_toggle_and_click_emits_key():
    data = ChartData('donut', ['步行', '公共交通'], [Series('share', '分担', QColor('#000'),
                                                     [Decimal(26), Decimal(52)], keys=['walk', 'pt'],
                                                     colors=[QColor('#1677FF'), QColor('#159A79')])],
                     center_text='100', center_caption='%')
    widget = canvas(data, width=420, height=240)
    assert [part['key'] for part in widget._slices] == ['walk', 'pt']
    assert round(sum(part['percent'] for part in widget._slices)) == 100
    clicked = []
    widget.slice_clicked.connect(clicked.append)
    part = widget._slices[1]
    angle = part['start'] + part['span'] / 2
    from math import cos, radians, sin
    radius = (part['inner'] + part['outer']) / 2
    point = part['center'] + QPointF(cos(radians(angle)) * radius, -sin(radians(angle)) * radius)
    event = QMouseEvent(QMouseEvent.Type.MouseButtonPress, point, widget.mapToGlobal(point.toPoint()),
                        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    widget.mousePressEvent(event)
    assert clicked == ['pt']


def test_horizontal_bars_name_every_category():
    data = ChartData('hbar', ['公交', '有轨电车', '无轨电车'], [line([5, 3, 1])])
    widget = canvas(data, height=200)
    assert widget.axis.lower == 0
    assert widget.plot_rect().left() > widget.fontMetrics().horizontalAdvance('有轨电车')


def test_detailed_canvas_zooms_and_resets():
    data = ChartData('line', [str(index) for index in range(40)], [line(list(range(40)))])
    widget = canvas(data, detailed=True)
    assert widget.window() == (0, 40)
    widget.zoom(2, .5)
    first, last = widget.window()
    assert last - first == 20 and first == 10
    widget.set_window(0, 40)
    assert widget.window() == (0, 40)
