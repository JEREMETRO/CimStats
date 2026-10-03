"""Fluent categorical cards over real snapshots, with independent old-home states."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import atan2, degrees
import re
from types import SimpleNamespace

from PySide6.QtCore import QEvent, Qt, QPointF, QRect, QRectF, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPainter
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy, QToolTip,
                              QStackedWidget, QVBoxLayout, QWidget)
from qfluentwidgets import DropDownPushButton, FluentIcon, RoundMenu, TransparentPushButton, TransparentToolButton
from display_rules import display_mode, format_number
from latest_info_model import ModeCount
from stats_charts import ChartPanel
from stats_controls import FluentSegmentedControl
from stats_elevation import attach_card_elevation
from stats_motion import SurfaceMotion, attach_surface_reveal
from stats_typography import emphasis_font
import stats_tokens as tokens


def numeric(value):
    if value is None:
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def shown(value):
    return format_number(numeric(value))


def font(size=12, bold=False):
    if size >= 18 or bold:
        return emphasis_font(size, QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    result = QFont(tokens.FONT_FAMILY)
    result.setPixelSize(size)
    result.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return result


class FullLabel(QLabel):
    """Full identity survives elided painting; numeric fields reserve measured width."""
    def __init__(self, text='', size=12, bold=False, parent=None):
        self._explicit_tip = None
        self._full_text = None
        super().__init__(parent)
        self.setFont(font(size, bold))
        self.setStyleSheet(f'color:{tokens.TEXT_PRIMARY};background:transparent;')
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text):
        super().setText(str(text))
        self._refresh_tip()
        self.setAccessibleName(str(text))

    def setToolTip(self, text):
        # An explicit empty tip is a persistent opt-out (city/date/clock).
        self._explicit_tip = str(text)
        super().setToolTip(str(text))

    def set_full_text(self, text):
        self._full_text = str(text)
        self._refresh_tip()

    def _refresh_tip(self):
        if self._explicit_tip is not None:
            super().setToolTip(self._explicit_tip)
            return
        rect = self.contentsRect()
        metrics = self.fontMetrics()
        clipped = metrics.horizontalAdvance(self.text()) > rect.width() or metrics.height() > rect.height()
        full = self._full_text or self.text()
        super().setToolTip(full if clipped or full != self.text() else '')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_tip()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange, QEvent.Type.ContentsRectChange):
            self._refresh_tip()

    def setFixedWidth(self, width):
        super().setFixedWidth(width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

    def paintEvent(self, event):
        self._refresh_tip()
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(self.foregroundRole()))
        mode = Qt.TextElideMode.ElideMiddle if self.property('elideMode') == 'middle' else Qt.TextElideMode.ElideRight
        painter.drawText(self.contentsRect(), self.alignment(), self.fontMetrics().elidedText(
            self.text(), mode, self.contentsRect().width()))


def label(text='', name='', size=12, bold=False, parent=None):
    widget = FullLabel(text, size, bold, parent)
    widget.setObjectName(name)
    return widget


class AccessibleToolButton(TransparentToolButton):
    """Add Enter activation while preserving the native Space key behavior."""
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.isEnabled() and not event.isAutoRepeat():
                self.click()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
            return
        super().keyReleaseEvent(event)


def icon_button(icon, name, description, parent=None):
    button = AccessibleToolButton(parent)
    button.setIcon(icon)
    button.setObjectName(name)
    button.setToolTip(description)
    button.setAccessibleName(description)
    button.setFixedSize(24, 24)
    return button


class ViewSegments(FluentSegmentedControl):
    """Statistics segments with local arrow navigation and Enter activation."""
    def eventFilter(self, watched, event):
        if watched in self._buttons.values() and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if watched.isEnabled() and not event.isAutoRepeat():
                    buttons = [button for button in self._buttons.values() if button.isEnabled()]
                    target = watched
                    if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                        direction = 1 if key == Qt.Key.Key_Right else -1
                        target = buttons[(buttons.index(watched) + direction) % len(buttons)]
                        target.setFocus(Qt.FocusReason.TabFocusReason)
                    target.click()
                event.accept()
                return True
        if watched in self._buttons.values() and event.type() == QEvent.Type.KeyRelease and event.key() in (
                Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
            return True
        return super().eventFilter(watched, event)


class ModeMenu(DropDownPushButton):
    """Visible local range menu; the original data-key API remains available."""
    currentIndexChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(font())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedHeight(max(20, self.fontMetrics().height() + 2))
        self._items, self._index = [], -1
        self.range_menu = RoundMenu(parent=self)
        self.range_menu.view.installEventFilter(self)
        self.setMenu(self.range_menu)
        self.setStyleSheet('DropDownPushButton {border:0;background:transparent;padding:0 14px 0 2px;}')

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if self.isEnabled() and not event.isAutoRepeat():
                self._showMenu()
                self.range_menu.view.setCurrentRow(self._index)
                self.range_menu.view.setFocus(Qt.FocusReason.TabFocusReason)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            event.accept()
            return
        super().keyReleaseEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.range_menu.view and event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                if event.type() == QEvent.Type.KeyPress and self.isEnabled() and not event.isAutoRepeat():
                    item = self.range_menu.view.currentItem()
                    if item is not None:
                        self.range_menu.view.itemClicked.emit(item)
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def clear(self):
        self.range_menu.clear()
        self._items, self._index = [], -1

    def addItem(self, text, userData=None):
        index = len(self._items)
        action = QAction(text, self.range_menu)
        action.setCheckable(True)
        action.triggered.connect(lambda checked=False, index=index: self.setCurrentIndex(index))
        self._items.append((text, userData, action))
        self.range_menu.addAction(action)
        if self._index < 0:
            self.setCurrentIndex(0)

    def findData(self, value):
        return next((index for index, item in enumerate(self._items) if item[1] == value), -1)

    def currentData(self):
        return self._items[self._index][1] if self._index >= 0 else None

    def currentIndex(self):
        return self._index

    def count(self):
        return len(self._items)

    def setCurrentIndex(self, index):
        if not 0 <= index < len(self._items):
            return
        changed = index != self._index
        self._index = index
        text = self._items[index][0]
        self.setText(text)
        self.setFixedWidth(self.fontMetrics().horizontalAdvance(text) + 24)
        self.setToolTip('')
        self.setAccessibleName('制式：' + text)
        for position, item in enumerate(self._items):
            item[2].setChecked(position == index)
        if changed:
            self.currentIndexChanged.emit(index)


def text_button(text, name, parent):
    button = TransparentPushButton(text, parent)
    button.setObjectName(name)
    button.setFont(font())
    button.setFixedHeight(28)
    button.setToolTip('')
    button.setAccessibleName(text)
    return button


def empty_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            widget = item.widget()
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()


_MODE_GROUPS = {'公交': 'bus', '有轨电车': 'tram', '无轨电车': 'trolley',
                '地铁': 'metro', '水上巴士': 'waterbus', '单轨列车': 'monorail'}
_STATISTICS_CATEGORY_STYLE = SimpleNamespace(_category_palette=tokens.DATA_CATEGORY_COLORS)
_UNSET = object()


def mode_color(mode):
    """Use the statistics renderer's canonical-key mapping and stable unknown hash."""
    return ChartPanel._category_color(_STATISTICS_CATEGORY_STYLE, _MODE_GROUPS.get(display_mode(mode), str(mode)))


