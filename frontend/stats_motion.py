"""Interruptible Fluent surface motion, respecting Windows client animations."""
import os
from PySide6.QtCore import QObject, QEvent, QEasingCurve, QVariantAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect
from shiboken6 import isValid


class _RevealEffect(QGraphicsOpacityEffect):
    offset = 0

    def draw(self, painter):
        painter.save()
        painter.translate(0, self.offset)
        super().draw(painter)
        painter.restore()


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

    def reveal(self, float_in=False):
        widget = self.widget
        effect = widget.graphicsEffect()
        # A foreign effect belongs to another controller. Never clear or replace it.
        if effect is not None and effect is not self.effect:
            return
        start = effect.opacity() if effect is not None else .78
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
        self.float_in = bool(float_in)
        effect.setOpacity(start)
        animation = QVariantAnimation(self)
        animation.setDuration(220 if float_in else 160)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(start)
        animation.setEndValue(1.)
        animation.valueChanged.connect(lambda value: self.advance(effect, float(value)))
        animation.finished.connect(self.finish)
        self.animation = animation
        self.running = True
        animation.start()

    def advance(self, effect, value):
        if not isValid(effect) or self.widget.graphicsEffect() is not effect:
            self.finish()
            return
        effect.setOpacity(value)
        effect.offset = round((1 - value) * 28) if self.float_in else 0
        effect.update()
        from stats_elevation import refresh_elevation
        refresh_elevation(self.widget)

    def finish(self):
        self.running = False
        if self.effect is not None and isValid(self.widget) and self.widget.graphicsEffect() is self.effect:
            self.widget.setGraphicsEffect(None)
        self.effect = None
        if self.animation is not None:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None


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

    def set_collapsed(self, collapsed):
        start = self.widget.maximumHeight() if self.animation else self.widget.height()
        if self.animation:
            self.animation.stop()
            self.animation.deleteLater()
        self.collapsed = bool(collapsed)
        if not animations_enabled() or not self.widget.parentWidget().isVisible():
            self.finish()
            return
        self.widget.show()
        if self.surface is not None:
            self.surface_start = self.surface.height()
            self.widget.setMaximumHeight(16777215)
            natural_height = self.surface.layout().sizeHint().height()
            content_height = self.widget.sizeHint().height()
            self.surface_end = (natural_height - content_height - self.surface.layout().spacing()
                                if collapsed else natural_height)
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
        animation.start()

    def finish(self):
        self.widget.setVisible(not self.collapsed)
        self.widget.setMaximumHeight(16777215)
        if self.surface is not None:
            self.surface.setMinimumHeight(0)
            self.surface.setMaximumHeight(16777215)
        if self.animation:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None
        self.finished()


class _ShowMotion(QObject):
    def __init__(self, widget):
        super().__init__(widget)
        self.motion = SurfaceMotion(widget)
        widget.installEventFilter(self)

    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.Show:
            self.motion.reveal(float_in=True)
        elif event.type() == QEvent.Type.Hide:
            self.motion.finish()
        return False


def attach_surface_reveal(widget):
    if not hasattr(widget, '_show_motion'):
        widget._show_motion = _ShowMotion(widget)
    return widget._show_motion
