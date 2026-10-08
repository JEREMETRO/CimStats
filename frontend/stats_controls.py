"""Shared Fluent statistics controls that match the approved desktop references."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QEasingCurve, QVariantAnimation, QRect, QRectF, QSize, Qt, Signal, QObject
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QPainter
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QStyle, QStyleOptionButton, QLayout
from qfluentwidgets import ComboBox, ScrollArea, TogglePushButton, TransparentToolButton, FluentIcon
from qfluentwidgets import PushButton, PrimaryPushButton

import stats_tokens as tokens
from stats_typography import ui_font
import stats_motion as motion_policy

_FONT_ID = -1


class _NavigationPivotStyle(QObject):
    """Shared icon states and keyboard emphasis for page navigation."""
    def __init__(self,pivot,icons):
        super().__init__(pivot)
        self.pivot=pivot;self.icons=dict(icons)
        for item in pivot.items.values():
            item.setProperty('keyboardFocus',False)
            item.installEventFilter(self)

    def update_icons(self,route):
        for key,icon in self.icons.items():
            self.pivot.items[key].setIcon(icon.icon(
                color=QColor(tokens.ACCENT if key==route else tokens.TEXT_SECONDARY)))

    def eventFilter(self,watched,event):
        if (event.type()==QEvent.Type.DynamicPropertyChange
                and bytes(event.propertyName())==b'isSelected'):
            self.update_icons(self.pivot.currentRouteKey())
        if event.type() in (QEvent.Type.FocusIn,QEvent.Type.FocusOut,QEvent.Type.MouseButtonPress):
            keyboard=(event.type()==QEvent.Type.FocusIn and event.reason() in (
                Qt.FocusReason.TabFocusReason,Qt.FocusReason.BacktabFocusReason,Qt.FocusReason.ShortcutFocusReason))
            watched.setProperty('keyboardFocus',keyboard)
            watched.style().unpolish(watched);watched.style().polish(watched)
        return super().eventFilter(watched,event)


def configure_navigation_pivot(pivot,icons=None,*,in_header=False):
    """Reuse the established statistics Pivot appearance and header sizing."""
    # Pivot's forced layout minimum would overwrite the explicit 40px host.
    pivot.hBoxLayout.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
    pivot.setMinimumHeight(40)
    pivot.setMaximumWidth(16777215 if in_header else 480)
    if in_header:pivot.setItemFontSize(14)
    rule=('QPushButton { background: transparent; border: 0; outline: 0; padding: 7px 12px 7px 34px; '
          'color: #65758B; } QPushButton:hover { background: transparent; color: #0067C0; } '
          'QPushButton[isSelected="true"] { color: #0067C0; font-weight: 600; } '
          'QPushButton[keyboardFocus="true"] { text-decoration: underline; background: transparent; border: 0; outline: 0; }')
    for item in pivot.items.values():
        item.setIconSize(QSize(18,18))
        item.setMinimumHeight(36 if in_header else 40)
        item.setFixedWidth(118 if in_header else 148)
        item.setStyleSheet(rule)
    if not hasattr(pivot,'_navigation_style'):
        pivot._navigation_style=_NavigationPivotStyle(pivot,icons or {})
    elif icons is not None:
        pivot._navigation_style.icons=dict(icons)
    pivot._navigation_style.update_icons(pivot.currentRouteKey())


def button_text_size(button):
    """Measure polished text plus its real Fluent padding and arrow reserve."""
    button.ensurePolished()
    option = QStyleOptionButton()
    button.initStyleOption(option)
    ink = option.fontMetrics.boundingRect(QRect(0, 0, 10000, 10000),
        int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextSingleLine), option.text)
    contents = QSize(max(ink.width(), option.fontMetrics.horizontalAdvance(option.text)) + 2,
                     ink.height())
    return button.style().sizeFromContents(QStyle.ContentsType.CT_PushButton,
                                          option, contents, button)


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


class _SegmentButton(TogglePushButton):
    """Text and icons follow the moving fill without opacity effects or polish."""
    def paintEvent(self, event):
        QPushButton.paintEvent(self, event)
        owner = self.parentWidget()
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        painter.setFont(self.font())
        left = 36 if not self.icon().isNull() else tokens.SPACE_MD
        text_rect = QRectF(self.rect()).adjusted(left, 0, -tokens.SPACE_SM, 0)
        clip = owner._indicator.translated(-self.x(), -self.y())
        color = tokens.TEXT_DISABLED if not self.isEnabled() else (
            tokens.TEXT_SECONDARY if owner._subtle else tokens.TEXT_PRIMARY)
        painter.setPen(QColor(color))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.text())
        if not owner._subtle and self.isEnabled():
            painter.save(); painter.setClipRect(clip)
            painter.setPen(QColor(tokens.CARD_BG))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.text())
            painter.restore()
        if not self.icon().isNull():
            if not self.isEnabled(): painter.setOpacity(.3628)
            elif self.isPressed: painter.setOpacity(.786)
            w, h = self.iconSize().width(), self.iconSize().height()
            x = 12 + max(0, self.width() - self.minimumSizeHint().width()) // 2
            if self.isRightToLeft(): x = self.width() - w - x
            icon_rect = QRectF(x, (self.height()-h)/2, w, h)
            PushButton._drawIcon(self, self._icon, painter, icon_rect)
            if not owner._subtle and self.isEnabled():
                painter.setClipRect(clip)
                PrimaryPushButton._drawIcon(self, self._icon, painter, icon_rect)


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
        self._indicator = QRectF()
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
        button = _SegmentButton(text, self, icon)
        button.setAccessibleName(text)
        button.setFixedHeight(self._height - 2)
        font = ui_font(tokens.FONT_SIZE_CAPTION if self._compact else tokens.FONT_SIZE_BODY)
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
        selected_weight = 'font-weight: 600;' if self._subtle else ''
        for index, key in enumerate(keys):
            button = self._buttons[key]
            left_radius = tokens.RADIUS_CONTROL - 1 if index == 0 else 0
            right_radius = tokens.RADIUS_CONTROL - 1 if index == len(keys) - 1 else 0
            divider = '0' if index == len(keys) - 1 else f'1px solid {tokens.BORDER}'
            left_padding = 36 if not button.icon().isNull() else tokens.SPACE_MD
            button.setStyleSheet(
                f'ToggleButton {{ background: transparent; color: transparent; '
                f'border: 0; border-right: {divider}; '
                f'border-top-left-radius: {left_radius}px; '
                f'border-bottom-left-radius: {left_radius}px; '
                f'border-top-right-radius: {right_radius}px; '
                f'border-bottom-right-radius: {right_radius}px; '
                f'padding-left: {left_padding}px; padding-right: {tokens.SPACE_SM}px; }}'
                f'ToggleButton:hover:!checked {{ background: {tokens.ACCENT_SOFT}; }}'
                f'ToggleButton:pressed:!checked {{ background: {tokens.BORDER_STRONG}; }}'
                f'ToggleButton:checked {{ background: transparent; color: transparent; '
                f'{selected_weight} }}'
                f'ToggleButton:hover:checked {{ background: transparent; }}'
                f'ToggleButton:pressed:checked {{ background: transparent; }}'
                f'ToggleButton[keyboardFocus="true"] {{ border: '
                f'{tokens.FOCUS_RING_WIDTH}px solid {tokens.FOCUS_RING}; }}'
                f'ToggleButton:disabled {{ color: transparent; '
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
        start = QRectF(self._indicator)
        self._clear_animation()
        end = QRectF(button.geometry())
        if not motion_policy.animations_enabled() or not self.isVisible() or start.isEmpty():
            self._indicator = end
            self.update()
            return
        animation = QVariantAnimation(self)
        animation.setDuration(167)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setEasingCurve(motion_policy.reposition_easing())
        def advance(rect):
            self._indicator = rect
            self.update()
            for item in self._buttons.values(): item.update()
        animation.valueChanged.connect(advance)
        animation.finished.connect(self._clear_animation)
        self._animation = animation
        animation.start()

    def _clear_animation(self):
        animation = self._animation
        self._animation = None
        if animation is not None:
            animation.stop()
        if animation is not None:
            animation.deleteLater()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._indicator.isEmpty(): return
        button = self._buttons.get(self._current_key)
        color = tokens.SEGMENT_QUIET_BG if self._subtle else tokens.ACCENT
        if button is not None and button.isDown():
            color = tokens.BORDER_STRONG if self._subtle else tokens.ACCENT_PRESSED
        elif button is not None and button.underMouse():
            color = tokens.SEGMENT_QUIET_HOVER if self._subtle else tokens.ACCENT_HOVER
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(color))
        painter.drawRoundedRect(self._indicator, tokens.RADIUS_CONTROL-1, tokens.RADIUS_CONTROL-1)

    def _settle_indicator(self):
        self._clear_animation()
        if self._current_key in self._buttons:
            self._layout.activate()
            self._indicator = QRectF(self._buttons[self._current_key].geometry())
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._settle_indicator()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_buttons'): self._settle_indicator()

    def hideEvent(self, event):
        self._settle_indicator()
        super().hideEvent(event)

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

    def currentText(self) -> str:
        button = self._buttons.get(self._current_key)
        return button.text() if button is not None else ''

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
    font = ui_font(font_size)
    table.setFont(font)
    table.setShowGrid(False)
    table.setBorderVisible(False)
    header = table.horizontalHeader()
    header_font = ui_font(header_font_size)
    header.setFont(header_font)
    header.setStyleSheet(f'QHeaderView::section {{font-family:"{tokens.FONT_FAMILY}";'
                         f'font-size:{header_font_size}px;padding:{header_padding}px;'
                         f'border:0;border-bottom:1px solid {tokens.BORDER};'
                         f'background:{tokens.CARD_BG};color:{tokens.TEXT_SECONDARY};}}')
