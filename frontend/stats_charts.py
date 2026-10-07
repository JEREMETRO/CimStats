"""Dashboard chart cards. Values stay in their original units in Result.

``ChartPanel`` turns a statistics ``Result`` into :class:`chart_canvas.ChartData`
and owns the card chrome around it: title, mode switch, legend chips and the
full-screen view. All drawing lives in :mod:`chart_canvas`.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
from math import ceil, floor
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QVBoxLayout, QWidget)
from qfluentwidgets import FluentIcon, TransparentPushButton, TransparentToolButton

from chart_canvas import AxisSpec, ChartCanvas, ChartData, Series, format_value, auto_axis
from display_rules import number_places
from chart_details import DetailSummary, InlineChartDetail
from shiboken6 import isValid
from stats_controls import FluentSegmentedControl
from stats_text import group_label, label
from stats_typography import apply_emphasis_font, emphasis_css
import stats_tokens as tokens
from stats_elevation import attach_card_elevation
from stats_motion import SurfaceMotion, attach_surface_reveal
from statistics_model import period_bounds, summarize_buckets
from ui_kit import FlowHost, LegendChip, SeriesLegend

__all__ = ['AxisSpec', 'ChartPanel', 'nice_axis', 'company_color']

MODE_NAMES = {'line': '趋势', 'area': '趋势', 'trend-bar': '趋势', 'bar': '分布', 'pie': '比例',
              'summary': '总量'}
TOTAL_GROUPS = ('总计', '__total__', '')
WEEKDAYS = '一二三四五六日'
_FONT_ID = -1


def _ensure_chinese_font():
    global _FONT_ID
    if _FONT_ID < 0:
        font_path = Path('C:/Windows/Fonts/msyh.ttc')
        if font_path.is_file():
            _FONT_ID = QFontDatabase.addApplicationFont(str(font_path))


def nice_axis(values, *, max_ticks=7, decimal_places=0) -> AxisSpec:
    """Zero-based shared integer axis used when several cards must align."""
    return auto_axis(values, zero=True, max_ticks=max_ticks, decimal_places=decimal_places)


def shared_axis_budget(panels):
    return min((view.axis_tick_budget() for panel in panels for view in getattr(panel, 'chart_views', ())), default=7)


def _stable_color(key: str, palette: tuple[str, ...]) -> QColor:
    from semantic_colors import stable_color
    return QColor(stable_color(key, palette))


def company_color(company_id: str) -> QColor:
    from semantic_colors import color_for
    return QColor(color_for('company', company_id))


def category_color(group: str, palette: tuple[str, ...] | None = None) -> QColor:
    from semantic_colors import category_color_hex
    return QColor(category_color_hex(group, palette))


def _number(value: Decimal | None, metric=None) -> str:
    return format_value(value, number_places(metric))


class ChartPanel(QFrame):
    """One chart card. Subclasses customise through the small ``_hook`` methods."""

    hover_offset_changed = Signal(object)
    MODES = ('summary', 'bar', 'line', 'pie')
    ALL_MODES = (*MODES, 'trend-bar', 'area')

    def __init__(self, title: str, modes: bool = False, default_mode: str = 'line',
                 settings=None, settings_key: str = '', parent=None,
                 allowed_modes: tuple[str, ...] | None = None):
        super().__init__(parent)
        _ensure_chinese_font()
        self.setObjectName('chartPanel')
        self._detailed = isinstance(parent, QDialog) or bool(parent and parent.property('chartDetailSurface'))
        if not self._detailed:
            attach_card_elevation(self, radius=tokens.RADIUS_CARD)
        self.surface_motion = SurfaceMotion(self)
        attach_surface_reveal(self, self.surface_motion)
        self.setStyleSheet(
            f'QFrame#chartPanel {{ background: {tokens.CARD_BG}; border: 0; }}' if self._detailed else
            f'QFrame#chartPanel {{ background: {tokens.CARD_BG}; '
            f'border: 1px solid {tokens.BORDER}; border-radius: {tokens.RADIUS_CARD}px; }}')
        self.result = None
        self.companies: dict = {}
        self._comparison_label = label('comparison-value')
        self._company_palette: dict[str, QColor] = {}
        self._category_palette: tuple[str, ...] | None = None
        self._fullscreen_dialog = None
        self.series_legend_entries = []
        self._axis_override: AxisSpec | None = None
        self.axis_spec: AxisSpec | None = None
        self._hidden_groups: set = set()
        self._default_zero_hidden: set = set()
        self._category_choices: dict = {}
        self._settings = settings
        self._settings_key = settings_key
        self._compact_layout = False
        self._compact_height: int | None = None
        self._mode_labels: dict[str, str] = {}
        self._combined_totals = False
        self._dates: list = []
        self.chart_views: list[ChartCanvas] = []
        self.company_labels: list[QLabel] = []
        self.legend_buttons: dict = {}
        self.summary_values: dict = {}
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
        self._layout.setContentsMargins(16, 12, 12, 12)
        self._layout.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(8)
        self._header_layout = header
        self.title_label = QLabel(title)
        self.title_label.setObjectName('panelTitle')
        self.title_label.setStyleSheet(emphasis_css(tokens.FONT_SIZE_CHART_TITLE) +
                                       f'color: {tokens.TEXT_PRIMARY}; border: 0; background: transparent;')
        apply_emphasis_font(self.title_label, tokens.FONT_SIZE_CHART_TITLE)
        self.title_label.setMinimumWidth(0)
        header.addWidget(self.title_label, 1)
        self.mode_selector: FluentSegmentedControl | None = None
        self._mode_slot = QHBoxLayout()
        self._mode_slot.setContentsMargins(0, 0, 0, 0)
        header.addLayout(self._mode_slot)
        if self._detailed:
            self.fullscreen_button = TransparentPushButton(FluentIcon.BACK_TO_WINDOW, '缩小', self)
            self.fullscreen_button.setIconSize(QSize(16, 16))
            self.fullscreen_button.setFixedHeight(32)
            self.fullscreen_button.setAccessibleName('缩小图表，返回原图')
            self.fullscreen_button.clicked.connect(parent.close)
        else:
            self.fullscreen_button = TransparentToolButton(self)
            self.fullscreen_button.setIcon(FluentIcon.FULL_SCREEN)
            self.fullscreen_button.setIconSize(QSize(14, 14))
            self.fullscreen_button.setFixedSize(30, 30)
            self.fullscreen_button.setToolTip('放大查看')
            self.fullscreen_button.setAccessibleName('放大查看图表')
            self.fullscreen_button.clicked.connect(self._open_fullscreen)
        header.addWidget(self.fullscreen_button)
        self._layout.addLayout(header)
        self.detail_summary = DetailSummary(self)
        self._layout.addWidget(self.detail_summary)
        self.legend_host = FlowHost(self, spacing=2)
        self._layout.addWidget(self.legend_host)
        self.period_label = QLabel(self)
        self.period_label.setStyleSheet(f'color: {tokens.TEXT_SECONDARY}; font-size: {tokens.FONT_SIZE_CAPTION}px;'
                                        f' border: 0; background: transparent;')
        self.period_label.hide()
        self._layout.addWidget(self.period_label)
        self.summary_label = QLabel(label('missing'))
        self.summary_label.setWordWrap(True)
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.summary_label.setStyleSheet(emphasis_css(20, QFont.Weight.DemiBold) +
                                         f'color: {tokens.TEXT_PRIMARY}; border: 0; background: transparent;')
        self._layout.addWidget(self.summary_label)
        self.chart_host = QWidget(self)
        self.chart_layout = QGridLayout(self.chart_host)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_layout.setHorizontalSpacing(16)
        self.chart_layout.setVerticalSpacing(8)
        self._layout.addWidget(self.chart_host, 1)
        self._has_modes = bool(modes or self._restricted_modes)
        if self._has_modes:
            self._replace_mode_selector(self._allowed_modes if self._restricted_modes else
                                        ((*self.MODES, self.mode) if self.mode in ('area', 'trend-bar')
                                         else self.MODES))
        self.setMinimumHeight(220)
        self._render()

    # ------------------------------------------------------------- modes
    @classmethod
    def _validate_modes(cls, modes):
        values = tuple(modes)
        if not values or len(values) != len(set(values)) or any(mode not in cls.ALL_MODES for mode in values):
            raise ValueError('allowed chart modes')
        return values

    def _replace_mode_selector(self, modes):
        if self.mode_selector is not None:
            self._mode_slot.removeWidget(self.mode_selector)
            self.mode_selector.hide()
            self.mode_selector.deleteLater()
            self.mode_selector = None
        names = [self._mode_labels.get(mode, MODE_NAMES.get(mode, label(mode))) for mode in modes]
        if len(modes) <= 1 or len(set(names)) <= 1:
            return
        self.mode_selector = FluentSegmentedControl(self, compact=True)
        for mode, name in zip(modes, names):
            self.mode_selector.addItem(mode, name)
        self.mode_selector.setCurrentKey(self.mode)
        self.mode_selector.currentKeyChanged.connect(self.set_mode)
        self._mode_slot.addWidget(self.mode_selector)

    def set_mode_options(self, modes: tuple[str, ...]) -> None:
        modes = self._validate_modes(modes)
        if self._restricted_modes and self._allowed_modes == modes and self.mode in modes:
            return
        self._allowed_modes = modes
        self._restricted_modes = True
        self._has_modes = True
        if self.mode not in self._allowed_modes:
            self.mode = self._allowed_modes[0]
        self._replace_mode_selector(self._allowed_modes)
        if self._settings is not None and self._settings_key:
            self._settings.setValue(self._settings_key, self.mode)
        self._render()

    def set_mode_labels(self, labels: dict[str, str] | None) -> None:
        labels = labels or {}
        if any(mode not in self.ALL_MODES or not isinstance(name, str) or not name.strip()
               for mode, name in labels.items()):
            raise ValueError('chart mode labels')
        if self._mode_labels == labels:
            return
        self._mode_labels = dict(labels)
        if self._has_modes:
            modes = (self._allowed_modes if self._restricted_modes else
                     ((*self.MODES, self.mode) if self.mode in ('area', 'trend-bar') else self.MODES))
            self._replace_mode_selector(modes)

    def set_mode(self, mode: str):
        if mode not in self.ALL_MODES or (self._restricted_modes and mode not in self._allowed_modes):
            raise ValueError(mode)
        changed = mode != self.mode
        self.mode = mode
        if self.mode_selector is not None:
            self.mode_selector.blockSignals(True)
            self.mode_selector.setCurrentKey(mode)
            self.mode_selector.blockSignals(False)
        if self._settings is not None and self._settings_key and mode in (*self.MODES, 'area'):
            self._settings.setValue(self._settings_key, mode)
        self._render()
        if changed:
            self.surface_motion.reveal()

    # --------------------------------------------------------- data in
    def set_result(self, result, companies: dict[str, str] | None = None):
        from chart_content_key import result_key
        content_key = (result_key(result), tuple((companies or {}).items()))
        if getattr(self, '_result_content_key', None) == content_key:
            self.result = result
            self.companies = companies or {}
            return
        self._result_content_key = content_key
        from stats_motion import settle_surface_motion
        settle_surface_motion(self)
        if result is not self.result:
            self._cancel_detail()
        self.result = result
        self.companies = companies or {}
        self._render()

    def set_comparison_label(self, text: str):
        text = text.strip() or label('comparison-value')
        if text != self._comparison_label:
            self._comparison_label = text
            self._render()

    def set_axis_range(self, lower, upper, step):
        self.set_axis_spec(AxisSpec(int(lower), int(upper), int(step)))

    def set_axis_spec(self, spec: AxisSpec | None):
        if spec is not None and (spec.step <= 0 or spec.scale <= 0 or spec.upper <= spec.lower):
            raise ValueError('axis range')
        if self._axis_override == spec:
            return
        self._axis_override = spec
        self._render()

    def clear(self):
        self._result_content_key = None
        from stats_motion import settle_surface_motion
        settle_surface_motion(self)
        self._cancel_detail()
        self.result = None
        self._axis_override = None
        self._render()

    def set_company_palette(self, palette: dict[str, str]) -> None:
        converted = {company: QColor(value) for company, value in palette.items()}
        if any(not color.isValid() for color in converted.values()):
            raise ValueError('company palette')
        if self._company_palette == converted:
            return
        self._company_palette = converted
        self._render()

    def set_category_palette(self, colors: tuple[str, ...] | None) -> None:
        if colors is not None:
            colors = tuple(colors)
            if len(colors) < 6 or any(not QColor(value).isValid() for value in colors):
                raise ValueError('category palette')
        if self._category_palette == colors:
            return
        self._category_palette = colors
        self._render()

    # ------------------------------------------------------- compactness
    def set_compact_layout(self, enabled: bool) -> None:
        self._compact_layout = bool(enabled)
        self._layout.setContentsMargins(*((14, 10, 10, 10) if enabled else (16, 12, 12, 12)))

    def set_compact_height(self, height: int) -> None:
        if not isinstance(height, int) or isinstance(height, bool) or height < 180:
            raise ValueError('compact chart height must be at least 180')
        self._compact_height = height
        self.set_compact_layout(True)
        for entry in self.series_legend_entries:
            entry['widget'].set_compact(True)
        for canvas in self.chart_views:
            canvas.setMinimumHeight(0)
        self.setFixedHeight(height)

    def clear_compact_height(self) -> None:
        if self._compact_height is None:
            return
        self._compact_height = None
        for entry in self.series_legend_entries:
            entry['widget'].set_compact(False)
        for canvas in self.chart_views:
            canvas.setMinimumHeight(140 if len(self.chart_views) > 1 else 170)
        self.setMinimumHeight(220)
        self.setMaximumHeight(16777215)

    def sizeHint(self):
        return QSize(420, self._compact_height or 300)

    # ------------------------------------------------------------ hooks
    def _company_color(self, company: str) -> QColor:
        return QColor(self._company_palette.get(company, company_color(company)))

    def _category_color(self, group: str) -> QColor:
        return category_color(group, getattr(self, '_category_palette', None))

    def _legend_color(self, key) -> QColor:
        if self._combined_totals:
            return self._company_color(key)
        groups = self._groups()
        if len(groups) == 1 and len(next(iter(groups.values()))) == 1:
            return self._company_color(next(iter(groups)))
        return self._category_color(key)

    def _company_name(self, company):
        return self.companies.get(company, company)

    def _legend_text(self, key) -> str:
        return self._company_name(key) if self._combined_totals else group_label(key)

    def _legend_tooltip(self, key) -> str:
        return ''

    def _series_options(self, company, group, previous) -> dict:
        return {}

    def _point_note(self, company, group, bucket, previous) -> str:
        if bucket is None:
            return ''
        parts = []
        if previous:
            parts.append(f'{self._comparison_name()} {bucket.start:%Y-%m-%d %H:%M}')
        if getattr(bucket, 'complete', True) is False:
            parts.append('数据不完整')
        return ' · '.join(parts)

    def _time_label_text(self, date, dates):
        cross_year = dates[0].year != dates[-1].year
        if self.result.query.grain == 'hour':
            return date.strftime('%H:%M') if dates[0].date() == dates[-1].date() else date.strftime('%m-%d %H:%M')
        return date.strftime('%Y-%m-%d' if cross_year else '%m-%d')

    def _time_title(self, date) -> str:
        grain = self.result.query.grain
        if grain == 'hour':
            return f'{date:%Y-%m-%d %H:%M}'
        if grain == 'day':
            return f'{date:%Y-%m-%d} 周{WEEKDAYS[date.weekday()]}'
        if grain == 'week':
            return f'{date:%Y-%m-%d} 起一周'
        return f'{date:%Y-%m}'

    def _donut_center(self, total, unit):
        return _number(total, self.result.query.metric), unit

    # ---------------------------------------------------------- building
    def _groups(self):
        grouped = {}
        if self.result is not None:
            for (company, group), buckets in self.result.series.items():
                grouped.setdefault(company, {})[group] = buckets
        return grouped

    def _time_geometry(self):
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
        slots, cursor = [], start
        for _ in range(count):
            slots.append(cursor)
            cursor = period_bounds(cursor, grain)[1]
        return slots

    def _bucket_series(self, company, group, buckets, previous, key, color, count, name, *, bar=False):
        values = [None] * count
        notes = [''] * count
        titles = [''] * count
        for index, bucket in enumerate(buckets[:count]):
            if bucket is not None and bucket.value is not None:
                values[index] = bucket.value
                notes[index] = self._point_note(company, group, bucket, previous)
                titles[index] = self._time_title(bucket.start)
                if bar and previous and getattr(bucket, 'complete', True):
                    notes[index] = ''
                elif bar and previous:
                    notes[index] = '数据不完整'
        options = dict(self._series_options(company, group, previous))
        return Series(key=key, name=name, color=QColor(color), values=values, notes=notes, titles=titles,
                      stack=f'{key}|{int(previous)}', dashed=previous or options.pop('dashed', False),
                      faded=previous, **options)

    def _time_data(self, kind, categories, company=None):
        """``categories``: list of (company, group, buckets) for one canvas."""
        dates = self._dates
        series = []
        multiple = len(categories) > 1
        for owner, group, buckets in categories:
            key = owner if self._combined_totals else group
            color = (self._company_color(owner) if self._combined_totals or not multiple
                     else self._category_color(group))
            base = self._legend_text(key) if (self._combined_totals or multiple) else (
                self._company_name(owner) or group_label(group))
            comparison = self.result.comparison.get((owner, group), [])
            series.append(self._bucket_series(owner, group, buckets, False, key, color, len(dates),
                                              f'{base} · {label("current")}' if comparison else base, bar=kind == 'bar'))
            if comparison:
                series.append(self._bucket_series(owner, group, comparison, True, key, color, len(dates),
                                                  f'{base} · {self._comparison_name()}', bar=kind == 'bar'))
        if kind == 'bar':
            for item in series:
                item.dashed = False
        return ChartData(kind=kind, labels=[self._time_label_text(date, dates) for date in dates],
                         titles=[self._time_title(date) for date in dates], series=series,
                         unit=self.result.metric.unit)

    def _total_data(self, company, categories):
        names = ([] if self._combined_totals and company in self._hidden_groups else
                 list(categories) if self._combined_totals else
                 [group for group in categories if group not in self._hidden_groups])
        current = {group: summarize_buckets(buckets, self.result.metric) for group, buckets in categories.items()}
        multiple = len(categories) > 1
        colors = [self._category_color(group) if multiple else self._company_color(company) for group in names]
        color = colors[0] if colors else self._company_color(company)
        series = [Series(key='current', name=label('current') if self.result.comparison else self._company_name(company),
                         color=color, colors=colors,
                         values=[current[group] for group in names])]
        if self.result.comparison:
            previous = {group: summarize_buckets(self.result.comparison.get((company, group), []), self.result.metric)
                        for group in names}
            series.append(Series(key='comparison', name=self._comparison_name(), color=color, colors=colors,
                                 values=[previous[group] for group in names], faded=True))
        return ChartData(kind='hbar', labels=[group_label(group) for group in names], series=series,
                         unit=self.result.metric.unit)

    def _donut_data(self, company, categories):
        values = {group: summarize_buckets(buckets, self.result.metric) for group, buckets in categories.items()}
        positive = {group: value for group, value in values.items() if value is not None and value > 0}
        if self._combined_totals and company in self._hidden_groups:
            positive = {}
        total = sum(positive.values(), Decimal(0))
        text, caption = self._donut_center(total, self.result.metric.unit)
        return ChartData(kind='donut', labels=[group_label(group) for group in positive],
                         series=[Series(key='share', name=self._company_name(company),
                                        color=QColor(tokens.ACCENT), keys=([company] * len(positive) if self._combined_totals else list(positive)),
                                        values=list(positive.values()),
                                        colors=[self._category_color(group) for group in positive])],
                         unit=self.result.metric.unit, center_text=text, center_caption=caption,
                         empty_text=label('missing'))

    def _chart_specs(self):
        """[(caption, ChartData)] for the current mode and result."""
        groups = self._groups()
        if self.mode in ('line', 'area', 'trend-bar'):
            kind = 'bar' if self.mode == 'trend-bar' else 'line'
            if self._combined_totals:
                return [('', self._time_data(kind, [(company, *next(iter(entries.items())))
                                                   for company, entries in groups.items()]))]
            return [(self._company_name(company) if len(groups) > 1 else '',
                     self._time_data(kind, [(company, group, buckets) for group, buckets in entries.items()]))
                    for company, entries in groups.items()]
        if self.mode == 'bar':
            return [(self._company_name(company) if len(groups) > 1 else '', self._total_data(company, entries))
                    for company, entries in groups.items()]
        if self.mode == 'pie':
            return [(self._company_name(company) if len(groups) > 1 else '', self._donut_data(company, entries))
                    for company, entries in groups.items()]
        return []

    # ----------------------------------------------------------- render
    def _clear_views(self):
        while self.chart_layout.count():
            item = self.chart_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.chart_views = []
        self.company_labels = []

    def _render(self):
        if not hasattr(self, 'chart_layout'):
            return
        groups = self._groups()
        if self._detailed:
            self.detail_summary.refresh()
        self._combined_totals = (len(groups) > 1
                                 and all(len(entries) == 1 for entries in groups.values())
                                 and len({next(iter(entries)) for entries in groups.values()}) == 1
                                 and next(iter(next(iter(groups.values())))) in TOTAL_GROUPS)
        values = {}
        if self.result is not None:
            for series in (self.result.series, self.result.comparison):
                for (company, category), buckets in series.items():
                    key = company if self._combined_totals else category
                    values.setdefault(key, []).extend(bucket.value for bucket in buckets if bucket.value is not None)
        self._sync_zero_categories(values)
        self.summary_values = {}
        if self.result is not None:
            for company, categories in groups.items():
                valid = [value for value in (summarize_buckets(buckets, self.result.metric)
                                             for buckets in categories.values()) if value is not None]
                if valid:
                    self.summary_values[company] = sum(valid, Decimal(0))
        has_data = self.result is not None and bool(groups)
        show_chart = has_data and self.mode != 'summary'
        self.summary_label.setVisible(not show_chart)
        self.chart_host.setVisible(show_chart)
        self.fullscreen_button.setEnabled(self._detailed or show_chart)
        self.period_label.hide()
        if not has_data:
            self._clear_views()
            self.summary_label.setText(label('missing') if self.result is None else '暂无可用数据')
            self._build_legend({})
            return
        if self.mode == 'summary':
            self._clear_views()
            self.summary_label.setText('\n'.join(
                f'{self._company_name(company)}  {_number(self.summary_values.get(company), self.result.query.metric)} '
                f'{self.result.metric.unit}' for company in groups))
            self._build_legend({})
            return
        self._dates = self._time_geometry() if self.mode in ('line', 'area', 'trend-bar') else []
        specs = self._chart_specs()
        self._place_specs(specs)
        self._build_legend(groups)

    def _place_specs(self, specs):
        columns = 1 if len(specs) == 1 else 2 if self.mode in ('pie', 'bar') or self._detailed else 1
        if len(self.chart_views) != len(specs):
            self._clear_views()
        old_views = list(self.chart_views)
        self.company_labels = []
        for index, (caption, data) in enumerate(specs):
            if index < len(old_views):
                canvas = old_views[index]
                cell = canvas.parentWidget()
                heading = cell._chart_heading
                self.chart_layout.removeWidget(cell)
            else:
                cell = QWidget(self.chart_host)
                box = QVBoxLayout(cell)
                box.setContentsMargins(0, 0, 0, 0)
                box.setSpacing(2)
                heading = QLabel(cell)
                heading.setStyleSheet(f'color: {tokens.TEXT_SECONDARY}; font-size: 12px; border: 0;')
                cell._chart_heading = heading
                box.addWidget(heading)
                canvas = ChartCanvas(cell, detailed=self._detailed)
                canvas.hover_changed.connect(lambda index, source=canvas: self._canvas_hover(source, index))
                canvas.slice_clicked.connect(self._toggle_category)
                box.addWidget(canvas, 1)
                self.chart_views.append(canvas)
            heading.setText(caption)
            heading.setVisible(bool(caption))
            if caption:
                self.company_labels.append(heading)
            canvas.set_hidden(self._hidden_groups)
            canvas.set_axis(self._axis_override if data.kind in ('line', 'bar', 'hbar') else None)
            data.decimal_places = number_places(self.result.query.metric)
            canvas.set_data(data)
            canvas.setMinimumHeight(0 if self._compact_height is not None else
                                    140 if len(specs) > 1 and not self._detailed else 170)
            self.chart_layout.addWidget(cell, index // columns, index % columns)
            cell.show()
        self.axis_spec = self._axis_override

    def _build_legend(self, groups):
        self.legend_host.clear()
        self.legend_buttons = {}
        self.series_legend_entries = []
        if self.mode == 'summary' or self.result is None or not groups:
            self.legend_host.hide()
            return
        keys = (list(groups) if self._combined_totals else
                list(dict.fromkeys(group for entries in groups.values() for group in entries)))
        show_categories = self.mode != 'pie' and (len(keys) > 1 or keys[0] in self._hidden_groups or keys[0] in self._category_choices)
        for key in keys if show_categories else []:
            if self._combined_totals:
                entry = self._add_series_legend(key, self._legend_text(key), [self._legend_color(key)])
                chip = entry['widget']
            else:
                chip = LegendChip(self._legend_text(key), self._legend_color(key), self.legend_host)
                self.legend_host.flow.addWidget(chip)
            tooltip = self._legend_tooltip(key)
            if tooltip:
                chip.setToolTip(tooltip)
                chip.setAccessibleName(tooltip)
            self._configure_legend_toggle(key, chip)
        self._build_comparison_legend()
        self.legend_host.setVisible(bool(self.legend_buttons or self.series_legend_entries))
        self.legend_host.updateGeometry()

    def _comparison_name(self):
        return self._comparison_label

    def _configure_legend_toggle(self, key, chip):
        chip.setCheckable(True)
        chip.setChecked(key not in self._hidden_groups)
        chip.setCursor(Qt.CursorShape.PointingHandCursor)
        chip.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        chip.clicked.connect(lambda checked=False, k=key: self._toggle_category(k))
        self.legend_buttons[key] = chip

    def _add_series_legend(self, key, name, colors):
        if not colors:
            return
        widget = SeriesLegend(name, colors, self.legend_host, compact=self._compact_height is not None)
        if key in self.companies:
            # Use the actual key, never infer identity from a visual position.
            raw = self.companies[key]
            suffixes = (f' [{key}]', f' ({key})')
            for suffix in suffixes:
                if raw.endswith(suffix):
                    raw = raw[:-len(suffix)]
                    break
            if (any(name.endswith(suffix) for suffix in suffixes)
                    or list(self.companies.values()).count(raw) > 1):
                widget.set_company_identity(raw, key)
        self.legend_host.flow.addWidget(widget)
        entry = dict(key=key, name=name, colors=tuple(QColor(color) for color in colors), widget=widget)
        self.series_legend_entries.append(entry)
        return entry

    def _build_comparison_legend(self):
        if self.result is None or not self.result.comparison:
            return
        palettes = {False: {}, True: {}}
        for canvas in self.chart_views:
            for item in canvas.data.series:
                for color in item.colors or (item.color,):
                    color = QColor(color)
                    if item.faded:
                        color.setAlphaF(color.alphaF() * tokens.CHART_COMPARISON_OPACITY)
                    palettes[item.faded][color.rgba()] = color
        if not palettes[True]:
            return
        for previous, name in ((False, label('current')), (True, self._comparison_name())):
            self._add_series_legend('comparison' if previous else 'current', name,
                                    list(palettes[previous].values()))

    def _toggle_category(self, group):
        if group in self._hidden_groups:
            self._hidden_groups.remove(group)
        else:
            self._hidden_groups.add(group)
        self._category_choices[group] = group not in self._hidden_groups
        self._apply_category(group)

    def _sync_zero_categories(self, values):
        """Presentation defaults only; missing buckets and signed cancellation stay distinct."""
        self._hidden_groups.difference_update(self._default_zero_hidden)
        self._default_zero_hidden = {key for key, observed in values.items()
                                     if observed and all(value == 0 for value in observed)
                                     and key not in self._category_choices}
        self._hidden_groups.update(self._default_zero_hidden)
        for key, visible in self._category_choices.items():
            if visible: self._hidden_groups.discard(key)
            else: self._hidden_groups.add(key)

    def _apply_category(self, group):
        visible = group not in self._hidden_groups
        if group in self.legend_buttons:
            self.legend_buttons[group].setChecked(visible)
        if self.mode == 'bar':
            self._render()
            return
        for canvas in self.chart_views:
            canvas.set_hidden(self._hidden_groups)

    # ------------------------------------------------------------- hover
    def _canvas_hover(self, source, index):
        offset = None
        if index is not None and self._dates and index < len(self._dates) and self.result is not None:
            offset = (self._dates[index] - self.result.current_window[0]).total_seconds()
        for canvas in self.chart_views:
            if canvas is not source:
                canvas.set_linked_index(index)
        self.hover_offset_changed.emit(offset)

    def set_hover_offset(self, seconds: float | None) -> None:
        """Show a linked crosshair at a relative time without re-emitting."""
        index = None
        if seconds is not None and self.result is not None and self._dates:
            start = self.result.current_window[0]
            index = next((position for position, date in enumerate(self._dates)
                          if abs((date - start).total_seconds() - seconds) < .5), None)
        for canvas in self.chart_views:
            canvas.set_linked_index(index)

    # -------------------------------------------------------- fullscreen
    def _create_clone(self, dialog):
        clone = type(self)(self.title_label.text(), default_mode=self.mode, parent=dialog,
                           modes=self.mode_selector is not None,
                           allowed_modes=self._allowed_modes if self._restricted_modes else None)
        clone._hidden_groups = set(self._hidden_groups)
        clone._category_choices = dict(self._category_choices)
        clone.set_comparison_label(self._comparison_label)
        clone.set_mode_labels(self._mode_labels)
        clone.set_company_palette({key: color.name() for key, color in self._company_palette.items()})
        clone.set_category_palette(self._category_palette)
        clone.set_result(self.result, self.companies)
        clone.set_axis_spec(self._axis_override)
        return clone

    def _open_fullscreen(self):
        if self.result is None:
            return
        previous = self._fullscreen_dialog
        if previous is not None and isValid(previous):
            if previous.isVisible():
                return previous.panel
            previous.deleteLater()
        surface = InlineChartDetail(self)
        clone = self._create_clone(surface)
        surface.set_panel(clone)
        surface.finished.connect(lambda: self._adopt_hidden(clone)
                                 if surface.adopt_on_return and isValid(self) else None)
        self._fullscreen_dialog = surface
        surface.expand()
        return clone

    def _cancel_detail(self):
        surface = self._fullscreen_dialog
        if surface is not None and isValid(surface) and surface.isVisible():
            surface.cancel()

    def _adopt_hidden(self, clone):
        self._category_choices = dict(clone._category_choices)
        if set(clone._hidden_groups) != self._hidden_groups:
            self._hidden_groups = set(clone._hidden_groups)
            self._default_zero_hidden = set(clone._default_zero_hidden)
            self._render()


_category_color = category_color  # backwards-compatible name
