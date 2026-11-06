"""Five city KPI positions and six charts sharing one immutable query snapshot."""
from __future__ import annotations
from stats_typography import emphasis_css, apply_emphasis_font
from stats_icons import colored_icon
from decimal import Decimal
from hashlib import sha256
from PySide6.QtCore import Qt, QSize, QEvent, QTimer
from PySide6.QtGui import QColor, QFontMetricsF
from PySide6.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, IconWidget
from city_model import CHART_KEYS, CityValue
from display_rules import format_number
from stats_charts import ChartPanel
from stats_controls import FluentSegmentedControl, SummaryToggleButton
import stats_tokens as tokens
from stats_motion import SurfaceMotion, CollapseMotion
from stats_elevation import attach_card_elevation
from card_comparison_label import ComparisonLabel
from semantic_colors import SOCIAL, stable_color
from stats_text import label
from filter_summary import summary_window
from statistics_model import summarize_buckets

MODE_COLORS = {'步行': '#1677FF', '公共交通': '#159A79', '私家车': '#F5A653'}
SERIES_COLORS = {**MODE_COLORS, '平均': '#1677FF', **{item.key: item.color for item in SOCIAL}, '经济增长率': '#1677FF',
    '利率': '#F5A653', '电力': '#1677FF', '柴油': '#F5A653'}


def series_color(group):
    transport = tokens.transport_color(group)
    if transport is not None:
        return QColor(transport)
    return SERIES_COLORS.get(group, tokens.DATA_CATEGORY_COLORS[
        int.from_bytes(sha256(group.encode()).digest()[:4], 'big') % len(tokens.DATA_CATEGORY_COLORS)])


def number(value):
    return format_number(value)


class CityTile(QFrame):
    def __init__(self, title, icon, parent):
        super().__init__(parent)
        self.setObjectName('cityTile')
        attach_card_elevation(self, radius=tokens.RADIUS_KPI)
        self.setMinimumHeight(132)
        self.setStyleSheet(f'QFrame#cityTile {{ background: {tokens.CARD_BG}; border: 1px solid '
                           f'{tokens.BORDER}; border-radius: {tokens.RADIUS_KPI}px; }}')
        box = QVBoxLayout(self)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(4)
        heading = QHBoxLayout()
        image = IconWidget(colored_icon(icon, tokens.CHART_BLUE), self)
        image.setFixedSize(18, 18)
        heading.addWidget(image)
        self.title = QLabel(title)
        self.title.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};font-size:12px;')
        self.title.setWordWrap(True)
        heading.addWidget(self.title, 1)
        box.addLayout(heading)
        self.value_host = QWidget(self)
        self.values = QVBoxLayout(self.value_host)
        self.values.setContentsMargins(0, 0, 0, 0)
        self.values.setSpacing(3)
        box.addWidget(self.value_host, 1)
        self.model = None
        self._baseline_pairs = []
        self._hover_fields = []

    def set_value(self, model: CityValue):
        self.model = model
        self._baseline_pairs = []
        self._hover_fields = []
        while self.values.count():
            item = self.values.takeAt(0)
            item.widget().hide()
            item.widget().deleteLater()
        for detail in model.details or (model,):
            row = QWidget(self)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            if model.details:
                title = QLabel(('● ' if detail.title in MODE_COLORS else '') + detail.title)
                title.setStyleSheet(f'font-size:12px;color:{series_color(detail.title) if detail.title in MODE_COLORS else tokens.TEXT_SECONDARY};')
                layout.addWidget(title)
            value, unit = detail.value, detail.unit
            if model.title == '人口' and value is not None and abs(value) >= 10000:
                value, unit = value / 10000, '万人'
            text = QLabel(number(value))
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value_size = 16 if model.details else tokens.FONT_SIZE_KPI
            text.setStyleSheet(f'{emphasis_css(value_size)}color:{tokens.TEXT_PRIMARY};')
            apply_emphasis_font(text, value_size)
            layout.addWidget(text)
            suffix = QLabel(unit if value is not None else '')
            suffix.setStyleSheet(f'{emphasis_css(12)}color:{tokens.TEXT_SECONDARY};')
            apply_emphasis_font(suffix, 12)
            text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
            suffix.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
            self._baseline_pairs.append((text, suffix))
            self._update_unit_baselines()
            text.installEventFilter(self)
            suffix.installEventFilter(self)
            layout.addWidget(suffix, 0, Qt.AlignmentFlag.AlignBottom)
            layout.addStretch()
            self.values.addWidget(row)
            if model.title != '交通方式分担率' or detail.title == '公共交通':
                comparison = ComparisonLabel(detail.comparison, self.value_host)
                self.values.addWidget(comparison)
            self._hover_fields.append((row, text, suffix, detail, value))
            text.setAccessibleName(f'{number(detail.value)} {detail.unit}'.strip())
        self._update_hover_fields()

    def _update_hover_fields(self):
        if self.model is None:
            return
        tooltip = []
        for row, text, suffix, detail, shown_value in self._hover_fields:
            stamp = detail.observed.strftime('%Y-%m-%d %H:%M') if detail.observed else '无有效观测'
            parts = [f'{detail.title}：{stamp}' if self.model.details else stamp]
            clipped = any(label.fontMetrics().horizontalAdvance(label.text()) > label.contentsRect().width()
                          for label in (text, suffix))
            exact_count_hidden = (self.model.title == '人口' and detail.value is not None
                                  and abs(detail.value) >= 10000
                                  and Decimal(number(shown_value).replace(',', '')) * 10000 != detail.value)
            if clipped or exact_count_hidden:
                parts.insert(0, f'{detail.title}：{number(detail.value)} {detail.unit}'.strip())
            if detail.reason:
                parts.append(detail.reason)
            if not detail.complete:
                parts.append('数据不完整')
            tip = '；'.join(parts)
            row.setToolTip(tip)
            tooltip.append(tip)
        if self.model.reason and self.model.reason not in '\n'.join(tooltip):
            tooltip.append(self.model.reason)
        self.setToolTip('\n'.join(tooltip))

    def _update_unit_baselines(self):
        for value, unit in self._baseline_pairs:
            delta = round(QFontMetricsF(value.font()).descent() - QFontMetricsF(unit.font()).descent())
            value.setContentsMargins(0, 0, 0, max(0, -delta))
            unit.setContentsMargins(0, 0, 0, max(0, delta))

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.ApplicationFontChange,
                            QEvent.Type.DevicePixelRatioChange):
            self._update_unit_baselines()
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.FontChange,
                            QEvent.Type.ApplicationFontChange, QEvent.Type.DevicePixelRatioChange):
            self._update_hover_fields()
        return super().eventFilter(watched, event)