def short_line_name(name):
    """Show the serialized route designation, without its origin/destination suffix."""
    text = str(name)
    match = re.match(r'^[A-Za-z]{0,3}\d+[A-Za-z]?(?:路)?', text)
    return match.group(0) if match else text.split('·', 1)[0]


def complete_total(values):
    numbers = [numeric(value) for value in values]
    return (sum(numbers, Decimal(0)) if numbers and all(
        number is not None and number >= 0 for number in numbers) else None)


def complete_distribution(counts, total):
    denominator = numeric(total)
    subtotal = complete_total(count.value for count in counts)
    return denominator is not None and denominator >= 0 and subtotal == denominator


@dataclass(frozen=True)
class ShareEntry:
    """Presentation-only slice identity; source observations remain LineSummary."""
    key: str
    name: str
    mode: str
    value: Decimal | None
    line_key: str | None
    count: int = 1
    complete: bool = True


def line_share_data(lines, attribute, total):
    """Top ten plus the real remainder. An incomplete full range has no percentage."""
    valid = tuple(line for line in lines if numeric(getattr(line, attribute)) is not None
                  and numeric(getattr(line, attribute)) >= 0)
    ordered = sorted(valid, key=lambda line: numeric(getattr(line, attribute)), reverse=True)
    full = complete_total(getattr(line, attribute) for line in lines)
    supplied = numeric(total)
    denominator = full if full is not None and supplied == full else None
    entries = [ShareEntry(line.key, line.name, line.mode,
                          numeric(getattr(line, attribute)), line.key) for line in ordered[:10]]
    selected = {line.key for line in ordered[:10]}
    remaining_lines = [line for line in lines if line.key not in selected]
    if remaining_lines:
        known = [numeric(getattr(line, attribute)) for line in remaining_lines
                 if numeric(getattr(line, attribute)) is not None and numeric(getattr(line, attribute)) >= 0]
        remaining = sum(known, Decimal(0)) if known else None
        entries.append(ShareEntry('__other__', f'其他线路（{len(remaining_lines)}条）',
                                  '', remaining, None, len(remaining_lines), len(known) == len(remaining_lines)))
    return tuple(entries), denominator


