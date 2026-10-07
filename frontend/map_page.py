"""Map page using the existing application shell and Fluent component language."""
from __future__ import annotations

import json
from pathlib import Path
from PySide6.QtCore import QThread, Signal, Slot, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidgetItem, QStackedWidget
from qfluentwidgets import SearchLineEdit, TransparentToolButton, PushButton, FluentIcon, ListWidget, setCustomStyleSheet, IndeterminateProgressBar
import stats_tokens as tokens
from stats_typography import ui_font
from map_canvas import MapCanvas, ROAD_STYLES
from map_panels import MapPanelSet
from map_docking import MapDockHost
from map_model import MapSnapshot, road_display_level
from map_query import MapQuery, stats_from_session


def _json(value):
    return json.dumps(value, ensure_ascii=False, default=lambda v: sorted(v, key=str) if isinstance(v, set) else str(v))


class MapWorker(QThread):
    completed = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, generation, source, cache, parent=None):
        super().__init__(parent)
        self.generation, self.source, self.cache = generation, source, cache

    def run(self):
        from map_geometry import MapGeometryService, MapCancelled
        try:
            snapshot = MapGeometryService(cache_dir=self.cache).load(self.source, self.isInterruptionRequested)
            if not self.isInterruptionRequested():
                self.completed.emit(self.generation, snapshot)
        except MapCancelled:
            pass
        except Exception as error:
            if not self.isInterruptionRequested():
                self.failed.emit(self.generation, str(error))


class _MapSurface(QWidget):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        canvas.setParent(self)
        self.loading = IndeterminateProgressBar(self)
        self.loading.setAccessibleName('正在加载地图')
        self.loading.stop()
        self.loading.hide()
        self.search = SearchLineEdit(self)
        self.search.setPlaceholderText('搜索线路、站点或建筑')
        self.search.setAccessibleName('搜索线路、站点或建筑')
        self.search.setFixedHeight(36)
        setCustomStyleSheet(self.search, f'SearchLineEdit {{ background: {tokens.CARD_BG}; color: {tokens.TEXT_PRIMARY}; }}', f'SearchLineEdit {{ background: {tokens.CARD_BG}; color: {tokens.TEXT_PRIMARY}; }}')
        self.results = ListWidget(self)
        self.results.setFont(ui_font(tokens.FONT_SIZE_BODY))
        self.results.hide()
        self.search.searchSignal.connect(self._search)
        self.search.clearSignal.connect(self.results.hide)
        self.results.itemClicked.connect(self._focus)
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
        for result in self.canvas.search(self.search.text()):
            item=QListWidgetItem(result.label)
            item.setData(Qt.ItemDataRole.UserRole,result)
            self.results.addItem(item)
        self.results.setVisible(bool(self.results.count()))
        self.results.raise_()

    def set_loading(self, active):
        if active:
            self.loading.start()
            self.loading.show()
            self.loading.raise_()
        else:
            self.loading.stop()
            self.loading.hide()

    def _focus(self,item):
        self.canvas.focus_result(item.data(Qt.ItemDataRole.UserRole))
        self.results.hide()


