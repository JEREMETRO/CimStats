"""Window-internal map docking; never creates native or top-level windows."""
from __future__ import annotations
from copy import deepcopy
from PySide6.QtCore import QEvent, QPoint, QRect, Qt, Signal, QTimer
from PySide6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QStackedWidget, QApplication
from qfluentwidgets import BodyLabel, TransparentPushButton, Pivot, setCustomStyleSheet, TransparentToolButton, FluentIcon
import stats_tokens as tokens
from stats_typography import ui_font

_TITLES={'layers':'图层控制','filters':'线路筛选','display':'显示设置'}

class _ResizeGrip(QWidget):
    def __init__(self,frame,edges):
        super().__init__(frame); self.frame=frame; self.edges=edges; self.start=None
        self.setCursor(Qt.CursorShape.SizeFDiagCursor if len(edges)==2 else (Qt.CursorShape.SizeHorCursor if edges[0] in ('l','r') else Qt.CursorShape.SizeVerCursor))
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and not self.frame.pinned:
            self.start=event.globalPosition().toPoint(); self.original=self.frame.geometry(); event.accept()
    def mouseMoveEvent(self,event):
        if self.start is None:return
        delta=event.globalPosition().toPoint()-self.start; rect=QRect(self.original)
        for edge in self.edges:
            if edge=='r':rect.setRight(max(rect.left()+239,self.original.right()+delta.x()))
            elif edge=='l':rect.setLeft(min(rect.right()-239,self.original.left()+delta.x()))
            elif edge=='b':rect.setBottom(max(rect.top()+119,self.original.bottom()+delta.y()))
            else:rect.setTop(min(rect.bottom()-119,self.original.top()+delta.y()))
        self.frame.setGeometry(self.frame.host._clamp(rect)); event.accept()
    def mouseReleaseEvent(self,event):
        if self.start is not None:
            self.start=None; self.frame.expanded_geometry=QRect(self.frame.geometry()); self.frame.host._emit()

class _PanelFrame(QFrame):
    def __init__(self,host,key,panel):
        super().__init__(host); self.host=host; self.key=key; self.floating=False; self.pinned=False; self.collapsed=False
        self.expanded_geometry=QRect(32,32,360,520)
        self.setObjectName('mapPanelFrame')
        self.setStyleSheet(f'QFrame#mapPanelFrame {{background:{tokens.CARD_BG}; border:1px solid {tokens.BORDER_STRONG}; border-radius:{tokens.RADIUS_CONTROL}px;}}')
        layout=QVBoxLayout(self); layout.setContentsMargins(1,1,1,1); layout.setSpacing(0)
        self.header=QWidget(); row=QHBoxLayout(self.header); row.setContentsMargins(8,0,4,0); row.setSpacing(2)
        self.title=BodyLabel(_TITLES.get(key,panel.accessibleName() or key)); self.title.setFont(ui_font(tokens.FONT_SIZE_BODY))
        setCustomStyleSheet(self.title,f'QLabel {{color:{tokens.TEXT_PRIMARY};}}',f'QLabel {{color:{tokens.TEXT_PRIMARY};}}')
        self.title.setAccessibleName(self.title.text()); self.title.installEventFilter(host)
        host._drag_sources[self.title]=key
        row.addWidget(self.title,1)
        self.pin_button=TransparentPushButton('固定'); self.pin_button.setCheckable(True); self.pin_button.setFixedWidth(54)
        self.pin_button.clicked.connect(lambda checked:host.set_pinned(key,checked))
        self.collapse_button=TransparentPushButton('收起'); self.collapse_button.setFixedWidth(54)
        self.collapse_button.clicked.connect(lambda:host.set_panel_collapsed(key,not self.collapsed))
        row.addWidget(self.pin_button); row.addWidget(self.collapse_button); self.header.setFixedHeight(36)
        layout.addWidget(self.header); layout.addWidget(panel,1); self.panel=panel
        self.grips=[_ResizeGrip(self,e) for e in [('l',),('r',),('t',),('b',),('r','b')]]
        self.sync()
    def sync(self):
        self.pin_button.setVisible(self.floating); self.pin_button.setChecked(self.pinned)
        self.pin_button.setText('取消固定' if self.pinned else '固定'); self.pin_button.setFixedWidth(80 if self.pinned else 54)
        self.collapse_button.setText('展开' if self.collapsed else '收起')
        self.panel.setVisible(not self.collapsed)
        self.header.setVisible(self.floating)
        self.setStyleSheet(f'QFrame#mapPanelFrame {{background:{tokens.CARD_BG};border:{"1px solid "+tokens.BORDER if self.floating else "0"};border-radius:{tokens.RADIUS_CONTROL}px;}}')
        for grip in self.grips:grip.setVisible(self.floating and not self.pinned and not self.collapsed)
        if self.floating:
            self.setMinimumSize(240,38 if self.collapsed else 120)
            self.setMaximumHeight(38 if self.collapsed else 16777215)
        else:self.setMinimumSize(0,0); self.setMaximumHeight(16777215)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        w,h=self.width(),self.height()
        for grip,rect in zip(self.grips,[QRect(0,36,6,h-42),QRect(w-6,36,6,h-42),QRect(0,0,w,5),QRect(0,h-6,w,6),QRect(w-12,h-12,12,12)]):
            grip.setGeometry(rect); grip.raise_()

