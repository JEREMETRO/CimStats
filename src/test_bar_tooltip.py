"""Real painted bars and pointer delivery, with explicit boundary fixtures."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import QApplication

from chart_canvas import ChartCanvas, ChartData, Series


class RealPainter:
    def __init__(self, painter, owner):
        self.painter, self.owner = painter, owner

    def drawText(self, rect, flags, text):
        self.owner.drawn.append((rect, flags, text, self.painter.font()))
        return self.painter.drawText(rect, flags, text)

    def __getattr__(self, name):
        return getattr(self.painter, name)


class PaintedCanvas(ChartCanvas):
    def _paint_tooltip(self, painter, title, rows):
        self.painted_tip = (title, rows)
        super()._paint_tooltip(painter, title, rows)

    def _draw_tooltip(self, painter, box, layout):
        self.drawn = []
        super()._draw_tooltip(RealPainter(painter, self), box, layout)
        self.tip_box = box


def deliver(widget, point):
    QApplication.sendEvent(widget, QMouseEvent(
        QEvent.Type.MouseMove, point, widget.mapToGlobal(point.toPoint()),
        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
    widget.grab()


def bar_point(widget, position, value):
    stacks, width, gap, total = widget._stack_layout()
    return QPointF(widget._slot_center(0) - total / 2 + position * (width + gap) + width / 2,
                   widget._y(value))


@pytest.mark.parametrize('size,detailed', [((480, 260), False), ((400, 190), False), ((960, 540), True)])
def test_pointer_selects_only_the_painted_stack_and_clears_gaps(size, detailed):
    widget = PaintedCanvas(detailed=detailed)
    widget.resize(*size)
    widget.set_data(ChartData('bar', ['05-19'], [
        Series('bus', '本期 · 公交', QColor('blue'), [10], stack='current'),
        Series('tram', '本期 · 电车', QColor('orange'), [5], stack='current'),
        Series('old-bus', '环比 · 公交', QColor('blue'), [20], stack='previous', faded=True),
        Series('old-tram', '环比 · 电车', QColor('orange'), [7], stack='previous', faded=True),
    ], unit='人次', titles=['2013-05-19 周日']))
    widget.show(); QApplication.processEvents(); widget.grab()
    try:
        for position, expected in ((0, ['本期 · 公交', '本期 · 电车']),
                                   (1, ['环比 · 公交', '环比 · 电车'])):
            point = bar_point(widget, position, 3)
            deliver(widget, QPointF(1, 1))
            image = widget.grab().toImage()
            color = image.pixelColor(int(point.x() * image.devicePixelRatio()),
                                     int(point.y() * image.devicePixelRatio()))
            assert color.alpha() == 255 and color.saturation() > 100
            deliver(widget, point)
            assert [row[1] for row in widget.painted_tip[1]] == expected
        gap = (bar_point(widget, 0, 3) + bar_point(widget, 1, 3)) / 2
        deliver(widget, gap)
        assert widget._hover is None
        deliver(widget, bar_point(widget, 0, 3))
        deliver(widget, QPointF(bar_point(widget, 0, 3).x(), widget.plot_rect().top() - 3))
        assert widget._hover is None
    finally:
        widget.close()


@pytest.mark.parametrize('value', [0, -10])
def test_zero_is_unpainted_and_negative_hits_only_its_own_company(value):
    widget = PaintedCanvas(); widget.resize(400, 190)
    widget.set_data(ChartData('bar', ['x'], [
        Series('a', '公交公司 [76561198845688243]', QColor('blue'), [value]),
        Series('b', '公交公司 [76561198000000001]', QColor('orange'), [8]),
        Series('missing', '缺失', QColor('red'), [None]),
    ]))
    widget.show(); QApplication.processEvents(); widget.grab()
    try:
        point = bar_point(widget, 0, value / 2)
        if value == 0:
            point.setY(min(max(widget._y(0), widget.plot_rect().top() + 3), widget.plot_rect().bottom() - 3))
        deliver(widget, point)
        if value == 0:
            assert widget._hover is None and not any(index == 0 and stack == 'a'
                                                    for index,stack,path in widget._bar_hits)
            return
        assert [row[1] for row in widget.painted_tip[1]] == ['公交公司 [76561198845688243]']
        assert widget.painted_tip[1][0][2] == str(value)
        widget.set_hidden({'a'}); widget.grab()
        assert widget._hover is None
        widget.set_data(None); widget.grab()
        assert widget._hover is None
    finally:
        widget.close()


def test_comparison_bar_uses_its_real_date_in_painted_heading():
    from statistics_model import Bucket, METRICS, Query, Result
    from stats_charts import ChartPanel
    day = datetime(2013, 5, 19); old = day - timedelta(days=7)
    def bucket(date, value):
        return Bucket(date, date + timedelta(days=1), Decimal(value), True, False, date, None, None, 24)
    query = Query('transport-by-type', ('76561198845688243',), None, day, day + timedelta(days=1),
                  'day', (old, old + timedelta(days=1)))
    result = Result(query, METRICS[query.metric], {('76561198845688243', 'bus'): [bucket(day, 10)]},
                    {('76561198845688243', 'bus'): [bucket(old, 20)]},
                    (query.start, query.end), query.comparison)
    panel = ChartPanel('客流', default_mode='trend-bar'); panel.set_result(result, {'76561198845688243': '八连交通集团'})
    widget = PaintedCanvas(); widget.resize(400, 190); widget.set_data(panel.chart_views[0].data)
    widget.show(); QApplication.processEvents(); widget.grab()
    try:
        deliver(widget, bar_point(widget, 1, 5))
        assert '2013-05-12' in widget.painted_tip[0]
        assert '2013-05-19' not in widget.painted_tip[0]
        assert len(widget.painted_tip[1]) == 1
    finally:
        widget.close(); panel.close()


def test_six_segments_and_long_identity_draw_without_elision_or_canvas_clipping():
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QFontMetricsF
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QWidget
    host = QWidget(); host.resize(960, 680)
    widget = PaintedCanvas(host); widget.setGeometry(30, 30, 400, 140)
    names = [f'环比 · 滨海市公共交通运营有限公司 [76561198845688243] · 分类{n}' for n in range(6)]
    widget.set_data(ChartData('bar', ['05-12'], [
        Series(str(n), name, QColor('blue'), [10], stack='previous', faded=True)
        for n, name in enumerate(names)], unit='人次', titles=['2013-05-12 周日']))
    host.show(); QApplication.processEvents(); widget.grab()
    try:
        deliver(widget, bar_point(widget, 0, 3)); QTest.qWait(30)
        tip = widget._overflow_tip
        assert tip is not None and tip.isVisible()
        assert tip.windowType() == Qt.WindowType.ToolTip
        assert tip.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
        assert tip.focusPolicy() == Qt.FocusPolicy.NoFocus
        pixels = tip.grab().toImage()
        assert pixels.pixelColor(int(5 * pixels.devicePixelRatio()), int(5 * pixels.devicePixelRatio())).alpha() == 255
        assert set(names) <= {text for _, _, text, _ in widget.drawn}
        for rect, flags, text, font in widget.drawn:
            assert font.pixelSize() == 12 and font.weight() == 400
            assert widget.tip_box.contains(rect)
            needed = QFontMetricsF(font).boundingRect(QRectF(0, 0, rect.width(), 10000), flags, text)
            assert needed.height() <= rect.height()
        assert widget.screen().availableGeometry().contains(tip.geometry())
        deliver(widget, QPointF(1, 1))
        assert not tip.isVisible()
        deliver(widget, bar_point(widget, 0, 3)); QTest.qWait(10)
        host.hide(); QApplication.processEvents()
        assert not tip.isVisible() and widget._hover is None
    finally:
        host.close()


def test_dense_overlapping_marks_hit_the_last_actually_painted_company():
    widget = PaintedCanvas(); widget.resize(400, 190)
    widget.set_data(ChartData('bar', list(map(str, range(120))), [
        Series(key, key, QColor(color), [10] * 120) for key, color in (
            ('a', 'blue'), ('b', 'orange'), ('c', 'green'))]))
    widget.show(); QApplication.processEvents(); widget.grab()
    try:
        # At minimum bar width, adjacent date slots overlap. Paint order,
        # rather than the first matching old slot, decides the visible mark.
        point = QPointF(widget._slot_center(20), widget._y(5))
        matching = [(index, key) for index, key, path in widget._bar_hits if path.contains(point)]
        assert len(matching) > 1
        deliver(widget, point)
        assert (widget._hover, widget._hover_stack) == matching[-1]
    finally:
        widget.close()


def test_network_period_stack_keeps_all_valid_categories_and_actual_date():
    from test_network_charts import make_result, descriptor, snapshot
    from network_charts import NetworkChartPanel
    panel = NetworkChartPanel()
    result = make_result(companies=('a',), groups=('bus', 'tram', 'trolleybus', 'metro', 'waterbus', 'share'),
                         comparison=True, missing=('a', 'share', 0, True))
    panel.set_descriptor(descriptor(result, company_id='a'), snapshot('period', '上周同期'))
    widget = PaintedCanvas(); widget.resize(400, 190); widget.set_data(panel.chart_views[0].data)
    widget.show(); QApplication.processEvents(); widget.grab()
    try:
        deliver(widget, bar_point(widget, 1, 3))
        assert len(widget.painted_tip[1]) == 5
        assert all('上周同期' in row[1] for row in widget.painted_tip[1])
        assert widget.painted_tip[0].startswith('2024-02-16')
        deliver(widget, bar_point(widget, 0, 3))
        assert len(widget.painted_tip[1]) == 6
        assert widget.painted_tip[0].startswith('2024-02-19')
    finally:
        widget.close(); panel.close()
