"""One touchscreen owner: delayed taps, descendant scrolling and context holds.

Accepting TouchBegin prevents Qt from also synthesizing an early mouse press.
Text editors keep press/drag selection; menus/sliders keep Qt's input path. Mouse, wheel and
keyboard events are never intercepted. New widgets join on Polish, independent
of page layout or when a dialog/menu is constructed.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QTimer, Qt
from PySide6.QtGui import QContextMenuEvent, QInputDevice, QMouseEvent
from PySide6.QtWidgets import (QAbstractItemView, QAbstractScrollArea, QAbstractSlider, QAbstractSpinBox,
                              QApplication, QComboBox, QLineEdit, QMenu, QTextEdit,
                              QPlainTextEdit, QWidget)
from shiboken6 import isValid


def _alive(widget):
    return widget is not None and isValid(widget)


def _ancestors(widget):
    while _alive(widget):
        yield widget
        widget = widget.parentWidget()


def _native(widget):
    from qfluentwidgets import ScrollBar
    return any(isinstance(parent, (QLineEdit, QAbstractSpinBox, QComboBox,
                                   QAbstractSlider, QTextEdit, QPlainTextEdit, QMenu, ScrollBar))
               or parent.property('nativeTouchInput')
               for parent in _ancestors(widget))


def _editor(widget):
    parents = tuple(_ancestors(widget))
    if any(isinstance(parent, QMenu) or parent.property('nativeTouchInput') for parent in parents):
        return None
    return next((parent for parent in parents
                 if isinstance(parent, (QLineEdit, QTextEdit, QPlainTextEdit))), None)


class TouchInputPolicy(QObject):
    def __init__(self, app):
        super().__init__(app)
        self._target = None
        self._device = None
        self._chart = self._scroll = self._inspector = None
        self._editing = self._mouse_down = False
        self._mode = 'idle'
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._hold)
        app.installEventFilter(self)
        for widget in app.allWidgets():
            self._enable(widget)

    @staticmethod
    def _enable(widget):
        transparent = any(parent.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                          for parent in _ancestors(widget))
        widget.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, not transparent)

    def _reset(self):
        self._timer.stop()
        if _alive(self._target):
            self._target.destroyed.disconnect(self._target_destroyed)
        if self._mouse_down and _alive(self._target):
            # An interrupted edit/press receives a release outside its bounds,
            # avoiding a click while clearing the control's pressed state.
            self._mouse(QEvent.Type.MouseButtonRelease,
                        QPointF(self._target.mapToGlobal(QPoint(-100, -100))),
                        Qt.MouseButton.LeftButton)
        if _alive(self._chart):
            self._chart.touch_cancel()
        if _alive(self._inspector):
            self._inspector.touch_inspect_end()
        self._target = self._device = self._chart = self._scroll = self._inspector = None
        self._mode = 'idle'
        self._editing = self._mouse_down = False

    def _target_destroyed(self):
        self._reset()

    def _cancel_pending(self):
        self._timer.stop()
        self._mode = 'cancelled'
        if self._mouse_down and _alive(self._target):
            self._mouse(QEvent.Type.MouseButtonRelease,
                        QPointF(self._target.mapToGlobal(QPoint(-100, -100))),
                        Qt.MouseButton.LeftButton)
        if _alive(self._chart):
            self._chart.touch_cancel(clear_inspection=True)
        if _alive(self._inspector):
            self._inspector.touch_inspect_end()

    def _mouse(self, kind, global_point, button=Qt.MouseButton.NoButton):
        target = self._target
        if not _alive(target):
            return
        local = QPointF(target.mapFromGlobal(global_point.toPoint()))
        if kind == QEvent.Type.MouseButtonPress:
            self._mouse_down = True
        elif kind == QEvent.Type.MouseButtonRelease:
            self._mouse_down = False
        buttons = Qt.MouseButton.LeftButton if self._mouse_down else Qt.MouseButton.NoButton
        event = QMouseEvent(kind, local, local, global_point, button, buttons,
                            Qt.KeyboardModifier.NoModifier,
                            Qt.MouseEventSource.MouseEventSynthesizedByApplication)
        QApplication.sendEvent(target, event)

    def _inspect(self, point):
        self._mouse(QEvent.Type.MouseMove, point)
        if _alive(self._inspector):
            self._inspector.touch_inspect(point)

    def _scroll_by(self, delta):
        """Convert logical pixels for item views whose bars count rows/columns."""
        self._scroll_remainder += delta
        scroll = self._scroll
        for vertical in (True, False):
            bar = scroll.verticalScrollBar() if vertical else scroll.horizontalScrollBar()
            unit = 1
            if isinstance(scroll, QAbstractItemView):
                mode = scroll.verticalScrollMode() if vertical else scroll.horizontalScrollMode()
                if mode == QAbstractItemView.ScrollMode.ScrollPerItem:
                    viewport = scroll.viewport()
                    point = QPoint(1, viewport.height() // 2) if vertical else QPoint(viewport.width() // 2, 1)
                    index = scroll.indexAt(point)
                    if not index.isValid():
                        index = scroll.model().index(0, 0, scroll.rootIndex())
                    rect = scroll.visualRect(index)
                    unit = max(1, rect.height() if vertical else rect.width())
            amount = self._scroll_remainder.y() if vertical else self._scroll_remainder.x()
            steps = int(amount / unit)
            bar.setValue(bar.value() - steps)
            if vertical:
                self._scroll_remainder.setY(amount - steps * unit)
            else:
                self._scroll_remainder.setX(amount - steps * unit)

    def _hold(self):
        if self._mode != 'pending' or not _alive(self._target):
            return
        self._mode = 'held'
        target = self._target
        point = self._last.toPoint()
        if self._mouse_down:
            self._mouse(QEvent.Type.MouseButtonRelease, self._last, Qt.MouseButton.LeftButton)
        if not _alive(target):
            return
        # QWidget propagates ignored context events to its parents, just as
        # physical right-click does. No new menu or context action is invented.
        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse,
                                  target.mapFromGlobal(point), point)
        QApplication.sendEvent(target, event)

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.Type.Polish and isinstance(watched, QWidget):
            self._enable(watched)
        if kind in (QEvent.Type.ApplicationDeactivate, QEvent.Type.WindowDeactivate):
            if self._mode != 'idle':
                self._cancel_pending()
                self._reset()
        if kind == QEvent.Type.Hide and self._mode != 'idle':
            if watched in _ancestors(self._target):
                self._cancel_pending()
                self._reset()
        if kind not in (QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate,
                        QEvent.Type.TouchEnd, QEvent.Type.TouchCancel):
            return False
        if not isinstance(watched, QWidget) or event.device().type() != QInputDevice.DeviceType.TouchScreen:
            return False
        if kind == QEvent.Type.TouchBegin:
            points = event.points()
            if not points:
                return False
            point = points[0].globalPosition()
            # Check the hit widget as well as receiver: ignored native touches
            # can propagate to a passive parent before Qt synthesizes its mouse.
            hit = QApplication.widgetAt(point.toPoint())
            if any(parent.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                   for parent in _ancestors(watched)):
                return False
            editing = _editor(hit or watched) is not None
            if not editing and (_native(watched) or _native(hit)):
                return False
            if self._mode != 'idle':
                self._reset()
            self._target, self._device = watched, event.device()
            watched.destroyed.connect(self._target_destroyed)
            self._editing = editing
            self._start = self._last = QPointF(point)
            self._scroll_remainder = QPointF()
            self._point_id = points[0].id()
            self._scroll = next((parent for parent in _ancestors(watched)
                                 if isinstance(parent, QAbstractScrollArea)), None)
            self._chart = next((parent for parent in _ancestors(watched)
                                if callable(getattr(parent, 'touch_pan', None))), None)
            self._inspector = next((parent for parent in _ancestors(watched)
                                    if callable(getattr(parent, 'touch_inspect', None))), None)
            self._mode = 'pending' if len(points) == 1 else 'cancelled'
            if self._mode == 'pending':
                self._inspect(point)
                if self._editing:
                    self._mouse(QEvent.Type.MouseButtonPress, point, Qt.MouseButton.LeftButton)
                self._timer.start(QApplication.styleHints().mousePressAndHoldInterval())
        elif event.device() != self._device:
            return False
        elif kind == QEvent.Type.TouchCancel:
            self._cancel_pending()
            self._reset()
        else:
            points = event.points()
            if len(points) != 1 or points[0].id() != self._point_id or not _alive(self._target):
                self._cancel_pending()
            elif self._mode not in ('cancelled', 'held'):
                point = QPointF(points[0].globalPosition())
                distance = point - self._start
                if self._mode == 'pending' and distance.manhattanLength() >= QApplication.startDragDistance():
                    self._timer.stop()
                    horizontal = abs(distance.x()) > abs(distance.y())
                    self._mode = ('editing' if self._editing else
                                  'chart-pan' if horizontal and _alive(self._chart)
                                  and self._chart.touch_pan(self._start, point)
                                  else 'scroll-pan')
                    if self._mode == 'scroll-pan' and _alive(self._chart):
                        self._chart.touch_cancel(clear_inspection=True)
                if self._mode == 'editing' or self._editing and self._mode == 'pending':
                    self._mouse(QEvent.Type.MouseMove, point)
                elif self._mode == 'chart-pan':
                    self._chart.touch_pan(self._start, point)
                elif self._mode == 'scroll-pan' and _alive(self._scroll):
                    delta = point - self._last
                    self._scroll_by(delta)
                elif self._mode == 'pending':
                    self._inspect(point)
                self._last = point
            if kind == QEvent.Type.TouchEnd:
                self._timer.stop()
                if self._editing and self._mode in ('pending', 'editing'):
                    self._mouse(QEvent.Type.MouseButtonRelease, self._last, Qt.MouseButton.LeftButton)
                elif self._mode == 'pending' and _alive(self._target):
                    self._inspect(self._last)
                    self._mouse(QEvent.Type.MouseButtonPress, self._last, Qt.MouseButton.LeftButton)
                    self._mouse(QEvent.Type.MouseButtonRelease, self._last, Qt.MouseButton.LeftButton)
                self._reset()
        event.accept()
        return True


def install_touch_input(app=None):
    """Idempotent app-wide policy; theme initialization owns installation."""
    app = app or QApplication.instance()
    if app is not None and not hasattr(app, '_cimstats_touch_input'):
        policy = TouchInputPolicy(app)
        app._cimstats_touch_input = policy
    return getattr(app, '_cimstats_touch_input', None)
