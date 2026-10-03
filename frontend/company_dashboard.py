"""Company KPI groups and four-slot charts for the three analysis modes."""
from __future__ import annotations
from stats_typography import emphasis_css, apply_emphasis_font

from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QColor, QFont, QFontMetrics, QFontMetricsF
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, ComboBox as FluentComboBox, FluentIcon, IconWidget

from statistics_model import summarize_buckets
from stats_charts import ChartPanel, nice_axis
from stats_controls import SummaryToggleButton
from stats_text import label
from stats_tokens import (BORDER, CARD_BG, CARD_PADDING, CHART_BLUE, CONTROL_GAP,
                          DATA_CATEGORY_COLORS, FONT_FAMILY,
                          FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_KPI,
                          RADIUS_CARD, RADIUS_KPI, SECTION_GAP, TEXT_PRIMARY,
                          TEXT_SECONDARY)
from stats_view_model import company_result
from card_comparisons import company_comparison, CardComparison
from card_comparison_label import ComparisonLabel


KPI_KEYS = ('cashflow', 'company-value', 'monthly-ticket', 'satisfaction-speed',
            'reputation', 'popularity')
DEFAULT_SLOTS = ('cashflow', 'company-value', 'popularity', 'monthly-ticket')


def _display(value) -> str:
    if value is None:
        return label('missing')
    text = f'{value:,.0f}' if value == value.to_integral_value() else f'{value:,.2f}'.rstrip('0').rstrip('.')
    return text


from stats_elevation import attach_card_elevation
from stats_motion import CollapseMotion


class KpiCard(QFrame):
    _ICONS = {
        'cashflow': FluentIcon.MARKET, 'company-value': FluentIcon.CERTIFICATE,
        'monthly-ticket': FluentIcon.TAG, 'satisfaction-speed': FluentIcon.EMOJI_TAB_SYMBOLS,
        'reputation': FluentIcon.ASTERISK, 'popularity': FluentIcon.PEOPLE,
    }

    def __init__(self, title: str, parent=None, metric_key: str = '', color: str = CHART_BLUE):
        super().__init__(parent)
        self.color = color
        self.setObjectName('companyKpiCard')
        attach_card_elevation(self, radius=RADIUS_KPI)
        self.setMinimumHeight(80)
        self.setStyleSheet(f'QFrame#companyKpiCard {{ background: {CARD_BG}; border: 1px solid {BORDER}; '
                           f'border-radius: {RADIUS_KPI}px; }}')
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 6)
        root.setSpacing(1)
        self.header_host = QWidget(self)
        self.header_host.setFixedHeight(28)
        self.header_layout = QHBoxLayout(self.header_host)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(6)
        self.icon = IconWidget(self)
        self.icon.setIcon(self._ICONS.get(metric_key, FluentIcon.PIE_SINGLE).icon(color=QColor(color)))
        self.icon.setFixedSize(18, 18)
        self.title = QLabel(title, self)
        self.title.setStyleSheet(f'color: {TEXT_SECONDARY}; font-family: "{FONT_FAMILY}"; font-size: {FONT_SIZE_CAPTION}px;')
        self.header_layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)
        self.header_layout.addWidget(self.title, 1, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self.header_host)
        self.value = QLabel(label('missing'), self)
        self.value.setStyleSheet(f'color: {TEXT_PRIMARY}; {emphasis_css(FONT_SIZE_KPI)}')
        apply_emphasis_font(self.value, FONT_SIZE_KPI)
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.unit = QLabel('', self)
        self.unit.setStyleSheet(f'color: {TEXT_SECONDARY}; {emphasis_css(FONT_SIZE_CAPTION)}')
        apply_emphasis_font(self.unit, FONT_SIZE_CAPTION)
        self.value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.unit.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self._update_unit_baseline()
        self.value.installEventFilter(self)
        self.unit.installEventFilter(self)
        number_row = QHBoxLayout()
        number_row.setContentsMargins(0, 0, 0, 0)
        number_row.setSpacing(4)
        number_row.addWidget(self.value)
        number_row.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBottom)
        number_row.addStretch()
        root.addLayout(number_row)
        self.comparison_label = ComparisonLabel(parent=self, tooltip_target=self.value)
        root.addWidget(self.comparison_label)

    def _update_unit_baseline(self):
        delta = round(QFontMetricsF(self.value.font()).descent() - QFontMetricsF(self.unit.font()).descent())
        self.value.setContentsMargins(0, 0, 0, max(0, -delta))
        self.unit.setContentsMargins(0, 0, 0, max(0, delta))

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.ApplicationFontChange,
                            QEvent.Type.DevicePixelRatioChange):
            self._update_unit_baseline()
        return super().eventFilter(watched, event)

    def set_result(self, result, owner: str):
        if result is None:
            self.value.setText(label('missing'))
            self.unit.clear()
            self.comparison_label.set_comparison(CardComparison())
            return
        buckets = [bucket for (company, _), series in result.series.items()
                   if company == owner for bucket in series]
        value = summarize_buckets(buckets, result.metric)
        self.value.setText(_display(value))
        self.unit.setText(result.metric.unit if value is not None else '')


