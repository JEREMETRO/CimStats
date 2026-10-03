"""Content-centred progress for the existing parse worker."""
from PySide6.QtCore import Qt, QEvent, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget
from qfluentwidgets import ProgressRing, PushButton
import stats_motion
from stats_tokens import PAGE_BG


class _CoverFade(QWidget):
    """Blend the previous cover into the live destination without delaying it."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.animation = None
        self.snapshot = None
        self.opacity = 0.
        parent.installEventFilter(self)
        self.hide()

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() in (QEvent.Type.Resize, QEvent.Type.Hide):
            self.finish()
        return False

    def begin(self, snapshot):
        self.finish()
        if not stats_motion.animations_enabled() or not self.parentWidget().isVisible():
            return
        self.snapshot = snapshot
        self.opacity = 1.
        self.setGeometry(self.parentWidget().rect())
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
        animation.start()

    def _advance(self, value):
        self.opacity = float(value)
        self.update()

    def paintEvent(self, event):
        if self.snapshot is not None:
            painter = QPainter(self)
            painter.setOpacity(self.opacity)
            painter.drawPixmap(self.rect(), self.snapshot, self.snapshot.rect())

    def finish(self):
        if self.animation is not None:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None
        self.hide()
        self.snapshot = None
        self.opacity = 0.


class LoadingOverlay(QFrame):
    def __init__(self, parent, cancel):
        super().__init__(parent)
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
        snapshot = (self.parentWidget().grab() if self.isVisible() and stats_motion.animations_enabled()
                    and not getattr(self.window(), '_closing_app', False) else None)
        self.hide()
        if snapshot is not None:
            self.transition.begin(snapshot)

    def raise_transition(self):
        if self.transition.isVisible():
            self.transition.raise_()
