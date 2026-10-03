"""Responsive four-board statistics page over a shared dashboard snapshot."""
from __future__ import annotations
from stats_typography import emphasis_css, apply_emphasis_font

import sys
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QDateTime, QEasingCurve, QSize, Qt, QThread, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QAction, QColor, QFontMetrics, QPalette
from shiboken6 import isValid
from PySide6.QtWidgets import (QBoxLayout, QDialog, QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, CheckableMenu, ComboBox as FluentComboBox,
    DoubleSpinBox, DropDownPushButton, FluentIcon, IconWidget,
    Pivot, PrimaryPushButton, PushButton, SubtitleLabel, SwitchButton,
    TransparentToolButton)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))
from dashboard_model import FilterState, build_dashboard
from statistics_model import HistoryStore, parse_time, summarize_buckets
from stats_charts import ChartPanel
from stats_view_model import preset_window, resolve_comparison
from company_dashboard import CompanyDashboard, DEFAULT_SLOTS
from stats_range_picker import RangePicker
from stats_controls import FluentSegmentedControl, StatisticsScrollArea, SummaryToggleButton
from stats_style import CARD_PADDING, CONTROL_GAP, NARROW_MARGIN, PAGE_MARGIN, SECTION_GAP
from stats_text import label, group_label
from stats_integration import configure_dashboard
from network_model import NetworkOptions, build_network_snapshot
from network_dashboard import NetworkDashboard
from city_dashboard import CityDashboard
from city_model import build_city_snapshot
import stats_motion as motion_policy
from stats_tokens import (ACCENT, ACCENT_SOFT, BORDER, CARD_BG, DATA_COMPANY_COLORS,
                          ACTION_BUTTON_WIDTH, CONTROL_HEIGHT,
                          FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_CHART_TITLE,
                          PAGE_BG, TEXT_PRIMARY, TEXT_SECONDARY)

COMPANY = ('cashflow', 'company-value', 'monthly-ticket', 'satisfaction-speed', 'reputation', 'popularity')
SERVICE = ('linecount', 'stopcount', 'depotcount', 'vehicles-running', 'coverage')
PASSENGER = ('transport-by-group', 'transport-by-type', 'trip-types')
CITY = ('population', 'economy', 'energy-prices', 'trip-number', 'city-mode-share', 'traffic-density')


def display(value, coefficient=False):
    if value is None:
        return label('missing')
    number = Decimal(value)
    if coefficient:
        return f'{number:,.2f}'
    if number == number.to_integral_value():
        return f'{number:,.0f}'
    return f'{number:,.2f}'.rstrip('0').rstrip('.')


class DashboardTask(QThread):
    ready = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, token, store, filters, thresholds, parent=None,
                 network_options=None, companies=None):
        super().__init__(parent)
        self.token, self.store, self.filters, self.thresholds = token, store, filters, thresholds
        self.network_options, self.companies = network_options, companies or {}

    def run(self):
        try:
            snapshot = build_dashboard(self.store, self.filters, self.thresholds,
                                       self.isInterruptionRequested)
            if self.network_options is not None:
                network = build_network_snapshot(snapshot, self.network_options,
                                                 self.companies, self.isInterruptionRequested)
                payload = (snapshot, network, build_city_snapshot(self.store, self.filters, self.isInterruptionRequested))
            else:
                payload = snapshot
            if not self.isInterruptionRequested():
                self.ready.emit(self.token, payload)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(self.token, str(exc))


class NetworkModelTask(QThread):
    ready = Signal(int, object, object)
    failed = Signal(int, str)

    def __init__(self, token, source, options, companies, parent=None):
        super().__init__(parent)
        self.token, self.source, self.options, self.companies = token, source, options, companies

    def run(self):
        try:
            network = build_network_snapshot(self.source, self.options, self.companies,
                                             self.isInterruptionRequested)
            if not self.isInterruptionRequested():
                self.ready.emit(self.token, self.source, network)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(self.token, str(exc))


from stats_elevation import attach_card_elevation
from stats_motion import SurfaceMotion, attach_surface_reveal


class MetricTile(CardWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        attach_card_elevation(self)
        self.setObjectName('fluentMetric')
        self.setMinimumWidth(138)
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 16, 16, 16)
        box.setSpacing(4)
        self.title = CaptionLabel(title)
        self.title.setObjectName('cardLabel')
        self.title.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px;')
        self.title.setWordWrap(True)
        row = QWidget(self)
        first = QHBoxLayout(row)
        first.setContentsMargins(0, 0, 0, 0)
        first.setSpacing(6)
        self.owner = CaptionLabel('')
        self.owner.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: 11px;')
        self.owner.setWordWrap(True)
        self.owner.hide()
        self.value = BodyLabel(label('missing'))
        self.value.setObjectName('cardValue')
        self.value.setStyleSheet(f'color: {TEXT_PRIMARY}; {emphasis_css(17)}')
        apply_emphasis_font(self.value, 17)
        self.value.setWordWrap(True)
        first.addWidget(self.owner)
        first.addWidget(self.value, 1)
        box.addWidget(self.title)
        box.addWidget(row)
        self.first_row = row
        self.extra_values = []

    def set_rows(self, rows):
        for row in self.extra_values:
            self.layout().removeWidget(row)
            row.hide()
            row.deleteLater()
        self.extra_values = []
        if not rows:
            self.owner.hide()
            self.value.setText(label('missing'))
            return
        show_owner = len(rows) > 1 or bool(rows[0][0] and ' · ' in rows[0][0])
        self.owner.setText(rows[0][0])
        self.owner.setStyleSheet(f'color: {rows[0][2]}; {emphasis_css(11)}')
        apply_emphasis_font(self.owner, 11)
        self.owner.setVisible(show_owner)
        self.value.setText(rows[0][1])
        for name, number, color in rows[1:]:
            row = QWidget(self)
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(6)
            owner = CaptionLabel(name, row)
            owner.setStyleSheet(f'color: {color}; {emphasis_css(11)}')
            apply_emphasis_font(owner, 11)
            owner.setWordWrap(True)
            value = BodyLabel(number, row)
            value.setObjectName('cardValue')
            value.setStyleSheet(f'color: {TEXT_PRIMARY}; {emphasis_css(17)}')
            apply_emphasis_font(value, 17)
            value.setWordWrap(True)
            line.addWidget(owner)
            line.addWidget(value, 1)
            self.layout().addWidget(row)
            self.extra_values.append(row)


