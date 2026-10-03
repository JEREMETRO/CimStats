"""Window chrome shared by every page: header, save context and empty state."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import Action, FluentIcon, IconWidget, PrimaryPushButton, PushButton, RoundMenu

import stats_tokens as tokens
from stats_typography import apply_emphasis_font, emphasis_css

HEADER_HEIGHT = 64
PAGE_GUTTER = 24


class ElidedText(QLabel):
    """Label that elides in the middle and keeps the full text as tooltip."""

    def __init__(self, text='', parent=None, *, size=13, color=tokens.TEXT_PRIMARY, weight=400):
        super().__init__(parent)
        self._full = ''
        self.setStyleSheet(f'color: {color}; font-size: {size}px; font-weight: {weight}; '
                           f'background: transparent; border: 0;')
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setText(text)

    def setText(self, text):
        self._full = str(text or '')
        self.setToolTip(self._full)
        self.setAccessibleName(self._full)
        self._elide()

    def text(self):
        return self._full

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self):
        width = max(0, self.width())
        shown = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideMiddle, width) if width else self._full
        super().setText(shown)


class SaveChip(QFrame):
    """Compact identity of the loaded save: file name and simulated time."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('saveChip')
        self.setStyleSheet(f'QFrame#saveChip {{ background: {tokens.CARD_BG}; border: 1px solid {tokens.BORDER}; '
                           f'border-radius: 8px; }}')
        self.setFixedHeight(44)
        self.setMinimumWidth(260)
        self.setMaximumWidth(380)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 12, 4)
        row.setSpacing(8)
        self.icon = IconWidget(self)
        self.icon.setIcon(FluentIcon.DOCUMENT.icon(color=QColor(tokens.ACCENT)))
        self.icon.setFixedSize(16, 16)
        row.addWidget(self.icon)
        column = QVBoxLayout()
        column.setSpacing(0)
        column.setContentsMargins(0, 0, 0, 0)
        self.name = ElidedText('未载入存档', self, size=13, weight=600)
        self.detail = ElidedText('', self, size=12, color=tokens.TEXT_SECONDARY)
        column.addWidget(self.name)
        column.addWidget(self.detail)
        row.addLayout(column, 1)

    def set_context(self, name: str, detail: str = ''):
        self.name.setText(name)
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))


class AppHeader(QWidget):
    """One header for every page: title, page slot, save chip and actions."""

    open_requested = Signal()
    export_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('appHeader')
        self.setFixedHeight(HEADER_HEIGHT)
        row = QHBoxLayout(self)
        row.setContentsMargins(PAGE_GUTTER, 12, PAGE_GUTTER, 8)
        row.setSpacing(12)
        self.icon_base = QFrame(self)
        self.icon_base.setObjectName('pageIconBase')
        self.icon_base.setFixedSize(36, 36)
        self.icon_base.setStyleSheet(f'QFrame#pageIconBase {{ background: {tokens.ACCENT_SOFT}; border: 0; '
                                     f'border-radius: 8px; }}')
        icon_row = QHBoxLayout(self.icon_base)
        icon_row.setContentsMargins(8, 8, 8, 8)
        self.icon = IconWidget(self.icon_base)
        self.icon.setFixedSize(20, 20)
        icon_row.addWidget(self.icon)
        row.addWidget(self.icon_base)
        self.title = QLabel('', self)
        self.title.setObjectName('pageTitle')
        self.title.setStyleSheet(emphasis_css(22) + f'color: {tokens.TEXT_PRIMARY}; background: transparent;')
        apply_emphasis_font(self.title, 22)
        row.addWidget(self.title)
        self.page_slot = QHBoxLayout()
        self.page_slot.setContentsMargins(12, 0, 0, 0)
        row.addLayout(self.page_slot)
        row.addStretch(1)
        self.save_chip = SaveChip(self)
        row.addWidget(self.save_chip, 0)
        self.export_button = PushButton('导出', self)
        self.export_button.setIcon(FluentIcon.SAVE)
        self.export_button.setFixedHeight(36)
        self.export_menu = RoundMenu(parent=self.export_button)
        self.export_actions: dict[str, Action] = {}
        self.export_button.clicked.connect(self._show_export_menu)
        row.addWidget(self.export_button)
        self.open_button = PrimaryPushButton('打开存档', self)
        self.open_button.setIcon(FluentIcon.FOLDER)
        self.open_button.setFixedHeight(36)
        self.open_button.setMinimumWidth(120)
        self.open_button.clicked.connect(self.open_requested.emit)
        row.addWidget(self.open_button)
        self._page_widget = None
        self.about_to_show_exports = None

    def set_page(self, title: str, icon: FluentIcon, widget: QWidget | None = None):
        self.title.setText(title)
        self.icon.setIcon(icon.icon(color=QColor(tokens.ACCENT)))
        if self._page_widget is not None and self._page_widget is not widget:
            self.page_slot.removeWidget(self._page_widget)
            self._page_widget.hide()
        self._page_widget = widget
        if widget is not None:
            if widget.parentWidget() is not self:
                widget.setParent(self)
            self.page_slot.addWidget(widget)
            widget.show()

    def set_exports(self, items):
        """``items``: iterable of (key, text, icon, enabled). Separators: key None."""
        self.export_menu.clear()
        self.export_actions = {}
        any_enabled = False
        for key, text, icon, enabled in items:
            if key is None:
                self.export_menu.addSeparator()
                continue
            action = Action(icon, text, self.export_menu) if icon else Action(text, self.export_menu)
            action.setEnabled(bool(enabled))
            action.triggered.connect(lambda checked=False, k=key: self.export_requested.emit(k))
            self.export_menu.addAction(action)
            self.export_actions[key] = action
            any_enabled = any_enabled or bool(enabled)
        self.export_button.setEnabled(any_enabled)

    def _show_export_menu(self):
        if self.about_to_show_exports is not None:
            self.about_to_show_exports()
        self.export_menu.exec(self.export_button.mapToGlobal(QPoint(0, self.export_button.height() + 4)))


