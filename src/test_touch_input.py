"""Touchscreen device delivery must distinguish tap, pan, hold and cancellation."""
import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QColor, QInputDevice, QTouchEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QLabel, QLineEdit, QPushButton, QSlider,
                              QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from chart_canvas import ChartCanvas, ChartData, Series
from stats_controls import StatisticsScrollArea
from stats_style import initialize_theme


@pytest.fixture
def touch():
    app = QApplication.instance() or QApplication([])
    initialize_theme(app)
    device = QTest.createTouchDevice(QInputDevice.DeviceType.TouchScreen)
    yield app, device
    app.processEvents()


def sequence(widget, device):
    return QTest.touchEvent(widget, device, False)


def test_touch_bar_inspection_selects_one_stack_and_cancel_clears_it(touch):
    app, device = touch
    chart = ChartCanvas(); chart.resize(400, 190)
    chart.set_data(ChartData('bar', ['x'], [
        Series('bus', '本期 · 公交', QColor('blue'), [10], stack='current'),
        Series('tram', '本期 · 电车', QColor('orange'), [5], stack='current'),
        Series('previous', '环比 · 公交', QColor('blue'), [20], stack='previous')]))
    chart.show(); app.processEvents(); chart.grab()
    stacks, width, gap, total = chart._stack_layout()
    clicks = []; chart.slot_clicked.connect(clicks.append)
    try:
        for position, stack in enumerate(stacks):
            point = QPoint(round(chart._slot_center(0) - total / 2 + position * (width + gap) + width / 2),
                           round(chart._y(3)))
            events = sequence(chart, device)
            events.press(0, point, chart).commit(); chart.grab()
            assert chart._hover == 0 and chart._hover_stack == stack
            assert len(chart._tooltip_rows(0, chart._hover_stack)) == (2 if position == 0 else 1)
            QApplication.sendEvent(chart, QTouchEvent(QEvent.Type.TouchCancel, device))
            events.release(0, point, chart).commit()
            assert chart._hover is None and chart._hover_stack is None
        assert clicks == []
    finally:
        chart.close()


def test_swipe_starting_on_child_scrolls_without_activation(touch):
    app, device = touch
    scroll = StatisticsScrollArea()
    host = QWidget()
    host.setMinimumSize(260, 1000)
    layout = QVBoxLayout(host)
    button = QPushButton('action')
    layout.addWidget(button)
    layout.addStretch()
    scroll.setWidget(host)
    scroll.resize(320, 240)
    scroll.show()
    app.processEvents()
    clicked = []
    button.clicked.connect(lambda: clicked.append(True))
    point = button.rect().center()
    events = sequence(button, device)
    events.press(0, point, button).commit()
    events.move(0, point - QPoint(0, 90), button).commit()
    events.release(0, point - QPoint(0, 90), button).commit()
    assert scroll.verticalScrollBar().value() >= 60
    assert clicked == []
    scroll.close()


def test_touch_chart_inspects_same_slot_and_tap_activates_once(touch):
    app, device = touch
    chart = ChartCanvas()
    chart.resize(400, 190)
    chart.set_data(ChartData('line', ['Mon', 'Tue'], [Series('a', 'A', QColor('blue'), [12, 34])], unit='人'))
    chart.show()
    app.processEvents()
    point = chart.plot_rect().center().toPoint()
    seen = []
    chart.slot_clicked.connect(seen.append)
    events = sequence(chart, device)
    events.press(0, point, chart).commit()
    assert chart._hover == 1
    assert chart._tooltip_rows(1)[0][2] == '34 人'
    assert seen == []
    events.release(0, point, chart).commit()
    assert seen == [1]
    chart.close()


def test_touch_hold_delivers_existing_context_once_without_click(touch):
    app, device = touch
    button = QPushButton('context')
    button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    button.resize(160, 80)
    button.show()
    app.processEvents()
    clicked, contexts = [], []
    button.clicked.connect(lambda: clicked.append(True))
    button.customContextMenuRequested.connect(contexts.append)
    events = sequence(button, device)
    point = button.rect().center()
    events.press(0, point, button).commit()
    QTest.qWait(QApplication.styleHints().mousePressAndHoldInterval() + 80)
    events.release(0, point, button).commit()
    assert len(contexts) == 1
    assert clicked == []
    button.close()


