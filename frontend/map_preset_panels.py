"""Fluent preset panels; caller supplies native records and immutable facts."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite

from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QColor,QPixmap,QIcon
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CheckBox, LineEdit, PushButton, TransparentPushButton

from line_schedule import TICKS_PER_SECOND
from display_rules import format_number
from map_visibility import usable_paths as _usable_paths
from map_panels import _ChoiceGroup, _OptionGrid, _SingleLineList, _style_control
from display_rules import display_mode
from semantic_colors import color_for
from map_line_labels import resolve_line_labels
from stats_controls import StatisticsScrollArea
from stats_typography import ui_font
import stats_tokens as tokens


def _field(record, key, default=None):
    return record.get(key, default) if isinstance(record, Mapping) else getattr(record, key, default)


def _number(value, unit, precision=0):
    if value is None:
        return '—'
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return '—'
    if not isfinite(number) or number < 0:
        return '—'
    return f'{format_number(number, places=precision)} {unit}'


def _catalog(routes):
    """Normalize identity once per catalog, never infer building associations."""
    routes=tuple(routes or ())
    labels=resolve_line_labels(routes) if any(not (_field(r,'display_label') or _field(r,'label')) for r in routes) else {}
    result = []
    seen = set()
    for route in routes or ():
        identity = _field(route, 'id')
        if identity is None or identity in seen:
            continue
        seen.add(identity)
        has_paths = _field(route, 'paths')
        selectable = _field(route, 'selectable')
        if selectable is None:
            legs = _field(route, 'leg_paths', ())
            selectable = _usable_paths(tuple(path for leg in legs for path in leg) if legs else has_paths)
        result.append(dict(id=identity, name=str(_field(route, 'name', identity)),
                           company_id=_field(route, 'company_id'), company_name=str(_field(route, 'company_name', '') or ''),
                           mode=_field(route, 'mode'), color=_field(route, 'color'), selectable=bool(selectable),
                           display_label=_field(route,'display_label',_field(route,'label')) or labels.get(identity)))
    return result


def _label(layout, text, heading=False):
    label = _style_control(BodyLabel(text), tokens.FONT_SIZE_BODY if heading else tokens.FONT_SIZE_CAPTION,
                           tokens.TEXT_PRIMARY if heading else tokens.TEXT_SECONDARY)
    label.setWordWrap(True)
    if heading:
        label.setFont(ui_font(tokens.FONT_SIZE_BODY, 600))
    layout.addWidget(label)
    return label


def _section(layout):
    frame = QFrame(); frame.setObjectName('mapPresetSection')
    frame.setStyleSheet(f'QFrame#mapPresetSection {{background:{tokens.SURFACE_SUBTLE};border:0;border-radius:{tokens.RADIUS_CONTROL}px;}}')
    child = QVBoxLayout(frame); child.setContentsMargins(10, 8, 10, 8); child.setSpacing(6)
    layout.addWidget(frame)
    return child


class _PresetPanel(StatisticsScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True); self.setMinimumWidth(240)
        body = QWidget(); body.setFont(ui_font(tokens.FONT_SIZE_BODY))
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(12, 10, 12, 12); self.body_layout.setSpacing(8)
        self.setWidget(body)


class _RouteList(QWidget):
    changed = Signal(object)
    activated = Signal(object)

    def __init__(self, checked=True, parent=None):
        super().__init__(parent)
        self._checked = checked; self._routes = []; self._selected = set(); self._duplicate_companies = set()
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(6)
        self.search = _style_control(LineEdit()); self.search.setPlaceholderText('搜索线路'); self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName('搜索线路'); layout.addWidget(self.search)
        if checked:
            row = QHBoxLayout(); row.setSpacing(8)
            self.select_all = _style_control(PushButton('全选'))
            self.clear_selection = _style_control(PushButton('清空'))
            self.select_all.setEnabled(False); self.clear_selection.setEnabled(False)
            row.addWidget(self.select_all); row.addWidget(self.clear_selection); row.addStretch(1)
            layout.addLayout(row)
            self.select_all.clicked.connect(lambda: self._bulk(True))
            self.clear_selection.clicked.connect(lambda: self._bulk(False))
        self.line_list = _SingleLineList(); _style_control(self.line_list)
        self.line_list.setProperty('heightCap', 260); self.line_list.setFixedHeight(260)
        self.line_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.line_list)
        self.search.textChanged.connect(self._searched)
        self.search.returnPressed.connect(self._submit)
        self.search.installEventFilter(self)
        self.line_list.itemChanged.connect(self._item_changed)
        self.line_list.itemClicked.connect(self._activate)
        self.line_list.itemActivated.connect(self._activate)
        if not checked:self.line_list.hide()

    def _searched(self,*_):
        self.refresh()
        if not self._checked:self.line_list.show()

    def eventFilter(self,watched,event):
        if watched is self.search and not self._checked and event.type()==QEvent.Type.FocusIn:
            if event.reason() in (Qt.FocusReason.MouseFocusReason,Qt.FocusReason.TabFocusReason,Qt.FocusReason.BacktabFocusReason):
                self.line_list.show()
        return super().eventFilter(watched,event)

    def collapse_results(self):
        if not self._checked:self.line_list.hide()

    def _submit(self):
        available=[self.line_list.item(i) for i in range(self.line_list.count()) if self.line_list.item(i).flags()&Qt.ItemFlag.ItemIsEnabled]
        if len(available)==1:self._activate(available[0])
        else:
            self.line_list.show()
            if available:
                self.line_list.setCurrentItem(available[0]);self.line_list.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_routes(self, routes, selected, duplicate_companies=()):
        if routes == self._routes and set(duplicate_companies) == self._duplicate_companies:
            self.set_selection(selected); return
        self._routes = routes; self._selected = set(selected)
        self._duplicate_companies = set(duplicate_companies); self.refresh()

    def set_selection(self, selected):
        if set(selected) == self._selected: return
        self._selected = set(selected)
        blocked = self.line_list.blockSignals(True)
        try:
            matched=False
            for i in range(self.line_list.count()):
                item = self.line_list.item(i)
                if self._checked and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole) in self._selected else Qt.CheckState.Unchecked)
                elif not self._checked and item.data(Qt.ItemDataRole.UserRole) in self._selected:
                    self.line_list.setCurrentItem(item);matched=True
            if not self._checked and not matched:self.line_list.setCurrentRow(-1)
        finally:
            self.line_list.blockSignals(blocked)

    def refresh(self, *_):
        query = self.search.text().strip().casefold()
        blocked = self.line_list.blockSignals(True)
        self.line_list.clear()
        for route in self._routes:
            text=route.get('display_label') or f"{display_mode(route.get('mode'))} {route['name']}".strip()
            if query and query not in f"{text} {route['id']} {route['company_name']}".casefold():
                continue
            item = QListWidgetItem(text); item.setData(Qt.ItemDataRole.UserRole, route['id'])
            color=route.get('color') or color_for('mode',route.get('mode'))
            pix=QPixmap(10,10);pix.fill(QColor(color));item.setIcon(QIcon(pix))
            item.setFont(ui_font(tokens.FONT_SIZE_BODY)); item.setToolTip('')
            if not route['selectable']:
                item.setData(Qt.ItemDataRole.AccessibleDescriptionRole,route.get('unavailable_text','无地图路径'))
            item.setForeground(QColor(tokens.TEXT_PRIMARY if route['selectable'] else tokens.TEXT_DISABLED))
            if self._checked and route['selectable']:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if route['id'] in self._selected else Qt.CheckState.Unchecked)
            elif not route['selectable']:
                item.setFlags(item.flags() & ~(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable))
            self.line_list.addItem(item)
            if not self._checked and route['id'] in self._selected:
                self.line_list.setCurrentItem(item)
        self.line_list.wrap_items(); self.line_list.blockSignals(blocked)
        if self._checked:
            available = bool(self._visible_ids())
            self.select_all.setEnabled(available); self.clear_selection.setEnabled(available)

    def _visible_ids(self):
        return {self.line_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.line_list.count())
                if self.line_list.item(i).flags() & Qt.ItemFlag.ItemIsEnabled}

    def _bulk(self, checked):
        ids = self._visible_ids()
        selected = self._selected | ids if checked else self._selected - ids
        if selected != self._selected:
            self.set_selection(selected); self.changed.emit(set(selected))

    def _item_changed(self, item):
        if not self._checked or not item.flags() & Qt.ItemFlag.ItemIsEnabled:
            return
        selected = set(self._selected); identity = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            selected.add(identity)
        else:
            selected.discard(identity)
        if selected != self._selected:
            self._selected = selected; self.changed.emit(set(selected))

    def _activate(self, item):
        if not item.flags()&Qt.ItemFlag.ItemIsEnabled:return
        identity=item.data(Qt.ItemDataRole.UserRole)
        if self._checked:
            if identity not in self._selected:
                selected=self._selected|{identity};self.set_selection(selected);self.changed.emit(set(selected))
        else:
            self.collapse_results();self.activated.emit(identity)


def _duplicate_companies(routes):
    companies = {}
    for route in routes:
        companies.setdefault(route['company_name'], set()).add(route['company_id'])
    return {name for name, ids in companies.items() if name and len(ids) > 1}


class SingleLinePanel(_PresetPanel):
    routeSelected = Signal(object)
    directionChanged = Signal(str)
    deadheadChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent); self.setAccessibleName('线路信息')
        self._state = dict(direction='up', deadhead=False, selected_route_id=None)
        self._route = None; self._facts = None; self._operating_km = None; self._deadhead_km = None;self._information=None;self._information_schema=None
        self._routes = []
        search_section = QVBoxLayout();search_section.setContentsMargins(0,0,0,0);self.body_layout.addLayout(search_section)
        self._search_section = self._catalog_view_host = QWidget()
        search_section.addWidget(self._catalog_view_host);search_layout=QVBoxLayout(self._catalog_view_host);search_layout.setContentsMargins(0,0,0,0)
        self._catalog_view = _RouteList(False); search_layout.addWidget(self._catalog_view)
        self._catalog_view.line_list.setProperty('heightCap',112)
        self.search = self._catalog_view.search; self.route_list = self._catalog_view.line_list
        self._catalog_view.activated.connect(self._route_selected)
        section = _section(self.body_layout); self.route_title = _label(section, '线路信息', True)
        self.route_identity = _label(section, '')
        self._direction = _ChoiceGroup([('up', '上行'), ('down', '下行'), ('whole', '双向')], 3)
        self.direction_buttons = dict(self._direction.buttons)
        self.direction_buttons['both'] = self.direction_buttons['whole']
        section.addWidget(self._direction); self._direction.changed.connect(self._direction_changed)
        self.deadhead_check = _style_control(CheckBox('计入空放里程')); section.addWidget(self.deadhead_check)
        self.deadhead_check.clicked.connect(self._deadhead_changed)
        self.data_sections={};self._data_layouts={};self.information_labels={};self.fact_labels={}
        for key,title in [('line_information','线路信息'),('passenger_data','客流数据')]:
            layout=_section(self.body_layout);_label(layout,title,True)
            self.data_sections[key]=layout.parentWidget();self._data_layouts[key]=layout
        self._build_information()
        self.body_layout.addStretch(1); self._refresh()

    def state(self):
        return deepcopy(self._state)

    def set_state(self, state):
        old_identity=self._state['selected_route_id']
        direction = state.get('direction', self._state['direction'])
        if direction == 'both': direction = 'whole'
        if direction in ('up', 'down', 'whole'): self._state['direction'] = direction
        for key in ('deadhead', 'selected_route_id'):
            if key in state: self._state[key] = bool(state[key]) if key == 'deadhead' else state[key]
        self._catalog_view.set_selection({self._state['selected_route_id']}); self._refresh()
        if self._state['selected_route_id']!=old_identity:self.collapse_results()

    def set_routes(self, routes):
        self._routes = _catalog(routes)
        self._catalog_view.set_routes(self._routes, {self._state['selected_route_id']}, _duplicate_companies(self._routes))

    def set_search_visible(self, visible):
        """Show the sidebar's full-catalog search beside the shared map search."""
        self._search_section.setVisible(bool(visible))

    def collapse_results(self):self._catalog_view.collapse_results()

    def set_route(self, route, facts, operating_km, deadhead_km,information=None):
        self._route = route; self._facts = facts; self._operating_km = operating_km; self._deadhead_km = deadhead_km
        self._state['selected_route_id'] = _field(route, 'id')
        self._information=deepcopy(information);self._build_information()
        self._catalog_view.set_selection({self._state['selected_route_id']}); self._refresh()

    def set_information(self,information):
        self._information=deepcopy(information);self._build_information();self._refresh()

    def _build_information(self):
        sections=_field(self._information,'sections') or (
            ('line_information','线路信息',(('duration_minutes','核定时间（全线）','—'),('scheduled_departures','当日发班（计划）','—'))),
            ('passenger_data','客流数据',(('transported_today','当日客流','—'),)))
        schema=tuple((key,tuple((field,label) for field,label,text in rows)) for key,title,rows in sections)
        if schema!=self._information_schema:
            self._information_schema=schema;self.fact_labels={};self.information_labels={}
            for layout in self._data_layouts.values():
                while layout.count()>1:
                    item=layout.takeAt(1)
                    if item.widget():item.widget().hide();item.widget().deleteLater()
            def add_row(layout,key,title):
                host=QWidget();row=QHBoxLayout(host);row.setContentsMargins(0,0,0,0);row.setSpacing(10)
                caption=_style_control(BodyLabel(title),tokens.FONT_SIZE_BODY,tokens.TEXT_SECONDARY);caption.setWordWrap(True)
                value=_style_control(BodyLabel('—'));value.setWordWrap(True);value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
                row.addWidget(caption);row.addWidget(value,1);layout.addWidget(host);self.information_labels[key]=value
                return host,value
            geometry=self._data_layouts['line_information']
            for key,title in [('geometry_km','所选方向长度'),('operating_km','运营长度'),('deadhead_km','空放长度')]:
                host,value=add_row(geometry,key,title);self.fact_labels[key]=value
                if key!='geometry_km':setattr(self,f'_{key}_widgets',(host,))
            aliases={'单程时间':'duration_minutes','今日客流':'transported_today','当日发班数':'scheduled_departures'}
            for section_id,title,rows in sections:
                layout=self._data_layouts.get(section_id)
                if layout is None:continue
                for key,label,text in rows:
                    host,value=add_row(layout,key,label);self.fact_labels[aliases.get(key,key)]=value
        for section_id,title,rows in sections:
            for key,label,text in rows:
                if key in self.information_labels:self.information_labels[key].setText(str(text))

    def _route_selected(self, identity):
        self.collapse_results()
        if identity == self._state['selected_route_id']: return
        self._state['selected_route_id'] = identity; self.routeSelected.emit(identity)

    def _direction_changed(self, direction):
        if direction != self._state['direction']:
            self._state['direction'] = direction; self.directionChanged.emit(direction)

    def _deadhead_changed(self, checked):
        if checked != self._state['deadhead']:
            self._state['deadhead'] = checked; self._refresh(); self.deadheadChanged.emit(checked)

    def _refresh(self):
        route = self._route
        identity=_field(self._information,'identity')
        route_id=_field(route,'id')
        label=next((record.get('display_label') for record in self._routes if record['id']==route_id),None)
        if route is not None and not label:label=resolve_line_labels((route,)).get(route_id)
        self.route_title.setText(str(label or _field(identity,'name',_field(route, 'name', '线路信息'))))
        self.route_identity.setText(str(_field(identity,'company_name',_field(route, 'company_name', '')) or ''))
        roundtrip = _field(_field(route, 'direction'), 'kind') == 'roundtrip'
        for button in self._direction.buttons.values(): button.setEnabled(roundtrip)
        self._direction.set_value(self._state['direction'])
        self._direction.setVisible(roundtrip)
        self.deadhead_check.setEnabled(bool(_field(route, 'depot_paths', ())))
        self.deadhead_check.setChecked(self._state['deadhead'])
        total = self._operating_km
        if self._state['deadhead']:
            total = None if total is None or self._deadhead_km is None else total + self._deadhead_km
        self.fact_labels['geometry_km'].setText(_number(total, 'km', 2))
        self.fact_labels['operating_km'].setText(_number(self._operating_km, 'km', 2))
        self.fact_labels['deadhead_km'].setText(_number(self._deadhead_km, 'km', 2))
        for key in ('operating_km', 'deadhead_km'):
            for widget in getattr(self, f'_{key}_widgets'): widget.setVisible(self._state['deadhead'])
        if self._information is None:
            ticks = _field(self._facts, 'approved_duration_ticks')
            duration = ticks / TICKS_PER_SECOND / 60 if ticks is not None else _field(self._facts, 'duration_minutes')
            today = _field(self._facts, 'today_passengers', _field(self._facts, 'transported_today'))
            self.fact_labels['duration_minutes'].setText(_number(duration, '分钟', 2))
            self.fact_labels['transported_today'].setText(_number(today, '人次'))
            self.fact_labels['scheduled_departures'].setText(_number(_field(self._facts, 'scheduled_departures'), '班次'))


