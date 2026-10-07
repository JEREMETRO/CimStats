"""Compact line query surfaces; the list may float over a stable detail pane."""
from PySide6.QtCore import Qt, QRect, QPropertyAnimation, QEasingCurve, QEvent, QObject, QTimer, Slot
from PySide6.QtGui import QAction, QPainter, QFont, QColor, QFontMetrics
import re
from decimal import Decimal
from display_rules import format_number, display_mode
from PySide6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QSizePolicy, QHeaderView, QTableWidget, QFrame, QStyle, QStyleOptionButton,
    QStyleOptionViewItem, QStyleOptionHeader, QToolTip)
from qfluentwidgets import (CardWidget, CheckableMenu, DropDownPushButton,
    LineEdit, ComboBox, TableWidget, TableItemDelegate, TransparentToolButton, FluentIcon, IconWidget, setCustomStyleSheet)
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
TABLE_TEXT_PADDING = 16
# QStyledItemDelegate's text/focus margin adds 3 px inside the Fluent inset.
# Do not query its stylesheet proxy's item metrics: it can crash this Qt build.
TABLE_TEXT_INSET = TABLE_TEXT_PADDING + 3
# Qt reserves another focus margin when deciding whether to elide numeric
# text. Include it in width measurement as well as the painted text inset.
TABLE_CONTENT_MARGIN = 2 * TABLE_TEXT_INSET + 6


def _column_alignment(column):
    return (Qt.AlignmentFlag.AlignLeft if column < 3 else Qt.AlignmentFlag.AlignRight) | Qt.AlignmentFlag.AlignVCenter


class LineTableDelegate(TableItemDelegate):
    """Preserve Fluent selection/hover painting with explicit text anchors."""
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = _column_alignment(index.column())


class LineTableHeader(QHeaderView):
    """Match the cell's text inset, independent of section position/sort state."""
    def __init__(self, parent):
        super().__init__(Qt.Orientation.Horizontal, parent)

    def paintSection(self, painter, rect, logical_index):
        option = QStyleOptionHeader()
        self.initStyleOptionForIndex(option, logical_index)
        option.rect = rect
        text = option.text
        option.text = ''
        painter.save()
        painter.setClipRect(rect)
        self.style().drawControl(QStyle.ControlElement.CE_HeaderSection, option, painter, self)
        inset = TABLE_TEXT_INSET
        text_rect = rect.adjusted(inset, 0, -inset, 0)
        numeric = logical_index >= 3
        if self.isSortIndicatorShown() and self.sortIndicatorSection() == logical_index:
            # Put the arrow on the opposite edge from the text anchor; sorting
            # never displaces the right edge of a numeric column's glyphs.
            arrow = QStyleOptionHeader(option)
            arrow.rect = QRect(rect.left() + 4 if numeric else rect.right() - 12,
                               rect.center().y() - 4, 8, 8)
            self.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorHeaderArrow,
                                      arrow, painter, self)
        painter.setFont(self.font())
        painter.setPen(QColor(tokens.TEXT_SECONDARY))
        text = self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, max(0, text_rect.width()))
        painter.drawText(text_rect, _column_alignment(logical_index), text)
        painter.restore()


class LineFilterComboBox(ComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentIndexChanged.connect(self._refresh_tooltip)

    def _refresh_tooltip(self, *_):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        rect = self.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, option, self)
        self.setToolTip(self.currentText() if self.fontMetrics().horizontalAdvance(self.currentText()) > rect.width() else '')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_tooltip()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.ApplicationFontChange):
            self._refresh_tooltip()


class ElisionOnlyTableTooltips(QObject):
    def __init__(self, table):
        super().__init__(table)
        self.table = table

    def eventFilter(self, watched, event):
        if event.type() != QEvent.Type.ToolTip:
            return False
        index = self.table.indexAt(event.pos())
        if not index.isValid():
            return False
        option = QStyleOptionViewItem()
        self.table.initViewItemOption(option)
        option.widget = self.table
        delegate = self.table.itemDelegateForIndex(index)
        delegate.initStyleOption(option, index)
        option.rect = self.table.visualRect(index)
        # Fluent TABLE_VIEW gives plain text cells 16 px padding on each side.
        # Querying SE_ItemViewItemText through its stylesheet proxy can crash Qt.
        rect = option.rect.adjusted(16, 0, -16, 0)
        rect = rect.intersected(self.table.viewport().rect())
        if QFontMetrics(option.font).horizontalAdvance(option.text) <= rect.width():
            delegate.tooltipDelegate.hideToolTip()
            QToolTip.hideText()
            return True
        return False