class CategoryTile(MetricTile):
    """One compact cell per transport category, preserving company rows."""

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.category_host = QWidget(self)
        self.category_grid = QGridLayout(self.category_host)
        self.category_grid.setContentsMargins(0, 0, 0, 0)
        self.category_grid.setSpacing(CONTROL_GAP)
        self.layout().addWidget(self.category_host)
        self.category_host.hide()

    def set_rows(self, rows):
        self.category_host.hide()
        self.first_row.show()
        super().set_rows(rows)

    def set_categories(self, groups):
        while self.category_grid.count():
            item = self.category_grid.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        if not groups:
            self.set_rows([])
            return
        self.first_row.hide()
        self.category_host.show()
        for index, (group, values) in enumerate(groups.items()):
            cell = QWidget(self.category_host)
            box = QVBoxLayout(cell)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(2)
            heading = CaptionLabel(group_label(group), cell)
            heading.setWordWrap(True)
            box.addWidget(heading)
            for owner, number, color in values:
                row = QWidget(cell)
                line = QHBoxLayout(row)
                line.setContentsMargins(0, 0, 0, 0)
                line.setSpacing(4)
                if owner:
                    badge = CaptionLabel(owner, row)
                    badge.setStyleSheet(f'color: {color}; {emphasis_css(11)}')
                    apply_emphasis_font(badge, 11)
                    badge.setWordWrap(True)
                    line.addWidget(badge)
                value = BodyLabel(number, row)
                value.setObjectName('categoryValue')
                value.setStyleSheet(f'color: {TEXT_PRIMARY}; {emphasis_css(15)}')
                apply_emphasis_font(value, 15)
                value.setWordWrap(True)
                line.addWidget(value, 1)
                box.addWidget(row)
            self.category_grid.addWidget(cell, index // 3, index % 3)


class CompanyTag(QFrame):
    def __init__(self, name: str, remove, parent=None):
        super().__init__(parent)
        self.setObjectName('companyFilterTag')
        self.setStyleSheet(f'QFrame#companyFilterTag {{ background: {ACCENT_SOFT}; border: 0; '
                           'border-radius: 5px; }')
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 2, 2, 2)
        row.setSpacing(2)
        self.name_label = QLabel(self)
        self.name_label.setText(QFontMetrics(self.name_label.font()).elidedText(
            name, Qt.TextElideMode.ElideRight, 105))
        self.name_label.setToolTip(name)
        self.name_label.setAccessibleName(name)
        self.name_label.setStyleSheet(f'color: {ACCENT}; font-size: 12px;')
        row.addWidget(self.name_label)
        self.close_button = TransparentToolButton(self)
        self.close_button.setText('×')
        self.close_button.setToolTip(f'移除{name}')
        self.close_button.setAccessibleName(f'移除{name}')
        self.close_button.setFixedSize(20, 20)
        self.close_button.clicked.connect(remove)
        row.addWidget(self.close_button)