class BuildingLineMenu(QFrame):
    """Fluent child overlay confined to the map surface; no separate window."""
    selectionChanged = Signal(object)

    def __init__(self, host):
        super().__init__(host)
        self.setObjectName('buildingLineMenu'); self.setAccessibleName('建筑服务线路')
        self.setStyleSheet(f'QFrame#buildingLineMenu {{background:{tokens.CARD_BG};border:1px solid {tokens.BORDER_STRONG};border-radius:{tokens.RADIUS_CONTROL}px;}}')
        root = QVBoxLayout(self); root.setContentsMargins(12, 10, 12, 12); root.setSpacing(8)
        header = QHBoxLayout(); self.title_label = _label(header, '', True)
        self.close_button = _style_control(TransparentPushButton('关闭')); self.close_button.setFixedWidth(54)
        self.close_button.setAccessibleName('关闭建筑服务线路'); header.addWidget(self.close_button); root.addLayout(header)
        self.status_label = _label(root, '')
        self._catalog_view = _RouteList(); root.addWidget(self._catalog_view)
        self.search = self._catalog_view.search; self.line_list = self._catalog_view.line_list
        self.select_all = self._catalog_view.select_all; self.clear_selection = self._catalog_view.clear_selection
        self._catalog_view.changed.connect(self.selectionChanged)
        self.close_button.clicked.connect(self.hide)
        self._anchor = QPoint();self.source_unresolved_refs=();self.source_complete=False;self.hide()

    def showEvent(self, event):
        QApplication.instance().installEventFilter(self)
        super().showEvent(event)

    def hideEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().hideEvent(event)

    def present(self, building, routes, selected, global_pos, known, duplicate_companies):
        self.title_label.setText(str(_field(building, 'name', '') or '建筑服务线路'))
        self.search.clear(); self._catalog_view.set_routes(routes, selected, duplicate_companies)
        association=_field(building,'service_lines')
        self.source_complete=bool(known and _field(association,'complete') is True and not self.source_unresolved_refs)
        available=any(route['selectable'] for route in routes)
        confirmed_empty=self.source_complete and not routes and not _field(association,'route_ids',())
        self.status_label.setText('无服务线路' if confirmed_empty else '线路信息暂不可用' if not known or not available else '部分线路不可用' if not self.source_complete else '')
        self.status_label.setVisible(bool(self.status_label.text()))
        self._anchor = self.parentWidget().mapFromGlobal(global_pos)
        self._place(); self.show(); self.raise_(); self.search.setFocus(Qt.FocusReason.PopupFocusReason)

    def _place(self):
        host = self.parentWidget(); margin = 8
        width = min(360, max(1, host.width() - 2 * margin))
        self.setFixedWidth(width)
        self.line_list.setProperty('heightCap', min(260, max(32, host.height() - 200)))
        self.line_list.wrap_items()
        height = min(self.sizeHint().height(), max(1, host.height() - 2 * margin))
        x = min(max(margin, self._anchor.x()), max(margin, host.width() - width - margin))
        y = min(max(margin, self._anchor.y()), max(margin, host.height() - height - margin))
        self.setGeometry(x, y, width, height)

    def eventFilter(self, watched, event):
        if self.isVisible():
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                if watched is self or isinstance(watched, QWidget) and self.isAncestorOf(watched):
                    self.hide(); return True
            if event.type() == QEvent.Type.MouseButtonPress and isinstance(watched, QWidget):
                if watched.window() is self.window() and watched is not self and not self.isAncestorOf(watched):
                    self.hide()
            if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
                self._place()
            if watched is self.parentWidget() and event.type() in (QEvent.Type.Hide, QEvent.Type.Close):
                self.hide()
        return super().eventFilter(watched, event)

    def wheelEvent(self, event):
        event.accept()


