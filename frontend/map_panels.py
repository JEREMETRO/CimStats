"""Fluent map controls. Panels own presentation state, never save-game data."""
from __future__ import annotations
from copy import deepcopy
from math import isfinite, sqrt
from datetime import datetime,timedelta
import re
from PySide6.QtCore import Qt, Signal, QRect, QSize, QDateTime
from PySide6.QtGui import QColor, QIcon, QPixmap, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidgetItem, QAbstractItemView, QFrame, QGridLayout, QButtonGroup, QSizePolicy
from qfluentwidgets import CheckBox, ComboBox, LineEdit, PushButton, ListWidget, BodyLabel, RadioButton, FluentIcon, TransparentPushButton, CompactDoubleSpinBox, setCustomStyleSheet
from qfluentwidgets.components.widgets.slider import SliderHandle
from stats_controls import StatisticsScrollArea, button_text_size
from stats_typography import ui_font
import stats_tokens as tokens
from semantic_colors import PROFIT, category, building_function_fill, map_fill
from map_model import BuildingFunctionValues
from display_rules import display_mode, format_number, truncated_number
from map_line_labels import resolve_line_labels
from ui_kit import FlowLayout
from map_canvas import ROAD_STYLES

_SET_KEYS = ('road_levels', 'building_classes', 'building_uses', 'layer_modes', 'modes', 'company_ids', 'manual_line_ids', 'profit_statuses')
_DEFAULTS = dict(roads=True, buildings=True, routes=True, **{k:None for k in _SET_KEYS},
    passenger_min=None, passenger_max=None, building_color_by='class', building_class_target=None,
    building_metric='density', direction='whole', color_by='mode', interval_mode='daytime', priority_by='mode',
    passenger_desc=True, mode_order=[], company_order=[], deadhead=False, stops=True,
    stop_names=False, line_numbers=False, mode_widths={}, distinguish_directions=False, building_emphasis=None,
    service_time_mode='off', service_start=None, service_end=None)
_PROFITS = [dict(id=entry.key, name=entry.name, color=entry.color) for entry in PROFIT]
_FILTER_BLOCK_KEYS = {
    'company_ids':('company_ids',), 'modes':('modes',), 'profit_statuses':('profit_statuses',),
    'passengers':('passenger_min','passenger_max'),
    'service':('service_time_mode','service_start','service_end'),
    'manual_line_ids':('manual_line_ids',),
}
_FILTER_OWNER = {key:block for block,keys in _FILTER_BLOCK_KEYS.items() for key in keys}

class _WrappedList(ListWidget):
    """Keep the Fluent delegate, with actual row heights for wrapped names."""
    def wrap_items(self):
        blocked=self.blockSignals(True)
        width=max(80,self.viewport().width()-70)
        try:
            for i in range(self.count()):
                item=self.item(i)
                bounds=QFontMetrics(item.font()).boundingRect(QRect(0,0,width,10000),int(Qt.TextFlag.TextWordWrap),item.text())
                size=QSize(max(1,self.viewport().width()-4),max(26,bounds.height()+6))
                if item.sizeHint()!=size:item.setSizeHint(size)
            cap=self.property('heightCap')
            if cap is not None:
                height=sum(self.item(i).sizeHint().height()+6 for i in range(self.count()))+6
                self.setFixedHeight(min(int(cap),max(32,height)))
        finally:self.blockSignals(blocked)
    def resizeEvent(self,event):
        super().resizeEvent(event); self.wrap_items()


class _SingleLineList(_WrappedList):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWordWrap(False);self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    def wrap_items(self):
        blocked=self.blockSignals(True)
        try:
            height=0
            for i in range(self.count()):
                item=self.item(i);row_height=max(28,QFontMetrics(item.font()).height()+8)
                item.setSizeHint(QSize(max(1,self.viewport().width()-4),row_height));height+=row_height+6
            cap=self.property('heightCap')
            if cap is not None:self.setFixedHeight(min(int(cap),max(32,height+6)))
        finally:self.blockSignals(blocked)


def _style_control(widget, size=tokens.FONT_SIZE_BODY, color=tokens.TEXT_PRIMARY):
    widget.setFont(ui_font(size))
    if hasattr(widget,'setTextColor'):widget.setTextColor(QColor(color),QColor(color))
    rule=f'QLabel, RadioButton, CheckBox, ComboBox, LineEdit, PushButton, ListWidget, CompactDoubleSpinBox {{color:{color};font-family:"{tokens.FONT_FAMILY}";font-size:{size}px;}}'
    setCustomStyleSheet(widget,rule,rule)
    return widget