class CategoryCard(QFrame):
    def __init__(self, name, parent=None):
        super().__init__(parent)
        self.setObjectName(name)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setStyleSheet(f'QFrame#{name} {{background:{tokens.CARD_BG};'
                          f'border:1px solid {tokens.BORDER};border-radius:{tokens.RADIUS_CHART}px;}}')
        attach_card_elevation(self, radius=tokens.RADIUS_CHART)
        self.surface_motion = SurfaceMotion(self)
        attach_surface_reveal(self, self.surface_motion)
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(8, 8, 8, 8)
        self.box.setSpacing(4)


class BarTrack(QWidget):
    def __init__(self, value, maximum, color, parent=None):
        super().__init__(parent)
        self.value, self.maximum, self.color = value, maximum, color
        self.setMinimumWidth(0)
        self.setFixedHeight(14)
        self.setAccessibleName(f'条形值 {shown(value)}，最大值 {shown(maximum)}')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens.SURFACE_SUBTLE))
        painter.drawRoundedRect(QRectF(self.rect()), 2, 2)
        if self.value is not None and self.value > 0 and self.maximum > 0:
            painter.setBrush(self.color)
            painter.drawRoundedRect(QRectF(0, 0, float(self.value / self.maximum) * self.width(),
                                            self.height()), 2, 2)


class RankingRow(QFrame):
    line_requested = Signal(str)

    def __init__(self, line, value, maximum, position, prefix, unit, aggregate, parent=None):
        super().__init__(parent)
        self.line = line
        self.setObjectName(f'{prefix}-row-{position}')
        self.setFixedHeight(22)
        self.setMinimumWidth(0)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        display_name = short_line_name(line.name)
        self.name = label(f'{line.mode} {display_name}' if aggregate else display_name, size=12, parent=self)
        self.name.setFixedWidth(112)
        self.name.set_full_text(f'{line.mode} {line.name}' if aggregate else line.name)
        self.track = BarTrack(numeric(value), maximum, QColor(tokens.ACCENT) if aggregate else mode_color(line.mode), self)
        self.number = label(f'{shown(value)} {unit}', bold=True, parent=self)
        self.number.setFixedWidth(max(76, self.number.fontMetrics().horizontalAdvance(self.number.text()) + 2))
        self.number.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.action = icon_button(FluentIcon.CHEVRON_RIGHT, f'{prefix}-line-{position}', f'查看线路：{line.mode} {display_name}', self)
        self.action.setFixedSize(18, 20)
        self.action.clicked.connect(lambda: self.line_requested.emit(line.key))
        row.addWidget(self.name)
        row.addWidget(self.track, 1)
        row.addWidget(self.number)
        row.addWidget(self.action)
        self.number.hide()
        self.track.setToolTip(self.number.toolTip())
        self.setAccessibleName(f'第{position + 1}名 {line.mode} {display_name} {shown(value)} {unit}')