class MapDockHost(QWidget):
    """Host content and mapping of panels; layout state uses Qt logical pixels.

    Public imperative docking methods also support keyboard/menu integration.
    Only registered title/tab widgets initiate a panel drag.
    """
    layoutChanged=Signal(dict)
    def __init__(self,content,panels,parent=None):
        super().__init__(parent)
        self.content=content; self.panels=dict(panels); self._drag_sources={}; self._press=None; self._drag_key=None
        self._restoring=False; self._pending_layout=None; self._group_collapsed=False; self._active=next(iter(self.panels),'')
        self._dock_width=360
        layout=QHBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        layout.addWidget(content,1)
        self.dock=QFrame(); self.dock.setObjectName('mapDock')
        self.dock.setStyleSheet(f'QFrame#mapDock {{background:{tokens.CARD_BG};border-left:1px solid {tokens.BORDER};}}')
        self.dock.setFixedWidth(360); layout.addWidget(self.dock)
        dock_layout=QVBoxLayout(self.dock); dock_layout.setContentsMargins(2,2,2,2); dock_layout.setSpacing(2)
        self.group_button=TransparentToolButton(FluentIcon.CHEVRON_RIGHT); self.group_button.setFixedSize(32,32); self.group_button.setAccessibleName('收起面板')
        setCustomStyleSheet(self.group_button,'TransparentPushButton {padding:0px;}','TransparentPushButton {padding:0px;}')
        self.group_button.clicked.connect(lambda:self.set_group_collapsed(not self._group_collapsed))
        self.tabs_widget=Pivot(); self.tabs_widget.setItemFontSize(tokens.FONT_SIZE_BODY)
        self.tabs_widget.currentItemChanged.connect(self.activate_panel)
        self.dock_bar=QWidget(); bar_layout=QHBoxLayout(self.dock_bar); bar_layout.setContentsMargins(0,0,0,0); bar_layout.setSpacing(0)
        bar_layout.addWidget(self.tabs_widget,1); bar_layout.addWidget(self.group_button)
        dock_layout.addWidget(self.dock_bar); self.tabs={}
        self.rail=QWidget(); rail_layout=QVBoxLayout(self.rail); rail_layout.setContentsMargins(0,0,0,0)
        self.rail.hide(); dock_layout.addWidget(self.rail); self.rail_buttons={}
        self.stack=QStackedWidget(); dock_layout.addWidget(self.stack,1)
        self.frames={}
        for key,panel in self.panels.items():
            tab=self.tabs_widget.addItem(key,_TITLES.get(key,panel.accessibleName() or key)); tab.setFont(ui_font(tokens.FONT_SIZE_BODY))
            tab.setStyleSheet(f'QPushButton {{background:transparent;border:0;outline:0;padding:8px 7px;color:{tokens.TEXT_SECONDARY};}} QPushButton[isSelected="true"] {{color:{tokens.ACCENT};}}')
            tab.installEventFilter(self); self._drag_sources[tab]=key; self.tabs[key]=tab
            rail_button=TransparentPushButton('\n'.join(_TITLES.get(key,key)))
            rail_button.clicked.connect(lambda checked=False,k=key:self.activate_panel(k))
            rail_button.setFixedHeight(90); rail_layout.addWidget(rail_button); self.rail_buttons[key]=rail_button
            frame=_PanelFrame(self,key,panel); self.frames[key]=frame; self.stack.addWidget(frame)
        rail_layout.addStretch(1)
        self.preview=QFrame(self); self.preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.preview.setStyleSheet(f'background:{tokens.ACCENT_SOFT};border:2px solid {tokens.ACCENT};border-radius:6px;'); self.preview.hide()
        if self._active:self.activate_panel(self._active)

    def _emit(self):
        if not self._restoring and self._pending_layout is None:self.layoutChanged.emit(self.layout_state())

    def activate_panel(self,key):
        if key not in self.frames:return
        frame=self.frames[key]
        if frame.floating:frame.show(); frame.raise_(); return
        self._active=key
        if self._group_collapsed:self.set_group_collapsed(False)
        self.stack.setCurrentWidget(frame)
        self.tabs_widget.blockSignals(True); self.tabs_widget.setCurrentItem(key); self.tabs_widget.blockSignals(False)
        self._emit()

    def _clamp(self,rect):
        width=min(max(240,rect.width()),max(1,self.width()))
        height=min(max(38,rect.height()),max(1,self.height()))
        return QRect(min(max(0,rect.x()),max(0,self.width()-width)),min(max(0,rect.y()),max(0,self.height()-height)),width,height)

    def float_panel(self,key,geometry=None):
        frame=self.frames[key]
        if not frame.floating:
            self.stack.removeWidget(frame); frame.setParent(self); frame.floating=True
            candidates=[k for k,f in self.frames.items() if not f.floating]
            if candidates:self.activate_panel(candidates[0])
        rect=QRect(geometry if geometry is not None else frame.expanded_geometry)
        frame.sync(); frame.setGeometry(self._clamp(rect)); frame.show(); frame.raise_()
        frame.expanded_geometry=QRect(frame.geometry()); self._emit()

    def dock_panel(self,key):
        frame=self.frames[key]; frame.floating=False; frame.collapsed=False; frame.sync()
        self.stack.addWidget(frame); self.activate_panel(key); self.preview.hide(); self._emit()

    def set_pinned(self,key,pinned):
        frame=self.frames[key]; frame.pinned=bool(pinned); frame.sync(); self._emit()

    def set_panel_collapsed(self,key,collapsed):
        frame=self.frames[key]
        if not frame.floating:
            self.set_group_collapsed(collapsed); return
        if frame.collapsed==bool(collapsed):return
        if frame.floating and not frame.collapsed:frame.expanded_geometry=QRect(frame.geometry())
        frame.collapsed=bool(collapsed); frame.sync()
        if frame.floating:
            rect=QRect(frame.expanded_geometry)
            if frame.collapsed:rect.setHeight(38)
            frame.setGeometry(self._clamp(rect))
        self._emit()

    def set_group_collapsed(self,collapsed):
        self._group_collapsed=bool(collapsed)
        self.dock.setFixedWidth(44 if collapsed else min(self._dock_width,max(240,self.width()-200)))
        self.stack.setVisible(not collapsed)
        self.tabs_widget.setVisible(not collapsed); self.rail.setVisible(collapsed)
        self.group_button.setIcon(FluentIcon.LEFT_ARROW if collapsed else FluentIcon.CHEVRON_RIGHT)
        self.group_button.setAccessibleName('展开面板' if collapsed else '收起面板')
        self._emit()

    def layout_state(self):
        state={'version':1,'active':self._active,'group_collapsed':self._group_collapsed,'dock_width':self._dock_width,
                'viewport':[self.width(),self.height()], 'dpi':self.devicePixelRatioF(),
                'panels':{k:{'floating':f.floating,'pinned':f.pinned,'collapsed':f.collapsed,
                             'geometry':[f.x(),f.y(),f.width(),f.height()],
                             'expanded_geometry':[f.expanded_geometry.x(),f.expanded_geometry.y(),f.expanded_geometry.width(),f.expanded_geometry.height()]}
                          for k,f in self.frames.items()}}
        if self._pending_layout is not None:
            # Report saved bounds while hidden, never constructor-sized frames.
            pending=deepcopy(self._pending_layout)
            state.update({key:value for key,value in pending.items() if key!='panels'})
            for key,saved in pending.get('panels',{}).items():
                if key in state['panels']:state['panels'][key].update(saved)
        return state

    def restore_layout(self,state):
        if not self.isVisible():
            # A page can be constructed at 100x30 or hidden in a stacked shell.
            # Preserve its saved logical coordinates until the final parent layout.
            self._pending_layout=deepcopy(state)
            return
        self._pending_layout=None
        self._apply_layout(state)

    def _apply_pending_layout(self):
        if self._pending_layout is None or not self.isVisible():return
        saved=self._pending_layout
        self._pending_layout=None
        self._apply_layout(saved)

    def _apply_layout(self,state):
        self._restoring=True
        try:
            self._dock_width=max(240,min(600,int(state.get('dock_width',360))))
            for key,saved in state.get('panels',{}).items():
                if key not in self.frames:continue
                frame=self.frames[key]
                if saved.get('floating'):self.float_panel(key,QRect(*saved.get('geometry',[32,32,360,520])))
                else:self.dock_panel(key)
                self.set_pinned(key,saved.get('pinned',False)); self.set_panel_collapsed(key,saved.get('collapsed',False))
                # Collapse captures live geometry; install saved expanded bounds afterwards.
                frame.expanded_geometry=self._clamp(QRect(*saved.get('expanded_geometry',saved.get('geometry',[32,32,360,520]))))
            active=state.get('active',self._active)
            if active in self.frames:self.activate_panel(active)
            self.set_group_collapsed(state.get('group_collapsed',False))
        finally:self._restoring=False
        self._emit()

    def reset_layout(self):
        self.restore_layout({'active':next(iter(self.frames),''),'dock_width':360,'group_collapsed':False,
                            'panels':{k:{'floating':False,'pinned':False,'collapsed':False} for k in self.frames}})

    def showEvent(self,event):
        super().showEvent(event)
        if self._pending_layout is not None:
            QTimer.singleShot(0,self._apply_pending_layout)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if not hasattr(self,'frames'):return
        if self._pending_layout is not None:
            if self.isVisible():QTimer.singleShot(0,self._apply_pending_layout)
            return
        for frame in self.frames.values():
            if frame.floating:
                frame.setGeometry(self._clamp(frame.geometry()))
                frame.expanded_geometry=self._clamp(frame.expanded_geometry)
        if self.preview.isVisible():self._show_preview()
        self._emit()

    def _show_preview(self):
        self.preview.setGeometry(max(0,self.width()-self._dock_width),0,min(self.width(),self._dock_width),self.height())
        self.preview.show(); self.preview.raise_()

    def eventFilter(self,watched,event):
        key=self._drag_sources.get(watched)
        if key is None or key not in self.frames:return super().eventFilter(watched,event)
        frame=self.frames[key]
        if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.LeftButton:
            if frame.pinned and frame.floating:return False
            self._press=event.globalPosition().toPoint(); self._origin=frame.geometry(); self._drag_key=key; self._started=False; self._redock=False
            if frame.floating:frame.raise_()
        elif event.type()==QEvent.Type.MouseMove and self._press is not None and self._drag_key==key:
            point=event.globalPosition().toPoint(); delta=point-self._press
            if not self._started and delta.manhattanLength()<QApplication.startDragDistance():return False
            if not self._started:
                self._started=True
                if not frame.floating:
                    pos=self.mapFromGlobal(point)-QPoint(100,18)
                    self.float_panel(key,QRect(pos.x(),pos.y(),360,min(520,self.height())))
                    self._origin=frame.geometry(); self._press=point
                else:frame.setGeometry(self._clamp(self._origin.translated(delta)))
            else:frame.setGeometry(self._clamp(self._origin.translated(delta)))
            local=self.mapFromGlobal(point)
            self._redock=local.x()>=self.width()-min(100,self.dock.width()) and self.rect().contains(local)
            if self._redock:self._show_preview()
            else:self.preview.hide()
            return True
        elif event.type()==QEvent.Type.MouseButtonRelease and self._drag_key==key:
            moved=getattr(self,'_started',False)
            if moved:
                if getattr(self,'_redock',False):self.dock_panel(key)
                elif frame.floating and not frame.collapsed:frame.expanded_geometry=QRect(frame.geometry())
                self._emit()
            self._press=None; self._drag_key=None; self.preview.hide()
            if moved:return True
        return super().eventFilter(watched,event)