class _ChoiceGroup(QWidget):
    changed=Signal(object)
    def __init__(self,choices,columns=1,parent=None):
        super().__init__(parent)
        grid=QGridLayout(self); grid.setContentsMargins(0,0,0,0); grid.setSpacing(4)
        self.buttons={}; self.group=QButtonGroup(self); self.group.setExclusive(True)
        for index,(key,text) in enumerate(choices):
            button=_style_control(RadioButton(text)); button.setMinimumHeight(28)
            self.buttons[key]=button; self.group.addButton(button)
            button.clicked.connect(lambda checked,k=key:self.changed.emit(k) if checked else None)
            grid.addWidget(button,index//columns,index%columns)
    def set_value(self,value):
        if value in self.buttons:self.buttons[value].setChecked(True)


class _RangeHandle(SliderHandle):
    def __init__(self,axis,index):
        super().__init__(axis);self.axis=axis;self.index=index
        self.setHandleColor(tokens.ACCENT,tokens.ACCENT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason);self.axis._drag=self.index
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.axis._drag==self.index:
            self.axis._move_to(self.index,self.axis.mapFromGlobal(event.globalPosition().toPoint()).x());event.accept()
        else:super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        self.axis._drag=None;super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        keys={Qt.Key.Key_Left:-1,Qt.Key.Key_Down:-1,Qt.Key.Key_Right:1,Qt.Key.Key_Up:1,
              Qt.Key.Key_PageDown:-self.axis.page_step,Qt.Key.Key_PageUp:self.axis.page_step}
        value=self.axis.values()[self.index]
        if event.key() in keys:value+=keys[event.key()]
        elif event.key()==Qt.Key.Key_Home:value=0
        elif event.key()==Qt.Key.Key_End:value=self.axis.maximum
        else:super().keyPressEvent(event);return
        self.axis._change(self.index,value);event.accept()


class _RangeAxis(QWidget):
    """Independent named endpoints; wrapped selections are drawn as two ends."""
    valueChanged=Signal(int,int)
    def __init__(self,maximum,ticks,accessible,parent=None):
        super().__init__(parent);self.maximum=maximum;self.page_step=60 if maximum==1440 else 1
        self._values=(0,maximum);self._single=False;self._drag=None;self.ticks=ticks
        self.endpoint_labels=('开始','结束');self.show_endpoint_labels=True
        self.setAccessibleName(accessible)
        self.handles=[_RangeHandle(self,i) for i in (0,1)]
        for i,handle in enumerate(self.handles):handle.setAccessibleName(('开始' if i==0 else '结束')+accessible)
    @property
    def show_endpoint_labels(self):return self._show_endpoint_labels
    @show_endpoint_labels.setter
    def show_endpoint_labels(self,visible):
        self._show_endpoint_labels=bool(visible);self.setFixedHeight(self.track_y+31)
        if hasattr(self,'handles'):self._place_handles()
    @property
    def track_y(self):return 28 if self.show_endpoint_labels else 20
    def values(self):return self._values
    def set_values(self,start,end):
        self._values=(min(self.maximum,max(0,int(start))),min(self.maximum,max(0,int(end))))
        self._place_handles();self.update()
    def set_single(self,single):
        self._single=bool(single);self.handles[1].setVisible(not single);self.handles[1].setEnabled(not single);self.update()
    def _x(self,value):return 12+(max(1,self.width()-24))*value/self.maximum
    def _place_handles(self):
        for handle,value in zip(self.handles,self._values):handle.move(round(self._x(value))-11,self.track_y-11)
    def resizeEvent(self,event):super().resizeEvent(event);self._place_handles()
    def _change(self,index,value):
        if index==1 and self._single:return
        values=list(self._values);values[index]=min(self.maximum,max(0,int(value)))
        if tuple(values)!=self._values:self.set_values(*values);self.valueChanged.emit(*values)
    def _move_to(self,index,x):
        self._change(index,round((x-12)*self.maximum/max(1,self.width()-24)))
    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:super().mousePressEvent(event);return
        candidates=(0,) if self._single else (0,1)
        self._drag=min(candidates,key=lambda i:abs(event.position().x()-self._x(self._values[i])))
        self.handles[self._drag].setFocus(Qt.FocusReason.MouseFocusReason);self._move_to(self._drag,event.position().x());event.accept()
    def mouseMoveEvent(self,event):
        if self._drag is not None:self._move_to(self._drag,event.position().x());event.accept()
        else:super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):self._drag=None;event.accept()
    def wheelEvent(self,event):event.accept()
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(tokens.BORDER_STRONG),4,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        painter.drawLine(12,self.track_y,self.width()-12,self.track_y)
        first,last=self._values
        painter.setPen(QPen(QColor(tokens.ACCENT),4,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        if not self._single:
            segments=((first,last),) if first<=last else ((0,last),(first,self.maximum))
            for a,b in segments:painter.drawLine(round(self._x(a)),self.track_y,round(self._x(b)),self.track_y)
        painter.setFont(ui_font(tokens.FONT_SIZE_CAPTION));painter.setPen(QColor(tokens.TEXT_SECONDARY))
        names=[(first,self.endpoint_labels[0])] if self._single else list(zip((first,last),self.endpoint_labels))
        if not self._single and abs(self._x(first)-self._x(last))<36:names=[(first,'/'.join(self.endpoint_labels))]
        if not self.show_endpoint_labels:names=[]
        for value,text in names:
            width=70 if '/' in text else 36;x=min(max(0,round(self._x(value)-width/2)),max(0,self.width()-width))
            painter.drawText(QRect(x,0,width,16),Qt.AlignmentFlag.AlignCenter,text)
        for value,text in self.ticks:
            x=min(max(0,round(self._x(value)-20)),max(0,self.width()-40))
            painter.drawText(QRect(x,self.track_y+13,40,18),Qt.AlignmentFlag.AlignCenter,text)


def _local_datetime(value):
    if isinstance(value,datetime):return value
    try:return datetime.fromisoformat(str(value))
    except (ValueError,TypeError):return None


class _ServiceTimeEditor(QWidget):
    edited=Signal(str,str)
    def __init__(self,parent=None):
        super().__init__(parent);self._clock=None;self._start_date=None;self._end_date=None;self._setting=False;self._mode='off'
        box=QVBoxLayout(self);box.setContentsMargins(0,0,0,0);box.setSpacing(4)
        self.week_axis=_RangeAxis(6,list(enumerate(('周一','周二','周三','周四','周五','周六','周日'))),'星期')
        box.addWidget(self.week_axis);row=QHBoxLayout();row.setSpacing(8)
        self.labels={}
        for key,text in [('start','开始时间'),('end','结束时间')]:
            host=QWidget();column=QVBoxLayout(host);column.setContentsMargins(0,0,0,0);column.setSpacing(4)
            caption=_style_control(BodyLabel(text),tokens.FONT_SIZE_CAPTION,tokens.TEXT_SECONDARY);column.addWidget(caption);self.labels[key]=caption
            edit=_style_control(LineEdit());edit.setPlaceholderText('HH:mm');edit.setAccessibleName(text);edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit.textChanged.connect(self._time_changed);column.addWidget(edit,1);row.addWidget(host);setattr(self,key+'_edit',edit)
        box.addLayout(row)
        self.time_axis=_RangeAxis(1440,[(0,'00'),(360,'06'),(720,'12'),(1080,'18'),(1440,'24')],'时间')
        self.time_axis.show_endpoint_labels=False
        box.addWidget(self.time_axis)
        self.summary=_style_control(BodyLabel(''),tokens.FONT_SIZE_CAPTION,tokens.TEXT_SECONDARY);self.summary.setWordWrap(True);box.addWidget(self.summary)
        self.error_label=_style_control(BodyLabel(''),tokens.FONT_SIZE_CAPTION,tokens.ERROR_COLOR);self.error_label.setWordWrap(True);self.error_label.hide();box.addWidget(self.error_label)
        self.week_axis.valueChanged.connect(self._weekday_changed);self.time_axis.valueChanged.connect(self._axis_time_changed)
    @staticmethod
    def _minutes(text):
        if text=='24:00':return 1440
        if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',text):return None
        hours,minutes=map(int,text.split(':'));return hours*60+minutes
    @staticmethod
    def _text(minutes):return f'{minutes//60:02d}:{minutes%60:02d}'
    def _error(self,text):self.error_label.setText(text);self.error_label.setVisible(bool(text))
    def set_state(self,state,clock):
        self._clock=_local_datetime(clock)
        start=_local_datetime(state.get('service_start')) or self._clock
        end=_local_datetime(state.get('service_end')) or (start+timedelta(hours=1) if start else None)
        current=self.values(show_error=False)
        wanted=(start.isoformat(timespec='seconds'),end.isoformat(timespec='seconds')) if start and end else None
        if wanted!=current:
            self._setting=True
            try:
                self._start_date=start.date() if start else None;self._end_date=end.date() if end else None
                self.start_edit.setText(start.strftime('%H:%M') if start else '')
                self.end_edit.setText(end.strftime('%H:%M') if end else '')
                self.time_axis.set_values(start.hour*60+start.minute if start else 0,end.hour*60+end.minute if end else 60)
                self.week_axis.set_values(start.weekday() if start else 0,end.weekday() if end else 0)
            finally:self._setting=False
        self.set_mode(state.get('service_time_mode','off'));self._summary()
    def set_mode(self,mode):
        self._mode=mode;self.setVisible(mode!='off');valid=self._start_date is not None
        if mode!='range' and self._minutes(self.end_edit.text()) is None:
            self._setting=True
            try:self.end_edit.setText(self._text(self.time_axis.values()[1]))
            finally:self._setting=False
        self.start_edit.setEnabled(valid);self.end_edit.setEnabled(valid and mode=='range')
        for axis in (self.week_axis,self.time_axis):axis.setEnabled(valid);axis.set_single(mode!='range')
        if mode=='off':self._error('')
    def values(self,show_error=True):
        first,last=self._minutes(self.start_edit.text()),self._minutes(self.end_edit.text())
        if last is None and self._mode!='range':last=self.time_axis.values()[1]
        if self._start_date is None or self._end_date is None:
            if show_error:self._error('模拟日期不可用')
            return None
        if first is None or last is None:
            if show_error:self._error('请输入有效的 HH:mm 时间')
            return None
        start=datetime.combine(self._start_date,datetime.min.time())+timedelta(minutes=first)
        end=datetime.combine(self._end_date,datetime.min.time())+timedelta(minutes=last)
        if self._mode=='range' and end<start and self._end_date==self._start_date:end+=timedelta(days=1)
        if end<=start and self._mode=='range':
            if show_error:self._error('结束时间须晚于开始时间')
            return None
        if show_error:self._error('')
        return start.isoformat(timespec='seconds'),end.isoformat(timespec='seconds')
    def _summary(self):
        values=self.values(show_error=False)
        if values:self.summary.setText(' — '.join(value.replace('T',' ')[:16] for value in values) if self._mode=='range' else values[0].replace('T',' ')[:16])
        else:self.summary.clear()
    def _publish(self):
        values=self.values()
        if values is None:return
        start,end=map(datetime.fromisoformat,values)
        self._start_date=start.date()
        if self._mode=='range':self._end_date=end.date()
        if self._minutes(self.start_edit.text())==1440 or self._minutes(self.end_edit.text())==1440:
            self._setting=True
            try:
                self.start_edit.setText(start.strftime('%H:%M'));self.end_edit.setText(end.strftime('%H:%M'))
                self.time_axis.set_values(start.hour*60+start.minute,end.hour*60+end.minute)
            finally:self._setting=False
        self.week_axis.set_values(start.weekday(),end.weekday());self._summary();self.edited.emit(*values)
    def _time_changed(self,*_):
        if self._setting:return
        values=self.values()
        if values is None:return
        self.time_axis.set_values(self._minutes(self.start_edit.text()),self._minutes(self.end_edit.text()));self._publish()
    def _axis_time_changed(self,start,end):
        self._setting=True
        try:self.start_edit.setText(self._text(start));self.end_edit.setText(self._text(end))
        finally:self._setting=False
        self._publish()
    def _weekday_changed(self,start,end):
        anchor=self._clock or (datetime.combine(self._start_date,datetime.min.time()) if self._start_date else None)
        if anchor is None:return
        monday=anchor.date()-timedelta(days=anchor.weekday())
        self._start_date=monday+timedelta(days=start)
        if self._mode=='range':self._end_date=monday+timedelta(days=end+7 if end<start else end)
        self._publish()


class _RoadSample(QWidget):
    def __init__(self,key,parent=None):
        super().__init__(parent); self.key=key; self.setFixedSize(16,16)
    def paintEvent(self,event):
        fill,shell,overview,detail=ROAD_STYLES.get(self.key,ROAD_STYLES['unknown'])
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(shell),detail+2)); painter.drawLine(1,8,15,8)
        painter.setPen(QPen(QColor(fill),detail)); painter.drawLine(1,8,15,8)

