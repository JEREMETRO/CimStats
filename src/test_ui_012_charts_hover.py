"""0.1.2 chart owner regressions: all home structure views and hover edges."""
from dataclasses import replace
from decimal import Decimal
from math import ceil
import pytest
from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from test_latest_info_page import page, snapshot, session


@pytest.mark.parametrize('attribute', ['passengers', 'departures'])
@pytest.mark.parametrize('width', [400, 520, 864])
def test_line_share_keeps_aligned_values_close_to_names_at_both_widths(qt_application, monkeypatch, attribute, width):
    from latest_info_charts import PassengerRanking, DepartureStructure, short_line_name
    data = snapshot()  # Explicit capacity fixture using the actual snapshot model.
    panel = PassengerRanking() if attribute == 'passengers' else DepartureStructure()
    if attribute == 'passengers':
        panel.set_data(data.lines, data.passenger_top10, data.passenger_modes)
    else:
        panel.set_data(data.lines, data.departure_modes, data.total_departures)
    panel.show_line_share()
    panel.resize(width, panel.height())
    panel.show()
    qt_application.processEvents()
    panel.grab()
    try:
        assert panel.width() == width
        rows = panel.visible_share_rows()
        assert rows and all(row.name.width() <= 112 for row in rows)
        assert len({row.number.x() for row in rows}) == len({row.share.x() for row in rows}) == 1
        from PySide6.QtCore import QPoint
        ring_left = panel.share_ring.mapTo(panel.line_share, QPoint(0, 0)).x()
        data_right = max(row.share.mapTo(panel.line_share, row.share.rect().bottomRight()).x() for row in rows)
        assert abs(ring_left - (panel.line_share.width() - 1 - data_right)) <= 8
        legend_left = rows[0].dot.mapTo(panel.line_share, QPoint(0, 0)).x()
        ring_right = panel.share_ring.mapTo(panel.line_share, panel.share_ring.rect().bottomRight()).x()
        ring_gap = legend_left - ring_right - 1
        name_gap = rows[0].number.x() - rows[0].name.geometry().right() - 1
        if width >= 520:
            gaps = [ring_left, panel.line_share.width() - 1 - data_right, ring_gap, name_gap]
            assert max(gaps) - min(gaps) <= 2
        else:
            assert ring_gap >= 16 and name_gap >= 4
        assert all(row.number.width() == 90 and row.share.width() == 41 for row in rows)
        painted = []
        original = QPainter.drawText
        def record(painter, *args):
            if isinstance(args[-1], str):
                painted.append(args[-1])
            return original(painter, *args)
        monkeypatch.setattr(QPainter, 'drawText', record)
        for row in rows:
            painted.clear()
            row.name.grab()
            assert any(short_line_name(row.entry.name) in text for text in painted)
            assert row.number.x() - row.name.geometry().right() - 1 == name_gap
            assert row.share.x() - row.number.geometry().right() - 1 == 8
            for field in (row.number, row.share):
                assert field.isVisible()
                assert field.width() >= field.fontMetrics().horizontalAdvance(field.text())
                assert panel.rect().contains(field.mapTo(panel, field.rect().bottomRight()))
    finally:
        panel.close()
        panel.deleteLater()


@pytest.mark.parametrize('before_show', [True, False])
def test_mode_menu_reserves_real_painted_arrow_space(qt_application, before_show):
    from latest_info_charts import ModeMenu
    from PySide6.QtWidgets import QStyle, QStyleOptionButton
    menu = ModeMenu()
    captions = ['全部制式', '公交', '有轨电车', '无轨电车', '地铁', '单轨', '水上巴士']
    for caption in captions:
        menu.addItem(caption, userData=caption)
    if not before_show:
        menu.show()
        qt_application.processEvents()
    arrows = []
    original = menu._drawDropDownIcon
    menu._drawDropDownIcon = lambda painter, rect: (arrows.append(QRectF(rect)), original(painter, rect))[-1]
    try:
        for index, caption in enumerate(captions):
            menu.setCurrentIndex(index)
            menu.show()
            qt_application.processEvents()
            arrows.clear()
            menu.grab()
            option = QStyleOptionButton()
            menu.initStyleOption(option)
            contents = menu.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, option, menu)
            ink = menu.fontMetrics().boundingRect(contents, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine, caption)
            assert arrows and ink.right() + 4 < arrows[-1].left(), caption
            assert contents.contains(ink), caption
            assert menu.width() <= 88
    finally:
        menu.close()
        menu.deleteLater()


@pytest.mark.parametrize('attribute', ['passengers', 'departures'])
def test_share_spacing_can_shrink_after_wide_card(qt_application, attribute):
    from latest_info_charts import PassengerRanking, DepartureStructure
    from PySide6.QtCore import QPoint
    data = snapshot()
    panel = PassengerRanking() if attribute == 'passengers' else DepartureStructure()
    if attribute == 'passengers':
        panel.set_data(data.lines, data.passenger_top10, data.passenger_modes)
    else:
        panel.set_data(data.lines, data.departure_modes, data.total_departures)
    panel.show_line_share()
    panel.show()
    try:
        for width in (864, 400, 639, 640, 520, 864):
            panel.resize(width, panel.height())
            qt_application.processEvents()
            panel.grab()
            assert panel.width() == width
            rows = panel.visible_share_rows()
            first = rows[0]
            left = panel.share_ring.x()
            right = panel.line_share.width() - 1 - first.share.mapTo(panel.line_share, first.share.rect().bottomRight()).x()
            ring_gap = first.dot.mapTo(panel.line_share, QPoint()).x() - panel.share_ring.geometry().right() - 1
            name_gap = first.number.x() - first.name.geometry().right() - 1
            if width >= 520:
                assert max(left, right, ring_gap, name_gap) - min(left, right, ring_gap, name_gap) <= 2
            assert all(panel.rect().contains(row.mapTo(panel, row.rect().bottomRight())) for row in rows)
    finally:
        panel.close()
        panel.deleteLater()