def test_plain_descendant_pan_and_tap_on_parent_card(touch):
    app, device = touch

    class Card(QWidget):
        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                activated.append(True)
                event.accept()

    activated = []
    scroll = StatisticsScrollArea()
    host = QWidget()
    host.setMinimumSize(260, 1000)
    card = Card(host)
    card.setGeometry(10, 10, 220, 180)
    label = QLabel('child surface', card)
    label.setGeometry(0, 0, 220, 180)
    scroll.setWidget(host)
    scroll.resize(320, 240)
    scroll.show()
    app.processEvents()
    viewport = scroll.viewport()
    point = label.mapTo(viewport, QPoint(100, 150))
    events = sequence(viewport, device)
    events.press(0, point, viewport).commit()
    assert activated == []
    events.move(0, point - QPoint(0, 80), viewport).commit()
    events.release(0, point - QPoint(0, 80), viewport).commit()
    assert scroll.verticalScrollBar().value() == 80
    assert activated == []
    scroll.verticalScrollBar().setValue(0)
    events.press(0, point, viewport).commit()
    events.release(0, point, viewport).commit()
    assert activated == [True]
    scroll.close()


def test_table_touch_scroll_then_single_row_tap(touch):
    app, device = touch
    table = QTableWidget(80, 1)
    for row in range(80):
        table.setItem(row, 0, QTableWidgetItem(str(row)))
    table.resize(320, 240)
    table.show()
    app.processEvents()
    clicked = []
    table.cellClicked.connect(lambda row, column: clicked.append(row))
    view = table.viewport()
    point = QPoint(40, 150)
    events = sequence(view, device)
    events.press(0, point, view).commit()
    events.move(0, QPoint(40, 50), view).commit()
    events.release(0, QPoint(40, 50), view).commit()
    assert 1 <= table.verticalScrollBar().value() <= 5
    assert clicked == []
    row = table.indexAt(QPoint(40, 50)).row()
    events.press(0, QPoint(40, 50), view).commit()
    events.release(0, QPoint(40, 50), view).commit()
    assert clicked == [row]
    table.close()


