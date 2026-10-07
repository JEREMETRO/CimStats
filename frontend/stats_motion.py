"""Interruptible Fluent surface motion, respecting Windows client animations."""
import os
from math import ceil
from PySide6.QtCore import QObject, QEvent, QEasingCurve, QPoint, QPointF, QRect, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QMouseEvent, QPixmapCache
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QWidget
from shiboken6 import getCppPointer, isValid


class _RevealEffect(QGraphicsOpacityEffect):
    offset = 0.
    _extent = 0
    _needs_source_cache = True

    def __init__(self, widget):
        super().__init__(widget)
        widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Paint, QEvent.Type.Resize):
            self.invalidate()
        return False

    def invalidate(self):
        self._needs_source_cache = True

    def sourceChanged(self, flags):
        self.invalidate()
        super().sourceChanged(flags)

    def boundingRectFor(self, rect):
        return rect.united(rect.translated(0, self._extent))

    def set_offset(self, offset):
        self.offset = offset
        extent = ceil(offset)
        if extent > self._extent:
            self._extent = extent
            self.updateBoundingRect()
        self.update()

    def draw(self, painter):
        # QWidget sourcePixmap always rerenders; drawSource reuses Qt's cache
        # and falls back to live painting when QWidget.update invalidates it.
        # A live source Paint event asks us to reseed that cache next frame.
        # Keep no application-owned frozen image that could conceal updates.
        if self._needs_source_cache:
            rect = self.sourceBoundingRect()
            scale = painter.device().devicePixelRatioF()
            budget = min(128 * 1024, max(64 * 1024, ceil(rect.width()*rect.height()*scale*scale*8/1024)+8192))
            if QPixmapCache.cacheLimit() < budget:
                QPixmapCache.setCacheLimit(budget)
            self.sourcePixmap(Qt.CoordinateSystem.LogicalCoordinates, QPoint(), self.PixmapPadMode.NoPad)
            self._needs_source_cache = False
        painter.save()
        painter.translate(0, self.offset)
        painter.setOpacity(painter.opacity() * self.opacity())
        self.drawSource(painter)
        painter.restore()


def entrance_easing():
    """Microsoft Fluent entrance: cubic-bezier(0, 0, 0, 1)."""
    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(QPointF(0, 0), QPointF(0, 1), QPointF(1, 1))
    return curve


def reposition_easing():
    """Microsoft Fluent on-screen movement: cubic-bezier(.55, .55, 0, 1)."""
    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(QPointF(.55, .55), QPointF(0, 1), QPointF(1, 1))
    return curve


def animations_enabled():
    if os.environ.get('CIM2_REDUCED_MOTION') == '1':
        return False
    if os.name == 'nt':
        import ctypes
        enabled = ctypes.c_int(1)
        if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
            return bool(enabled.value)
    return True