class ModeRing(QWidget):
    mode_requested = Signal(str)
    share_requested = Signal()

    def __init__(self, parent=None, *, show_values=False):
        super().__init__(parent)
        self.show_values = show_values
        self.counts, self.total, self.colors = (), None, {}
        self.caption = '制式占比'
        self.unit = ''
        self.display_labels = {}
        self.inner_ratio = .78
        self.setFixedSize(136, 136)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('制式占比；扇区查看制式排行，环心或空白展开线路占比')
        self.center_total = QLabel('—', self)
        self.center_total.setFont(font(21, True))
        self.center_total.setStyleSheet(f'color:{tokens.TEXT_PRIMARY};background:transparent;')
        self.center_caption = label(self.caption, parent=self)
        self.center_note = label('', parent=self)
        for widget in (self.center_total, self.center_caption, self.center_note):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_data(self, counts, total, colors=None, *, caption='制式占比', display_labels=None, unit=''):
        self.counts, self.total, self.colors = counts, numeric(total), colors or {}
        self.caption, self.display_labels = caption, display_labels or {}
        self.unit = unit
        self.center_total.setText(shown(total))
        self.center_caption.setText(unit or caption)
        self.center_note.setText('总量不完整' if not complete_distribution(counts, total) else '暂无占比' if numeric(total) == 0 else '')
        self._position_center()
        self.update()

    def _position_center(self):
        center, radius = self.geometry_for_hit()
        width = int(radius * self.inner_ratio * 2)
        show_total = self.show_values and self.total_fits()
        self.center_total.setGeometry(int(center.x() - width / 2), int(center.y() - 25), width, 28)
        self.center_total.setVisible(show_total)
        self.center_caption.setGeometry(int(center.x() - width / 2), int(center.y() + (3 if show_total else -9)), width, 18)
        self.center_note.setGeometry(int(center.x() - width / 2), int(center.y() + (21 if show_total else 9)), width, 16)
        self.center_total.setAccessibleName(self.center_total.text())

    def total_fits(self):
        _, radius = self.geometry_for_hit()
        return self.center_total.fontMetrics().horizontalAdvance(self.center_total.text()) + 4 <= int(radius * self.inner_ratio * 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'center_total'):
            self._position_center()

    def geometry_for_hit(self):
        return QPointF(self.width() / 2, self.height() / 2), (min(self.width(), self.height()) - 8) / 2

    def sectors(self):
        if not complete_distribution(self.counts, self.total) or not self.total or self.total <= 0:
            return []
        angle, result = 0., []
        for count in self.counts:
            value = numeric(count.value)
            if value > 0:
                span = float(value / self.total) * 360
                result.append((angle, angle + span, count.mode, value))
                angle += span
        return result

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center, radius = self.geometry_for_hit()
        rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens.GRID_COLOR))
        painter.drawEllipse(rect)
        for start, end, mode, value in self.sectors():
            painter.setBrush(self.colors.get(mode, mode_color(mode)))
            painter.drawPie(rect, round((90 - end) * 16), max(1, round((end - start) * 16)))
        painter.setBrush(QColor(tokens.CARD_BG))
        inset = radius * (1 - self.inner_ratio)
        painter.drawEllipse(rect.adjusted(inset, inset, -inset, -inset))
        painter.setFont(font())
        painter.setPen(QColor(tokens.TEXT_SECONDARY))

    def _hit(self, point):
        center, radius = self.geometry_for_hit()
        dx, dy = point.x() - center.x(), point.y() - center.y()
        distance = (dx * dx + dy * dy) ** .5
        if not radius * self.inner_ratio <= distance <= radius:
            return None
        angle = (degrees(atan2(dy, dx)) + 90) % 360
        return next((sector for sector in self.sectors() if sector[0] <= angle < sector[1]), None)

    def mouseMoveEvent(self, event):
        sector = self._hit(event.position())
        self.setToolTip(f'{self.display_labels.get(sector[2], sector[2])} · {shown(sector[3])} {self.unit} · {format_number(sector[3] / self.total * 100, 1, fixed=True)}%' if sector else '')
        super().mouseMoveEvent(event)

    def touch_inspect(self, global_point):
        """Expose the existing mouse tooltip while a finger inspects a sector."""
        point = global_point.toPoint()
        if self._hit(QPointF(self.mapFromGlobal(point))) is not None:
            QToolTip.showText(point, self.toolTip(), self)
        else:
            QToolTip.hideText()

    def touch_inspect_end(self):
        QToolTip.hideText()

    def leaveEvent(self, event):
        self.setToolTip('')
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            sector = self._hit(event.position())
            if sector:
                self.mode_requested.emit(sector[2])
            else:
                self.share_requested.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.share_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class ModeRow(QFrame):
    mode_requested = Signal(str)

    def __init__(self, count, total, index, unit='班', scale=Decimal(1), prefix='mode', parent=None, percent_width=None):
        super().__init__(parent)
        self.mode = count.mode
        self.setObjectName(f'{prefix}-row-{index}')
        self.setFixedHeight(22)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f'{count.mode} · 点击查看线路排行')
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        dot = QLabel(self)
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(f'background:{mode_color(count.mode).name()};border-radius:3px;')
        row.addWidget(dot)
        self.name = label(count.mode, parent=self)
        self.name.setMinimumWidth(self.name.fontMetrics().horizontalAdvance(count.mode) + 2)
        row.addWidget(self.name, 1)
        value, denominator = numeric(count.value), numeric(total)
        self.number = label(f'{shown(value / scale if value is not None else None)} {unit}', bold=True, parent=self)
        self.number.setFixedWidth(max(64, self.number.fontMetrics().horizontalAdvance(self.number.text()) + 2))
        self.number.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.number)
        percent = f'{format_number(value / denominator * 100, 1, fixed=True)}%' if value is not None and value >= 0 and denominator and denominator > 0 else '—'
        self.share = label(percent, parent=self)
        self.share.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.share.setFixedWidth(percent_width or self.share.fontMetrics().horizontalAdvance(percent) + 2)
        row.addWidget(self.share)
        self.setToolTip('')

        self.setAccessibleName(f'{count.mode} · 点击查看线路排行 {self.number.text()} {self.share.text()}')

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mode_requested.emit(self.mode)
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.mode_requested.emit(self.mode)
            event.accept()
        else:
            super().keyPressEvent(event)