class CompanyGroup(QFrame):
    """Compact company identity plus six KPIs and, when applicable, four charts."""

    satisfaction_changed = Signal(str)
    summary_toggled = Signal(bool)

    def __init__(self, company_id: str, name: str, color: str, *, charts: bool,
                 satisfaction: str = 'satisfaction-speed', parent=None):
        super().__init__(parent)
        self.company_id = company_id
        self.full_name = name
        self.setObjectName('companyGroup')
        self.setStyleSheet('QFrame#companyGroup { background: transparent; border: 0; }')
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(CONTROL_GAP)
        self.summary_card = QFrame(self)
        self.summary_card.setObjectName('companySummaryCard')
        attach_card_elevation(self.summary_card, radius=RADIUS_CARD)
        self.summary_card.setStyleSheet(f'QFrame#companySummaryCard {{ background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: {RADIUS_CARD}px; }}')
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(CARD_PADDING, 8, CARD_PADDING, CARD_PADDING)
        summary_layout.setSpacing(CONTROL_GAP)
        root.addWidget(self.summary_card)
        header = QHBoxLayout()
        dot = QLabel('●', self.summary_card)
        dot.setStyleSheet(f'color: {color}; font-size: {FONT_SIZE_BODY}px;')
        self.color_dot = dot
        self.name_label = QLabel(name, self.summary_card)
        self.name_label.setToolTip(name)
        self.name_label.setAccessibleName(name)
        self.name_label.setStyleSheet(f'color: {TEXT_PRIMARY}; {emphasis_css(FONT_SIZE_BODY)}')
        apply_emphasis_font(self.name_label, FONT_SIZE_BODY)
        header.addWidget(dot)
        header.addWidget(self.name_label, 1)
        self.summary_button = SummaryToggleButton(self.summary_card)
        self.summary_button.setFixedSize(24, 24)
        self.summary_button.clicked.connect(lambda: self.summary_toggled.emit(not self.summary_button.collapsed))
        header.addWidget(self.summary_button)
        summary_layout.addLayout(header)
        self.kpi_host = QWidget(self.summary_card)
        self.kpi_grid = QGridLayout(self.kpi_host)
        self.kpi_grid.setContentsMargins(0, 0, 0, 0)
        self.kpi_grid.setSpacing(CONTROL_GAP)
        self.kpis = {key: KpiCard(label(key), self.kpi_host, key, color) for key in KPI_KEYS}
        summary_layout.addWidget(self.kpi_host)
        self.summary_motion = CollapseMotion(self.kpi_host, self._summary_finished, self.summary_card)
        self.summary_motion.on_progress = self._summary_finished
        self.panels = {}
        self.satisfaction_toolbar = None
        satisfaction_tile = self.kpis['satisfaction-speed']
        self.satisfaction_combo = FluentComboBox(satisfaction_tile)
        self.satisfaction_combo.setFixedHeight(28)
        self.satisfaction_combo.setStyleSheet(self.satisfaction_combo.styleSheet() +
            f'\nComboBox {{ color: {TEXT_SECONDARY}; font-family: "{FONT_FAMILY}"; font-size: {FONT_SIZE_CAPTION}px; font-weight: 400; }}')
        self.satisfaction_combo.setToolTip('满意度维度')
        self.satisfaction_combo.setAccessibleName('满意度维度')
        for key in ('satisfaction-speed', 'satisfaction-cost', 'satisfaction-quality'):
            self.satisfaction_combo.addItem(label(key), userData=key)
        self.satisfaction_combo.setCurrentIndex(max(0, self.satisfaction_combo.findData(satisfaction)))
        self.satisfaction_combo.currentIndexChanged.connect(
            lambda _=0: self.satisfaction_changed.emit(self.satisfaction_combo.currentData()))
        satisfaction_tile.title.hide()
        satisfaction_tile.header_layout.addWidget(self.satisfaction_combo, 1, Qt.AlignmentFlag.AlignVCenter)
        if charts:
            self.chart_host = QWidget(self)
            self.chart_grid = QGridLayout(self.chart_host)
            self.chart_grid.setContentsMargins(0, 0, 0, 0)
            self.chart_grid.setSpacing(CONTROL_GAP)
            root.addWidget(self.chart_host)
        else:
            self.chart_host = None
            self.chart_grid = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = max(20, self.name_label.width())
        self.name_label.setText(QFontMetrics(self.name_label.font()).elidedText(
            self.full_name, Qt.TextElideMode.ElideRight, width))

    def reflow(self, kpi_columns: int, chart_columns: int):
        for tile in self.kpis.values():
            self.kpi_grid.removeWidget(tile)
        for index, key in enumerate(KPI_KEYS):
            self.kpi_grid.addWidget(self.kpis[key], index // kpi_columns, index % kpi_columns)
        if self.chart_grid is not None:
            for panel in self.panels.values():
                self.chart_grid.removeWidget(panel)
            for index, panel in enumerate(self.panels.values()):
                self.chart_grid.addWidget(panel, index // chart_columns, index % chart_columns)

    def set_summary_collapsed(self, collapsed):
        self.summary_button.set_collapsed(collapsed)
        if self.summary_motion.collapsed != bool(collapsed):
            self.summary_motion.set_collapsed(collapsed)

    def _summary_finished(self):
        dashboard = self.parentWidget()
        while dashboard is not None and not isinstance(dashboard, CompanyDashboard):
            dashboard = dashboard.parentWidget()
        if dashboard is not None:
            dashboard.reflow(dashboard._content_width, dashboard._viewport_height)

    def chart_fit_chrome(self) -> int:
        """Height occupied by everything except the two chart rows."""
        layout = self.layout()
        margins = layout.contentsMargins()
        other_items = sum((self.summary_card.height() if self.summary_motion.animation
                           and layout.itemAt(index).widget() is self.summary_card
                           else layout.itemAt(index).sizeHint().height())
                          for index in range(layout.count())
                          if layout.itemAt(index).widget() is not self.chart_host
                          and not (layout.itemAt(index).widget() and layout.itemAt(index).widget().isHidden()))
        return (margins.top() + margins.bottom() +
                layout.spacing() * (layout.count() - 1) + other_items +
                2 * self.frameWidth() + self.chart_grid.spacing())


class CompanyDashboard(QWidget):
    """Present company identity without inventing summary fields."""

    satisfaction_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('companyDashboard')
        self.groups: dict[str, CompanyGroup] = {}
        self.shared_panels: dict[str, ChartPanel] = {}
        self._slots = DEFAULT_SLOTS
        self._content_width = 1120
        self._viewport_height = 0
        self._mode = 'default'
        self._summary_collapsed = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SECTION_GAP)
        self.notice = QLabel('', self)
        self.notice.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY}px;')
        root.addWidget(self.notice)
        self.group_host = QWidget(self)
        self.group_grid = QGridLayout(self.group_host)
        self.group_grid.setContentsMargins(0, 0, 0, 0)
        self.group_grid.setSpacing(SECTION_GAP)
        root.addWidget(self.group_host)
        self.shared_host = QWidget(self)
        self.shared_grid = QGridLayout(self.shared_host)
        self.shared_grid.setContentsMargins(0, 0, 0, 0)
        self.shared_grid.setSpacing(SECTION_GAP)
        root.addWidget(self.shared_host)
        root.addStretch()

    def clear(self):
        for grid in (self.group_grid, self.shared_grid):
            while grid.count():
                item = grid.takeAt(0)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()
        self.groups = {}
        self.shared_panels = {}
        self.notice.clear()

    def render(self, snapshot, company_ids: tuple[str, ...], names: dict[str, str],
               palette: dict[str, str], mode: str, satisfaction: str,
               slots: tuple[str, ...], comparison_label: str = '对比'):
        self.clear()
        self._mode, self._slots = mode, slots
        self.notice.setText('请选择公司' if not company_ids else
                            '请选择至少两家公司进行对比' if mode == 'companies' and len(company_ids) < 2 else '')
        self.notice.setVisible(bool(self.notice.text()))
        for company_id in company_ids:
            group = CompanyGroup(company_id, names.get(company_id, company_id),
                                 palette[company_id], charts=mode != 'companies',
                                 satisfaction=satisfaction, parent=self.group_host)
            self.groups[company_id] = group
            group.set_summary_collapsed(self._summary_collapsed)
            group.summary_toggled.connect(self.set_summary_collapsed)
            group.satisfaction_changed.connect(self.satisfaction_changed)
            for key, tile in group.kpis.items():
                metric_key = satisfaction if key == 'satisfaction-speed' else key
                tile.title.setText(label(metric_key))
                tile.set_result(snapshot.results.get(metric_key), company_id)
                tile.comparison_label.set_comparison(company_comparison(snapshot, mode, metric_key, company_id, names))
            if mode != 'companies':
                for index, slot in enumerate(slots):
                    key = satisfaction if slot == 'satisfaction-speed' else slot
                    panel = ChartPanel(label(key), modes=False,
                                       default_mode='trend-bar' if key == 'cashflow' else 'line',
                                       parent=group.chart_host)
                    panel.set_mode_options(('trend-bar',) if key == 'cashflow' else ('line',))
                    panel.set_mode_labels({'line': '趋势', 'trend-bar': '趋势',
                                           'bar': '分布', 'pie': '比例'})
                    panel.set_compact_layout(True)
                    panel.set_company_palette(palette)
                    panel.set_category_palette(DATA_CATEGORY_COLORS)
                    panel.set_comparison_label(comparison_label)
                    result = snapshot.results.get(key)
                    if result is not None:
                        panel.set_result(company_result(result, (company_id,), include_comparison=mode == 'period'), names)
                    group.panels[slot] = panel
                    panel.hover_offset_changed.connect(
                        lambda seconds, current_slot=slot, source=panel:
                        self._relay_hover(current_slot, source, seconds))
        if mode == 'companies':
            for index, slot in enumerate(slots):
                key = satisfaction if slot == 'satisfaction-speed' else slot
                panel = ChartPanel(label(key), modes=False,
                                   default_mode='trend-bar' if key == 'cashflow' else 'line',
                                   parent=self.shared_host)
                panel.set_mode_options(('trend-bar',) if key == 'cashflow' else ('line',))
                panel.set_mode_labels({'line': '趋势', 'trend-bar': '趋势',
                                       'bar': '分布', 'pie': '比例'})
                panel.set_compact_layout(True)
                panel.set_company_palette(palette)
                panel.set_category_palette(DATA_CATEGORY_COLORS)
                result = snapshot.results.get(key)
                if result is not None:
                    panel.set_result(company_result(result, company_ids, include_comparison=False), names)
                self.shared_panels[slot] = panel
        self._align_axes(snapshot, satisfaction, mode)
        self.reflow(self._content_width)

    def _relay_hover(self, slot: str, source: ChartPanel, seconds: float | None):
        for group in self.groups.values():
            other = group.panels.get(slot)
            if other is not None and other is not source:
                other.set_hover_offset(seconds)

    def _align_axes(self, snapshot, satisfaction: str, mode: str):
        for slot in self._slots:
            key = satisfaction if slot == 'satisfaction-speed' else slot
            result = snapshot.results.get(key)
            if result is None:
                continue
            values = [bucket.value for source in (result.series, result.comparison if mode == 'period' else {})
                      for buckets in source.values() for bucket in buckets if bucket.value is not None]
            if not values:
                continue
            spec = nice_axis(values)
            panels = ([group.panels[slot] for group in self.groups.values()] if mode != 'companies'
                      else [self.shared_panels[slot]])
            for panel in panels:
                panel.set_axis_spec(spec)

    def set_summary_collapsed(self, collapsed):
        self._summary_collapsed = bool(collapsed)
        for group in self.groups.values():
            group.set_summary_collapsed(collapsed)
        if not any(group.summary_motion.animation for group in self.groups.values()):
            self.reflow(self._content_width, self._viewport_height)

    def reflow(self, content_width: int, viewport_height: int | None = None):
        self._content_width = content_width
        if viewport_height is not None:
            self._viewport_height = viewport_height
        group_columns = 2 if content_width >= 720 and len(self.groups) > 1 else 1
        for group in self.groups.values():
            self.group_grid.removeWidget(group)
        for index, group in enumerate(self.groups.values()):
            self.group_grid.addWidget(group, index // group_columns, index % group_columns)
            fit_charts = (self._mode in ('default', 'period') and
                          self._viewport_height > 0 and len(self.groups) <= 2)
            dense = fit_charts and len(self.groups) == 2
            padding = 8 if dense else CARD_PADDING
            group.layout().setContentsMargins(0, 0, 0, 0)
            group.summary_card.layout().setContentsMargins(padding, 8, padding, padding)
            group.summary_card.layout().setSpacing(4 if dense else CONTROL_GAP)
            group.layout().setSpacing(6 if dense else CONTROL_GAP)
            group.kpi_grid.setSpacing(4 if dense else CONTROL_GAP)
            if group.chart_grid is not None:
                group.chart_grid.setSpacing(6 if dense else CONTROL_GAP)
            for tile in group.kpis.values():
                tile.setMinimumHeight(84 if dense else 96)
                tile.layout().setContentsMargins(10, 4 if dense else 6, 10, 4 if dense else 6)
            kpi_columns = (6 if len(self.groups) == 1 and content_width >= 1120 else
                           3 if content_width >= 1120 else
                           1 if len(self.groups) > 1 and content_width < 850 else 2)
            chart_columns = 2 if (content_width >= 1120 or len(self.groups) == 1 and content_width >= 720) else 1
            group.setMinimumHeight(0)
            group.setMaximumHeight(16777215)
            for panel in group.panels.values():
                if not (fit_charts and chart_columns == 2):
                    panel.clear_compact_height()
                    panel.setMaximumHeight(16777215)
                    panel.setMinimumHeight(248 if len(self.groups) == 1 and chart_columns == 2 else 300)
            group.reflow(kpi_columns, chart_columns)
            if fit_charts and group.panels and chart_columns == 2:
                chrome = group.chart_fit_chrome()
                height = max(180, (self._viewport_height - chrome) // 2)
                for panel in group.panels.values():
                    if (getattr(panel, '_compact_height', None) != height or
                            panel.minimumHeight() != height):
                        if getattr(panel, '_compact_height', None) is None:
                            panel.set_compact_height(height)
                        else:
                            panel._compact_height = height
                            panel.setFixedHeight(height)
                            for view in panel.chart_views:
                                view.setMinimumHeight(min(view.minimumHeight(), max(90, height - 112)))
                group.setFixedHeight(chrome + 2 * height)
        for panel in self.shared_panels.values():
            self.shared_grid.removeWidget(panel)
        chart_columns = 2 if content_width >= 720 else 1
        fit_shared = (self._mode == 'companies' and chart_columns == 2 and
                      self._viewport_height > 0 and bool(self.shared_panels))
        for index, panel in enumerate(self.shared_panels.values()):
            self.shared_grid.addWidget(panel, index // chart_columns, index % chart_columns)
            if not fit_shared:
                panel.clear_compact_height()
                panel.setMaximumHeight(16777215)
                panel.setMinimumHeight(248 if chart_columns == 2 else 300)
        if fit_shared:
            group_rows = (len(self.groups) + group_columns - 1) // group_columns
            group_height = sum(max(
                (group.summary_card.height() if group.summary_motion.animation else
                 group.summary_card.sizeHint().height())
                for group in list(self.groups.values())[row * group_columns:(row + 1) * group_columns])
                for row in range(group_rows))
            group_height += max(0, group_rows - 1) * self.group_grid.spacing()
            margins = self.layout().contentsMargins()
            chrome = (group_height + margins.top() + margins.bottom() +
                      self.layout().spacing() + self.shared_grid.spacing())
            if self.notice.isVisible():
                chrome += self.notice.height() + self.layout().spacing()
            chart_height = max(180, (self._viewport_height - chrome) // 2)
            for panel in self.shared_panels.values():
                if (getattr(panel, '_compact_height', None) != chart_height or
                        panel.minimumHeight() != chart_height):
                    if getattr(panel, '_compact_height', None) is None:
                        panel.set_compact_height(chart_height)
                    else:
                        panel._compact_height = chart_height
                        panel.setFixedHeight(chart_height)
                        for view in panel.chart_views:
                            view.setMinimumHeight(min(view.minimumHeight(), max(90, chart_height - 112)))
        self.shared_host.setVisible(bool(self.shared_panels))