class DropZone(QWidget):
    """Dashed drop target painted directly so it scales cleanly."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setBrush(QColor(tokens.ACCENT_SOFT if self.active else tokens.CARD_BG))
        pen = QPen(QColor(tokens.ACCENT if self.active else tokens.BORDER_STRONG), 1.5, Qt.PenStyle.DashLine)
        pen.setDashPattern([6, 4])
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 16, 16)


class EmptyState(QWidget):
    """Shown on every page until a save has been parsed."""

    open_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('emptyState')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(PAGE_GUTTER, 8, PAGE_GUTTER, PAGE_GUTTER)
        self.zone = DropZone(self)
        outer.addWidget(self.zone, 1)
        column = QVBoxLayout(self.zone)
        column.setContentsMargins(32, 32, 32, 32)
        column.setSpacing(10)
        column.addStretch(3)
        badge = QFrame(self.zone)
        badge.setObjectName('emptyBadge')
        badge.setFixedSize(72, 72)
        badge.setStyleSheet(f'QFrame#emptyBadge {{ background: {tokens.ACCENT_SOFT}; border-radius: 36px; }}')
        badge_row = QHBoxLayout(badge)
        badge_row.setContentsMargins(20, 20, 20, 20)
        icon = IconWidget(badge)
        icon.setIcon(FluentIcon.FOLDER_ADD.icon(color=QColor(tokens.ACCENT)))
        badge_row.addWidget(icon)
        column.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)
        column.addSpacing(6)
        self.title = QLabel('打开一个 Cities in Motion 2 存档', self.zone)
        self.title.setStyleSheet(emphasis_css(22) + f'color: {tokens.TEXT_PRIMARY}; background: transparent;')
        apply_emphasis_font(self.title, 22)
        column.addWidget(self.title, 0, Qt.AlignmentFlag.AlignHCenter)
        self.hint = QLabel('将 .save 文件拖到这里，或点击下方按钮选择文件', self.zone)
        self.hint.setStyleSheet(f'color: {tokens.TEXT_SECONDARY}; font-size: 14px; background: transparent;')
        column.addWidget(self.hint, 0, Qt.AlignmentFlag.AlignHCenter)
        column.addSpacing(10)
        self.open_button = PrimaryPushButton('选择存档文件', self.zone)
        self.open_button.setIcon(FluentIcon.FOLDER)
        self.open_button.setFixedSize(180, 40)
        self.open_button.clicked.connect(self.open_requested.emit)
        column.addWidget(self.open_button, 0, Qt.AlignmentFlag.AlignHCenter)
        column.addSpacing(18)
        steps = QHBoxLayout()
        steps.setSpacing(28)
        steps.addStretch(1)
        for number, (head, text) in enumerate((('读取存档', '只读解析，不修改原文件'),
                                              ('浏览统计', '最新信息、线路、公司/网络/城市'),
                                              ('导出结果', 'XLSX 工作簿与 PNG 图表')), 1):
            box = QVBoxLayout()
            box.setSpacing(2)
            heading = QLabel(f'{number}  {head}', self.zone)
            heading.setStyleSheet(f'color: {tokens.TEXT_PRIMARY}; font-size: 13px; font-weight: 600; '
                                  f'background: transparent;')
            detail = QLabel(text, self.zone)
            detail.setStyleSheet(f'color: {tokens.TEXT_SECONDARY}; font-size: 12px; background: transparent;')
            box.addWidget(heading, 0, Qt.AlignmentFlag.AlignHCenter)
            box.addWidget(detail, 0, Qt.AlignmentFlag.AlignHCenter)
            steps.addLayout(box)
        steps.addStretch(1)
        column.addLayout(steps)
        column.addStretch(4)
        self.note = QLabel('', self.zone)
        self.note.setStyleSheet(f'color: {tokens.ERROR_COLOR}; font-size: 13px; background: transparent;')
        self.note.setWordWrap(True)
        self.note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note.hide()
        column.addWidget(self.note)

    def set_drag_active(self, active: bool):
        self.zone.active = active
        self.zone.update()

    def set_note(self, text: str):
        self.note.setText(text)
        self.note.setVisible(bool(text))