class CityChartPanel(ChartPanel):
    def __init__(self, key, parent=None):
        self.city_key = key
        self.curve_control = None
        self.city_controller = None
        super().__init__({'population': '人口变化', 'trip-number': '出行量',
            'city-mode-share': '交通方式分担率', 'trip-time': '出行时间',
            'economy': '经济增长与利率', 'energy-prices': '能源价格'}[key],
            default_mode='trend-bar' if key == 'trip-number' else 'line', parent=parent)
        self.setMinimumWidth(0)
        self.motion = self.surface_motion

    def _category_color(self, group):
        return QColor(series_color(group))

    def _toggle_category(self, group):
        super()._toggle_category(group)
        if self.city_key == 'trip-time' and self.city_controller and self.result:
            self.city_controller.set_curves(tuple(g for _, g in self.result.series
                                                 if g not in self._hidden_groups))

    def _company_color(self, owner):
        if self.result and len(self.result.series) == 1:
            group = next(iter(self.result.series))[1]
            return QColor(series_color(group))
        return QColor(tokens.CHART_BLUE)

    def _series_options(self, company, group, previous):
        return dict(area=False, width=2.8 if group == '平均' else 2.0)

    def _donut_center(self, total, unit):
        if self.city_key == 'city-mode-share' and self.result is not None:
            return self._mode_share_center(self.result.series)
        return '', ''

    def _mode_share_center(self, source):
        value = summarize_buckets(source.get(('', '公共交通'), []), self.result.metric)
        return (f'{number(value)} %' if value is not None else label('missing'), '公共交通分担率')

    def _donut_data(self, company, categories):
        data = super()._donut_data(company, categories)
        if self.city_key == 'city-mode-share':
            data.center_key = '公共交通'
            data.donut_value_labels = True
        return data

    def _chart_specs(self):
        if self.mode != 'pie' or self.result is None or not self.result.comparison:
            specs = super()._chart_specs()
            if self.city_key == 'trip-time':
                for _, data in specs:
                    data.hidden_series_text = '曲线已隐藏，点击图例显示'
            return specs
        output = []
        for previous, source, window in (
            (False, self.result.series, self.result.current_window),
            (True, self.result.comparison, self.result.comparison_window)):
            data = self._donut_data('', {group: buckets for (_, group), buckets in source.items()})
            if self.city_key == 'city-mode-share':
                data.center_text, data.center_caption = self._mode_share_center(source)
            data.donut_legend = False
            data.series[0].faded = previous
            title = self._comparison_name() if previous else label('current')
            data.series[0].name = f'{title} · {summary_window(window)}'
            output.append((f'{title}\n{summary_window(window)}', data))
        return output

    def _place_specs(self, specs):
        super()._place_specs(specs)
        if self.mode == 'pie' and len(specs) == 2:
            self._layout_pies()

    def _layout_pies(self):
        if self.mode != 'pie' or len(self.chart_views) != 2:
            return False
        columns = 2 if self.chart_host.width() >= 360 else 1
        changed = columns != getattr(self, '_pie_columns', None)
        self._pie_columns = columns
        for index, canvas in enumerate(self.chart_views):
            compact = self._compact_height is not None and self._compact_height <= 190
            canvas.setMinimumHeight(0 if compact else 170)
            cell = canvas.parentWidget()
            cell._chart_heading.setWordWrap(True)
            self.chart_layout.removeWidget(cell)
            self.chart_layout.addWidget(cell, index // columns, index % columns)
        width = max(1, (self.chart_host.width() - self.chart_layout.horizontalSpacing() * (columns - 1)) // columns)
        headings = [canvas.parentWidget()._chart_heading for canvas in self.chart_views]
        heading_height = max(max(heading.fontMetrics().height() * 2, heading.heightForWidth(width))
                             for heading in headings)
        for heading in headings:
            heading.setMinimumHeight(heading_height)
        return changed

    def resizeEvent(self, event):
        super().resizeEvent(event)
        columns_changed = self._layout_pies()
        paired = self.mode == 'pie' and len(self.chart_views) == 2
        width_changed = event.size().width() != event.oldSize().width()
        if paired and (columns_changed or width_changed) and self.city_controller and not self._detailed:
            QTimer.singleShot(0, self.city_controller, self.city_controller._summary_reflow)

    def _point_note(self, company, group, bucket, previous):
        parts = []
        if bucket.observed:
            parts.append(f'实际观测 {bucket.observed:%Y-%m-%d %H:%M}')
        if not bucket.complete:
            parts.append('数据不完整')
        return ' · '.join(parts)

    def _create_clone(self, dialog):
        clone = CityChartPanel(self.city_key, dialog)
        clone.city_controller = self.city_controller
        clone._hidden_groups = set(self._hidden_groups)
        clone._category_choices = dict(self._category_choices)
        clone.set_comparison_label(self._comparison_label)
        clone.set_mode(self.mode)
        clone.set_result(self.result)
        if self.city_controller:
            self.city_controller.attach_controls(clone, fullscreen=True)
        dialog.city_panel = clone
        if self.city_controller and self.city_controller.snapshot:
            filters = self.city_controller.snapshot.filters
            caption = QLabel(f'{filters.start:%Y-%m-%d %H:%M} 至 {filters.end:%Y-%m-%d %H:%M} · '
                             f'{dict(hour="小时", day="日", week="周", month="月")[filters.grain]}', dialog)
            caption.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};')
            dialog.layout().addWidget(caption)
        return clone


class CityDashboard(QWidget):
    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.snapshot = None
        self.selected_curves = ('平均',)
        self.mode_preference = None
        self.summary_collapsed = False
        self.chart_columns = 3
        self._layout_signature = None
        self._available_width = 1200
        self._available_height = 850
        self.motion = SurfaceMotion(self)
        self.panels, self.tiles = {}, {}
        if settings:
            saved = settings.value('city/curves', ['平均'])
            if isinstance(saved, (list, tuple)) and saved:
                self.selected_curves = tuple(saved)
            saved_mode = settings.value('city/mode', '')
            self.mode_preference = saved_mode if saved_mode in ('pie', 'line') else None
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(10)
        self.summary = QFrame(self)
        self.summary.setObjectName('citySummary')
        attach_card_elevation(self.summary, radius=12)
        self.summary.setStyleSheet(f'QFrame#citySummary {{background:{tokens.CARD_BG};border:1px solid '
                                  f'{tokens.BORDER};border-radius:12px;}}')
        summary_layout = QVBoxLayout(self.summary)
        summary_layout.setContentsMargins(10, 8, 10, 10)
        header = QHBoxLayout()
        self.city_title = QLabel('城市核心指标')
        self.city_title.setStyleSheet(f'{emphasis_css(14)}color:{tokens.TEXT_PRIMARY};')
        apply_emphasis_font(self.city_title, 14)
        header.addWidget(self.city_title, 1)
        self.summary_button = SummaryToggleButton(self.summary)
        self.summary_button.clicked.connect(lambda: self.set_summary_collapsed(not self.summary_collapsed))
        header.addWidget(self.summary_button)
        summary_layout.addLayout(header)
        self.kpi_host = QWidget(self.summary)
        self.kpi_grid = QGridLayout(self.kpi_host)
        self.kpi_grid.setContentsMargins(0, 0, 0, 0)
        self.kpi_grid.setSpacing(8)
        for key, title, icon in zip(('population', 'trip-number', 'city-mode-share', 'trip-time', 'traffic-density'),
            ('人口', '出行量', '交通方式分担率', '平均出行时间', '最大交通密度'),
            (FluentIcon.PEOPLE, FluentIcon.BUS, FluentIcon.PIE_SINGLE, FluentIcon.HISTORY, FluentIcon.MARKET)):
            self.tiles[key] = CityTile(title, icon, self.kpi_host)
            self.tiles[key].set_value(CityValue(title))
        summary_layout.addWidget(self.kpi_host)
        self.summary_motion = CollapseMotion(self.kpi_host, self._summary_reflow, self.summary)
        self.summary_motion.on_progress = self._summary_reflow
        box.addWidget(self.summary)
        self.chart_host = QWidget(self)
        self.chart_grid = QGridLayout(self.chart_host)
        self.chart_grid.setContentsMargins(0, 0, 0, 0)
        self.chart_grid.setSpacing(10)
        for key in CHART_KEYS:
            panel = CityChartPanel(key, self.chart_host)
            panel.city_controller = self
            self.panels[key] = panel
            self.attach_controls(panel)
        box.addWidget(self.chart_host, 1)
        self.reflow(1200, 850)

    def attach_controls(self, panel, fullscreen=False):
        if panel.city_key == 'city-mode-share':
            control = FluentSegmentedControl(panel, compact=True, dense=True)
            control.addItem('pie', '饼图')
            control.addItem('line', '折线图')
            control.setCurrentKey(panel.mode if panel.mode in ('pie', 'line') else 'line')
            control.currentKeyChanged.connect(lambda key: self._mode_for_panel(key, panel, fullscreen))
            panel.mode_control = control
            panel._header_layout.insertWidget(1, control)
            self._sync_mode_control(panel)

    def _sync_mode_control(self, panel):
        if not hasattr(panel, 'mode_control'):
            return
        valid = bool(self.snapshot and self.snapshot.pie_valid)
        panel.mode_control.setItemEnabled('pie', valid)
        panel.mode_control.setToolTip(self.snapshot.pie_reason if self.snapshot else '尚未载入数据')
        panel.mode_control.blockSignals(True)
        panel.mode_control.setCurrentKey(panel.mode)
        panel.mode_control.blockSignals(False)

    def _time_result(self):
        # Keep hidden series in the result so their legend buttons remain available.
        return self.snapshot.charts['trip-time']

    def set_curves(self, groups):
        self.selected_curves = tuple(dict.fromkeys(groups))
        if self.settings:
            self.settings.setValue('city/curves', list(self.selected_curves))
        if self.snapshot:
            panel = self.panels['trip-time']
            panels = [panel]
            dialog = getattr(panel, '_fullscreen_dialog', None)
            if dialog is not None and dialog.isVisible():
                panels.append(dialog.city_panel)
            for target in panels:
                target._hidden_groups = {g for _, g in self._time_result().series
                                         if g not in self.selected_curves}
                for _, group in self._time_result().series:
                    target._apply_category(group)

    def _mode_for_panel(self, mode, panel, fullscreen):
        self.set_mode(mode)

    def set_mode(self, mode):
        if not self.snapshot:
            return
        if mode == 'pie' and not self.snapshot.pie_valid:
            mode = 'line'
        self.mode_preference = mode
        if self.settings:
            self.settings.setValue('city/mode', mode)
        panel = self.panels['city-mode-share']
        targets = [panel]
        surface = panel._fullscreen_dialog
        if surface is not None and surface.isVisible():
            panel._adopt_hidden(surface.panel)
            targets.append(surface.panel)
        result = self.snapshot.pie_result if mode == 'pie' else self.snapshot.charts['city-mode-share']
        for target in targets:
            target.set_presentation(mode, result)
            self._sync_mode_control(target)
        # The new chart cells and legend post layout requests when rendered.
        # Measure the card after those requests have settled.
        QTimer.singleShot(0, self, self._summary_reflow)
        panel.motion.reveal()

    def set_snapshot(self, snapshot, comparison_label='对比期'):
        self.snapshot = snapshot
        for panel in self.panels.values():
            panel.set_comparison_label(comparison_label)
        for key, tile in self.tiles.items():
            tile.set_value(snapshot.kpis[key])
        for key, panel in self.panels.items():
            if key not in ('trip-time', 'city-mode-share'):
                panel.set_result(snapshot.charts[key])
        available = {g for _, g in snapshot.charts['trip-time'].series}
        selected = tuple(g for g in self.selected_curves if g in available)
        if self.selected_curves and not selected and '平均' in available:
            selected = ('平均',)
        self.panels['trip-time'].set_result(self._time_result())
        self.set_curves(selected)
        mode = self.mode_preference or ('pie' if snapshot.pie_valid else 'line')
        if mode == 'pie' and not snapshot.pie_valid:
            mode = 'line'
        # New data replaces the detail; chart-type switches above do not.
        self.panels['city-mode-share'].set_result(
            snapshot.pie_result if mode == 'pie' else snapshot.charts['city-mode-share'])
        self.set_mode(mode)
        self.panels['trip-time'].setToolTip(snapshot.kpis['trip-time'].reason)
        self.panels['energy-prices'].setToolTip('')

    def clear(self):
        self.snapshot = None
        for tile in self.tiles.values():
            tile.set_value(CityValue(tile.title.text()))
        for panel in self.panels.values():
            panel.clear()

    def set_summary_collapsed(self, collapsed):
        self.summary_collapsed = bool(collapsed)
        self.summary_motion.set_collapsed(collapsed)
        self.summary_button.set_collapsed(bool(collapsed))

    def display_state(self):
        return dict(mode=self.panels['city-mode-share'].mode, curves=list(self.selected_curves),
                    hidden={key: sorted(panel._hidden_groups) for key, panel in self.panels.items()})

    def _summary_reflow(self):
        self.reflow(self._available_width, self._available_height)

    def reflow(self, width, height):
        self._available_width = width
        self._available_height = height
        self.chart_columns = columns = 3 if width >= 1100 else 2 if width >= 720 else 1
        kpi_columns = 5 if width >= 1100 else 3 if width >= 720 else 1 if width < 440 else 2
        rows = (6 + columns - 1) // columns
        signature = (columns, kpi_columns)
        if signature != self._layout_signature:
            self._layout_signature = signature
            for grid, widgets, count in ((self.kpi_grid, self.tiles.values(), kpi_columns),
                                         (self.chart_grid, self.panels.values(), columns)):
                while grid.count():
                    grid.takeAt(0)
                for col in range(5):
                    grid.setColumnStretch(col, 1 if col < count else 0)
                for index, widget in enumerate(widgets):
                    grid.addWidget(widget, index // count, index % count,
                                   Qt.AlignmentFlag.AlignTop if grid is self.chart_grid else Qt.AlignmentFlag(0))
            self.summary.layout().invalidate()
        if self.summary_motion.animation is not None:
            summary_height = self.summary.height()
        else:
            summary_height = self.summary.layout().sizeHint().height()
            self.summary.setFixedHeight(summary_height)
        minimum = 245 if columns == 3 else 285
        chart_height = max(minimum, (height - summary_height - 10 - (rows - 1) * 10) // rows)
        for panel in self.panels.values():
            if panel.mode == 'pie' and panel.result and panel.result.comparison:
                panel._layout_pies()
                layout = panel.layout()
                # The legend can wrap at the actual card width. Its generic
                # minimum size only budgets one line.
                legend = panel.legend_host
                margins = layout.contentsMargins()
                width = max(1, panel.width() - margins.left() - margins.right())
                wrapped = legend.heightForWidth(width) - legend.minimumSizeHint().height()
                chart_height = max(chart_height, layout.minimumSize().height() + max(0, wrapped))
        for panel in self.panels.values():
            paired = panel.mode == 'pie' and panel.result and bool(panel.result.comparison)
            if paired:
                panel._layout_pies()
            panel_height = chart_height
            if panel._compact_height is None:
                panel.set_compact_height(panel_height)
            elif panel._compact_height != panel_height or panel.minimumHeight() != panel_height:
                panel._compact_height = panel_height
                panel.setFixedHeight(panel_height)
                for view in panel.chart_views:
                    view.setMinimumHeight(170 if paired else min(view.minimumHeight(), max(90, panel_height - 112)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