@pytest.mark.parametrize('attribute', ['passengers', 'departures'])
def test_home_structure_draws_values_in_all_three_views(page, qt_application, attribute):
    page.set_session(session())
    page.set_snapshot(snapshot())
    panel = getattr(page, attribute)
    qt_application.processEvents()
    assert panel.ring.center_total.isVisible()
    rows = panel.visible_mode_rows()
    assert all(row.number.isVisible() and row.share.isVisible() for row in rows)
    assert rows[0].share.text() == ('20.3%' if attribute == 'passengers' else '21.9%')
    panel.show_ranking()
    assert all(row.number.isVisible() for row in panel.visible_ranking_rows())
    assert panel.visible_ranking_rows()[0].number.text() == ('100 人次' if attribute == 'passengers' else '20 班')
    panel.show_line_share()
    assert panel.share_ring.center_total.isVisible()
    assert all(row.number.isVisible() and row.share.isVisible() for row in panel.visible_share_rows())
    first = panel.visible_share_rows()[0]
    assert first.number.text() == ('100 人次' if attribute == 'passengers' else '20 班')
    assert first.share.text() == ('10.4%' if attribute == 'passengers' else '12.9%')
    panel.show_structure()
    qt_application.processEvents()
    assert panel.ring.center_total.isVisible()
    assert all(row.number.isVisible() and row.share.isVisible() for row in panel.visible_mode_rows())


def test_long_ring_totals_use_existing_total_field_and_ranking_hides_it(page, qt_application):
    from latest_info_model import ModeCount
    from latest_info_charts import shown
    data = snapshot()
    value = Decimal('123456789012345678901234567')
    line = replace(data.lines[0], passengers=value)
    data = replace(data, lines=(line,), passenger_top10=(line,), passenger_modes=(ModeCount('公交', value),))
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    panel = page.passengers
    assert panel.ring.center_total.isHidden()
    assert panel.total_label.isVisible() and panel.total_label.text() == f'{shown(value)} 人次'
    panel.show_ranking()
    assert panel.total_label.isHidden()
    panel.show_line_share()
    assert panel.share_ring.center_total.isHidden()
    assert panel.total_label.isVisible() and panel.total_label.text() == f'{shown(value)} 人次'


def test_distribution_missing_count_stays_missing_and_zero_is_hidden(page, qt_application):
    from latest_info_model import ModeCount
    data = replace(snapshot(), departure_modes=(ModeCount('公交', None), ModeCount('地铁', 0)), total_departures=None)
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    panel = page.departures
    rows = panel.visible_mode_rows()
    assert len(rows) == 1
    missing = rows[0]
    assert missing.number.isVisible() and missing.number.text() == '— 班'
    assert missing.share.isVisible() and missing.share.text() == '—'
    assert panel._counts[1].value == 0
    assert panel.ring.sectors() == []


@pytest.mark.parametrize('offset', [0, .35, .75])
def test_tooltip_paints_only_light_border_without_black_shadow(qt_application, offset):
    from chart_canvas import ChartCanvas
    canvas = ChartCanvas()
    rows = [(QColor('#1677FF'), '蓝领', '135,820 人次', '')]
    layout = canvas._tooltip_layout('2013-05-16 周四', rows)
    width, height = layout[:2]
    image = QImage(400, 300, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    box = QRectF(10, 10 + offset, width, height)
    canvas._draw_tooltip(painter, box, layout)
    painter.end()
    # A centered 1px antialiased pen can cover the first fractional boundary
    # pixel. Beyond that fringe, the former 2px black shadow must be absent.
    assert image.pixelColor(int(box.center().x()), ceil(box.bottom()) + 1).alpha() == 0
    canvas.deleteLater()


def test_overflow_tip_round_corners_are_transparent_and_short_long_short_reuses_surface(qt_application):
    from chart_canvas import ChartCanvas
    canvas = ChartCanvas()
    canvas.setMinimumHeight(0)
    canvas.resize(400, 40)
    canvas.show()
    image = QImage(400, 300, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    rows = [(QColor('#1677FF'), '蓝领', '135,820 人次', '')]
    sizes, identities = [], []
    class Events(QObject):
        def __init__(self):
            super().__init__()
            self.shows = self.hides = 0
        def eventFilter(self, watched, event):
            self.shows += event.type() == QEvent.Type.Show
            self.hides += event.type() == QEvent.Type.Hide
            return False
    events = Events()
    for content in (rows, rows * 6, rows):
        painter = QPainter(image)
        canvas._paint_tooltip(painter, '2013-05-16 周四', content)
        painter.end()
        qt_application.processEvents()
        tip = canvas._overflow_tip
        tip.installEventFilter(events)
        assert tip.isVisible()
        sizes.append((tip.width(), tip.height()))
        identities.append(id(tip))
        grabbed = tip.grab().toImage()
        assert grabbed.pixelColor(0, 0).alpha() == 0
        assert grabbed.pixelColor(grabbed.width() // 2, grabbed.height() // 2).alpha() == 255
    assert len(set(identities)) == 1
    assert sizes[0] == sizes[2] and sizes[1][1] > sizes[0][1]
    assert events.shows == events.hides == 0  # no hide/show between contents
    canvas.hide()
    assert not canvas._overflow_tip.isVisible()
    canvas.deleteLater()
