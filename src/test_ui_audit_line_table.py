"""Actual header/cell text edge and column interaction checks for UI-01."""
from types import SimpleNamespace
import pytest
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QFont, QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTableWidgetItem
from line_query_page import LinesPage
from line_schedule_view import SchedulePanel
from stats_style import initialize_theme
from stats_typography import ui_font


@pytest.fixture
def page(qt_application):
    initialize_theme(qt_application)
    owner = SimpleNamespace(refresh_lines=lambda *a: None, line_clicked=lambda *a: None,
                            line_selection_changed=lambda *a: None)
    widget = LinesPage(owner, SchedulePanel)
    widget.resize(1700, 680)
    widget.set_expanded(True, animated=False)
    table = widget.line_table
    table.setSortingEnabled(False)
    table.setRowCount(2)
    font = ui_font(14)
    for column in range(table.columnCount()):
        table.horizontalHeaderItem(column).setText('123')
        table.horizontalHeaderItem(column).setFont(font)
        for row, text in enumerate(('123', '321')):
            cell = QTableWidgetItem(text)
            cell.setFont(font)
            cell.setForeground(QColor('#18314f'))
            table.setItem(row, column, cell)
    table.horizontalHeader().setFont(font)
    table.horizontalHeader().setStyleSheet(table.horizontalHeader().styleSheet().replace('font-size:12px', 'font-size:14px'))
    table.setSortingEnabled(True)
    table.sortItems(7, Qt.SortOrder.AscendingOrder)
    widget.show()
    QTest.qWait(30)
    yield widget
    widget.close()
    widget.deleteLater()


def text_edges(image, rect):
    # Only dark glyph ink; the pale section border and alternate background
    # are excluded. Header and cell use the same glyphs/font for this probe.
    xs = [x for x in range(rect.left(), rect.right() + 1)
          for y in range(rect.top() + 5, rect.bottom() - 5)
          if image.pixelColor(x, y).lightness() < 220
          and image.pixelColor(x, y).blue() - image.pixelColor(x, y).red() > 8]
    assert xs, 'text was not actually painted'
    return min(xs), max(xs)


@pytest.mark.parametrize('column', [2, 7, 12, 13])
@pytest.mark.parametrize('sorted_column', [7, 12, 13])
def test_painted_header_and_cell_share_text_anchor(page, column, sorted_column):
    table = page.line_table
    header = table.horizontalHeader()
    header.setSortIndicator(sorted_column, Qt.SortOrder.AscendingOrder)
    # Move the sorted column away from the final visual position too.
    header.moveSection(header.visualIndex(13), 1)
    table.setColumnHidden(12, column != 12)
    QTest.qWait(20)
    cell = table.visualRect(table.model().index(0, column))
    head = QRect(header.sectionViewportPosition(column), 0, header.sectionSize(column), header.height())
    cell_edges = text_edges(table.viewport().grab().toImage(), cell)
    head_edges = text_edges(header.viewport().grab().toImage(), head)
    anchor = 0 if column == 2 else 1
    assert abs(head_edges[anchor] - cell_edges[anchor]) <= 1


def test_width_sort_and_visual_order_survive_expand_hide_and_resize(page):
    table = page.line_table
    header = table.horizontalHeader()
    table.setColumnWidth(13, 180)
    table.setColumnWidth(2, 210)
    header.moveSection(header.visualIndex(13), 0)
    table.sortItems(13, Qt.SortOrder.DescendingOrder)
    widths = (header.sectionSize(2), header.sectionSize(13))
    order = [header.logicalIndex(i) for i in range(header.count())]
    page._column_changed(13, True)
    page.set_expanded(False, animated=False)
    page.resize(1800, 700)
    page.set_expanded(True, animated=False)
    QTest.qWait(20)
    assert not header.stretchLastSection()
    assert (header.sectionSize(2), header.sectionSize(13)) == widths
    assert [header.logicalIndex(i) for i in range(header.count())] == order
    assert header.sortIndicatorSection() == 13
    assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    assert table.item(0, 13).text() == '321'
    header.resizeSection(13, 190)
    assert table.columnWidth(13) == 190