def shown(value, unit=''):
    if value is None or value == '':
        return '—'
    if isinstance(value, (int, float, Decimal)):
        text = format_number(value)
    else:
        text = str(value)
    return text + ((' ' + unit) if unit else '')


def _numbered_line_name(line):
    """Recognize whole numbered templates only, never digits inside a custom name."""
    mode = display_mode(line.get('运输制式', ''))
    name = str(line.get('线路名称') or '').strip()
    if not name:
        number = line.get('线路号')
        name = str(number) if number is not None and number != '' else ''
    raw_mode = str(line.get('运输制式') or '').strip()
    prefixes = {mode, raw_mode}
    if mode == '单轨':
        prefixes.add('单轨列车')
    prefix = next((value for value in sorted(prefixes, key=len, reverse=True)
                   if value and name.startswith(value)), '')
    candidate = name[len(prefix):].strip() if prefix else name
    match = re.fullmatch(r'(\d+[A-Za-z]?)(路|号线)?', candidate)
    return mode, name, match.groups() if match else None


def _line_company_identity(line):
    identity = line.get('公司标识')
    if identity is not None and identity != '':
        return ('id', str(identity))
    return ('name', str(line.get('原始公司名称') or line.get('公司名称') or ''))


def line_query_name(line, all_lines=None):
    """Display-only numbering within the complete save's company context.

    Keep the source dictionary and the shared workbook formatter untouched.
    A filtered subset must not replace ``all_lines`` when checking collisions.
    """
    mode, original, numbered = _numbered_line_name(line)
    if numbered is None:
        return original
    identifier, suffix = numbered
    if mode == '公交':
        # Letter route codes already carry their established identity, e.g. 812E.
        return identifier if not identifier.isdigit() and suffix is None else identifier + '路'
    known_modes = {'有轨电车', '无轨电车', '地铁', '单轨', '水上巴士'}
    if mode not in known_modes:
        return original
    company = _line_company_identity(line)
    collision = False
    for other in all_lines or ():
        if _line_company_identity(other) != company:
            continue
        other_mode, _, other_numbered = _numbered_line_name(other)
        if (other_numbered is not None and other_mode != mode
                and other_mode in known_modes | {'公交'}
                and other_numbered[0].casefold() == identifier.casefold()):
            collision = True
            break
    if collision:
        return mode + identifier + '号线'
    if mode in ('地铁', '单轨') and identifier.isdigit():
        return identifier + '号线'
    return identifier + (suffix or ('路' if identifier.isdigit() else ''))


def line_display_value(line, key, all_lines=None):
    availability = line.get('字段可用性') or {}
    if availability.get(key) is False:
        return None
    if key in ('核定速度', '今日平均车公里人次') and availability.get('地图里程') is False:
        return None
    if key in ('当日发班数', '今日平均单班人次', '今日平均车公里人次') and line.get('班次数据完整', True) is False:
        return None
    if key == '线路名称' and all_lines is not None:
        return line_query_name(line, all_lines)
    return line.get(key)


class FullTextLabel(QLabel):
    """Reveal clipped text without replacing dedicated explanatory tooltips."""
    def __init__(self, text='', parent=None):
        self._explicit_tooltip = None
        super().__init__(text, parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setAccessibleName(text)
        self._refresh_tooltip()

    def setText(self, text):
        super().setText(text)
        self.setAccessibleName(text)
        self._refresh_tooltip()

    def setToolTip(self, text):
        self._explicit_tooltip = text
        self._refresh_tooltip()

    def _is_clipped(self):
        return self.fontMetrics().horizontalAdvance(self.text()) > self.contentsRect().width()

    def _refresh_tooltip(self):
        tip = self._explicit_tooltip
        if tip is None:
            tip = self.text() if self._is_clipped() else ''
        QLabel.setToolTip(self, tip)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_tooltip()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.ApplicationFontChange):
            self._refresh_tooltip()

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

    def _is_clipped(self):
        match = re.fullmatch(r'(.*?) (km/h|km|min|班|辆|人次)', self.text())
        if not match:
            return super()._is_clipped()
        number, unit = match.groups()
        width = self.fontMetrics().horizontalAdvance(number) + 6 + QFontMetrics(self.unit_font()).horizontalAdvance(unit)
        return width > self.contentsRect().width()

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