class ShareRow(QFrame):
    line_requested = Signal(str)

    def __init__(self, entry, total, unit, index, color, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName(f'share-row-{index}')
        self.setFixedHeight(20 if entry.line_key else 32)
        self.setMinimumWidth(0)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if entry.line_key else Qt.FocusPolicy.NoFocus)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.dot = QLabel(self)
        self.dot.setFixedSize(6, 6)
        self.dot.setProperty('legendColor', color.name())
        self.dot.setStyleSheet(f'background:{color.name()};border-radius:3px;')
        row.addWidget(self.dot)
        display_name = short_line_name(entry.name) if entry.line_key else entry.name
        self.name = label(f'{entry.mode} {display_name}'.strip(), parent=self) if entry.line_key else QLabel(display_name, self)
        if not entry.line_key:
            self.name.setFont(font())
            self.name.setWordWrap(True)
            self.name.setMinimumWidth(0)
            self.name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            self.name.setStyleSheet(f'color:{tokens.TEXT_PRIMARY};background:transparent;')
        if entry.line_key:
            self.name.set_full_text(f'{entry.mode} {entry.name}'.strip())
        row.addWidget(self.name, 1)
        known = '（已知）' if not entry.complete and entry.value is not None else ''
        self.number = label(f'{shown(entry.value)}{known} {unit}', parent=self)
        self.number.setFixedWidth(max(64, self.number.fontMetrics().horizontalAdvance(self.number.text()) + 2))
        self.number.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.number)
        self.share = label(f'{format_number(entry.value / total * 100, 1, fixed=True)}%' if entry.value is not None and total and total > 0 else '—', parent=self)
        self.share.setFixedWidth(self.share.fontMetrics().horizontalAdvance(self.share.text()) + 2)
        self.share.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.share)
        self.number.hide()
        self.share.hide()
        self.setToolTip('')
        self.setAccessibleName(f'{entry.mode} {entry.name} {shown(entry.value)} {unit} {self.share.text()}')

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.entry.line_key:
            self.line_requested.emit(self.entry.line_key)
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self.entry.line_key:
            self.line_requested.emit(self.entry.line_key)
            event.accept()
        else:
            super().keyPressEvent(event)


