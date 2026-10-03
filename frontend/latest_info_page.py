"""Fluent latest-information board over a precomputed, save-local snapshot."""
from __future__ import annotations

from pathlib import Path, PureWindowsPath
import sys

from PySide6.QtCore import Qt, QRect, QRectF, Signal
from PySide6.QtGui import QAction, QColor, QPainter, QPainterPath
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QBoxLayout, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
                              QSizePolicy, QVBoxLayout, QWidget)
from qfluentwidgets import (ComboBox, DropDownPushButton, FluentIcon, IconWidget,
                           PrimaryPushButton, PushButton, RoundMenu)
from display_rules import display_mode
from latest_info_model import InfoValue, LatestInfoSnapshot
from map_name_source import resolve_session_map_name
from latest_info_charts import (DepartureStructure, PassengerRanking, font,
                                label, numeric, short_line_name, shown)
from statistics_model import parse_time
from stats_charts import ChartPanel
from stats_controls import StatisticsScrollArea
from stats_elevation import attach_card_elevation
from stats_motion import SurfaceMotion
import stats_tokens as tokens


METRICS = (
    ('line-count', '线路总数', '条'), ('fleet', '车辆总数', '辆'),
    ('drive-minutes', '行车总时间', '分钟'), ('turnover', '车辆周转率', '班/辆/天'),
    ('weekly-income', '每周收入', ''), ('weekly-expense', '每周支出', ''),
    ('profit', '净利润', ''), ('interval', '平均间隔', '分钟'),
    ('speed', '平均核定速度', 'km/h'), ('passengers-per-run', '平均单班人次', '人次'),
    ('passengers-per-km', '平均车公里人次', '人次/车公里'),
    ('public-transport-share', '公共交通分担率', '%'),
    ('transfer-coefficient', '平均换乘系数', ''),
)
CORE = ('line-count', 'fleet', 'weekly-income', 'profit')
BUSINESS_MODULES = (
    ('network', '网络规模', ('line-count', 'fleet'), 188),
    ('finance', '经营收支', ('weekly-income', 'weekly-expense', 'profit'), 248),
    ('operations', '运行效率', ('drive-minutes', 'turnover', 'interval', 'speed'), 236),
    ('travel', '乘客出行', ('passengers-per-run', 'passengers-per-km', 'public-transport-share', 'transfer-coefficient'), 224),
)
MODULE_ICONS = {'network': FluentIcon.BUS, 'finance': FluentIcon.MARKET,
                'operations': FluentIcon.HISTORY, 'travel': FluentIcon.PEOPLE}
HIGHLIGHTS = ('当日最大客流线路', '当日最小客流线路', '当日最多班次线路', '当日最少班次线路')
EXTREME_ROLE_COLORS = ('#D13438', '#0F9D58')
EXTREME_ROLE_LABELS = ('客流最多', '客流最少', '班次最多', '班次最少')


class TodayTrendPanel(ChartPanel):
    """Same chart/axis/hit-testing; the Hero already carries today's full date."""
    def _time_label_text(self, date, dates):
        if self.result.query.grain == 'hour' and dates[0].date() == dates[-1].date():
            return date.strftime('%H:%M')
        return super()._time_label_text(date, dates)

    def set_result(self, result, companies=None):
        self._raw_company_names = dict(companies or {})
        names = list(self._raw_company_names.values())
        duplicate_ids = {key for key, name in self._raw_company_names.items() if names.count(name) > 1}
        self._short_company_names = dict(self._raw_company_names)
        full_names = dict(self._raw_company_names)
        for key in duplicate_ids:
            # A suffix taken from the real ID, lengthened until it is unique.
            length = min(4, len(key))
            while length < len(key) and any(other != key and other[-length:] == key[-length:] for other in duplicate_ids):
                length += 1
            self._short_company_names[key] = f'{full_names[key]} [{key[-length:]}]'
            full_names[key] = f'{full_names[key]} [{key}]'
        super().set_result(result, full_names)

    def _legend_text(self, key):
        short = getattr(self, '_short_company_names', {})
        if self._combined_totals and key in short:
            return short[key]
        return super()._legend_text(key)

    def _legend_tooltip(self, key):
        raw = getattr(self, '_raw_company_names', {})
        if self._combined_totals and key in raw:
            return f'{raw[key]}\n公司标识：{key}'
        return ''

    def _create_clone(self, dialog):
        clone = TodayTrendPanel(self.title_label.text(), default_mode='line', allowed_modes=('line',), parent=dialog)
        clone._hidden_groups = set(self._hidden_groups)
        clone.set_comparison_label(self._comparison_label)
        clone.set_company_palette({key: value.name() for key, value in self._company_palette.items()})
        clone.set_category_palette(self._category_palette)
        clone.set_result(self.result, self._raw_company_names)
        clone.set_axis_spec(self._axis_override)
        return clone


def card(name, radius=tokens.RADIUS_KPI, *, elevated=True):
    widget = QFrame()
    widget.setObjectName(name)
    widget.setMinimumWidth(0)
    widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    widget.setStyleSheet(f'QFrame#{name} {{background:{tokens.CARD_BG};border:1px solid '
                        f'{tokens.BORDER};border-radius:{radius}px;}}')
    if elevated:
        attach_card_elevation(widget, radius=radius)
    return widget


