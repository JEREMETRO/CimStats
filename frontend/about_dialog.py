"""Compact Fluent about action; no page-stack or selected-route changes."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, QRect, QPoint, QEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QDialog, QWidget, QLabel, QVBoxLayout,
                               QHBoxLayout, QPlainTextEdit, QScrollArea, QFrame)
from qfluentwidgets import PushButton, MessageBoxBase
from shiboken6 import isValid

from app_metadata import (application_metadata, project_license_path,
                          third_party_notices_path)
from stats_typography import apply_emphasis_font
from stats_motion import SurfaceMotion, animations_enabled
from stats_tokens import TEXT_PRIMARY, TEXT_SECONDARY
from stats_dialogs import FluentMessageBox
from window_chrome import clear_secondary_window_icon


class _CompactDialog(MessageBoxBase):
    """Reuse project motion policy and Fluent mask, shadow, button and Esc path."""
    preferred_width = 480

    def __init__(self, parent):
        super().__init__(parent)
        clear_secondary_window_icon(self)
        self.motion = SurfaceMotion(self)
        self._closing_surface = False
        self._return_focus = None
        self.yesButton.setText('关闭')
        self.yesButton.setFixedWidth(104)
        self.hideCancelButton()
        self.buttonGroup.setFixedHeight(64)
        self.buttonLayout.setContentsMargins(24, 14, 24, 14)
        self.setModal(True)
        parent.installEventFilter(self)
        self.finished.connect(self._restore_focus)

    def _fit_surface(self):
        parent = self.parentWidget()
        visible = QRect(parent.mapToGlobal(QPoint(0, 0)), parent.size())
        screen = parent.screen()
        if screen is not None:
            visible = visible.intersected(screen.availableGeometry())
        if visible.isEmpty():
            visible = QRect(parent.mapToGlobal(QPoint(0, 0)), parent.size())
        if not self.isWindow():
            visible.moveTopLeft(parent.mapFromGlobal(visible.topLeft()))
        self.setGeometry(visible)
        self.widget.setFixedWidth(min(self.preferred_width, max(1, self.width() - 32)))
        if hasattr(self, 'content'):
            layout = self.content.layout()
            width = max(1, self.widget.width() - 48)
            height = layout.totalHeightForWidth(width)
            if height < 0:
                height = layout.sizeHint().height()
            height = max(height, layout.minimumSize().height())
            natural = height + 48 + self.buttonGroup.height() + 2 * self.widget.frameWidth()
        else:
            natural = 520
        margins = self._hBoxLayout.contentsMargins()
        available_height = self.height() - margins.top() - margins.bottom()
        self.widget.setFixedHeight(min(natural, max(1, available_height)))

    def showEvent(self, event):
        self._closing_surface = False
        self._fit_surface()
        QDialog.showEvent(self, event)
        self.motion.reveal()
        self.yesButton.setFocus(Qt.FocusReason.PopupFocusReason)

    def done(self, code):
        if self._closing_surface:
            return
        self._closing_surface = True
        self.motion.finish()
        if animations_enabled():
            super().done(code)
        else:
            QDialog.done(self, code)

    def eventFilter(self, watched, event):
        if (watched is self.parentWidget() and self.isVisible() and
                event.type() in (QEvent.Type.Resize, QEvent.Type.Move)):
            self._fit_surface()
        return super().eventFilter(watched, event)

    def _restore_focus(self, _code):
        target = self._return_focus
        if target is not None and isValid(target) and target.isVisible() and target.isEnabled():
            target.setFocus(Qt.FocusReason.PopupFocusReason)


class LicenseTextDialog(_CompactDialog):
    preferred_width = 680

    def __init__(self, title: str, path: Path, parent):
        text = path.read_text(encoding='utf-8-sig')
        super().__init__(parent)
        heading = QLabel(title, self)
        apply_emphasis_font(heading, 20)
        self.viewLayout.addWidget(heading)
        self.document = QPlainTextEdit(self)
        self.document.setReadOnly(True)
        self.document.setMinimumSize(0, 0)
        self.document.setPlainText(text)
        self.viewLayout.addWidget(self.document, 1)


class AboutDialog(_CompactDialog):
    def __init__(self, parent, *, root: Path | None = None):
        super().__init__(parent)
        self.setObjectName('aboutDialog')
        self.metadata = application_metadata(root)
        self._document_dialog = None
        self.scroll = QScrollArea(self.widget)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setMinimumSize(0, 0)
        self.scroll.setStyleSheet('QScrollArea { background: transparent; border: 0; }')
        self.content = QWidget(self.scroll)
        self.content.setObjectName('aboutContent')
        self.content.setStyleSheet('QWidget#aboutContent { background: transparent; }')
        self.scroll.setWidget(self.content)
        self.viewLayout.addWidget(self.scroll)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        identity = QHBoxLayout()
        identity.setSpacing(16)
        lines = QVBoxLayout()
        lines.setSpacing(3)
        name = QLabel(self.metadata.name, self.content)
        name.setStyleSheet(f'color: {TEXT_PRIMARY};')
        apply_emphasis_font(name, 23)
        lines.addWidget(name)
        for text in (f'版本 {self.metadata.version}', f'作者 {self.metadata.author}'):
            label = QLabel(text, self.content)
            label.setStyleSheet(f'color: {TEXT_SECONDARY};')
            apply_emphasis_font(label, 14, QFont.Weight.Normal)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lines.addWidget(label)
        identity.addLayout(lines, 1)
        layout.addLayout(identity)
        license_title = QLabel('开源协议', self.content)
        apply_emphasis_font(license_title, 16)
        layout.addWidget(license_title)
        for text in (self.metadata.license_name,):
            label = QLabel(text, self.content)
            label.setWordWrap(True)
            label.setStyleSheet(f'color: {TEXT_SECONDARY};')
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(label)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.license_button = PushButton('查看协议', self.content)
        self.notices_button = PushButton('第三方声明', self.content)
        self.license_button.clicked.connect(
            lambda: self._open_document('开源协议', project_license_path(root), self.license_button))
        self.notices_button.clicked.connect(
            lambda: self._open_document('第三方声明', third_party_notices_path(root), self.notices_button))
        actions.addWidget(self.license_button)
        actions.addWidget(self.notices_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)

    def _open_document(self, title: str, path: Path, return_focus):
        current = self._document_dialog
        if current is not None and isValid(current) and current.isVisible():
            current.raise_()
            return
        try:
            dialog = LicenseTextDialog(title, path, self)
        except (OSError, UnicodeError):
            FluentMessageBox.warning(self, '无法打开文档', '本地协议文件不可用。')
            return
        self._document_dialog = dialog
        dialog._return_focus = return_focus
        dialog.finished.connect(lambda _code: dialog.deleteLater())
        dialog.open()


def show_about_dialog(window, *, root: Path | None = None):
    """One reusable modal instance per parent; selected page and route untouched."""
    dialog = getattr(window, '_cimstats_about_dialog', None)
    if dialog is not None and isValid(dialog) and dialog.isVisible():
        dialog.raise_()
        dialog.yesButton.setFocus(Qt.FocusReason.PopupFocusReason)
        return dialog
    previous_focus = QApplication.focusWidget()
    if dialog is None or not isValid(dialog):
        dialog = AboutDialog(window, root=root)
        window._cimstats_about_dialog = dialog
    dialog._return_focus = previous_focus
    dialog.open()
    return dialog
