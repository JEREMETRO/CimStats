"""Map page using the existing application shell and Fluent component language."""
from __future__ import annotations

import json
import time
from pathlib import Path
from copy import deepcopy
from dataclasses import dataclass
from PySide6.QtCore import QThread, Signal, Slot, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidgetItem, QStackedWidget
from qfluentwidgets import SearchLineEdit, TransparentToolButton, PushButton, FluentIcon, ListWidget, setCustomStyleSheet, IndeterminateProgressBar, Pivot
import stats_tokens as tokens
from stats_typography import ui_font
from stats_controls import configure_navigation_pivot
from map_canvas import MapCanvas, ROAD_STYLES, MapSearchResult
from map_icon import MAP_ICON
from map_panels import MapPanelSet
from map_docking import MapDockHost
from map_model import MapSnapshot, road_display_level
from map_query import MapQuery, stats_from_session
from map_presets import PresetStore, PRESETS, valid_view
from map_visibility import route_has_geometry


def _json(value):
    return json.dumps(value, ensure_ascii=False, default=lambda v: sorted(v, key=str) if isinstance(v, set) else str(v))


@dataclass(frozen=True, slots=True)
class _SaveSearchResult(MapSearchResult):
    save_token: tuple[str, int]
    selectable: bool = True


class MapWorker(QThread):
    completed = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, generation, source, cache, parent=None):
        super().__init__(parent)
        self.generation, self.source, self.cache = generation, source, cache

    def run(self):
        from map_geometry import MapGeometryService, MapCancelled
        from background_work import CooperativeCancellation
        cancelled = CooperativeCancellation(self.isInterruptionRequested)

        try:
            snapshot = MapGeometryService(cache_dir=self.cache).load(
                self.source, cancelled, use_disk_cache=False)
            if not self.isInterruptionRequested():
                self.completed.emit(self.generation, snapshot)
        except MapCancelled:
            pass
        except Exception as error:
            if not self.isInterruptionRequested():
                self.failed.emit(self.generation, str(error))