class CitySummaryCard(QFrame):
    """Light-blue summary by default; WinUI-blue is retained for code callers."""
    PALETTES = {
        'light': ('#F1F7FF', '#E3EFFF', '#C9DCF3', '#18314F', '#465D79', .065),
        'dark': (tokens.ACCENT, '#005FAF', '#2D86D2', '#FFFFFF', '#EEF6FF', .08),
    }

    def __init__(self):
        super().__init__()
        self.setObjectName('cityCard')
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._variant = 'light'
        self._decoration = QSvgRenderer(self)
        attach_card_elevation(self, radius=tokens.RADIUS_CARD)
        self.set_visual_variant('light')

    def set_visual_variant(self, variant):
        start, end, border, primary, secondary, _ = self.PALETTES[variant]
        self._variant = variant
        surface = start if start == end else (
            f'qlineargradient(x1:0,y1:0,x2:1,y2:0.2,stop:0 {start},stop:1 {end})')
        self.setStyleSheet(f'QFrame#cityCard {{background:{surface};border:1px solid '
                          f'{border};border-radius:{tokens.RADIUS_CARD}px;}}')
        for widget in self.findChildren(QLabel):
            muted = widget.objectName() in (
                'cityPopulationTitle', 'citySimulationDate', 'cityPopulationUnit')
            widget.setStyleSheet(f'color:{secondary if muted else primary};background:transparent;')
        if not self._decoration.isValid():
            base = (Path(sys._MEIPASS) / 'frontend' if getattr(sys, 'frozen', False)
                    else Path(__file__).resolve().parent)
            resource = base / 'static' / 'cimstats' / 'home-decoration.svg'
            if resource.is_file():
                self._decoration.load(str(resource))
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        opacity = self.PALETTES[self._variant][-1]
        if not opacity or not self._decoration.isValid():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1),
                            tokens.RADIUS_CARD - 1, tokens.RADIUS_CARD - 1)
        # Reserve the actual painted text, rather than each stretched column.
        for widget in self.findChildren(QLabel):
            if not widget.isVisible():
                continue
            metrics = widget.fontMetrics()
            elide = (Qt.TextElideMode.ElideMiddle if widget.property('elideMode') == 'middle'
                     else Qt.TextElideMode.ElideRight)
            text = metrics.elidedText(widget.text(), elide, widget.contentsRect().width())
            rect = metrics.boundingRect(widget.contentsRect(), widget.alignment().value, text)
            rect.translate(widget.mapTo(self, widget.rect().topLeft()))
            clear = QPainterPath()
            clear.addRect(QRectF(rect).adjusted(-6, -6, 6, 6))
            clip = clip.subtracted(clear)
        painter.setClipPath(clip)
        painter.setOpacity(opacity)
        extent = min(128., max(84., self.height() * 1.65), self.width() * .22)
        self._decoration.render(painter, QRectF(self.width() - extent + 8,
                                               (self.height() - extent) / 2, extent, extent))
        painter.end()


class MetricCard(QFrame):
    def __init__(self, key, title, unit):
        super().__init__()
        self.key, self.default_unit = key, unit
        self.setObjectName(f'metric-{key}')
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setStyleSheet(f'QFrame#metric-{key} {{background:transparent;border:0;}}')
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        heading = QHBoxLayout()
        heading.setSpacing(5)
        self.title = label(title, size=12, parent=self)
        self.title.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};background:transparent;')
        self.title.setFixedHeight(self.title.fontMetrics().height())
        heading.addWidget(self.title, 1)
        box.addLayout(heading)
        values = QHBoxLayout()
        values.setSpacing(4)
        size = 28 if key in ('line-count', 'fleet') else 24 if key in CORE else 20
        self.value = label('—', f'metric-{key}-value', size, key in CORE, self)
        self.value.setFixedHeight(self.value.fontMetrics().height())
        self.unit = label(unit, f'metric-{key}-unit', parent=self)
        self.unit.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};background:transparent;')
        self.unit.setFixedHeight(self.unit.fontMetrics().height())
        self.unit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.value.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        values.addWidget(self.value, 0, Qt.AlignmentFlag.AlignBaseline)
        values.addWidget(self.unit, 0, Qt.AlignmentFlag.AlignBaseline)
        values.addStretch()
        box.addLayout(values)
        self.setFixedHeight(self.title.height() + self.value.height())
        self.set_value(None)

    def set_value(self, value: InfoValue | None):
        self.value.setText(shown(value.value) if value else '—')
        self.unit.setText(value.unit if value else self.default_unit)
        for widget in (self.value, self.unit):
            widget.setFixedWidth(widget.fontMetrics().horizontalAdvance(widget.text()) + 1)
        parts = (value.title, value.scope, value.reason) if value else (self.title.text(), '未载入数据')
        self.setToolTip('\n'.join(part for part in parts if part))

    def content_width(self):
        return max(self.title.fontMetrics().horizontalAdvance(self.title.text()),
                   self.value.width() + self.unit.width() + 4)


