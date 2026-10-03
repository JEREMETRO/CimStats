"""Fluent scrolling keeps mouse, precision touchpad, touch, and keyboard paths usable."""
import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScroller, QSpinBox, QVBoxLayout, QWidget
from qfluentwidgets.components.widgets.scroll_bar import SmoothScrollBar

from stats_controls import StatisticsScrollArea


def test_statistics_scroll_area_uses_fluent_overlay_and_shared_touch_policy():
    app = QApplication.instance() or QApplication([])
    scroll = StatisticsScrollArea()
    content = QWidget()
    content.setMinimumSize(240, 800)
    scroll.setWidget(content)
    scroll.resize(320, 220)
    scroll.show()
    app.processEvents()
    assert scroll.verticalScrollBar().maximum() > 0
    assert isinstance(scroll.scrollDelagate.vScrollBar, SmoothScrollBar)
    assert scroll.scrollDelagate.vScrollBar.isVisible()
    assert not scroll.verticalScrollBar().isVisible()
    assert hasattr(app, '_cimstats_touch_input')
    assert scroll.viewport().testAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
    QScroller.scroller(scroll.viewport()).scrollTo(QPointF(0, 100), 0)
    app.processEvents()
    assert scroll.verticalScrollBar().value() == 100
    scroll.close()


def test_statistics_scroll_area_handles_direction_keys_and_precision_wheel():
    app = QApplication.instance() or QApplication([])
    scroll = StatisticsScrollArea()
    content = QWidget()
    content.setMinimumSize(240, 800)
    scroll.setWidget(content)
    scroll.resize(320, 220)
    scroll.show()
    app.processEvents()
    bar = scroll.verticalScrollBar()
    scroll.setFocus()
    QTest.keyClick(scroll, Qt.Key.Key_Down)
    assert bar.value() > 0
    QTest.keyClick(scroll, Qt.Key.Key_PageDown)
    assert bar.value() > 100
    QTest.keyClick(scroll, Qt.Key.Key_Home)
    assert bar.value() == 0
    wheel = QWheelEvent(QPointF(100, 100), QPointF(100, 100), QPoint(0, -60),
                        QPoint(), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.ScrollUpdate, False)
    QApplication.sendEvent(scroll.viewport(), wheel)
    assert bar.value() == 60
    mouse_wheel = QWheelEvent(QPointF(100, 100), QPointF(100, 100), QPoint(),
                               QPoint(0, -120), Qt.MouseButton.NoButton,
                               Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase,
                               False)
    QApplication.sendEvent(scroll.viewport(), mouse_wheel)
    QTest.qWait(250)
    assert bar.value() > 60
    scroll.close()


def test_direction_key_on_focused_child_keeps_its_own_action():
    app = QApplication.instance() or QApplication([])
    scroll = StatisticsScrollArea()
    content = QWidget()
    layout = QVBoxLayout(content)
    spin = QSpinBox(content)
    spin.setValue(10)
    layout.addWidget(spin)
    content.setMinimumSize(240, 800)
    scroll.setWidget(content)
    scroll.resize(320, 220)
    scroll.show()
    app.processEvents()
    spin.setFocus()
    QTest.keyClick(spin, Qt.Key.Key_Down)
    assert spin.value() == 9
    assert scroll.verticalScrollBar().value() == 0
    scroll.close()
