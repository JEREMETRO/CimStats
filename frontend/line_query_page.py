"""Compact line query surfaces; the list may float over a stable detail pane."""
from PySide6.QtCore import Qt, QRect, QPropertyAnimation, QEasingCurve, QEvent
from PySide6.QtGui import QAction, QPainter, QFont, QColor, QFontMetrics
import re
from PySide6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QSizePolicy, QHeaderView, QTableWidget, QFrame)
from qfluentwidgets import (CardWidget, CheckableMenu, DropDownPushButton,
    LineEdit, ComboBox, TableWidget, TransparentToolButton, FluentIcon, IconWidget, setCustomStyleSheet)
from stats_motion import SurfaceMotion, CollapseMotion, animations_enabled
from stats_controls import StatisticsScrollArea, configure_fluent_table, SummaryToggleButton
from stats_elevation import attach_card_elevation
import stats_tokens as tokens
from stats_typography import emphasis_font, emphasis_css, apply_emphasis_font

HEADERS = ['公司', '制式', '线路名称', '地图 km', '折算 km', '单程时间 min',
           '核定速度 km/h', '今日客流', '发班', '最大需求', '每周收入', '每周支出',
           '今日平均单班人次', '今日平均车公里人次']
CORE_COLUMNS = {2, 7, 8, 9, 10}
QUERY_COLUMNS = frozenset(range(len(HEADERS))) - {4}


def shown(value, unit=''):
    if value is None or value == '':
        return '—'
    if isinstance(value, int):
        text = f'{value:,}'
    elif isinstance(value, float):
        text = f'{value:,.2f}'
    else:
        text = str(value)
    return text + ((' ' + unit) if unit else '')


def line_display_value(line, key):
    availability = line.get('字段可用性') or {}
    if availability.get(key) is False:
        return None
    if key in ('核定速度', '今日平均车公里人次') and availability.get('地图里程') is False:
        return None
    if key in ('当日发班数', '今日平均单班人次', '今日平均车公里人次') and line.get('班次数据完整', True) is False:
        return None
    return line.get(key)


class FullTextLabel(QLabel):
    """Elide only paint; tooltip and assistive technologies retain the full value."""
    def __init__(self, text='', parent=None):
        super().__init__(text, parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text):
        super().setText(text)
        self.setToolTip(text)
        self.setAccessibleName(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(self.contentsRect(), self.alignment(), self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideRight, self.contentsRect().width()))


class SelectionSummaryLabel(FullTextLabel):
    def setText(self, text):
        _, separator, selected = str(text).partition('    选中：')
        super().setText('选中：' + selected if separator else str(text))


class MetricValueLabel(FullTextLabel):
    """Keep the complete value while painting its unit at the KPI caption size."""
    def unit_font(self):
        return emphasis_font(tokens.FONT_SIZE_CAPTION, QFont.Weight.DemiBold)

    def paintEvent(self,event):
        match=re.fullmatch(r'(.*?) (km/h|km|min|班|辆|人次)',self.text())
        if not match:
            return super().paintEvent(event)
        number,unit=match.groups()
        painter=QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        font=self.font(); metrics=QFontMetrics(font)
        unit_font=self.unit_font(); unit_metrics=QFontMetrics(unit_font)
        rect=self.contentsRect(); gap=6
        number=metrics.elidedText(number,Qt.TextElideMode.ElideRight,
                                 max(0,rect.width()-gap-unit_metrics.horizontalAdvance(unit)))
        baseline=rect.y()+(rect.height()-metrics.height())//2+metrics.ascent()
        painter.setFont(font); painter.drawText(rect.x(),baseline,number)
        painter.setFont(unit_font)
        painter.setPen(QColor(tokens.TEXT_SECONDARY))
        painter.drawText(rect.x()+metrics.horizontalAdvance(number)+gap,baseline,unit)