class _OptionCell(QWidget):
    def __init__(self,choice,road=False,parent=None):
        super().__init__(parent)
        row=QHBoxLayout(self); row.setContentsMargins(0,0,0,0); row.setSpacing(3)
        self.check=_style_control(CheckBox('')); self.check.setFixedWidth(22); self.check.setMinimumHeight(30)
        self.check.setAccessibleName(choice['name']); row.addWidget(self.check)
        if road:sample=_RoadSample(choice['id'])
        else:
            sample=QFrame(); sample.setFixedSize(8,8)
            sample.setStyleSheet(f'background:{choice.get("color",tokens.TEXT_SECONDARY)};border:0;')
        sample.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents); row.addWidget(sample)
        label=_style_control(BodyLabel(choice['name'])); label.setWordWrap(True)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents); row.addWidget(label,1)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.check.click(); event.accept()
        else:super().mouseReleaseEvent(event)

class _OptionGrid(QWidget):
    changed=Signal()
    def __init__(self,key,parent=None):
        super().__init__(parent); self.key=key; self.buttons={}; self.expanded=True; self._choices=[]
        self.layout_box=QVBoxLayout(self); self.layout_box.setContentsMargins(0,0,0,0); self.layout_box.setSpacing(3)
    def populate(self,choices,selected):
        if choices==self._choices:
            for key,button in self.buttons.items():button.setChecked(key in selected)
            return
        self._choices=deepcopy(choices)
        while self.layout_box.count():
            item=self.layout_box.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.buttons={}
        groups=[choices]
        if self.key=='building_classes':
            groups=[[v for v in choices if v['id'] not in ('transport','special','unknown')],
                    [v for v in choices if v['id'] in ('transport','special','unknown')]]
        for group_index,group in enumerate(groups):
            if not group:continue
            widget=QWidget(); grid=QGridLayout(widget); grid.setContentsMargins(0,0,0,0); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(2)
            if self.key=='building_classes' and group_index==0:
                header=_style_control(TransparentPushButton('社会群体',icon=FluentIcon.CHEVRON_DOWN_MED if self.expanded else FluentIcon.CHEVRON_RIGHT))
                self.layout_box.addWidget(header); widget.setVisible(self.expanded)
                def toggle(checked=False,target=widget,button=header):
                    self.expanded=not self.expanded; target.setVisible(self.expanded)
                    button.setIcon(FluentIcon.CHEVRON_DOWN_MED if self.expanded else FluentIcon.CHEVRON_RIGHT)
                header.clicked.connect(toggle)
            for i,choice in enumerate(group):
                cell=_OptionCell(choice,self.key=='road_levels'); cell.check.setChecked(choice['id'] in selected)
                self.buttons[choice['id']]=cell.check
                cell.check.clicked.connect(lambda checked:self.changed.emit())
                grid.addWidget(cell,i//2,i%2)
            self.layout_box.addWidget(widget)
    def selected(self):return {key for key,button in self.buttons.items() if button.isChecked()}


def _clean_widths(values):
    result={}
    for key,value in values.items():
        try:width=float(value)
        except (ValueError,TypeError):continue
        if isfinite(width) and width>0:result[key]=round(min(12.,max(.5,width)),1)
    return result

class _ModeWidths(QWidget):
    changed=Signal(dict)
    def __init__(self,parent=None):
        super().__init__(parent); self.spins={}; self._choices=[]; self._values={}
        self.grid=QGridLayout(self); self.grid.setContentsMargins(0,0,0,0); self.grid.setSpacing(4)
    def populate(self,choices,values):
        self._values=deepcopy(values)
        if choices!=self._choices:
            self._choices=deepcopy(choices)
            while self.grid.count():
                item=self.grid.takeAt(0)
                if item.widget():item.widget().deleteLater()
            self.spins={}
            for i,choice in enumerate(choices):
                row_widget=QWidget(); row=QHBoxLayout(row_widget); row.setContentsMargins(0,0,0,0); row.setSpacing(3)
                swatch=QFrame(); swatch.setFixedSize(8,8)
                swatch.setStyleSheet(f'background:{choice.get("color",tokens.TEXT_SECONDARY)};border:0;')
                row.addWidget(swatch)
                label=_style_control(BodyLabel(choice['name']),tokens.FONT_SIZE_CAPTION); label.setWordWrap(True); row.addWidget(label,1)
                spin=_style_control(CompactDoubleSpinBox(),tokens.FONT_SIZE_CAPTION); spin.setRange(0.,12.); spin.setDecimals(1); spin.setSingleStep(.5)
                spin.setSpecialValueText('自动'); spin.setSuffix(' px'); spin.setFixedWidth(88)
                spin.setAccessibleName(f"{choice['name']}线路粗细")
                spin.valueChanged.connect(lambda value,key=choice['id']:self._edit(key,value))
                row.addWidget(spin); self.spins[choice['id']]=spin; self.grid.addWidget(row_widget,i//2,i%2)
        for key,spin in self.spins.items():
            spin.blockSignals(True); spin.setValue(values.get(key,0.)); spin.blockSignals(False)
    def _edit(self,key,value):
        values=deepcopy(self._values)
        if value<=0:values.pop(key,None)
        else:values[key]=value
        self._values=values; self.changed.emit(deepcopy(values))


class _FilterSection(QFrame):
    """The block header only changes visibility; confirmation is a separate action."""
    def __init__(self,title,parent=None):
        super().__init__(parent);self._title=title;self.setObjectName('mapFilterSection')
        self.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Maximum)
        self.setStyleSheet(f'QFrame#mapFilterSection {{background:{tokens.SURFACE_SUBTLE};border:0;border-radius:{tokens.RADIUS_CONTROL}px;}}')
        layout=QVBoxLayout(self);layout.setContentsMargins(10,6,10,6);layout.setSpacing(4)
        self.toggle=_style_control(TransparentPushButton(''));self.toggle.setAccessibleName(f'展开或折叠{title}')
        header=QHBoxLayout(self.toggle);header.setContentsMargins(0,0,0,0);header.setSpacing(8)
        self.title_label=_style_control(BodyLabel(title));self.arrow_label=_style_control(BodyLabel(''))
        for label in (self.title_label,self.arrow_label):label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        self.arrow_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.title_label);header.addStretch(1);header.addWidget(self.arrow_label)
        layout.addWidget(self.toggle)
        self.summary_label=_style_control(BodyLabel(''),tokens.FONT_SIZE_CAPTION,tokens.TEXT_SECONDARY)
        self.summary_label.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Maximum)
        self.summary_label.setWordWrap(True);self.summary_label.hide();layout.addWidget(self.summary_label)
        self.body=QWidget();self.body_layout=QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0,0,0,0);self.body_layout.setSpacing(6);layout.addWidget(self.body)
        self.apply_button=_style_control(PushButton('确定'));self.apply_button.setAccessibleName(f'确定{title}筛选')
        self.toggle.clicked.connect(lambda:self.set_expanded(not self.is_expanded()))
        self.set_expanded(False)
    def is_expanded(self):return not self.body.isHidden()
    def set_expanded(self,expanded):
        self.body.setVisible(bool(expanded));self.arrow_label.setText('▾' if expanded else '▸')
    def set_summary(self,text):
        self.summary_label.setText(text);self.summary_label.setVisible(bool(text))