class _MapSurface(QWidget):
    def __init__(self, canvas, parent=None, search=None, focus=None, defer_search=None):
        super().__init__(parent)
        self.canvas = canvas
        self._search_provider = search or canvas.search
        self._focus_provider = focus or canvas.focus_result
        self._defer_search = defer_search
        canvas.setParent(self)
        self.loading = IndeterminateProgressBar(self)
        self.loading.setAccessibleName('正在加载地图')
        self.loading.stop()
        self.loading.hide()
        self.search = SearchLineEdit(self)
        self.search.setPlaceholderText('搜索单条线路')
        self.search.setAccessibleName('搜索单条线路')
        self.search.setFixedHeight(36)
        self.search.setObjectName("mapSearchInput")
        setCustomStyleSheet(self.search, f'SearchLineEdit#mapSearchInput, SearchLineEdit#mapSearchInput:hover, SearchLineEdit#mapSearchInput:focus, SearchLineEdit#mapSearchInput:disabled {{ background: {tokens.CARD_BG}; color: {tokens.TEXT_PRIMARY}; }}', f'SearchLineEdit#mapSearchInput, SearchLineEdit#mapSearchInput:hover, SearchLineEdit#mapSearchInput:focus, SearchLineEdit#mapSearchInput:disabled {{ background: {tokens.CARD_BG}; color: {tokens.TEXT_PRIMARY}; }}')
        self.results = ListWidget(self)
        self.results.setObjectName('mapSearchResults')
        result_style=f'ListWidget#mapSearchResults {{ background:{tokens.CARD_BG}; color:{tokens.TEXT_PRIMARY}; border:1px solid {tokens.BORDER}; border-radius:{tokens.RADIUS_CONTROL}px; }}'
        setCustomStyleSheet(self.results,result_style,result_style)
        self.results.setFont(ui_font(tokens.FONT_SIZE_BODY))
        self.results.hide()
        self.search.searchSignal.connect(self._submit_search)
        self.search.returnPressed.connect(self._submit_search)
        self.search.clearSignal.connect(self._clear_search)
        self.results.itemClicked.connect(self._focus)
        self.results.itemActivated.connect(self._focus)
        self.controls = QWidget(self)
        column = QVBoxLayout(self.controls)
        column.setContentsMargins(0,0,0,0)
        column.setSpacing(2)
        for icon, name, callback in ((FluentIcon.ADD,'放大',canvas.zoom_in),
                                     (FluentIcon.REMOVE,'缩小',canvas.zoom_out),
                                     (FluentIcon.HOME,'复位视图',canvas.reset_view)):
            button = TransparentToolButton(icon,self.controls)
            button.setFixedSize(34,34)
            button.setAccessibleName(name)
            button.clicked.connect(callback)
            column.addWidget(button)
        self.controls.setStyleSheet(f'background:{tokens.CARD_BG};border-radius:6px;')

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.canvas.setGeometry(self.rect())
        self.loading.setGeometry(0,0,self.width(),4)
        self.loading.raise_()
        self.search.setGeometry(14,14,min(320,max(150,self.width()-75)),36)
        self.results.setGeometry(14,54,self.search.width(),min(250,max(60,self.height()-130)))
        self.controls.setGeometry(max(0,self.width()-48),max(54,self.height()-130),34,106)

    def _search(self,*_):
        self.results.clear()
        for result in self._search_provider(self.search.text()):
            item=QListWidgetItem(result.label)
            item.setData(Qt.ItemDataRole.UserRole,result)
            if not getattr(result,'selectable',True):
                item.setData(Qt.ItemDataRole.AccessibleDescriptionRole,'无地图路径')
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled & ~Qt.ItemFlag.ItemIsSelectable)
            self.results.addItem(item)
        self.results.setVisible(bool(self.results.count()))
        self.results.raise_()

    def _clear_search(self):
        self.results.clear()
        self.results.hide()
        if self._defer_search is not None:self._defer_search('')

    def _submit_search(self,*_):
        text=self.search.text().strip()
        if not text:
            self._clear_search()
            return
        if self._defer_search is not None and self._defer_search(text):
            self.results.clear()
            self.results.hide()
            return
        self._search()
        if self.results.count()==1 and self.results.item(0).flags() & Qt.ItemFlag.ItemIsEnabled:
            self._focus(self.results.item(0))
        elif self.results.count():
            for index in range(self.results.count()):
                if self.results.item(index).flags() & Qt.ItemFlag.ItemIsEnabled:
                    self.results.setCurrentRow(index)
                    self.results.setFocus()
                    break

    def set_loading(self, active):
        if active:
            self.loading.start()
            self.loading.show()
            self.loading.raise_()
        else:
            self.loading.stop()
            self.loading.hide()

    def _focus(self,item):
        if item is None or not item.flags() & Qt.ItemFlag.ItemIsEnabled:return
        self._focus_provider(item.data(Qt.ItemDataRole.UserRole))
        self.results.hide()