class CompactFactCard(QFrame):
    ICONS = {
        '线路车库': FluentIcon.HOME,
        '开线日期': FluentIcon.CALENDAR,
        '地图里程': FluentIcon.PIE_SINGLE,
        '单程时间': FluentIcon.HISTORY,
        '当日发班数': FluentIcon.BUS,
        '理论最大车辆需求数': FluentIcon.CAR,
        '今日客流': FluentIcon.PEOPLE,
        '今日平均单班人次': FluentIcon.PIE_SINGLE,
        '每周收入': FluentIcon.MARKET,
    }
    def __init__(self, primary, alternate=None, parent=None, tooltip=''):
        super().__init__(parent)
        self.setObjectName('lineFactCard')
        attach_card_elevation(self, radius=tokens.RADIUS_KPI)
        self.setStyleSheet(f'QFrame#lineFactCard {{background:{tokens.CARD_BG};border:1px solid {tokens.BORDER};border-radius:{tokens.RADIUS_KPI}px;}}')
        self.setFixedHeight(86)
        self.setMinimumWidth(0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(4)
        self.header_host = QWidget(self)
        self.header_host.setFixedHeight(18)
        header_row = QHBoxLayout(self.header_host); header_row.setContentsMargins(0,0,0,0); header_row.setSpacing(6)
        self.icon = IconWidget(self.header_host); self.icon.setFixedSize(18,18)
        self.icon.setIcon(self.ICONS.get(primary[0],FluentIcon.PIE_SINGLE).icon(color=QColor(tokens.DATA_COMPANY_COLORS[0])))
        self.label = FullTextLabel(str(primary[0]), self.header_host)
        header_row.addWidget(self.icon); header_row.addWidget(self.label,1)
        self.label.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};font-family:"{tokens.FONT_FAMILY}";font-size:{tokens.FONT_SIZE_CAPTION}px;')
        garage = primary[0] == '线路车库' and not alternate
        date = primary[0] == '开线日期'
        self.value = (QLabel(shown(primary[1]), self) if garage else
                      FullTextLabel(shown(primary[1]), self) if date else
                      MetricValueLabel(shown(primary[1]), self))
        if garage:
            self.value.setMinimumWidth(0)
            self.value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            self.value.setWordWrap(True)
            self.value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        if date:
            self.value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        value_size = 18 if primary[0] in ('线路车库','开线日期') else tokens.FONT_SIZE_KPI
        self.value.setStyleSheet(f'color:{tokens.TEXT_PRIMARY};{emphasis_css(value_size)}')
        apply_emphasis_font(self.value, value_size)
        self.note_label = FullTextLabel(str(alternate[0]) if alternate else '', self)
        self.note_label.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};font-family:"{tokens.FONT_FAMILY}";font-size:{tokens.FONT_SIZE_CAPTION}px;')
        self.note_value = FullTextLabel(shown(alternate[1]) if alternate else '', self)
        self.note_value.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};font-family:"{tokens.FONT_FAMILY}";font-size:{tokens.FONT_SIZE_CAPTION}px;')
        self.label.setFixedHeight(18); self.value.setFixedHeight(50 if garage else 28)
        self.note_label.setFixedHeight(18); self.note_value.setFixedHeight(18)
        self.note_value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        note = QHBoxLayout(); note.setSpacing(8)
        self.note_label.ensurePolished()
        self.note_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.note_label.setFixedWidth(self.note_label.fontMetrics().horizontalAdvance(self.note_label.text()))
        note.addWidget(self.note_label); note.addWidget(self.note_value, 1)
        layout.addWidget(self.header_host); layout.addWidget(self.value)
        if garage:
            self.note_label.hide(); self.note_value.hide()
            self.note_label.setFixedSize(0,0); self.note_value.setFixedSize(0,0)
        else:
            layout.addLayout(note)
        self.value.setText(shown(primary[1]))
        self.value.setToolTip(shown(primary[1])); self.value.setAccessibleName(shown(primary[1]))
        self.note_value.setText(shown(alternate[1]) if alternate else '')
        if tooltip:
            self.setToolTip(tooltip); self.note_label.setToolTip(tooltip); self.note_value.setToolTip(tooltip)
        self.setAccessibleName('；'.join((str(primary[0])+' '+shown(primary[1]),
            str(alternate[0])+' '+shown(alternate[1]) if alternate else '')))