class _PassengerAxis(_RangeAxis):
    finite_maximum=1000
    @classmethod
    def position(cls,value):return min(cls.finite_maximum,max(0,round(sqrt(max(0,value)/50000)*cls.finite_maximum)))
    @classmethod
    def passenger_value(cls,value):return 50000*value**2/cls.finite_maximum**2
    def __init__(self):
        super().__init__(1100,[(0,'0'),(self.position(10000),'1万'),(self.position(30000),'3万'),(1100,'∞')],'客流')
        self.endpoint_labels=('下限','上限');self.show_endpoint_labels=False
        for handle,name in zip(self.handles,('客流下限','客流上限')):handle.setAccessibleName(name)
    def _change(self,index,value):
        first,last=self.values()
        if index==0:value=min(last,self.finite_maximum,value)
        else:
            if last==self.maximum and value==self.maximum-1:value=self.finite_maximum
            elif value>self.finite_maximum:value=self.maximum
            value=max(first,value)
        super()._change(index,value)


class _PassengerRangeEditor(QWidget):
    changed=Signal(object,object)
    def __init__(self,parent=None):
        super().__init__(parent);self._setting=False
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(4)
        row=QHBoxLayout();row.setSpacing(8);layout.addLayout(row)
        for key,title in [('min','最少人次'),('max','最多人次')]:
            host=QWidget();column=QVBoxLayout(host);column.setContentsMargins(0,0,0,0);column.setSpacing(4)
            column.addWidget(_style_control(BodyLabel(title),tokens.FONT_SIZE_CAPTION,tokens.TEXT_SECONDARY))
            edit=_style_control(LineEdit());edit.setAccessibleName(title);column.addWidget(edit);row.addWidget(host,1)
            edit.editingFinished.connect(self._typed);setattr(self,key+'_edit',edit)
        self.axis=_PassengerAxis();layout.addWidget(self.axis);self.axis.valueChanged.connect(self._slid)
        self.error_label=_style_control(BodyLabel(''),tokens.FONT_SIZE_CAPTION,tokens.ERROR_COLOR)
        self.error_label.setWordWrap(True);self.error_label.hide();layout.addWidget(self.error_label)
    def values(self):
        try:
            values=[]
            for index,edit in enumerate((self.min_edit,self.max_edit)):
                text=edit.text().strip().replace(',','')
                if index==1 and text in ('','∞','不限'):value=None
                else:
                    value=truncated_number(float(text or '0'))
                    if value is None or value<0:raise ValueError
                    value=float(value)
                values.append(value)
            if values[1] is not None and values[0]>values[1]:raise ValueError
        except (TypeError,ValueError,OverflowError):
            self.error_label.setText('请输入有效范围，上限不得小于下限');self.error_label.show();return None
        self.error_label.clear();self.error_label.hide();return tuple(values)
    def set_values(self,minimum,maximum):
        self._setting=True
        try:
            self.min_edit.setText('0' if minimum is None else format_number(minimum,grouped=False))
            self.max_edit.setText('∞' if maximum is None else format_number(maximum,grouped=False))
            first=self.axis.position(minimum or 0)
            last=self.axis.maximum if maximum is None else max(first,self.axis.position(maximum))
            self.axis.set_values(first,last)
            self._axis_positions=(first,last)
        finally:self._setting=False
    def _typed(self):
        if self._setting:return
        values=self.values()
        if values is not None:self.set_values(*values);self.changed.emit(*values)
    def _slid(self,minimum,maximum):
        values=[self.axis.passenger_value(minimum),None if maximum==self.axis.maximum else self.axis.passenger_value(maximum)]
        previous=self.values()
        if previous is not None:
            for index,position in enumerate((minimum,maximum)):
                if position==self._axis_positions[index]:values[index]=previous[index]
        self.set_values(*values);self.error_label.clear();self.error_label.hide();self.changed.emit(*values)


