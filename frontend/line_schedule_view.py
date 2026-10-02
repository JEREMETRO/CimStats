"""Compact, read-only timetable. All dimensions use Qt logical pixels.

Integrate ``SchedulePanel.set_line(line)`` and ``clear()``. The selected
``current_group``, prepared ``summary`` and painted ``matrix.entries`` are
available for consumers. Calculation and operating-day ordering belong to
``line_schedule.prepare_schedule``; this module only presents its result.
Narrow parents should put the panel in a scrollable container: it reflows
columns and grows vertically rather than dropping or shrinking times.
"""
from __future__ import annotations

from collections.abc import Mapping
from math import ceil
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPainter
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                              QScrollArea, QSizePolicy, QToolTip,
                              QVBoxLayout, QWidget)
from qfluentwidgets import (ComboBox, FluentIcon, IconWidget, TogglePushButton,
                            TransparentToolButton, ToolTip)

from line_schedule import prepare_schedule
import stats_tokens as tokens
from stats_typography import emphasis_css, apply_emphasis_font
from stats_controls import FluentSegmentedControl, StatisticsScrollArea
from stats_elevation import attach_card_elevation


VEHICLE_COLORS = {
    '任意': '#242B32', '小型': '#206343', '中型': '#876519',
    '大型': '#A33C38',
}
PERIOD_COLORS = {
    'morning_peak': '#FFF3DF', 'evening_peak': '#E7F0FC',
    'night': '#F0F2F5', 'next_day': '#E4E7EB',
}
_VEHICLE_ALIASES = {
    '任': '任意', '小': '小型', '中': '中型', '大': '大型',
    0: '任意', 1: '小型', 2: '中型', 3: '大型',
    '0': '任意', '1': '小型', '2': '中型', '3': '大型',
}
_NUMBER_FONT_ID = None


def _vehicle_type(entry):
    for key in ('vehicle_type', 'preferred_vehicle', 'vehicle_code', '首选车型'):
        value = entry.get(key)
        if value is not None and value != '':
            return value if value in VEHICLE_COLORS else _VEHICLE_ALIASES.get(value, '—')
    return '—'


