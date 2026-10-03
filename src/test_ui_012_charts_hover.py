"""0.1.2 chart owner regressions: the two home distributions and hover edges."""
from dataclasses import replace
from decimal import Decimal
import pytest
from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from test_latest_info_page import page, snapshot, session


@pytest.mark.parametrize('attribute', ['passengers', 'departures'])
def test_home_structure_draws_count_and_existing_share_only_in_distribution(page, qt_application, attribute):
    page.set_session(session())
    page.set_snapshot(snapshot())
    panel = getattr(page, attribute)
    qt_application.processEvents()
    assert panel.ring.center_total.isVisible()
    rows = panel.visible_mode_rows()
    assert all(row.number.isVisible() and row.share.isVisible() for row in rows)
    assert rows[0].share.text() == ('20.3%' if attribute == 'passengers' else '21.9%')
    panel.show_ranking()
    assert all(row.number.isHidden() for row in panel.visible_ranking_rows())
    panel.show_line_share()
    assert panel.share_ring.center_total.isHidden()
    assert all(row.number.isHidden() and row.share.isHidden() for row in panel.visible_share_rows())
    panel.show_structure()
    qt_application.processEvents()
    assert panel.ring.center_total.isVisible()
    assert all(row.number.isVisible() and row.share.isVisible() for row in panel.visible_mode_rows())


def test_long_structure_total_uses_existing_total_field_and_other_views_hide_it(page, qt_application):
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
    for view in ('ranking', 'line_share'):
        getattr(panel, 'show_' + view)()
        assert panel.total_label.isHidden()


def test_distribution_missing_count_stays_missing_and_zero_stays_visible(page, qt_application):
    from latest_info_model import ModeCount
    data = replace(snapshot(), departure_modes=(ModeCount('公交', None), ModeCount('地铁', 0)), total_departures=None)
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    panel = page.departures
    missing, zero = panel.visible_mode_rows()
    assert missing.number.isVisible() and missing.number.text() == '— 班'
    assert zero.number.isVisible() and zero.number.text() == '0 班'
    assert all(row.share.isVisible() and row.share.text() == '—' for row in (missing, zero))
    assert panel.ring.sectors() == []


def test_tooltip_paints_only_light_border_without_black_shadow(qt_application):
    from chart_canvas import ChartCanvas
    canvas = ChartCanvas()
    rows = [(QColor('#1677FF'), '蓝领', '135,820 人次', '')]
    layout = canvas._tooltip_layout('2013-05-16 周四', rows)
    width, height = layout[:2]
    image = QImage(400, 300, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    box = QRectF(10, 10, width, height)
    canvas._draw_tooltip(painter, box, layout)
    painter.end()
    # No dark strip outside the shared thin light border.
    assert image.pixelColor(int(box.center().x()), int(box.bottom()) + 1).alpha() == 0
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