class PlanningPanel(_PresetPanel):
    selectionChanged = Signal(object)
    buildingViewChanged = Signal(str)
    buildingEmphasisChanged = Signal(bool)
    buildingClassesChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent); self.setAccessibleName('建筑视图与线路比选')
        self._state = dict(selected_ids=set(), building_view='combined', building_emphasis=True, building_classes=None)
        self._routes = []; self._class_options = []; self._class_population = None
        self._popup_host = None; self.building_menu = None
        section = _section(self.body_layout); _label(section, '建筑视图', True)
        self._view = _ChoiceGroup([('combined', '综合功能'), ('home', '住宅'), ('work', '工作'), ('leisure', '休闲')], 2)
        self.building_view_buttons = self._view.buttons; section.addWidget(self._view)
        self._view.changed.connect(self._view_changed)
        self.class_grid = _OptionGrid('building_classes'); section.addWidget(self.class_grid)
        self.class_grid.changed.connect(self._classes_changed)
        self.emphasis_check = _style_control(CheckBox('强调建筑功能')); section.addWidget(self.emphasis_check)
        self.emphasis_check.clicked.connect(self._emphasis_changed)
        lines = _section(self.body_layout); _label(lines, '线路比选', True)
        self.selection_summary = _label(lines, '已选 0 / 共 0')
        self._catalog_view = _RouteList(); lines.addWidget(self._catalog_view)
        self.search = self._catalog_view.search; self.line_list = self._catalog_view.line_list
        self.select_all = self._catalog_view.select_all; self.clear_selection = self._catalog_view.clear_selection
        self._catalog_view.changed.connect(self._selection_changed)
        self.body_layout.addStretch(1); self._refresh()

    def state(self):
        state = deepcopy(self._state); state['selected_line_ids'] = set(state['selected_ids'])
        return state

    def set_state(self, state):
        for key in ('selected_ids', 'selected_line_ids', 'manual_line_ids'):
            if key in state:
                self._state['selected_ids'] = set(state[key] or ()); break
        if state.get('building_view') in self.building_view_buttons: self._state['building_view'] = state['building_view']
        if 'building_emphasis' in state: self._state['building_emphasis'] = True if state['building_emphasis'] is None else bool(state['building_emphasis'])
        if 'building_classes' in state:
            self._state['building_classes'] = ({v['id'] for v in self._class_options} if self._class_options else None) if state['building_classes'] is None else set(state['building_classes'])
        self._refresh()

    def set_options(self, options):
        self._class_options = deepcopy(options.get('building_classes', []))
        if self._state['building_classes'] is None and self._class_options:
            self._state['building_classes'] = {v['id'] for v in self._class_options}
        self._refresh()

    def set_routes(self, routes, selected_ids):
        self._routes = _catalog(routes); self._state['selected_ids'] = set(selected_ids or ())
        self._catalog_view.set_routes(self._routes, self._state['selected_ids'], _duplicate_companies(self._routes)); self._refresh()

    def set_popup_host(self, host):
        if self.building_menu is not None:
            self.building_menu.hide(); self.building_menu.setParent(host)
        self._popup_host = host

    def open_building_menu(self, building, candidate_routes, selected_ids, global_pos, *, source_known=None, unresolved_refs=()):
        association = _field(building, 'service_lines')
        if source_known is None:
            source_known = _field(association, 'known', candidate_routes is not None)
        if not unresolved_refs: unresolved_refs = _field(association, 'unresolved_refs', ())
        candidates = _catalog(candidate_routes) if source_known and candidate_routes is not None else []
        full_labels={route['id']:route.get('display_label') for route in self._routes}
        for route in candidates:
            if full_labels.get(route['id']):route['display_label']=full_labels[route['id']]
        self._state['selected_ids'] = set(selected_ids or ())
        host = self._popup_host or self.window()
        if self.building_menu is None:
            self.building_menu = BuildingLineMenu(host); self.building_menu.selectionChanged.connect(self._selection_changed)
        self.building_menu.source_unresolved_refs=tuple(dict.fromkeys(unresolved_refs))
        self._refresh()
        self.building_menu.present(building, candidates, self._state['selected_ids'], global_pos, bool(source_known), _duplicate_companies(self._routes + candidates))

    def _selection_changed(self, selected):
        if selected != self._state['selected_ids']:
            self._state['selected_ids'] = set(selected)
            self._sync_selection(); self.selectionChanged.emit(set(selected))

    def _sync_selection(self):
        selected = self._state['selected_ids']; self._catalog_view.set_selection(selected)
        if self.building_menu is not None: self.building_menu._catalog_view.set_selection(selected)
        count = sum(route['id'] in selected for route in self._routes)
        self.selection_summary.setText(f'已选 {count} / 共 {len(self._routes)}')

    def _view_changed(self, view):
        if view != self._state['building_view']:
            self._state['building_view'] = view; self.buildingViewChanged.emit(view)

    def _emphasis_changed(self, checked):
        if checked != self._state['building_emphasis']:
            self._state['building_emphasis'] = checked; self.buildingEmphasisChanged.emit(checked)

    def _classes_changed(self):
        selected = self.class_grid.selected()
        if selected != self._state['building_classes']:
            self._state['building_classes'] = selected; self.buildingClassesChanged.emit(set(selected))

    def _refresh(self):
        self._view.set_value(self._state['building_view']); self.emphasis_check.setChecked(self._state['building_emphasis'])
        classes=self._state['building_classes'] or set()
        if self._class_population is None or self._class_population!=(self._class_options,classes):
            self.class_grid.populate(self._class_options, classes)
            self._class_population=(deepcopy(self._class_options),set(classes))
        self._sync_selection()
