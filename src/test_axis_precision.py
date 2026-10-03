"""Auto axes remain distinguishable within the authorized display precision."""
from decimal import Decimal

import pytest
from chart_canvas import AxisSpec, ChartData, _tick_text
from test_chart_canvas import canvas, line


@pytest.mark.parametrize('values,places', [
    ([1000001, 1000002], 2), ([121.91, 121.99], 1),
    ([.001, .002], 2), ([-.002, -.001], 2),
    ([1000000000001, 1000000000002], 2),
])
def test_compact_auto_axis_has_distinct_ticks_without_extra_decimals(values, places):
    widget = canvas(ChartData('line', ['a', 'b'], [line(values)], decimal_places=places), 400, 190)
    ticks = widget._ticks()
    labels = [_tick_text(value, widget.axis.step, places) for value in ticks]
    assert len(labels) >= 2
    assert len(set(labels)) == len(labels)
    assert all(len(text.partition('.')[2]) <= places for text in labels)
    assert widget.axis.lower * widget.axis.scale <= min(values)
    assert widget.axis.upper * widget.axis.scale >= max(values)
    assert widget.data.series[0].values == values
    widget.close()


@pytest.mark.parametrize('kind', ['bar', 'hbar'])
def test_small_positive_and_negative_auto_bar_axes_keep_zero_and_distinct_labels(kind):
    values = [Decimal('-.001'), Decimal('.002')]
    widget = canvas(ChartData(kind, ['a', 'b'], [line(values)]), 400, 190)
    labels = [_tick_text(value, widget.axis.step) for value in widget._ticks()]
    assert len(set(labels)) == len(labels)
    assert widget.axis.lower < 0 < widget.axis.upper
    assert 0 in widget._ticks()
    assert widget.data.series[0].values == values
    widget.close()


def test_decimal_tick_generation_does_not_shift_point_eight_to_point_seven():
    widget = canvas(ChartData('line', ['a', 'b'], [line([.8, 1.1])]), 960, 680)
    assert widget.axis.step == .1
    assert widget._ticks() == [.7, .8, .9, 1., 1.1, 1.2]
    assert [_tick_text(value, .1) for value in widget._ticks()] == ['0.7', '0.8', '0.9', '1.0', '1.1', '1.2']
    widget.close()


@pytest.mark.parametrize('kind', ['line', 'bar', 'hbar'])
def test_explicit_axis_remains_the_same_object_with_decimal_tick_coordinates(kind):
    widget = canvas(ChartData(kind, ['a', 'b'], [line([.8, 1.1])]))
    spec = AxisSpec(.7, 1.2, .1)
    widget.set_axis(spec)
    widget.grab()
    assert widget.axis is spec
    assert widget._ticks() == [.7, .8, .9, 1., 1.1, 1.2]
    widget.close()


def test_tick_normalization_does_not_round_actual_hover_values():
    values = [Decimal('.7999999999999999'), Decimal('1.239')]
    widget = canvas(ChartData('line', ['a', 'b'], [line(values)]))
    assert widget._tooltip_rows(0)[0][2] == '0.79'
    assert widget._tooltip_rows(1)[0][2] == '1.23'
    widget.close()
