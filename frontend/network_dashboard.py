"""Network statistics content built from one audited NetworkSnapshot."""
from __future__ import annotations
from stats_typography import emphasis_css, apply_emphasis_font

from dataclasses import replace
from decimal import Decimal

from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QColor, QFontMetricsF
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, IconWidget

from network_model import NetworkOptions, NetworkSnapshot, NetworkSummary, NetworkValue
from display_rules import format_number, number_places
from stats_charts import nice_axis
from stats_controls import FluentSegmentedControl, SummaryToggleButton
from card_comparison_label import ComparisonLabel
from stats_tokens import (BORDER, CARD_BG, CHART_BLUE, CONTROL_GAP,
                          FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_KPI,
                          RADIUS_CARD, RADIUS_KPI, SECTION_GAP, TEXT_PRIMARY,
                          TEXT_SECONDARY)


CHART_KEYS = ('linecount', 'stopcount', 'coverage', 'vehicles-running',
              'transfer-coefficient', 'transport-by-type', 'transport-by-group', 'trip-types')
SWITCHES = {
    1: ('facility', (('车库', 'depotcount'), ('站点', 'stopcount'))),
    2: ('vehicle', (('平均', 'average'), ('最大', 'maximum'))),
    4: ('passenger', (('客流', 'transport-by-type'), ('出行量', 'trip-types'))),
}
ICONS = (FluentIcon.MARKET, FluentIcon.HOME, FluentIcon.BUS,
         FluentIcon.PIE_SINGLE, FluentIcon.PEOPLE, FluentIcon.CALORIES)
VALUE_POSITIONS = {'linecount': 0, 'depotcount': 1, 'stopcount': 1,
                   'vehicles-running': 2, 'coverage': 3,
                   'transport-by-type': 4, 'trip-types': 4,
                   'transfer-coefficient': 5}
MODE_LABELS = {'line': '趋势', 'bar': '分布', 'trend-bar': '趋势', 'pie': '比例'}


def _number(value: Decimal | None, metric=None) -> str:
    return format_number(value, number_places(metric))


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


from stats_elevation import attach_card_elevation
from stats_motion import CollapseMotion


class NetworkValueTile(QFrame):
    option_changed = Signal(str, str)

    def __init__(self, position: int, value: NetworkValue, options: NetworkOptions,
                 color: str, parent=None, *, dense=False, tight=False):
        super().__init__(parent)
        self.position = position
        self.value_model = value
        self.setObjectName('networkValueTile')
        attach_card_elevation(self)
        self.setMinimumHeight(88 if tight else 96)
        self.setStyleSheet(f'QFrame#networkValueTile {{ background: {CARD_BG}; '
                           f'border: 1px solid {BORDER}; border-radius: {RADIUS_KPI}px; }}')
        box = QVBoxLayout(self)
        box.setContentsMargins(6 if dense else 10, 4 if tight else 8,
                               6 if dense else 10, 4 if tight else 8)
        box.setSpacing(3)
        heading = QHBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(4 if dense else 6)
        icon = IconWidget(self)
        icon.setIcon(ICONS[position].icon(color=QColor(color)))
        icon.setFixedSize(18, 18)
        heading.addWidget(icon)
        self.option_control = None
        self.metric_title = None
        if position == 2:
            self.metric_title = QLabel('车辆', self)
            self.metric_title.setStyleSheet(
                f'color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px;')
            heading.addWidget(self.metric_title)
        if position in SWITCHES:
            field, choices = SWITCHES[position]
            control = FluentSegmentedControl(self, compact=True, dense=dense)
            for title, key in choices:
                control.addItem(key, title)
            control.setCurrentKey(getattr(options, field))
            control.currentKeyChanged.connect(
                lambda key, option=field: self.option_changed.emit(option, key))
            heading.addWidget(control)
            self.option_control = control
        else:
            title = QLabel(value.title, self)
            title.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px;')
            heading.addWidget(title)
            self.metric_title = title
        heading.addStretch()
        box.addLayout(heading)
        number_row = QHBoxLayout()
        number_row.setContentsMargins(0, 0, 0, 0)
        number_row.setSpacing(4)
        self.number = QLabel(_number(value.value, value.metric_id), self)
        self.number.setStyleSheet(f'color: {TEXT_PRIMARY}; {emphasis_css(FONT_SIZE_KPI)}')
        apply_emphasis_font(self.number, FONT_SIZE_KPI)
        self.number.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        number_row.addWidget(self.number)
        self.unit = QLabel(value.unit if value.value is not None else '', self)
        self.unit.setStyleSheet(f'color: {TEXT_SECONDARY}; {emphasis_css(FONT_SIZE_CAPTION)}')
        apply_emphasis_font(self.unit, FONT_SIZE_CAPTION)
        self.number.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.unit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self._update_unit_baseline()
        self.number.installEventFilter(self)
        self.unit.installEventFilter(self)
        number_row.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom)
        number_row.addStretch()
        box.addLayout(number_row)
        self.comparison_label = ComparisonLabel(value.comparison, self, tooltip_target=self.number)
        box.addWidget(self.comparison_label)
        if value.value is None and value.reason:
            reason = QLabel(value.reason, self)
            reason.setWordWrap(True)
            reason.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px;')
            box.addWidget(reason)
        detail_text = '；'.join(f'{name}: {_number(amount, value.metric_id)}' for name, amount in value.details)
        self.setToolTip('；'.join(dict.fromkeys(part for part in
            (value.reason, detail_text) if part)))

    def _update_unit_baseline(self):
        delta = round(QFontMetricsF(self.number.font()).descent() - QFontMetricsF(self.unit.font()).descent())
        self.number.setContentsMargins(0, 0, 0, max(0, -delta))
        self.unit.setContentsMargins(0, 0, 0, max(0, delta))

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.ApplicationFontChange,
                            QEvent.Type.DevicePixelRatioChange):
            self._update_unit_baseline()
        return super().eventFilter(watched, event)