class SurfaceMotion(QObject):
    """One effect per surface; interrupted reveals continue from current opacity."""
    def __init__(self, widget):
        super().__init__(widget)
        self.widget = widget
        self.animation = None
        self.running = False
        self.float_in = False
        self.effect = None
        self._pointer_down = False
        self._mouse_target = None
        self._input_offset = QPointF()
        self._input_button = Qt.MouseButton.NoButton
        self._pending_touch_id = None
        self._touch_device = None
        widget.installEventFilter(self)

    def eventFilter(self, widget, event):
        if getattr(QApplication.instance(), '_surface_input_dispatch_depth', 0): return False
        if getattr(event, '_surface_mouse_relay', False): return False
        surface = getattr(self, 'widget', None)
        if (not getattr(self, 'running', False) or surface is None
                or not isValid(self) or not isValid(surface)):
            return False
        kind = event.type()
        if (isinstance(widget, QWidget) and self._mouse_target is not None
                and kind in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease)):
            self._relay_mouse(event)
            if kind == QEvent.Type.MouseButtonRelease:
                self._pointer_down = False
                self._mouse_target = None
                QTimer.singleShot(0, self, self.finish)
            return True
        if kind in (QEvent.Type.ApplicationDeactivate, QEvent.Type.WindowDeactivate):
            self.finish()
            return False
        if (isinstance(widget, QWidget) and self._pointer_down
                and kind in (QEvent.Type.TouchEnd, QEvent.Type.TouchCancel)
                and event.device() == self._touch_device):
            self._pointer_down = False
            QTimer.singleShot(0, self, self.finish)
        point = None
        if isinstance(widget, QWidget) and kind in (QEvent.Type.MouseButtonPress, QEvent.Type.TouchBegin):
            point = (event.globalPosition() if kind == QEvent.Type.MouseButtonPress else
                     event.points()[0].globalPosition() if event.points() else None)
        inside = isinstance(widget, QWidget) and (widget is surface or surface.isAncestorOf(widget))
        if inside or point is not None and self._contains_visual_input(widget, point):
            if kind in (QEvent.Type.MouseButtonPress, QEvent.Type.TouchBegin):
                if self.effect is not None and self.effect.offset > 0:
                    if point is None: return False
                    self._input_offset = QPointF(0, self.effect.offset)
                    logical = point - self._input_offset
                    target = surface.childAt(surface.mapFromGlobal(logical.toPoint())) or surface
                    # Translate input through the same visual transform; hold
                    # it still until release so the pressed control cannot move.
                    self._pointer_down = True
                    self.animation.pause()
                    if kind == QEvent.Type.MouseButtonPress:
                        self._input_button = event.button()
                        self._mouse_target = target
                        self._relay_mouse(event)
                        return True
                    # Borrowed QEvent Python wrappers can differ between app
                    # filters. Hand off by the underlying event's identity.
                    self._pending_touch_id = getCppPointer(event)[0]
                    self._touch_device = event.device()
                    QApplication.instance()._surface_touch_transform = (
                        self._pending_touch_id, target, QPointF(self._input_offset))
                else:
                    self.finish()
            elif kind in (QEvent.Type.MouseButtonRelease, QEvent.Type.TouchEnd, QEvent.Type.TouchCancel) and self._pointer_down:
                self._pointer_down = False
                QTimer.singleShot(0, self, self.finish)
            elif kind in (QEvent.Type.KeyPress, QEvent.Type.Wheel):
                self.finish()
            elif kind in (QEvent.Type.Resize, QEvent.Type.LayoutRequest,
                          QEvent.Type.StyleChange, QEvent.Type.FontChange,
                          QEvent.Type.DynamicPropertyChange):
                if self.effect is not None: self.effect.invalidate()
            elif kind == QEvent.Type.Hide and widget is self.widget:
                self.finish()
        return False

    def _contains_visual_input(self, receiver, point):
        surface = self.widget
        if self.effect is None or QWidget.window(receiver) is not QWidget.window(surface): return False
        rect = QRectF(surface.rect().translated(surface.mapToGlobal(QPoint()))).translated(0, self.effect.offset)
        if not rect.contains(point): return False
        ancestor = surface.parentWidget()
        while ancestor is not None:
            if not ancestor.rect().translated(ancestor.mapToGlobal(QPoint())).contains(point.toPoint()): return False
            ancestor = None if ancestor.isWindow() else ancestor.parentWidget()
        hit = QApplication.widgetAt(point.toPoint()) or receiver
        if hit is surface or surface.isAncestorOf(hit) or hit.isAncestorOf(surface): return True
        ancestors = set()
        node = hit
        while node is not None:
            ancestors.add(node); node = node.parentWidget()
        branch = surface
        while branch.parentWidget() is not None and branch.parentWidget() not in ancestors:
            branch = branch.parentWidget()
        common = branch.parentWidget()
        if common is None: return False
        hit_branch = hit
        while hit_branch.parentWidget() is not common:
            hit_branch = hit_branch.parentWidget()
        siblings = [child for child in common.children() if isinstance(child, QWidget)]
        return siblings.index(branch) > siblings.index(hit_branch)

    def _relay_mouse(self, event):
        target = self._mouse_target
        if target is None or not isValid(target):
            self.finish()
            return
        point = event.globalPosition() - self._input_offset
        local = QPointF(target.mapFromGlobal(point.toPoint()))
        scene = QPointF(QWidget.window(target).mapFromGlobal(point.toPoint()))
        mapped = QMouseEvent(event.type(), local, scene, point, event.button(), event.buttons(),
                             event.modifiers(), event.pointingDevice())
        mapped._surface_mouse_relay = True
        send_surface_input(target, mapped)

    def reveal(self, float_in=False):
        widget = self.widget
        effect = widget.graphicsEffect()
        # A foreign effect belongs to another controller. Never clear or replace it.
        if effect is not None and effect is not self.effect:
            return
        # Qt widget effects must not nest: a child reveal is already included in
        # its parent's transition. Show events arrive child-first, so an incoming
        # parent also settles any earlier child reveals before taking ownership.
        ancestor = None if widget.isWindow() else widget.parentWidget()
        while ancestor is not None:
            if ancestor.graphicsEffect() is not None:
                self.finish()
                return
            ancestor = None if ancestor.isWindow() else ancestor.parentWidget()
        for motion in widget.findChildren(SurfaceMotion):
            if motion is not self and motion.widget.window() is widget.window():
                motion.finish()
        if any(child.graphicsEffect() is not None and child.window() is widget.window()
               for child in widget.findChildren(QWidget)):
            self.finish()
            return
        start = effect.opacity() if effect is not None else .78
        # Capture both channels before an interruption. Opacity is not a clock:
        # a mode fade can interrupt a float while it still has a visible offset.
        start_offset = effect.offset if effect is not None else (28. if float_in else 0.)
        if self.animation is not None:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None
        if not animations_enabled() or not widget.isVisible():
            self.finish()
            return
        if effect is None:
            effect = _RevealEffect(widget)
            widget.setGraphicsEffect(effect)
            self.effect = effect
        effect.invalidate()
        self.float_in = bool(float_in)
        animation = QVariantAnimation(self)
        animation.setDuration(250 if float_in else 167)
        animation.setEasingCurve(entrance_easing() if float_in else QEasingCurve.Type.Linear)
        animation.setStartValue(0.)
        animation.setEndValue(1.)
        def advance(progress):
            progress = float(progress)
            self.advance(effect, start + (1 - start) * progress,
                         start_offset * (1 - progress))
        animation.valueChanged.connect(advance)
        animation.finished.connect(self.finish)
        self.animation = animation
        self.running = True
        QApplication.instance().installEventFilter(self)
        # QVariantAnimation.start() need not emit its unchanged initial value.
        # Apply the complete first frame now, before any paint can see offset 0.
        advance(0.)
        animation.start()

    def advance(self, effect, value, offset):
        if not isValid(effect) or self.widget.graphicsEffect() is not effect:
            self.finish()
            return
        effect.setOpacity(value)
        effect.set_offset(offset)
        from stats_elevation import refresh_elevation
        refresh_elevation(self.widget)

    def finish(self):
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
            pending = getattr(app, '_surface_touch_transform', None)
            if pending is not None and pending[0] == self._pending_touch_id:
                app._surface_touch_transform = None
        self._pending_touch_id = None
        self.running = False
        self._pointer_down = False
        self._touch_device = None
        target = self._mouse_target
        self._mouse_target = None
        if target is not None and isValid(target):
            # Cancel an interrupted press without activating the control.
            local = QPointF(-100, -100)
            cancelled = QMouseEvent(QEvent.Type.MouseButtonRelease, local, local,
                                   QPointF(target.mapToGlobal(QPoint(-100, -100))),
                                   self._input_button, Qt.MouseButton.NoButton,
                                   Qt.KeyboardModifier.NoModifier)
            cancelled._surface_mouse_relay = True
            send_surface_input(target, cancelled)
        if self.effect is not None and isValid(self.widget) and self.widget.graphicsEffect() is self.effect:
            self.widget.setGraphicsEffect(None)
        self.effect = None
        if self.animation is not None:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None