def test_native_edit_slider_and_menu_tap_keep_existing_input(touch):
    from qfluentwidgets import ComboBox
    app, device = touch
    host = QWidget()
    layout = QVBoxLayout(host)
    edit = QLineEdit('original')
    slider = QSlider(Qt.Orientation.Horizontal)
    combo = ComboBox()
    combo.addItems(['first', 'second'])
    for widget in (edit, slider, combo):
        layout.addWidget(widget)
    host.resize(320, 220)
    host.show()
    app.processEvents()
    events = sequence(edit, device)
    point = edit.rect().center()
    events.press(0, point, edit).commit()
    events.release(0, point, edit).commit()
    assert edit.hasFocus()
    QTest.keyClicks(edit, 'X')
    assert 'X' in edit.text()
    events = sequence(slider, device)
    point = QPoint(slider.width() - 20, slider.height() // 2)
    events.press(0, point, slider).commit()
    events.release(0, point, slider).commit()
    assert slider.value() > 0
    events = sequence(combo, device)
    point = combo.rect().center()
    events.press(0, point, combo).commit()
    events.release(0, point, combo).commit()
    app.processEvents()
    menu = combo.dropMenu
    assert menu is not None and menu.isVisible()
    view = menu.view
    point = view.visualItemRect(view.item(1)).center()
    events = sequence(view.viewport(), device)
    events.press(0, point, view.viewport()).commit()
    events.release(0, point, view.viewport()).commit()
    assert combo.currentIndex() == 1
    host.close()


def test_edit_hold_context_and_drag_selection_do_not_pan_parent(touch):
    app, device = touch
    scroll = StatisticsScrollArea()
    host = QWidget()
    host.setMinimumSize(260, 1000)
    edit = QLineEdit('editing remains selectable', host)
    edit.setGeometry(10, 10, 220, 40)
    edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    contexts = []
    edit.customContextMenuRequested.connect(contexts.append)
    scroll.setWidget(host)
    scroll.resize(320, 240)
    scroll.show()
    app.processEvents()
    events = sequence(edit, device)
    point = QPoint(30, 20)
    events.press(0, point, edit).commit()
    QTest.qWait(QApplication.styleHints().mousePressAndHoldInterval() + 80)
    events.release(0, point, edit).commit()
    assert len(contexts) == 1
    events.press(0, point, edit).commit()
    events.move(0, QPoint(180, 20), edit).commit()
    events.release(0, QPoint(180, 20), edit).commit()
    assert edit.selectedText()
    assert scroll.verticalScrollBar().value() == 0
    scroll.close()


def test_home_ring_touch_inspects_existing_values_without_early_drilldown(touch):
    from decimal import Decimal
    from latest_info_charts import ModeRing
    from latest_info_model import ModeCount
    from PySide6.QtWidgets import QToolTip
    app, device = touch
    ring = ModeRing()
    ring.set_data((ModeCount('bus', Decimal(10)), ModeCount('tram', Decimal(20))), Decimal(30))
    ring.show()
    app.processEvents()
    requested = []
    ring.mode_requested.connect(requested.append)
    point = QPoint(ring.width() // 2 + 4, 10)
    events = sequence(ring, device)
    events.press(0, point, ring).commit()
    assert '10' in ring.toolTip() and '33.3%' in ring.toolTip()
    assert QToolTip.isVisible()
    assert requested == []
    events.release(0, point, ring).commit()
    assert requested == ['bus']
    ring.close()


def test_zoomed_detail_horizontal_pan_does_not_emit_click(touch):
    app, device = touch
    chart = ChartCanvas(detailed=True)
    chart.resize(600, 400)
    chart.set_data(ChartData('line', list(map(str, range(40))), [Series('a', 'A', QColor('blue'), list(range(40)))]))
    chart.set_window(10, 30)
    chart.show()
    app.processEvents()
    clicks = []
    chart.slot_clicked.connect(clicks.append)
    point = chart.plot_rect().center().toPoint()
    events = sequence(chart, device)
    events.press(0, point, chart).commit()
    events.move(0, point - QPoint(100, 0), chart).commit()
    events.release(0, point - QPoint(100, 0), chart).commit()
    assert chart.window()[0] > 10
    assert clicks == []
    assert chart._drag_origin is None
    chart.close()


def test_destroyed_target_and_multitouch_leave_no_activation(touch):
    app, device = touch
    host = QWidget()
    button = QPushButton('destroy', host)
    button.setGeometry(0, 0, 180, 80)
    host.resize(220, 160)
    host.show()
    app.processEvents()
    clicks = []
    button.clicked.connect(lambda: clicks.append(True))
    events = sequence(host, device)
    events.press(0, QPoint(50, 40), host).commit()
    button.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QTest.qWait(QApplication.styleHints().mousePressAndHoldInterval() + 40)
    events.release(0, QPoint(50, 40), host).commit()
    assert clicks == []
    button = QPushButton('new', host)
    button.setGeometry(0, 0, 180, 80)
    button.show()
    app.processEvents()
    button.clicked.connect(lambda: clicks.append(True))
    events.press(0, QPoint(40, 30), host).commit()
    events.stationary(0).press(1, QPoint(60, 30), host).commit()
    events.release(0, QPoint(40, 30), host).release(1, QPoint(60, 30), host).commit()
    assert clicks == []
    events.press(0, QPoint(50, 40), host).commit()
    events.release(0, QPoint(50, 40), host).commit()
    assert clicks == [True]
    host.close()


@pytest.mark.parametrize('interruption', ['hide', 'deactivate'])
def test_pending_touch_interruption_stops_hold_and_preserves_mouse_keyboard(touch, interruption):
    app, device = touch
    host = QWidget()
    button = QPushButton('interruption', host)
    button.setGeometry(0, 0, 180, 80)
    host.resize(220, 160)
    host.show()
    app.processEvents()
    clicks, contexts = [], []
    button.clicked.connect(lambda: clicks.append(True))
    button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    button.customContextMenuRequested.connect(contexts.append)
    events = sequence(host, device)
    point = QPoint(50, 40)
    events.press(0, point, host).commit()
    if interruption == 'hide':
        host.hide()
    else:
        QApplication.sendEvent(host, QEvent(QEvent.Type.WindowDeactivate))
    QTest.qWait(QApplication.styleHints().mousePressAndHoldInterval() + 60)
    events.release(0, point, host).commit()
    assert clicks == [] and contexts == []
    assert app._cimstats_touch_input._mode == 'idle'
    host.show()
    app.processEvents()
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    QTest.keyClick(button, Qt.Key.Key_Space)
    assert clicks == [True, True]
    host.close()


def test_context_hold_on_label_reaches_existing_parent_action(touch):
    app, device = touch
    host = QWidget()
    host.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    label = QLabel('context descendant', host)
    label.setGeometry(0, 0, 200, 100)
    host.resize(240, 140)
    host.show()
    app.processEvents()
    contexts = []
    host.customContextMenuRequested.connect(contexts.append)
    point = QPoint(50, 40)
    events = sequence(label, device)
    events.press(0, point, label).commit()
    QTest.qWait(QApplication.styleHints().mousePressAndHoldInterval() + 60)
    events.release(0, point, label).commit()
    assert len(contexts) == 1
    host.close()


def test_chart_cancel_clears_inspection_and_does_not_emit_activation(touch):
    app, device = touch
    chart = ChartCanvas()
    chart.resize(400, 190)
    chart.set_data(ChartData('line', ['Mon', 'Tue'], [Series('a', 'A', QColor('blue'), [12, 34])]))
    chart.show()
    app.processEvents()
    clicks = []
    chart.slot_clicked.connect(clicks.append)
    point = chart.plot_rect().center().toPoint()
    events = sequence(chart, device)
    events.press(0, point, chart).commit()
    assert chart._hover is not None
    QApplication.sendEvent(chart, QTouchEvent(QEvent.Type.TouchCancel, device))
    events.release(0, point, chart).commit()
    assert chart._hover is None and chart._drag_origin is None
    assert clicks == []
    chart.close()


def test_touch_donut_sector_activates_only_once_at_release(touch):
    from math import cos, radians, sin
    from PySide6.QtCore import QPointF
    app, device = touch
    chart = ChartCanvas()
    chart.resize(400, 240)
    chart.set_data(ChartData('donut', ['one', 'two'], [Series(
        'share', 'share', QColor('blue'), [10, 20], keys=['a', 'b'],
        colors=[QColor('blue'), QColor('green')])]))
    chart.show()
    app.processEvents()
    part = chart._slices[1]
    angle = radians(part['start'] + part['span'] / 2)
    radius = (part['inner'] + part['outer']) / 2
    point = (part['center'] + QPointF(cos(angle) * radius, -sin(angle) * radius)).toPoint()
    clicks = []
    chart.slice_clicked.connect(clicks.append)
    events = sequence(chart, device)
    events.press(0, point, chart).commit()
    assert clicks == [] and chart._hover_slice == 'b'
    events.release(0, point, chart).commit()
    assert clicks == ['b']
    chart.close()


def test_zoomed_chart_vertical_swipe_scrolls_parent_without_activation(touch):
    app, device = touch
    scroll = StatisticsScrollArea()
    host = QWidget()
    host.setMinimumSize(300, 1000)
    chart = ChartCanvas(host, detailed=True)
    chart.setGeometry(0, 0, 300, 200)
    chart.set_data(ChartData('line', list(map(str, range(40))), [Series('a', 'A', QColor('blue'), list(range(40)))]))
    chart.set_window(10, 30)
    scroll.setWidget(host)
    scroll.resize(320, 240)
    scroll.show()
    app.processEvents()
    clicks = []
    chart.slot_clicked.connect(clicks.append)
    viewport = scroll.viewport()
    point = chart.mapTo(viewport, chart.plot_rect().center().toPoint())
    events = sequence(viewport, device)
    events.press(0, point, viewport).commit()
    events.move(0, point - QPoint(0, 70), viewport).commit()
    events.release(0, point - QPoint(0, 70), viewport).commit()
    assert scroll.verticalScrollBar().value() == 70
    assert chart.window() == (10, 30)
    assert clicks == []
    assert chart._hover is None and chart._drag_origin is None
    scroll.close()


def test_cancel_does_not_activate_or_leave_state_for_next_tap(touch):
    app, device = touch
    button = QPushButton('cancel')
    button.resize(160, 80)
    button.show()
    app.processEvents()
    clicked = []
    button.clicked.connect(lambda: clicked.append(True))
    point = button.rect().center()
    events = sequence(button, device)
    events.press(0, point, button).commit()
    QApplication.sendEvent(button, QTouchEvent(QEvent.Type.TouchCancel, device))
    events.release(0, point, button).commit()
    assert clicked == []
    assert not button.isDown()
    events.press(0, point, button).commit()
    events.release(0, point, button).commit()
    assert clicked == [True]
    button.close()