class StatisticsPage(QWidget):
    snapshot_changed = Signal(object)
    query_failed = Signal(str)
    export_requested = Signal()

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.setObjectName('statsPage')
        self.settings, self.snapshot, self.store = settings, None, None
        self.companies, self.simulation_time, self.session_key, self._short_ids = [], None, '', {}
        self.analysis_mode = 'default'
        self.range_preset = 'previous_full_week'
        self.comparison_preset = 'previous'
        network_mode = str(settings.value('network/mode', 'overall')) if settings else 'overall'
        self.network_options = NetworkOptions(mode=network_mode if network_mode in
                                              ('overall', 'companies', 'period') else 'overall')
        self.network_comparison_preset = str(settings.value('network/comparison', 'previous')) if settings else 'previous'
        if self.network_comparison_preset not in ('previous', 'previous_week', 'previous_month', 'custom'):
            self.network_comparison_preset = 'previous'
        if self.network_comparison_preset == 'custom':
            self.network_comparison_preset = 'previous'
        self.network_snapshot = None
        self.city_snapshot = None
        self.network_model_token = 0
        self.network_workers = []
        self._custom_window = None
        self._custom_comparison = None
        self._network_custom_comparison = None
        self._range_window = None
        self._company_palette = {}
        self.metric_slots = DEFAULT_SLOTS
        keys = ('percentage_points', 'relative_percent', 'passenger_absolute')
        self.thresholds = tuple(float(settings.value('statistics/' + key, default))
                                if settings else default
                                for key, default in zip(keys, (5, 20, 100)))
        self.token, self.workers = 0, []
        self._closing, self._layout_mode, self._layout_signature = False, None, None
        self._filters_collapsed = False
        self._filter_animation = None
        self._filter_animating = False
        self.query_timer = QTimer(self)
        self.query_timer.setSingleShot(True)
        self.query_timer.timeout.connect(self._submit_query)
        self._build()
        configure_dashboard(self, self.settings)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(CONTROL_GAP)
        self.tab_bar = Pivot(self)
        self.tab_bar.setObjectName('statsSubTabs')
        self.tab_bar.setMinimumHeight(40)
        self.tab_bar.setMaximumWidth(480)
        self.tab_bar.setItemFontSize(15)
        self._tab_icons = {'company': FluentIcon.PEOPLE,
                           'network': FluentIcon.BUS, 'city': FluentIcon.GLOBE}
        for route, title, icon in (('company', '公司数据', FluentIcon.PEOPLE),
                                   ('network', '网络数据', FluentIcon.BUS),
                                   ('city', '城市数据', FluentIcon.GLOBE)):
            item = self.tab_bar.addItem(route, title,
                                        icon=icon.icon(color=QColor(ACCENT if route == 'company'
                                                                   else TEXT_SECONDARY)))
            item.setIconSize(QSize(18, 18))
            item.setMinimumHeight(40)
            item.setFixedWidth(148)
            item.setStyleSheet('QPushButton { background: transparent; border: 0; padding: 7px 12px 7px 34px; '
                               'color: #65758B; } QPushButton:hover { background: #E8F2FC; color: #0067C0; } '
                               'QPushButton[isSelected="true"] { color: #0067C0; font-weight: 600; } '
                               'QPushButton:focus { border: 2px solid #0067C0; border-radius: 6px; }')
        self.tab_bar.currentItemChanged.connect(self._tab_changed)
        self.tab_bar.setCurrentItem('company')
        outer.addWidget(self.tab_bar)
        self.filter_card = CardWidget(self)
        attach_card_elevation(self.filter_card)
        self.filter_card.setObjectName('filterCard')
        filter_shell = QHBoxLayout(self.filter_card)
        filter_shell.setContentsMargins(0, 0, 0, 0)
        filter_shell.setSpacing(0)
        self.filter_body = QWidget(self.filter_card)
        filter_shell.addWidget(self.filter_body, 1)
        filter_layout = QVBoxLayout(self.filter_body)
        self.filter_layout = filter_layout
        filter_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        filter_layout.setSpacing(CONTROL_GAP)
        self.compact_filter_bar = QWidget(self.filter_card)
        compact_row = QHBoxLayout(self.compact_filter_bar)
        compact_row.setContentsMargins(0, 0, 0, 0)
        compact_row.setSpacing(CONTROL_GAP)
        self.compact_filter_summary = QLabel('', self.compact_filter_bar)
        self.compact_filter_summary.setStyleSheet(f'color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}px;')
        self.compact_filter_summary.setSizePolicy(QSizePolicy.Policy.Ignored,
                                                  QSizePolicy.Policy.Preferred)
        compact_row.addWidget(self.compact_filter_summary, 1)
        self.filter_toggle_host = QWidget(self.filter_card)
        self.filter_toggle_host.setFixedWidth(40)
        toggle_layout = QVBoxLayout(self.filter_toggle_host)
        toggle_layout.setContentsMargins(0, 8, 8, 0)
        self.filter_toggle = SummaryToggleButton(self.filter_toggle_host)
        self.filter_toggle.set_labels('展开筛选', '收起筛选')
        self.filter_toggle.clicked.connect(
            lambda: self.set_filters_collapsed(not self._filters_collapsed, animate=True))
        toggle_layout.addWidget(self.filter_toggle)
        toggle_layout.addStretch()
        filter_shell.addWidget(self.filter_toggle_host)
        self.expand_filters_button = self.filter_toggle
        self.confirm_filters_button = self.filter_toggle
        filter_layout.addWidget(self.compact_filter_bar)
        self.compact_filter_bar.hide()
        self.toolbar_host = QWidget(self.filter_card)
        self.toolbar_grid = QGridLayout(self.toolbar_host)
        self.toolbar_grid.setSpacing(CONTROL_GAP)
        self.toolbar_grid.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(self.toolbar_host)
        outer.addWidget(self.filter_card)

        self.company_selector = QFrame(self.filter_card)
        self.company_selector.setObjectName('companySelector')
        self.company_selector.setStyleSheet(f'QFrame#companySelector {{ background: {CARD_BG}; '
                                            f'border: 1px solid {BORDER}; border-radius: 6px; }}')
        self.company_selector.setFixedHeight(CONTROL_HEIGHT)
        selector_row = QHBoxLayout(self.company_selector)
        selector_row.setContentsMargins(6, 2, 4, 2)
        selector_row.setSpacing(4)
        self.company_tag_host = QWidget(self.company_selector)
        self.company_tag_layout = QHBoxLayout(self.company_tag_host)
        self.company_tag_layout.setContentsMargins(0, 0, 0, 0)
        self.company_tag_layout.setSpacing(4)
        selector_row.addWidget(self.company_tag_host, 1)
        self.company_button = DropDownPushButton('选择', self.company_selector)
        self.company_button.setFixedWidth(70)
        self.company_button.setFixedHeight(CONTROL_HEIGHT - 4)
        self.company_menu = CheckableMenu(parent=self.company_button)
        self.company_button.setMenu(self.company_menu)
        selector_row.addWidget(self.company_button)
        self.company_tags = {}
        self.range_combo = FluentComboBox(self.filter_card)
        self.range_combo.setFixedHeight(CONTROL_HEIGHT)
        for title, key in (('上一完整周', 'previous_full_week'), ('上一完整日', 'previous_full_day'),
                           ('自定义时间', 'custom')):
            self.range_combo.addItem(title, userData=key)
        self.range_combo.currentIndexChanged.connect(self._range_changed)
        self.grain_combo = FluentComboBox(self.filter_card)
        self.grain_combo.setFixedHeight(CONTROL_HEIGHT)
        for key in ('hour', 'day', 'week', 'month'):
            self.grain_combo.addItem(label(key), userData=key)
        self.grain_combo.setCurrentIndex(1)
        self.grain_combo.currentIndexChanged.connect(self.schedule_query)
        self.analysis_mode_control = FluentSegmentedControl(self.filter_card)
        for title, key, icon in (('默认模式', 'default', FluentIcon.PIE_SINGLE),
                                 ('多公司对比', 'companies', FluentIcon.PEOPLE),
                                 ('同期对比', 'period', FluentIcon.CALENDAR)):
            self.analysis_mode_control.addItem(key, title, icon)
        self.analysis_mode_control.currentKeyChanged.connect(self._mode_changed)
        self.network_mode_control = FluentSegmentedControl(self.filter_card)
        for title, key, icon in (('总体数据', 'overall', FluentIcon.PIE_SINGLE),
                                 ('多公司对比', 'companies', FluentIcon.PEOPLE),
                                 ('单公司同期', 'period', FluentIcon.CALENDAR)):
            self.network_mode_control.addItem(key, title, icon)
        self.network_mode_control.setCurrentKey(self.network_options.mode)
        self.network_mode_control.currentKeyChanged.connect(self._network_mode_changed)
        self.mode_host = QWidget(self.filter_card)
        self.mode_host.setFixedHeight(CONTROL_HEIGHT)
        mode_row = QHBoxLayout(self.mode_host)
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(0)
        mode_row.addWidget(self.analysis_mode_control)
        mode_row.addWidget(self.network_mode_control)
        mode_row.addStretch()
        self.network_mode_control.hide()
        self.compare_combo = FluentComboBox(self.filter_card)
        self.compare_combo.setFixedHeight(CONTROL_HEIGHT)
        for key in ('previous', 'previous_week', 'previous_month', 'custom'):
            self.compare_combo.addItem(label(key), userData=key)
        self.compare_combo.currentIndexChanged.connect(self._compare_changed)
        self.export_button = PrimaryPushButton(label('export'), self.filter_card)
        self.export_button.setIcon(FluentIcon.SAVE)
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_requested.emit)
        self.range_summary = QLabel('未载入存档', self.filter_card)
        self.range_summary.setObjectName('rangeSummary')
        self.range_summary.setStyleSheet(f'color: {TEXT_SECONDARY};')
        self.range_summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._controls = (self.company_selector, self.range_combo, self.grain_combo,
                          self.mode_host, self.compare_combo, self.range_summary, self.export_button)
        self._fields = tuple(self._field(key, control) for key, control in zip(
            ('companies', 'time', 'grain', 'analysis-mode', 'comparison', 'range-summary', 'export'), self._controls))
        self.compare_field = self._fields[4]
        self.compare_field.hide()
        self.filter_detail_host = QWidget(self.filter_card)
        detail_layout = QHBoxLayout(self.filter_detail_host)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(CONTROL_GAP)
        detail_layout.addWidget(self._fields[5], 1)
        self.compare_slot = QWidget(self.filter_detail_host)
        self.compare_slot.setFixedSize(220, CONTROL_HEIGHT)
        slot_layout = QHBoxLayout(self.compare_slot)
        slot_layout.setContentsMargins(0, 0, 0, 0)
        slot_layout.addWidget(self.compare_field)
        self.compare_field.layout().setDirection(QBoxLayout.Direction.LeftToRight)
        self.compare_field.layout().setSpacing(6)
        detail_layout.addWidget(self.compare_slot)
        self.bottom_strip = QWidget(self.filter_card)
        bottom_layout = QHBoxLayout(self.bottom_strip)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(CONTROL_GAP)
        self.export_button.setFixedSize(ACTION_BUTTON_WIDTH, 32)
        bottom_layout.addWidget(self._fields[5], 1)
        bottom_layout.addWidget(self._fields[6])

        self.data_stack = QStackedWidget(self)
        outer.addWidget(self.data_stack, 1)
        self.scroll = StatisticsScrollArea(self.data_stack)
        self.scroll.setObjectName('statsScroll')
        palette = self.scroll.viewport().palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(PAGE_BG))
        self.scroll.viewport().setPalette(palette)
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.company_dashboard = CompanyDashboard(self.scroll)
        self.scroll.setWidget(self.company_dashboard)
        self.data_stack.addWidget(self.scroll)
        self.network_scroll = StatisticsScrollArea(self.data_stack)
        self.network_scroll.setWidgetResizable(True)
        self.network_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.network_host = QWidget(self.network_scroll)
        network_layout = QVBoxLayout(self.network_host)
        network_layout.setContentsMargins(0, 0, 0, 0)
        network_layout.setSpacing(SECTION_GAP)
        self.network_scroll.setWidget(self.network_host)
        self.data_stack.addWidget(self.network_scroll)
        self.city_scroll = StatisticsScrollArea(self.data_stack)
        self.city_scroll.setWidgetResizable(True)
        self.city_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.city_host = QWidget(self.city_scroll)
        city_layout = QVBoxLayout(self.city_host)
        city_layout.setContentsMargins(0, 0, 0, 0)
        self.city_scroll.setWidget(self.city_host)
        self.data_stack.addWidget(self.city_scroll)
        self.boards = [self._board(label(key), icon) for key, icon in zip(
            ('service', 'passenger', 'city'),
            (FluentIcon.BUS, FluentIcon.PIE_SINGLE, FluentIcon.GLOBE))]
        network_layout.addWidget(self.boards[0])
        network_layout.addWidget(self.boards[1])
        self.boards[0].hide()
        self.boards[1].hide()
        self.network_dashboard = NetworkDashboard(self.settings, self.network_host)
        self.network_dashboard.options_changed.connect(self._network_options_changed)
        network_layout.addWidget(self.network_dashboard)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._retry_company_fit)
        self.network_scroll.verticalScrollBar().rangeChanged.connect(self._retry_network_fit)
        city_layout.addWidget(self.boards[2])
        self._tile_grids = {}
        self._build_service()
        self._build_passenger()
        self._build_city()
        self._build_company_controls()
        self.company_dashboard.satisfaction_changed.connect(self._group_satisfaction_changed)
        self.reflow(1100)

    def _board(self, title, icon):
        board = CardWidget(self.data_stack)
        attach_card_elevation(board)
        board.setObjectName('fluentBoard')
        box = QVBoxLayout(board)
        box.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        box.setSpacing(CONTROL_GAP)
        header = QHBoxLayout()
        badge = QFrame(board)
        badge.setFixedSize(28, 28)
        badge.setStyleSheet(f'QFrame {{ background: {ACCENT}; border: 0; border-radius: 7px; }}')
        badge_layout = QHBoxLayout(badge)
        badge_layout.setContentsMargins(6, 6, 6, 6)
        glyph = IconWidget(badge)
        glyph.setIcon(icon.icon(color=QColor(CARD_BG)))
        glyph.setFixedSize(16, 16)
        badge_layout.addWidget(glyph)
        header.addWidget(badge)
        heading = SubtitleLabel(title)
        heading.setObjectName('panelTitle')
        heading.setStyleSheet(f'color: {TEXT_PRIMARY}; {emphasis_css(FONT_SIZE_CHART_TITLE)}')
        apply_emphasis_font(heading, FONT_SIZE_CHART_TITLE)
        header.addWidget(heading)
        header.addStretch()
        box.addLayout(header)
        return board

    def _field(self, key, control):
        host = QWidget(self)
        box = QVBoxLayout(host)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        if key not in ('alerts', 'export', 'thresholds', 'range-summary'):
            heading = CaptionLabel('分析模式' if key == 'analysis-mode' else
                                   '实际范围' if key == 'range-summary' else label(key), host)
            box.addWidget(heading)
        box.addWidget(control)
        return host

    def _tiles(self, board, metrics, wide_metric=None):
        host = QWidget(board)
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(CONTROL_GAP)
        tiles = {}
        row = 0
        for index, key in enumerate(metrics):
            if key == wide_metric:
                continue
            tile = MetricTile(label(key), host)
            grid.addWidget(tile, row // 2, row % 2)
            row += 1
            tiles[key] = tile
        if wide_metric:
            tile = CategoryTile(label(wide_metric), host)
            grid.addWidget(tile, (row + 1) // 2, 0, 1, 2)
            tiles[wide_metric] = tile
        self._tile_grids[board] = (grid, metrics, wide_metric, tiles)
        board.layout().addWidget(host)
        return tiles

    def _build_service(self):
        board = self.boards[0]
        self.service_tiles = self._tiles(board, SERVICE, wide_metric='stopcount')
        self.service_chart_host = QWidget(board)
        self.service_chart_grid = QGridLayout(self.service_chart_host)
        self.service_chart_grid.setContentsMargins(0, 0, 0, 0)
        self.service_chart_grid.setSpacing(CONTROL_GAP)
        self.line_panel = ChartPanel(label('linecount'), parent=self.service_chart_host)
        self.stop_panel = ChartPanel(label('stopcount'), default_mode='bar', parent=self.service_chart_host)
        board.layout().addWidget(self.service_chart_host)

    def _build_passenger(self):
        board = self.boards[1]
        self.passenger_panels = {}
        for key, mode in zip(PASSENGER, ('line', 'pie', 'bar')):
            panel = ChartPanel(label(key), modes=True, default_mode=mode, settings=self.settings,
                settings_key='statistics/view/' + key, parent=board)
            board.layout().addWidget(panel)
            self.passenger_panels[key] = panel
        self.transfer_tile = MetricTile(label('transfer-coefficient'), board)
        board.layout().addWidget(self.transfer_tile)
        self.transfer_panel = ChartPanel(label('transfer-coefficient'), parent=board)
        board.layout().addWidget(self.transfer_panel)

    def _build_city(self):
        self.boards[2].hide()
        self.city_dashboard = CityDashboard(self.settings, self.city_host)
        self.city_host.layout().addWidget(self.city_dashboard)
        self.city_tiles = self.city_dashboard.tiles
        self.city_trends = self.city_dashboard.panels
        self.mode_panel = self.city_trends['city-mode-share']

    def _build_company_controls(self):
        self.company_toolbar = QWidget(self.company_dashboard)
        self.company_toolbar.hide()
        self.satisfaction_combo = FluentComboBox(self.company_toolbar)
        for key in ('satisfaction-speed', 'satisfaction-cost', 'satisfaction-quality'):
            self.satisfaction_combo.addItem(label(key), userData=key)
        saved = str(self.settings.value('statistics/satisfaction', 'satisfaction-speed')) if self.settings else 'satisfaction-speed'
        self.satisfaction_combo.setCurrentIndex(max(0, self.satisfaction_combo.findData(saved)))
        self.satisfaction_combo.currentIndexChanged.connect(self._satisfaction_changed)

    def _group_satisfaction_changed(self, key: str):
        index = self.satisfaction_combo.findData(key)
        if index >= 0:
            self.satisfaction_combo.setCurrentIndex(index)

    def _satisfaction_changed(self, *_):
        if self.settings:
            self.settings.setValue('statistics/satisfaction', self.satisfaction_combo.currentData())
        self._render_company()

    def _city_metric_changed(self, *_):
        pass  # Six city charts are always visible; obsolete single-metric preference is ignored.

    def _update_compact_filter_summary(self):
        if not hasattr(self, 'compact_filter_summary'):
            return
        companies = '、'.join(action.text() for action in self.company_menu.actions()
                             if action.isChecked()) or '未选择公司'
        if self.tab_bar.currentRouteKey() == 'city':
            summary = ' · '.join((self.range_summary.text(), self.grain_combo.currentText()))
            self.compact_filter_summary.setText(summary)
            self.compact_filter_summary.setToolTip(summary)
            return
        is_network = self.tab_bar.currentRouteKey() == 'network'
        mode = (self.network_mode_control.currentKey() if is_network else
                self.analysis_mode_control.currentKey())
        mode_name = ({'overall': '总体数据', 'companies': '多公司对比', 'period': '单公司同期'}
                     if is_network else
                     {'default': '默认模式', 'companies': '多公司对比', 'period': '同期对比'})[mode]
        parts = [companies, self.range_summary.text(), self.grain_combo.currentText(), mode_name]
        if mode == 'period':
            parts.append(self.compare_combo.currentText())
        summary = ' · '.join(part for part in parts if part)
        self.compact_filter_summary.setText(summary)
        self.compact_filter_summary.setToolTip(summary)

    def _filter_padding(self, width: int, collapsed: bool) -> int:
        if self.tab_bar.currentRouteKey() == 'city':
            return 6 if collapsed else 8
        return 6 if collapsed else 10 if width < 1400 else 14 if width < 2200 else CARD_PADDING

    def _finish_filter_transition(self):
        if self._filter_animation is not None:
            self._filter_animation.deleteLater()
            self._filter_animation = None
        self._filter_animating = False
        self.filter_card.setMinimumHeight(0)
        self.filter_card.setMaximumHeight(16777215)
        self.toolbar_host.setVisible(not self._filters_collapsed)
        self.compact_filter_bar.setVisible(self._filters_collapsed)
        for widget in (self.toolbar_host, self.compact_filter_bar):
            widget.setMaximumHeight(16777215)
            widget.setGraphicsEffect(None)
        self.confirm_filters_button.setEnabled(True)
        self.expand_filters_button.setEnabled(True)
        self.reflow(self.width())
        QTimer.singleShot(0, self._reflow_company)
        QTimer.singleShot(0, self._reflow_network)

    def set_filters_collapsed(self, collapsed: bool, *, animate: bool = False):
        collapsed = bool(collapsed)
        if hasattr(self, 'filter_toggle'):
            self.filter_toggle.set_collapsed(collapsed)
        interrupted = self._filter_animation is not None
        if collapsed == self._filters_collapsed and animate:
            return
        if self._filter_animation is not None:
            self._filter_animation.stop()
            self._filter_animation.deleteLater()
            self._filter_animation = None
        self._update_compact_filter_summary()
        if not animate or not self.isVisible() or not motion_policy.animations_enabled():
            self._filters_collapsed = collapsed
            self._finish_filter_transition()
            return
        expanded_height = self.toolbar_host.sizeHint().height()
        compact_height = self.compact_filter_bar.sizeHint().height()
        start_padding = self.filter_layout.contentsMargins().top()
        end_padding = self._filter_padding(self.width(), collapsed)
        start_card_height = self.filter_card.height()
        end_card_height = (compact_height if collapsed else expanded_height) + 2 * end_padding
        widgets = (self.toolbar_host, self.compact_filter_bar)
        natural = (expanded_height, compact_height)
        targets = (0, compact_height) if collapsed else (expanded_height, 0)
        starts, effects, opacities = [], [], []
        for widget, full in zip(widgets, natural):
            start = widget.maximumHeight() if interrupted else (0 if widget.isHidden() else full)
            effect = widget.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(effect)
                effect.setOpacity(0 if start == 0 else 1)
            starts.append(start)
            opacities.append(effect.opacity())
            effects.append(effect)
            widget.setMaximumHeight(start)
            widget.show()
        self.filter_layout.setSpacing(0)
        self.confirm_filters_button.setEnabled(True)
        self.expand_filters_button.setEnabled(True)
        self._filters_collapsed = collapsed
        self._filter_animating = True
        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(167 if collapsed else 250)
        animation.setEasingCurve(QEasingCurve.Type.InCubic if collapsed else
                                 QEasingCurve.Type.OutCubic)

        def advance(value):
            progress = float(value)
            for widget, effect, start, end, opacity in zip(widgets, effects, starts, targets, opacities):
                widget.setMaximumHeight(round(start + (end - start) * progress))
                effect.setOpacity(opacity + ((1 if end else 0) - opacity) * progress)
            padding = round(start_padding + (end_padding - start_padding) * progress)
            self.filter_layout.setContentsMargins(padding, padding, padding, padding)
            # Own the surface height as well as child maxima: layout minimum-size
            # caching must not keep the outer card at its expanded size mid-flight.
            self.filter_card.setFixedHeight(round(start_card_height +
                (end_card_height - start_card_height) * progress))
            QTimer.singleShot(0, self._reflow_company)
            QTimer.singleShot(0, self._reflow_network)
            QTimer.singleShot(0, self._reflow_city)

        animation.valueChanged.connect(advance)
        animation.finished.connect(self._finish_filter_transition)
        self._filter_animation = animation
        animation.start()

    def _tab_changed(self, route):
        for key, icon in self._tab_icons.items():
            self.tab_bar.items[key].setIcon(icon.icon(
                color=QColor(ACCENT if key == route else TEXT_SECONDARY)))
        if hasattr(self, 'data_stack'):
            self.data_stack.setCurrentIndex(('company', 'network', 'city').index(route))
            target = self.data_stack.currentWidget()
            if not hasattr(target, '_route_motion'):
                target._route_motion = SurfaceMotion(target)
            target._route_motion.reveal(float_in=True)
        if hasattr(self, 'network_mode_control'):
            is_network = route == 'network'
            is_city = route == 'city'
            self._fields[0].setVisible(not is_city)
            self._fields[3].setVisible(not is_city)
            self.analysis_mode_control.setVisible(not is_network and not is_city)
            self.network_mode_control.setVisible(is_network)
            self.compare_field.setVisible(not is_city and (self.network_options.mode if is_network else
                                           self.analysis_mode) == 'period')
            self._restore_combo(self.compare_combo, self.network_comparison_preset
                                if is_network else self.comparison_preset)
            self._update_compact_filter_summary()
            self._layout_signature = None
            self.reflow(self.width())
            if self.store is not None:
                if route == 'network':
                    self._refresh_network_model()
                elif route == 'company' and self.snapshot is not None:
                    expected = self._route_comparison('company')
                    if self.snapshot.filters.comparison != expected:
                        self.schedule_query()
                elif route == 'city' and self.city_snapshot is not None:
                    self.city_dashboard.set_snapshot(self.city_snapshot)
                    self.city_dashboard.motion.reveal(float_in=True)
            self._reflow_city()

    def _mode_changed(self, *_):
        self.analysis_mode = self.analysis_mode_control.currentKey()
        self.compare_field.setVisible(self.analysis_mode == 'period')
        self._update_compact_filter_summary()
        self.reflow(self.width())
        self.schedule_query()

    def _network_mode_changed(self, *_):
        mode = self.network_mode_control.currentKey()
        if mode == 'companies' and len(self.selected_companies()) < 2:
            self.network_mode_control.setCurrentKey('overall')
            self.network_dashboard.show_notice('至少选择两家公司才能进行多公司对比')
            return
        self.network_dashboard.show_notice('')
        self.network_options = replace(self.network_options, mode=mode)
        if self.settings:
            self.settings.setValue('network/mode', mode)
        self.compare_field.setVisible(mode == 'period' and self.tab_bar.currentRouteKey() == 'network')
        self._update_compact_filter_summary()
        self._layout_signature = None
        self.reflow(self.width())
        self._refresh_network_model()

    def _network_options_changed(self, options):
        self.network_options = options
        self._refresh_network_model()

    def _refresh_network_model(self):
        if self.store is None:
            return
        if self.snapshot is None:
            self.schedule_query()
            return
        if self.snapshot.filters.comparison != self._route_comparison('network'):
            self.schedule_query()
            return
        self.network_snapshot = None
        if self.tab_bar.currentRouteKey() == 'network':
            self.export_button.setEnabled(False)
        self.network_model_token += 1
        for worker in self.network_workers:
            worker.requestInterruption()
        worker = NetworkModelTask(self.network_model_token, self.snapshot,
                                  self._effective_network_options(), self._names(), self)
        worker.ready.connect(self._receive_network_model)
        worker.failed.connect(self._failed_network_model)
        worker.finished.connect(lambda w=worker: self._network_worker_finished(w))
        self.network_workers.append(worker)
        worker.start()

    def _effective_network_options(self):
        label_map = {'previous': '环比', 'previous_week': '上周同期',
                     'previous_month': '上月同期', 'custom': '自定义对比'}
        return replace(self.network_options,
                       comparison_label=label_map[self.network_comparison_preset])

    def _route_comparison(self, route):
        mode = self.network_options.mode if route == 'network' else self.analysis_mode
        if mode != 'period' or self._range_window is None:
            return None
        return resolve_comparison(
            *self._range_window,
            self.network_comparison_preset if route == 'network' else self.comparison_preset,
            self._network_custom_comparison if route == 'network' else self._custom_comparison)

    def _receive_network_model(self, token, source, network):
        if token != self.network_model_token or source is not self.snapshot or self._closing:
            return
        self.network_snapshot = network
        self.network_dashboard.set_snapshot(network)
        self._reflow_network()
        if self.tab_bar.currentRouteKey() == 'network':
            self.export_button.setEnabled(True)

    def _failed_network_model(self, token, _message):
        if token == self.network_model_token:
            self.network_snapshot = None
            self.network_dashboard.clear()

    def _network_worker_finished(self, worker):
        if worker in self.network_workers:
            self.network_workers.remove(worker)
        worker.deleteLater()

    def _range_changed(self, *_):
        choice = self.range_combo.currentData()
        if choice == 'custom':
            if self.simulation_time is None:
                self._restore_combo(self.range_combo, self.range_preset)
                return
            start, end = self._range_window or preset_window(self.simulation_time, 'previous_full_week')
            timed = any(value.hour or value.minute or value.second for value in (start, end))
            picker = RangePicker(start, end if timed else end - timedelta(days=1), parent=self)
            if picker.exec() != QDialog.DialogCode.Accepted:
                self._restore_combo(self.range_combo, self.range_preset)
                return
            self._custom_window = picker.selected_range()
        self.range_preset = choice
        self._refresh_range_summary()
        self.schedule_query()

    def _compare_changed(self, *_):
        is_network = self.tab_bar.currentRouteKey() == 'network'
        choice = self.compare_combo.currentData()
        if choice == 'custom':
            if self._range_window is None:
                self._restore_combo(self.compare_combo, self.network_comparison_preset
                                    if is_network else self.comparison_preset)
                return
            start, end = self._range_window
            previous = (self._network_custom_comparison if is_network else self._custom_comparison) or (start - (end - start), start)
            timed = any(value.hour or value.minute or value.second for value in previous)
            picker = RangePicker(previous[0], previous[1] if timed else previous[1] - timedelta(days=1),
                                 title='自定义对比周期', parent=self)
            if picker.exec() != QDialog.DialogCode.Accepted:
                self._restore_combo(self.compare_combo, self.network_comparison_preset
                                    if is_network else self.comparison_preset)
                return
            if is_network:
                self._network_custom_comparison = picker.selected_range()
            else:
                self._custom_comparison = picker.selected_range()
        if is_network:
            self.network_comparison_preset = choice
            if self.settings:
                self.settings.setValue('network/comparison', choice)
        else:
            self.comparison_preset = choice
        self.schedule_query()

    def _restore_combo(self, combo, value):
        combo.blockSignals(True)
        combo.setCurrentIndex(combo.findData(value))
        combo.blockSignals(False)

    def _refresh_range_summary(self):
        if self.simulation_time is None:
            self.range_summary.setText('未载入存档')
            self._update_compact_filter_summary()
            return
        interval = (self._custom_window if self.range_preset == 'custom' else
                    preset_window(self.simulation_time, self.range_preset))
        self._range_window = interval
        self.range_summary.setText(f'{interval[0]:%Y-%m-%d %H:%M} 至 {interval[1]:%Y-%m-%d %H:%M}')
        self.range_summary.setToolTip('结束时间不计入统计')
        self._update_compact_filter_summary()

    def selected_companies(self):
        return tuple(str(a.data()) for a in self.company_menu.actions() if a.isChecked())

    def _refresh_company_tags(self, *_):
        while self.company_tag_layout.count():
            item = self.company_tag_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.company_tags = {}
        checked = [action for action in self.company_menu.actions() if action.isChecked()]
        for action in checked[:2]:
            company_id = str(action.data())
            name = action.text()
            tag = CompanyTag(name, lambda _=False, item=action: item.setChecked(False),
                             self.company_tag_host)
            self.company_tag_layout.addWidget(tag)
            self.company_tags[company_id] = tag
        if len(checked) > 2:
            more = QLabel(f'+{len(checked) - 2}', self.company_tag_host)
            more.setToolTip('、'.join(action.text() for action in checked[2:]))
            self.company_tag_layout.addWidget(more)
        self.company_tag_layout.addStretch()
        if hasattr(self, 'network_mode_control'):
            enough = len(checked) >= 2
            if not enough and self.network_mode_control.currentKey() == 'companies':
                self.network_mode_control.setCurrentKey('overall')
                self.network_dashboard.show_notice('至少选择两家公司才能进行多公司对比')
            self.network_mode_control.setItemEnabled('companies', enough)
        self._update_compact_filter_summary()

    def clear_session(self):
        self.token += 1
        self.query_timer.stop()
        for worker in self.workers:
            worker.requestInterruption()
        self.network_model_token += 1
        for worker in self.network_workers:
            worker.requestInterruption()
        self.store, self.snapshot, self.simulation_time = None, None, None
        self.network_snapshot = None
        self.city_snapshot = None
        self.companies, self.session_key, self._short_ids = [], '', {}
        self._company_palette = {}
        self._range_window = None
        self.network_dashboard.set_company_palette({})
        self._custom_window = None
        self._custom_comparison = None
        self._network_custom_comparison = None
        if self.network_comparison_preset == 'custom':
            self.network_comparison_preset = 'previous'
        self.range_preset = 'previous_full_week'
        self.comparison_preset = 'previous'
        self._restore_combo(self.range_combo, self.range_preset)
        self._restore_combo(self.compare_combo, self.network_comparison_preset
                            if self.tab_bar.currentRouteKey() == 'network' else self.comparison_preset)
        self._refresh_range_summary()
        self.company_menu.clear()
        self._refresh_company_tags()
        self._clear_views()
        self.snapshot_changed.emit(None)

    def _clear_views(self):
        self.export_button.setEnabled(False)
        self.company_dashboard.clear()
        self.network_dashboard.clear()
        self.city_dashboard.clear()
        for tile in (*self.service_tiles.values(), self.transfer_tile):
            tile.set_rows([])
        for panel in (self.line_panel, self.stop_panel, *self.passenger_panels.values(), self.transfer_panel):
            panel.clear()

    def _invalidate_snapshot(self):
        self.token += 1
        self.query_timer.stop()
        for worker in self.workers:
            worker.requestInterruption()
        self.network_model_token += 1
        for worker in self.network_workers:
            worker.requestInterruption()
        self.snapshot = None
        self.network_snapshot = None
        self.city_snapshot = None
        self._clear_views()
        self.snapshot_changed.emit(None)

    def set_session(self, data):
        self.clear_session()
        self.companies = list(data.get('companies', []))
        self._short_ids = {str(c['公司标识']): str(index + 1)
                           for index, c in enumerate(sorted(self.companies,
                                                             key=lambda item: str(item['公司标识'])))}
        self._company_palette = {company_id: DATA_COMPANY_COLORS[index % len(DATA_COMPANY_COLORS)]
                                 for index, company_id in enumerate(sorted(self._short_ids))}
        self.network_dashboard.set_company_palette(self._company_palette)
        self.simulation_time = parse_time(data['simulation_time'])
        self.store = HistoryStore(data.get('history', []), self.simulation_time)
        self.session_key = str(data.get('save_key', ''))
        names = [str(c.get('公司名称', '')) for c in self.companies]
        for company in self.companies:
            key = str(company['公司标识'])
            name = str(company.get('公司名称', key))
            action = QAction(f'{name} [{key}]' if names.count(name) > 1 else name, self.company_menu)
            action.setData(key)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(self._refresh_company_tags)
            action.toggled.connect(self.schedule_query)
            self.company_menu.addAction(action)
        self._refresh_company_tags()
        self._refresh_range_summary()
        self.schedule_query()

    def schedule_query(self, *_):
        if self.store is not None and not self._closing:
            self._invalidate_snapshot()
            self.query_timer.start(80)

    def _submit_query(self):
        if self.store is None:
            return
        self._invalidate_snapshot()
        start, end = self._range_window or preset_window(self.simulation_time, self.range_preset)
        if start >= end:
            self.snapshot = None
            self.export_button.setEnabled(False)
            return
        comparison = None
        is_network = self.tab_bar.currentRouteKey() == 'network'
        period_mode = (self.network_options.mode == 'period' if is_network else
                       self.tab_bar.currentRouteKey() != 'city' and self.analysis_mode == 'period')
        if period_mode:
            try:
                comparison = resolve_comparison(
                    start, end,
                    self.network_comparison_preset if is_network else self.comparison_preset,
                    self._network_custom_comparison if is_network else self._custom_comparison)
            except ValueError:
                return
        filters = FilterState(companies=self.selected_companies(), start=start, end=end,
            grain=self.grain_combo.currentData(), comparison=comparison)
        worker = DashboardTask(self.token, self.store, filters, self.thresholds, self,
                               self._effective_network_options(), self._names())
        worker.ready.connect(self._receive)
        worker.failed.connect(self._failed)
        worker.finished.connect(lambda w=worker: self._worker_finished(w))
        self.workers.append(worker)
        worker.start()

    def _worker_finished(self, worker):
        if worker in self.workers:
            self.workers.remove(worker)
        worker.deleteLater()

    def _receive(self, token, snapshot):
        if token != self.token or self.store is None or self._closing:
            return
        network = None
        if isinstance(snapshot, tuple):
            if len(snapshot) == 3:
                snapshot, network, self.city_snapshot = snapshot
            else:
                snapshot, network = snapshot
        self.snapshot = snapshot
        self.network_snapshot = network
        self._render_snapshot()
        self.export_button.setEnabled(True)
        self.snapshot_changed.emit(snapshot)

    def _failed(self, token, _message):
        if token == self.token:
            self.snapshot = None
            self.network_snapshot = None
            self.network_dashboard.clear()
            self.export_button.setEnabled(False)
            self.snapshot_changed.emit(None)
            self.query_failed.emit(_message)

    def _names(self):
        names = [str(c.get('公司名称', '')) for c in self.companies]
        return {str(c['公司标识']): (f"{c.get('公司名称', '')} [{c['公司标识']}]"
                if names.count(str(c.get('公司名称', ''))) > 1 else str(c.get('公司名称', '')))
                for c in self.companies}

    def _tile_value(self, tile, result, names, coefficient=False):
        if result is None:
            tile.set_rows([])
            return
        values = []
        series = dict(result.series)
        selected = result.query.companies if result.metric.scope == 'company' else ()
        if selected:
            present = {owner for owner, _ in series}
            for owner in selected:
                if owner not in present:
                    series[(owner, '总计')] = []
        order = {owner: index for index, owner in enumerate(selected)}
        for (owner, group), buckets in sorted(series.items(),
                                              key=lambda item: (order.get(item[0][0], len(order)), item[0][1])):
            value = summarize_buckets(buckets, result.metric)
            name = names.get(owner, owner)
            if owner and len(selected) > 1:
                name = '● ' + self._short_ids.get(owner, owner)
            if group not in ('', '__total__', '总计'):
                name = (name + ' · ' if name else '') + group_label(group)
            unit = f' {result.metric.unit}' if result.metric.unit else ''
            formatted = label('missing') if value is None else f'{display(value, coefficient)}{unit}'
            color = self._company_palette.get(owner, TEXT_SECONDARY)
            values.append((name, formatted, color))
        tile.set_rows(values)

    def _render_snapshot(self):
        if self.snapshot is None:
            return
        results, breakdowns, names = self.snapshot.results, self.snapshot.breakdowns, self._names()
        self._render_company()
        if self.network_snapshot is not None and self.tab_bar.currentRouteKey() == 'network':
            self.network_dashboard.set_snapshot(self.network_snapshot)
            self._reflow_network()
        for key, tile in self.service_tiles.items():
            if key == 'stopcount':
                self._stopcount_value(tile, breakdowns.get(key))
            else:
                self._tile_value(tile, results.get(key), names)
        if self.city_snapshot is not None:
            self.city_dashboard.set_snapshot(self.city_snapshot)
            self._reflow_city()
        self._tile_value(self.transfer_tile, results.get('transfer-coefficient'), names, coefficient=True)
        self.line_panel.set_result(results.get('linecount'), names)
        self.stop_panel.set_result(breakdowns.get('stopcount'), names)
        for key, panel in self.passenger_panels.items():
            panel.set_result(breakdowns.get(key), names)
        self.transfer_panel.set_result(results.get('transfer-coefficient'), names)

    def _render_company(self):
        if self.snapshot is None:
            return
        self.company_dashboard.render(
            self.snapshot, self.selected_companies(), self._names(), self._company_palette,
            self.analysis_mode, self.satisfaction_combo.currentData(), self.metric_slots)
        self._reflow_company()

    def _stopcount_value(self, tile, result):
        groups = defaultdict(list)
        if result is not None:
            categories = dict.fromkeys(group for _, group in result.series)
            owners = result.query.companies
            for group in categories:
                for owner in owners:
                    value = summarize_buckets(result.series.get((owner, group), []), result.metric)
                    short = '● ' + self._short_ids.get(owner, owner) if owner else ''
                    color = self._company_palette.get(owner, TEXT_SECONDARY)
                    formatted = label('missing') if value is None else f'{display(value)} {result.metric.unit}'
                    groups[group].append((short, formatted, color))
        tile.set_categories(groups)

    def set_thresholds(self, thresholds):
        self.thresholds = tuple(thresholds)
        if self.settings:
            for key, value in zip(('percentage_points', 'relative_percent', 'passenger_absolute'), self.thresholds):
                self.settings.setValue('statistics/' + key, value)
        self.schedule_query()


    def _reflow_company(self):
        self._reflow_surface('scroll', 'company_dashboard')

    def _reflow_surface(self, scroll_name, dashboard_name):
        if not isValid(self) or self._closing:
            return
        scroll = getattr(self, scroll_name, None)
        dashboard = getattr(self, dashboard_name, None)
        if (scroll is None or dashboard is None or
                not isValid(scroll) or not isValid(dashboard)):
            return
        viewport = scroll.viewport()
        if viewport is not None and isValid(viewport):
            dashboard.reflow(viewport.width(), viewport.height())

    def _retry_company_fit(self, _minimum, maximum):
        if maximum > 0 and self.analysis_mode == 'default':
            QTimer.singleShot(0, self._reflow_company)

    def _reflow_network(self):
        self._reflow_surface('network_scroll', 'network_dashboard')

    def _reflow_city(self):
        self._reflow_surface('city_scroll', 'city_dashboard')

    def _retry_network_fit(self, _minimum, maximum):
        if maximum > 0 and self.network_options.mode == 'overall':
            QTimer.singleShot(0, self._reflow_network)

    def reflow(self, width):
        is_city = self.tab_bar.currentRouteKey() == 'city'
        if not self._filter_animating:
            filter_padding = self._filter_padding(width, self._filters_collapsed)
            self.filter_layout.setContentsMargins(
                filter_padding, filter_padding, filter_padding, filter_padding)
            self.filter_layout.setSpacing(6 if width < 1400 else CONTROL_GAP)
        columns = 4 if width >= 1100 else 2
        period = not self.compare_field.isHidden()
        signature = (columns, period, width >= 900, is_city)
        if signature == self._layout_signature:
            self._reflow_company()
            self._reflow_network()
            self._reflow_city()
            return
        self._layout_signature = signature
        # The application shell owns the page gutter.
        self.layout().setContentsMargins(0, 0, 0, 0)
        for field in self._fields[:5]:
            self.toolbar_grid.removeWidget(field)
        for widget in (self.bottom_strip, self.filter_detail_host, self._fields[5]):
            self.toolbar_grid.removeWidget(widget)
        self.bottom_strip.layout().removeWidget(self.filter_detail_host)
        self.bottom_strip.layout().removeWidget(self._fields[5])
        self.filter_detail_host.layout().removeWidget(self._fields[5])
        self.bottom_strip.hide()
        self.toolbar_grid.setHorizontalSpacing(12)
        self.toolbar_grid.setVerticalSpacing(8)
        for field in self._fields[1:3]:
            field.layout().setDirection(QBoxLayout.Direction.TopToBottom)
            field.layout().setSpacing(4)
            heading = field.layout().itemAt(0).widget()
            heading.setMinimumWidth(0)
            heading.setMaximumWidth(16777215)
        # One row of filters in a fixed order; hidden fields leave no gap.
        primary = [field for field in self._fields[:4] if not field.isHidden()]
        stretches = {self._fields[0]: 4, self._fields[1]: 3, self._fields[2]: 2, self._fields[3]: 0}
        for index in range(4):
            self.toolbar_grid.setColumnStretch(index, 0)
            self.toolbar_grid.setColumnMinimumWidth(index, 0)
        limits = {self._fields[0]: 560, self._fields[1]: 360, self._fields[2]: 200, self._fields[3]: 16777215}
        for index in range(5):
            self.toolbar_grid.setColumnStretch(index, 0)
        for index, field in enumerate(primary):
            field.setMaximumWidth(limits[field] if columns == 4 else 16777215)
            self.toolbar_grid.addWidget(field, index // columns, index % columns)
            self.toolbar_grid.setColumnStretch(index % columns, max(
                self.toolbar_grid.columnStretch(index % columns), stretches[field] if columns == 4 else 1))
        if columns == 4:
            # Spare width collects at the right instead of inflating controls.
            self.toolbar_grid.setColumnStretch(len(primary), 1)
        rows = (len(primary) + columns - 1) // columns
        self.filter_detail_host.layout().insertWidget(0, self._fields[5], 1)
        self.toolbar_grid.addWidget(self.filter_detail_host, rows, 0, 1, max(columns, len(primary) + 1))
        self.filter_detail_host.show()
        for board, (grid, metrics, wide_metric, tiles) in self._tile_grids.items():
            for tile in tiles.values():
                grid.removeWidget(tile)
            board_columns = 2 if board is self.boards[0] else 3 if width >= 900 else 2
            regular = [key for key in metrics if key != wide_metric]
            for index, key in enumerate(regular):
                grid.addWidget(tiles[key], index // board_columns, index % board_columns)
            if wide_metric:
                grid.addWidget(tiles[wide_metric], (len(regular) + board_columns - 1) // board_columns,
                               0, 1, board_columns)
        self.service_chart_grid.removeWidget(self.line_panel)
        self.service_chart_grid.removeWidget(self.stop_panel)
        if width >= 900:
            self.service_chart_grid.addWidget(self.line_panel, 0, 0)
            self.service_chart_grid.addWidget(self.stop_panel, 0, 1)
        else:
            self.service_chart_grid.addWidget(self.line_panel, 0, 0)
            self.service_chart_grid.addWidget(self.stop_panel, 1, 0)
        self._reflow_company()
        self._reflow_network()
        self._reflow_city()

    def export_target(self) -> QWidget:
        """The complete content for the currently selected statistics tab."""
        return {'company': self.company_dashboard, 'network': self.network_dashboard.export_target(),
                'city': self.city_host}[self.tab_bar.currentRouteKey()]

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow(self.width())
        QTimer.singleShot(0, self._reflow_company)
        QTimer.singleShot(0, self._reflow_network)
        QTimer.singleShot(0, self._reflow_city)

    def stop_workers(self):
        self._closing = True
        if self._filter_animation is not None:
            self._filter_animation.stop()
            self._filter_animation.deleteLater()
            self._filter_animation = None
        self._filter_animating = False
        self.query_timer.stop()
        self.token += 1
        for worker in list(self.workers):
            worker.requestInterruption()
            worker.wait()
        self.network_model_token += 1
        for worker in list(self.network_workers):
            worker.requestInterruption()
            worker.wait()

    def closeEvent(self, event):
        self.stop_workers()
        super().closeEvent(event)
