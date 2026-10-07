"""UI-09: compare real tooltip value pixels with an unbroken reference line."""
from decimal import Decimal
from math import ceil

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter

from chart_canvas import ChartCanvas, ChartData, Series


@pytest.fixture(scope='module', autouse=True)
def tooltip_theme(qt_application):
    # Match application font registration. Bare offscreen Qt otherwise uses
    # an unavailable-family fallback, which is much wider than the app font.
    from stats_style import initialize_theme
    initialize_theme(qt_application)


def image_for(width, height, dpr):
    image = QImage(ceil(width * dpr), ceil(height * dpr), QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(dpr)
    image.fill(Qt.GlobalColor.transparent)
    return image


class ValuePixels:
    """Forward all drawing; also capture the actual value ink on transparency."""
    def __init__(self, painter, actual, value):
        self.painter, self.actual, self.value = painter, actual, value
        self.draws = {}

    def drawText(self, rect, flags, text):
        self.draws[text] = (QRectF(rect), flags, self.painter.font())
        if text == self.value:
            self.actual.setFont(self.painter.font())
            self.actual.setPen(Qt.GlobalColor.black)
            self.actual.drawText(rect, flags, text)
        return self.painter.drawText(rect, flags, text)

    def __getattr__(self, name):
        return getattr(self.painter, name)


def render_tooltip(canvas, name, value, dpr=1, note=''):
    layout = canvas._tooltip_layout('2013-05-19 周日', [(QColor('#1677ff'), name, value, note)])
    width, height = layout[:2]
    image = image_for(width + 4, height + 4, dpr)
    actual = image_for(width + 4, height + 4, dpr)
    expected = image_for(width + 4, height + 4, dpr)
    painter, ink = QPainter(image), QPainter(actual)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    recorder = ValuePixels(painter, ink, value)
    box = QRectF(2, 2, width, height)
    try:
        canvas._draw_tooltip(recorder, box, layout)
    finally:
        painter.end(); ink.end()
    rect, _, font = recorder.draws[value]
    reference = QPainter(expected)
    reference.setFont(font)
    reference.setPen(Qt.GlobalColor.black)
    reference.drawText(rect, Qt.TextFlag.TextSingleLine | Qt.AlignmentFlag.AlignVCenter
                       | Qt.AlignmentFlag.AlignRight, value)
    reference.end()
    return image, actual, expected, box, recorder.draws


def assert_complete_single_line(actual, expected, box, draws, value):
    # An independent single-line QPainter image catches lone units, split
    # numbers, and missing glyphs; geometry alone would accept the old wrap.
    assert bytes(actual.constBits()) == bytes(expected.constBits()), value
    rect, flags, font = draws[value]
    metrics = QFontMetricsF(font)
    needed = metrics.boundingRect(rect, Qt.TextFlag.TextSingleLine
                                  | Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, value)
    assert rect.contains(needed), (value, rect, needed)
    assert box.contains(rect)
    assert font.pixelSize() == 12


def test_reported_people_trip_unit_is_one_complete_painted_line():
    canvas = ChartCanvas()
    try:
        _, actual, expected, box, draws = render_tooltip(canvas, '八连交通集团', '123,456.78 人次')
        assert_complete_single_line(actual, expected, box, draws, '123,456.78 人次')
    finally:
        canvas.close()


@pytest.mark.parametrize('dpr', [1, 1.25, 1.5, 2])
@pytest.mark.parametrize('size,detailed', [((480, 260), False), ((400, 190), False), ((960, 540), True)])
@pytest.mark.parametrize('name', ['八连交通集团', '环比 · 滨海市公共交通运营有限公司 [76561198845688243]'])
@pytest.mark.parametrize('unit', ['人数', '人次', '人次每班', '人次每车公里'])
@pytest.mark.parametrize('number', ['0', '-123,456.78', '123,456.78', '123,456,789,012,345,678,901,234,567.89'])
def test_values_and_units_keep_every_glyph_on_one_line(dpr, size, detailed, name, unit, number):
    canvas = ChartCanvas(detailed=detailed); canvas.resize(*size)
    value = f'{number} {unit}'
    try:
        _, actual, expected, box, draws = render_tooltip(canvas, name, value, dpr, '观测不完整')
        assert_complete_single_line(actual, expected, box, draws, value)
        name_rect, name_flags, font = draws[name]
        assert box.contains(name_rect)
        assert QFontMetricsF(font).boundingRect(name_rect, name_flags, name).height() <= name_rect.height()
        value_rect = draws[value][0]
        assert not name_rect.intersects(value_rect)
        assert box.width() + 2 <= canvas.screen().availableGeometry().width()
        if number.startswith('123,456,789'):
            assert value_rect.top() >= name_rect.bottom()
    finally:
        canvas.close()


def test_missing_rows_are_absent_and_zero_negative_values_are_preserved():
    canvas = ChartCanvas()
    data = ChartData('line', ['05-19'], [
        Series('zero', '实际零', QColor('blue'), [Decimal(0)]),
        Series('negative', '负数', QColor('orange'), [Decimal('-123456.789')]),
        Series('missing', '缺失', QColor('red'), [None]),
    ], unit='人次')
    canvas.set_data(data)
    try:
        rows = canvas._tooltip_rows(0)
        assert [(row[1], row[2]) for row in rows] == [('实际零', '0 人次'), ('负数', '-123,456.78 人次')]
        assert data.series[1].values == [Decimal('-123456.789')]
        canvas.set_hidden({'negative'})
        assert [row[1] for row in canvas._tooltip_rows(0)] == ['实际零']
        canvas.set_hidden({'negative', 'zero'})
        assert canvas._tooltip_rows(0) == []
    finally:
        canvas.close()