def test_full_cell_contents_determine_width_even_when_headers_are_elided(page):
    from PySide6.QtGui import QFontMetrics
    from PySide6.QtWidgets import QStyleOptionViewItem
    from line_query_page import TABLE_TEXT_PADDING
    table=page.line_table
    samples={0:'八连交通集团',1:'无轨电车',2:'812E 秋山市南站—山顶公园',
             7:'123,456,789',10:'123,456,789.00',13:'123,456.78'}
    for column,text in samples.items():
        table.item(0,column).setText(text)
    QTest.qWait(30)
    for column,text in samples.items():
        index=table.model().index(0,column)
        option=QStyleOptionViewItem()
        table.delegate.initStyleOption(option,index)
        # Include both Fluent padding and QStyledItemDelegate's text margins.
        required=QFontMetrics(option.font).horizontalAdvance(text)+2*(TABLE_TEXT_PADDING+3)
        assert table.columnWidth(column)>=required, f'{text} will be elided'
        table.horizontalHeader().resizeSection(column,42)
        QTest.qWait(20)
        assert table.columnWidth(column)>=required, 'resizing must retain complete values'


@pytest.mark.parametrize('text', ['15.74', '31,299.57', '无轨电车', '有轨电车1号线', '水上巴士1号线'])
def test_minimum_content_width_paints_complete_glyphs_without_ellipsis(page,text):
    from PySide6.QtGui import QImage,QPainter,QColor
    table=page.line_table
    column=2 if '号线' in text else 1 if text=='无轨电车' else 3
    for row in range(table.rowCount()):
        table.item(row,column).setText(text)
        if column==2:
            font=table.item(row,column).font();font.setWeight(QFont.Weight.Medium)
            table.item(row,column).setFont(font)
    QTest.qWait(30)
    table.horizontalHeader().resizeSection(column,42)
    QTest.qWait(30)
    cell=table.visualRect(table.model().index(0,column))
    painted=text_edges(table.viewport().grab().toImage(),cell)
    image=QImage(240,30,QImage.Format.Format_RGB32)
    image.fill(QColor('white'))
    painter=QPainter(image);painter.setFont(table.item(0,column).font())
    painter.setPen(QColor('#18314f'))
    painter.drawText(image.rect(),Qt.AlignmentFlag.AlignCenter,text);painter.end()
    expected=text_edges(image,image.rect())
    assert painted[1]-painted[0]>=expected[1]-expected[0]-1,'cell was elided despite its measured width'


def test_elided_header_exposes_complete_caption_in_hover_tooltip(page):
    from PySide6.QtCore import QEvent,QPoint,QCoreApplication
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QToolTip
    from line_query_page import HEADERS
    header=page.line_table.horizontalHeader()
    header.moveSection(header.visualIndex(13),0)
    QTest.qWait(20)
    point=QPoint(header.sectionViewportPosition(13)+header.sectionSize(13)//2,header.height()//2)
    event=QHelpEvent(QEvent.Type.ToolTip,point,header.viewport().mapToGlobal(point))
    QCoreApplication.sendEvent(header.viewport(),event)
    QTest.qWait(20)
    assert QToolTip.text()==HEADERS[13]
    QToolTip.hideText()


def test_collapsing_from_last_columns_returns_to_line_identity(page):
    page.resize(1000,680)
    QTest.qWait(20)
    scroll=page.line_table.horizontalScrollBar()
    scroll.setValue(scroll.maximum())
    assert scroll.value()>0
    page.set_expanded(False,animated=False)
    QTest.qWait(20)
    assert scroll.value()==0, 'expanded tail-column offset hides compact line names'


def test_reduced_motion_finishes_line_list_and_schedule_changes(page,monkeypatch):
    from PySide6.QtCore import QAbstractAnimation
    monkeypatch.setattr('line_query_page.animations_enabled',lambda:False)
    monkeypatch.setattr('stats_motion.animations_enabled',lambda:False)
    page.set_expanded(False)
    page.set_schedule_expanded(True)
    QTest.qWait(20)
    assert page._animation.state()==QAbstractAnimation.State.Stopped
    assert page.detail_motion.animation is None
    assert page.schedule_panel.graphicsEffect() is None
    assert page.schedule_panel.expanded and not page.detail.isVisible()
    page.set_expanded(True)
    page.set_schedule_expanded(False)
    QTest.qWait(20)
    assert page.detail.isVisible() and not page.schedule_panel.expanded
    assert page.detail_motion.animation is None
    assert page._animation.state()==QAbstractAnimation.State.Stopped
