"""Reusable dashboard charts. Values stay in their original units in Result."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from html import escape
from hashlib import sha256
from math import ceil, floor
from pathlib import Path
import shiboken6

from PySide6.QtCore import QEvent, QMargins, QPointF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QFontDatabase, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QGraphicsEllipseItem, QGridLayout, QHBoxLayout, QLabel, QToolTip, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, TransparentTogglePushButton, TransparentToolButton
from PySide6.QtCharts import (
    QAreaSeries, QBarCategoryAxis, QBarSeries, QBarSet, QCategoryAxis, QChart, QChartView,
    QHorizontalBarSeries, QLineSeries, QPieSeries, QPieSlice, QValueAxis,
)

from stats_text import group_label, label
from stats_controls import FluentSegmentedControl
from fluent_chart_view import FluentChartView
from chart_details import (ChartNumbers, DetailSummary, detail_canvas_plan, detail_window,
                           detail_axis_values, detail_axis_range, detail_axis_format, exact_number)
from stats_typography import apply_emphasis_font, emphasis_css
import stats_tokens as tokens
from stats_elevation import attach_card_elevation
from stats_motion import SurfaceMotion
from statistics_model import period_bounds, summarize_buckets


@dataclass(frozen=True)
class AxisSpec:
    lower: int
    upper: int
    step: int
    scale: int = 1
    unit_suffix: str = ''


def nice_axis(values) -> AxisSpec:
    numbers = [float(v) for v in values if v is not None]
    low = min([0.0, *numbers])
    high = max([0.0, *numbers])
    magnitude = max(abs(low), abs(high))
    scale, suffix = (100000000, '亿') if magnitude >= 100000000 else (
        (10000, '万') if magnitude >= 10000 else ((1000, '千') if magnitude >= 1000 else (1, '')))
    low /= scale
    high /= scale
    needed = max(high - low, 1)
    candidates = sorted({n * 10 ** power for power in range(0, max(1, len(str(ceil(needed))) + 1))
                         for n in (1, 2, 5)})
    options = []
    for step in candidates:
        lower = floor(low / step) * step
        upper = ceil(high / step) * step
        if lower == upper:
            upper += step
        ticks = (upper - lower) // step + 1
        if ticks > 7:
            continue
        # Prefer four to seven ticks, then the closest usable range.
        score = (0 if 4 <= ticks <= 7 else 1, (upper - lower) - (high - low), abs(ticks - 5))
        options.append((score, lower, upper, step))
    _, lower, upper, step = min(options)
    if lower == 0 and upper < 4 and high <= 2:
        upper = 4
        step = 1
    return AxisSpec(lower, upper, step, scale, suffix)


_KNOWN_GROUP_COLORS = dict(zip(
    ('BlueCollar', 'WhiteCollar', 'BusinessPeople', 'Pensioner', 'Student', 'Tourist',
     'bus', 'tram', 'trolley', 'metro', 'waterbus', 'misc'),
    tokens.CATEGORY_COLORS[:6] + tokens.CATEGORY_COLORS[:6]))
_CHART_FONT = QFont(tokens.FONT_FAMILY)
_CHART_FONT.setPixelSize(tokens.FONT_SIZE_CAPTION)
_FONT_ID = -1


def _ensure_chinese_font():
    global _FONT_ID
    if _FONT_ID < 0:
        font_path = Path('C:/Windows/Fonts/msyh.ttc')
        if font_path.is_file():
            _FONT_ID = QFontDatabase.addApplicationFont(str(font_path))


def _stable_color(key: str, palette: tuple[str, ...]) -> QColor:
    return QColor(palette[int.from_bytes(sha256(key.encode('utf-8')).digest()[:4], 'big') % len(palette)])


def company_color(company_id: str) -> QColor:
    return _stable_color('company:' + company_id, tokens.COMPANY_COLORS)


def _category_color(group: str) -> QColor:
    return (QColor(_KNOWN_GROUP_COLORS[group]) if group in _KNOWN_GROUP_COLORS
            else _stable_color('category:' + group, tokens.CATEGORY_COLORS))


def _number(value: Decimal | None) -> str:
    if value is None:
        return label('missing')
    if value == value.to_integral_value():
        return f'{value:,.0f}'
    return f'{value:,.2f}'.rstrip('0').rstrip('.')


class ChartPanel(QFrame):
    hover_offset_changed = Signal(object)
    MODES = ('summary', 'bar', 'line', 'pie')

    def __init__(self, title: str, modes: bool = False, default_mode: str = 'line',
                 settings=None, settings_key: str = '', parent=None,
                 allowed_modes: tuple[str, ...] | None = None):
        super().__init__(parent)
        _ensure_chinese_font()
        self.setObjectName('chartPanel')
        attach_card_elevation(self, radius=tokens.RADIUS_CHART)
        self.surface_motion = SurfaceMotion(self)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            f'QFrame#chartPanel {{ background: {tokens.CARD_BG}; '
            f'border: 1px solid {tokens.BORDER}; border-radius: {tokens.RADIUS_CHART}px; }}'
            f'QToolTip {{ color: {tokens.TEXT_PRIMARY}; background: {tokens.CARD_BG}; '
            f'border: 1px solid {tokens.BORDER_STRONG}; padding: {tokens.SPACE_SM}px; }}')
        self.result = None
        self.companies = {}
        self._company_palette: dict[str, QColor] = {}
        self.hovered_bucket = None
        self._hover_targets = []
        self._hover_markers = {}
        self._area_boundaries = []
        self._fullscreen_dialog = None
        self._detailed = isinstance(parent, QDialog)
        self._detail_zoom = 1.0
        self._detail_first = 0
        self._detail_range = (0, 1)
        self._configuring_detail = False
        self._cached_time_geometry = None
        self.chart_views: list[QChartView] = []
        self.company_labels: list[QLabel] = []
        self.summary_values = {}
        self.axis_spec = None
        self._base_axis_spec = None
        self._axis_override = None
        self._adapting_axis = False
        self._adapting_time_labels = False
        self._hidden_groups = set()
        self._category_palette: tuple[str, ...] | None = None
        self._category_items = {}
        self._category_markers = {}
        self._bar_entries = {}
        self.legend_buttons = {}
        self._legend_in_header = False
        self._settings = settings
        self._settings_key = settings_key
        self._compact_layout = False
        self._compact_height: int | None = None
        self._restricted_modes = allowed_modes is not None
        self._allowed_modes = self._validate_modes(allowed_modes) if self._restricted_modes else self.MODES
        self.mode = default_mode
        if (modes or self._restricted_modes) and settings is not None and settings_key:
            saved = settings.value(settings_key, default_mode)
            if saved in (self._allowed_modes if self._restricted_modes else (*self.MODES, 'area')):
                self.mode = saved
        if self._restricted_modes and self.mode not in self._allowed_modes:
            self.mode = self._allowed_modes[0]
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(tokens.SPACE_MD, tokens.SPACE_SM,
                                        tokens.SPACE_MD, tokens.SPACE_MD)
        self._layout.setSpacing(tokens.SPACE_SM)
        header = QHBoxLayout()
        self._header_layout = header
        header.setSpacing(tokens.CHART_HEADER_GAP)
        self.title_label = QLabel(title)
        self.title_label.setObjectName('panelTitle')
        self.title_label.setStyleSheet(emphasis_css(tokens.FONT_SIZE_CHART_TITLE) +
                                           f'color: {tokens.TEXT_PRIMARY}; border: 0;')
        apply_emphasis_font(self.title_label, tokens.FONT_SIZE_CHART_TITLE)
        self.title_label.setWordWrap(True)
        header.addWidget(self.title_label, 1)
        self.mode_selector = None
        self._mode_row = None
        self._mode_host = None
        self._mode_in_header = False
        self._mode_items = set()
        self._selector_modes: tuple[str, ...] = ()
        self._mode_labels: dict[str, str] = {}
        self.fullscreen_button = TransparentToolButton(self)
        self.fullscreen_button.setIcon(FluentIcon.FULL_SCREEN.icon(color=QColor(tokens.TEXT_SECONDARY)))
        self.fullscreen_button.setIconSize(QSize(tokens.CHART_ACTION_ICON_SIZE,
                                                 tokens.CHART_ACTION_ICON_SIZE))
        self.fullscreen_button.setFixedSize(tokens.CONTROL_HEIGHT, tokens.CONTROL_HEIGHT)
        self.fullscreen_button.setToolTip('全屏查看')
        self.fullscreen_button.setAccessibleName('全屏查看图表')
        self.fullscreen_button.setProperty('keyboardFocus', False)
        self.fullscreen_button.installEventFilter(self)
        self.fullscreen_button.setStyleSheet(
            f'QToolButton {{ border: 0; border-radius: {tokens.RADIUS_CONTROL}px; }}'
            f'QToolButton:hover {{ background: {tokens.ACCENT_SOFT}; }}'
            f'QToolButton[keyboardFocus="true"] {{ border: '
            f'{tokens.FOCUS_RING_WIDTH}px solid {tokens.FOCUS_RING}; }}')
        self.fullscreen_button.clicked.connect(self._open_fullscreen)
        header.addWidget(self.fullscreen_button)
        self._layout.addLayout(header)
        self.detail_summary = DetailSummary(self)
        self._layout.addWidget(self.detail_summary)
        if modes or self._restricted_modes:
            initial_modes = self._allowed_modes if self._restricted_modes else (
                (*self.MODES, self.mode) if self.mode in ('area', 'trend-bar') else self.MODES)
            self._replace_mode_selector(initial_modes)
        self.legend_host = QWidget(self)
        self.legend_layout = QGridLayout(self.legend_host)
        self.legend_layout.setContentsMargins(0, 0, 0, 0)
        self.legend_layout.setHorizontalSpacing(8)
        self.legend_layout.setVerticalSpacing(8)
        self.legend_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._layout.addWidget(self.legend_host)
        self.period_label = QLabel(self)
        self.period_label.setFont(QFont('Microsoft YaHei UI'))
        self.period_label.setStyleSheet(f'color: {tokens.TEXT_SECONDARY}; '
                                        f'font-size: {tokens.FONT_SIZE_CAPTION}px; border: 0;')
        self._layout.addWidget(self.period_label)
        self.summary_label = QLabel(label('missing'))
        self.summary_label.setWordWrap(True)
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.summary_label.setStyleSheet(emphasis_css(22, QFont.Weight.Bold) +
                                         f'color: {tokens.TEXT_PRIMARY};')
        apply_emphasis_font(self.summary_label, 22, QFont.Weight.Bold)
        self._layout.addWidget(self.summary_label)
        self.chart_host = QWidget(self)
        self.chart_layout = (QHBoxLayout if self._detailed else QVBoxLayout)(self.chart_host)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_layout.setSpacing(tokens.CHART_CONTENT_GAP)
        if self._detailed:
            self.detail_zoom_host = QWidget(self)
            zoom_row = QHBoxLayout(self.detail_zoom_host)
            zoom_row.setContentsMargins(0, 0, 0, 0)
            self.detail_previous = TransparentToolButton(self.detail_zoom_host)
            self.detail_previous.setText('‹')
            self.detail_previous.setToolTip('前一时间段')
            self.detail_previous.clicked.connect(lambda: self.move_detail_window(-1))
            zoom_row.addWidget(self.detail_previous)
            self.detail_zoom_out = TransparentToolButton(self.detail_zoom_host)
            self.detail_zoom_out.setText('−')
            self.detail_zoom_out.setAccessibleName('缩小图表')
            self.detail_zoom_out.clicked.connect(lambda: self.set_detail_zoom(self._detail_zoom / 1.5))
            zoom_row.addWidget(self.detail_zoom_out)
            self.detail_zoom_label = QLabel('1×', self.detail_zoom_host)
            zoom_row.addWidget(self.detail_zoom_label)
            self.detail_zoom_in = TransparentToolButton(self.detail_zoom_host)
            self.detail_zoom_in.setText('+')
            self.detail_zoom_in.setAccessibleName('放大图表')
            self.detail_zoom_in.clicked.connect(lambda: self.set_detail_zoom(self._detail_zoom * 1.5))
            zoom_row.addWidget(self.detail_zoom_in)
            self.detail_next = TransparentToolButton(self.detail_zoom_host)
            self.detail_next.setText('›')
            self.detail_next.setToolTip('后一时间段')
            self.detail_next.clicked.connect(lambda: self.move_detail_window(1))
            zoom_row.addWidget(self.detail_next)
            for button in (self.detail_previous, self.detail_zoom_out, self.detail_zoom_in, self.detail_next):
                button.setFixedSize(28, 28)
            self._header_layout.insertWidget(self._header_layout.indexOf(self.fullscreen_button), self.detail_zoom_host)
            self._layout.addWidget(self.chart_host, 1)
        else:
            self._layout.addWidget(self.chart_host, 1)
        self.numbers = ChartNumbers(self)
        self._layout.addWidget(self.numbers)
        self._render()

    def _refresh_value_content(self):
        self.numbers.refresh()
        if self._detailed:
            self.detail_summary.refresh()
            self._configure_detail_canvas()
        elif self._compact_height is not None:
            self.setFixedHeight(self._compact_height)

    def set_detail_zoom(self, value):
        self._detail_zoom = min(24., max(1., value))
        self._configure_detail_canvas()

    def move_detail_window(self, direction):
        first, last = self._detail_range
        self._detail_first = first + direction * (last - first)
        self._configure_detail_canvas()

    def _configure_detail_canvas(self):
        if not self._detailed or self._configuring_detail:
            return
        self._configuring_detail = True
        font = QFont(tokens.FONT_FAMILY)
        font.setPixelSize(12)
        metrics = QFontMetrics(font)
        temporal = False
        count = max((visual.get('count', len(visual.get('slots', visual.get('dates', []))))
                     for view in self.chart_views for visual in view.visuals), default=1)
        first, last = detail_window(max(1, count), self._detail_zoom, self._detail_first)
        self._detail_first, self._detail_range = first, (first, last)
        for view in self.chart_views:
            plan = detail_canvas_plan(view.visuals, self.numbers.model.rows,
                                      metrics.horizontalAdvance)
            view.detail_plan = plan
            if not plan:
                continue
            temporal = True
            groups = max((len(visual['groups'] if visual['type'] == 'network-stacks' else visual['sets'])
                          for visual in view.visuals if visual['type'] in ('network-stacks', 'time-bars')), default=1)
            label_width = max((metrics.horizontalAdvance(exact_number(row['value'])) + 16 for row in self.numbers.model.rows
                              if row['value'] is not None), default=80)
            available = max(200, self.width() - 110)
            plan['window'] = first, last
            plan['labels'] = available / ((last - first) * groups) >= max(80, label_width)
            plan['header_height'] = 0
            view.setMinimumWidth(0)
            view.parentWidget().setMinimumWidth(0)
            view.setMinimumHeight(260)
            view.chart().setMargins(QMargins(6, ceil(plan['header_height']) + 6, 6, 6))
            horizontal = next((axis for axis in view.chart().axes(Qt.Orientation.Horizontal)
                               if isinstance(axis, QValueAxis)), None)
            if horizontal:
                horizontal.setRange(first - .5, last - .5)
                self._adapt_time_label_axis(horizontal, self._time_geometry(), available)
            view.viewport().update()
        self.detail_zoom_host.setVisible(temporal)
        self.detail_zoom_out.setEnabled(self._detail_zoom > 1)
        self.detail_zoom_in.setEnabled(self._detail_zoom < 24)
        self.detail_previous.setEnabled(first > 0)
        self.detail_next.setEnabled(last < count)
        self.detail_zoom_label.setText(f'{self._detail_zoom:g}×')
        self.chart_layout.invalidate()
        self.chart_layout.activate()
        self.chart_host.setMinimumWidth(0)
        self._configuring_detail = False
        self._update_detail_axes()

    def _update_detail_axes(self):
        if not self._detailed or not self.chart_views or self._axis_override is not None:
            return
        hidden = self._hidden_groups | getattr(self, '_hidden_categories', set())
        visuals = [visual for view in self.chart_views for visual in view.visuals]
        values, zero = detail_axis_values(visuals, *self._detail_range, hidden)
        if not any(visual['type'] in ('line', 'time-bars', 'network-stacks') for visual in visuals):
            return
        # A 32 px label line must fit beneath negative bar ends. Estimate usable
        # height conservatively, including axes, before the chart's next paint.
        plot_height = min(max(120., view.height() - 70.) for view in self.chart_views)
        negative_padding = max(.05, 32. * 1.05 / (plot_height - 32.))
        spec = AxisSpec(**detail_axis_range(values, zero, negative_padding))
        self.axis_spec = self._base_axis_spec = spec
        for view in self.chart_views:
            for axis in view.chart().axes(Qt.Orientation.Vertical):
                if isinstance(axis, QValueAxis):
                    axis.setRange(spec.lower, spec.upper)
                    axis.setTickAnchor(spec.lower)
                    axis.setTickInterval(spec.step)
                    axis.setLabelFormat(detail_axis_format(spec.step))
            for visual in view.visuals:
                if 'axis' in visual:
                    visual['axis'] = spec
                if visual['type'] == 'line':
                    visual['points'] = [(index, float(bucket.value) / spec.scale, bucket)
                                        for index, _, bucket in visual['points']]
                elif visual['type'] == 'time-bars':
                    for entry in visual['sets']:
                        entry['values'] = [float(bucket.value) / spec.scale if bucket and bucket.value is not None else None
                                           for bucket in entry['buckets']]
            view.unit_text = spec.unit_suffix + self.result.metric.unit
            view.viewport().update()

    def setFixedHeight(self, height):
        # Page budgets may request less than a readable graph and complete
        # values area require. Honour their request up to the content minimum.
        if (getattr(self, '_compact_height', None) is not None and hasattr(self, 'numbers')
                and self.mode == 'pie'):
            height = max(height, self.minimumSizeHint().height())
        super().setFixedHeight(height)

    def event(self, event):
        handled = super().event(event)
        if (event.type() == QEvent.Type.LayoutRequest and
                getattr(self, '_compact_height', None) is not None and hasattr(self, 'numbers')):
            minimum = (max(self._compact_height, self.minimumSizeHint().height())
                       if self.mode == 'pie' else self._compact_height)
            if self.minimumHeight() != minimum or self.maximumHeight() != minimum:
                self.setFixedHeight(minimum)
        return handled

    def _axis_font(self):
        font = QFont(_CHART_FONT)
        if self._detailed:
            font.setPixelSize(max(12, font.pixelSize()))
        return font

    def sizeHint(self):
        if self._compact_height is not None:
            return QSize(360, max(self._compact_height, self.minimumHeight()))
        return QSize(360, max(247 if self._compact_layout else 260,
                             self.minimumSizeHint().height()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_mode_selector()
        self._position_legend()
        self._reflow_legend()
        self._adapt_axes()
        if self._detailed:
            self._configure_detail_canvas()
        if self._compact_height is not None:
            self.setFixedHeight(self._compact_height)

    def _position_legend(self):
        if not self.legend_buttons:
            return
        threshold = 680 if self._compact_layout and self._mode_in_header else 520
        in_header = self._combined_totals and self.width() >= threshold
        if in_header and not self._legend_in_header:
            self._layout.removeWidget(self.legend_host)
            self._header_layout.insertWidget(self._header_layout.count() - 1,
                                             self.legend_host, 0, Qt.AlignmentFlag.AlignRight)
            self._legend_in_header = True
        elif not in_header and self._legend_in_header:
            self._header_layout.removeWidget(self.legend_host)
            self._layout.insertWidget(1, self.legend_host)
            self._legend_in_header = False

    def eventFilter(self, watched, event):
        if (watched is getattr(self, 'fullscreen_button', None) or
                watched in self.legend_buttons.values()) and (
                event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut)):
            keyboard = (event.type() == QEvent.Type.FocusIn and event.reason() in (
                Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
                Qt.FocusReason.ShortcutFocusReason))
            watched.setProperty('keyboardFocus', keyboard)
            watched.style().unpolish(watched)
            watched.style().polish(watched)
        return super().eventFilter(watched, event)

    def _legend_icon(self, group):
        image = QPixmap(12, 12)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._legend_color(group))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 8, 8)
        painter.end()
        return QIcon(image)

    def _legend_color(self, group):
        if self._combined_totals:
            return self._company_color(group)
        groups = self._groups()
        if len(groups) == 1 and len(next(iter(groups.values()))) == 1:
            return self._company_color(next(iter(groups)))
        return self._category_color(group)

    def _build_legend(self, groups):
        for button in self.legend_buttons.values():
            self.legend_layout.removeWidget(button)
            button.hide()
            button.deleteLater()
        self.legend_buttons = {}
        if self.mode == 'summary' or self.result is None or not groups:
            self.legend_host.hide()
            return
        categories = (dict.fromkeys(groups) if self._combined_totals else
                      dict.fromkeys(group for entries in groups.values() for group in entries))
        self._position_legend()
        if (len(groups) == 1 and len(categories) == 1 and
                next(iter(categories)) in ('总计', '__total__', '') and
                next(iter(categories)) not in self._hidden_groups):
            self.legend_host.hide()
            return
        for group in categories:
            button = TransparentTogglePushButton(self.legend_host)
            legend_font = QFont(tokens.FONT_FAMILY)
            legend_font.setPixelSize(tokens.FONT_SIZE_CAPTION)
            button.setFont(legend_font)
            button.setText(self._company_name(group) if self._combined_totals else group_label(group))
            button.setAccessibleName(button.text())
            button.setToolTip(button.text())
            button.setProperty('keyboardFocus', False)
            button.installEventFilter(self)
            button.setIcon(self._legend_icon(group))
            button.setIconSize(QSize(12, 12))
            button.setCheckable(True)
            button.setChecked(group not in self._hidden_groups)
            left_padding = 28 if not button.icon().isNull() else 5
            button.setStyleSheet(
                f'ToggleButton {{ color: {tokens.TEXT_SECONDARY}; border: 0; '
                f'padding: 2px 5px 2px {left_padding}px; text-align: left; }} '
                f'ToggleButton:hover, ToggleButton:checked {{ background: {tokens.ACCENT_SOFT}; '
                f'border-radius: {tokens.RADIUS_CONTROL}px; }} '
                f'ToggleButton:!checked {{ color: {tokens.TEXT_DISABLED}; }} '
                f'ToggleButton[keyboardFocus="true"] {{ border: '
                f'{tokens.FOCUS_RING_WIDTH}px solid {tokens.FOCUS_RING}; }}')
            button.clicked.connect(lambda checked=False, g=group: self._toggle_category(g))
            self.legend_buttons[group] = button
        self.legend_host.show()
        self._position_legend()
        self._reflow_legend()
        for group in categories:
            self._apply_category(group)

    def _reflow_legend(self):
        if not self.legend_buttons:
            return
        width = max(button.sizeHint().width() for button in self.legend_buttons.values())
        columns = max(1, min(3, len(self.legend_buttons), min(self.width(), 320) // (width + 8)))
        while self.legend_layout.count():
            self.legend_layout.takeAt(0)
        for index, button in enumerate(self.legend_buttons.values()):
            self.legend_layout.addWidget(button, index // columns, index % columns)

    def _add_mode_item(self, mode):
        name = self._mode_labels.get(
            mode, {'line': '趋势', 'area': '趋势', 'trend-bar': '趋势',
                   'bar': '分布', 'pie': '比例'}.get(mode, label(mode)))
        self.mode_selector.addItem(mode, name)
        self._mode_items.add(mode)
        if mode not in self._selector_modes:
            self._selector_modes += (mode,)

    @classmethod
    def _validate_modes(cls, modes):
        values = tuple(modes)
        if not values or len(values) != len(set(values)) or any(
                mode not in (*cls.MODES, 'trend-bar', 'area') for mode in values):
            raise ValueError('allowed chart modes')
        return values

    def _replace_mode_selector(self, modes):
        self._selector_modes = tuple(modes)
        if self.mode_selector is not None:
            if self._mode_in_header:
                self._header_layout.removeWidget(self.mode_selector)
            else:
                self._mode_row.removeWidget(self.mode_selector)
            self.mode_selector.hide()
            self.mode_selector.deleteLater()
        self.mode_selector = None
        self._mode_in_header = False
        self._mode_items.clear()
        if len(modes) <= 1:
            if self._mode_host is not None:
                self._mode_host.hide()
            return
        if self._mode_row is None:
            self._mode_host = QWidget(self)
            self._mode_row = QHBoxLayout(self._mode_host)
            self._mode_row.setContentsMargins(0, 0, 0, 0)
            self._mode_row.addStretch(1)
            self._layout.insertWidget(1, self._mode_host)
        self.mode_selector = FluentSegmentedControl(self, compact=True)
        for mode in modes:
            self._add_mode_item(mode)
        self.mode_selector.setCurrentKey(self.mode)
        self.mode_selector.currentKeyChanged.connect(self._selected_mode)
        self._mode_row.addWidget(self.mode_selector)
        self._mode_host.show()
        self._position_mode_selector()

    def _position_mode_selector(self):
        if self.mode_selector is None:
            return
        combined = getattr(self, '_combined_totals', False)
        in_header = self._compact_layout and self.width() >= (680 if combined else 520)
        if in_header and not self._mode_in_header:
            self._mode_row.removeWidget(self.mode_selector)
            self._header_layout.insertWidget(
                self._header_layout.indexOf(self.fullscreen_button), self.mode_selector)
            self._mode_host.hide()
            self._mode_in_header = True
            self.updateGeometry()
        elif not in_header and self._mode_in_header:
            self._header_layout.removeWidget(self.mode_selector)
            self._mode_row.addWidget(self.mode_selector)
            self._mode_host.show()
            self._mode_in_header = False
            self.updateGeometry()

    def set_compact_layout(self, enabled: bool) -> None:
        """Use a readable, shorter company card; full-screen stays spacious."""
        enabled = bool(enabled)
        if enabled == self._compact_layout:
            return
        self._compact_layout = enabled
        self._layout.setContentsMargins(*(8, 6, 8, 8) if enabled else
                                        (tokens.SPACE_MD, tokens.SPACE_SM,
                                         tokens.SPACE_MD, tokens.SPACE_MD))
        self._layout.setSpacing(4 if enabled else tokens.SPACE_SM)
        self._header_layout.setSpacing(6 if enabled else tokens.CHART_HEADER_GAP)
        self.chart_layout.setSpacing(6 if enabled else tokens.CHART_CONTENT_GAP)
        size = 32 if enabled else tokens.CONTROL_HEIGHT
        self.fullscreen_button.setFixedSize(size, size)
        self._position_mode_selector()
        self._render()
        self.updateGeometry()

    def set_compact_height(self, height: int) -> None:
        """Fit an opt-in company/network card to a page-assigned height.

        180 logical pixels is the lower bound for the requested graph budget.
        The complete value area and current controls determine the card minimum.
        """
        if not isinstance(height, int) or isinstance(height, bool) or height < 180:
            raise ValueError('compact chart height must be at least 180')
        self._compact_height = height
        self.set_compact_layout(True)
        self.setFixedHeight(height)
        self._layout.setContentsMargins(6, 4, 6, 4)
        self._layout.setSpacing(2)
        self._header_layout.setSpacing(4)
        self.chart_layout.setSpacing(2)
        self.legend_layout.setHorizontalSpacing(6)
        self.legend_layout.setVerticalSpacing(2)
        self.fullscreen_button.setFixedSize(28, 28)
        self._render()
        self.updateGeometry()

    def _chart_minimum(self, default: int) -> int:
        if self._detailed:
            return 300
        if self._compact_height is None:
            return default
        return min(default, max(130 if self.mode == 'pie' else 90, self._compact_height - 112))

    def clear_compact_height(self) -> None:
        """Release a page's two-column height budget when it becomes one column."""
        if self._compact_height is None:
            return
        self._compact_height = None
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        self._render()
        self.updateGeometry()

    def set_mode_options(self, modes: tuple[str, ...]) -> None:
        """Show only modes supported by this metric; one allowed mode needs no switch."""
        self._allowed_modes = self._validate_modes(modes)
        self._restricted_modes = True
        if self.mode not in self._allowed_modes:
            self.mode = self._allowed_modes[0]
        self._replace_mode_selector(self._allowed_modes)
        if self._settings is not None and self._settings_key:
            self._settings.setValue(self._settings_key, self.mode)
        self._render()

    def set_mode_labels(self, labels: dict[str, str] | None) -> None:
        """Override visible Fluent mode text without changing saved mode keys."""
        if labels is None:
            labels = {}
        if any(mode not in (*self.MODES, 'trend-bar', 'area') or
               not isinstance(name, str) or not name.strip()
               for mode, name in labels.items()):
            raise ValueError('chart mode labels')
        self._mode_labels = dict(labels)
        if self.mode_selector is not None:
            self._replace_mode_selector(self._selector_modes)

    def _selected_mode(self, route_key):
        self.set_mode(route_key)

    def _company_color(self, company: str) -> QColor:
        return self._company_palette.get(company, company_color(company))

    def _category_color(self, group: str) -> QColor:
        if self._category_palette is None:
            return _category_color(group)
        if group in tokens.DATA_CATEGORY_GROUPS:
            index = tokens.DATA_CATEGORY_GROUPS.index(group) % 6
            return QColor(self._category_palette[index])
        return _stable_color('category:' + group, self._category_palette)

    def set_category_palette(self, colors: tuple[str, ...] | None) -> None:
        """Opt a company/network card into a stable category palette.

        None restores the city chart's existing colors.
        """
        if colors is not None:
            colors = tuple(colors)
            if len(colors) < 6 or any(not QColor(value).isValid() for value in colors):
                raise ValueError('category palette')
        self._category_palette = colors
        self._render()

    def set_company_palette(self, palette: dict[str, str]) -> None:
        """Use the page's stable save-wide company ID colors for this panel."""
        converted = {company: QColor(value) for company, value in palette.items()}
        if any(not color.isValid() for color in converted.values()):
            raise ValueError('company palette')
        self._company_palette = converted
        self._render()

    def set_hover_offset(self, seconds: float | None) -> None:
        """Highlight a relative time position without emitting hover_offset_changed."""
        self._hide_hover_markers()
        self.hovered_bucket = None
        self._selected_value = None
        if seconds is None or not self._hover_targets:
            return
        for chart in {target['chart'] for target in self._hover_targets}:
            candidates = [target for target in self._hover_targets
                          if target['chart'] is chart and target['key'] not in self._hidden_groups
                          and abs(target['offset'] - seconds) < .5]
            if not candidates:
                continue
            target = min(candidates, key=lambda item: (abs(item['offset'] - seconds),
                                                        item['previous']))
            self._show_hover_target(target)

    def _show_hover_target(self, target):
        chart = target['chart']
        self.hovered_bucket = target['bucket']
        marker = self._hover_markers.get(chart)
        if marker is None:
            marker = QGraphicsEllipseItem(-5, -5, 10, 10, chart)
            marker.setPen(QPen(QColor(tokens.CARD_BG), 2))
            marker.setZValue(100)
            self._hover_markers[chart] = marker
        marker.setBrush(QBrush(target['color']))
        marker.setPos(self._hover_position(target))
        self._active_hover_targets[chart] = target
        marker.show()

    def _hide_hover_markers(self):
        self._active_hover_targets = {}
        for marker in self._hover_markers.values():
            marker.hide()

    def _hover_position(self, target):
        for view in self.chart_views:
            if view.chart() is not target['chart']:
                continue
            for _, hit in view._hit_regions:
                if (hit.get('bucket') is target['bucket'] and
                        hit.get('company') == target['company'] and
                        hit.get('group') == target['group'] and
                        hit.get('previous') == target['previous'] and
                        'hover_point' in hit):
                    return hit['hover_point']
        return target['chart'].mapToPosition(target['point'], target['series'])

    def _register_hover_target(self, chart, series, company, group, bucket, plotted,
                               scale, previous, key, color=None):
        dates = self._time_geometry()
        if plotted >= len(dates):
            return
        self._hover_targets.append({
            'chart': chart, 'series': series, 'company': company, 'group': group,
            'bucket': bucket, 'offset': (dates[plotted] - self.result.current_window[0]).total_seconds(),
            'point': QPointF(plotted, float(bucket.value) / scale), 'previous': previous,
            'key': key, 'color': QColor(color) if color is not None else self._legend_color(group),
        })

    def _series_hover(self, point, state, chart, series, company, group, segment,
                      previous, key):
        if not state:
            self.set_hover_offset(None)
            self.hover_offset_changed.emit(None)
            return
        if key in self._hidden_groups:
            return
        observed = next(((plotted, bucket) for plotted, bucket in segment
                         if abs(plotted - point.x()) < 1e-6
                         and abs(float(bucket.value) / self.axis_spec.scale - point.y()) < 1e-6),
                        None)
        if observed is None:
            return
        plotted, bucket = observed
        target = next((item for item in self._hover_targets
                       if item['chart'] is chart and item['series'] is series
                       and item['bucket'] is bucket), None)
        if target is not None:
            self._hide_hover_markers()
            self._show_hover_target(target)
            self.hover_offset_changed.emit(target['offset'])
        self._tooltip(company, group, bucket, previous)

    def _bar_hover(self, state, index, chart, series, company, group, buckets,
                   dates, previous, key):
        if not state:
            self.set_hover_offset(None)
            self.hover_offset_changed.emit(None)
            return
        if key in self._hidden_groups or not (0 <= index < len(dates)):
            return
        bucket = buckets.get(dates[index])
        if bucket is None or bucket.value is None:
            return
        target = next((item for item in self._hover_targets
                       if item['chart'] is chart and item['series'] is series
                       and item['bucket'] is bucket), None)
        if target is not None:
            self._hide_hover_markers()
            self._show_hover_target(target)
            self.hover_offset_changed.emit(target['offset'])
        self._tooltip(company, group, bucket, previous)

    def _open_fullscreen(self):
        if self.result is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self.title_label.text())
        dialog.setStyleSheet(f'QDialog {{ background: {tokens.PAGE_BG}; }}')
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(tokens.SPACE_LG, tokens.SPACE_LG,
                                  tokens.SPACE_LG, tokens.SPACE_LG)
        clone = ChartPanel(self.title_label.text(), default_mode=self.mode, parent=dialog,
                           modes=self.mode_selector is not None,
                           allowed_modes=self._allowed_modes if self._restricted_modes else None)
        clone.fullscreen_button.hide()
        clone._hidden_groups = set(self._hidden_groups)
        clone.set_company_palette({company: color.name() for company, color in self._company_palette.items()})
        clone.set_category_palette(self._category_palette)
        clone.set_mode_labels(self._mode_labels)
        clone.set_result(self.result, self.companies)
        clone.set_axis_spec(self._axis_override)
        layout.addWidget(clone)
        dialog.resize(1100, 700)
        self._fullscreen_dialog = dialog
        dialog.showMaximized()

    def set_mode(self, mode: str):
        previous_mode = self.mode
        if mode not in (*self.MODES, 'trend-bar', 'area'):
            raise ValueError(mode)
        if self._restricted_modes and mode not in self._allowed_modes:
            raise ValueError(mode)
        self.mode = mode
        if self.mode_selector is not None:
            if mode not in self._mode_items:
                self._add_mode_item(mode)
            self.mode_selector.blockSignals(True)
            self.mode_selector.setCurrentKey(mode)
            self.mode_selector.blockSignals(False)
        if self._settings is not None and self._settings_key and mode in (*self.MODES, 'area'):
            self._settings.setValue(self._settings_key, mode)
        self._render()
        if previous_mode != mode:
            self.surface_motion.reveal()

    def set_result(self, result, companies: dict[str, str] | None = None):
        self.result = result
        self.companies = companies or {}
        self._render()

    def set_axis_range(self, lower, upper, step):
        self.set_axis_spec(AxisSpec(int(lower), int(upper), int(step)))

    def set_axis_spec(self, spec: AxisSpec | None):
        if spec is not None and (spec.step <= 0 or spec.scale <= 0 or spec.upper <= spec.lower):
            raise ValueError('axis range')
        self._axis_override = spec
        self._render()

    def clear(self):
        self.result = None
        self._axis_override = None
        self.set_hover_offset(None)
        self._render()

    def _clear_views(self):
        if any(view._active_hit is not None for view in self.chart_views):
            QToolTip.hideText()
        self._hide_hover_markers()
        self._hover_markers = {}
        self._hover_targets = []
        self.hovered_bucket = None
        self._selected_value = None
        self._cached_time_geometry = None
        while self.chart_layout.count():
            item = self.chart_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.chart_views = []
        self.company_labels = []
        self._category_items = {}
        self._category_markers = {}
        self._bar_entries = {}

    def _register_category(self, group, item, marker):
        self._category_items.setdefault(group, []).append(
            (item, None if isinstance(item, (QLineSeries, QAreaSeries)) else item.brush()))
        if marker is not None:
            self._category_markers.setdefault(group, []).append(marker)
            marker.clicked.connect(lambda g=group: self._toggle_category(g))
        self._apply_category(group)

    def _toggle_category(self, group):
        if group in self._hidden_groups:
            self._hidden_groups.remove(group)
        else:
            self._hidden_groups.add(group)
        self._apply_category(group)
        self._refresh_value_content()

    def _apply_category(self, group):
        visible = group not in self._hidden_groups
        if group in self.legend_buttons:
            self.legend_buttons[group].setChecked(visible)
        for item, original_brush in self._category_items.get(group, []):
            if isinstance(item, (QLineSeries, QAreaSeries)):
                item.setVisible(visible)
            else:
                item.setBrush(original_brush if visible else QBrush(QColor(0, 0, 0, 0)))
                if isinstance(item, QPieSlice):
                    item.setLabelVisible(visible)
        for marker in self._category_markers.get(group, []):
            marker.setBrush(QBrush(self._legend_color(group) if visible else QColor(tokens.TEXT_DISABLED)))
        for bar_set, index, original in self._bar_entries.get(group, []):
            bar_set.replace(index, original if visible else 0)
        for view in self.chart_views:
            view.viewport().update()

    def _fluent_hover(self, hit):
        kind = hit['type']
        if kind == 'time-hit':
            target = next((item for item in self._hover_targets
                           if item['bucket'] is hit['bucket'] and
                           item['company'] == hit['company'] and
                           item['previous'] == hit['previous']), None)
            if target is not None:
                self._hide_hover_markers()
                self._show_hover_target(target)
                marker = self._hover_markers.get(target['chart'])
                if marker is not None and 'hover_point' in hit:
                    marker.setPos(hit['hover_point'])
                self.hover_offset_changed.emit(target['offset'])
            self._tooltip(hit['company'], hit['group'], hit['bucket'],
                          hit['previous'], hit.get('color'))
        elif kind == 'total-hit':
            window = (self.result.comparison_window if hit['previous'] else
                      self.result.current_window)
            if window:
                self._total_tooltip(hit['company'], hit['group'], hit['value'], window)
        elif kind == 'pie-slice-hit':
            window = self.result.current_window
            parts = (self._company_name(hit['company']), group_label(hit['group']),
                     window[0].strftime('%Y-%m-%d %H:%M'),
                     window[1].strftime('%Y-%m-%d %H:%M'),
                     f"{hit['percent']:.1f}%",
                     label(self.result.query.metric), _number(hit['value']),
                     self.result.metric.unit)
            self._show_color_tooltip(
                ' · '.join(part for part in parts if part), hit['color'])

    def _show_color_tooltip(self, message: str, color: QColor) -> None:
        """Keep the hover dot on the exact series hue in the Fluent tooltip."""
        dot = QColor(color).name()
        QToolTip.showText(QCursor.pos(),
                          f'<span style="color:{dot}">●</span> {escape(message)}', self)

    def _groups(self):
        grouped = {}
        if self.result is not None:
            for (company, group), buckets in self.result.series.items():
                grouped.setdefault(company, {})[group] = buckets
        return grouped

    def _company_name(self, company):
        return self.companies.get(company, company)

    def _render(self):
        self._clear_views()
        self._base_axis_spec = None
        self.axis_spec = None
        groups = self._groups()
        self._company_count = len(groups)
        total_groups = {next(iter(entries)) for entries in groups.values() if len(entries) == 1}
        self._combined_totals = (self.mode in ('line', 'area', 'trend-bar') and len(groups) > 1
                                 and all(len(entries) == 1 for entries in groups.values())
                                 and len(total_groups) == 1
                                 and next(iter(total_groups)) in ('总计', '__total__', ''))
        period_key = bool(self.result and self.result.comparison and self.mode in ('line', 'area', 'trend-bar', 'bar'))
        self.period_label.setVisible(period_key)
        if period_key:
            glyphs = ('━', '┄') if self.mode in ('line', 'area') else ('■', '▫')
            self.period_label.setText(f'{glyphs[0]}  {label("current")}     {glyphs[1]}  {label("comparison-value")}')
        self.summary_values = {}
        self.summary_label.setVisible(self.mode == 'summary' or self.result is None)
        self.chart_host.setVisible(self.mode != 'summary' and self.result is not None)
        self.fullscreen_button.setEnabled(self.result is not None and self.mode != 'summary')
        if self.result is None:
            self.summary_label.setText(label('missing'))
            self._build_legend(groups)
            self._refresh_value_content()
            return
        if not groups:
            self.chart_host.hide()
            self.summary_label.setText('暂无可用数据')
            self.summary_label.show()
            self.fullscreen_button.setEnabled(False)
            self._build_legend(groups)
            self._refresh_value_content()
            return
        for company, categories in groups.items():
            values = [summarize_buckets(buckets, self.result.metric) for buckets in categories.values()]
            valid = [value for value in values if value is not None]
            if valid:
                self.summary_values[company] = sum(valid, Decimal(0))
        if self.mode == 'summary':
            self.summary_label.setText('\n'.join(
                f'{self._company_name(company)}  {_number(self.summary_values.get(company))} {self.result.metric.unit}'
                for company in groups) or label('missing'))
            self._build_legend(groups)
            self._refresh_value_content()
            return
        if self.mode in ('line', 'area'):
            (self._combined_time_charts if self._combined_totals else self._time_charts)(groups)
        elif self.mode == 'trend-bar':
            (self._combined_time_bars if self._combined_totals else self._time_bars)(groups)
        elif self.mode == 'bar':
            self._bar_charts(groups)
        elif self.mode == 'pie':
            self._pie_charts(groups)
        self._apply_empty_chart_states()
        self._build_legend(groups)
        self._position_mode_selector()
        self._position_legend()
        self._adapt_axes()
        self._refresh_value_content()

    def _apply_empty_chart_states(self):
        for view in self.chart_views:
            def has_value(visual):
                kind = visual['type']
                if kind == 'line':
                    return bool(visual['points'])
                if kind in ('time-bars', 'horizontal-bars'):
                    return any(value is not None for entry in visual['sets']
                               for value in entry['values'])
                if kind == 'pie':
                    return bool(visual['slices'])
                return False
            if any(has_value(visual) for visual in view.visuals):
                continue
            view.visuals = [{'type': 'empty', 'text': '暂无可用数据'}]
            view.unit_text = ''
            for axis in view.chart().axes():
                axis.setVisible(False)
            view.viewport().update()

    def _chart(self, title=''):
        chart = QChart()
        chart_parent = self.chart_host
        chart_layout = self.chart_layout
        if self._detailed:
            chart_parent = QWidget(self.chart_host)
            chart_parent.setMinimumWidth(0)
            chart_layout = QVBoxLayout(chart_parent)
            chart_layout.setContentsMargins(0, 0, 0, 0)
            chart_layout.setSpacing(4)
            self.chart_layout.addWidget(chart_parent, 1)
        if title:
            heading = QLabel(title, chart_parent)
            heading.setFont(QFont('Microsoft YaHei UI'))
            heading.setWordWrap(True)
            heading.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            heading.setStyleSheet(f'color: {tokens.TEXT_PRIMARY}; '
                                  f'font-size: {tokens.FONT_SIZE_CAPTION}px; border: 0;')
            chart_layout.addWidget(heading)
            self.company_labels.append(heading)
        chart.setTitleFont(_CHART_FONT)
        chart.setTitleBrush(QBrush(QColor(tokens.TEXT_PRIMARY)))
        chart.setBackgroundVisible(False)
        chart.setPlotAreaBackgroundVisible(False)
        chart.setMargins(QMargins(0, 0, 0, 0) if self._compact_layout or
                         self._compact_height is not None else QMargins(4, 4, 4, 4))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.legend().setMarkerShape(chart.legend().MarkerShape.MarkerShapeCircle)
        chart.legend().setFont(_CHART_FONT)
        chart.legend().hide()
        view = FluentChartView(chart, self, chart_parent)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setFrameShape(QFrame.Shape.NoFrame)
        view.setStyleSheet(f'background: {tokens.CARD_BG}; border: 0;')
        view.setMinimumHeight(self._chart_minimum(
            195 if self._compact_layout and self.mode != 'pie' else
            200 if self._company_count > 1 and self.mode == 'pie' else
            185 if self._company_count > 1 else 210))
        chart_layout.addWidget(view, 1)
        self.chart_views.append(view)
        chart.plotAreaChanged.connect(lambda area: self._adapt_axes())
        chart.plotAreaChanged.connect(lambda area: self._position_hover_markers())
        return chart

    def _position_hover_markers(self):
        if self.hovered_bucket is None:
            return
        for chart, target in self._active_hover_targets.items():
            marker = self._hover_markers.get(chart)
            if marker is not None and marker.isVisible():
                marker.setPos(self._hover_position(target))

    def _value_axis(self, values, horizontal=False):
        self.axis_spec = self._axis_override or nice_axis(values)
        self._base_axis_spec = self.axis_spec
        axis = QValueAxis()
        axis.setRange(self.axis_spec.lower, self.axis_spec.upper)
        axis.setTickInterval(self.axis_spec.step)
        axis.setTickType(QValueAxis.TickType.TicksDynamic)
        axis.setTickAnchor(self.axis_spec.lower)
        axis.setLabelFormat('%d')
        axis.setTruncateLabels(False)
        axis.setLabelsFont(self._axis_font())
        axis.setTitleFont(self._axis_font())
        axis.setLabelsColor(QColor(tokens.TEXT_SECONDARY))
        grid_pen = QPen(QColor(tokens.GRID_COLOR))
        grid_pen.setWidthF(tokens.CHART_GRID_WIDTH)
        axis.setGridLinePen(grid_pen)
        axis.setLineVisible(False)
        axis.setMinorTickCount(1 if self._detailed else 0)
        minor = QColor(tokens.GRID_COLOR)
        minor.setAlphaF(.4)
        axis.setMinorGridLinePen(QPen(minor, .5))
        axis.setMinorGridLineVisible(self._detailed)
        axis.setGridLineVisible(self._detailed or not horizontal)
        if self.result.metric.unit or self.axis_spec.unit_suffix:
            axis.setTitleText(self.axis_spec.unit_suffix + self.result.metric.unit)
            axis.setTitleVisible(False)
            if self.chart_views:
                self.chart_views[-1].unit_text = self.axis_spec.unit_suffix + self.result.metric.unit
        return axis

    def _adapt_axes(self):
        if self._detailed:
            if not self._configuring_detail and not self._adapting_axis:
                self._adapting_axis = True
                try:
                    self._update_detail_axes()
                finally:
                    self._adapting_axis = False
            return
        if self._adapting_axis or self._base_axis_spec is None or self._axis_override is not None:
            return
        self._adapting_axis = True
        try:
            base = self._base_axis_spec
            horizontal = self.mode == 'bar'
            extents = [(view.chart().plotArea().width() if horizontal else view.chart().plotArea().height())
                       for view in self.chart_views]
            # Qt reports a transient near-zero plot area while layouts settle.
            if not extents or min(extents) < 60:
                return
            extent = min(extents)
            minimum_ticks = 3 if base.lower < 0 < base.upper else 2
            max_ticks = min(7, max(minimum_ticks, int(extent / (45 if horizontal else 32)) + 1))
            step = base.step
            lower, upper = base.lower, base.upper
            while (upper - lower) // step + 1 > max_ticks:
                magnitude = 10 ** (len(str(step)) - 1)
                step = next(unit * magnitude for unit in (1, 2, 5, 10) if unit * magnitude > step)
                lower = floor(base.lower / step) * step
                upper = ceil(base.upper / step) * step
            effective = AxisSpec(lower, upper, step, base.scale, base.unit_suffix)
            for view in self.chart_views:
                chart = view.chart()
                axis = next((item for item in chart.axes(Qt.Orientation.Horizontal if horizontal else Qt.Orientation.Vertical)
                             if isinstance(item, QValueAxis)), None)
                if axis is not None and (axis.min(), axis.max(), axis.tickInterval()) != (lower, upper, step):
                    axis.setRange(lower, upper)
                    axis.setTickAnchor(lower)
                    axis.setTickInterval(step)
                for visual in view.visuals:
                    if 'axis' in visual:
                        visual['axis'] = effective
                view.viewport().update()
            self.axis_spec = effective
        finally:
            self._adapting_axis = False

    def _style_category_axis(self, axis):
        if isinstance(axis, (QBarCategoryAxis, QCategoryAxis)):
            axis.setTruncateLabels(False)
        axis.setLabelsFont(self._axis_font())
        axis.setTitleFont(self._axis_font())
        axis.setLabelsColor(QColor(tokens.TEXT_SECONDARY))
        axis.setLineVisible(False)
        axis.setGridLineVisible(False)

    def _tooltip(self, company, group, bucket, previous=False, color=None):
        if bucket is None or bucket.value is None:
            return
        parts = [self._company_name(company), group_label(group),
                 (label('comparison-value') if previous else label('current'))
                 if self.result.comparison else '',
                 bucket.start.strftime('%Y-%m-%d %H:%M'),
                 label(self.result.query.metric), _number(bucket.value), self.result.metric.unit]
        self._show_color_tooltip(
            ' · '.join(part for part in parts if part),
            QColor(color) if color is not None else self._legend_color(group))

    def _total_tooltip(self, company, group, value, window):
        if value is None:
            return
        parts = [self._company_name(company), group_label(group),
                 (label('comparison-value') if window == self.result.comparison_window
                  else label('current')) if self.result.comparison_window else '',
                 window[0].strftime('%Y-%m-%d %H:%M'), window[1].strftime('%Y-%m-%d %H:%M'),
                 label(self.result.query.metric), _number(value), self.result.metric.unit]
        self._show_color_tooltip(
            ' · '.join(part for part in parts if part), self._legend_color(group))

    def _time_geometry(self):
        if self._cached_time_geometry is not None:
            return self._cached_time_geometry
        start, end = self.result.current_window
        grain = self.result.query.grain

        def periods(first, last):
            count = 0
            while first < last:
                first = min(last, period_bounds(first, grain)[1])
                count += 1
            return count

        count = periods(start, end)
        if self.result.comparison_window:
            count = max(count, periods(*self.result.comparison_window))
        count = max(1, count, *(len(buckets) for source in (self.result.series, self.result.comparison)
                                for buckets in source.values()))
        slots = []
        cursor = start
        for _ in range(count):
            slots.append(cursor)
            cursor = period_bounds(cursor, grain)[1]
        self._cached_time_geometry = slots
        return slots

    def _time_label_text(self, date, dates):
        cross_year = dates[0].year != dates[-1].year
        pattern = ('%Y-%m-%d' if cross_year or self._detailed else '%m-%d')
        if self.result.query.grain == 'hour':
            pattern += ' %H:%M'
        return date.strftime(pattern)

    def _set_time_labels(self, axis, dates, target, edge_slots=0):
        start, end = self._detail_range if self._detailed else (0, len(dates))
        first, last = start + edge_slots, end - 1 - edge_slots
        target = min(target, last - first + 1)
        stride = max(1, ceil((last - first) / max(1, target - 1)))
        indices = (list(range(first, last + 1, stride)) if self._detailed and target > 1 else
                   sorted({first + round(i * (last - first) / (target - 1)) for i in range(target)})
                   if target > 1 else [len(dates) // 2])
        labels = [self._time_label_text(dates[index], dates) for index in indices]
        if axis.categoriesLabels() == labels:
            return
        for old in axis.categoriesLabels():
            axis.remove(old)
        for index, text in zip(indices, labels):
            axis.append(text, index)

    def _adapt_time_label_axis(self, axis, dates, width):
        if self.result is None or not dates or self._adapting_time_labels or width < 60:
            return
        metrics = QFontMetrics(self._axis_font())
        label_width = max(metrics.horizontalAdvance(self._time_label_text(date, dates)) for date in dates)
        spacing = max(70, label_width + 32)
        count = self._detail_range[1] - self._detail_range[0] if self._detailed else len(dates)
        target = min(8 if self._detailed else 4, count, max(1, int(width / spacing)))
        edge_slots = min((count - 1) // 2,
                         max(0, ceil((label_width / 2 + 8) * count / width - .5)))
        self._adapting_time_labels = True
        try:
            self._set_time_labels(axis, dates, target, edge_slots)
        finally:
            self._adapting_time_labels = False

    def _time_label_axis(self, chart, dates):
        axis = QCategoryAxis()
        axis.setRange(-.5, len(dates) - .5)
        axis.setStartValue(-.5)
        axis.setLabelsPosition(QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionOnValue)
        axis.setGridLineVisible(False)
        self._set_time_labels(axis, dates, min(4, len(dates)))
        self._style_category_axis(axis)
        chart.plotAreaChanged.connect(lambda area, a=axis, ds=dates:
                                      self._adapt_time_label_axis(a, ds, area.width()))
        return axis

    def _append_time_segments(self, chart, xaxis, yaxis, company, group, source,
                              previous, color, key, name, scale):
        segments, active = [], []
        for plotted, bucket in enumerate(source):
            if bucket.value is None:
                if active:
                    segments.append(active)
                    active = []
            else:
                active.append((plotted, bucket))
        if active:
            segments.append(active)
        for segment_number, segment in enumerate(segments):
            upper = QLineSeries()
            for plotted, bucket in segment:
                upper.append(plotted, float(bucket.value) / scale)
            pen_color = QColor(color)
            if previous:
                pen_color.setAlphaF(tokens.CHART_COMPARISON_OPACITY)
            pen = QPen(pen_color)
            pen.setWidthF(tokens.CHART_LINE_WIDTH)
            if previous:
                pen.setStyle(Qt.PenStyle.DashLine)
            if self.mode == 'area':
                self._area_boundaries = [boundary for boundary in self._area_boundaries
                                         if shiboken6.isValid(boundary)]
                series = QAreaSeries(upper)
                self._area_boundaries.append(upper)
                fill = QColor(color)
                fill.setAlphaF(tokens.CHART_AREA_OPACITY *
                               (tokens.CHART_COMPARISON_OPACITY if previous else 1))
                series.setBrush(QBrush(fill))
                series.setPen(pen)
            else:
                series = upper
                series.setPen(pen)
                series.setPointsVisible(len(source) <= 12)
            series.setName(name)
            chart.addSeries(series)
            series.attachAxis(xaxis)
            series.attachAxis(yaxis)
            series.setOpacity(0)
            self.chart_views[-1].add_visual({
                'type': 'line', 'points': [(plotted, float(bucket.value) / scale, bucket)
                                           for plotted, bucket in segment],
                'count': len(self._time_geometry()), 'axis': self.axis_spec,
                'color': QColor(color), 'previous': previous, 'area': True,
                'company': company, 'group': group, 'key': key,
            })
            series.hovered.connect(
                lambda point, state, c=company, g=group, bs=segment, p=previous,
                       k=key, s=series, ch=chart:
                self._series_hover(point, state, ch, s, c, g, bs, p, k))
            for plotted, bucket in segment:
                self._register_hover_target(chart, series, company, group, bucket,
                                            plotted, scale, previous, key, color)
            marker = chart.legend().markers(series)[0]
            if segment_number or previous:
                marker.setVisible(False)
                marker = None
            self._register_category(key, series, marker)

    def _time_charts(self, grouped):
        all_values = [bucket.value for source in (self.result.series, self.result.comparison)
                      for buckets in source.values() for bucket in buckets if bucket.value is not None]
        axis = self._axis_override or nice_axis(all_values)
        dates = self._time_geometry()
        for company, categories in grouped.items():
            chart = self._chart(self._company_name(company) if len(grouped) > 1 and company else '')
            xaxis = self._time_label_axis(chart, dates)
            chart.addAxis(xaxis, Qt.AlignmentFlag.AlignBottom)
            yaxis = self._value_axis(all_values)
            self.axis_spec = axis
            yaxis.setRange(axis.lower, axis.upper)
            chart.addAxis(yaxis, Qt.AlignmentFlag.AlignLeft)
            for group, buckets in categories.items():
                compare = self.result.comparison.get((company, group), [])
                for previous, source in ((False, buckets), (True, compare)):
                    color = self._category_color(group) if len(categories) > 1 else self._company_color(company)
                    suffix = label('comparison-value') if previous else label('current')
                    name = f'{group_label(group)} · {suffix}' if compare else group_label(group)
                    self._append_time_segments(chart, xaxis, yaxis, company, group, source,
                                               previous, color, group, name, axis.scale)

    def _combined_time_charts(self, grouped):
        values = [bucket.value for source in (self.result.series, self.result.comparison)
                  for buckets in source.values() for bucket in buckets if bucket.value is not None]
        axis = self._axis_override or nice_axis(values)
        dates = self._time_geometry()
        chart = self._chart()
        self.chart_views[-1].setMinimumHeight(
            self._chart_minimum(195 if self._compact_layout else 210))
        xaxis = self._time_label_axis(chart, dates)
        chart.addAxis(xaxis, Qt.AlignmentFlag.AlignBottom)
        yaxis = self._value_axis(values)
        yaxis.setRange(axis.lower, axis.upper)
        chart.addAxis(yaxis, Qt.AlignmentFlag.AlignLeft)
        for company, categories in grouped.items():
            group, buckets = next(iter(categories.items()))
            comparison = self.result.comparison.get((company, group), [])
            for previous, source in ((False, buckets), (True, comparison)):
                name = self._company_name(company) + ' · ' + (
                    label('comparison-value') if previous else label('current'))
                self._append_time_segments(chart, xaxis, yaxis, company, group, source,
                                           previous, self._company_color(company), company,
                                           name, axis.scale)

    def _combined_time_bars(self, grouped):
        values = [bucket.value for source in (self.result.series, self.result.comparison)
                  for buckets in source.values() for bucket in buckets if bucket.value is not None]
        axis = self._axis_override or nice_axis(values)
        chart = self._chart()
        self.chart_views[-1].setMinimumHeight(
            self._chart_minimum(195 if self._compact_layout else 210))
        projected = {}
        dates = self._time_geometry()
        for company, categories in grouped.items():
            group, buckets = next(iter(categories.items()))
            comparison = self.result.comparison.get((company, group), [])
            current_by_date = {dates[index]: bucket for index, bucket in enumerate(buckets)}
            compared_by_date = {dates[index]: bucket for index, bucket in enumerate(comparison)}
            projected[company] = (group, current_by_date, compared_by_date)
        series = QBarSeries()
        ownership = []
        for company, (group, current, previous) in projected.items():
            for compared, source in ((False, current), (True, previous)):
                if compared and not source:
                    continue
                bar_set = QBarSet(self._company_name(company) + ' · ' +
                                  (label('comparison-value') if compared else label('current')))
                color = QColor(self._company_color(company))
                if compared:
                    color.setAlphaF(tokens.CHART_COMPARISON_OPACITY)
                bar_set.setColor(color)
                bar_set.setBrush(QBrush(QColor(0, 0, 0, 0)))
                bar_set.setBorderColor(QColor(0, 0, 0, 0))
                for date in dates:
                    bucket = source.get(date)
                    bar_set.append(float(bucket.value) / axis.scale if bucket and bucket.value is not None else 0)
                bar_set.hovered.connect(lambda state, index, c=company, g=group,
                                               bs=source, ds=dates, p=compared:
                                        self._bar_hover(state, index, chart, series, c, g,
                                                        bs, ds, p, c))
                series.append(bar_set)
                ownership.append((company, bar_set))
                for plotted, date in enumerate(dates):
                    bucket = source.get(date)
                    if bucket is not None and bucket.value is not None:
                        self._register_hover_target(chart, series, company, group,
                                                    bucket, plotted, axis.scale, compared, company)
        chart.addSeries(series)
        series.setOpacity(0)
        self.chart_views[-1].add_visual({
            'type': 'time-bars', 'dates': dates, 'axis': axis,
            'sets': [dict(company=company, group=group, key=company,
                          previous=compared, color=self._company_color(company),
                          values=[float(source.get(date).value) / axis.scale
                                  if source.get(date) and source.get(date).value is not None else None
                                  for date in dates],
                          buckets=[source.get(date) for date in dates])
                     for company, (group, current, previous) in projected.items()
                     for compared, source in ((False, current), (True, previous))
                     if source],
        })
        for index, (company, bar_set) in enumerate(ownership):
            self._register_category(company, bar_set, chart.legend().markers(series)[index])
        xaxis = QBarCategoryAxis()
        xaxis.append([date.strftime('%m-%d' if self.result.query.grain != 'hour' else '%d %H:%M') for date in dates])
        self._style_category_axis(xaxis)
        xaxis.setLabelsVisible(False)
        chart.addAxis(xaxis, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(xaxis)
        chart.addAxis(self._time_label_axis(chart, dates), Qt.AlignmentFlag.AlignBottom)
        yaxis = self._value_axis(values)
        yaxis.setRange(axis.lower, axis.upper)
        chart.addAxis(yaxis, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(yaxis)

    def _bar_charts(self, grouped):
        aggregates = {company: {group: summarize_buckets(buckets, self.result.metric)
                                for group, buckets in categories.items()}
                      for company, categories in grouped.items()}
        compared = {company: {group: summarize_buckets(self.result.comparison.get((company, group), []), self.result.metric)
                              for group in categories}
                    for company, categories in grouped.items()}
        values = [value for source in (aggregates, compared) for categories in source.values()
                  for value in categories.values() if value is not None]
        axis = self._axis_override or nice_axis(values)
        for company, categories in aggregates.items():
            chart = self._chart(self._company_name(company) if company else '')
            minimum = 185 if len(aggregates) > 1 else 210
            if self._compact_layout:
                minimum = 195
            if len(categories) >= 4:
                minimum = max(minimum, 120 + len(categories) * 26)
            self.chart_views[-1].setMinimumHeight(self._chart_minimum(minimum))
            series = QHorizontalBarSeries()
            names = list(categories)
            current_set = QBarSet(label('current'))
            current_set.setColor(self._company_color(company))
            current_set.setBrush(QBrush(QColor(0, 0, 0, 0)))
            current_set.setBorderColor(QColor(0, 0, 0, 0))
            previous_set = QBarSet(label('comparison-value')) if self.result.comparison else None
            if previous_set:
                compare_color = QColor(self._company_color(company))
                compare_color.setAlphaF(tokens.CHART_COMPARISON_OPACITY)
                previous_set.setColor(compare_color)
                previous_set.setBrush(QBrush(QColor(0, 0, 0, 0)))
                previous_set.setBorderColor(QColor(0, 0, 0, 0))
            for index, group in enumerate(names):
                value = categories[group]
                raw = float(value) / axis.scale if value is not None else 0
                current_set.append(raw)
                self._bar_entries.setdefault(group, []).append((current_set, index, raw))
                if previous_set:
                    previous = compared[company][group]
                    old_raw = float(previous) / axis.scale if previous is not None else 0
                    previous_set.append(old_raw)
                    self._bar_entries[group].append((previous_set, index, old_raw))
            current_set.hovered.connect(lambda state, index, c=company, gs=names, vals=categories:
                                        self._total_tooltip(c, gs[index], vals[gs[index]], self.result.current_window)
                                        if state and 0 <= index < len(gs) and gs[index] not in self._hidden_groups else None)
            series.append(current_set)
            if previous_set:
                previous_set.hovered.connect(lambda state, index, c=company, gs=names, vals=compared[company]:
                                             self._total_tooltip(c, gs[index], vals[gs[index]], self.result.comparison_window)
                                             if state and 0 <= index < len(gs) and gs[index] not in self._hidden_groups
                                             and self.result.comparison_window else None)
                series.append(previous_set)
            chart.addSeries(series)
            series.setOpacity(0)
            self.chart_views[-1].add_visual({
                'type': 'horizontal-bars', 'names': names, 'axis': axis,
                'sets': [dict(company=company, previous=previous,
                              colors=[self._category_color(group) if len(categories) > 1
                                      else self._company_color(company) for group in names],
                              values=[float(source[group]) / axis.scale if source[group] is not None
                                      else None for group in names],
                              raw_values=[source[group] for group in names])
                         for previous, source in ((False, categories), (True, compared[company]))
                         if not previous or previous_set is not None],
            })
            categories_axis = QBarCategoryAxis()
            categories_axis.append([group_label(group) for group in names])
            self._style_category_axis(categories_axis)
            chart.addAxis(categories_axis, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(categories_axis)
            value_axis = self._value_axis(values, horizontal=True)
            self.axis_spec = axis
            value_axis.setRange(axis.lower, axis.upper)
            chart.addAxis(value_axis, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(value_axis)

    def _time_bars(self, grouped):
        all_values = [bucket.value for source in (self.result.series, self.result.comparison)
                      for buckets in source.values() for bucket in buckets if bucket.value is not None]
        axis = self._axis_override or nice_axis(all_values)
        dates = self._time_geometry()
        for company, categories in grouped.items():
            chart = self._chart(self._company_name(company) if len(grouped) > 1 and company else '')
            series = QBarSeries()
            bar_groups = []
            for group, buckets in categories.items():
                indexed = {dates[index]: bucket for index, bucket in enumerate(buckets)}
                bar_set = QBarSet(group_label(group))
                bar_set.setColor(self._category_color(group) if len(categories) > 1 else self._company_color(company))
                bar_set.setBrush(QBrush(QColor(0, 0, 0, 0)))
                bar_set.setBorderColor(QColor(0, 0, 0, 0))
                for date in dates:
                    bucket = indexed.get(date)
                    bar_set.append(float(bucket.value) / axis.scale if bucket and bucket.value is not None else 0)
                bar_set.hovered.connect(lambda state, index, c=company, g=group,
                                               bs=indexed, ds=dates:
                                        self._bar_hover(state, index, chart, series, c, g,
                                                        bs, ds, False, g))
                series.append(bar_set)
                bar_groups.append(group)
                for plotted, date in enumerate(dates):
                    bucket = indexed.get(date)
                    if bucket is not None and bucket.value is not None:
                        self._register_hover_target(chart, series, company, group,
                                                    bucket, plotted, axis.scale, False, group)
                comparison = self.result.comparison.get((company, group), [])
                if comparison:
                    compared = QBarSet(group_label(group) + ' · ' + label('comparison-value'))
                    compare_color = QColor(self._category_color(group) if len(categories) > 1
                                           else self._company_color(company))
                    compare_color.setAlphaF(tokens.CHART_COMPARISON_OPACITY)
                    compared.setColor(compare_color)
                    compared.setBrush(QBrush(QColor(0, 0, 0, 0)))
                    compared.setBorderColor(QColor(0, 0, 0, 0))
                    by_date = {dates[index]: bucket for index, bucket in enumerate(comparison)}
                    for date in dates:
                        bucket = by_date.get(date)
                        compared.append(float(bucket.value) / axis.scale if bucket and bucket.value is not None else 0)
                    compared.hovered.connect(lambda state, index, c=company, g=group,
                                                    bs=by_date, ds=dates:
                                             self._bar_hover(state, index, chart, series, c, g,
                                                             bs, ds, True, g))
                    series.append(compared)
                    bar_groups.append(group)
                    for plotted, date in enumerate(dates):
                        bucket = by_date.get(date)
                        if bucket is not None and bucket.value is not None:
                            self._register_hover_target(chart, series, company, group,
                                                        bucket, plotted, axis.scale, True, group)
            chart.addSeries(series)
            series.setOpacity(0)
            self.chart_views[-1].add_visual({
                'type': 'time-bars', 'dates': dates, 'axis': axis,
                'sets': [dict(company=company, group=group, key=group,
                              previous=previous, color=(self._category_color(group)
                                  if len(categories) > 1 else self._company_color(company)),
                              values=[float(source.get(date).value) / axis.scale
                                      if source.get(date) and source.get(date).value is not None
                                      else None for date in dates],
                              buckets=[source.get(date) for date in dates])
                         for group, buckets in categories.items()
                         for previous, source in ((False, {dates[i]: bucket for i, bucket in enumerate(buckets)}),
                                                  (True, {dates[i]: bucket for i, bucket in enumerate(
                                                      self.result.comparison.get((company, group), []))}))
                         if source],
            })
            for index, bar_set in enumerate(series.barSets()):
                group = bar_groups[index]
                self._register_category(group, bar_set, chart.legend().markers(series)[index])
            xaxis = QBarCategoryAxis()
            xaxis.append([date.strftime('%m-%d' if self.result.query.grain != 'hour' else '%d %H:%M')
                          for date in dates])
            self._style_category_axis(xaxis)
            xaxis.setLabelsVisible(False)
            chart.addAxis(xaxis, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(xaxis)
            chart.addAxis(self._time_label_axis(chart, dates), Qt.AlignmentFlag.AlignBottom)
            yaxis = self._value_axis(all_values)
            self.axis_spec = axis
            yaxis.setRange(axis.lower, axis.upper)
            chart.addAxis(yaxis, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(yaxis)

    def _pie_charts(self, grouped):
        for company, categories in grouped.items():
            chart = self._chart(self._company_name(company))
            series = QPieSeries()
            values = {group: summarize_buckets(buckets, self.result.metric)
                      for group, buckets in categories.items()}
            positive = {group: value for group, value in values.items() if value is not None and value > 0}
            total = sum(positive.values(), Decimal(0))
            self.chart_views[-1].add_visual({
                'type': 'pie', 'slices': [dict(company=company, group=group, key=group,
                                            value=value, color=self._category_color(group))
                                      for group, value in positive.items()],
                'total_text': _number(total), 'unit': self.result.metric.unit,
            } if positive else {'type': 'empty', 'text': label('missing')})
            for group, value in positive.items():
                percent = value / total * 100
                slice_ = series.append(f'{group_label(group)} {percent:.1f}%', float(value))
                slice_.setBrush(self._category_color(group))
                slice_.setBrush(QBrush(QColor(0, 0, 0, 0)))
                slice_.setPen(QPen(QColor(0, 0, 0, 0)))
                slice_.setLabelFont(_CHART_FONT)
                slice_.setLabelPosition(QPieSlice.LabelPosition.LabelOutside)
                slice_.setLabelVisible(False)
                slice_.hovered.connect(lambda state, c=company, g=group, v=value:
                                       QToolTip.showText(QCursor.pos(),
                                                         ' · '.join((self._company_name(c), group_label(g),
                                                                     label(self.result.query.metric), _number(v), self.result.metric.unit)), self)
                                       if state and g not in self._hidden_groups else None)
            if series.count():
                chart.addSeries(series)
                series.setOpacity(0)
                for group, slice_, marker in zip(positive,
                                                  series.slices(), chart.legend().markers(series)):
                    self._register_category(group, slice_, marker)
            else:
                chart.setTitle('')
