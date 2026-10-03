"""Shared Fluent statistics controls that match the approved desktop references."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QEasingCurve, QPropertyAnimation, QVariantAnimation, QSize, Qt, Signal
from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics
from PySide6.QtWidgets import QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QPushButton
from qfluentwidgets import ComboBox, ScrollArea, TogglePushButton, TransparentToolButton, FluentIcon

import stats_tokens as tokens
import stats_motion as motion_policy

_FONT_ID = -1


class ElidingComboBox(ComboBox):
    """Keep Fluent selection semantics without resizing on a long selection."""

    def __init__(self, parent=None):
        self._full_text = ''
        super().__init__(parent)
        self.clicked.connect(self._toggleComboMenu)

    def mouseReleaseEvent(self, event):
        # Use the same clicked path for mouse and keyboard without toggling twice.
        QPushButton.mouseReleaseEvent(self, event)

    def _createComboMenu(self):
        menu = super()._createComboMenu()
        menu.view.itemActivated.connect(menu.view.itemClicked.emit)
        return menu

    def setText(self, text):
        self._full_text = str(text)
        self.setAccessibleDescription(self._full_text)
        self._elide_text()

    def _elide_text(self):
        # Fluent's text padding and arrow occupy 40 logical pixels.
        shown = self.fontMetrics().elidedText(getattr(self, '_full_text', ''),
                                             Qt.TextElideMode.ElideRight, max(0, self.width() - 40))
        # ComboBoxBase.setText calls adjustSize(), which fights its parent layout.
        QPushButton.setText(self, shown)

    def sizeHint(self):
        hint = super().sizeHint()
        metrics = self.fontMetrics()
        hint.setWidth(hint.width() + metrics.horizontalAdvance(getattr(self, '_full_text', '')) -
                      metrics.horizontalAdvance(self.text()))
        return hint

    def minimumSizeHint(self):
        return QSize(76, super().minimumSizeHint().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide_text()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._elide_text()


def _ensure_chinese_font():
    global _FONT_ID
    if _FONT_ID < 0:
        path = Path('C:/Windows/Fonts/msyh.ttc')
        if path.is_file():
            _FONT_ID = QFontDatabase.addApplicationFont(str(path))


class FluentSegmentedControl(QFrame):
    """Exclusive Fluent segments, prominent for filters and quiet inside cards."""

    currentKeyChanged = Signal(str)

    def __init__(self, parent=None, compact=False, dense=False, subtle=None):
        super().__init__(parent)
        _ensure_chinese_font()
        self.setObjectName('fluentSegmentedControl')
        self._compact = bool(compact)
        self._dense = bool(compact and dense)
        # Card controls share one quiet treatment; page-level mode controls stay prominent.
        self._subtle = bool(compact) if subtle is None else bool(subtle)
        self._height = 28 if self._compact else tokens.CONTROL_HEIGHT
        self._buttons: dict[str, TogglePushButton] = {}
        self._current_key = ''
        self._animation = None
        self._effect_button = None
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(1, 1, 1, 1)
        self._layout.setSpacing(0)
        self.setFixedHeight(self._height)
        self.setStyleSheet(
            f'QFrame#fluentSegmentedControl {{ background: '
            f'{tokens.CARD_BG if self._subtle else tokens.SURFACE_SUBTLE}; '
            f'border: 1px solid {tokens.BORDER}; '
            f'border-radius: {tokens.RADIUS_CONTROL}px; }}')

    def addItem(self, key: str, text: str, icon=None) -> None:
        if not key or key in self._buttons:
            raise ValueError('segment key')
        button = TogglePushButton(text, self, icon)
        button.setAccessibleName(text)
        button.setFixedHeight(self._height - 2)
        font = QFont(tokens.FONT_FAMILY)
        font.setPixelSize(tokens.FONT_SIZE_CAPTION if self._compact else tokens.FONT_SIZE_BODY)
        button.setFont(font)
        button.setIconSize(QSize(16, 16))
        text_width = QFontMetrics(font).horizontalAdvance(text)
        if self._dense and icon is None:
            button.setFixedWidth(max(58, text_width + 22))
        else:
            button.setFixedWidth(max(72, text_width + (24 if icon else 0) + 28))
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.setProperty('keyboardFocus', False)
        button.installEventFilter(self)
        self._buttons[key] = button
        self._group.addButton(button)
        self._layout.addWidget(button)
        self.setFixedWidth(sum(item.width() for item in self._buttons.values()) + 2)
        button.clicked.connect(lambda checked=False, item_key=key: self._select(item_key))
        self._restyle_buttons()
        if not self._current_key:
            self._current_key = key
            button.setChecked(True)

    def _restyle_buttons(self) -> None:
        keys = tuple(self._buttons)
        ordinary_color = tokens.TEXT_SECONDARY if self._subtle else tokens.TEXT_PRIMARY
        selected_bg = tokens.SEGMENT_QUIET_BG if self._subtle else tokens.ACCENT
        selected_hover = tokens.SEGMENT_QUIET_HOVER if self._subtle else tokens.ACCENT_HOVER
        selected_pressed = tokens.BORDER_STRONG if self._subtle else tokens.ACCENT_PRESSED
        selected_color = tokens.TEXT_SECONDARY if self._subtle else tokens.CARD_BG
        selected_weight = 'font-weight: 600;' if self._subtle else ''
        for index, key in enumerate(keys):
            button = self._buttons[key]
            left_radius = tokens.RADIUS_CONTROL - 1 if index == 0 else 0
            right_radius = tokens.RADIUS_CONTROL - 1 if index == len(keys) - 1 else 0
            divider = '0' if index == len(keys) - 1 else f'1px solid {tokens.BORDER}'
            left_padding = 36 if not button.icon().isNull() else tokens.SPACE_MD
            button.setStyleSheet(
                f'ToggleButton {{ background: transparent; color: {ordinary_color}; '
                f'border: 0; border-right: {divider}; '
                f'border-top-left-radius: {left_radius}px; '
                f'border-bottom-left-radius: {left_radius}px; '
                f'border-top-right-radius: {right_radius}px; '
                f'border-bottom-right-radius: {right_radius}px; '
                f'padding-left: {left_padding}px; padding-right: {tokens.SPACE_SM}px; }}'
                f'ToggleButton:hover:!checked {{ background: {tokens.ACCENT_SOFT}; }}'
                f'ToggleButton:pressed:!checked {{ background: {tokens.BORDER_STRONG}; }}'
                f'ToggleButton:checked {{ background: {selected_bg}; color: {selected_color}; '
                f'{selected_weight} }}'
                f'ToggleButton:hover:checked {{ background: {selected_hover}; }}'
                f'ToggleButton:pressed:checked {{ background: {selected_pressed}; }}'
                f'ToggleButton[keyboardFocus="true"] {{ border: '
                f'{tokens.FOCUS_RING_WIDTH}px solid {tokens.FOCUS_RING}; }}'
                f'ToggleButton:disabled {{ color: {tokens.TEXT_DISABLED}; '
                f'background: {tokens.SURFACE_SUBTLE}; }}')

    def _select(self, key: str) -> None:
        if key == self._current_key:
            self._buttons[key].setChecked(True)
            return
        self._current_key = key
        self._buttons[key].setChecked(True)
        self._animate_selection(self._buttons[key])
        self.currentKeyChanged.emit(key)

    def _animate_selection(self, button):
        self._clear_animation()
        if not motion_policy.animations_enabled():
            return
        effect = QGraphicsOpacityEffect(button)
        button.setGraphicsEffect(effect)
        effect.setOpacity(0.72)
        animation = QPropertyAnimation(effect, b'opacity', self)
        animation.setDuration(160)
        animation.setStartValue(0.72)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(self._clear_animation)
        self._effect_button = button
        self._animation = animation
        animation.start()

    def _clear_animation(self):
        animation = self._animation
        button = self._effect_button
        self._animation = None
        self._effect_button = None
        if animation is not None:
            animation.stop()
        if button is not None and button.graphicsEffect() is not None:
            button.setGraphicsEffect(None)
        if animation is not None:
            animation.deleteLater()

    def eventFilter(self, watched, event):
        if watched in self._buttons.values() and event.type() in (
                QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            keyboard = (event.type() == QEvent.Type.FocusIn and
                        event.reason() in (Qt.FocusReason.TabFocusReason,
                                           Qt.FocusReason.BacktabFocusReason,
                                           Qt.FocusReason.ShortcutFocusReason))
            watched.setProperty('keyboardFocus', keyboard)
            watched.style().unpolish(watched)
            watched.style().polish(watched)
        return super().eventFilter(watched, event)

    def setCurrentKey(self, key: str) -> None:
        if key not in self._buttons:
            raise KeyError(key)
        if not self._buttons[key].isEnabled():
            raise ValueError('disabled segment')
        self._select(key)

    def currentKey(self) -> str:
        return self._current_key

    def setItemEnabled(self, key: str, enabled: bool) -> None:
        if key not in self._buttons:
            raise KeyError(key)
        self._buttons[key].setEnabled(enabled)
        if not enabled and key == self._current_key:
            replacement = next((candidate for candidate, button in self._buttons.items()
                                if candidate != key and button.isEnabled()), None)
            if replacement is not None:
                self.setCurrentKey(replacement)


class StatisticsScrollArea(ScrollArea):
    """Fluent overlay scrollbar with touch panning and keyboard scrolling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        viewport = self.viewport()
        from touch_input import install_touch_input
        install_touch_input()
        # Run before the library wheel delegate so precision touchpad deltas survive.
        viewport.installEventFilter(self)

    def setWidget(self, widget):
        super().setWidget(widget)
        # QScrollArea otherwise makes its content paint the platform gray Base.
        widget.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)
        self.viewport().setStyleSheet('background: transparent;')

    def eventFilter(self, watched, event):
        if watched is self.viewport() and event.type() == QEvent.Type.Wheel:
            delta = event.pixelDelta().y()
            if delta:
                bar = self.verticalScrollBar()
                bar.setValue(bar.value() - delta)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        bar = self.verticalScrollBar()
        if bar.maximum() > 0 and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            step = max(24, min(64, self.viewport().height() // 10))
            offsets = {Qt.Key.Key_Up: -step, Qt.Key.Key_Down: step,
                       Qt.Key.Key_PageUp: -self.viewport().height(),
                       Qt.Key.Key_PageDown: self.viewport().height()}
            if event.key() in offsets:
                bar.setValue(bar.value() + offsets[event.key()])
                event.accept()
                return
            if event.key() in (Qt.Key.Key_Home, Qt.Key.Key_End):
                bar.setValue(bar.minimum() if event.key() == Qt.Key.Key_Home else bar.maximum())
                event.accept()
                return
        super().keyPressEvent(event)


class SummaryToggleButton(TransparentToolButton):
    """One accessible Fluent affordance for an entire summary region."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.chevron_angle = 180.
        self._expand_text, self._collapse_text = '展开数据摘要', '收起数据摘要'
        self.setIcon(FluentIcon.CHEVRON_DOWN_MED)
        self._arrow_animation = QVariantAnimation(self)
        self._arrow_animation.valueChanged.connect(self._advance_chevron)
        self.set_collapsed(False)

    def set_collapsed(self, collapsed):
        self.collapsed = bool(collapsed)
        target = 0. if collapsed else 180.
        start_angle = self.chevron_angle
        self._arrow_animation.stop()
        if not self.isVisible() or not motion_policy.animations_enabled():
            self._advance_chevron(target)
        elif self.chevron_angle != target:
            self._arrow_animation.setDuration(167 if collapsed else 250)
            self._arrow_animation.setEasingCurve(QEasingCurve.Type.InCubic if collapsed else QEasingCurve.Type.OutCubic)
            self._arrow_animation.setStartValue(start_angle)
            self._arrow_animation.setEndValue(target)
            self._arrow_animation.start()
        text = self._expand_text if collapsed else self._collapse_text
        self.setToolTip(text)
        self.setAccessibleName(text)

    def set_labels(self, expand_text, collapse_text):
        self._expand_text, self._collapse_text = expand_text, collapse_text
        text = expand_text if self.collapsed else collapse_text
        self.setToolTip(text); self.setAccessibleName(text)

    def _advance_chevron(self, value):
        self.chevron_angle = float(value)
        self.update()

    def _drawIcon(self, icon, painter, rect, state=None):
        painter.save()
        center=rect.center();painter.translate(center);painter.rotate(self.chevron_angle);painter.translate(-center)
        super()._drawIcon(icon, painter, rect)
        painter.restore()


def configure_fluent_table(table, *, font_size=12, header_font_size=11, header_padding=4):
    """Keep Fluent's delegate/selection feedback and existing row/column geometry."""
    from qfluentwidgets import FluentStyleSheet
    # Apply the actual Fluent table stylesheet, not a naked QTableWidget rule.
    FluentStyleSheet.TABLE_VIEW.apply(table)
    font = QFont(tokens.FONT_FAMILY); font.setPixelSize(font_size)
    table.setFont(font)
    table.setShowGrid(False)
    table.setBorderVisible(False)
    header = table.horizontalHeader()
    header_font = QFont(tokens.FONT_FAMILY); header_font.setPixelSize(header_font_size)
    header.setFont(header_font)
    header.setStyleSheet(f'QHeaderView::section {{font-family:"{tokens.FONT_FAMILY}";'
                         f'font-size:{header_font_size}px;padding:{header_padding}px;'
                         f'border:0;border-bottom:1px solid {tokens.BORDER};'
                         f'background:{tokens.CARD_BG};color:{tokens.TEXT_SECONDARY};}}')