class LinesPage(QWidget):
    def __init__(self, owner, schedule_factory):
        super().__init__()
        self.owner = owner
        self.setObjectName('linesPage')
        self.setStyleSheet(f'QWidget#linesPage {{background:{tokens.PAGE_BG};}}')
        self.expanded = False
        self.schedule_expanded = False
        self._saved_columns = set(CORE_COLUMNS)
        self.left = QFrame(self); self.left.setObjectName('lineListCard')
        attach_card_elevation(self.left, radius=tokens.RADIUS_CARD)
        self.left.setStyleSheet(f'QFrame#lineListCard {{background:{tokens.CARD_BG};border:1px solid {tokens.BORDER};border-radius:{tokens.RADIUS_CARD}px;}}')
        self._animation = QPropertyAnimation(self.left, b'geometry', self)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.finished.connect(self._finish_motion)
        self.motion = SurfaceMotion(self)
        left_layout = QVBoxLayout(self.left)
        left_layout.setContentsMargins(12, 12, 12, 8); left_layout.setSpacing(8)
        search_row = QHBoxLayout(); search_row.setSpacing(6)
        self.query = LineEdit(self.left)
        self.query.setPlaceholderText('搜索线路号、公司、线路名称或制式')
        self.query.setFixedHeight(36); self.query.textChanged.connect(owner.refresh_lines)
        self.expand_button = TransparentToolButton(self.left)
        self.expand_button.setFixedSize(32, 32)
        self.expand_button.clicked.connect(lambda: self.set_expanded(not self.expanded))
        search_row.addWidget(self.query, 1); search_row.addWidget(self.expand_button)
        left_layout.addLayout(search_row)
        filters = QGridLayout(); filters.setContentsMargins(0,0,0,0); filters.setSpacing(6)
        self._filters_layout = filters
        self._filter_wrapped = None
        self.line_company = ComboBox(self.left); self.line_company.setMinimumWidth(0)
        self.line_company.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.line_mode = ComboBox(self.left); self.line_mode.setMinimumWidth(0)
        self.line_mode.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        for combo in (self.line_company, self.line_mode):
            combo.setFixedHeight(36); combo.currentIndexChanged.connect(owner.refresh_lines)
        self.line_columns_button = DropDownPushButton('显示列', self.left)
        self.line_columns_button.setFixedSize(max(92, self.line_columns_button.sizeHint().width()), 36)
        self.line_columns_menu = CheckableMenu(parent=self.line_columns_button)
        self.line_columns_button.setMenu(self.line_columns_menu)
        self.line_count = QLabel('0 条', self.left)
        self.line_count.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};font-family:"{tokens.FONT_FAMILY}";font-size:12px;')
        left_layout.addLayout(filters)
        self.line_table = TableWidget(self.left)
        self.line_table.setColumnCount(len(HEADERS)); self.line_table.setHorizontalHeaderLabels(HEADERS)
        self.line_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.line_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.line_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.line_table.setSortingEnabled(True); self.line_table.setWordWrap(False)
        self.line_table.setAlternatingRowColors(True); self.line_table.setShowGrid(False)
        self.line_table.verticalHeader().hide()
        self.line_table.verticalHeader().setDefaultSectionSize(30)
        self.line_table.verticalHeader().setMinimumSectionSize(28)
        configure_fluent_table(self.line_table, font_size=tokens.FONT_SIZE_BODY, header_font_size=tokens.FONT_SIZE_CAPTION)
        self.line_table.setObjectName('lineTable')
        table_style = (f'QTableView#lineTable {{font-family:"{tokens.FONT_FAMILY}";'
                       f'font-size:{tokens.FONT_SIZE_BODY}px;}} '
                       'QTableView#lineTable::item {padding-left: 6px; padding-right: 6px;}')
        setCustomStyleSheet(self.line_table, table_style, table_style)
        header = self.line_table.horizontalHeader()
        header.setMinimumSectionSize(42); header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionsMovable(True); header.setFixedHeight(32)
        for pos, column in enumerate([2,8,9,7,10,0,1,3,4,5,6,11,12,13]):
            header.moveSection(header.visualIndex(column), pos)
        self.column_actions = []
        for index, label in enumerate(HEADERS):
            if index not in QUERY_COLUMNS:
                continue
            action = QAction(label, self.line_columns_menu)
            action.setCheckable(True); action.setChecked(index in CORE_COLUMNS)
            if index == 2:
                action.setEnabled(False); action.setToolTip('线路身份列始终显示')
            action.toggled.connect(lambda checked, col=index: self._column_changed(col, checked))
            self.line_columns_menu.addAction(action); self.column_actions.append(action)
        self.line_table.cellClicked.connect(owner.line_clicked)
        self.line_table.itemSelectionChanged.connect(owner.line_selection_changed)
        left_layout.addWidget(self.line_table, 1)
        self.list_footer = SelectionSummaryLabel('从列表选择线路', self.left)
        self.list_footer.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};font-family:"{tokens.FONT_FAMILY}";font-size:12px;')
        list_footer_row = QHBoxLayout(); list_footer_row.setSpacing(8)
        list_footer_row.addWidget(self.list_footer,1); list_footer_row.addWidget(self.line_count)
        left_layout.addLayout(list_footer_row)
        self.right_scroll = StatisticsScrollArea(self)
        self.right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.right_host = QWidget()
        self.right_host.setMinimumWidth(620)
        right = QVBoxLayout(self.right_host); right.setContentsMargins(0,0,0,0); right.setSpacing(12)
        self.detail = QFrame(); self.detail.setObjectName('lineDetailCard'); self.detail.setMaximumHeight(348)
        attach_card_elevation(self.detail, radius=tokens.RADIUS_CARD)
        self.detail.setStyleSheet(f'QFrame#lineDetailCard {{background:{tokens.CARD_BG};border:1px solid {tokens.BORDER};border-radius:{tokens.RADIUS_CARD}px;}}')
        detail = QVBoxLayout(self.detail); detail.setContentsMargins(16,16,16,16); detail.setSpacing(8)
        head = QHBoxLayout(); head.setSpacing(8)
        self.detail_title = FullTextLabel('选择线路查看详情', self.detail)
        self.detail_title.setStyleSheet(f'{emphasis_css(18)}color:{tokens.TEXT_PRIMARY};')
        apply_emphasis_font(self.detail_title, 18)
        head.addWidget(self.detail_title, 1)
        self.fact_menu_button = DropDownPushButton('显示字段', self.detail)
        self.fact_menu_button.setFixedSize(max(104, self.fact_menu_button.sizeHint().width()),32)
        self.fact_menu = CheckableMenu(parent=self.fact_menu_button); self.fact_menu_button.setMenu(self.fact_menu)
        head.addWidget(self.fact_menu_button)
        self.fact_fold_button = SummaryToggleButton(self.detail)
        self.fact_fold_button.setToolTip('收起线路数据')
        self.fact_fold_button.setAccessibleName('收起线路数据')
        self.fact_fold_button.clicked.connect(lambda: self.set_schedule_expanded(not self.schedule_expanded))
        head.addWidget(self.fact_fold_button); detail.addLayout(head)
        self.facts_host = QWidget(); self.facts_grid = QGridLayout(self.facts_host)
        self.facts_grid.setContentsMargins(0,0,0,0); self.facts_grid.setSpacing(8)
        for i in range(3): self.facts_grid.setColumnStretch(i,1)
        detail.addWidget(self.facts_host, 1); right.addWidget(self.detail)
        self.schedule_panel = schedule_factory()
        self.schedule_panel.expansionRequested.connect(lambda _: self.set_schedule_expanded(not self.schedule_expanded))
        self.detail_motion = CollapseMotion(self.detail, self._finish_detail_motion)
        self.schedule_motion = SurfaceMotion(self.schedule_panel)
        right.addWidget(self.schedule_panel, 1)
        self.right_scroll.setWidget(self.right_host)
        self._apply_columns(); self._update_button()
        self.left.installEventFilter(self)
        self._fit_filters()
        for combo in (self.line_company, self.line_mode):
            combo.currentIndexChanged.connect(lambda _=0, control=combo: control.setToolTip(control.currentText()))
        self.installEventFilter(self)

    def _fit_filters(self):
        margins = self.left.layout().contentsMargins()
        available = self.left.width() - margins.left() - margins.right() - 2 * self.left.frameWidth()
        mode_width = max(100, self.line_mode.sizeHint().width())
        company_minimum = self.line_company.fontMetrics().horizontalAdvance('全部公司') + 44
        wrapped = available < company_minimum + mode_width + self.line_columns_button.width() + 12
        if wrapped == self._filter_wrapped:
            return
        self._filter_wrapped = wrapped
        for control in (self.line_company, self.line_mode, self.line_columns_button):
            self._filters_layout.removeWidget(control)
        self._filters_layout.setColumnStretch(0, 1)
        self._filters_layout.setColumnStretch(1, 0)
        self._filters_layout.setColumnStretch(2, 0)
        if wrapped:
            self.line_mode.setMinimumWidth(mode_width)
            self.line_mode.setMaximumWidth(16777215)
            self._filters_layout.addWidget(self.line_company, 0, 0, 1, 2)
            self._filters_layout.addWidget(self.line_mode, 1, 0)
            self._filters_layout.addWidget(self.line_columns_button, 1, 1)
        else:
            self.line_mode.setFixedWidth(mode_width)
            self._filters_layout.addWidget(self.line_company, 0, 0)
            self._filters_layout.addWidget(self.line_mode, 0, 1)
            self._filters_layout.addWidget(self.line_columns_button, 0, 2)

    def set_schedule_expanded(self, expanded, animated=True):
        expanded = bool(expanded)
        if expanded == self.schedule_expanded and self.detail_motion.animation is None:
            return
        self.schedule_expanded = expanded
        self.fact_fold_button.set_collapsed(expanded)
        action_text = '显示线路数据' if expanded else '收起线路数据'
        self.fact_fold_button.setToolTip(action_text)
        self.fact_fold_button.setAccessibleName(action_text)
        if not expanded:
            self.schedule_panel.set_expanded(False)
        if animated:
            self.detail_motion.set_collapsed(expanded)
        else:
            self.detail_motion.collapsed = expanded
            self.detail_motion.finish()

    def _finish_detail_motion(self):
        self.detail.setMaximumHeight(348 if not self.schedule_expanded else 16777215)
        self.schedule_panel.set_expanded(self.schedule_expanded)
        self.right_host.layout().invalidate()
        self.right_host.layout().activate()
        self.schedule_motion.reveal()

    def _column_changed(self, column, checked):
        if checked: self._saved_columns.add(column)
        else: self._saved_columns.discard(column)
        self._saved_columns.add(2)
        self._apply_columns()

    def _apply_columns(self):
        visible = QUERY_COLUMNS if self.expanded else self._saved_columns & QUERY_COLUMNS
        for i in range(len(HEADERS)): self.line_table.setColumnHidden(i, i not in visible)
        widths = ([135,64,84,72,72,96,108,90,52,76,98,98,116,136] if self.expanded
                  else [110,64,72,72,72,96,108,98,52,76,112,98,116,136])
        for i, width in enumerate(widths): self.line_table.setColumnWidth(i,width)
        self.line_table.horizontalHeader().setStretchLastSection(self.expanded)

    def _compact_width(self):
        return 436 if self.width() >= 1150 else (340 if self.width() >= 940 else 260)

    def _left_rect(self):
        return QRect(0,0,self.width() if self.expanded else self._compact_width(),self.height())

    def _update_button(self):
        text = '折叠线路列表' if self.expanded else '展开线路列表'
        self.expand_button.setIcon(FluentIcon.LEFT_ARROW if self.expanded else FluentIcon.CHEVRON_RIGHT)
        self.expand_button.setToolTip(text); self.expand_button.setAccessibleName(text)

    def set_expanded(self, expanded, animated=True):
        self.expanded=bool(expanded)
        self._animation.stop(); self._apply_columns(); self._update_button()
        self.left.raise_()
        if animated and animations_enabled() and self.isVisible():
            self._animation.setDuration(250 if self.expanded else 167)
            self._animation.setStartValue(self.left.geometry()); self._animation.setEndValue(self._left_rect())
            self._animation.start()
        else:
            self.left.setGeometry(self._left_rect()); self._finish_motion()

    def _finish_motion(self):
        self.left.setGeometry(self._left_rect())
        self._apply_columns()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._animation.stop()
        left = self._compact_width()
        self.right_scroll.setGeometry(left+12,0,max(0,self.width()-left-12),self.height())
        self.left.setGeometry(self._left_rect()); self.left.raise_()

    def hideEvent(self, event):
        self._animation.stop(); self.motion.finish(); self.schedule_motion.finish(); self.detail_motion.finish(); self._finish_motion()
        super().hideEvent(event)

    def eventFilter(self, obj, event):
        if obj is self.left and event.type() == QEvent.Type.Resize:
            self._fit_filters()
        if event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Escape and self.expanded:
            self.set_expanded(False); self.expand_button.setFocus(); return True
        if event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Escape and self.schedule_expanded:
            self.set_schedule_expanded(False); self.fact_fold_button.setFocus(); return True
        return super().eventFilter(obj,event)