class MapPage(QWidget):
    ready = Signal()
    failed = Signal(str)

    def __init__(self, settings, parent=None, cache_dir=None):
        super().__init__(parent)
        self.settings=settings
        self.cache_dir=Path(cache_dir) if cache_dir is not None else None
        self.session={}
        self.query=None
        self.result=None
        self._generation=0
        self._session_generation=0
        self._pending_route=None
        self._pending_search=None
        self._switching=True
        self._snapshot=None
        self._panel_catalogs={}
        self._presentation_source=None
        self._presentation_companies=None
        self._presentation_routes=()
        self._planning_options=None
        self._awaiting_frame=False
        self._panel_presentation=None
        self._prefetch_path=None
        self._prefetch_snapshot=None
        self._prefetch_error=None
        self.workers=[]
        self._requested=False
        self.setMinimumWidth(0)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,8)
        layout.setSpacing(0)
        self.canvas=MapCanvas()
        if hasattr(self.canvas, 'frame_ready'):
            self.canvas.frame_ready.connect(self._frame_ready)
        if hasattr(self.canvas, 'render_failed'):
            self.canvas.render_failed.connect(self._render_failed)
        self.surface=_MapSurface(self.canvas, search=self.search, focus=self._focus_search, defer_search=self._defer_search)
        building_clicked=getattr(self.canvas,'buildingClicked',None)
        if building_clicked is not None:building_clicked.connect(self.show_building)
        self.panel_set=MapPanelSet(self)
        self._network_defaults=self.panel_set.state()
        for key in ('manual_line_ids','company_ids','modes','layer_modes','road_levels','building_classes','building_uses','profit_statuses'):
            self._network_defaults[key]=None
        self.presets=PresetStore(settings,self._network_defaults)
        self.preset='network'
        self.dock=MapDockHost(self.surface,self.panel_set.panels,self)
        self.docks={'network':self.dock}
        self._placeholders={'network':QWidget(self)}
        self.dock_stack=QStackedWidget(self)
        self.dock_stack.addWidget(self.dock)
        self.preset_pivot=Pivot(self)
        for key,title in [('single','单线'),('network','线网'),('planning','规划')]:
            self.preset_pivot.addItem(key,title)
        configure_navigation_pivot(self.preset_pivot,{
            'single':FluentIcon.BUS,'network':MAP_ICON,'planning':FluentIcon.EDIT})
        self.preset_pivot.setCurrentItem('network')
        self.preset_pivot.currentItemChanged.connect(self.set_preset)
        layout.addWidget(self.preset_pivot)
        layout.addWidget(self.dock_stack,1)
        footer=QHBoxLayout()
        footer.setContentsMargins(12,3,6,0)
        self.status=QLabel()
        self.status.setFont(ui_font(tokens.FONT_SIZE_CAPTION))
        self.status.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};background:transparent;')
        footer.addWidget(self.status,1)
        self.reset_layout=PushButton('恢复默认布局',self)
        self.reset_layout.setFixedHeight(28)
        self.reset_layout.clicked.connect(lambda:self.dock.reset_layout())
        footer.addWidget(self.reset_layout)
        layout.addLayout(footer)
        self.panel_set.stateChanged.connect(self.apply_state)
        self.dock.layoutChanged.connect(lambda state:self._save_layout('network',state))
        self.canvas.view_changed.connect(self._save_view)
        saved=self.presets.state('network')['layout']
        if saved:self.dock.restore_layout(saved)
        self._switching=False
        self.set_preset(self.presets.current)

    @property
    def save_token(self):
        return (str(self.session.get('save_key') or self.session.get('session_key') or ''),
                self._session_generation)

    def _save_layout(self,preset,state):
        if not self._switching:
            self.presets.update(preset,layout=state)
            if preset=='network':self.settings.setValue('map/layout',_json(state))

    def _save_view(self,x,z,zoom):
        if not self._switching and self.query is not None:
            self.presets.update(self.preset,view=[x,z,zoom])

    def _ensure_dock(self,preset):
        if preset in self.docks:return self.docks[preset]
        from map_preset_panels import SingleLinePanel, PlanningPanel
        if preset=='single':
            from map_preset_panels import SingleLineListPanel
            self.single_list_panel=SingleLineListPanel(self)
            self.single_list_panel.routeSelected.connect(lambda identity:self.show_route(identity,self.save_token))
            self.single_panel=SingleLinePanel(self)
            self.single_panel.routeSelected.connect(lambda identity:self.show_route(identity,self.save_token))
            self.single_panel.directionChanged.connect(lambda value:self._preset_changed('single',direction=value))
            self.single_panel.deadheadChanged.connect(lambda value:self._preset_changed('single',deadhead=value))
            panels={'lines':self.single_list_panel,'single':self.single_panel}
        else:
            self.planning_panel=PlanningPanel(self)
            self.planning_panel.set_popup_host(self.surface)
            self.planning_panel.selectionChanged.connect(lambda value:self._preset_changed('planning',selected_ids=set(value)))
            self.planning_panel.buildingViewChanged.connect(lambda value:self._preset_changed('planning',building_view=value))
            self.planning_panel.buildingClassesChanged.connect(lambda value:self._preset_changed('planning',building_classes=set(value)))
            self.planning_panel.buildingEmphasisChanged.connect(lambda value:self._preset_changed('planning',building_emphasis=value))
            panels={'planning':self.planning_panel}
        placeholder=QWidget(self)
        self._placeholders[preset]=placeholder
        host=MapDockHost(placeholder,panels,self)
        self.docks[preset]=host
        self.dock_stack.addWidget(host)
        host.layoutChanged.connect(lambda state,key=preset:self._save_layout(key,state))
        saved=self.presets.state(preset)['layout']
        if saved:host.restore_layout(saved)
        elif preset=='single' and self.presets.state('single')['query']['route_id'] is not None:
            host.activate_panel('single')
        return host

    def set_preset(self,preset):
        if preset not in PRESETS:raise ValueError('Unknown map preset: '+str(preset))
        if preset==self.preset:return
        if self.query is not None:
            self.presets.update(self.preset,view=[*self.canvas.center,self.canvas.zoom])
        host=self._ensure_dock(preset)
        self._switching=True
        try:
            if hasattr(self,'planning_panel') and hasattr(self.planning_panel,'building_menu'):
                menu=self.planning_panel.building_menu
                if menu is not None:menu.hide()
            self.dock.set_content(self._placeholders[self.preset])
            self.preset=preset
            self.dock=host
            host.set_content(self.surface)
            self.dock_stack.setCurrentWidget(host)
            self.preset_pivot.blockSignals(True)
            self.preset_pivot.setCurrentItem(preset)
            self.preset_pivot.blockSignals(False)
            self.presets.activate(preset)
            self.surface.search.setPlaceholderText('搜索单条线路')
            self.surface.search.setAccessibleName(self.surface.search.placeholderText())
            self.surface.results.hide()
            self._sync_preset_panels()
            if self.query is not None:
                self._apply_current()
                self._restore_view()
        finally:self._switching=False

    def _restore_view(self):
        view=valid_view(self.presets.state(self.preset)['view'])
        if view is not None:
            self.canvas.center=tuple(view[:2])
            self.canvas.zoom=view[2]
            self.canvas._changed()
        else:self.canvas.fit_to_map()
        self.canvas._fit_pending=False

    def _preset_changed(self,preset,**values):
        self.presets.update(preset,query=values)
        if self.query is not None and self.preset==preset:self._apply_current()

    def _sync_preset_panels(self):
        if self.query is None:self.panel_set.set_result_count(0)
        routes=self._presentation_catalog()
        if hasattr(self,'single_list_panel'):
            state=self.presets.state('single')['query']
            if self._panel_catalogs.get('lines') is not routes:
                self.single_list_panel.set_routes(routes)
                self._panel_catalogs['lines']=routes
            self.single_list_panel.set_state({'selected_route_id':state['route_id']})
            if state['route_id'] is None and self._pending_route is None:
                self.docks['single'].activate_panel('lines')
        if hasattr(self,'single_panel'):
            state=self.presets.state('single')['query']
            if self._panel_catalogs.get('single') is not routes:
                self.single_panel.set_routes(routes)
                self._panel_catalogs['single']=routes
            self.single_panel.set_state(dict(state,selected_route_id=state['route_id']))
            if self.query is None:self.single_panel.set_route(None,None,None,None)
        if hasattr(self,'planning_panel'):
            state=self.presets.state('planning')['query']
            self.planning_panel.set_state(state)
            if self._panel_catalogs.get('planning') is not routes:
                self.planning_panel.set_routes(routes,state['selected_ids'])
                self._panel_catalogs['planning']=routes
            if self.query is not None and self._planning_options is not self._panel_options:
                self.planning_panel.set_options(self._panel_options)
                self.presets.update('planning',query={'building_classes':self.planning_panel.state()['building_classes']})
                self._planning_options=self._panel_options

    def _current_state(self):
        if self.preset=='network':return self.panel_set.state()
        state=deepcopy(self._network_defaults)
        own=self.presets.state(self.preset)['query']
        if self.preset=='single':
            state.update(manual_line_ids=[] if own['route_id'] is None else [own['route_id']],
                         direction=own['direction'],deadhead=own['deadhead'],distinguish_directions=True)
        else:
            state.update(manual_line_ids=own['selected_ids'],building_view=own['building_view'],
                         building_classes=own['building_classes'],building_emphasis=own['building_emphasis'])
        return state

    def _presentation_catalog(self):
        """One save-local catalog for every search, independent of map filters."""
        from report_model import display_company
        from map_line_labels import resolve_line_labels
        routes=self.query.snapshot.routes if self.query is not None else ()
        companies={str(row['公司标识']):display_company(row.get('公司名称',''))
                   for row in self.session.get('companies',()) if row.get('公司标识') is not None}
        names=tuple(sorted(companies.items()))
        if self._presentation_source is routes and self._presentation_companies==names:
            return self._presentation_routes
        self._presentation_source=routes
        self._presentation_companies=names
        self._presentation_routes=tuple(dict(id=route.id,name=self.canvas.route_label(route),
            company_id=route.company_id,company_name=display_company(companies.get(str(route.company_id),route.company_name)),
            mode=route.mode,selectable=route_has_geometry(route)) for route in routes)
        labels=resolve_line_labels(self._presentation_routes)
        for route in self._presentation_routes:route['display_label']=labels[route['id']]
        return self._presentation_routes

    def search(self,text):
        if self.query is None:return []
        from display_rules import display_mode
        needle=str(text).strip().casefold()
        if not needle:return []
        results=[]
        for route in self._presentation_catalog():
            identity=route['display_label']
            haystack=f"{identity} {route['company_name']} {display_mode(route['mode'])} {route['id']}".casefold()
            if needle not in haystack:continue
            results.append(_SaveSearchResult('route',route['id'],identity,self.query.snapshot.bounds,
                                            self.save_token,route['selectable']))
        return results

    def _search_token(self):
        # Statistics handoff changes save_token but continues this exact prefetch.
        # Its source and worker generation remain stable until cancellation.
        if self._prefetch_path is not None:
            return ('prefetch',str(self._prefetch_path),self._generation)
        return ('session',*self.save_token)

    def _defer_search(self,text):
        self._pending_search=(self._search_token(),text) if text and self.query is None else None
        return self._pending_search is not None

    def _consume_pending_search(self):
        pending=self._pending_search
        self._pending_search=None
        if pending is None:return
        token,text=pending
        if token==self._search_token() and text==self.surface.search.text().strip():
            self.surface._submit_search()

    def _focus_search(self,result):
        if getattr(result,'save_token',self.save_token)!=self.save_token:return False
        if result.kind=='route':
            return self.show_route(result.id,self.save_token)
        return self.canvas.focus_result(result)

    def show_route(self,route_id,save_key=None):
        if save_key is not None:
            if isinstance(save_key,(tuple,list)):
                if tuple(save_key)!=self.save_token:return False
            elif str(save_key)!=self.save_token[0]:return False
        try:route_id=int(route_id)
        except (TypeError,ValueError):return False
        if self.query is not None and not route_has_geometry(next(
                (r for r in self.query.snapshot.routes if r.id==route_id),None)):return False
        if (self.query is not None and self.preset=='single'
                and self.presets.state('single')['query']['route_id']==route_id):
            self.docks['single'].activate_panel('single')
            return True
        self._pending_route=(self.save_token,route_id)
        self.set_preset('single')
        self.docks['single'].activate_panel('single')
        if self.query is not None:self._consume_pending_route()
        else:self.ensure_loaded()
        return True

    def _consume_pending_route(self):
        if self._pending_route is None or self.query is None:return
        token,identity=self._pending_route
        self._pending_route=None
        if token!=self.save_token:return
        route=next((r for r in self.query.snapshot.routes if r.id==identity),None)
        if not route_has_geometry(route):return
        self.presets.update('single',query={'route_id':identity})
        if self.preset=='single':
            self._sync_preset_panels()
            self._apply_current()
            self.canvas.focus_result(MapSearchResult('route',identity,'',self.query.snapshot.bounds))

    def show_building(self,building_id,global_pos):
        if self.preset!='planning' or self._snapshot is None:return False
        building=next((b for b in self._snapshot.buildings if b.id==building_id),None)
        if building is None:return False
        source=getattr(building,'service_lines',None)
        known=bool(source is not None and source.known)
        route_by_id={route['id']:route for route in self._presentation_catalog()}
        ids=tuple(dict.fromkeys(source.route_ids)) if known else ()
        candidates=[route_by_id[identity] for identity in ids if identity in route_by_id] if known else None
        unresolved=tuple(getattr(source,'unresolved_refs',()))+tuple(identity for identity in ids if identity not in route_by_id)
        self.planning_panel.open_building_menu(building,candidates,
            self.presets.state('planning')['query']['selected_ids'],global_pos,
            source_known=known,unresolved_refs=unresolved)
        return True

    def _close_building_menu(self):
        if hasattr(self,'planning_panel') and self.planning_panel.building_menu is not None:
            self.planning_panel.building_menu.hide()

    def set_session(self, session):
        self._close_building_menu()
        self.surface.results.clear()
        self.surface.results.hide()
        self._session_generation+=1
        self._pending_route=None
        self._switching=True
        source=Path(session.get('save_path','')) if session else None
        attached=bool(source and self._prefetch_path == source)
        if not attached:
            self._generation+=1
            for worker in self.workers:worker.requestInterruption()
            self._prefetch_path=None
            self._prefetch_snapshot=None
            self._prefetch_error=None
        self.session=session or {}
        self._snapshot=None
        self.query=None
        self.result=None
        self._requested=attached
        self._awaiting_frame=False
        self._panel_presentation=None
        self.canvas.set_snapshot(MapSnapshot())
        self.surface.set_loading(False)
        self.status.clear()
        self.presets.load(self.save_token[0])
        self.panel_set.set_state(self._network_defaults)
        self.panel_set.set_state(self.presets.state('network')['query'])
        self._sync_preset_panels()
        self._switching=False
        if attached and self._prefetch_snapshot is not None:
            snapshot=self._prefetch_snapshot
            self._prefetch_snapshot=None
            self._loaded(self._generation,snapshot)
        elif attached and self._prefetch_error is not None:
            message=self._prefetch_error
            self._prefetch_error=None
            self._failed(self._generation,message)
        elif attached:
            if self.isVisible():self.surface.set_loading(True)
        elif self.isVisible():self.ensure_loaded()

    def start_prefetch(self, source):
        """Read the map alongside the statistics parser for this save."""
        self.cancel_prefetch()
        self._prefetch_path=Path(source)
        self._requested=True
        if self.isVisible():self.surface.set_loading(True)
        worker=MapWorker(self._generation,self._prefetch_path,self.cache_dir,self)
        self.workers.append(worker)
        worker.completed.connect(self._loaded)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._worker_finished)
        worker.start()

    def cancel_prefetch(self):
        self._close_building_menu()
        self.surface.results.clear()
        self.surface.results.hide()
        self._session_generation+=1
        self._pending_route=None
        self._snapshot=None
        self._generation+=1
        for worker in self.workers:worker.requestInterruption()
        self._prefetch_path=None
        self._prefetch_snapshot=None
        self._prefetch_error=None
        self.session={}
        self.query=None
        self.result=None
        self._requested=False
        self._awaiting_frame=False
        self._panel_presentation=None
        self.canvas.set_snapshot(MapSnapshot())
        self._sync_preset_panels()
        self.surface.set_loading(False)
        self.status.clear()

    def ensure_loaded(self):
        if self._requested or not self.session:return
        source=Path(self.session.get('save_path',''))
        if not source.is_file():return
        self._requested=True
        self.surface.set_loading(True)
        worker=MapWorker(self._generation,source,self.cache_dir,self)
        self.workers.append(worker)
        worker.completed.connect(self._loaded)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._worker_finished)
        worker.start()

    @Slot()
    def _worker_finished(self):
        worker=self.sender()
        if worker is None:return
        if worker in self.workers:self.workers.remove(worker)
        worker.deleteLater()

    def _loaded(self,generation,snapshot):
        if generation!=self._generation:return
        if self._prefetch_path is not None and not self.session:
            self._prefetch_snapshot=snapshot
            return
        if any((snapshot.roads,snapshot.buildings,snapshot.routes,snapshot.stops)):
            self.surface.set_loading(True)
        self._prepare_hidden_layout()
        self.set_snapshot(snapshot)
        if not self.canvas.isVisible():
            self.canvas._fit_pending=not isinstance(self.parentWidget(),QStackedWidget)
        self.canvas.prepare_frame()
        self.ready.emit()

    def _prepare_hidden_layout(self):
        """Resolve the actual stacked shell bounds before hidden frame prewarming."""
        parent=self.parentWidget()
        if self.isVisible() or not isinstance(parent,QStackedWidget):return
        self.resize(parent.contentsRect().size())
        self.ensurePolished()
        self.layout().setGeometry(self.rect())
        self.dock_stack.layout().setGeometry(self.dock_stack.rect())
        self.dock.setGeometry(self.dock_stack.contentsRect())
        self.dock.layout().setGeometry(self.dock.rect())
        if self.dock._pending_layout is not None:
            saved=self.dock._pending_layout
            self.dock._pending_layout=None
            self.dock._apply_layout(saved)
            self.dock.layout().setGeometry(self.dock.rect())
        self.canvas.setGeometry(self.surface.rect())

    def _failed(self,generation,message):
        if generation==self._generation:
            if self._prefetch_path is not None and not self.session:
                self._prefetch_error=message
                return
            self._awaiting_frame=False
            self.surface.set_loading(False)
            self._requested=False
            self.failed.emit(message)

    def set_snapshot(self,snapshot):
        self._snapshot=snapshot
        self._switching=True
        self._awaiting_frame=self._requested and any((snapshot.roads,snapshot.buildings,snapshot.routes,snapshot.stops))
        if not self._awaiting_frame:
            self.surface.set_loading(False)
        self.query=MapQuery(snapshot,stats_from_session(self.session,snapshot.routes),
                            company_ids=(str(company['公司标识']) for company in self.session.get('companies',())
                                         if company.get('公司标识') is not None))
        options=self.query.panel_options(self.session,self.panel_set.state())
        names={'express':'高速路／快速路','arterial':'主干路','secondary':'次干路','local':'支路',
               'pedestrian':'步行道路','track':'独立轨道','unknown':'未分类'}
        present={road_display_level(road) for road in snapshot.roads}
        options['road_levels']=[{'id':key,'name':name,'color':ROAD_STYLES[key][0]}
                                for key,name in names.items() if key in present]
        options['simulated_datetime']=self.session.get('simulation_time')
        self._panel_options=options
        self.panel_set.set_options(options)
        self._panel_presentation=self._network_presentation(self.panel_set.state(),options['building_emphasis_effective'])
        self.presets.update('network',query=self.panel_set.state())
        self._sync_preset_panels()
        self._apply_current()
        self._restore_view()
        self._switching=False
        self._consume_pending_route()
        self._consume_pending_search()

    def _frame_ready(self):
        if self._awaiting_frame:
            self._awaiting_frame=False
            self.surface.set_loading(False)

    def _render_failed(self, message):
        self._awaiting_frame=False
        self.surface.set_loading(False)
        self.failed.emit(message)

    def apply_state(self,state):
        if state!=self.panel_set.state():self.panel_set.set_state(state)
        self.presets.update('network',query=self.panel_set.state())
        if self.save_token[0]:self.settings.setValue('map/query/'+self.save_token[0],_json(self.panel_set.state()))
        if self.query is not None and self.preset=='network':self._apply_current()

    @staticmethod
    def _network_presentation(state,emphasis):
        return (emphasis,state.get('color_by','mode'),state.get('service_time_mode','off'),
                state.get('service_start'),state.get('service_end'))

    def _apply_current(self):
        state=self._current_state()
        self.result=self.query.select(state)
        self.canvas.set_snapshot(self.result.snapshot)
        options={key:value for key,value in state.items() if key in self.canvas.options}
        options.update(route_colors=self.result.route_colors,building_colors=self.result.building_colors,
                       legend_items=self.query.legend_items(state,self.result),
                       building_classes=None,building_uses=None)
        self.canvas.set_options(**options)
        if self.preset=='network':
            presentation=self._network_presentation(state,self.result.building_emphasis)
            if presentation!=self._panel_presentation:
                self._panel_options.update(self.query.panel_options(self.session,state,self.result))
                self.panel_set.set_options(self._panel_options)
                self._panel_presentation=presentation
            self.panel_set.set_result_count(len(self.result.routes))
        elif self.preset=='single':
            from map_line_facts import line_facts, geometry_lengths
            from map_line_presentation import line_information
            identity=self.presets.state('single')['query']['route_id']
            route=next((r for r in self.query.snapshot.routes if r.id==identity),None)
            facts=line_facts(self.session,identity) if route is not None else None
            lengths=geometry_lengths(route,state['direction'],state['deadhead']) if route is not None else None
            self.single_panel.set_state(dict(self.presets.state('single')['query'],selected_route_id=identity))
            self.single_panel.set_route(route,facts,
                lengths.operating_km if lengths else None,lengths.deadhead_km if lengths else None,
                information=line_information(self.session,identity))
        else:
            self.planning_panel.set_state(self.presets.state('planning')['query'])

        city=self.session.get('metadata',{}).get('地图名称','')
        day=(self._panel_options['passenger_date'] if self.preset=='network' else
             str(self.session.get('simulation_time') or '')[:10])
        modes=state.get('layer_modes')
        visible=sum(1 for route in self.result.routes if state.get('routes',True) and (modes is None or route.mode in modes))
        self.status.setText('   ·   '.join(str(v) for v in (city,day,f'显示 {visible} 条线路',f'已选 {len(self.result.routes)} 条') if v))

    def showEvent(self,event):
        super().showEvent(event)
        if self._awaiting_frame or (self._prefetch_path is not None and self._requested and self.query is None):
            self.surface.set_loading(True)
        self.ensure_loaded()

    def stop_workers(self):
        for worker in self.workers:worker.requestInterruption()
        return not any(worker.isRunning() for worker in self.workers)

    def export_image(self,path):
        return self.canvas.export_image(path)
