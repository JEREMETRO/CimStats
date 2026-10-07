"""Content-centred progress for the existing parse worker."""
from PySide6.QtCore import Qt, QEvent, QPoint, QRect, Signal, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget
from qfluentwidgets import ProgressRing, PushButton
import stats_motion
from stats_elevation import _InputTransparentDecoration
from stats_tokens import PAGE_BG
from shiboken6 import isValid
from startup_readiness import FirstFrameGate


class _BackgroundCache(stats_motion._RevealEffect):
    """Use the shared live Qt source cache without fading the destination."""
    _metadata_events = frozenset((QEvent.Type.EnabledChange, QEvent.Type.FontChange,
                                 QEvent.Type.PaletteChange, QEvent.Type.StyleChange,
                                 QEvent.Type.LayoutRequest, QEvent.Type.Resize,
                                 QEvent.Type.Move, QEvent.Type.Show, QEvent.Type.Hide))

    def __init__(self, source, fade):
        self.fade = fade
        self.source_widget = source
        super().__init__(source)
        self.setOpacity(1.)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, watched, event):
        # Seed a changed source once rather than first drawing it uncached and
        # recapturing it on the next tick. Hidden pages cannot change this image.
        source = self.source_widget
        kind = event.type()
        if (kind in self._metadata_events and isinstance(watched, QWidget)
                and isValid(source) and (watched is source or source.isAncestorOf(watched))
                and (kind == QEvent.Type.Hide or watched.isVisibleTo(source))):
            self.invalidate()
        if watched is source:
            return super().eventFilter(watched, event)
        return False

    def sourceChanged(self, flags):
        super().sourceChanged(flags)
        if isValid(self.fade) and not self.fade._disposing:
            self.fade.update()


class _CoverFade(_InputTransparentDecoration):
    """Blend the previous cover into the live destination without delaying it."""
    frame_painted = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.animation = None
        self.snapshot = None
        self.opacity = 0.
        self._source = parent
        self._background_cache = None
        self._disposing = False
        self._first_frame_gate = None
        parent.installEventFilter(self)
        parent.destroyed.connect(self.finish)
        self.hide()

    def eventFilter(self, watched, event):
        if (watched in (self.parentWidget(), self._source)
                and event.type() in (QEvent.Type.Resize, QEvent.Type.Hide, QEvent.Type.ParentChange)):
            self.finish()
        return False

    def begin(self, snapshot):
        self.finish()
        if (not isValid(self._source) or not stats_motion.animations_enabled()
                or not self._source.isVisible()):
            return
        self.snapshot = snapshot
        self.opacity = 1.
        self.setGeometry(self.parentWidget().rect())
        source = self._source
        if not source.isWindow() and source.graphicsEffect() is None:
            # The loading cover owns this entry. Finish descendant entry fades
            # before caching; their final content remains in the live source.
            for motion in source.findChildren(stats_motion.SurfaceMotion):
                if motion.running:
                    motion.finish()
            self._background_cache = _BackgroundCache(source, self)
            source.setGraphicsEffect(self._background_cache)
            # An opaque sibling can reuse the live background cache without
            # asking Qt to repaint every covered control on every blend tick.
            # Keeping the cover inside source would capture itself recursively.
            host = source.window()
            self.setParent(host)
            host.installEventFilter(self)
            self.setGeometry(QRect(source.mapTo(host, QPoint()), source.size()))
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.show()
        self.raise_()
        animation = QVariantAnimation(self)
        animation.setDuration(220)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(1.)
        animation.setEndValue(0.)
        animation.valueChanged.connect(self._advance)
        animation.finished.connect(self.finish)
        self.animation = animation
        # The complete initial composite includes any queued destination/layout
        # updates. Its necessary render must precede the animation clock.
        self._first_frame_gate = FirstFrameGate(self.window(), self._start_animation, surface=self)
        self._first_frame_gate.setParent(self)
        self.update()

    def _start_animation(self):
        gate, self._first_frame_gate = self._first_frame_gate, None
        if gate is not None:
            gate.deleteLater()
        if self.animation is not None and self.isVisible():
            self.animation.start()

    def _advance(self, value):
        self.opacity = float(value)
        self.update()

    def paintEvent(self, event):
        if self.snapshot is not None:
            painter = QPainter(self)
            if not painter.isActive():
                return
            if self._background_cache is not None:
                # grab enters the shared effect's drawSource path: Qt reuses
                # cached pixels for static content and invalidates them on live
                # updates. No application-owned frozen destination is retained.
                background = self._source.grab()
                painter.drawPixmap(self.rect(), background, background.rect())
            painter.setOpacity(self.opacity)
            painter.drawPixmap(self.rect(), self.snapshot, self.snapshot.rect())
            painter.end()
            if event.region().contains(self.rect()):
                self.frame_painted.emit()

    def finish(self):
        self._disposing = True
        if self._first_frame_gate is not None:
            self._first_frame_gate.cancel()
            self._first_frame_gate.deleteLater()
            self._first_frame_gate = None
        if self.animation is not None:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None
        self.hide()
        self.snapshot = None
        self.opacity = 0.
        if isValid(self._source):
            if (self._background_cache is not None
                    and self._source.graphicsEffect() is self._background_cache):
                self._source.setGraphicsEffect(None)
            if self.parentWidget() is not self._source:
                self.setParent(self._source)
        self._background_cache = None
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self._disposing = False