class MapPage(QWidget):
    ready = Signal()
    failed = Signal(str)

    def __init__(self, settings, parent=None, cache_dir=None):
        super().__init__(parent)
        self.settings=settings
        self.cache_dir=Path(cache_dir or Path(__file__).resolve().parents[1]/'jobs'/'map-cache')
        self.session={}
        self.query=None
        self.result=None
        self._generation=0
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
        self.surface=_MapSurface(self.canvas)
        self.panel_set=MapPanelSet(self)
        self.dock=MapDockHost(self.surface,self.panel_set.panels,self)
        layout.addWidget(self.dock,1)
        footer=QHBoxLayout()
        footer.setContentsMargins(12,3,6,0)
        self.status=QLabel()
        self.status.setFont(ui_font(tokens.FONT_SIZE_CAPTION))
        self.status.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};background:transparent;')
        footer.addWidget(self.status,1)
        self.reset_layout=PushButton('恢复默认布局',self)
        self.reset_layout.setFixedHeight(28)
        self.reset_layout.clicked.connect(self.dock.reset_layout)
        footer.addWidget(self.reset_layout)
        layout.addLayout(footer)
        self.panel_set.stateChanged.connect(self.apply_state)
        self.dock.layoutChanged.connect(self._save_layout)
        try:
            saved=json.loads(str(settings.value('map/layout','{}')))
            if saved:self.dock.restore_layout(saved)
        except (TypeError,ValueError,KeyError):
            pass

    def _save_layout(self,state):
        self.settings.setValue('map/layout',_json(state))

    def set_session(self, session):
        source=Path(session.get('save_path','')) if session else None
        attached=bool(source and self._prefetch_path == source)
        if not attached:
            self._generation+=1
            for worker in self.workers:worker.requestInterruption()
            self._prefetch_path=None
            self._prefetch_snapshot=None
            self._prefetch_error=None
        self.session=session
        self.query=None
        self.result=None
        self._requested=attached
        self._awaiting_frame=False
        self._panel_presentation=None
        self.canvas.set_snapshot(MapSnapshot())
        self.surface.set_loading(False)
        self.status.clear()
        # Selections are save-local; docking is application-local.
        self.panel_set.set_state({'manual_line_ids':None,'company_ids':None,'modes':None,
                                  'layer_modes':None,'road_levels':None,'building_classes':None,'building_uses':None,
                                  'profit_statuses':None,'passenger_min':None,'passenger_max':None})
        try:
            saved=json.loads(str(self.settings.value('map/query/'+str(session.get('save_key','')),'{}')))
            if saved:self.panel_set.set_state(saved)
        except (ValueError,TypeError):pass
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
        self.canvas.fit_to_map()
        # A replacement save can arrive while the canvas is hidden and already
        # marked loaded. Keep its deferred resize fit for the actual dock size.
        if not self.canvas.isVisible():
            self.canvas._fit_pending=not isinstance(self.parentWidget(),QStackedWidget)
        self.canvas.prepare_frame()
        self.ready.emit()

    def _prepare_hidden_layout(self):
        """Lay out a stacked page before prewarming its first visible frame."""
        parent=self.parentWidget()
        if self.isVisible() or not isinstance(parent,QStackedWidget):
            return
        self.resize(parent.contentsRect().size())
        self.ensurePolished()
        self.layout().setGeometry(self.rect())
        self.dock.layout().setGeometry(self.dock.rect())
        # These are now the actual host bounds, so saved floating-panel clamps
        # and collapsed-dock widths can be resolved before the page is shown.
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
        self._panel_options=options
        self.panel_set.set_options(options)
        self._panel_presentation=(options['building_emphasis_effective'],self.panel_set.state().get('color_by','mode'))
        self.apply_state(self.panel_set.state())

    def _frame_ready(self):
        if self._awaiting_frame:
            self._awaiting_frame=False
            self.surface.set_loading(False)

    def _render_failed(self, message):
        self._awaiting_frame=False
        self.surface.set_loading(False)
        self.failed.emit(message)

    def apply_state(self,state):
        if state!=self.panel_set.state():
            self.panel_set.set_state(state)
        if self.query is None:return
        self.result=self.query.select(state)
        self.canvas.set_snapshot(self.result.snapshot)
        options={key: value for key,value in state.items() if key in self.canvas.options}
        options.update(route_colors=self.result.route_colors,building_colors=self.result.building_colors,
                       legend_items=self.query.legend_items(state,self.result))
        # Buildings were filtered in the immutable query; do not intersect the inactive category mode.
        options.update(building_classes=None,building_uses=None)
        self.canvas.set_options(**options)
        presentation=(self.result.building_emphasis,state.get('color_by','mode'))
        if presentation!=self._panel_presentation:
            self._panel_options.update(self.query.panel_options(self.session,state,self.result))
            self.panel_set.set_options(self._panel_options)
            self._panel_presentation=presentation
        city=self.session.get('metadata',{}).get('地图名称','')
        day=self._panel_options['passenger_date']
        modes=state.get('layer_modes')
        visible=sum(1 for route in self.result.routes if state.get('routes',True) and (modes is None or route.mode in modes))
        self.status.setText('   ·   '.join(str(v) for v in (city,day,f'显示 {visible} 条线路',f'已选 {len(self.result.routes)} 条') if v))
        key=str(self.session.get('save_key',''))
        if key:self.settings.setValue('map/query/'+key,_json(state))

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
