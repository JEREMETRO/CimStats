"""Mouse sorting must preserve typed values and the selected route identity."""
import copy
import time
import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
import desktop_app


@pytest.fixture
def window(qt_application, monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *a: QSettings(
        str(tmp_path / 'sorting.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    w = desktop_app.MainWindow()
    w.resize(960, 680)
    w.show()
    deadline = time.monotonic() + 3
    while not w._welcome_handoff_complete and time.monotonic() < deadline:
        QTest.qWait(10)
    assert w._welcome_handoff_complete
    # Controlled normalized model rows, not a substitute for real-save visual QA.
    rows = []
    for key, name, passengers, minutes, income in (
            ('ten', 'Zulu', 10, 10.004, -10),
            ('two', 'alpha', 2, 10.001, -2),
            ('zero', 'Bravo', 0, 2, 0),
            ('missing', 'Charlie', None, None, None)):
        rows.append({'key': key, '对象ID': len(rows) + 101, '公司标识': 'company',
                     '公司名称': '公司', '运输制式': '公交', '线路名称': name,
                     '今日客流': passengers, '单程时间': minutes, '每周收入': income,
                     '字段可用性': {'今日客流': passengers is not None}})
    w.data = {'lines': rows, 'companies': [{'公司标识': 'company', '公司名称': '公司'}]}
    rows[-1]['今日客流'] = 999  # unavailable raw values must not masquerade as observations
    w.map_page.set_session({'save_key': 'sorting-save'})
    w.refresh_lines()
    w._refresh_body()
    w.navigate(2)
    w.lines_page.motion.finish()
    w.lines_page.set_expanded(True, animated=False)
    QTest.qWait(30)
    yield w
    w.close()


def keys(table):
    return [table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(table.rowCount())]


def row_background_lightness(table, row):
    rect = table.visualItemRect(table.item(row, 2))
    pixel = table.viewport().grab().toImage().pixelColor(rect.left() + 8, rect.center().y())
    # The Fluent viewport is transparent; composite its neutral fill over the
    # white card as the window does rather than treating transparent black as ink.
    return pixel.lightness() * pixel.alphaF() + 255 * (1 - pixel.alphaF())


def click_header(table, column):
    header = table.horizontalHeader()
    # Logical column lookup must survive section movement and horizontal scroll.
    table.scrollToItem(table.item(0, column))
    QTest.qWait(10)
    point = QPoint(header.sectionViewportPosition(column) + header.sectionSize(column) // 2,
                   header.height() // 2)
    assert header.viewport().rect().contains(point)
    QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QTest.qWait(10)


@pytest.mark.parametrize('column, ascending', [
    (7, ['zero', 'two', 'ten', 'missing']),
    (2, ['two', 'zero', 'missing', 'ten']),
    (5, ['zero', 'two', 'ten', 'missing']),
    (10, ['ten', 'two', 'zero', 'missing']),
])
def test_mouse_header_repeatedly_sorts_typed_values(window, column, ascending):
    table = window.line_table
    originals = copy.deepcopy(window.data['lines'])
    header = table.horizontalHeader()
    header.moveSection(header.visualIndex(column), 0)
    for expected in (ascending, list(reversed(ascending)), ascending):
        click_header(table, column)
        assert header.sortIndicatorSection() == column
        assert keys(table) == expected
    assert window.data['lines'] == originals
    if column == 5:
        # Equal rendered strings still sort by their original precision.
        assert table.item(1, 5).text() == table.item(2, 5).text()
    if column == 7:
        assert table.item(0, 7).text() == '0'
        assert table.item(3, 7).text() == '—'


def test_header_sort_filter_and_refresh_keep_selected_route_and_columns(window):
    w = window
    table = w.line_table
    header = table.horizontalHeader()
    table.setColumnWidth(2, 240)
    header.moveSection(header.visualIndex(7), 0)
    row = keys(table).index('ten')
    table.scrollToItem(table.item(row, 2))
    QTest.qWait(10)
    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton,
                     pos=table.visualItemRect(table.item(row, 2)).center())
    assert w.selected_key == 'ten'
    target = w.lines_page.map_target
    assert target == (101, ('sorting-save', 1))
    order = [header.logicalIndex(i) for i in range(header.count())]
    width = header.sectionSize(2)
    for expected in (['zero', 'two', 'ten', 'missing'], ['missing', 'ten', 'two', 'zero']):
        click_header(table, 7)
        assert keys(table) == expected
        assert keys(table)[table.currentRow()] == w.selected_key == 'ten'
        assert w._selected_line['key'] == 'ten'
        assert w.lines_page.map_target == target
        # Fluent's painted selection must follow Qt's persistent selection too.
        assert row_background_lightness(table, table.currentRow()) < 242, \
            'selected route lost its Fluent highlight after sorting'
        assert row_background_lightness(table, 0) > 242, \
            'old row retained the selection highlight after sorting'
    w.query.setText('Zulu')
    assert keys(table) == ['ten']
    w.query.clear()
    w.refresh_lines()
    assert keys(table) == ['missing', 'ten', 'two', 'zero']
    assert header.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
    assert keys(table)[table.currentRow()] == w.selected_key == 'ten'
    w.lines_page._column_changed(7, False)
    w.lines_page.set_expanded(False, animated=False)
    assert not table.isColumnHidden(2)
    assert table.isColumnHidden(7)
    w.resize(1100, 680)
    w.lines_page.set_expanded(True, animated=False)
    QTest.qWait(10)
    assert [header.logicalIndex(i) for i in range(header.count())] == order
    assert header.sectionSize(2) == width
    assert w.lines_page.map_target == target
    QTest.keyClick(table, Qt.Key.Key_Down)
    assert keys(table)[table.currentRow()] == w.selected_key == 'two'
