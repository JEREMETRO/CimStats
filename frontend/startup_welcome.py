"""Full central-window welcome continuing its initial logo cover."""
from PySide6.QtCore import QEvent, QEasingCurve, Qt, Signal, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, PrimaryPushButton

from app_metadata import APP_NAME, icon_svg_path
import stats_motion
import stats_tokens as tokens
from stats_typography import apply_emphasis_font, emphasis_css
from startup_surface import StartupSurface


class StartupWelcome(StartupSurface):
    open_requested = Signal()

    def __init__(self, parent):
        super().__init__(icon_svg_path(), parent)
        self.setObjectName('startupWelcome')
        self.setAccessibleName('打开存档')
        self.animation = None
        self.reveal_progress = 0.
        self._started = False
        self.drag_active = False
        self.content = QWidget(self)
        column = QVBoxLayout(self.content)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)
        self.title = QLabel(APP_NAME, self.content)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(emphasis_css(28) + f'color: {tokens.TEXT_PRIMARY}; background: transparent;')
        apply_emphasis_font(self.title, 28)
        column.addWidget(self.title)
        self.open_button = PrimaryPushButton('打开存档', self.content)
        self.open_button.setIcon(FluentIcon.FOLDER)
        self.open_button.setFixedSize(180, 44)
        self.open_button.clicked.connect(self.open_requested.emit)
        column.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.hint = QLabel('或将 .save 文件拖到窗口中', self.content)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet(f'color: {tokens.TEXT_SECONDARY}; font-size: 14px; background: transparent;')
        column.addWidget(self.hint)
        self.note = QLabel('', self.content)
        self.note.setStyleSheet(f'color: {tokens.ERROR_COLOR}; font-size: 13px; background: transparent;')
        self.note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note.setWordWrap(True)
        self.note.hide()
        column.addWidget(self.note)
        self.effect = QGraphicsOpacityEffect(self.content)
        self.effect.setOpacity(0.)
        self.content.setGraphicsEffect(self.effect)
        parent.installEventFilter(self)
        self.setGeometry(parent.rect())
        self._place_content()
        self.hide()

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.setGeometry(watched.rect())
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'content'):
            self._place_content()

    def begin_transition(self):
        if self._started:
            return
        self._started = True
        if not stats_motion.animations_enabled() or not self.isVisible():
            self.finish_transition()
            return
        animation = QVariantAnimation(self)
        animation.setDuration(333)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(self.reveal_progress)
        animation.setEndValue(1.)
        animation.valueChanged.connect(self._advance)
        animation.finished.connect(self.finish_transition)
        self.animation = animation
        animation.start()

    def _advance(self, progress):
        self.reveal_progress = float(progress)
        if self.effect is not None:
            self.effect.setOpacity(self.reveal_progress)
        self._place_content()
        self.update()

    def _place_content(self):
        width = max(0, min(560, self.width() - 48))
        self.content.setFixedWidth(width)
        height = self.content.sizeHint().height()
        # Center the final mark + prompt group as a single composition.
        offset = (height + 24) / 2
        self.logo_offset = offset * self.reveal_progress
        final_bottom = self.rect().center().y() - offset + 48
        self.content.setGeometry((self.width() - width) // 2,
                                 round(final_bottom + 24 + 16 * (1 - self.reveal_progress)), width, height)

    def finish_transition(self):
        self._started = True
        if self.animation is not None:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None
        self._advance(1.)
        if self.effect is not None:
            self.content.setGraphicsEffect(None)
            self.effect = None

    def hideEvent(self, event):
        # A hidden/replaced welcome must never retain animation or an effect.
        if self._started:
            self.finish_transition()
        super().hideEvent(event)

    def set_drag_active(self, active):
        self.drag_active = bool(active)
        self.update()

    def set_note(self, text):
        # Failure copy is concise even for a very long backend exception.
        full = str(text)
        shown = self.note.fontMetrics().elidedText(full, Qt.TextElideMode.ElideRight,
                                                   max(0, self.content.width() - 24))
        self.note.setText(shown)
        self.note.setToolTip(full if shown != full else '')
        self.note.setAccessibleName(full)
        self.note.setVisible(bool(text))
        self._place_content()
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.drag_active:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(tokens.ACCENT), 2, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(self.rect().adjusted(20, 20, -20, -20), 16, 16)