class HighlightCard(QFrame):
    line_requested = Signal(str)

    def __init__(self, index):
        super().__init__()
        self.setObjectName(f'highlight-{index}')
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        color = EXTREME_ROLE_COLORS[index % 2]
        self.setStyleSheet(f'QFrame#highlight-{index} {{background:{tokens.CARD_BG};border:1px solid '
                          f'{tokens.BORDER};border-radius:{tokens.RADIUS_KPI}px;}} '
                          f'QFrame#highlight-{index}:hover {{border-color:{color};}} '
                          f'QFrame#highlight-{index}:focus {{border-color:{tokens.FOCUS_RING};}}')
        self.marker = QFrame(self)
        self.marker.setObjectName(f'highlight-marker-{index}')
        self.marker.setProperty('extremeColor', color)
        self.marker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.marker.setStyleSheet(f'background:{color};border:0;border-radius:1px;')
        self._line_key = None
        self.role_title = HIGHLIGHTS[index]
        box = QVBoxLayout(self)
        box.setContentsMargins(tokens.SPACE_MD, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM)
        box.setSpacing(tokens.SPACE_XS)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        self.role_label = label(EXTREME_ROLE_LABELS[index], size=12, parent=self)
        self.role_label.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};background:transparent;')
        self.role_label.setFixedWidth(self.role_label.fontMetrics().horizontalAdvance(self.role_label.text()) + 1)
        self.name = QLabel('—', self)
        self.name.setFont(font(15, True))
        self.name.setWordWrap(True)
        self.name.setMinimumWidth(0)
        self.name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.name.setStyleSheet(f'color:{tokens.TEXT_PRIMARY};background:transparent;')
        header.addWidget(self.role_label)
        header.addWidget(self.name, 1)
        box.addLayout(header)
        self.values, self.units, self.field_labels = [], [], []
        primary_index = 0 if index < 2 else 1
        for i, title in enumerate(('客流', '班次', '单班人次', '车公里人次')):
            emphasized = i == primary_index
            field = self.role_label if emphasized else label(title, size=13, parent=self)
            if not emphasized:
                field.setFixedWidth(field.fontMetrics().horizontalAdvance(title) + 1)
            self.field_labels.append(field)
            number = label('—', size=20 if emphasized else 13, bold=emphasized, parent=self)
            number.setFixedHeight(number.fontMetrics().height())
            self.values.append(number)
            unit = label(('人次', '班', '人次/班', '人次/车公里')[i], size=12, parent=self)
            unit.setFixedWidth(unit.fontMetrics().horizontalAdvance(unit.text()) + 1)
            unit.setFixedHeight(unit.fontMetrics().height())
            self.units.append(unit)
        self.primary_value = self.values[primary_index]
        primary_row = QHBoxLayout()
        primary_row.setContentsMargins(0, 0, 0, 0)
        primary_row.setSpacing(tokens.SPACE_XS)
        primary_row.addWidget(self.primary_value, 0, Qt.AlignmentFlag.AlignBaseline)
        primary_row.addWidget(self.units[primary_index], 0, Qt.AlignmentFlag.AlignBaseline)
        primary_row.addStretch()
        box.addLayout(primary_row)
        self.auxiliary_indices = tuple(i for i in range(4) if i != primary_index)
        self.auxiliary_grid = grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(tokens.SPACE_XS)
        grid.setVerticalSpacing(tokens.SPACE_XS)
        self.auxiliary_rows = []
        for row, i in enumerate(self.auxiliary_indices):
            field_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
            field_row.setContentsMargins(0, 0, 0, 0)
            field_row.setSpacing(tokens.SPACE_XS)
            field_row.addWidget(self.field_labels[i], 0, Qt.AlignmentFlag.AlignLeft)
            field_row.addStretch()
            quantity = QHBoxLayout()
            quantity.setContentsMargins(0, 0, 0, 0)
            quantity.setSpacing(tokens.SPACE_XS)
            quantity.addStretch()
            quantity.addWidget(self.values[i], 0, Qt.AlignmentFlag.AlignBaseline)
            quantity.addWidget(self.units[i], 0, Qt.AlignmentFlag.AlignBaseline)
            field_row.addLayout(quantity)
            grid.addLayout(field_row, row, 0)
            self.auxiliary_rows.append(field_row)
        box.addLayout(grid)
        self.prepare_header(224)
        self.set_line(None)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_line(self, line):
        self._line_key = line.key if line else None
        self.name.setText(f'{line.mode} {short_line_name(line.name)}' if line else '—')
        self.name.setToolTip(self.name.text())
        self.name.setAccessibleName(self.name.text())
        values = (line.passengers, line.departures, line.passengers_per_departure,
                  line.passengers_per_vehicle_km) if line else (None,) * 4
        for widget, value in zip(self.values, values):
            widget.setText(shown(value))
            widget.setFixedWidth(widget.fontMetrics().horizontalAdvance(widget.text()) + 1)
        self.setToolTip(f'{self.role_title}\n{line.mode} {short_line_name(line.name)}\n公司：{line.company_id}' if line else '当前范围没有可用线路')
        self.setAccessibleName(self.toolTip())
        self.setCursor(Qt.CursorShape.PointingHandCursor if line else Qt.CursorShape.ArrowCursor)

    def prepare_header(self, width):
        available = max(1, width - 26 - self.role_label.width() - 6)
        height = self.name.fontMetrics().boundingRect(QRect(0, 0, available, 10000),
                                                     Qt.TextFlag.TextWordWrap, self.name.text()).height()
        self.name.setFixedHeight(max(20, height))
        for row, i in zip(self.auxiliary_rows, self.auxiliary_indices):
            required = self.field_labels[i].width() + self.values[i].width() + self.units[i].width() + 2 * tokens.SPACE_XS
            row.setDirection(QBoxLayout.Direction.LeftToRight if required <= width - 26
                             else QBoxLayout.Direction.TopToBottom)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'marker'):
            self.marker.setGeometry(0, 8, 3, max(0, self.height() - 16))
            self.marker.raise_()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._line_key is not None:
            self.line_requested.emit(self._line_key)
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self._line_key is not None:
            self.line_requested.emit(self._line_key)
            event.accept()
        else:
            super().keyPressEvent(event)