class WrappedFactLabel(FullTextLabel):
    def _is_clipped(self):
        rect = self.contentsRect()
        bounds = self.fontMetrics().boundingRect(
            rect, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft, self.text())
        return bounds.height() > rect.height() or bounds.width() > rect.width()

    def paintEvent(self, event):
        QLabel.paintEvent(self, event)


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
        self.value = (WrappedFactLabel(shown(primary[1]), self) if garage else
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
        self.value.setAccessibleName(shown(primary[1]))
        self.note_value.setText(shown(alternate[1]) if alternate else '')
        if tooltip:
            self.note_label.setToolTip(tooltip); self.note_value.setToolTip(tooltip)
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
        self.line_company = LineFilterComboBox(self.left); self.line_company.setMinimumWidth(0)
        self.line_company.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.line_mode = LineFilterComboBox(self.left); self.line_mode.setMinimumWidth(0)
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
        self.line_table.setHorizontalHeader(LineTableHeader(self.line_table))
        old_delegate = self.line_table.itemDelegate()
        self.line_table.setItemDelegate(LineTableDelegate(self.line_table))
        old_delegate.deleteLater()
        self._table_tooltips = ElisionOnlyTableTooltips(self.line_table)
        self.line_table.viewport().installEventFilter(self._table_tooltips)
        self.line_table.setColumnCount(len(HEADERS)); self.line_table.setHorizontalHeaderLabels(HEADERS)
        for column, text in enumerate(HEADERS):
            self.line_table.horizontalHeaderItem(column).setToolTip(text)
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
                       f'QTableView#lineTable::item {{padding-left: {TABLE_TEXT_PADDING}px; padding-right: {TABLE_TEXT_PADDING}px;}}')
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
        self._content_widths = {}
        self._sizing_columns = False
        self._column_fit_timer = QTimer(self)
        self._column_fit_timer.setSingleShot(True)
        self._column_fit_timer.timeout.connect(self._fit_content_columns)
        for signal in (self.line_table.model().dataChanged,
                       self.line_table.model().rowsInserted,
                       self.line_table.model().rowsRemoved,
                       self.line_table.model().modelReset):
            signal.connect(self._queue_content_fit)
        header.sectionResized.connect(self._keep_content_width)
        self.left.installEventFilter(self)
        self._fit_filters()
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
        if not getattr(self, '_column_widths_initialized', False):
            widths = [135,64,84,72,72,96,108,98,52,76,112,98,116,136]
            self._column_widths = dict(enumerate(widths))
            for i, width in enumerate(widths):
                self.line_table.setColumnWidth(i, width)
            self._column_widths_initialized = True
        # Tail space stays blank. Interactive widths/order remain the user's
        # choices through expand, resize and visibility changes.
        self.line_table.horizontalHeader().setStretchLastSection(False)

    @Slot()
    def _queue_content_fit(self):
        self._column_fit_timer.start(0)

    def _fit_content_columns(self):
        """Values stay complete; captions may elide and expose their tooltip."""
        table = self.line_table
        self._sizing_columns = True
        try:
            for column in range(table.columnCount()):
                width = 42
                for row in range(table.rowCount()):
                    item = table.item(row, column)
                    if item is not None:
                        font = item.data(Qt.ItemDataRole.FontRole) or table.font()
                        width = max(width, QFontMetrics(font).horizontalAdvance(item.text()) + TABLE_CONTENT_MARGIN)
                self._content_widths[column] = width
                # Keep larger user widths; visibility/sort changes never reset
                # them. Hidden sections get the same complete-content budget.
                if table.isColumnHidden(column):
                    target = max(width, self._column_widths[column])
                    table.setColumnWidth(column, target)
                    self._column_widths[column] = target
                elif table.columnWidth(column) < width:
                    table.setColumnWidth(column, width)
                    self._column_widths[column] = width
        finally:
            self._sizing_columns = False

    def _keep_content_width(self, column, old_size, new_size):
        if self._sizing_columns:
            return
        if new_size == 0:
            if old_size > 0:
                self._column_widths[column] = old_size
            return
        minimum = self._content_widths.get(column, 42)
        if new_size < minimum:
            self._sizing_columns = True
            try:
                self.line_table.horizontalHeader().resizeSection(column, minimum)
            finally:
                self._sizing_columns = False
        self._column_widths[column] = max(minimum, new_size)

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
        if not self.expanded:
            self.line_table.horizontalScrollBar().setValue(0)

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
