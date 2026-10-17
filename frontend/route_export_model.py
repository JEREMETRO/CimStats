"""Frozen single-route export inputs; no widgets, disk cache or save parsing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
import re

from map_model import MapSnapshot
from map_visibility import operating_paths, visible_route_stop_ids, usable_paths
from map_route_metrics import selected_route_metrics
from map_service_time import session_line, operating_time_text
from map_line_presentation import line_information, _LINE_FIELDS, _PASSENGER_FIELDS
from line_query_page import line_display_value, shown
from report_model import display_company


class ExportError(ValueError):
    """Actionable export validation or output failure."""


class ExportCancelled(InterruptedError):
    pass


class LayoutError(ExportError):
    pass


FIELD_SECTIONS = tuple((key,title,tuple((f[0],f[1]) for f in fields))
    for key,title,fields in (('line_information','线路信息',(('运营时间','运营时间',''),)+_LINE_FIELDS),
                            ('passenger_data','客流数据',_PASSENGER_FIELDS)))
ALL_FIELDS = tuple(key for _,_,fields in FIELD_SECTIONS for key,_ in fields)
DEFAULT_FIELDS = ('运营时间','地图里程','单程时间','核定速度','站点数','当日发班数','平均间隔','今日客流')


@dataclass(frozen=True, slots=True)
class ExportOptions:
    format: str = 'PNG'
    direction: str = 'whole'
    include_deadhead: bool = False
    show_stops: bool = True
    show_depot_names: bool = False
    aspect: str = '3:2'
    orientation: str = 'landscape'
    width_mm: float = 254.
    height_mm: float | None = None
    ppi: int = 300
    theme: str = 'day'
    selected_fields: tuple[str,...] = DEFAULT_FIELDS
    logo_source: str = 'save'
    brand_override: tuple[str,str] | None = None
    custom_logo_png: bytes | None = None

    def __post_init__(self):
        for key,allowed in (('format',('PNG','JPG','PDF')),('direction',('whole','up','down')),
            ('aspect',('16:9','16:10','3:2','A4')),('orientation',('landscape','portrait')),
            ('theme',('day','night')),('logo_source',('save','custom','none'))):
            if getattr(self,key) not in allowed:raise ExportError(f'无效的导出选项：{key}')
        if self.ppi not in (80,150,300,600):raise ExportError('精度应为 80、150、300 或 600 ppi')
        for v in (self.width_mm,self.height_mm):
            if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) or not 0<v<=1000):
                raise ExportError('成品尺寸应在 0 至 1000 毫米之间')
        object.__setattr__(self,'selected_fields',tuple(self.selected_fields))
        if any(key not in ALL_FIELDS for key in self.selected_fields):raise ExportError('存在未知的导出字段')
        if self.brand_override is not None:
            object.__setattr__(self,'brand_override',tuple(self.brand_override))
            if len(self.brand_override)!=2 or any(not re.fullmatch('#[0-9a-fA-F]{6}',v) for v in self.brand_override):
                raise ExportError('品牌颜色应为两项 RGB 颜色')
        if self.custom_logo_png is not None and not isinstance(self.custom_logo_png,bytes):
            raise ExportError('自选标志应为已冻结的图像数据')


@dataclass(frozen=True, slots=True)
class OutputSize:
    width_mm: float
    height_mm: float
    width_px: int
    height_px: int

    @property
    def pixels(self):return self.width_px,self.height_px

    @property
    def millimetres(self):return self.width_mm,self.height_mm


def measure_output(options):
    if options.aspect=='A4':
        w,h=(297.,210.) if options.orientation=='landscape' else (210.,297.)
    else:
        ratio={'16:9':16/9,'16:10':1.6,'3:2':1.5}[options.aspect]
        if options.orientation=='portrait':ratio=1/ratio
        w,h=((options.width_mm,options.width_mm/ratio) if options.height_mm is None
             else (options.height_mm*ratio,options.height_mm))
    px,py=round(w/25.4*options.ppi),round(h/25.4*options.ppi)
    if px<1 or py<1:raise ExportError('成品尺寸过小')
    if px*py>120_000_000 or max(px,py)>32768:raise ExportError('成品尺寸超出可导出范围，请减小尺寸或精度')
    return OutputSize(w,h,px,py)


@dataclass(frozen=True, slots=True)
class ExportInformation:
    company_name: str
    route_name: str
    mode: str
    direction: str
    sections: tuple


@dataclass(frozen=True, slots=True)
class ExportDepot:
    name: str
    position: tuple


@dataclass(frozen=True, slots=True)
class RouteExportRequest:
    save_identity: str
    route_id: int
    snapshot: MapSnapshot
    information: ExportInformation
    branding: object
    options: ExportOptions
    route: object
    metrics: object
    paths: tuple
    stops: tuple
    depots: tuple
    simulated_date: str
    company: tuple = ()


def _number(value):
    return float(value) if isinstance(value,(int,float)) and not isinstance(value,bool) and isfinite(value) else None


def _depot_paths(route,direction):
    if direction=='whole':return route.depot_paths
    if not route.depot_paths:return ()
    if len(route.depot_leg_paths)!=2:
        raise ExportError('空放方向信息不完整，请选择全线或关闭空放')
    return route.depot_leg_paths[0 if direction=='down' else 1]


def build_export_request(session,map_snapshot,route_id,options,*,branding=None):
    """Capture only stable identity and the shared formatted facts on the GUI thread."""
    measure_output(options)
    matches=tuple(r for r in map_snapshot.routes if r.id==route_id)
    line=session_line(session,route_id)
    if len(matches)!=1 or line is None:raise ExportError('选中线路不存在或身份不唯一')
    route=matches[0]
    metrics=selected_route_metrics(route,options.direction,options.include_deadhead,
        whole_duration_minutes=_number(line_display_value(line,'单程时间',session.get('lines',()))),
        whole_length_km=_number(line_display_value(line,'地图里程',session.get('lines',()))))
    direction=metrics.effective_direction
    paths=tuple(operating_paths(route,direction))
    if not usable_paths(paths):raise ExportError('当前线路没有可导出的运营路径')
    if options.include_deadhead:
        paths+=_depot_paths(route,direction)
    ids=visible_route_stop_ids(route,direction)
    stops=tuple(s for s in map_snapshot.stops if s.id in ids)
    source=line_information(session,route_id,direction_metrics=metrics)
    suffix={'whole':'全线','up':'上行','down':'下行'}[direction]
    sections=[]
    for section_id,title,rows in source['sections']:
        rows=list(rows)
        if section_id=='line_information':
            rows.insert(0,('运营时间','运营时间',operating_time_text(session,route_id,route=route)))
        # The existing single panel adds direction length independently of line_information.
        length=('地图里程','地图里程',shown(metrics.length_km,'km'))
        rows=[length if row[0]=='地图里程' else row for row in rows]
        if not any(row[0]=='地图里程' for row in rows) and section_id=='line_information':
            rows.insert(next(i for i,row in enumerate(rows) if row[0]=='单程时间'),length)
        filtered=[]
        for key,label,value in rows:
            if key not in options.selected_fields:continue
            label=label.replace(f'（{suffix}）','')
            filtered.append((key,label,value))
        if filtered:
            if section_id=='passenger_data':
                title=next((key for key,_,_ in filtered if key in ('今日客流','平均客流')),'今日客流')
            sections.append((section_id,title,tuple(filtered)))
    companies=tuple(c for c in session.get('companies',()) if str(c.get('公司标识'))==str(route.company_id))
    company=companies[0] if len(companies)==1 else {'公司标识':route.company_id,'公司名称':source['identity']['company_name']}
    company_name=display_company(company.get('公司名称') or source['identity']['company_name'])
    mode=source['identity']['mode']
    information=ExportInformation(company_name,source['identity']['name'],
        '城市公交' if mode=='公交' else mode,suffix,tuple(sections))
    try:date=datetime.fromisoformat(session.get('simulation_time','')).date().isoformat()
    except (TypeError,ValueError):date='—'
    # A depot requires confirmed object identity; textual names alone cannot locate one.
    depot_name=route.depot_name
    if not depot_name:
        label=line_display_value(line,'线路车库',session.get('lines',()))
        # The report already formats an unnamed depot from its saved number.
        # Reuse that stable route's display name only with confirmed location.
        depot_name=label if isinstance(label,str) and label.strip() not in ('','—') else ''
    depots=((ExportDepot(depot_name,route.depot_position),)
        if route.depot_id is not None and depot_name and route.depot_position is not None else ())
    frozen_company=tuple((key,company.get(key)) for key in
        ('公司标识','公司名称','公司标志','颜色1','颜色2'))
    return RouteExportRequest(str(map_snapshot.source_hash or session.get('save_path','')),
        route_id,map_snapshot,information,branding,options,route,metrics,paths,stops,depots,date,frozen_company)