def settle_surface_motion(widget):
    """New query data must become live before an entrance snapshot is discarded."""
    while widget is not None:
        for motion in widget.findChildren(SurfaceMotion, options=Qt.FindChildOption.FindDirectChildrenOnly):
            if motion.running: motion.finish()
        widget = None if widget.isWindow() else widget.parentWidget()


def take_surface_touch_transform(event):
    """Consume the current TouchBegin's visual-coordinate handoff once."""
    app = QApplication.instance()
    pending = getattr(app, '_surface_touch_transform', None)
    if pending is not None and pending[0] == getCppPointer(event)[0]:
        app._surface_touch_transform = None
        return pending[1], pending[2]
    return None, QPointF()


def send_surface_input(target, event):
    """Prevent re-entry when Qt propagates a mapped event to a parent."""
    app = QApplication.instance()
    depth = getattr(app, '_surface_input_dispatch_depth', 0)
    app._surface_input_dispatch_depth = depth + 1
    try:
        return QApplication.sendEvent(target, event)
    finally:
        app._surface_input_dispatch_depth = depth


class CollapseMotion(QObject):
    def __init__(self, widget, finished, surface=None):
        super().__init__(widget)
        self.widget, self.finished = widget, finished
        self.animation = None
        self.collapsed = False
        self.surface = surface
        self.surface_start = 0
        self.surface_end = 0
        self.on_progress = None
        self._frozen_layout = None
        self._frozen_surface_layout = None
        if widget.parentWidget() is not None:
            widget.parentWidget().installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Hide and getattr(self, 'animation', None) is not None:
            self.finish()
        return False

    def set_collapsed(self, collapsed):
        start = (self.widget.maximumHeight() if self.animation else
                 (0 if self.widget.isHidden() else self.widget.height()))
        if self.animation:
            self.animation.stop()
            self.animation.deleteLater()
        self.collapsed = bool(collapsed)
        parent = self.widget.parentWidget() or self.widget
        if not animations_enabled() or not parent.isVisible():
            self.finish()
            return
        # Keep natural row geometry while the host clips it. Letting a grid
        # relayout at every shrinking height makes fixed-height KPI rows overlap.
        layout = self.widget.layout()
        if self._frozen_layout is None and layout is not None and layout.isEnabled():
            if self.widget.isHidden():
                layout.setGeometry(QRect(0, 0, self.widget.width(), self.widget.sizeHint().height()))
            layout.setEnabled(False)
            self._frozen_layout = layout
        if self.surface is not None:
            self.surface_start = self.surface.height()
        self.widget.show()
        if self.surface is not None:
            self.widget.setMaximumHeight(16777215)
            natural_height = self.surface.layout().sizeHint().height()
            content_height = self.widget.sizeHint().height()
            self.surface_end = (natural_height - content_height - self.surface.layout().spacing()
                                if collapsed else natural_height)
            outer = self.surface.layout()
            if self._frozen_surface_layout is None and outer.isEnabled():
                if start == 0:
                    outer.setGeometry(QRect(0, 0, self.surface.width(), natural_height))
                outer.setEnabled(False)
                self._frozen_surface_layout = outer
        end = 0 if collapsed else self.widget.sizeHint().height()
        self.widget.setMaximumHeight(start)
        animation = QVariantAnimation(self)
        animation.setDuration(167 if collapsed else 250)
        animation.setEasingCurve(QEasingCurve.Type.InCubic if collapsed else QEasingCurve.Type.OutCubic)
        animation.setStartValue(start)
        animation.setEndValue(end)
        def advance(value):
            self.widget.setMaximumHeight(round(value))
            if self.surface is not None:
                progress = 1. if start == end else (float(value)-start)/(end-start)
                self.surface.setFixedHeight(round(self.surface_start +
                    (self.surface_end-self.surface_start)*progress))
            if self.on_progress:
                self.on_progress()
        animation.valueChanged.connect(advance)
        animation.finished.connect(self.finish)
        self.animation = animation
        # Showing a previously hidden row invalidates the parent's layout.
        # Constrain both hosts before that layout can paint the full height.
        advance(start)
        animation.start()

    def finish(self):
        self.widget.setVisible(not self.collapsed)
        self.widget.setMaximumHeight(16777215)
        if self._frozen_layout is not None:
            self._frozen_layout.setEnabled(True)
            self._frozen_layout.invalidate()
            self._frozen_layout = None
        if self._frozen_surface_layout is not None:
            self._frozen_surface_layout.setEnabled(True)
            self._frozen_surface_layout.invalidate()
            self._frozen_surface_layout = None
        if self.surface is not None:
            self.surface.setMinimumHeight(0)
            self.surface.setMaximumHeight(16777215)
        if self.animation:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None
        self.finished()


class _ShowMotion(QObject):
    def __init__(self, widget, motion=None):
        super().__init__(widget)
        self.motion = motion or SurfaceMotion(widget)
        self._shown = False
        widget.installEventFilter(self)

    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.Show:
            if not self._shown:
                self._shown = True
                self.motion.reveal(float_in=True)
        elif event.type() == QEvent.Type.Hide:
            self.motion.finish()
        return False


def attach_surface_reveal(widget, motion=None):
    if not hasattr(widget, '_show_motion'):
        widget._show_motion = _ShowMotion(widget, motion)
    return widget._show_motion