class MapPanelSet(QWidget):
    """Use panels as dockable widgets; stateChanged carries a defensive state copy.

    Option IDs remain their original types. None selection initializes to all
    available IDs, while an empty collection always means none selected.
    """
    stateChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()
        self._state = deepcopy(_DEFAULTS)
        self._filter_drafts={key:deepcopy(self._state[key]) for key in _FILTER_OWNER};self._dirty_filters=set()
        self.filter_sections={};self.filter_apply_buttons={}
        self._options = {}
        self._updating = False
        self._service_clock = None
        self._result_count = None
        self.group_lists = {}; self.group_summaries = {}; self.layer_checks = {}; self.controls = {}; self.control_labels = {}
        self.panels = {}; self._layouts = {}
        for key, title in [('layers','图层控制'),('filters','线路筛选'),('display','显示设置')]:
            scroll = StatisticsScrollArea(self)
            scroll.setWidgetResizable(True)
            body = QWidget(); body.setFont(ui_font(tokens.FONT_SIZE_BODY))
            layout = QVBoxLayout(body); layout.setContentsMargins(12,10,12,12); layout.setSpacing(8)
            scroll.setWidget(body); scroll.setMinimumWidth(240)
            self.panels[key]=scroll; self._layouts[key]=layout
            scroll.setAccessibleName(title)
        self._build_layers(); self._build_filters(); self._build_display()
        for layout in self._layouts.values(): layout.addStretch(1)
        self.set_options({})

    def state(self):
        return deepcopy(self._state)

    def set_result_count(self, count):
        """Display the current combined query result without changing selection."""
        self._result_count = count
        self._selection_summary()
        self._filter_summaries()

    def set_state(self, state):
        for key, value in state.items():
            if key not in _DEFAULTS: continue
            if key=='mode_widths':self._state[key]=_clean_widths(value or {})
            else:self._state[key] = (None if value is None else set(value)) if key in _SET_KEYS else deepcopy(value)
        mode=self._state['service_time_mode']
        if mode not in ('off','instant','range'):mode='off'
        dates={key:QDateTime.fromString(str(self._state[key] or ''),Qt.DateFormat.ISODate)
               for key in ('service_start','service_end')}
        for key,value in dates.items():
            if self._state[key] is not None and not value.isValid():self._state[key]=None
        if mode!='off' and not dates['service_start'].isValid():mode='off'
        if mode=='range' and (not dates['service_end'].isValid() or dates['service_end']<=dates['service_start']):mode='off'
        self._state['service_time_mode']=mode
        self._filter_drafts={key:deepcopy(self._state[key]) for key in _FILTER_OWNER};self._dirty_filters.clear()
        if mode!='off':self.filter_sections['service'].set_expanded(True)
        self._refresh()

    def set_options(self, options):
        self._options=deepcopy(options)
        self._line_labels=resolve_line_labels(self._options.get('lines',()))
        clock=QDateTime.fromString(str(options.get('simulated_datetime') or ''),Qt.DateFormat.ISODate)
        self._service_clock=clock if clock.isValid() else None
        # Aliases accept model-facing category names, preserving public state keys.
        for key, alias in [('company_ids','companies'),('layer_modes','modes')]:
            if key not in self._options: self._options[key]=self._options.get(alias,[])
        self._options['profit_statuses']=_PROFITS
        self._options['manual_line_ids']=self._options.get('lines',[])
        for key in _SET_KEYS:
            choices=self._options.get(key,[])
            if self._state[key] is None and choices:
                self._state[key]={item['id'] for item in choices}
        for key, category in [('mode_order','modes'),('company_order','company_ids')]:
            order=self._state[key]
            self._state[key]=order+[v['id'] for v in self._options.get(category,[]) if v['id'] not in order]
        for key,block in _FILTER_OWNER.items():
            if block not in self._dirty_filters:self._filter_drafts[key]=deepcopy(self._state[key])
        self._refresh()

    def _label(self, layout, text, heading=False):
        label=BodyLabel(text)
        _style_control(label,tokens.FONT_SIZE_BODY if heading else tokens.FONT_SIZE_CAPTION,
                       tokens.TEXT_PRIMARY if heading else tokens.TEXT_SECONDARY)
        label.setWordWrap(True)
        if heading:label.setFont(ui_font(tokens.FONT_SIZE_BODY,600))
        layout.addWidget(label); return label

    def _section(self,layout):
        frame=QFrame(); frame.setObjectName('mapControlSection')
        frame.setStyleSheet(f'QFrame#mapControlSection {{background:{tokens.SURFACE_SUBTLE};border:0;border-radius:{tokens.RADIUS_CONTROL}px;}}')
        child=QVBoxLayout(frame); child.setContentsMargins(10,8,10,8); child.setSpacing(5)
        layout.addWidget(frame); return child

    def _columns(self,layout):
        row=QHBoxLayout(); row.setContentsMargins(0,0,0,0); row.setSpacing(8); layout.addLayout(row)
        columns=[]
        for _ in range(2):
            widget=QWidget(); column=QVBoxLayout(widget); column.setContentsMargins(0,0,0,0); column.setSpacing(4)
            row.addWidget(widget,1,Qt.AlignmentFlag.AlignTop); columns.append(column)
        return columns

    def _group(self, layout, key, name, height=100):
        self.group_summaries[key]=self._label(layout,name)
        if key in ('road_levels','building_classes','building_uses','layer_modes'):
            view=_OptionGrid(key); view.changed.connect(lambda k=key:self._group_changed(k))
        else:
            view=_SingleLineList() if key=='manual_line_ids' else _WrappedList()
            if key!='manual_line_ids':view.setWordWrap(True); view.setTextElideMode(Qt.TextElideMode.ElideNone)
            view.itemChanged.connect(lambda item,k=key:self._group_changed(k))
        _style_control(view)
        if not isinstance(view,_OptionGrid):
            view.setProperty('heightCap',height); view.setFixedHeight(height)
            view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.group_lists[key]=view; layout.addWidget(view)
        view.setAccessibleName(name)
        return view

    def _combo(self, layout, key, title, choices):
        self.control_labels[key]=self._label(layout,title)
        combo=_style_control(ComboBox())
        for value,text in choices: combo.addItem(text,userData=value)
        combo.currentIndexChanged.connect(lambda i,k=key,c=combo:self._changed(k,c.itemData(i)))
        layout.addWidget(combo); self.controls[key]=combo
        combo.setAccessibleName(title)
        return combo

    def _choices(self,layout,key,title,choices,columns=1):
        if title:self.control_labels[key]=self._label(layout,title,True)
        choice=_ChoiceGroup(choices,columns); choice.changed.connect(lambda value,k=key:self._changed(k,value))
        layout.addWidget(choice); self.controls[key]=choice; return choice

    def _check(self, layout, key, title):
        box=_style_control(CheckBox(title))
        box.clicked.connect(lambda checked,k=key:self._changed(k,checked))
        self.controls[key]=box; layout.addWidget(box); return box

    def _build_layers(self):
        layout=self._layouts['layers']
        for key,title in [('roads','路网'),('buildings','建筑'),('routes','公共交通')]:
            section=self._section(layout)
            box=_style_control(CheckBox(title)); box.setTristate(True)
            box.clicked.connect(lambda checked,k=key:self._toggle_layer(k,checked))
            self.layer_checks[key]=box; section.addWidget(box)
            if key=='roads':self._group(section,'road_levels','道路等级',90); self.group_summaries['road_levels'].hide()
            elif key=='buildings':
                self._group(section,'building_classes','社会群体',190)
                self.group_summaries['building_classes'].hide()
                self._label(section,'建筑功能',True)
                self.building_function_legend=QWidget()
                self.building_function_legend.setAccessibleName('建筑功能图例')
                self.building_function_grid=QGridLayout(self.building_function_legend)
                self.building_function_grid.setContentsMargins(0,0,0,0)
                self.building_function_grid.setHorizontalSpacing(8)
                self.building_function_grid.setVerticalSpacing(3)
                self.building_function_labels={}; self.building_function_swatches={}
                self._building_legend_keys=()
                section.addWidget(self.building_function_legend)
                row=QHBoxLayout(); self._check(row,'building_emphasis','强调建筑密度')
                self.building_emphasis_auto=_style_control(TransparentPushButton('自动')); self.building_emphasis_auto.setFixedWidth(54)
                self.building_emphasis_auto.setAccessibleName('自动建筑强调')
                self.building_emphasis_auto.clicked.connect(lambda:self._changed('building_emphasis',None))
                row.addWidget(self.building_emphasis_auto); section.addLayout(row)
            else:
                self._group(section,'layer_modes','制式',140)
                for option,text in [('stops','标出站点'),('stop_names','站点名称'),('line_numbers','线路编号')]:self._check(section,option,text)

    def _build_filters(self):
        layout=self._layouts['filters']
        layout.setSpacing(5)
        row=QHBoxLayout(); self.selection_summary=self._label(row,'已选 0 / 共 0',True)
        self.reset_filters=_style_control(PushButton('重置')); self.reset_filters.setFixedWidth(64)
        self.reset_filters.clicked.connect(self._reset_filters); row.addWidget(self.reset_filters); layout.addLayout(row)
        self.filter_tags=QWidget(); self.tag_layout=FlowLayout(self.filter_tags,spacing=4)
        layout.addWidget(self.filter_tags)
        def section(key,title):
            block=_FilterSection(title);layout.addWidget(block);self.filter_sections[key]=block
            self.filter_apply_buttons[key]=block.apply_button
            block.apply_button.clicked.connect(lambda:self._confirm_filter(key))
            return block.body_layout
        for key,title,height in [('company_ids','公司',100),('modes','制式',120),('profit_statuses','盈亏',120)]:
            body=section(key,title);self._group(body,key,title,height);self.group_summaries[key].hide()
        passenger=section('passengers','客流')
        self.passenger_date=_style_control(BodyLabel(''),tokens.FONT_SIZE_CAPTION,tokens.TEXT_SECONDARY)
        self.passenger_editor=_PassengerRangeEditor();passenger.addWidget(self.passenger_editor)
        self.controls['passenger_min']=self.passenger_editor.min_edit;self.controls['passenger_max']=self.passenger_editor.max_edit
        self.passenger_editor.changed.connect(self._passenger_draft_changed)
        for edit in (self.passenger_editor.min_edit,self.passenger_editor.max_edit):
            edit.textChanged.connect(lambda:self._filter_text_edited('passengers',self.passenger_editor._setting))
        service=section('service','运营时间')
        self._choices(service,'service_time_mode','', [('off','不限'),('instant','时刻'),('range','时段')],3)
        self.service_editor=_ServiceTimeEditor();service.addWidget(self.service_editor)
        self.service_editor.edited.connect(self._service_edited)
        for edit in (self.service_editor.start_edit,self.service_editor.end_edit):
            edit.textChanged.connect(lambda:self._filter_text_edited('service',self.service_editor._setting))
        self.controls['service_start']=self.service_editor.start_edit;self.controls['service_end']=self.service_editor.end_edit
        self.service_labels={'service_start':self.service_editor.labels['start'],'service_end':self.service_editor.labels['end']}
        self.service_error=self.service_editor.error_label
        results=section('manual_line_ids','线路选择')
        row=QHBoxLayout(); row.setSpacing(4)
        self.search=_style_control(LineEdit()); self.search.setPlaceholderText('搜索线路'); self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _:self._refresh_lines()); row.addWidget(self.search,1)
        self.manual_all=_style_control(PushButton('全选')); self.manual_all.setFixedWidth(button_text_size(self.manual_all).width())
        self.manual_none=_style_control(PushButton('全不选')); self.manual_none.setFixedWidth(button_text_size(self.manual_none).width())
        self.search.setMinimumWidth(0)
        row.addWidget(self.manual_all); row.addWidget(self.manual_none); results.addLayout(row)
        self.manual_all.clicked.connect(lambda:self._select_visible(True))
        self.manual_none.clicked.connect(lambda:self._select_visible(False))
        self.line_list=self._group(results,'manual_line_ids','线路结果',114)
        self.group_summaries['manual_line_ids'].hide()
        for key,block in self.filter_sections.items():
            if key=='passengers':
                footer=QWidget();row=QHBoxLayout(footer);row.setContentsMargins(0,0,0,0);row.setSpacing(8)
                row.addWidget(self.passenger_date,0,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
                row.addStretch(1);row.addWidget(block.apply_button);block.body_layout.addWidget(footer)
            else:block.body_layout.addWidget(block.apply_button,0,Qt.AlignmentFlag.AlignRight)
        self.filter_sections['manual_line_ids'].set_expanded(True)

    def _build_display(self):
        layout=self._layouts['display']
        direction=self._section(layout)
        self._choices(direction,'direction','线路显示', [('whole','整条线路显示'),('up','仅显示环行与上行线'),('down','仅显示环行与下行线')])
        self._check(direction,'distinguish_directions','区分上下行线形')
        colors=self._section(layout)
        self._choices(colors,'color_by','线路染色',[('mode','按制式染同色'),('profit','按盈亏染同色'),('company','按公司染同色'),('line','每条线路都不同颜色'),('interval','按平均间隔染色'),('passengers','按客流染色')],1)
        interval=QWidget(); interval_layout=QVBoxLayout(interval)
        interval_layout.setContentsMargins(26,0,0,0);interval_layout.setSpacing(0)
        self._combo(interval_layout,'interval_mode','',[('daytime','日间平均间隔'),('peak','高峰平均间隔'),('all_day','全日平均间隔')])
        self.control_labels['interval_mode'].hide()
        grid=self.controls['color_by'].layout()
        grid.addWidget(self.controls['color_by'].buttons['passengers'],6,0)
        grid.addWidget(interval,5,0)
        interval.setVisible(False)
        self.controls['color_by'].buttons['interval'].toggled.connect(interval.setVisible)
        width=self._section(layout); self.width_section=width.parentWidget()
        row=QHBoxLayout(); self._label(row,'线路粗细',True)
        self.reset_widths=_style_control(TransparentPushButton('默认')); self.reset_widths.setFixedWidth(54)
        self.reset_widths.clicked.connect(lambda:self._changed('mode_widths',{})); row.addWidget(self.reset_widths); width.addLayout(row)
        self.width_editor=_ModeWidths(); self.width_editor.changed.connect(lambda value:self._changed('mode_widths',value))
        width.addWidget(self.width_editor); self.mode_width_controls=self.width_editor.spins
        priority=self._section(layout)
        self._choices(priority,'priority_by','线路显示排序',[('passengers','客流'),('mode','制式'),('company','公司')],3)
        self.priority_note=self._label(priority,'越靠上，地图显示优先级越高。')
        self._check(priority,'passenger_desc','客流由高到低')
        self.order_lists={}; self.order_labels={}
        for key in ('mode_order','company_order'):
            self.order_labels[key]=self._label(priority,'制式排序' if key=='mode_order' else '公司排序')
            view=_WrappedList(); _style_control(view); view.setProperty('heightCap',180); view.setFixedHeight(180)
            view.setWordWrap(True); view.setTextElideMode(Qt.TextElideMode.ElideNone)
            view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            view.setDefaultDropAction(Qt.DropAction.MoveAction)
            view.model().rowsMoved.connect(lambda *args,k=key:self._order_changed(k))
            self.order_lists[key]=view; priority.addWidget(view)
        self.single_company_hint=self._label(priority,'多公司时可调整顺序')
        extra=self._section(layout)
        self._check(extra,'deadhead','计入空放里程')
        self._label(extra,'开启后，里程统计包含数据中可识别的出入库等空驶区段。')

    def _reset_filters(self):
        for key in ('manual_line_ids','company_ids','modes','profit_statuses'):
            self._state[key]={item['id'] for item in self._options.get(key,[])}
        self._state['passenger_min']=self._state['passenger_max']=None
        self._state['service_time_mode']='off'
        self._filter_drafts={key:deepcopy(self._state[key]) for key in _FILTER_OWNER};self._dirty_filters.clear()
        self.search.clear(); self._refresh(); self.stateChanged.emit(self.state())

    def _confirm_filter(self,block):
        if block=='passengers':
            values=self.passenger_editor.values()
            if values is None:return
            self._filter_drafts.update(zip(_FILTER_BLOCK_KEYS[block],values))
        elif block=='service':
            values=self._service_values(self._filter_drafts['service_time_mode'])
            if values is None:return
            self._filter_drafts.update(values)
        keys=_FILTER_BLOCK_KEYS[block]
        changed=any(self._state[key]!=self._filter_drafts[key] for key in keys)
        for key in keys:self._state[key]=deepcopy(self._filter_drafts[key])
        self._dirty_filters.discard(block)
        self._refresh();self.filter_sections[block].set_expanded(False)
        if changed:self.stateChanged.emit(self.state())

    def _passenger_draft_changed(self,minimum,maximum):
        self._filter_drafts.update(passenger_min=minimum,passenger_max=maximum)
        self._dirty_filters.add('passengers')

    def _filter_text_edited(self,block,setting):
        if not setting and not self._updating:self._dirty_filters.add(block)

    def _changed(self,key,value):
        if key=='service_time_mode':
            self._service_mode_changed(value); return
        if key=='mode_widths':value=_clean_widths(value or {})
        if self._updating:return
        if key in _FILTER_OWNER:
            if self._filter_drafts[key]==value:return
            self._filter_drafts[key]=deepcopy(value);self._dirty_filters.add(_FILTER_OWNER[key])
        else:
            if self._state[key]==value:return
            self._state[key]=value
            if key=='color_by' and value in ('interval','passengers'):self._state['stops']=False
        if key=='manual_line_ids':
            # Selection changes do not alter candidates or any other controls.
            blocked=self.line_list.blockSignals(True)
            try:
                for i in range(self.line_list.count()):
                    item=self.line_list.item(i)
                    item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole) in value else Qt.CheckState.Unchecked)
            finally:self.line_list.blockSignals(blocked)
        else:self._refresh()
        if key not in _FILTER_OWNER:self.stateChanged.emit(self.state())

    def _service_values(self,mode):
        if mode=='off':return {}
        old_mode=self.service_editor._mode;self.service_editor._mode=mode
        pair=self.service_editor.values();self.service_editor._mode=old_mode
        if pair is None:return None
        values={'service_start':pair[0]}
        if mode=='range':values['service_end']=pair[1]
        return values

    def _service_mode_changed(self,mode):
        if self._updating:return
        values=self._service_values(mode)
        if values is None:
            self.controls['service_time_mode'].set_value(self._filter_drafts['service_time_mode']); return
        if mode==self._filter_drafts['service_time_mode'] and all(self._filter_drafts[k]==v for k,v in values.items()):return
        self._filter_drafts.update(values);self._filter_drafts['service_time_mode']=mode;self._dirty_filters.add('service')
        self._sync_service_controls()

    def _service_edited(self,*_):
        if self._updating or self._filter_drafts['service_time_mode']=='off':return
        values=self._service_values(self._filter_drafts['service_time_mode'])
        if values is None:return
        if any(self._filter_drafts[k]!=v for k,v in values.items()):
            self._filter_drafts.update(values);self._dirty_filters.add('service')

    def _sync_service_controls(self):
        self.service_editor.set_mode(self._filter_drafts['service_time_mode'])

    def _toggle_layer(self,key,checked):
        if self._updating:return
        # Partially checked -> select all, fully checked -> clear all.
        active=self.layer_checks[key].checkState()!=Qt.CheckState.Unchecked
        keys={'roads':['road_levels'], 'buildings':['building_classes'], 'routes':['layer_modes']}[key]
        self._state[key]=active
        for category in keys:
            self._state[category]={v['id'] for v in self._options.get(category,[])} if active else set()
        self._refresh(); self.stateChanged.emit(self.state())

    def _group_changed(self,key):
        if self._updating:return
        selected=set((self._filter_drafts[key] if key in _FILTER_OWNER else self._state[key]) or ())
        view=self.group_lists[key]
        if isinstance(view,_OptionGrid):selected=(selected-set(view.buttons))|view.selected()
        else:
            for i in range(view.count()):
                item=view.item(i); identity=item.data(Qt.ItemDataRole.UserRole)
                if item.checkState()==Qt.CheckState.Checked:selected.add(identity)
                else:selected.discard(identity)
        if key in _FILTER_OWNER:
            self._filter_drafts[key]=selected;self._dirty_filters.add(_FILTER_OWNER[key]);return
        self._state[key]=selected
        parent={'road_levels':'roads','building_classes':'buildings','building_uses':'buildings','layer_modes':'routes'}.get(key)
        if parent:self._state[parent]=bool(selected)
        # Do not rebuild the emitting view: retain its item and keyboard focus.
        self._sync_layer_checks()
        if key in ('company_ids','modes','profit_statuses'):self._refresh_lines()
        else:self._summaries()
        self.stateChanged.emit(self.state())

    def _select_visible(self,checked):
        selected=set(self._filter_drafts['manual_line_ids'] or ())
        ids={self.line_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.line_list.count())}
        selected=selected|ids if checked else selected-ids
        self._changed('manual_line_ids',selected)

    def _order_changed(self,key):
        if self._updating:return
        view=self.order_lists[key]
        visible=[view.item(i).data(Qt.ItemDataRole.UserRole) for i in range(view.count())]
        self._state[key]=visible+[v for v in self._state[key] if v not in visible]
        self.stateChanged.emit(self.state())

    @staticmethod
    def _icon(color):
        if not color:return QIcon()
        pix=QPixmap(10,10); pix.fill(QColor(color)); return QIcon(pix)

    def _order_icon(self,color):
        pix=QPixmap(28,18); pix.fill(Qt.GlobalColor.transparent)
        painter=QPainter(pix)
        for x in (3,7):
            for y in (4,8,12):painter.fillRect(QRect(x,y,2,2),QColor(tokens.TEXT_SECONDARY))
        painter.fillRect(QRect(17,5,8,8),QColor(color or tokens.TEXT_SECONDARY)); painter.end()
        return QIcon(pix)

    def _fill(self,view,choices,selected=None):
        view.blockSignals(True)
        if isinstance(view,_OptionGrid):
            view.populate(choices,selected or set()); view.blockSignals(False); return
        view.clear()
        ordered=selected is None
        view.setIconSize(QSize(28,18) if ordered else QSize(10,10))
        for choice in choices:
            icon=self._order_icon(choice.get('color')) if ordered else self._icon(choice.get('color'))
            item=QListWidgetItem(icon,str(choice['name']))
            item.setData(Qt.ItemDataRole.UserRole,choice['id']); item.setToolTip('')
            item.setFont(ui_font(tokens.FONT_SIZE_BODY)); item.setForeground(QColor(tokens.TEXT_PRIMARY))
            if selected is not None:
                item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if choice['id'] in selected else Qt.CheckState.Unchecked)
            view.addItem(item)
        view.wrap_items()
        height=sum(view.item(i).sizeHint().height()+6 for i in range(view.count()))+6
        view.setFixedHeight(min(int(view.property('heightCap')),max(32,height)))
        view.blockSignals(False)

    def _line_matches(self,line):
        if self._state['service_time_mode']!='off' and line.get('service_matches') is not True:return False
        for key,field in [('company_ids','company_id'),('modes','mode')]:
            if self._state[key] is not None and line.get(field) not in self._state[key]:return False
        profit=line.get('profit')
        if profit not in ('profit','loss','zero','missing'):
            profit='missing' if profit is None else 'profit' if profit>0 else 'loss' if profit<0 else 'zero'
        if self._state['profit_statuses'] is not None and profit not in self._state['profit_statuses']:return False
        minimum,maximum=self._state['passenger_min'],self._state['passenger_max']; number=line.get('passengers')
        if (minimum is not None or maximum is not None) and number is None:return False
        return (minimum is None or number>=minimum) and (maximum is None or number<=maximum)

    def _refresh_lines(self):
        from line_search import line_matches_search
        query=self.search.text()
        choices=[v for v in self._options.get('lines',[]) if self._line_matches(v) and
                 line_matches_search(query,v)]
        modes={entry['id']:entry['name'] for entry in self._options.get('modes',[])}
        display=[]
        for line in choices:
            mode=modes.get(line.get('mode'),display_mode(line.get('mode')))
            text=line.get('display_label') or line.get('label') or self._line_labels.get(line['id']) or f"{mode}{line['name']}"
            display.append(dict(line,name=text))
        self._fill(self.line_list,display,self._filter_drafts['manual_line_ids'] or set())
        self._summaries()

    def _summaries(self):
        titles={'road_levels':'道路等级','building_classes':'社会群体','building_uses':'建筑用途','layer_modes':'制式',
                'manual_line_ids':'线路结果','company_ids':'公司','modes':'制式','profit_statuses':'盈亏'}
        for key,label in self.group_summaries.items():label.setText(titles[key])
        self._selection_summary()
        self._filter_summaries()
        while self.tag_layout.count():
            item=self.tag_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        for key,title in [('manual_line_ids','手动'),('company_ids','公司'),('modes','制式'),('profit_statuses','盈亏')]:
            choices=self._options.get(key,[]); chosen=self._state[key]
            count=sum(v['id'] in (chosen or ()) for v in choices)
            if chosen is None or count==len(choices):continue
            label=BodyLabel(f'{title} {count}')
            _style_control(label,tokens.FONT_SIZE_CAPTION,tokens.ACCENT)
            rule=f'QLabel {{background:{tokens.ACCENT_SOFT};color:{tokens.ACCENT};border-radius:4px;padding:2px 6px;}}'
            setCustomStyleSheet(label,rule,rule); self.tag_layout.addWidget(label)
        self.filter_tags.setVisible(self.tag_layout.count()>0)

    def _applied_result_count(self):
        if self._result_count is not None:return self._result_count
        selected=self._state['manual_line_ids']
        return sum((selected is None or line['id'] in selected) and self._line_matches(line)
                   for line in self._options.get('lines',[]))

    def _filter_summaries(self):
        criteria={key:'' for key in self.filter_sections}
        for key,title in [('company_ids','公司'),('modes','制式'),('profit_statuses','盈亏')]:
            choices=self._options.get(key,[]);chosen=self._state[key]
            if chosen is None or all(choice['id'] in chosen for choice in choices):continue
            names=[choice['name'] for choice in choices if choice['id'] in chosen]
            criteria[key]=f"筛选{title}："+('、'.join(names) if names else '无')
        selected=self._state['manual_line_ids'];lines=self._options.get('lines',[])
        if selected is not None and not all(line['id'] in selected for line in lines):
            criteria['manual_line_ids']=f"筛选线路：{sum(line['id'] in selected for line in lines)}条"
        minimum,maximum=self._state['passenger_min'],self._state['passenger_max']
        if minimum is not None or maximum is not None:
            low=format_number(0 if minimum is None else minimum,grouped=False)
            high='∞' if maximum is None else format_number(maximum,grouped=False)
            criteria['passengers']=f'筛选客流：{low}-{high}人次'
        mode=self._state['service_time_mode']
        if mode!='off':
            start=QDateTime.fromString(self._state['service_start'],Qt.DateFormat.ISODate)
            end=QDateTime.fromString(self._state['service_end'] or '',Qt.DateFormat.ISODate)
            weekdays=('周一','周二','周三','周四','周五','周六','周日')
            def boundary(value):return weekdays[value.date().dayOfWeek()-1]+value.toString('HH:mm')
            if start.isValid():
                criteria['service']=boundary(start)
                if mode=='range' and end.isValid():
                    if start.date().daysTo(end.date())>=7:
                        criteria['service']=start.toString('yyyy-MM-dd HH:mm')+'-'+end.toString('yyyy-MM-dd HH:mm')
                    else:criteria['service']+='-'+(end.toString('HH:mm') if start.date()==end.date() else boundary(end))
        count=self._applied_result_count()
        for key,section in self.filter_sections.items():
            section.set_summary(f'{criteria[key]} 已选：{count}条' if criteria[key] else '')

    def _selection_summary(self):
        lines=self._options.get('lines',[]);count=self._applied_result_count()
        self.selection_summary.setText(f'已选 {count} / 共 {len(lines)}')

    def _sync_layer_checks(self):
        categories={'roads':'road_levels','buildings':'building_classes','routes':'layer_modes'}
        for key,category in categories.items():
            box=self.layer_checks[key]; box.blockSignals(True)
            ids={v['id'] for v in self._options.get(category,[])}; selection=self._state[category]
            active=ids & (selection or set())
            status=Qt.CheckState.Unchecked if not self._state[key] else (Qt.CheckState.PartiallyChecked if ids and active!=ids else Qt.CheckState.Checked)
            box.setCheckState(status); box.blockSignals(False)

    def _refresh_building_legend(self):
        # Native legend A-F: homes, workplaces, leisure, home/work,
        # work/leisure, other. Colours use the same function resolver as the map.
        entries=[('residential',category('usage','residential').name,(1,0,0,1)),
                 ('work',category('usage','work').name,(0,1,0,1)),
                 ('commercial',f"{category('usage','commercial').name}／休闲",(0,0,1,1)),
                 ('home_work','住宅／工作',(1,1,0,1)),
                 ('mixed','商业／工作',(0,1,1,1)),
                 ('unknown','其他',(None,None,None,None))]
        present={v['id'] for v in self._options.get('building_classes',[])}
        entries += [(key,category('usage',key).name,None) for key in ('transport','special') if key in present]
        keys=tuple(key for key,_,_ in entries)
        if keys!=self._building_legend_keys:
            while self.building_function_grid.count():
                item=self.building_function_grid.takeAt(0)
                if item.widget():item.widget().deleteLater()
            self.building_function_labels={}; self.building_function_swatches={}
            for i,(key,name,_) in enumerate(entries):
                cell=QWidget(); row=QHBoxLayout(cell); row.setContentsMargins(0,0,0,0); row.setSpacing(5)
                swatch=QFrame(); swatch.setFixedSize(14,10); swatch.setAutoFillBackground(True)
                label=_style_control(BodyLabel(name),tokens.FONT_SIZE_CAPTION); label.setWordWrap(True)
                row.addWidget(swatch); row.addWidget(label,1)
                self.building_function_grid.addWidget(cell,i//2,i%2)
                self.building_function_labels[key]=label; self.building_function_swatches[key]=swatch
            self._building_legend_keys=keys
        emphasis=self._state['building_emphasis']
        if emphasis is None:emphasis=self._options.get('building_emphasis_effective',True)
        for key,_,values in entries:
            color=(building_function_fill(BuildingFunctionValues(*values),bool(emphasis)) if values is not None
                   else map_fill('usage',key,.65 if emphasis else .20))
            swatch=self.building_function_swatches[key]; palette=swatch.palette()
            palette.setColor(swatch.backgroundRole(),QColor(color)); swatch.setPalette(palette)
            swatch.setStyleSheet(f'background:{color};border:1px solid {tokens.BORDER};border-radius:2px;')

    def _refresh(self):
        self._updating=True
        try:
            self._refresh_building_legend()
            for key,view in self.group_lists.items():
                if key!='manual_line_ids':self._fill(view,self._options.get(key,[]),self._filter_drafts.get(key,self._state[key]) or set())
            # Retain legacy saved metric fields for caller migration, without old
            # mutually exclusive category/colour controls or guessed aggregation.
            if self._state['building_class_target'] is None:
                self._state['building_class_target']=next((v['id'] for v in self._options.get('building_classes',[])
                    if v['id'] not in ('transport','special','unknown')),None)
            self.width_editor.populate(self._options.get('modes',[]),self._state['mode_widths'])
            self.mode_width_controls=self.width_editor.spins
            self.width_section.setVisible(bool(self._options.get('modes')))
            for key,widget in self.controls.items():
                if key in ('service_start','service_end','passenger_min','passenger_max'):continue
                current=self._filter_drafts.get(key,self._state[key])
                widget.blockSignals(True)
                if isinstance(widget,_ChoiceGroup):widget.set_value(current)
                elif isinstance(widget,CheckBox):
                    value=self._options.get('building_emphasis_effective',True) if key=='building_emphasis' and self._state[key] is None else self._state[key]
                    widget.setChecked(bool(value))
                elif isinstance(widget,LineEdit):widget.setText('' if current is None else str(current))
                else:
                    index=next((i for i in range(widget.count()) if widget.itemData(i)==self._state[key]),-1)
                    widget.setCurrentIndex(index)
                widget.blockSignals(False)
            for key,category in [('mode_order','modes'),('company_order','company_ids')]:
                lookup={v['id']:v for v in self._options.get(category,[])}
                self._fill(self.order_lists[key],[lookup[i] for i in self._state[key] if i in lookup])
                visible=self._state['priority_by']==('mode' if key=='mode_order' else 'company')
                self.order_lists[key].setVisible(visible); self.order_labels[key].setVisible(visible)
            self.single_company_hint.setVisible(self._state['priority_by']=='company' and len(self._options.get('company_ids',[]))==1)
            self.controls['passenger_desc'].setVisible(self._state['priority_by']=='passengers')
            self.controls['distinguish_directions'].setEnabled(self._state['direction']=='whole')
            self.building_emphasis_auto.setEnabled(self._state['building_emphasis'] is not None)
            date=self._options.get('passenger_date')
            source=self._options.get('passenger_label')
            self.passenger_date.setText('平均客流' if source=='平均客流' or self._options.get('passenger_source')=='average' else str(date or ''))
            if 'passengers' not in self._dirty_filters:
                self.passenger_editor.set_values(self._filter_drafts['passenger_min'],self._filter_drafts['passenger_max'])
            self._refresh_lines(); self._sync_layer_checks(); self._summaries()
            if 'service' not in self._dirty_filters:
                self.service_editor.set_state(self._filter_drafts,self._service_clock.toPython() if self._service_clock is not None else None)
            self._sync_service_controls()
        finally:self._updating=False