class NetworkSummaryCard(QFrame):
    option_changed = Signal(str, str)
    summary_toggled = Signal(bool)

    def __init__(self, summary: NetworkSummary, options: NetworkOptions,
                 color: str, parent=None, *, tight=False):
        super().__init__(parent)
        self.summary = summary
        self.overview = options.mode == 'overall'
        self.setObjectName('networkSummaryCard')
        attach_card_elevation(self)
        self.setStyleSheet(f'QFrame#networkSummaryCard {{ background: {CARD_BG}; '
                           f'border: 1px solid {BORDER}; border-radius: {RADIUS_CARD}px; }}')
        box = QVBoxLayout(self)
        padding = 6 if tight else 8
        box.setContentsMargins(padding, padding, padding, padding)
        box.setSpacing(4 if tight else CONTROL_GAP)
        heading = QHBoxLayout()
        heading.setSpacing(6)
        dot = QLabel('●', self)
        dot.setStyleSheet(f'color: {color}; font-size: {FONT_SIZE_BODY}px;')
        heading.addWidget(dot)
        self.title = QLabel(summary.title, self)
        self.title.setStyleSheet(f'color: {TEXT_PRIMARY}; {emphasis_css(FONT_SIZE_BODY)}')
        apply_emphasis_font(self.title, FONT_SIZE_BODY)
        heading.addWidget(self.title)
        heading.addStretch()
        if self.overview:
            dot.hide()
            self.title.setText('数据摘要')
        self.summary_button = SummaryToggleButton(self)
        self.summary_button.clicked.connect(lambda: self.summary_toggled.emit(not self.summary_button.collapsed))
        heading.addWidget(self.summary_button)
        box.addLayout(heading)
        self.tile_host = QWidget(self)
        self.tile_grid = QGridLayout(self.tile_host)
        self.tile_grid.setContentsMargins(0, 0, 0, 0)
        self.tile_grid.setSpacing(6 if tight else CONTROL_GAP)
        self.tiles = []
        dense = True
        for value in summary.values:
            tile = NetworkValueTile(VALUE_POSITIONS[value.metric_id], value,
                                    options, color, self.tile_host, dense=dense,
                                    tight=tight)
            tile.option_changed.connect(self.option_changed)
            self.tiles.append(tile)
        box.addWidget(self.tile_host)
        self.summary_motion = CollapseMotion(self.tile_host, self._summary_finished, self)
        self.summary_motion.on_progress = self._summary_finished
        self.reflow(3)

    def set_summary_collapsed(self, collapsed):
        self.summary_button.set_collapsed(collapsed)
        if self.summary_motion.collapsed != bool(collapsed):
            self.summary_motion.set_collapsed(collapsed)

    def _summary_finished(self):
        dashboard = self.parentWidget()
        while dashboard is not None and not isinstance(dashboard, NetworkDashboard):
            dashboard = dashboard.parentWidget()
        if dashboard is not None and not dashboard._building_snapshot:
            dashboard.reflow(dashboard._content_width, dashboard._viewport_height)

    def reflow(self, columns: int):
        for tile in self.tiles:
            self.tile_grid.removeWidget(tile)
        for index, tile in enumerate(self.tiles):
            self.tile_grid.addWidget(tile, index // columns, index % columns)


class NetworkDashboard(QWidget):
    """Network page body. Its parent supplies one shared scroll area and filters."""

    options_changed = Signal(object)

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.snapshot: NetworkSnapshot | None = None
        self.options = NetworkOptions()
        self.palette: dict[str, str] = {}
        self.summary_cards: list[NetworkSummaryCard] = []
        self.chart_panels: dict[tuple[str | None, str], object] = {}
        self.chart_controls: dict[str, list[FluentSegmentedControl]] = {}
        self._sections: list[tuple[QWidget, QGridLayout, list[QWidget]]] = []
        self._summary_grid = None
        self._period_grid = None
        self._summary_collapsed = False
        self._content_width = 1120
        self._viewport_height = 0
        self._building_snapshot = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SECTION_GAP)
        self.notice = QLabel('', self)
        self.notice.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY}px;')
        self.notice.hide()
        root.addWidget(self.notice)

    def show_notice(self, message: str):
        self.notice.setText(message)
        self.notice.setVisible(bool(message))

    def set_company_palette(self, palette: dict[str, str]):
        self.palette = dict(palette)
        for panel in self.chart_panels.values():
            panel.set_company_palette(self.palette)

    def clear(self):
        while self.layout().count() > 1:
            item = self.layout().takeAt(1)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
            elif item.layout() is not None:
                _clear_layout(item.layout())
        self.summary_cards.clear()
        self.chart_panels.clear()
        self.chart_controls.clear()
        self._sections.clear()
        self._summary_grid = None
        self._period_grid = None
        self.snapshot = None

    def export_target(self) -> QWidget:
        return self

    def _request_option(self, field: str, key: str):
        if getattr(self.options, field) != key:
            self.options = replace(self.options, **{field: key})
            self.options_changed.emit(self.options)

    def _make_chart_panel(self, parent):
        from network_charts import NetworkChartPanel
        return NetworkChartPanel(parent=parent)

    def _preferred_mode(self, key: str, allowed: tuple[str, ...]) -> str:
        saved = self.settings.value(f'network/{key}/chart_mode', allowed[0]) if self.settings else allowed[0]
        return saved if saved in allowed else allowed[0]

    def _set_chart_mode(self, key: str, mode: str):
        if self.settings:
            self.settings.setValue(f'network/{key}/chart_mode', mode)
        for (company, chart_key), panel in self.chart_panels.items():
            if chart_key == key:
                panel.set_mode(mode)
        for control in self.chart_controls.get(key, []):
            if control.currentKey() != mode:
                control.blockSignals(True)
                control.setCurrentKey(mode)
                control.blockSignals(False)
        if self.snapshot is not None and self.snapshot.options.mode == 'period':
            self._align_period_axes(self.snapshot)

    def _chart_card(self, descriptor, parent):
        panel = self._make_chart_panel(parent)
        panel.set_company_palette(self.palette)
        panel.set_descriptor(descriptor, self.snapshot)
        selected = self._preferred_mode(descriptor.key, descriptor.allowed_modes)
        panel.set_mode(selected)
        self.chart_panels[(descriptor.company_id, descriptor.key)] = panel
        if len(descriptor.allowed_modes) > 1:
            control = FluentSegmentedControl(panel, compact=True, dense=True)
            for mode in descriptor.allowed_modes:
                control.addItem(mode, MODE_LABELS[mode])
            control.setCurrentKey(selected)
            control.currentKeyChanged.connect(
                lambda mode, key=descriptor.key: self._set_chart_mode(key, mode))
            self.chart_controls.setdefault(descriptor.key, []).append(control)
            panel.set_mode_control(control)
        panel.setMinimumHeight(290)
        return panel

    def _section(self, summary: NetworkSummary, descriptors, color: str):
        section = QWidget(self)
        column = QVBoxLayout(section)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(SECTION_GAP)
        card = NetworkSummaryCard(summary, self.options, color, section,
                                  tight=len(self.snapshot.summaries) > 1)
        card.option_changed.connect(self._request_option)
        card.set_summary_collapsed(self._summary_collapsed)
        card.summary_toggled.connect(self.set_summary_collapsed)
        self.summary_cards.append(card)
        column.addWidget(card)
        chart_host = QWidget(section)
        grid = QGridLayout(chart_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(CONTROL_GAP)
        charts = [self._chart_card(descriptor, chart_host) for descriptor in descriptors]
        column.addWidget(chart_host)
        self._sections.append((section, grid, charts))
        return section

    def set_snapshot(self, snapshot: NetworkSnapshot):
        self._building_snapshot = True
        self.clear()
        self.snapshot = snapshot
        self.options = snapshot.options
        if snapshot.options.mode == 'period':
            period_host = QWidget(self)
            self._period_grid = QGridLayout(period_host)
            self._period_grid.setContentsMargins(0, 0, 0, 0)
            self._period_grid.setSpacing(CONTROL_GAP)
            self.layout().addWidget(period_host)
            for summary in snapshot.summaries:
                descriptors = [item for item in snapshot.charts
                               if item.company_id == summary.company_id]
                self._section(summary, descriptors,
                              self.palette.get(summary.company_id, CHART_BLUE))
        else:
            summary_host = QWidget(self)
            summary_grid = QGridLayout(summary_host)
            summary_grid.setContentsMargins(0, 0, 0, 0)
            summary_grid.setSpacing(CONTROL_GAP)
            for summary in snapshot.summaries:
                card = NetworkSummaryCard(summary, snapshot.options,
                    self.palette.get(summary.company_id, CHART_BLUE), summary_host,
                    tight=snapshot.options.mode == 'companies')
                card.option_changed.connect(self._request_option)
                card.set_summary_collapsed(self._summary_collapsed)
                card.summary_toggled.connect(self.set_summary_collapsed)
                self.summary_cards.append(card)
            self.layout().addWidget(summary_host)
            self._summary_grid = summary_grid
            chart_host = QWidget(self)
            grid = QGridLayout(chart_host)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setSpacing(CONTROL_GAP)
            charts = [self._chart_card(item, chart_host) for item in snapshot.charts]
            self.layout().addWidget(chart_host)
            self._sections.append((chart_host, grid, charts))
        self._building_snapshot = False
        self.reflow(self._content_width)
        if snapshot.options.mode == 'period':
            self._align_period_axes(snapshot)

    def _align_period_axes(self, snapshot: NetworkSnapshot):
        for key in CHART_KEYS:
            descriptors = [item for item in snapshot.charts if item.key == key and item.result]
            values = []
            for item in descriptors:
                panel = self.chart_panels.get((item.company_id, key))
                result = item.bar_result if panel is not None and panel.mode == 'bar' and item.bar_result else item.result
                for source in (result.series, result.comparison):
                    if key in ('transport-by-type', 'transport-by-group', 'trip-types'):
                        totals = {}
                        for buckets in source.values():
                            for index, bucket in enumerate(buckets):
                                if bucket.value is not None and bucket.value > 0:
                                    totals[index] = totals.get(index, Decimal(0)) + bucket.value
                        values.extend(totals.values())
                    else:
                        values.extend(bucket.value for buckets in source.values()
                                      for bucket in buckets if bucket.value is not None)
            if not values:
                continue
            spec = nice_axis(values)
            for item in descriptors:
                panel = self.chart_panels.get((item.company_id, key))
                if panel is not None and panel.mode != 'pie':
                    panel.set_axis_spec(spec)

    def set_summary_collapsed(self, collapsed):
        self._summary_collapsed = bool(collapsed)
        for card in self.summary_cards:
            card.set_summary_collapsed(collapsed)
        if not any(card.summary_motion.animation for card in self.summary_cards):
            self.reflow(self._content_width, self._viewport_height)

    def reflow(self, width: int, viewport_height: int | None = None):
        self._content_width = width
        if viewport_height is not None:
            self._viewport_height = viewport_height
        if self.snapshot is None:
            return
        available_height = self._viewport_height
        if self.notice.isVisible():
            available_height -= self.notice.height() + self.layout().spacing()
        if self.snapshot.options.mode == 'period':
            columns = 2 if width >= 1120 and len(self._sections) > 1 else 1
            for section, grid, charts in self._sections:
                section_width = (width - CONTROL_GAP) // 2 if columns == 2 else width
                chart_columns = (4 if columns == 1 and section_width >= 1100 else
                                 2 if section_width >= 550 else 1)
                for chart in charts:
                    grid.removeWidget(chart)
                for index, chart in enumerate(charts):
                    grid.addWidget(chart, index // chart_columns, index % chart_columns)
                self._period_grid.removeWidget(section)
            for index, (section, _, _) in enumerate(self._sections):
                self._period_grid.addWidget(section, index // columns, index % columns)
                summary_columns = (6 if columns == 1 and section_width >= 1100 else
                                   3 if section_width >= 550 else 2)
                self.summary_cards[index].reflow(summary_columns)
                if self._viewport_height > 0:
                    card = self.summary_cards[index]
                    target = 46 if card.summary_motion.collapsed else 160 if summary_columns == 6 else 248
                    summary_height = self._summary_height(card, target)
                    chart_width = (section_width - (chart_columns - 1) * CONTROL_GAP) // chart_columns
                    chart_rows = (len(self._sections[index][2]) + chart_columns - 1) // chart_columns
                    section_rows = (len(self._sections) + columns - 1) // columns
                    section_height = (available_height - (section_rows - 1) * CONTROL_GAP) // section_rows
                    budget = (section_height - summary_height - SECTION_GAP -
                              (chart_rows - 1) * CONTROL_GAP) // chart_rows
                    chart_height = max(230 if chart_width < 360 else 180, budget)
                    for chart in self._sections[index][2]:
                        self._fit_chart_height(chart, chart_height)
        else:
            summary_columns = 2 if self.snapshot.options.mode == 'companies' and width >= 850 else 1
            for card in self.summary_cards:
                self._summary_grid.removeWidget(card)
            for index, card in enumerate(self.summary_cards):
                self._summary_grid.addWidget(card, index // summary_columns, index % summary_columns)
                if self.snapshot.options.mode == 'overall':
                    wide_columns = len(card.tiles)
                    wide_minimum = 1100 if wide_columns == 6 else 1120
                    card.reflow(wide_columns if width >= wide_minimum else 3 if width >= 760 else 2)
                else:
                    card.reflow(3 if summary_columns == 2 or width >= 700 else 2)
            chart_columns = 4 if width >= 1100 and self.snapshot.options.mode == 'overall' else (
                3 if width >= 1120 else 2 if width >= 760 else 1)
            _, grid, charts = self._sections[0]
            for chart in charts:
                grid.removeWidget(chart)
            for index, chart in enumerate(charts):
                if (self.snapshot.options.mode == 'overall' and
                        chart_columns == 4 and len(charts) == 7):
                    if index < 4:
                        grid.addWidget(chart, 0, index * 3, 1, 3)
                    else:
                        grid.addWidget(chart, 1, (index - 4) * 4, 1, 4)
                else:
                    grid.addWidget(chart, index // chart_columns, index % chart_columns)
            if self.snapshot.options.mode == 'overall':
                card = self.summary_cards[0]
                summary_tile_columns = (wide_columns if width >= wide_minimum else
                                        3 if width >= 760 else 2)
                summary_rows = (len(card.tiles) + summary_tile_columns - 1) // summary_tile_columns
                target = 50 if card.summary_motion.collapsed else 52 + summary_rows * 96 + (summary_rows - 1) * CONTROL_GAP + 2
                summary_height = self._summary_height(card, target)
                if self._viewport_height > 0:
                    chart_rows = (len(charts) + chart_columns - 1) // chart_columns
                    available = (available_height - summary_height - SECTION_GAP -
                                 (chart_rows - 1) * CONTROL_GAP - 8)
                    chart_height = max(0, available // chart_rows)
                    for chart in charts:
                        if chart_height >= 180:
                            self._fit_chart_height(chart, chart_height)
            elif self._viewport_height > 0:
                expanded_height = max(card.minimumSizeHint().height() + 2 for card in self.summary_cards)
                summary_heights = []
                for card in self.summary_cards:
                    target = 50 if card.summary_motion.collapsed else expanded_height
                    summary_heights.append(self._summary_height(card, target))
                summary_rows = (len(self.summary_cards) + summary_columns - 1) // summary_columns
                summary_height = sum(max(summary_heights[row * summary_columns:(row + 1) * summary_columns])
                                     for row in range(summary_rows))
                summary_height += max(0, summary_rows - 1) * self._summary_grid.spacing()
                chart_rows = (len(charts) + chart_columns - 1) // chart_columns
                chart_width = (width - (chart_columns - 1) * CONTROL_GAP) // chart_columns
                budget = (available_height - summary_height - SECTION_GAP -
                          (chart_rows - 1) * CONTROL_GAP) // chart_rows
                chart_height = max(230 if chart_width < 360 else 180, budget)
                for chart in charts:
                    self._fit_chart_height(chart, chart_height)

    @staticmethod
    def _summary_height(card, target):
        if card.summary_motion.animation is not None:
            return card.height()
        if not card.summary_motion.collapsed:
            target = max(target, card.minimumSizeHint().height())
        card.setFixedHeight(target)
        return target

    @staticmethod
    def _fit_chart_height(chart, height):
        if getattr(chart, '_compact_height', None) is None:
            chart.set_compact_height(height)
            chart._compact_height = height
        elif chart._compact_height != height or chart.minimumHeight() != height:
            chart._compact_height = height
            chart.setFixedHeight(height)
            for view in getattr(chart, 'chart_views', ()):
                view.setMinimumHeight(min(view.minimumHeight(), max(90, height - 112)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow(self.width(), self._viewport_height)
