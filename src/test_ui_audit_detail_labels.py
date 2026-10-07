"""Actual detailed-label painting stays readable as the same canvas shrinks."""
import copy
import pytest
from PySide6.QtCore import QRectF
from chart_canvas import ChartData, format_value
from test_chart_canvas import canvas, line


class LabelRecorder:
    def __init__(self, painter, drawn):
        self.painter, self.drawn = painter, drawn
    def __getattr__(self, name):
        return getattr(self.painter, name)
    def drawText(self, rect, flags, text):
        self.drawn.append((QRectF(rect), str(text)))
        return self.painter.drawText(rect, flags, text)


@pytest.mark.parametrize('size', [(960, 540), (700, 320), (420, 220), (300, 180)])
def test_detail_label_paint_stays_in_own_column_and_out_of_axes(size, monkeypatch):
    values = ([420048, 406632, 433524, 408476, 466113, 399453, 389049],
              [18305, 18176, 18003, 18142, 28488, 22819, 22926],
              [51454, 53202, 50077, 53241, 62784, 55560, 55347],
              [2002, 1745, 2120, 1792, 2206, 1612, 1347])
    data = ChartData('bar', [str(i) for i in range(7)],
                     [line(row, str(i), stack='transport') for i, row in enumerate(values)])
    original_values = copy.deepcopy(values)
    widget = canvas(data, width=size[0], height=size[1], detailed=True)
    drawn = []
    paint = widget._paint_value_labels
    monkeypatch.setattr(widget, '_paint_value_labels', lambda p, labels: paint(LabelRecorder(p, drawn), labels))
    try:
        widget.grab()
        plot = widget.plot_rect()
        columns = {format_value(value): index for row in values for index, value in enumerate(row)}
        columns.update({format_value(sum(row[index] for row in values)): index for index in range(7)})
        for rect, text in drawn:
            assert plot.contains(rect), (text, rect, plot)
            slot = plot.width() / 7
            center = widget._slot_center(columns[text])
            assert center - slot / 2 <= rect.left() < rect.right() <= center + slot / 2
        for i, (rect, text) in enumerate(drawn):
            assert not any(rect.adjusted(-1, -1, 1, 1).intersects(other) for other, _ in drawn[:i]), text
        if size[0] <= 700:
            assert '2,002' not in {text for _, text in drawn}
        assert values == original_values
        assert len(widget._tooltip_rows(0, 'transport')) == 4
        widget.resize(1800, 700)
        drawn.clear(); widget.grab()
        assert '2,002' in {text for _, text in drawn}, 'wide layout must restore safely placed labels'
    finally:
        widget.close(); widget.deleteLater()


def test_shrinking_signed_stacks_keeps_values_and_total_priority(monkeypatch):
    data = ChartData('bar', ['one'], [line([10], 'positive', stack='s'), line([-20], 'negative', stack='s')])
    widget = canvas(data, width=400, height=190, detailed=True)
    drawn = []
    paint = widget._paint_value_labels
    monkeypatch.setattr(widget, '_paint_value_labels', lambda p, labels: paint(LabelRecorder(p, drawn), labels))
    try:
        widget.grab()
        assert '-10' in {text for _, text in drawn}
        assert {row[2] for row in widget._tooltip_rows(0, 's')} == {'10', '-20'}
    finally:
        widget.close(); widget.deleteLater()


def test_external_segment_label_never_sits_on_another_colored_segment(monkeypatch):
    widget = canvas(ChartData('bar', ['one'], [line([1000], 'base', stack='s'),
                    line([20], 'small', stack='s'), line([100], 'top', stack='s')]),
                    width=960, height=300, detailed=True)
    drawn, sources = [], {}
    paint = widget._paint_value_labels
    def observe(painter, labels):
        sources.update({label['text']: label.get('inside_rect') for label in labels})
        return paint(LabelRecorder(painter, drawn), labels)
    monkeypatch.setattr(widget, '_paint_value_labels', observe)
    try:
        widget.grab()
        for rect, text in drawn:
            inside = sources[text]
            if inside is not None and any(path.intersects(rect) for _, _, path in widget._bar_hits):
                assert inside.contains(rect), (text, rect, inside)
    finally:
        widget.close(); widget.deleteLater()
