"""Small shared widgets for the reworked shell, pages and chart cards."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QLayout, QSizePolicy,
                               QVBoxLayout, QWidget)

import stats_tokens as tokens


class FlowLayout(QLayout):
    """Left-to-right wrapping layout with height-for-width support."""

    def __init__(self, parent=None, spacing=6, alignment=Qt.AlignmentFlag.AlignLeft):
        super().__init__(parent)
        self._items = []
        self._align = alignment
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, False)

    def sizeHint(self):
        width = sum(item.sizeHint().width() for item in self._items if not item.isEmpty())
        width += self.spacing() * max(0, len(self._items) - 1)
        height = max((item.sizeHint().height() for item in self._items), default=0)
        return QSize(width, height)

    def minimumSize(self):
        size = QSize(0, 0)
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _arrange(self, rect, test_only):
        rows, row, used = [], [], 0
        spacing = self.spacing()
        for item in self._items:
            if item.isEmpty():
                continue
            width = item.sizeHint().width()
            if row and used + spacing + width > rect.width():
                rows.append((row, used))
                row, used = [], 0
            used += (spacing if row else 0) + width
            row.append(item)
        if row:
            rows.append((row, used))
        y = rect.y()
        for items, used in rows:
            height = max(item.sizeHint().height() for item in items)
            x = rect.x() + (rect.width() - used if self._align & Qt.AlignmentFlag.AlignRight else 0)
            for item in items:
                hint = item.sizeHint()
                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y + (height - hint.height()) // 2), hint))
                x += hint.width() + spacing
            y += height + spacing
        return max(0, y - rect.y() - (spacing if rows else 0))


class LegendChip(QAbstractButton):
    """Checkable colour key; unchecked hides the series without recomputing."""

    def __init__(self, text: str, color: QColor, parent=None, *, compact=False):
        super().__init__(parent)
        self._compact = compact
        self.setText(text)
        self._color = QColor(color)
        self.setCheckable(True)
        self.setChecked(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        font = QFont(tokens.FONT_FAMILY)
        font.setPixelSize(11 if compact else tokens.FONT_SIZE_CAPTION)
        self.setFont(font)
        self.setAccessibleName(text)
        self.setToolTip(f'{text} · 点击显示/隐藏')
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.ensurePolished()

    def set_color(self, color: QColor):
        self._color = QColor(color)
        self.update()

    def sizeHint(self):
        if self._compact:
            return QSize(43, 18)
        metrics = QFontMetrics(self.font())
        return QSize(min(220, metrics.horizontalAdvance(self.text()) + 26), 22)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        if self.underMouse() or self.hasFocus():
            painter.setPen(QColor(tokens.FOCUS_RING) if self.hasFocus() else Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens.SEGMENT_QUIET_BG))
            painter.drawRoundedRect(rect, 6, 6)
        dot = QColor(self._color)
        if not self.isChecked():
            dot = QColor(tokens.TEXT_DISABLED)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot)
        if self._compact:
            painter.drawEllipse(QRectF(1, rect.center().y() - 3.5, 7, 7))
        else:
            painter.drawRoundedRect(QRectF(7, rect.center().y() - 4, 8, 8), 2, 2)
        painter.setPen(QColor(tokens.TEXT_SECONDARY if self.isChecked() else tokens.TEXT_DISABLED))
        text_rect = (QRectF(11, 0, rect.width() - 12, rect.height()) if self._compact else
                     QRectF(20, 0, rect.width() - 24, rect.height()))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight,
                                                       int(text_rect.width())))


class SeriesLegend(LegendChip):
    """Shared color-column key for company and period identities."""

    def __init__(self, text, colors, parent=None, *, compact=False):
        self.colors = tuple(QColor(color) for color in colors)
        super().__init__(text, self.colors[0], parent)
        self._compact = compact
        self.setCheckable(False)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(text)

    def sizeHint(self):
        return QSize(min(140 if self._compact else 252, self.fontMetrics().horizontalAdvance(self.text()) + 32),
                     18 if self._compact else 22)

    def set_compact(self, enabled):
        if self._compact != bool(enabled):
            self._compact = bool(enabled)
            self.updateGeometry()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        if self.isCheckable() and (self.underMouse() or self.hasFocus()):
            painter.setPen(QColor(tokens.FOCUS_RING) if self.hasFocus() else Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens.SEGMENT_QUIET_BG))
            painter.drawRoundedRect(rect, 6, 6)
        top = rect.center().y() - 8
        outline = QPainterPath()
        outline.addRoundedRect(QRectF(4, top, 12, 16), 6, 6)
        painter.save()
        painter.setClipPath(outline)
        active = not self.isCheckable() or self.isChecked()
        for index, color in enumerate(reversed(self.colors)):
            painter.fillRect(QRectF(4, top + index * 16 / len(self.colors), 12, 16 / len(self.colors)),
                             color if active else QColor(tokens.TEXT_DISABLED))
        painter.restore()
        painter.setPen(QColor(tokens.TEXT_SECONDARY if active else tokens.TEXT_DISABLED))
        text_rect = QRectF(23, 0, rect.width() - 29, rect.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight,
                                                       int(text_rect.width())))


class FlowHost(QWidget):
    """A widget that owns a FlowLayout and reports height-for-width."""

    def __init__(self, parent=None, spacing=6, alignment=Qt.AlignmentFlag.AlignLeft):
        super().__init__(parent)
        self.flow = FlowLayout(self, spacing, alignment)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.flow.heightForWidth(width)

    def clear(self):
        while self.flow.count():
            item = self.flow.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()


def caption_label(text='', parent=None, *, secondary=True, size=tokens.FONT_SIZE_CAPTION):
    label = QLabel(text, parent)
    label.setStyleSheet(f'color: {tokens.TEXT_SECONDARY if secondary else tokens.TEXT_PRIMARY}; '
                        f'font-size: {size}px; background: transparent; border: 0;')
    return label


class Card(QFrame):
    """Plain white card with the shared border, radius and padding."""

    def __init__(self, name='card', parent=None, *, padding=tokens.CARD_PADDING, spacing=tokens.SPACE_SM):
        super().__init__(parent)
        self.setObjectName(name)
        self.setStyleSheet(f'QFrame#{name} {{ background: {tokens.CARD_BG}; border: 1px solid {tokens.BORDER}; '
                           f'border-radius: {tokens.RADIUS_CARD}px; }}')
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding - 2, padding, padding)
        self.body.setSpacing(spacing)


def section_title(text, parent=None):
    label = QLabel(text, parent)
    label.setObjectName('sectionHeading')
    label.setStyleSheet(f'color: {tokens.TEXT_PRIMARY}; font-size: 15px; font-weight: 600; '
                        f'background: transparent; border: 0;')
    return label


class SectionHeader(QWidget):
    """Section title with optional trailing controls on the same baseline."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 0, 0, 0)
        row.setSpacing(tokens.SPACE_SM)
        self.title = section_title(text, self)
        row.addWidget(self.title)
        row.addStretch(1)
        self.row = row

    def add(self, widget):
        self.row.addWidget(widget)
        return widget