class LoadingOverlay(QFrame):
    def __init__(self, parent, cancel, *, prepare_destination=None):
        super().__init__(parent)
        self.prepare_destination = prepare_destination
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setObjectName('loadingOverlay')
        self.setStyleSheet(f'QFrame#loadingOverlay {{background: {PAGE_BG};}}')
        root = QVBoxLayout(self); root.addStretch()
        row = QHBoxLayout(); row.addStretch()
        card = QWidget(self); card.setMinimumWidth(520); box = QVBoxLayout(card); box.setSpacing(12)
        self.ring = ProgressRing(card); self.ring.setRange(0,100)
        self.ring.setValue(0)
        self.ring.setFixedSize(64,64); box.addWidget(self.ring,0,Qt.AlignmentFlag.AlignHCenter)
        self.read = QLabel('',card); self.read.setWordWrap(True); self.read.setMaximumWidth(480)
        self.read.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._estimated = False
        self.percent = QLabel('阶段进度：0%',card); self.percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.read); box.addWidget(self.percent)
        self.cancel_button = PushButton('取消读取',card); self.cancel_button.clicked.connect(cancel)
        box.addWidget(self.cancel_button,0,Qt.AlignmentFlag.AlignHCenter)
        row.addWidget(card); row.addStretch(); root.addLayout(row); root.addStretch()
        parent.installEventFilter(self); self.hide()
        self.transition = _CoverFade(parent)

    def paintEvent(self, event):
        # WA_OpaquePaintEvent promises that we fill every pixel ourselves; Qt
        # can otherwise skip the stylesheet background during a direct grab.
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(PAGE_BG))
        painter.end()
        super().paintEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return super().eventFilter(watched,event)

    def begin(self, stage):
        self.transition.finish()
        snapshot = (self.parentWidget().grab() if stats_motion.animations_enabled()
                    and self.parentWidget().isVisible() else None)
        self.cancel_button.setEnabled(True)
        self.update_progress(stage, 0, estimated=False)
        self.setGeometry(self.parentWidget().rect()); self.show(); self.raise_()
        if snapshot is not None:
            self.transition.begin(snapshot)

    def update_progress(self, stage, percent=None, *, estimated=None):
        self.read.setText(f'当前阶段：{stage}')
        # Stage/log updates preserve the last estimate, including cancellation
        # and chart preparation. Only begin resets the new task to zero.
        value = self.ring.value() if percent is None else percent
        value = min(99, max(0, int(value)))
        self.ring.setValue(value)
        if percent is not None and estimated is not None:
            self._estimated = estimated
        prefix = '预计进度' if self._estimated else '阶段进度'
        self.percent.setText(f'{prefix}：{value}%')

    def finish(self):
        self.transition.finish()
        closing = getattr(self.window(), '_closing_app', False)
        if self.isVisible() and not closing and self.prepare_destination is not None:
            self.prepare_destination()
        # This cover paints the entire source rectangle. Capturing only it
        # avoids rendering every control underneath merely to cover it again.
        snapshot = (self.grab() if self.isVisible() and stats_motion.animations_enabled()
                    and not closing else None)
        self.hide()
        if snapshot is not None:
            self.transition.begin(snapshot)

    def raise_transition(self):
        if self.transition.isVisible():
            self.transition.raise_()