class StructureAnalysis(CategoryCard):
    """capture_state/restore_state are JSON-safe and do not alter page-wide scope."""
    line_requested = Signal(str)

    def __init__(self, name, attribute, caption, unit, prefix, parent=None):
        super().__init__(name, parent)
        self.attribute, self.caption, self.unit, self.prefix = attribute, caption, unit, prefix
        self._lines, self._counts, self._total = (), (), None
        self._top10 = None
        self._scope_mode = '综合'
        self._view, self._mode = 'structure', None
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        self.title = label('当日客流结构' if attribute == 'passengers' else '班次结构', size=14, bold=True)
        self.total_label = QLabel('—', self)
        self.total_label.setObjectName('departureTotal' if attribute == 'departures' else 'passengerTotal')
        self.total_label.setFont(font(18, True))
        self.total_label.setWordWrap(True)
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_label.setStyleSheet(f'color:{tokens.TEXT_PRIMARY};background:transparent;')
        self.total_label.setMinimumWidth(0)
        self.total_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.mode_combo = ModeMenu(self)
        self.mode_combo.setObjectName('rankingMode' if attribute == 'passengers' else 'departureRankingMode')
        self.mode_combo.setAccessibleName(caption + '排行制式')
        self.mode_slot = QWidget(self)
        mode_layout = QHBoxLayout(self.mode_slot)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.addWidget(self.mode_combo, 0, Qt.AlignmentFlag.AlignRight)
        self.mode_slot.setFixedHeight(self.mode_combo.height())
        self.mode_slot.setFixedWidth(88)
        self.view_selector = ViewSegments(self, compact=True, dense=True, subtle=False)
        for key, text in (('structure', '制式分布'), ('ranking', '线路排行'), ('line_share', '线路占比')):
            self.view_selector.addItem(key, text)
        self.structure_button = self.view_selector._buttons['structure']
        self.ranking_button = self.view_selector._buttons['ranking']
        self.share_button = self.view_selector._buttons['line_share']
        self.structure_button.setObjectName(prefix + 'StructureAction')
        self.ranking_button.setObjectName('rankingAction' if attribute == 'passengers' else 'departureRankingAction')
        self.share_button.setObjectName(prefix + 'ShareAction')
        self.return_slot = QWidget(self)
        self.return_slot.setFixedSize(28, 28)
        self.return_button = icon_button(FluentIcon.RETURN, 'rankingReturn' if attribute == 'passengers' else 'departureReturn',
                                         '返回制式分布', self.return_slot)
        self.return_button.setFixedSize(28, 28)
        self.return_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        header.addWidget(self.title, 1)
        header.addWidget(self.mode_slot)
        self.box.addLayout(header)
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(4)
        controls.addWidget(self.view_selector)
        controls.addStretch()
        controls.addWidget(self.return_slot)
        self.box.addLayout(controls)
        self.box.addWidget(self.total_label)
        self.stack = QStackedWidget(self)
        self.stack.setMinimumWidth(0)
        self.box.addWidget(self.stack, 1)
        self.structure = QWidget()
        structure_box = QVBoxLayout(self.structure)
        structure_box.setContentsMargins(0, 0, 0, 0)
        structure_box.setSpacing(8)
        lower = QHBoxLayout()
        lower.setSpacing(8)
        # The two home distributions are the sole compact numeric exception.
        self.ring = ModeRing(self, show_values=True)
        self.ring.setFixedSize(156, 156)
        lower.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignVCenter)
        self.mode_list = QWidget()
        self.mode_list.setMinimumWidth(0)
        modes = QVBoxLayout(self.mode_list)
        modes.setContentsMargins(0, 0, 0, 0)
        modes.setSpacing(0)
        modes.addStretch()
        self.mode_rows = QVBoxLayout()
        self.mode_rows.setSpacing(0)
        modes.addLayout(self.mode_rows)
        self.empty_label = label('当前范围暂无数据')
        modes.addWidget(self.empty_label)
        modes.addStretch()
        lower.addWidget(self.mode_list, 1)
        structure_box.addLayout(lower, 1)
        self.stack.addWidget(self.structure)
        self.ranking = QWidget()
        self.ranking_rows = QVBoxLayout(self.ranking)
        self.ranking_rows.setContentsMargins(0, 0, 0, 0)
        self.ranking_rows.setSpacing(0)
        self.rows = self.ranking_rows
        self.stack.addWidget(self.ranking)
        self.line_share = QWidget()
        share_box = QHBoxLayout(self.line_share)
        share_box.setContentsMargins(0, 0, 0, 0)
        share_box.setSpacing(8)
        self.share_ring = ModeRing(self)
        self.share_ring.setFixedSize(156, 156)
        self.share_ring.setAccessibleName('当前范围线路 Top10 与其他占比')
        share_box.addWidget(self.share_ring, 0, Qt.AlignmentFlag.AlignVCenter)
        self.share_rows = QVBoxLayout()
        self.share_rows.setContentsMargins(0, 0, 0, 0)
        self.share_rows.setSpacing(0)
        share_box.addLayout(self.share_rows, 1)
        self.stack.addWidget(self.line_share)
        self.status = label('', 'rankingNote' if attribute == 'passengers' else 'departureNote')
        self.status.setFixedHeight(16)
        self.status.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};background:transparent;')
        self.note = self.status
        self.box.addWidget(self.status)
        self._mode_widgets, self._ranking_widgets, self._share_widgets = [], [], []
        self.ring.mode_requested.connect(self.show_ranking)
        self.ring.share_requested.connect(lambda: self.show_line_share())
        self.view_selector.currentKeyChanged.connect(self._view_selected)
        self.return_button.clicked.connect(self.show_structure)
        self.mode_combo.currentIndexChanged.connect(self._mode_selected)
        self._base_height = 16 + max(self.mode_combo.height(), self.title.fontMetrics().height()) + 28 + 8 + 232
        self.clear()

    def capture_state(self):
        return {'view': self._view, 'mode': self._mode if self._view != 'structure' else None}

    def restore_state(self, state):
        if not isinstance(state, dict) or state.get('view') not in ('structure', 'ranking', 'line_share'):
            self.show_structure()
            return False
        mode = state.get('mode')
        if mode is not None and not isinstance(mode, str):
            self.show_structure()
            return False
        if mode not in (None, '综合') and self.mode_combo.findData(mode) < 0:
            self.show_structure()
            return False
        if state['view'] == 'ranking':
            if mode not in (None, '综合') and self.mode_combo.findData(mode) < 0:
                self.show_structure()
                return False
            self.show_ranking(mode)
        elif state['view'] == 'line_share':
            self.show_line_share(mode)
        else:
            self.show_structure()
        return True

    def _set_data(self, lines, counts, total, top10=None, scope_mode='综合'):
        state = self.capture_state()
        self._lines, self._counts, self._total, self._top10 = tuple(lines), tuple(counts), numeric(total), top10
        self._scope_mode = scope_mode
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        self.mode_combo.addItem('全部制式' if scope_mode == '综合' else scope_mode, userData='综合')
        for mode in dict.fromkeys([*(count.mode for count in counts), *(line.mode for line in lines)]):
            if mode != '综合':
                self.mode_combo.addItem(mode, userData=mode)
        self.mode_combo.blockSignals(False)
        self.ring.set_data(counts, self._total, unit=self.unit)
        empty_layout(self.mode_rows)
        self._mode_widgets = []
        denominator = self._total if complete_distribution(counts, self._total) else None
        percentages = [f'{format_number(numeric(count.value) / denominator * 100, 1, fixed=True)}%'
                       if numeric(count.value) is not None and numeric(count.value) >= 0 and denominator and denominator > 0
                       else '—' for count in counts]
        percent_width = max((self.ring.center_caption.fontMetrics().horizontalAdvance(text) + 2
                             for text in percentages), default=0)
        for i, count in enumerate(counts):
            row = ModeRow(count, denominator, i, self.unit, Decimal(1),
                          'passenger-mode' if self.attribute == 'passengers' else 'mode', percent_width=percent_width)
            row.mode_requested.connect(self.show_ranking)
            self.mode_rows.addWidget(row)
            row.show()
            self._mode_widgets.append(row)
        self.empty_label.setVisible(not counts)
        empty_layout(self.ranking_rows)
        empty_layout(self.share_rows)
        self._ranking_widgets, self._share_widgets = [], []
        self.restore_state(state)

    def clear(self):
        self._view, self._mode = 'structure', None
        self._set_data((), (), None)

    def _header(self, view):
        self._view = view
        structure = view == 'structure'
        self.mode_combo.setVisible(self._scope_mode == '综合')
        self.mode_combo.setEnabled(not structure)
        self.mode_slot.setFixedWidth(max(88, self.mode_combo.width()))
        self.view_selector.blockSignals(True)
        self.view_selector.setCurrentKey(view)
        self.view_selector.blockSignals(False)
        ring = self.ring if structure else self.share_ring
        self.total_label.setText(f'{shown(ring.total)} {self.unit}')
        self.total_label.setVisible(structure and not self.ring.total_fits())
        content_height = max(232, *(widget.minimumSizeHint().height() for widget in
                                   (self.structure, self.ranking, self.line_share)))
        base_height = self._base_height - 232 + content_height
        self.setFixedHeight(base_height)
        self.return_button.setVisible(not structure)
        self.status.hide()

    def _view_selected(self, view):
        if view == 'structure':
            self.show_structure()
        elif view == 'ranking':
            self.show_ranking(self._mode)
        else:
            self.show_line_share()

    def show_structure(self):
        self._mode = None
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.blockSignals(False)
        self._header('structure')
        self.stack.setCurrentWidget(self.structure)
        text = f'{shown(self._total)} {self.unit}'
        self.total_label.setText(text)
        incomplete = bool(self._counts and not complete_distribution(self._counts, self._total))
        self.status.setText('总量不完整' if incomplete else '')
        self.status.setVisible(incomplete)

    def show_ranking(self, mode=None):
        mode = None if mode in (None, '综合') else mode
        if mode is not None and self.mode_combo.findData(mode) < 0:
            self.show_structure()
            return
        self._mode = mode
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(mode or '综合')))
        self.mode_combo.blockSignals(False)
        self._header('ranking')
        self.stack.setCurrentWidget(self.ranking)
        source = self._top10 if mode is None and self._top10 is not None else self._lines
        valid = [line for line in source if (mode is None or line.mode == mode)
                 and numeric(getattr(line, self.attribute)) is not None]
        lines = sorted(valid, key=lambda line: numeric(getattr(line, self.attribute)), reverse=True)[:10]
        empty_layout(self.ranking_rows)
        self._ranking_widgets = []
        maximum = max((numeric(getattr(line, self.attribute)) for line in lines), default=Decimal(0))
        for i, line in enumerate(lines):
            row = RankingRow(line, getattr(line, self.attribute), maximum, i, self.prefix, self.unit, mode is None)
            if sum(other.name == line.name and other.mode == line.mode for other in lines) > 1:
                row.name.set_full_text(f'{line.mode} {line.name}\n公司标识：{line.company_id}')
            row.line_requested.connect(self.line_requested.emit)
            self.ranking_rows.addWidget(row)
            row.show()
            self._ranking_widgets.append(row)
        if not lines:
            empty = label('当前范围暂无有效排行数据')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ranking_rows.addWidget(empty)
        self.ranking_rows.addStretch()
        self.status.setText(f'{mode or "全部制式"} · {len(lines)}条 · {self.unit}')
        available = sum(1 for line in self._lines if (mode is None or line.mode == mode)
                        and numeric(getattr(line, self.attribute)) is not None)
        self.ranking_button.setToolTip('')
        self._header('ranking')

    def _mode_selected(self, *_):
        if self._view == 'line_share':
            self.show_line_share(self.mode_combo.currentData())
        else:
            self.show_ranking(self.mode_combo.currentData())

    def show_line_share(self, mode=_UNSET):
        mode = self._mode if mode is _UNSET else (None if mode in (None, '综合') else mode)
        if mode is not None and self.mode_combo.findData(mode) < 0:
            self.show_structure()
            return
        self._mode = mode
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(mode or '综合')))
        self.mode_combo.blockSignals(False)
        self._header('line_share')
        self.stack.setCurrentWidget(self.line_share)
        source = tuple(line for line in self._lines if mode is None or line.mode == mode)
        expected = self._total if mode is None else next((count.value for count in self._counts if count.mode == mode),
                                                        complete_total(getattr(line, self.attribute) for line in source))
        entries, total = line_share_data(source, self.attribute, expected)
        colors = {entry.key: mode_color(entry.mode) if entry.line_key else QColor(tokens.TEXT_DISABLED) for entry in entries}
        labels = {entry.key: f'{entry.mode} {entry.name}'.strip() for entry in entries}
        self.share_ring.set_data(tuple(ModeCount(entry.key, entry.value) for entry in entries), total, colors,
                                 caption='线路占比', display_labels=labels, unit=self.unit)
        self._header('line_share')
        empty_layout(self.share_rows)
        self._share_widgets = []
        for i, entry in enumerate(entries):
            row = ShareRow(entry, total, self.unit, i, colors[entry.key])
            if entry.line_key and sum(other.name == entry.name and other.mode == entry.mode for other in entries) > 1:
                line = next(line for line in source if line.key == entry.line_key)
                identity = f'{entry.mode} {entry.name}\n公司标识：{line.company_id}'
                row.name.set_full_text(identity)
                self.share_ring.display_labels[entry.key] = identity
            row.line_requested.connect(self.line_requested.emit)
            self.share_rows.addWidget(row)
            row.show()
            self._share_widgets.append(row)
        if not entries:
            self.share_rows.addWidget(label('当前范围暂无有效线路数据'))
        self.share_rows.addStretch()
        self.share_button.setToolTip('')
        self._header('line_share')

    def visible_mode_rows(self):
        return [row for row in self._mode_widgets if row.isVisible()]

    def visible_ranking_rows(self):
        return [row for row in self._ranking_widgets if row.isVisible()]

    def visible_share_rows(self):
        return [row for row in self._share_widgets if row.isVisible()]


class PassengerRanking(StructureAnalysis):
    """Historical name/three-argument set_data retained; initial view is structure."""
    def __init__(self, parent=None):
        super().__init__('passengerRanking', 'passengers', '客流', '人次', 'ranking', parent)

    def set_data(self, lines, top10, counts, total=_UNSET, *, scope_mode='综合'):
        self._set_data(lines, counts, complete_total(count.value for count in counts) if total is _UNSET else total,
                       tuple(top10), scope_mode)


class DepartureStructure(StructureAnalysis):
    def __init__(self, parent=None):
        super().__init__('departureStructure', 'departures', '班次', '班', 'departure-ranking', parent)

    def set_data(self, lines, counts, total, *, scope_mode='综合'):
        self._set_data(lines, counts, total, scope_mode=scope_mode)
