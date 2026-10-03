"""Five city KPI positions and six charts sharing one immutable query snapshot."""
from __future__ import annotations
from stats_typography import emphasis_css, apply_emphasis_font
from decimal import Decimal
from hashlib import sha256
from PySide6.QtCore import Qt, QSize, QEvent
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

MODE_COLORS = {'步行': '#1677FF', '公共交通': '#159A79', '私家车': '#F5A653'}
SERIES_COLORS = {**MODE_COLORS, '平均': '#1677FF', 'WhiteCollar': '#F5A653',
    'BlueCollar': '#159A79', 'BusinessPeople': '#A477E6', 'Pensioner': '#C63864',
    'Student': '#72C7D9', 'Tourist': '#B99027', '经济增长率': '#1677FF',
    '利率': '#F5A653', '电力': '#1677FF', '柴油': '#F5A653'}


def series_color(group):
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
        image = IconWidget(icon.icon(color=QColor(tokens.CHART_BLUE)), self)
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

    def set_value(self, model: CityValue):
        self.model = model
        self._baseline_pairs = []
        while self.values.count():
            item = self.values.takeAt(0)
            item.widget().hide()
            item.widget().deleteLater()
        tooltip = [model.reason]
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
            stamp = detail.observed.strftime('%Y-%m-%d %H:%M') if detail.observed else '无有效观测'
            tip = f'{detail.title}：{number(detail.value)} {detail.unit}；{stamp}；{detail.reason}'
            if detail.comparison.tooltip and detail.comparison.tooltip not in tip:
                tip += '；' + detail.comparison.tooltip
            row.setToolTip(tip)
            tooltip.append(tip)
        tooltip.append('完整自然周期' if model.complete else '已记录部分；存在部分周期、缺测或未完成小时')
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
        # No unproven trip total or normalized price is written into the ring.
        return '', ''

    def _point_note(self, company, group, bucket, previous):
        parts = []
        if bucket.observed:
            parts.append(f'实际观测 {bucket.observed:%Y-%m-%d %H:%M}')
        if not bucket.complete:
            parts.append('部分/缺测/未完成小时')
        if self.city_key == 'energy-prices':
            parts.append('原值÷100；物理单位未确认')
        return ' · '.join(parts)

    def _create_clone(self, dialog):
        clone = CityChartPanel(self.city_key, dialog)
        clone.city_controller = self.city_controller
        clone._hidden_groups = set(self._hidden_groups)
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
            self.selected_curves = tuple(saved) if isinstance(saved, (list, tuple)) else ('平均',)
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
        panel.mode_control.setCurrentKey(panel.mode)

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
        if fullscreen and self.snapshot:
            panel.set_mode(self.panels['city-mode-share'].mode)
            panel.set_result(self.snapshot.pie_result if panel.mode == 'pie' else self.snapshot.charts['city-mode-share'])

    def set_mode(self, mode):
        if not self.snapshot:
            return
        if mode == 'pie' and not self.snapshot.pie_valid:
            mode = 'line'
        self.mode_preference = mode
        if self.settings:
            self.settings.setValue('city/mode', mode)
        panel = self.panels['city-mode-share']
        panel.set_mode(mode)
        panel.set_result(self.snapshot.pie_result if mode == 'pie' else self.snapshot.charts['city-mode-share'])
        self._sync_mode_control(panel)
        panel.motion.reveal()

    def set_snapshot(self, snapshot):
        self.snapshot = snapshot
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
        self.set_mode(self.mode_preference or ('pie' if snapshot.pie_valid else 'line'))
        self.panels['trip-time'].setToolTip(snapshot.kpis['trip-time'].reason)
        self.panels['energy-prices'].setToolTip('游戏显示值 = 原始值 ÷ 100；物理单位未确认')

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
                    grid.addWidget(widget, index // count, index % count)
            self.summary.layout().invalidate()
        if self.summary_motion.animation is not None:
            summary_height = self.summary.height()
        else:
            summary_height = self.summary.layout().sizeHint().height()
            self.summary.setFixedHeight(summary_height)
        minimum = 245 if columns == 3 else 285
        chart_height = max(minimum, (height - summary_height - 10 - (rows - 1) * 10) // rows)
        for panel in self.panels.values():
            if panel._compact_height is None:
                panel.set_compact_height(chart_height)
            elif panel._compact_height != chart_height or panel.minimumHeight() != chart_height:
                panel._compact_height = chart_height
                panel.setFixedHeight(chart_height)
                for view in panel.chart_views:
                    view.setMinimumHeight(min(view.minimumHeight(), max(90, chart_height - 112)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