class LatestInfoPage(QWidget):
    scope_changed = Signal(str, str)
    open_save_requested = Signal()
    line_requested = Signal(str)
    share_requested = Signal()
    report_requested = Signal()
    line_export_requested = Signal()
    company_export_requested = Signal()

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._snapshot: LatestInfoSnapshot | None = None
        self._workbook_availability = (False, False)
        self._session_key = None
        self._alert_panel = None
        self._pending_chart_state = None
        self._layout_signature = None
        self.setObjectName('latestInfoPage')
        self.setFont(font(tokens.FONT_SIZE_BODY))
        self.setStyleSheet(f'QWidget#latestInfoPage {{background:{tokens.PAGE_BG};}}')
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll = StatisticsScrollArea(self)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self.scroll)
        self.board = QWidget()
        self.board.setMinimumWidth(0)
        board = QVBoxLayout(self.board)
        board.setContentsMargins(0, 0, 0, 0)
        board.setSpacing(0)
        self._build_header(board)
        self.columns = QGridLayout()
        self.columns.setContentsMargins(0, 0, 0, 0)
        self.columns.setSpacing(12)
        board.addLayout(self.columns)
        self.main = QWidget()
        self.main.setMinimumWidth(0)
        main = QVBoxLayout(self.main)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(8)
        self._build_city(main)
        self._build_scope(main)
        self.metric_cards = {key: MetricCard(key, title, unit) for key, title, unit in METRICS}
        self.modules_host = QWidget()
        self.modules_host.setMinimumWidth(0)
        self.modules_grid = QGridLayout(self.modules_host)
        self.modules_grid.setContentsMargins(0, 0, 0, 0)
        self.modules_grid.setHorizontalSpacing(12)
        self.modules_grid.setVerticalSpacing(12)
        self.metric_modules = {}
        for group, title, keys, _ in BUSINESS_MODULES:
            module = card(f'metricModule-{group}', elevated=False)
            box = QVBoxLayout(module)
            box.setContentsMargins(tokens.SPACE_MD, tokens.SPACE_MD, tokens.SPACE_MD, tokens.SPACE_MD)
            box.setSpacing(0)
            module_header = QHBoxLayout()
            module_header.setSpacing(tokens.SPACE_SM)
            icon = IconWidget(module)
            icon.setIcon(MODULE_ICONS[group].icon(color=QColor(tokens.ACCENT)))
            icon.setFixedSize(16, 16)
            module_header.addWidget(icon)
            heading = label(title, size=14, bold=True, parent=module)
            heading.setFixedHeight(heading.fontMetrics().height())
            module_header.addWidget(heading, 1)
            box.addLayout(module_header)
            box.addSpacing(tokens.SPACE_XS)
            for index, key in enumerate(keys):
                if index:
                    box.addSpacing(tokens.SPACE_XS)
                if group == 'network' and index or group == 'finance' and key == 'profit':
                    box.addStretch()
                if group == 'finance' and key == 'profit':
                    divider = QFrame(module)
                    divider.setFixedHeight(1)
                    divider.setStyleSheet(f'background:{tokens.BORDER};border:0;')
                    box.addWidget(divider)
                    box.addSpacing(6)
                box.addWidget(self.metric_cards[key])
            if group == 'network':
                box.addStretch()
            module.setAccessibleName(title)
            self.metric_modules[group] = module
        main.addWidget(self.modules_host)
        self.highlights_host = QWidget()
        self.highlights_host.setMinimumWidth(0)
        highlights_box = QVBoxLayout(self.highlights_host)
        highlights_box.setContentsMargins(0, 0, 0, 0)
        highlights_box.setSpacing(2)
        self.highlight_section_title = label('线路亮点', 'highlightSectionTitle', 14, True)
        self.highlight_section_title.setFixedHeight(self.highlight_section_title.fontMetrics().height())
        highlights_box.addWidget(self.highlight_section_title)
        self.highlights = [HighlightCard(i) for i in range(4)]
        self.highlights_group = card('highlightsGroup', elevated=False)
        self.highlights_group.setStyleSheet('QFrame#highlightsGroup {background:transparent;border:0;}')
        self.highlights_group.setAccessibleName('线路亮点：客流最大、客流最小、班次最多、班次最少')
        self.highlight_grid = QGridLayout(self.highlights_group)
        self.highlight_grid.setContentsMargins(0, 0, 0, 0)
        self.highlight_grid.setSpacing(tokens.SPACE_MD)
        highlights_box.addWidget(self.highlights_group)
        main.addWidget(self.highlights_host)
        for highlight in self.highlights:
            highlight.line_requested.connect(self.line_requested.emit)
        self.chart_grid = QGridLayout()
        self.chart_grid.setContentsMargins(0, 0, 0, 0)
        self.chart_grid.setSpacing(10)
        self.chart_host = QWidget()
        self.chart_host.setObjectName('analysisSection')
        self.chart_host.setAccessibleName('运营分析')
        self.chart_host.setLayout(self.chart_grid)
        board.addSpacing(tokens.SPACE_XS)
        board.addWidget(self.chart_host)
        board.addStretch()
        self.trend = TodayTrendPanel('今日客流趋势', settings=settings, settings_key='latest-info/trend-style',
                               allowed_modes=('line',), modes=False)
        self.trend.setObjectName('todayTrend')
        self.trend.setStyleSheet(f'QFrame#todayTrend {{background:{tokens.CARD_BG};border:1px solid '
                                f'{tokens.BORDER};border-radius:{tokens.RADIUS_CHART}px;}}')
        self.trend.setMinimumWidth(0)
        self.trend.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.trend.set_compact_height(304)
        self.trend.set_category_palette(tokens.DATA_CATEGORY_COLORS)
        self.passengers = PassengerRanking()
        self.departures = DepartureStructure()
        for chart in (self.passengers, self.departures):
            chart.line_requested.connect(self.line_requested.emit)
        self.alert_host = QWidget()
        self.alert_host.setObjectName('alertHost')
        self.alert_layout = QVBoxLayout(self.alert_host)
        self.alert_layout.setContentsMargins(0, 0, 0, 0)
        self.alert_layout.setSpacing(0)
        self.alert_empty = card('alertEmpty', tokens.RADIUS_CARD)
        empty_box = QVBoxLayout(self.alert_empty)
        empty_box.setContentsMargins(16, 16, 16, 16)
        empty_box.addWidget(label('关键提醒', size=14, bold=True))
        empty_box.addWidget(label('未载入可比数据'))
        empty_box.addStretch()
        self.alert_layout.addWidget(self.alert_empty)
        self.scroll.setWidget(self.board)
        self.surface_motion = SurfaceMotion(self.board)
        self._reflow(1204)
        self.clear_session()

    def _build_header(self, layout):
        header = QWidget(self)
        header.setFixedHeight(40)
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        icon_base = QFrame(header)
        icon_base.setObjectName('latestPageIcon')
        icon_base.setFixedSize(40, 40)
        icon_base.setStyleSheet(f'QFrame#latestPageIcon {{background:{tokens.ACCENT_SOFT};border:0;border-radius:9px;}}')
        icon_box = QHBoxLayout(icon_base)
        icon_box.setContentsMargins(9, 9, 9, 9)
        icon = IconWidget(icon_base)
        icon.setIcon(FluentIcon.HOME.icon(color=QColor(tokens.ACCENT)))
        icon.setFixedSize(22, 22)
        icon_box.addWidget(icon)
        row.addWidget(icon_base)
        title = label('最新信息', 'latestTitle', tokens.FONT_SIZE_PAGE_TITLE, True)
        row.addWidget(title, 1)
        self.actions = {}
        specifications = (
            ('lineExportAction', '导出线路 XLSX', self.line_export_requested, FluentIcon.SAVE),
            ('companyExportAction', '导出公司 XLSX', self.company_export_requested, FluentIcon.SAVE),
            ('shareAction', '分享', self.share_requested, FluentIcon.SHARE),
            ('reportAction', '导出报告', self.report_requested, FluentIcon.DOCUMENT),
        )
        self.more = DropDownPushButton('更多')
        self.more.setFont(font())
        self.more.setFixedHeight(36)
        self.more_menu = RoundMenu(parent=self.more)
        self.menu_actions = {}
        for name, text, signal, icon in specifications:
            button = PushButton(text)
            button.setObjectName(name)
            button.setFont(font())
            button.setFixedHeight(36)
            button.setAccessibleName(text)
            button.setIcon(icon)
            button.clicked.connect(signal.emit)
            row.addWidget(button)
            self.actions[name] = button
            action = QAction(icon.icon(), text, self.more_menu)
            action.triggered.connect(signal.emit)
            self.more_menu.addAction(action)
            self.menu_actions[name] = action
        self.more.setMenu(self.more_menu)
        row.addWidget(self.more)
        self.open_button = PrimaryPushButton('打开存档')
        self.open_button.setObjectName('openSaveAction')
        self.open_button.setIcon(FluentIcon.FOLDER)
        self.open_button.setFont(font())
        self.open_button.setFixedHeight(36)
        self.open_button.clicked.connect(self.open_save_requested.emit)
        row.addWidget(self.open_button)
        # The application header owns title and actions; this row stays only
        # as the source of the page's action signals.
        self.page_header = header
        header.hide()

    def _build_city(self, layout):
        self.city = CitySummaryCard()
        self.city_grid = QGridLayout(self.city)
        self.city_grid.setContentsMargins(12, 8, 12, 8)
        self.city_grid.setHorizontalSpacing(12)
        self.city_grid.setVerticalSpacing(4)
        self.city_fields = []
        self.city_name = label('未提供城市名称', 'cityName', 29, True)
        self.city_date = label('未提供模拟时间', 'citySimulationDate', 14)
        self.city_clock = label('—', 'citySimulationTime', 21, True)
        self.city_population = label('—', 'cityPopulation', 21, True)
        self.city_population.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.city_population_unit = label('人', 'cityPopulationUnit', 12)
        self.city_population_unit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.city_save = label('未载入存档', 'citySaveName', 12)
        self.city_save.setProperty('elideMode', 'middle')
        for title, value in (('', self.city_name), ('', self.city_clock),
                             ('人口', self.city_population), ('', self.city_save)):
            field = QWidget()
            field.setMinimumWidth(0)
            field.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            box = QVBoxLayout(field)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(2)
            if title:
                heading = label(title, 'cityPopulationTitle', parent=field)
                heading.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};background:transparent;')
                box.addWidget(heading, 0)
            if value is self.city_clock:
                box.addWidget(self.city_date)
                box.addWidget(value, 1)
            elif value is self.city_population:
                numbers = QHBoxLayout()
                numbers.setSpacing(4)
                numbers.addWidget(value)
                numbers.addWidget(self.city_population_unit, 0, Qt.AlignmentFlag.AlignBaseline)
                numbers.addStretch()
                box.addLayout(numbers, 1)
            else:
                box.addWidget(value, 1)
            self.city_fields.append(field)
        self.city.set_visual_variant('light')
        layout.addWidget(self.city)

    def _build_scope(self, layout):
        self.scope_host = QWidget()
        self.scope_host.setFixedHeight(32)
        row = QHBoxLayout(self.scope_host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(label('运营概况', 'coreSectionTitle', 14, True), 1)
        self.company_combo = ComboBox(self.scope_host)
        self.company_combo.setAccessibleName('最新信息公司范围')
        self.company_combo.setMinimumWidth(0)
        self.company_combo.setMaximumWidth(240)
        self.mode_combo = ComboBox(self.scope_host)
        self.mode_combo.setAccessibleName('最新信息制式范围')
        self.mode_combo.setMinimumWidth(0)
        self.mode_combo.setMaximumWidth(140)
        for combo in (self.company_combo, self.mode_combo):
            combo.setFont(font())
            combo.setFixedHeight(32)
        row.addWidget(self.company_combo, 0)
        row.addWidget(self.mode_combo, 0)
        self.scope_label = label('未载入存档', 'latestScope', parent=self.scope_host)
        self.scope_label.setVisible(False)
        self.company_combo.currentIndexChanged.connect(self._scope_changed)
        self.mode_combo.currentIndexChanged.connect(self._scope_changed)
        layout.addWidget(self.scope_host)

    def _populate_scopes(self, companies, modes, scope=('', '综合')):
        for combo in (self.company_combo, self.mode_combo):
            combo.blockSignals(True)
            combo.clear()
        self.company_combo.addItem('全部公司', userData='')
        names = [name for _, name in companies]
        for key, name in companies:
            self.company_combo.addItem(f'{name} [{key}]' if names.count(name) > 1 else name, userData=key)
        self.mode_combo.addItem('综合', userData='综合')
        for mode in dict.fromkeys(modes):
            if mode != '综合':
                self.mode_combo.addItem(mode, userData=mode)
        self.company_combo.setCurrentIndex(max(0, self.company_combo.findData(scope[0])))
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(scope[1])))
        for combo in (self.company_combo, self.mode_combo):
            combo.blockSignals(False)

    def set_session(self, data: dict):
        self._workbook_availability = (False, False)
        self._clear_snapshot()
        self._session_key = str(data.get('save_key') or data.get('session_key') or '')
        metadata = data.get('metadata') or {}
        companies = tuple((str(company.get('公司标识') or company.get('玩家ID') or f'company-index:{i}'),
                           str(company.get('公司名称') or '未命名公司'))
                          for i, company in enumerate(data.get('companies') or []))
        modes = dict.fromkeys(display_mode(line.get('运输制式'))
                              for line in data.get('lines') or [] if line.get('运输制式'))
        for company in data.get('companies') or []:
            for mode, count in (company.get('车队') or {}).items():
                number = numeric(count)
                if number is not None and number > 0:
                    modes[display_mode(mode)] = None
            for mode in company.get('非零制式') or []:
                modes[display_mode(mode)] = None
        self._populate_scopes(companies, modes)
        candidate = data.get('simulation_time')
        if not candidate and metadata.get('当前日期'):
            candidate = f"{metadata['当前日期']} {metadata.get('当前时间') or '00:00:00'}"
        try:
            clock = parse_time(candidate) if candidate else None
        except (ValueError, TypeError):
            clock = None
        city_info = resolve_session_map_name(data)
        self._set_city(city_info.display_name,
                       clock,
                       numeric(metadata.get('当前人口数')),
                       PureWindowsPath(str(data.get('save_path') or '')).name
                       or str(data.get('save_name') or '未提供存档名称'))
        self.city_name.setToolTip('\n'.join(part for part in (
            city_info.display_name, city_info.source, city_info.raw_reference,
            city_info.raw_map_name, city_info.internal_id, city_info.reason) if part))
        self.scope_label.setText('等待当前范围数据')

    def _set_city(self, city, clock, population, save):
        self.city_name.setText(city)
        date = f'{clock:%Y-%m-%d}  周{"一二三四五六日"[clock.weekday()]}' if clock else '未提供模拟时间'
        self.city_date.setText(date)
        self.city_clock.setText(f'{clock:%H:%M:%S}' if clock else '—')
        complete_clock = f'{date} {clock:%H:%M:%S}' if clock else date
        for widget in (self.city_date, self.city_clock):
            widget.setToolTip(complete_clock)
            widget.setAccessibleName(complete_clock)
        self.city_population.setText(shown(population))
        self.city_save.setText(save or '未提供存档名称')

    def set_snapshot(self, snapshot: LatestInfoSnapshot):
        if self._session_key is None or snapshot.session_key != self._session_key or (
                snapshot.company_id, snapshot.mode) != self.scope():
            return
        self._snapshot = snapshot
        self._populate_scopes(snapshot.companies, snapshot.modes, self.scope())
        self._set_city(snapshot.city_name, snapshot.simulation_time, snapshot.population, snapshot.save_name)
        self.city_name.setToolTip('\n'.join(part for part in (
            snapshot.city_name, snapshot.city_source, snapshot.city_raw_reference,
            snapshot.city_raw_name, snapshot.city_internal_id, snapshot.city_name_reason) if part))
        metrics = {metric.key: metric for metric in snapshot.metrics}
        for key, widget in self.metric_cards.items():
            widget.set_value(metrics.get(key))
        for i, widget in enumerate(self.highlights):
            widget.set_line(snapshot.highlights[i].line if i < len(snapshot.highlights) else None)
        company_names = dict(snapshot.companies)
        company_names['__selected__'] = '所选公司合计'
        self.trend.set_company_palette({key: tokens.DATA_COMPANY_COLORS[index % len(tokens.DATA_COMPANY_COLORS)]
                                       for index, key in enumerate(sorted(dict(snapshot.companies)))})
        self.trend.set_result(snapshot.company_trend, company_names)
        self.passengers.set_data(snapshot.lines, snapshot.passenger_top10, snapshot.passenger_modes, scope_mode=snapshot.mode)
        self.departures.set_data(snapshot.lines, snapshot.departure_modes, snapshot.total_departures, scope_mode=snapshot.mode)
        self.scope_label.setText(snapshot.scope_text)
        if self._pending_chart_state is not None:
            self.restore_chart_state(self._pending_chart_state, allow_scope_change=True)
            self._pending_chart_state = None
        self._set_actions(True)
        self._layout_signature = None
        self._reflow(self.width())
        self.surface_motion.reveal()

    def _set_actions(self, enabled):
        availability = dict(zip(('lineExportAction', 'companyExportAction'), self._workbook_availability))
        for name, button in self.actions.items():
            available = bool(enabled and availability.get(name, True))
            button.setEnabled(available)
            self.menu_actions[name].setEnabled(available)
        self.more.setEnabled(enabled)

    def set_workbook_availability(self, line_available: bool, company_available: bool):
        self._workbook_availability = (bool(line_available), bool(company_available))
        self._set_actions(self._snapshot is not None)

    def _clear_snapshot(self):
        self._pending_chart_state = None
        self._snapshot = None
        self._set_actions(False)
        for widget in self.metric_cards.values():
            widget.set_value(None)
        for widget in self.highlights:
            widget.set_line(None)
        self.trend.clear()
        self.passengers.clear()
        self.departures.clear()
        if self._alert_panel is not None and hasattr(self._alert_panel, 'clear_session'):
            self._alert_panel.clear_session()
        self._layout_signature = None
        self._reflow(self.width())

    def clear_session(self):
        self._workbook_availability = (False, False)
        self._session_key = None
        self._clear_snapshot()
        self._populate_scopes((), ())
        self._set_city('未提供城市名称', None, None, '未载入存档')
        self.scope_label.setText('未载入存档')

    def _scope_changed(self, *_):
        state = self.capture_chart_state()
        self._clear_snapshot()
        self._pending_chart_state = state
        self.scope_label.setText('等待当前范围数据')
        self.scope_changed.emit(*self.scope())

    def scope(self) -> tuple[str, str]:
        return (str(self.company_combo.currentData() or ''), str(self.mode_combo.currentData() or '综合'))

    def capture_chart_state(self) -> dict:
        """JSON-safe intent only. D may retain it across same-session invalidation."""
        if self._snapshot is None and self._pending_chart_state is not None and self._pending_chart_state['session_key'] == self._session_key:
            return {**self._pending_chart_state,
                    'scope': tuple(self._pending_chart_state['scope']),
                    'passengers': dict(self._pending_chart_state['passengers']),
                    'departures': dict(self._pending_chart_state['departures'])}
        scope = (self._snapshot.company_id, self._snapshot.mode) if self._snapshot is not None else self.scope()
        return {'session_key': self._session_key, 'scope': scope,
                'passengers': self.passengers.capture_state(),
                'departures': self.departures.capture_state()}

    def restore_chart_state(self, state: dict, *, allow_scope_change: bool = False) -> bool:
        """Require a currently accepted snapshot; scope relaxation never relaxes session."""
        if not isinstance(state, dict) or self._snapshot is None or state.get('session_key') != self._session_key:
            return False
        scope = state.get('scope')
        if not isinstance(scope, (tuple, list)) or len(scope) != 2 or not all(isinstance(key, str) for key in scope):
            return False
        if not allow_scope_change and tuple(scope) != self.scope():
            return False
        self.passengers.restore_state(state.get('passengers'))
        self.departures.restore_state(state.get('departures'))
        return True

    def set_alert_panel(self, panel: QWidget):
        if panel is self._alert_panel:
            return
        if self._alert_panel is not None:
            self.alert_layout.removeWidget(self._alert_panel)
            self._alert_panel.hide()
            self._alert_panel.setParent(None)
        self.alert_empty.hide()
        self._alert_panel = panel
        self.alert_layout.addWidget(panel)
        panel.show()

    def export_target(self) -> QWidget:
        return self.board

    @staticmethod
    def _grid(grid, widgets, columns, height):
        while grid.count():
            grid.takeAt(0)
        for i in range(8):
            grid.setColumnStretch(i, 0)
        for i in range(columns):
            grid.setColumnStretch(i, 1)
        for i, widget in enumerate(widgets):
            widget.setFixedHeight(height)
            grid.addWidget(widget, i // columns, i % columns)

    def _reflow(self, width):
        wide = width >= 1180
        main_width = width - 272 if wide else width
        minimums = [max(self.metric_cards[key].content_width() for key in keys) + 24
                    for _, _, keys, _ in BUSINESS_MODULES]
        module_columns = (4 if wide and sum(minimums) + 36 <= main_width else
                          2 if main_width >= max(minimums) * 2 + 12 else 1)
        highlight_columns = 4 if wide else 2 if width >= 520 else 1
        compact_actions = width < 1000
        signature = (wide, module_columns, highlight_columns, compact_actions, tuple(minimums))
        if signature == self._layout_signature:
            return
        self._layout_signature = signature
        for button in self.actions.values():
            button.setVisible(not compact_actions)
        self.more.setVisible(compact_actions)
        while self.columns.count():
            self.columns.takeAt(0)
        self.columns.setColumnStretch(0, 1)
        self.columns.setColumnStretch(1, 0)
        while self.modules_grid.count():
            self.modules_grid.takeAt(0)
        for i in range(4):
            self.modules_grid.setColumnStretch(i, 0)
        module_height = max(module.minimumSizeHint().height() for module in self.metric_modules.values())
        available = main_width - 12 * (module_columns - 1)
        if module_columns == 4:
            spare = max(0, available - sum(minimums))
            weights = [item[3] for item in BUSINESS_MODULES]
            widths = [minimum + spare * weight // sum(weights) for minimum, weight in zip(minimums, weights)]
            widths[-1] += available - sum(widths)
        else:
            widths = [1] * module_columns
        for i in range(module_columns):
            self.modules_grid.setColumnStretch(i, widths[i])
        for i, (group, _, _, _) in enumerate(BUSINESS_MODULES):
            module = self.metric_modules[group]
            module.setFixedHeight(module_height)
            self.modules_grid.addWidget(module, i // module_columns, i % module_columns)
        module_rows = (4 + module_columns - 1) // module_columns
        self.modules_host.setFixedHeight(module_rows * module_height + (module_rows - 1) * 12)
        highlight_width = (main_width - tokens.SPACE_MD * (highlight_columns - 1)) // highlight_columns
        for widget in self.highlights:
            widget.prepare_header(highlight_width)
        header_height = max(widget.name.height() for widget in self.highlights)
        for widget in self.highlights:
            widget.name.setFixedHeight(header_height)
            # Direction and fixed-width changes must be measured synchronously.
            for row in widget.auxiliary_rows:
                row.itemAt(row.count() - 1).layout().invalidate()
                row.invalidate()
            widget.auxiliary_grid.invalidate()
            widget.layout().invalidate()
            widget.layout().activate()
        highlight_height = max(widget.minimumSizeHint().height() for widget in self.highlights)
        self._grid(self.highlight_grid, self.highlights, highlight_columns, highlight_height)
        highlight_rows = (4 + highlight_columns - 1) // highlight_columns
        self.highlights_host.setFixedHeight(highlight_rows * highlight_height + (highlight_rows - 1) * tokens.SPACE_MD
                                            + self.highlight_section_title.height() + 2)
        city_height = 65 if wide else 136
        self.city.setFixedHeight(city_height)
        main_height = city_height + 32 + self.modules_host.height() + self.highlights_host.height() + 24
        self.main.setFixedHeight(main_height)
        if wide:
            self.alert_host.setFixedWidth(260)
            self.alert_host.setFixedHeight(494)
            self.columns.addWidget(self.main, 0, 0)
            self.columns.addWidget(self.alert_host, 0, 1)
        else:
            self.alert_host.setMinimumWidth(0)
            self.alert_host.setMaximumWidth(16777215)
            self.alert_host.setMinimumHeight(494)
            self.alert_host.setMaximumHeight(16777215)
            self.columns.addWidget(self.main, 0, 0)
            self.columns.addWidget(self.alert_host, 1, 0)
        while self.city_grid.count():
            self.city_grid.takeAt(0)
        for i in range(4):
            self.city_grid.setColumnStretch(i, (30, 24, 22, 24)[i] if wide else (1 if i < 2 else 0))
        for i, field in enumerate(self.city_fields):
            self.city_grid.addWidget(field, 0 if wide else i // 2, i if wide else i % 2)
        while self.chart_grid.count():
            self.chart_grid.takeAt(0)
        for i, chart in enumerate((self.trend, self.passengers, self.departures)):
            self.chart_grid.addWidget(chart, 0 if wide else i, i if wide else 0)
            self.chart_grid.setColumnStretch(i, (384, 400, 400)[i] if wide else (1 if i == 0 else 0))
        self.board.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'board'):
            self._reflow(event.size().width())