class ScheduleMatrix(QWidget):
    """One paint surface, with no per-departure widgets or click action.

    ``row_height`` is the actual cell stride; ``minimum_row_height`` only
    determines the layout minimum, so a spacious matrix can shrink again.
    ``row_offset`` remains zero, keeping the first row next to the summary.
    """

    geometryChanged = Signal()
    ROW_HEIGHT = 20
    BASE_HEIGHT = 280
    MAX_COLUMNS = 10
    MAX_ROW_HEIGHT = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        global _NUMBER_FONT_ID
        if _NUMBER_FONT_ID is None:
            path = Path('C:/Windows/Fonts/msyh.ttc')
            _NUMBER_FONT_ID = QFontDatabase.addApplicationFont(str(path)) if path.is_file() else -1
        self.entries = []
        self.capacity = 140
        self.minimum_row_height = 20
        self.row_height = 20
        self.row_offset = 0
        self.base_height = 280
        self._hover = None
        self._tooltip = None
        self.columns = 10
        self._scroll = None
        self.setObjectName('scheduleMatrix')
        font = QFont(tokens.FONT_FAMILY)
        font.setFeature(QFont.Tag('tnum'), 1)
        font.setPixelSize(tokens.FONT_SIZE_BODY)
        font.setWeight(QFont.Weight.Normal)
        self.setFont(font)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.setMinimumHeight(self.BASE_HEIGHT)
        self.setAccessibleDescription('只读时刻表')

    @property
    def total_count(self):
        return len(self.entries)

    @property
    def display_count(self):
        return len(self.visible_indices())

    def set_entries(self, entries):
        self.entries = list(entries)
        self._hover = None
        self._hide_tooltip()
        self.setAccessibleName('发班时刻表；' + '；'.join(
            self.tooltip_for(index).replace('\n', '，') for index in range(len(self.entries))))
        self._update_geometry()
        self.update()

    def set_expanded(self, expanded):
        self.capacity = 200 if expanded else 140
        self.minimum_row_height = 24 if expanded else 20
        self.base_height = 480 if expanded else 280
        self._update_geometry()
        self.update()

    @staticmethod
    def vehicle_color(entry):
        return QColor(VEHICLE_COLORS.get(_vehicle_type(entry), tokens.TEXT_PRIMARY))

    @staticmethod
    def background_color(entry):
        if entry.get('next_day'):
            key='next_day'
        elif entry.get('period') == 'morning_peak' or entry.get('morning_peak'):
            key='morning_peak'
        elif entry.get('period') == 'evening_peak' or entry.get('evening_peak'):
            key='evening_peak'
        elif entry.get('period') == 'night':
            key='night'
        else:
            return QColor(tokens.CARD_BG)
        return QColor(PERIOD_COLORS[key])

    def _update_geometry(self):
        # Full HH:mm stays readable when a narrow parent requires fewer columns.
        cell_width = self.fontMetrics().horizontalAdvance('23:59') + 24
        # A hidden QScrollArea does not yet resize its viewport/content, although
        # its own layout geometry is already correct. Avoid using that 100px stub.
        width = (self._scroll.width() - 2 * self._scroll.frameWidth()
                 if self._scroll is not None and not self.isVisible() else self.width())
        self.columns = min(self.MAX_COLUMNS, max(1, width // cell_width))
        height = max(self.base_height,
                     ceil(len(self.entries) / self.columns) * self.minimum_row_height)
        self.setMinimumHeight(height)
        self.row_height = self.minimum_row_height
        self.row_offset = 0
        if len(self.entries) <= self.capacity:
            capacity_rows = ceil(self.capacity / self.columns)
            self.row_height = min(self.MAX_ROW_HEIGHT,
                                  max(self.minimum_row_height, self.height() // capacity_rows))
        self.geometryChanged.emit()

    def resizeEvent(self, event):
        self._hide_tooltip()
        super().resizeEvent(event)
        self._update_geometry()

    def cell_rect(self, index):
        if not 0 <= index < len(self.entries):
            return QRect()
        row, column = divmod(index, self.columns)
        left = column * self.width() // self.columns
        right = (column + 1) * self.width() // self.columns
        return QRect(left, self.row_offset + row * self.row_height, right - left, self.row_height)

    def entry_at(self, position):
        if not self.rect().contains(position) or self.width() <= 0:
            return None
        y = position.y() - self.row_offset
        if y < 0:
            return None
        column = min(self.columns - 1, position.x() * self.columns // self.width())
        index = y // self.row_height * self.columns + column
        return index if 0 <= index < len(self.entries) else None

    def period_runs(self):
        """Merge adjacent period colors within each row into one paint band."""
        ordinary = QColor(tokens.CARD_BG)
        for row_start in range(0, len(self.entries), self.columns):
            row_end = min(row_start + self.columns, len(self.entries))
            start = row_start
            color = self.background_color(self.entries[start])
            for index in range(row_start + 1, row_end + 1):
                following = self.background_color(self.entries[index]) if index < row_end else None
                if following != color:
                    if color != ordinary:
                        rect = self.cell_rect(start).united(self.cell_rect(index - 1))
                        yield rect.adjusted(0, 2, 0, -2), color
                    start, color = index, following

    def visible_indices(self):
        if self._scroll is None:
            visible = self.rect()
        else:
            viewport = self._scroll.viewport()
            visible = QRect(self.mapFrom(viewport, QPoint(0, 0)), viewport.size())
        return [index for index in range(len(self.entries))
                if visible.contains(self.cell_rect(index))]

    def tooltip_for(self, index):
        if not 0 <= index < len(self.entries):
            return ''
        entry = self.entries[index]
        clock = entry.get('display_time') or ('次日' if entry.get('next_day') else '') + entry['time']
        # The model keeps precise seconds separately from the compact HH:mm glyphs.
        seconds = entry.get('clock_seconds')
        if seconds is not None and seconds % 60:
            clock += ':' + f'{seconds % 60:09.6f}'.rstrip('0').rstrip('.')
        return f'发班序号：第{index + 1}班\n完整时刻：{clock}\n车型：{_vehicle_type(entry)}'

    def _hide_tooltip(self):
        from shiboken6 import isValid
        if self._tooltip is not None and isValid(self._tooltip):
            self._tooltip.opacityAni.stop()
            self._tooltip.hide()
        QToolTip.hideText()

    def _show_tooltip(self, index, global_position):
        if self._tooltip is None:
            self._tooltip = ToolTip(parent=self.window())
            self._tooltip.label.setTextFormat(Qt.TextFormat.PlainText)
            self._tooltip.setDuration(7000)
            self.destroyed.connect(self._tooltip.deleteLater)
        from stats_motion import animations_enabled
        self._tooltip.opacityAni.setDuration(150 if animations_enabled() else 0)
        self._tooltip.setText(self.tooltip_for(index))
        screen = QGuiApplication.screenAt(global_position) or self.screen()
        available = screen.availableGeometry()
        x = min(max(available.left(), global_position.x() + 8),
                available.right() - self._tooltip.width() + 1)
        y = global_position.y() + 16
        if y + self._tooltip.height() > available.bottom() + 1:
            y = global_position.y() - self._tooltip.height() - 8
        y = max(available.top(), y)
        self._tooltip.move(x, y)
        self._hover = index
        self._tooltip.show()
        self.update()

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            index = self.entry_at(event.pos())
            if index is not None:
                self._show_tooltip(index, event.globalPos())
            else:
                self._hide_tooltip()
            return True
        return super().event(event)

    def hideEvent(self, event):
        self._hide_tooltip()
        super().hideEvent(event)

    def mouseMoveEvent(self, event):
        index = self.entry_at(event.position().toPoint())
        if index != self._hover:
            self._hide_tooltip()
            self._hover = index
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hide_tooltip()
        self._hover = None
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(tokens.CARD_BG))
        painter.setFont(self.font())
        if not self.entries:
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, '当前日组暂无班次')
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for rect, color in self.period_runs():
            if event.rect().intersects(rect):
                painter.setBrush(color)
                painter.drawRoundedRect(rect, tokens.RADIUS_CONTROL, tokens.RADIUS_CONTROL)
        for index, entry in enumerate(self.entries):
            rect = self.cell_rect(index)
            if not event.rect().intersects(rect):
                continue
            if index == self._hover:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(tokens.SEGMENT_QUIET_HOVER))
                painter.drawRoundedRect(rect.adjusted(0, 2, 0, -2),
                                        tokens.RADIUS_CONTROL, tokens.RADIUS_CONTROL)
            painter.setFont(self.font())
            painter.setPen(self.vehicle_color(entry))
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, entry['time'])
        painter.end()


class SchedulePanel(QFrame):
    """Timetable card; ``set_line`` accepts the normalized line dictionary.

    ``period_rules`` is optional and is forwarded only to the pure model.
    At normal widths the default 280-pixel matrix fits 140 entries. Expanded
    mode uses 24–30-pixel rows and fits 200 entries. The parent owns hiding and
    restoring the detail cards in response to ``expansionRequested(bool)``.
    """

    currentGroupChanged = Signal(str)
    expansionRequested = Signal(bool)
    SUMMARY_TRACKS = {
        'first': (0, 1), 'last': (1, 1), 'count': (2, 1),
        'morning_peak': (3, 2), 'evening_peak': (5, 2),
        'offpeak': (7, 2), 'night': (9, 1),
    }

    def __init__(self, parent=None, period_rules=None):
        super().__init__(parent)
        self.period_rules = period_rules
        self.expanded = False
        self.day_groups = ()
        self.current_group = None
        self.summary = {}
        self._line = {}
        self._schedules = {}
        self.group_buttons = {}
        self.group_control = None
        self.setObjectName('schedulePanel')
        self.setStyleSheet(
            f'QFrame#schedulePanel {{background: {tokens.CARD_BG}; '
            f'border: 1px solid {tokens.BORDER}; border-radius: {tokens.RADIUS_CARD}px;}}')
        attach_card_elevation(self, radius=tokens.RADIUS_CARD)
        self.setMinimumHeight(426)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(tokens.CARD_PADDING, tokens.CARD_PADDING,
                                       tokens.CARD_PADDING, tokens.CARD_PADDING)
        self._layout.setSpacing(tokens.CONTROL_GAP)
        heading = QHBoxLayout()
        self._heading_layout = heading
        heading.setSpacing(8)
        self.title_icon = IconWidget(self)
        self.title_icon.setIcon(FluentIcon.CALENDAR.icon(color=QColor(tokens.ACCENT)))
        self.title_icon.setFixedSize(18, 18)
        heading.addWidget(self.title_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        self.title_label = QLabel('发班时刻表', self)
        self.title_label.setObjectName('panelTitle')
        self.title_label.setStyleSheet(
            f'{emphasis_css(tokens.FONT_SIZE_CHART_TITLE)}color: {tokens.TEXT_PRIMARY};')
        apply_emphasis_font(self.title_label, tokens.FONT_SIZE_CHART_TITLE)
        self.title_label.setFixedHeight(24)
        heading.addWidget(self.title_label)
        self.overflow_label = QLabel('超过 200 班 · 滚动查看全部', self)
        self.overflow_label.setObjectName('hint')
        self.overflow_label.setStyleSheet(
            f'font-family: "{tokens.FONT_FAMILY}"; color: {tokens.TEXT_SECONDARY}; '
            f'font-size: {tokens.FONT_SIZE_CAPTION}px;')
        heading.addWidget(self.overflow_label)
        self.expansion_button = TransparentToolButton(self)
        self.expansion_button.setFixedSize(24, 24)
        self.expansion_button.clicked.connect(self._request_expansion)
        self._update_expansion_button()
        heading.addWidget(self.expansion_button)
        self._layout.addLayout(heading)

        self.group_host = QWidget(self)
        self.group_host.setFixedHeight(28)
        self._group_layout = QHBoxLayout(self.group_host)
        self._group_layout.setContentsMargins(0, 0, 0, 0)
        self._group_layout.setSpacing(2)
        self.group_combo = ComboBox(self.group_host)
        self.group_combo.setAccessibleName('时刻表星期选择')
        self.group_combo.setFixedHeight(28)
        self.group_combo.setStyleSheet(
            f'ComboBox {{font-family: "{tokens.FONT_FAMILY}"; color: {tokens.TEXT_SECONDARY}; '
            f'font-size: {tokens.FONT_SIZE_CAPTION}px;}}')
        self.group_combo.currentIndexChanged.connect(self._combo_changed)
        self._group_layout.addWidget(self.group_combo)
        self._group_layout.addStretch()
        self.group_host.setMinimumWidth(0)
        self.group_host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        heading.insertWidget(2,self.group_host,1)

        summary_host = QWidget(self)
        self.summary_host = summary_host
        summary_host.setFixedHeight(40)
        summary_layout = QGridLayout(summary_host)
        self._summary_layout = summary_layout
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setHorizontalSpacing(0)
        summary_layout.setVerticalSpacing(tokens.CONTROL_GAP)
        self.summary_values = {}
        self.summary_labels = {}
        self._summary_tiles = {}
        for index, (key, title) in enumerate([
                ('first', '首班'), ('last', '末班'), ('count', '日发班'),
                ('morning_peak', '早高峰平均间隔'), ('evening_peak', '晚高峰平均间隔'),
                ('offpeak', '平峰平均间隔'), ('night', '夜间平均间隔')]):
            host = QWidget(summary_host)
            host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            box = QVBoxLayout(host)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(tokens.SPACE_XS)
            label = QLabel(title, host)
            label.setObjectName('cardLabel')
            label.setStyleSheet(
                f'font-family: "{tokens.FONT_FAMILY}"; color: {tokens.TEXT_SECONDARY}; '
                f'font-size: {tokens.FONT_SIZE_CAPTION}px;')
            label.setFixedHeight(16)
            value = QLabel('—', host)
            value.setFixedHeight(20)
            value.setStyleSheet(f'{emphasis_css(tokens.FONT_SIZE_BODY)}color: {tokens.TEXT_PRIMARY};')
            apply_emphasis_font(value, tokens.FONT_SIZE_BODY)
            box.addWidget(label)
            box.addWidget(value)
            self.summary_values[key] = value
            self.summary_labels[key] = label
            self._summary_tiles[key] = host
            column, span = self.SUMMARY_TRACKS[key]
            summary_layout.addWidget(host, 0, column, 1, span)
        for column in range(10):
            summary_layout.setColumnStretch(column, 1)
        self.count_label = self.summary_values['count']
        self._layout.addWidget(summary_host)

        self.matrix_scroll = StatisticsScrollArea(self)
        self.matrix_scroll.setObjectName('scheduleScroll')
        self.matrix_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.matrix_scroll.setWidgetResizable(True)
        self.matrix_scroll.setMinimumHeight(280)
        self.matrix_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.matrix_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.matrix_scroll.setStyleSheet('QScrollArea#scheduleScroll {background: white; border: 0;}')
        self.matrix = ScheduleMatrix()
        self.matrix._scroll = self.matrix_scroll
        self.matrix_scroll.setWidget(self.matrix)
        self.matrix.geometryChanged.connect(self._fit_matrix)
        self.matrix_scroll.verticalScrollBar().valueChanged.connect(self._update_display)
        self.matrix_scroll.verticalScrollBar().valueChanged.connect(lambda _value: self.matrix._hide_tooltip())
        self.matrix_scroll.viewport().installEventFilter(self)
        self._layout.addWidget(self.matrix_scroll, 1)

        self.footer_host=QWidget(self)
        self.footer_host.setMinimumWidth(0)
        self.footer_host.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
        self.footer_host.setFixedHeight(18)
        footer = QGridLayout(self.footer_host)
        self._footer_layout=footer
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        self.legend_label = QLabel(self)
        self.legend_label.setTextFormat(Qt.TextFormat.RichText)
        self.legend_label.setText(' · '.join(
            f'<span style="color:{color}">{name}</span>'
            for name, color in VEHICLE_COLORS.items()))
        self.legend_label.setAccessibleName('车型颜色图例：任意、小型、中型、大型')
        self.legend_label.setStyleSheet(f'font-family: "{tokens.FONT_FAMILY}"; '
                                       f'font-size: {tokens.FONT_SIZE_CAPTION}px;')
        self.legend_label.setFixedHeight(18)
        footer.addWidget(self.legend_label,0,0)
        self.period_legend=QWidget(self)
        self.period_legend.setAccessibleName('时段底色图例：早高峰、晚高峰、夜间、次日')
        period_row=QHBoxLayout(self.period_legend)
        period_row.setContentsMargins(0,0,0,0); period_row.setSpacing(8)
        self.period_swatches={}
        for key,name in [('morning_peak','早高峰'),('evening_peak','晚高峰'),('night','夜间'),('next_day','次日')]:
            item=QWidget(self.period_legend); row=QHBoxLayout(item)
            row.setContentsMargins(0,0,0,0); row.setSpacing(4)
            swatch=QLabel(item); swatch.setFixedSize(12,12)
            swatch.setStyleSheet(f'background:{PERIOD_COLORS[key]};border:1px solid {tokens.BORDER};border-radius:2px;')
            label=QLabel(name,item)
            label.setStyleSheet(f'font-family:"{tokens.FONT_FAMILY}";font-size:{tokens.FONT_SIZE_CAPTION}px;color:{tokens.TEXT_SECONDARY};')
            row.addWidget(swatch); row.addWidget(label); period_row.addWidget(item)
            self.period_swatches[key]=swatch
        self.period_legend.setFixedHeight(18)
        footer.addWidget(self.period_legend,0,1)
        footer.setColumnStretch(2,1)
        self.display_label = QLabel('显示 0 / 0', self)
        self.display_label.setObjectName('muted')
        self.display_label.setStyleSheet(f'font-family: "{tokens.FONT_FAMILY}"; '
                                        f'color: {tokens.TEXT_SECONDARY}; font-size: {tokens.FONT_SIZE_CAPTION}px;')
        footer.addWidget(self.display_label,0,3)
        self._layout.addWidget(self.footer_host)
        self.group_host.installEventFilter(self)
        self.clear()

    def minimumSizeHint(self):
        return QSize(320, self.minimumHeight())

    def sizeHint(self):
        return QSize(904, self.minimumHeight())

    def _fit_matrix(self):
        overflow = len(self.matrix.entries) > self.matrix.capacity
        height = self.matrix.base_height if overflow else self.matrix.minimumHeight()
        self.matrix_scroll.setMaximumHeight(self.matrix.base_height if overflow else 16777215)
        self.matrix_scroll.setMinimumHeight(height)
        if self.expanded:
            margins = self._layout.contentsMargins()
            chrome = (margins.top() + margins.bottom() + 2 * self.frameWidth()
                      + self._heading_layout.sizeHint().height() + self.group_host.height()
                      + self.summary_host.height() + self.footer_host.height()
                      + self._layout.spacing() * (self._layout.count() - 1))
        else:
            chrome = 146 + self.summary_host.height() - 40 + self.footer_host.height() - 18
        self.setMinimumHeight(chrome + height)
        self._update_display()

    def _update_expansion_button(self):
        text = '显示线路数据' if self.expanded else '展开时刻表'
        icon = FluentIcon.CHEVRON_DOWN_MED if self.expanded else FluentIcon.FULL_SCREEN
        self.expansion_button.setIcon(icon.icon(color=QColor(tokens.TEXT_SECONDARY)))
        self.expansion_button.setToolTip(text)
        self.expansion_button.setAccessibleName(text)

    @Slot()
    def _request_expansion(self):
        self.expansionRequested.emit(not self.expanded)

    def set_expanded(self, expanded):
        expanded = bool(expanded)
        if self.expanded == expanded:
            return
        self.expanded = expanded
        if expanded:
            self._heading_layout.removeWidget(self.group_host)
            self._layout.insertWidget(1, self.group_host)
        else:
            self._layout.removeWidget(self.group_host)
            self._heading_layout.insertWidget(2, self.group_host, 1)
        self.group_host.setFixedHeight(36 if expanded else 28)
        self.title_label.setFixedHeight(36 if expanded else 24)
        title_size = 18 if expanded else tokens.FONT_SIZE_CHART_TITLE
        self.title_label.setStyleSheet(f'{emphasis_css(title_size)}color: {tokens.TEXT_PRIMARY};')
        apply_emphasis_font(self.title_label, title_size)
        padding = 20 if expanded else tokens.CARD_PADDING
        self._layout.setContentsMargins(padding, padding, padding, padding)
        self._layout.setSpacing(12 if expanded else tokens.CONTROL_GAP)
        self._fit_footer()
        self.matrix.set_expanded(expanded)
        value_size = tokens.FONT_SIZE_KPI if expanded else tokens.FONT_SIZE_BODY
        for value in self.summary_values.values():
            value.setFixedHeight(28 if expanded else 20)
            value.setStyleSheet(f'{emphasis_css(value_size)}color: {tokens.TEXT_PRIMARY};')
            apply_emphasis_font(value, value_size)
            value.ensurePolished()
        self._fit_summary()
        self._update_expansion_button()
        self._update_overflow()
        self.matrix_scroll.verticalScrollBar().setValue(0)
        self._layout.activate()
        self._update_display()

    def _update_overflow(self):
        total = len(self.matrix.entries)
        overflow = total > self.matrix.capacity
        self.overflow_label.setText('超过 200 班 · 滚动查看全部' if total > 200 else '')
        self.overflow_label.setVisible(total > 200)
        self.matrix_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded if overflow else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _update_display(self, *args):
        self.display_label.setText(f'显示 {self.matrix.display_count} / {self.matrix.total_count}')

    def eventFilter(self, watched, event):
        if watched is getattr(self,'group_host',None) and event.type() == QEvent.Type.Resize:
            self._fit_group_control()
        scroll = getattr(self, 'matrix_scroll', None)
        if (scroll is not None and watched is scroll.viewport()
                and event.type() == QEvent.Type.Resize and hasattr(self, 'display_label')):
            self._update_display()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self,'display_label'):
            self._fit_footer()
            self._fit_matrix()
        self._fit_group_control()
        self._fit_summary()

    def _fit_footer(self):
        required = sum(widget.sizeHint().width() for widget in
                       (self.legend_label, self.period_legend, self.display_label)) + 32
        margins = self._layout.contentsMargins()
        available = self.width() - 2 * self.frameWidth() - margins.left() - margins.right()
        narrow = available < required
        self._footer_layout.removeWidget(self.period_legend)
        self._footer_layout.addWidget(self.period_legend, 1 if narrow else 0, 0 if narrow else 1,
                                      1, 4 if narrow else 1)
        self.footer_host.setFixedHeight(44 if narrow else 24 if self.expanded else 18)

    def _fit_summary(self):
        margins = self._layout.contentsMargins()
        available = self.width() - 2 * self.frameWidth() - margins.left() - margins.right()
        night_width = self.summary_labels['night'].fontMetrics().horizontalAdvance('夜间平均间隔')
        if self.expanded:
            required = max(night_width, self.summary_labels['morning_peak'].fontMetrics().horizontalAdvance('早高峰平均间隔'),
                           *(value.fontMetrics().horizontalAdvance(value.text()) for value in self.summary_values.values()))
            aligned = available // 7 >= required
        else:
            aligned = available // 10 >= night_width
        self._summary_layout.setHorizontalSpacing(0 if aligned else tokens.CONTROL_GAP)
        columns = (7 if self.expanded else 10) if aligned else 3
        for column in range(10):
            self._summary_layout.setColumnStretch(column, 1 if column < columns else 0)
        for index, host in enumerate(self._summary_tiles.values()):
            self._summary_layout.removeWidget(host)
            if aligned:
                key = tuple(self._summary_tiles)[index]
                column, span = (index, 1) if self.expanded else self.SUMMARY_TRACKS[key]
                self._summary_layout.addWidget(host, 0, column, 1, span)
            else:
                self._summary_layout.addWidget(host, index // columns, index % columns)
        rows = 1 if aligned else ceil(len(self._summary_tiles) / columns)
        row_height = 48 if self.expanded else 40
        padding = 8 if self.expanded else 0
        self._summary_layout.setContentsMargins(0, padding, 0, padding)
        self.summary_host.setFixedHeight(rows * row_height + (rows - 1) * tokens.CONTROL_GAP + 2 * padding)
        for key, title in {'morning_peak': '早高峰', 'evening_peak': '晚高峰',
                           'offpeak': '平峰', 'night': '夜间'}.items():
            self.summary_labels[key].setText(title + ('平均间隔' if aligned else '间隔'))
        self._fit_matrix()

    def _fit_group_control(self):
        width = self.group_control.sizeHint().width() if self.group_control is not None else 0
        use_combo = width > self.group_host.width()
        self.group_combo.setVisible(use_combo and bool(self.day_groups))
        if self.group_control is not None:
            self.group_control.setVisible(not use_combo)

    def _combo_changed(self, index):
        if 0 <= index < len(self.day_groups):
            self.set_current_group(self.day_groups[index])

    def _rebuild_groups(self):
        if self.group_control is not None:
            self._group_layout.removeWidget(self.group_control)
            self.group_control.hide()
            self.group_control.deleteLater()
            self.group_control = None
        self.group_buttons = {}
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItems(list(self.day_groups))
        self.group_combo.blockSignals(False)
        if self.day_groups:
            self.group_control = FluentSegmentedControl(self.group_host, compact=True, dense=True)
            for group in self.day_groups:
                self.group_control.addItem(group, group)
            self.group_control.currentKeyChanged.connect(self.set_current_group)
            self.group_buttons = dict(zip(self.day_groups, self.group_control.findChildren(TogglePushButton)))
            self._group_layout.insertWidget(0, self.group_control)
        self._fit_group_control()

    def set_line(self, line):
        self._line = line or {}
        groups = self._line.get('班次') or {}
        if not isinstance(groups, Mapping):
            groups = {}
        declared_groups = self._line.get('日组')
        self.day_groups = (tuple(group for group in declared_groups if group in groups)
                           if declared_groups is not None else tuple(groups))
        prepared = self._line.get('时刻表') or {}
        self._schedules = {
            group: prepared[group] if group in prepared and self.period_rules is None
            else prepare_schedule(groups[group] or [], self.period_rules)
            for group in self.day_groups}
        previous = self.current_group
        self.current_group = None
        self._rebuild_groups()
        if self.day_groups:
            self.set_current_group(previous if previous in self.day_groups else self.day_groups[0])
        else:
            self._show_summary(prepare_schedule([], self.period_rules))

    def set_current_group(self, group):
        if group not in self._schedules:
            raise KeyError(group)
        if self.current_group == group:
            return
        self.current_group = group
        self.group_control.blockSignals(True)
        self.group_control.setCurrentKey(group)
        self.group_control.blockSignals(False)
        self.group_combo.blockSignals(True)
        self.group_combo.setCurrentIndex(self.day_groups.index(group))
        self.group_combo.blockSignals(False)
        self._show_summary(self._schedules[group])
        self.currentGroupChanged.emit(group)

    def _show_summary(self, summary):
        self.summary = summary
        for key, label in self.summary_values.items():
            value = summary.get(key)
            label.setText(f'{value} 班' if key == 'count' else str(value) if value not in (None, '') else '—')
            tooltip = summary.get(f'{key}_tooltip') or (summary.get('service_text', '')
                                                       if key in ('first', 'last') else '')
            label.setToolTip(tooltip)
            self.summary_labels[key].setToolTip(tooltip)
            label.setAccessibleName(f'{self.summary_labels[key].text()}：{label.text()}')
        # Resolve the viewport before entries derive row count, including hidden pages.
        self._layout.activate()
        self.matrix.set_entries(summary['entries'])
        self._fit_summary()
        self._update_overflow()
        self.matrix_scroll.verticalScrollBar().setValue(0)
        self._update_display()

    def clear(self):
        self._line = {}
        self._schedules = {}
        self.day_groups = ()
        self.current_group = None
        self._rebuild_groups()
        self._show_summary(prepare_schedule([], self.period_rules))
