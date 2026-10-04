"""Pure QPainter chart canvas shared by every dashboard chart.

One widget owns the complete drawing: axes, grid, marks, hover and tooltip.
Callers describe *what* to draw with :class:`ChartData`; the canvas decides
layout, tick density and label thinning for the space it is given, so a card,
a full-screen dialog and an exported PNG always agree.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from math import atan2, ceil, cos, degrees, floor, hypot, log10, radians, sin

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QIcon, QLinearGradient, QPainter, QPainterPath,
                           QPen, QPixmap)
from PySide6.QtWidgets import QSizePolicy, QWidget

import stats_tokens as tokens
from display_rules import format_number
from stats_typography import emphasis_font, tooltip_font, ui_font

KINDS = ('line', 'bar', 'hbar', 'donut')
COMPARISON_ALPHA = tokens.CHART_COMPARISON_OPACITY


@dataclass(frozen=True)
class AxisSpec:
    """Value-axis range in *scaled* units (raw value / scale)."""
    lower: float
    upper: float
    step: float
    scale: int = 1
    unit_suffix: str = ''


@dataclass
class Series:
    key: str
    name: str
    color: QColor
    values: list                     # one raw number (or None) per slot
    stack: str | None = None         # bars sharing a stack id are stacked
    dashed: bool = False
    faded: bool = False              # comparison period: same hue, lighter
    width: float = 2.0
    area: bool | None = None         # None: fill only a lone line series
    colors: list | None = None       # per-slot colours (hbar categories, donut slices)
    notes: list | None = None        # per-slot extra tooltip text
    keys: list | None = None         # per-slot identity (donut slices)
    titles: list | None = None       # actual bucket dates, including comparison periods


@dataclass
class ChartData:
    kind: str
    labels: list
    series: list = field(default_factory=list)
    unit: str = ''
    titles: list | None = None       # full tooltip heading per slot
    zero: bool | None = None         # None: bars always, lines when sensible
    center_text: str = ''
    center_caption: str = ''
    empty_text: str = '暂无可用数据'
    decimal_places: int = 2

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(self.kind)


def format_value(value, places=2) -> str:
    """Grouped, truncated presentation; source values remain unchanged."""
    return format_number(value, places)


def value_scale(magnitude: float) -> tuple[int, str]:
    if magnitude >= 100_000_000:
        return 100_000_000, '亿'
    if magnitude >= 10_000:
        return 10_000, '万'
    return 1, ''


def nice_ticks(low: float, high: float, max_ticks: int = 6, *, min_step=0) -> tuple[float, float, float]:
    """Round range covering [low, high] with at most ``max_ticks`` ticks."""
    if high < low:
        low, high = high, low
    if high - low < 1e-12:
        pad = abs(high) * .1 or 1.
        low, high = low - pad, high + pad
    max_ticks = max(2, max_ticks)
    span = high - low
    exponent = floor(log10(span / (max_ticks - 1)))
    if min_step:
        exponent = max(exponent, floor(log10(min_step)))
    decimal_low, decimal_high = Decimal(str(low)), Decimal(str(high))
    for power in range(exponent, exponent + 3):
        for unit in (1, 2, 5):
            step = Decimal(unit).scaleb(power)
            if step < Decimal(str(min_step)):
                continue
            lower = (decimal_low / step).to_integral_value(rounding=ROUND_FLOOR) * step
            upper = (decimal_high / step).to_integral_value(rounding=ROUND_CEILING) * step
            if (upper - lower) / step + 1 <= max_ticks:
                return float(lower), float(upper), float(step)
    step = Decimal(1).scaleb(exponent + 3)
    return (float((decimal_low / step).to_integral_value(rounding=ROUND_FLOOR) * step),
            float((decimal_high / step).to_integral_value(rounding=ROUND_CEILING) * step), float(step))


def auto_axis(values, *, zero: bool, max_ticks: int = 6, decimal_places=2) -> AxisSpec:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return AxisSpec(0, 4, 1)
    low, high = min(numbers), max(numbers)
    scale, suffix = value_scale(max(abs(low), abs(high)))
    low, high = low / scale, high / scale
    if zero:
        low, high = min(0., low), max(0., high)
        if high == low == 0:
            high = 4
    else:
        pad = (high - low) * .12 or abs(high) * .05 or 1
        low, high = low - pad, high + pad
    quantum = 10 ** -decimal_places
    while scale > 1 and nice_ticks(low, high, max_ticks)[2] < quantum:
        # A magnitude suffix may hide a small but meaningful spread. Restore
        # the finer unit before widening the axis to the display quantum.
        next_scale, suffix = (10_000, '万') if scale == 100_000_000 else (1, '')
        low, high = low * (scale / next_scale), high * (scale / next_scale)
        scale = next_scale
    lower, upper, step = nice_ticks(low, high, max_ticks, min_step=quantum)
    return AxisSpec(lower, upper, step, scale, suffix)


def _tick_text(value: float, step: float, max_places=2) -> str:
    places = min(max_places, max(0, -Decimal(f'{step:.10g}').normalize().as_tuple().exponent))
    if abs(value) < step * 1e-6:
        value = 0.
    return format_number(value, places, fixed=True)


def _alpha(color: QColor, alpha: float) -> QColor:
    result = QColor(color)
    result.setAlphaF(result.alphaF() * alpha)
    return result


def _bar_path(rect: QRectF) -> QPainterPath:
    """The original capsule silhouette, including the baseline end."""
    radius = max(0., min(rect.width(), rect.height()) / 2)
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def _bar_brush(color: QColor, rect: QRectF, horizontal=False) -> QBrush:
    gradient = (QLinearGradient(rect.left(), rect.center().y(), rect.right(), rect.center().y())
                if horizontal else
                QLinearGradient(rect.center().x(), rect.top(), rect.center().x(), rect.bottom()))
    leading = QColor(color)
    hue, saturation, value, alpha = leading.getHsvF()
    leading.setHsvF(hue, saturation, value * tokens.CHART_BAR_GRADIENT_TOP_FACTOR, alpha)
    gradient.setColorAt(0, leading)
    gradient.setColorAt(1, color)
    return QBrush(gradient)


def _value_font(text, width, height, total=False):
    for size in range(15 if total else 13, 11 if total else 9, -1):
        font = emphasis_font(size, QFont.Weight.Bold) if total else ui_font(size)
        font.setPixelSize(size)
        metrics = QFontMetricsF(font)
        if metrics.horizontalAdvance(text) <= width - 8 and metrics.height() <= height - 4:
            return font
    return font


class _ChartTip(QWidget):
    """Overflow surface: owned by the canvas, outside its clipping rectangle."""

    def __init__(self, canvas):
        super().__init__(canvas, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        blank = QPixmap(1, 1)
        blank.fill(Qt.GlobalColor.transparent)
        self.setWindowIcon(QIcon(blank))
        self.canvas = canvas
        self.content_layout = None

    def paintEvent(self, event):
        painter = QPainter(self)
        # A reused native surface must clear old pixels, including the area
        # outside its rounded border after a shorter tooltip replaces it.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.canvas._draw_tooltip(painter, QRectF(self.rect()).adjusted(1, 1, -1, -1), self.content_layout)


class ChartCanvas(QWidget):
    """Render one :class:`ChartData` with hover, linked crosshair and zoom."""

    hover_changed = Signal(object)      # slot index under the pointer, or None
    slot_clicked = Signal(int)
    slice_clicked = Signal(str)

    def __init__(self, parent=None, *, detailed: bool = False):
        super().__init__(parent)
        self.data: ChartData | None = None
        self.detailed = detailed
        self.hidden: set[str] = set()
        self.axis_override: AxisSpec | None = None
        self.axis: AxisSpec | None = None
        self.show_values = detailed
        self.zoomable = detailed
        self._window: tuple[int, int] | None = None
        self._hover: int | None = None
        self._hover_slice: str | None = None
        self._hover_stack: str | None = None
        self._bar_hits = []
        self._overflow_tip = None
        self._linked: int | None = None
        self._pointer = QPointF()
        self._drag_origin: tuple[float, tuple[int, int]] | None = None
        self._plot = QRectF()
        self._slices: list[dict] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self._font = ui_font(tokens.FONT_SIZE_CAPTION)
        self._strong = QFont(self._font)
        self._strong.setWeight(QFont.Weight.DemiBold)
        from touch_input import install_touch_input
        install_touch_input()

    # ------------------------------------------------------------------ API
    def set_data(self, data: ChartData | None) -> None:
        from stats_motion import settle_surface_motion
        settle_surface_motion(self)
        self.touch_cancel(clear_inspection=True)
        self.data = data
        self._window = None
        self._hover = self._linked = None
        self._hover_slice = None
        self.setAccessibleName(self._accessible_summary())
        self.update()

    def set_hidden(self, keys) -> None:
        from stats_motion import settle_surface_motion
        settle_surface_motion(self)
        self.touch_cancel(clear_inspection=True)
        self.hidden = set(keys)
        self.update()

    def set_axis(self, spec: AxisSpec | None) -> None:
        from stats_motion import settle_surface_motion
        settle_surface_motion(self)
        self.axis_override = spec
        self.update()

    def set_linked_index(self, index: int | None) -> None:
        if index != self._linked:
            self._linked = index
            self.update()

    def slot_count(self) -> int:
        return len(self.data.labels) if self.data else 0

    def window(self) -> tuple[int, int]:
        count = self.slot_count()
        if self._window is None:
            return 0, count
        first, last = self._window
        return max(0, first), min(count, last)

    def set_window(self, first: int, last: int) -> None:
        if self._hover is not None:
            self.hover_changed.emit(None)
        self._hover = self._hover_stack = None
        self._hide_overflow_tip()
        count = self.slot_count()
        length = max(2, min(count, last - first))
        first = max(0, min(first, count - length))
        self._window = None if (first, first + length) == (0, count) else (first, first + length)
        self.update()

    def zoom(self, factor: float, anchor: float = .5) -> None:
        first, last = self.window()
        length = last - first
        target = max(2, min(self.slot_count(), round(length / factor)))
        start = round(first + (length - target) * anchor)
        self.set_window(start, start + target)

    def has_values(self) -> bool:
        data = self.data
        return bool(data and data.labels and any(
            value is not None for item in data.series for value in item.values))

    def sizeHint(self):
        return QSize(420, 240)

    def plot_rect(self) -> QRectF:
        """Plot area from the most recent paint (empty before the first paint)."""
        return QRectF(self._plot)

    def visible_series(self):
        return [item for item in (self.data.series if self.data else ()) if item.key not in self.hidden]

    # -------------------------------------------------------------- helpers
    def _accessible_summary(self) -> str:
        data = self.data
        if not data or not self.has_values():
            return data.empty_text if data else ''
        names = '、'.join(item.name for item in data.series[:6])
        return f'{len(data.labels)} 个数据点 · {names}'

    def _metrics(self, font=None) -> QFontMetricsF:
        return QFontMetricsF(font or self._font)

    def _value_range_values(self):
        data = self.data
        first, last = self.window()
        visible = self.visible_series()
        if data.kind in ('bar',):
            stacks: dict[tuple, list[float]] = {}
            for item in visible:
                for index in range(first, last):
                    value = item.values[index] if index < len(item.values) else None
                    if value is None:
                        continue
                    totals = stacks.setdefault((index, item.stack or item.key), [0., 0.])
                    totals[0 if value >= 0 else 1] += float(value)
            return [value for pair in stacks.values() for value in pair]
        if data.kind == 'hbar':
            return [value for item in visible for value in item.values if value is not None]
        return [value for item in visible for value in item.values[first:last] if value is not None]

    def _resolve_axis(self, max_ticks: int) -> AxisSpec:
        if self.axis_override is not None:
            return self.axis_override
        data = self.data
        values = [float(value) for value in self._value_range_values()]
        zero = data.zero
        if zero is None:
            if data.kind in ('bar', 'hbar'):
                zero = True
            elif not values:
                zero = True
            else:
                low, high = min(values), max(values)
                zero = low <= 0 <= high or (low > 0 and low <= high * .35) or (high < 0 and high >= low * .35)
        return auto_axis(values, zero=zero, max_ticks=max_ticks, decimal_places=data.decimal_places)

    def _y(self, value: float) -> float:
        axis, plot = self.axis, self._plot
        return plot.bottom() - (value / axis.scale - axis.lower) / (axis.upper - axis.lower) * plot.height()

    def _x(self, value: float) -> float:
        axis, plot = self.axis, self._plot
        return plot.left() + (value / axis.scale - axis.lower) / (axis.upper - axis.lower) * plot.width()

    def _slot_center(self, index: int) -> float:
        first, last = self.window()
        return self._plot.left() + (index - first + .5) * self._plot.width() / max(1, last - first)

    def _slot_at(self, x: float) -> int | None:
        first, last = self.window()
        if not self._plot.adjusted(-2, 0, 2, 0).contains(QPointF(x, self._plot.center().y())):
            return None
        width = self._plot.width() / max(1, last - first)
        index = first + int((x - self._plot.left()) // width)
        return index if first <= index < last else None

    def _ticks(self):
        axis = self.axis
        lower, upper, step = (Decimal(str(value)) for value in (axis.lower, axis.upper, axis.step))
        count = int(round((upper - lower) / step))
        return [float(lower + index * step) for index in range(count + 1)]

    # ------------------------------------------------------------- painting
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self._font)
        self._slices = []
        self._bar_hits = []
        data = self.data
        if data is None or not self.has_values():
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter,
                             data.empty_text if data else '暂无可用数据')
            return
        if data.kind == 'donut':
            self._paint_donut(painter)
        elif data.kind == 'hbar':
            self._paint_hbar(painter)
        else:
            self._paint_cartesian(painter)

    def _unit_caption(self) -> str:
        return (self.axis.unit_suffix + self.data.unit) if self.axis else self.data.unit

    def _paint_cartesian(self, painter: QPainter):
        data = self.data
        metrics = self._metrics()
        rect = QRectF(self.rect()).adjusted(2, 4, -8, -2)
        line_height = metrics.height()
        top = rect.top() + line_height * 1.5 + 6
        bottom = rect.bottom() - line_height - 8
        max_ticks = max(3, min(7, int((bottom - top) / 34) + 1))
        self.axis = self._resolve_axis(max_ticks)
        ticks = self._ticks()
        tick_labels = [_tick_text(value, self.axis.step, self.data.decimal_places) for value in ticks]
        gutter = max(metrics.horizontalAdvance(text) for text in tick_labels) + 10
        self._plot = QRectF(rect.left() + gutter, top, max(10., rect.width() - gutter), max(10., bottom - top))
        plot = self._plot

        # Unit caption sits above the value labels, never inside the plot.
        caption = self._unit_caption()
        if caption:
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            painter.drawText(QRectF(rect.left(), rect.top(), rect.width(), line_height),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, caption)

        grid = QPen(QColor(tokens.GRID_COLOR), 1)
        for value, text in zip(ticks, tick_labels):
            y = plot.bottom() - (value - self.axis.lower) / (self.axis.upper - self.axis.lower) * plot.height()
            painter.setPen(grid)
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            painter.drawText(QRectF(rect.left(), y - line_height / 2, gutter - 8, line_height),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)
        if self.axis.lower < 0 < self.axis.upper:
            painter.setPen(QPen(QColor(tokens.AXIS_COLOR), 1))
            y = self._y(0)
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        self._paint_x_labels(painter, bottom + 6, line_height)
        highlight = self._hover if self._hover is not None else self._linked
        first, last = self.window()
        if highlight is not None and first <= highlight < last:
            slot = plot.width() / max(1, last - first)
            band = QRectF(self._slot_center(highlight) - slot / 2, plot.top(), slot, plot.height())
            if data.kind == 'bar':
                painter.fillRect(band, _alpha(QColor(tokens.ACCENT), .07))
            else:
                painter.setPen(QPen(QColor(tokens.BORDER_STRONG), 1, Qt.PenStyle.DashLine))
                painter.drawLine(QPointF(band.center().x(), plot.top()), QPointF(band.center().x(), plot.bottom()))

        painter.save()
        painter.setClipRect(plot.adjusted(-6, -6, 6, 6))
        if data.kind == 'bar':
            labels = self._paint_bars(painter)
        else:
            labels = self._paint_lines(painter, highlight)
        painter.restore()
        if self.detailed and self.show_values:
            self._paint_value_labels(painter, labels)
        if self._hover is not None:
            self._paint_slot_tooltip(painter, self._hover)

    def _paint_x_labels(self, painter, y, line_height):
        data, plot, metrics = self.data, self._plot, self._metrics()
        first, last = self.window()
        count = last - first
        if not count:
            return
        slot = plot.width() / count
        widest = max(metrics.horizontalAdvance(str(data.labels[index])) for index in range(first, last))
        stride = max(1, ceil((widest + 14) / max(1., slot)))
        indices = list(range(first, last, stride))
        # Prefer showing the final slot when it does not collide.
        if indices and indices[-1] != last - 1 and (last - 1 - indices[-1]) * slot >= widest + 14:
            indices.append(last - 1)
        painter.setPen(QColor(tokens.TEXT_SECONDARY))
        for index in indices:
            text = str(data.labels[index])
            width = metrics.horizontalAdvance(text) + 4
            center = self._slot_center(index)
            left = min(max(center - width / 2, plot.left() - 4), self.width() - width - 2)
            painter.drawText(QRectF(left, y, width, line_height), Qt.AlignmentFlag.AlignCenter, text)

    def _stack_layout(self):
        stacks = list(dict.fromkeys(item.stack or item.key for item in self.visible_series()))
        first, last = self.window()
        slot = self._plot.width() / max(1, last - first)
        count = max(1, len(stacks))
        gap = min(24. if self.detailed else 4., max(.8, slot * .075))
        width = min(48. if self.detailed else 20.,
                    max(.6 if self.detailed else 2.,
                        (slot * (.78 if self.detailed else .72) - gap * (count - 1)) / count))
        total = width * count + gap * (count - 1)
        return stacks, width, gap, total

    def _paint_bars(self, painter):
        first, last = self.window()
        stacks, width, gap, total = self._stack_layout()
        baseline = self._y(0) if self.axis.lower <= 0 <= self.axis.upper else (
            self._plot.bottom() if self.axis.lower > 0 else self._plot.top())
        labels = []
        for index in range(first, last):
            left = self._slot_center(index) - total / 2
            for position, stack in enumerate(stacks):
                x = left + position * (width + gap)
                positive = negative = 0.
                members = [item for item in self.visible_series() if (item.stack or item.key) == stack]
                raw_values = [item.values[index] if index < len(item.values) else None for item in members]
                pieces = []
                for item in members:
                    value = item.values[index] if index < len(item.values) else None
                    if value is None:
                        continue
                    raw_value = value
                    value = float(value)
                    start = positive if value > 0 else negative
                    end = start + value
                    if value > 0:
                        positive = end
                    else:
                        negative = end
                    color = QColor(item.colors[index]) if item.colors else QColor(item.color)
                    if item.faded:
                        color = _alpha(color, COMPARISON_ALPHA)
                    y0, y1 = self._y(start), self._y(end)
                    rect = QRectF(x, min(y0, y1), width, abs(y1 - y0))
                    if value:
                        pieces.append((rect, color, value > 0))
                    if value and self.detailed and len(members) > 1:
                        labels.append(dict(text=format_value(raw_value, self.data.decimal_places), x=rect.center().x(),
                                           y=rect.center().y(), above=True, inside_rect=rect,
                                           color=QColor('white') if color.lightnessF() < .55 and not item.faded
                                           else QColor(tokens.TEXT_PRIMARY),
                                           slot_width=self._plot.width() / max(1, last - first) / max(1, len(stacks))))
                for upward in (True, False):
                    side = [(rect, color) for rect, color, sign in pieces if sign == upward]
                    if not side:
                        continue
                    outline = QRectF(side[0][0])
                    for rect, _ in side[1:]:
                        outline = outline.united(rect)
                    self._bar_hits.append((index, stack, _bar_path(outline)))
                    painter.save()
                    painter.setClipPath(_bar_path(outline), Qt.ClipOperation.IntersectClip)
                    for rect, color in side:
                        painter.fillRect(rect, _bar_brush(color, rect))
                    painter.restore()
                if any(value is not None and value != 0 for value in raw_values):
                    total_value = (sum((Decimal(str(value)) for value in raw_values), Decimal(0))
                                   if all(value is not None for value in raw_values) else None)
                    above = positive >= -negative
                    anchor = self._y(positive if above else negative)
                    labels.append(dict(text=format_value(total_value, self.data.decimal_places), x=x + width / 2,
                                       y=anchor, above=above,
                                       total=True, bar_width=width,
                                       slot_width=self._plot.width() / max(1, last - first) / max(1, len(stacks))))
        return labels

    def _paint_lines(self, painter, highlight):
        data = self.data
        first, last = self.window()
        visible = self.visible_series()
        fill_single = len(visible) == 1
        baseline = (self._y(0) if self.axis.lower <= 0 <= self.axis.upper else self._plot.bottom())
        dense = (last - first) > (60 if self.detailed else 31)
        labels = []
        for item in visible:
            color = _alpha(item.color, COMPARISON_ALPHA) if item.faded else QColor(item.color)
            segments, active = [], []
            for index in range(first, last):
                value = item.values[index] if index < len(item.values) else None
                if value is None:
                    if active:
                        segments.append(active)
                    active = []
                else:
                    active.append((index, QPointF(self._slot_center(index), self._y(float(value)))))
            if active:
                segments.append(active)
            area = item.area if item.area is not None else fill_single
            for segment in segments:
                points = [point for _, point in segment]
                if len(points) > 1 and area:
                    gradient = QLinearGradient(0, self._plot.top(), 0, baseline)
                    gradient.setColorAt(0, _alpha(color, .16))
                    gradient.setColorAt(1, _alpha(color, 0))
                    region = QPainterPath(QPointF(points[0].x(), baseline))
                    for point in points:
                        region.lineTo(point)
                    region.lineTo(QPointF(points[-1].x(), baseline))
                    region.closeSubpath()
                    painter.fillPath(region, gradient)
                pen = QPen(color, item.width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                if item.dashed:
                    pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                if len(points) > 1:
                    path = QPainterPath(points[0])
                    for point in points[1:]:
                        path.lineTo(point)
                    painter.drawPath(path)
                if len(points) == 1 or not dense:
                    painter.setPen(QPen(QColor(tokens.CARD_BG), 1.2))
                    painter.setBrush(color)
                    radius = 3.2 if len(points) == 1 else 2.4
                    for point in points:
                        painter.drawEllipse(point, radius, radius)
                for index, point in segment:
                    labels.append(dict(text=format_value(item.values[index], self.data.decimal_places), x=point.x(), y=point.y(),
                                       above=True, slot_width=self._plot.width() / max(1, last - first)))
        if highlight is not None and first <= highlight < last:
            for item in visible:
                value = item.values[highlight] if highlight < len(item.values) else None
                if value is None:
                    continue
                color = _alpha(item.color, COMPARISON_ALPHA) if item.faded else QColor(item.color)
                painter.setPen(QPen(QColor(tokens.CARD_BG), 2))
                painter.setBrush(color)
                painter.drawEllipse(QPointF(self._slot_center(highlight), self._y(float(value))), 4.5, 4.5)
        return labels

    def _paint_value_labels(self, painter, labels):
        painter.save()
        placed: list[QRectF] = []
        # Reserve totals first; a tiny segment must not displace its column sum.
        for label in sorted(labels, key=lambda item: not item.get('total', False)):
            inside = label.get('inside_rect')
            available = label['slot_width']
            height = 40
            if inside is not None and inside.height() >= 18:
                available, height = min(available, inside.width()), min(height, inside.height())
            font = (_value_font(label['text'], available, height, label.get('total', False))
                    if self.detailed else self._font)
            metrics = self._metrics(font)
            width = metrics.horizontalAdvance(label['text']) + 4
            if width > label['slot_width'] + 6:
                continue
            height = metrics.height()
            box = QRectF(label['x'] - width / 2, label['y'] - height / 2, width, height)
            centered = inside is not None and inside.adjusted(1, 1, -1, -1).contains(box)
            if not centered:
                y = label['y'] - height - 3 if label['above'] else label['y'] + 3
                box.moveTop(y)
            candidates = [box]
            if label.get('total'):
                half_bar = label['bar_width'] / 2
                candidates.extend((QRectF(label['x'] + half_bar + 5, label['y'] - height / 2, width, height),
                                   QRectF(label['x'] - half_bar - width - 5, label['y'] - height / 2, width, height),
                                   box.translated(0, height + 6 if label['above'] else -height - 6)))
            if inside is not None:
                for lane in range(ceil(self.height() / (height + 3))):
                    offsets = (0,) if lane == 0 else (lane * (height + 3), -lane * (height + 3))
                    for offset in offsets:
                        candidates.extend((QRectF(inside.right() + 5, label['y'] - height / 2 + offset, width, height),
                                           QRectF(inside.left() - width - 5, label['y'] - height / 2 + offset, width, height)))
            chosen = next((candidate for candidate in candidates
                           if candidate.top() >= 0 and candidate.bottom() <= self.height()
                           and candidate.left() >= self._plot.left() and candidate.right() <= self.width()
                           and not any(candidate.intersects(other) for other in placed)), None)
            if chosen is None:
                continue
            centered = centered and chosen == box
            box = chosen
            placed.append(box)
            if inside is not None and not centered:
                painter.setPen(QPen(QColor(tokens.TEXT_SECONDARY), .6))
                painter.drawLine(QPointF(label['x'], label['y']), box.center())
            painter.setFont(font)
            painter.setPen(label.get('color', QColor(tokens.TEXT_PRIMARY)) if centered else QColor(tokens.TEXT_PRIMARY))
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, label['text'])
        painter.restore()

    def _tooltip_rows(self, index, stack=None):
        rows = []
        for item in self.visible_series():
            if stack is not None and (item.stack or item.key) != stack:
                continue
            value = item.values[index] if index < len(item.values) else None
            if value is None:
                continue
            color = QColor(item.colors[index]) if item.colors else QColor(item.color)
            note = item.notes[index] if item.notes and index < len(item.notes) else ''
            rows.append((_alpha(color, COMPARISON_ALPHA) if item.faded else color, item.name,
                         f'{format_value(value, self.data.decimal_places)} {self.data.unit}'.strip(), note))
        return rows

    def _paint_slot_tooltip(self, painter, index):
        data = self.data
        title = (data.titles[index] if data.titles and index < len(data.titles) else str(data.labels[index]))
        stack = self._hover_stack if data.kind == 'bar' else None
        if stack is not None:
            member = next((item for item in self.visible_series()
                           if (item.stack or item.key) == stack and item.titles
                           and index < len(item.titles) and item.titles[index]), None)
            if member is not None:
                title = member.titles[index]
        self._paint_tooltip(painter, title, self._tooltip_rows(index, stack))

    def _paint_tooltip(self, painter, title, rows):
        if not rows:
            self._hide_overflow_tip()
            return
        layout = self._tooltip_layout(title, rows)
        width, height = layout[:2]
        if height + 8 > self.height() or width + 8 > self.width():
            if self._overflow_tip is None:
                self._overflow_tip = _ChartTip(self)
            tip = self._overflow_tip
            tip.content_layout = layout
            tip.resize(ceil(width + 2), ceil(height + 2))
            anchor = self.mapToGlobal(self._pointer.toPoint())
            bounds = self.screen().availableGeometry()
            x = anchor.x() + 16
            if x + tip.width() > bounds.right():
                x = anchor.x() - tip.width() - 16
            y = anchor.y() - tip.height() // 2
            tip.move(max(bounds.left(), min(x, bounds.right() - tip.width())),
                     max(bounds.top(), min(y, bounds.bottom() - tip.height())))
            tip.show(); tip.update()
            return
        self._hide_overflow_tip()
        x = self._pointer.x() + 16
        if x + width > self.width() - 4:
            x = self._pointer.x() - width - 16
        x = max(4., x)
        y = min(max(4., self._pointer.y() - height / 2), max(4., self.height() - height - 4))
        box = QRectF(x, y, width, height)
        self._draw_tooltip(painter, box, layout)

    def _tooltip_layout(self, title, rows):
        metrics = self._metrics(tooltip_font())
        line = metrics.height() + 4
        name_width = max(metrics.horizontalAdvance(name) for _, name, _, _ in rows)
        value_width = max(metrics.horizontalAdvance(value) for _, _, value, _ in rows)
        width = min(320., max(metrics.horizontalAdvance(title) + 24,
                             name_width + value_width + 54,
                             max((metrics.horizontalAdvance(note) + 38 for *_, note in rows), default=0)))
        # Reserve enough room for numbers and units; long identities wrap.
        value_width = min(value_width, (width - 54) * .55)
        name_width = max(1., width - 54 - value_width)
        flags = Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere
        def height(text, space):
            return max(line, metrics.boundingRect(QRectF(0, 0, space, 10000), flags, text).height() + 4)
        title_height = height(title, width - 24)
        blocks, seen = [], set()
        for color, name, value, note in rows:
            note = note if note not in seen else ''
            seen.add(note)
            blocks.append((color, name, value, note,
                           max(height(name, name_width), height(value, value_width)),
                           height(note, width - 38) if note else 0))
        return (width, 16 + title_height + sum(row[4] + row[5] for row in blocks),
                title, title_height, name_width, value_width, blocks)

    def _draw_tooltip(self, painter, box, layout):
        width, height, title, title_height, name_width, value_width, blocks = layout
        x, y = box.x(), box.y()
        tip_font = tooltip_font()
        flags = Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere | Qt.AlignmentFlag.AlignVCenter
        painter.save()
        painter.setPen(QPen(QColor(tokens.TOOLTIP_BORDER), 1))
        painter.setBrush(QColor(tokens.TOOLTIP_BG))
        painter.drawRoundedRect(box, tokens.TOOLTIP_RADIUS, tokens.TOOLTIP_RADIUS)
        painter.setFont(tip_font)
        painter.setPen(QColor(tokens.TOOLTIP_TEXT))
        cursor = y + 8
        painter.drawText(QRectF(x + 12, cursor, width - 24, title_height), flags, title)
        cursor += title_height
        for color, name, value, note, row_height, note_height in blocks:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x + 12, cursor + row_height / 2 - 4, 8, 8), 2, 2)
            painter.setFont(tip_font)
            painter.setPen(QColor(tokens.TOOLTIP_TEXT))
            painter.drawText(QRectF(x + 26, cursor, name_width, row_height), flags, name)
            painter.setFont(tip_font)
            painter.setPen(QColor(tokens.TOOLTIP_TEXT))
            painter.drawText(QRectF(x + width - 12 - value_width, cursor, value_width, row_height),
                             flags | Qt.AlignmentFlag.AlignRight, value)
            cursor += row_height
            if note:
                painter.setFont(tip_font)
                painter.setPen(QColor(tokens.TOOLTIP_TEXT))
                painter.drawText(QRectF(x + 26, cursor, width - 38, note_height), flags, note)
                cursor += note_height
        painter.restore()

    def _hide_overflow_tip(self):
        if self._overflow_tip is not None:
            self._overflow_tip.hide()

    def _paint_hbar(self, painter):
        data = self.data
        metrics = self._metrics()
        rect = QRectF(self.rect()).adjusted(2, 4, -10, -2)
        line_height = metrics.height()
        visible = self.visible_series()
        values = [float(value) for item in visible for value in item.values if value is not None]
        label_width = min(rect.width() * .32, max(metrics.horizontalAdvance(str(text)) for text in data.labels) + 12)
        value_font = ui_font(13 if self.detailed else 12)
        value_metrics = self._metrics(value_font)
        value_width = max((value_metrics.horizontalAdvance(format_value(value, self.data.decimal_places)) for value in values), default=0) + 10
        plot_width = max(20., rect.width() - label_width - value_width)
        max_ticks = max(2, min(6, int(plot_width / 70) + 1))
        self.axis = self.axis_override or auto_axis(values, zero=True, max_ticks=max_ticks,
                                                  decimal_places=data.decimal_places)
        top = rect.top() + line_height + 6
        self._plot = QRectF(rect.left() + label_width, top, plot_width, rect.bottom() - top - line_height - 8)
        plot = self._plot
        caption = self._unit_caption()
        if caption:
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            painter.drawText(QRectF(plot.left(), rect.top(), plot.width(), line_height),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, caption)
        for value in self._ticks():
            x = plot.left() + (value - self.axis.lower) / (self.axis.upper - self.axis.lower) * plot.width()
            painter.setPen(QPen(QColor(tokens.GRID_COLOR), 1))
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            text = _tick_text(value, self.axis.step, self.data.decimal_places)
            width = metrics.horizontalAdvance(text) + 4
            painter.drawText(QRectF(x - width / 2, plot.bottom() + 6, width, line_height),
                             Qt.AlignmentFlag.AlignCenter, text)
        count = len(data.labels)
        row = plot.height() / max(1, count)
        bands = max(1, len(visible))
        gap = min(3., max(1., row * .045))
        bar = min(14., max(3., (row * .72 - gap * (bands - 1)) / bands))
        block = bar * bands + gap * (bands - 1)
        baseline = self._x(0)
        if self._hover is not None:
            painter.fillRect(QRectF(rect.left(), plot.top() + self._hover * row, rect.width(), row),
                             _alpha(QColor(tokens.ACCENT), .06))
        for index, name in enumerate(data.labels):
            center = plot.top() + (index + .5) * row
            painter.setPen(QColor(tokens.TEXT_PRIMARY))
            painter.drawText(QRectF(rect.left(), center - line_height / 2, label_width - 10, line_height),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             metrics.elidedText(str(name), Qt.TextElideMode.ElideRight, label_width - 10))
            for position, item in enumerate(visible):
                value = item.values[index] if index < len(item.values) else None
                if value is None or value == 0:
                    continue
                end = self._x(float(value))
                color = QColor(item.colors[index]) if item.colors else QColor(item.color)
                if item.faded:
                    color = _alpha(color, COMPARISON_ALPHA)
                box = QRectF(min(baseline, end), center - block / 2 + position * (bar + gap),
                             max(1.5, abs(end - baseline)), bar)
                if value == 0:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(color)
                    painter.drawEllipse(QPointF(min(max(baseline, plot.left() + 3), plot.right() - 3),
                                               box.center().y()), 3., 3.)
                else:
                    painter.fillPath(_bar_path(box), _bar_brush(color, box, horizontal=True))
                if self.detailed and self.show_values:
                    painter.setFont(value_font)
                    painter.setPen(QColor(tokens.TEXT_SECONDARY))
                    text = format_value(value, self.data.decimal_places)
                    painter.drawText(QRectF(box.right() + 4 if end >= baseline else box.left() - value_width,
                                            box.center().y() - value_metrics.height() / 2,
                                            value_width, value_metrics.height()),
                                     (Qt.AlignmentFlag.AlignLeft if end >= baseline else Qt.AlignmentFlag.AlignRight)
                                     | Qt.AlignmentFlag.AlignVCenter, text)
                    painter.setFont(self._font)
        if self._hover is not None:
            self._paint_tooltip(painter, str(data.labels[self._hover]), self._tooltip_rows(self._hover))

    def _paint_donut(self, painter):
        data = self.data
        item = next((entry for entry in data.series), None)
        metrics = self._metrics()
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        entries = [(key, name, Decimal(str(value)), _alpha(color, COMPARISON_ALPHA) if item.faded else QColor(color))
                   for key, name, value, color in zip(
                       item.keys or data.labels, data.labels, item.values,
                       item.colors or [item.color] * len(data.labels))
                   if value is not None and float(value) > 0]
        total = sum(value for _, _, value, _ in entries)
        if total <= 0:
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, data.empty_text)
            return
        line = metrics.height() + 6
        side = rect.width() >= rect.height() * 1.25
        legend_height = len(entries) * line
        if side:
            diameter = min(rect.height() - 8, rect.width() * .46)
            ring = QRectF(rect.left() + 8, rect.center().y() - diameter / 2, diameter, diameter)
            legend = QRectF(ring.right() + 20, rect.center().y() - min(legend_height, rect.height()) / 2,
                            rect.right() - ring.right() - 20, min(legend_height, rect.height()))
        else:
            columns = 2 if rect.width() >= 320 and len(entries) > 3 else 1
            rows = ceil(len(entries) / columns)
            diameter = max(60., min(rect.width() * .7, rect.height() - rows * line - 12))
            ring = QRectF(rect.center().x() - diameter / 2, rect.top() + 4, diameter, diameter)
            legend = QRectF(rect.left() + 4, ring.bottom() + 10, rect.width() - 8, rows * line)
        center = ring.center()
        outer = diameter / 2
        inner = outer * .62
        angle = 90.
        for key, name, value, color in entries:
            span = 360. * float(value / total)
            self._slices.append(dict(key=key, name=name, value=value, color=color, start=angle,
                                     span=span, center=center, outer=outer, inner=inner,
                                     percent=100 * value / total))
            angle += span
        for part in self._slices:
            if part['key'] in self.hidden:
                continue
            grow = 4 if part['key'] == self._hover_slice else 0
            box = QRectF(center.x() - outer - grow, center.y() - outer - grow,
                         2 * (outer + grow), 2 * (outer + grow))
            hole = QRectF(center.x() - inner, center.y() - inner, 2 * inner, 2 * inner)
            path = QPainterPath()
            path.arcMoveTo(box, part['start'])
            path.arcTo(box, part['start'], part['span'])
            path.arcTo(hole, part['start'] + part['span'], -part['span'])
            path.closeSubpath()
            painter.setPen(QPen(QColor(tokens.CARD_BG), 1.5))
            painter.setBrush(part['color'])
            painter.drawPath(path)
        if self.detailed and data.center_text:
            font = QFont(self._strong)
            font.setPixelSize(max(12, min(22, int(inner * .42))))
            painter.setFont(font)
            painter.setPen(QColor(tokens.TEXT_PRIMARY))
            painter.drawText(QRectF(center.x() - inner, center.y() - inner * .5, 2 * inner, inner * .6),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                             QFontMetricsF(font).elidedText(data.center_text, Qt.TextElideMode.ElideRight, 1.8 * inner))
            painter.setFont(self._font)
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            painter.drawText(QRectF(center.x() - inner, center.y() + inner * .12, 2 * inner, line),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, data.center_caption)
        painter.setFont(self._font)
        columns = 1 if side else (2 if rect.width() >= 320 and len(entries) > 3 else 1)
        column_width = legend.width() / columns
        rows = ceil(len(entries) / columns)
        for number, part in enumerate(self._slices):
            column, row = divmod(number, rows) if columns > 1 else (0, number)
            y = legend.top() + row * line
            if y + line > rect.bottom() + 2:
                continue
            x = legend.left() + column * column_width
            hidden = part['key'] in self.hidden
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_alpha(part['color'], .35) if hidden else part['color'])
            painter.drawRoundedRect(QRectF(x, y + line / 2 - 4, 8, 8), 2, 2)
            percentage_value = data.unit == '%'
            percent = (f"{format_value(part['value'], data.decimal_places)} %" if percentage_value
                       else format_number(part['percent'], 1, fixed=True) + '%')
            value_text = f"{format_value(part['value'], data.decimal_places)}"
            right_width = metrics.horizontalAdvance(percent) + 8 if self.detailed else 0
            value_space = metrics.horizontalAdvance(value_text) + 12 if self.detailed and not percentage_value else 0
            painter.setPen(QColor(tokens.TEXT_DISABLED if hidden else tokens.TEXT_PRIMARY))
            painter.drawText(QRectF(x + 14, y, column_width - 14 - right_width - value_space, line),
                             Qt.AlignmentFlag.AlignVCenter,
                             metrics.elidedText(part['name'], Qt.TextElideMode.ElideRight,
                                                column_width - 14 - right_width - value_space))
            if self.detailed:
                painter.setPen(QColor(tokens.TEXT_SECONDARY))
                if not percentage_value:
                    painter.drawText(QRectF(x, y, column_width - right_width - 4, line),
                                     Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, value_text)
                painter.setFont(self._strong)
                painter.setPen(QColor(tokens.TEXT_DISABLED if hidden else tokens.TEXT_PRIMARY))
                painter.drawText(QRectF(x, y, column_width - 4, line),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, percent)
                painter.setFont(self._font)
            part['legend'] = QRectF(x, y, column_width, line)
        hovered = next((part for part in self._slices if part['key'] == self._hover_slice), None)
        if hovered is not None:
            self._paint_tooltip(painter, hovered['name'], [(
                hovered['color'], item.name if data.unit == '%' else format_number(hovered['percent'], 1, fixed=True) + '%',
                f"{format_value(hovered['value'], data.decimal_places)} {data.unit}".strip(), '')])

    # ------------------------------------------------------------- pointer
    def touch_pan(self, global_start, global_point):
        """Reserve horizontal touchscreen movement for an already zoomed detail."""
        if not self.zoomable or self._window is None:
            return False
        if self._drag_origin is None:
            self._drag_origin = (self.mapFromGlobal(global_start.toPoint()).x(), self.window())
        origin, (first, last) = self._drag_origin
        position = self.mapFromGlobal(global_point.toPoint()).x()
        slot = self._plot.width() / max(1, last - first)
        shift = round((origin - position) / max(1., slot))
        self.set_window(first + shift, last + shift)
        return True

    def touch_cancel(self, *, clear_inspection=False):
        self._drag_origin = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        if clear_inspection:
            changed = self._hover is not None
            self._hover = self._hover_slice = None
            self._hover_stack = None
            self._hide_overflow_tip()
            self.update()
            if changed and self.data is not None and self.data.kind in ('line', 'bar'):
                self.hover_changed.emit(None)

    def _slice_at(self, point: QPointF):
        for part in self._slices:
            if part.get('legend') is not None and part['legend'].contains(point):
                return part
            dx, dy = point.x() - part['center'].x(), part['center'].y() - point.y()
            radius = hypot(dx, dy)
            if not part['inner'] <= radius <= part['outer'] + 4:
                continue
            angle = degrees(atan2(dy, dx)) % 360
            if (angle - part['start']) % 360 < part['span']:
                return part
        return None

    def _row_at(self, point: QPointF):
        if not self.data or self.data.kind != 'hbar' or not self._plot.isValid():
            return None
        if not (self._plot.top() <= point.y() <= self._plot.bottom()):
            return None
        row = self._plot.height() / max(1, len(self.data.labels))
        index = int((point.y() - self._plot.top()) // row)
        return index if 0 <= index < len(self.data.labels) else None

    def mouseMoveEvent(self, event):
        self._pointer = event.position()
        if self._drag_origin is not None:
            origin, (first, last) = self._drag_origin
            slot = self._plot.width() / max(1, last - first)
            shift = round((origin - self._pointer.x()) / max(1., slot))
            self.set_window(first + shift, last + shift)
            return
        data = self.data
        if data is None or not self.has_values():
            return
        if data.kind == 'donut':
            part = self._slice_at(self._pointer)
            key = part['key'] if part else None
            if key != self._hover_slice:
                self._hover_slice = key
                self.setCursor(Qt.CursorShape.PointingHandCursor if key else Qt.CursorShape.ArrowCursor)
            self.update()
            return
        stack = None
        if data.kind == 'bar':
            hit = next(((index, key) for index, key, path in reversed(self._bar_hits)
                        if path.contains(self._pointer)), None) if self._plot.contains(self._pointer) else None
            index, stack = hit if hit is not None else (None, None)
        else:
            index = self._row_at(self._pointer) if data.kind == 'hbar' else self._slot_at(self._pointer.x())
        if index is not None and not self._tooltip_rows(index, stack):
            index = None
        changed = index != self._hover
        self._hover = index
        self._hover_stack = stack
        if index is None:
            self._hide_overflow_tip()
        self.update()
        if changed and data.kind != 'hbar':
            self.hover_changed.emit(index)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hide_overflow_tip()
        self._hover_stack = None
        if self._hover is not None or self._hover_slice is not None:
            self._hover = None
            self._hover_slice = None
            self.update()
            if self.data is not None and self.data.kind in ('line', 'bar'):
                self.hover_changed.emit(None)

    def hideEvent(self, event):
        self.touch_cancel(clear_inspection=True)
        super().hideEvent(event)

    def resizeEvent(self, event):
        self.touch_cancel(clear_inspection=True)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.data is None:
            return super().mousePressEvent(event)
        if self.data.kind == 'donut':
            part = self._slice_at(event.position())
            if part is not None:
                self.slice_clicked.emit(str(part['key']))
            return
        if self.zoomable and self._window is not None:
            self._drag_origin = (event.position().x(), self.window())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        if self._hover is not None:
            self.slot_clicked.emit(self._hover)

    def mouseReleaseEvent(self, event):
        if self._drag_origin is not None:
            self._drag_origin = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.zoomable and self._window is not None:
            self._window = None
            self.update()
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        if not self.zoomable or self.data is None or self.data.kind not in ('line', 'bar') or self.slot_count() < 4:
            return super().wheelEvent(event)
        anchor = 0.5
        if self._plot.width() > 0:
            anchor = min(1., max(0., (event.position().x() - self._plot.left()) / self._plot.width()))
        self.zoom(1.25 if event.angleDelta().y() > 0 else 1 / 1.25, anchor)
        event.accept()
