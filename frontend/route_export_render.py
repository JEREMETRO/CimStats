"""One measured vector scene for preview, tiled PNG, bounded JPG and vector PDF."""
from __future__ import annotations

from dataclasses import dataclass,replace
from pathlib import Path
import os
import struct
import tempfile
import zlib

from PySide6.QtCore import QPointF, QRectF, QSizeF, QMarginsF, Qt
from PySide6.QtGui import (QColor,QFont,QFontMetricsF,QImage,QImageWriter,QPageLayout,
    QPageSize,QPainter,QPainterPath,QPdfWriter,QPen)

from route_export_model import ExportError,ExportCancelled,LayoutError,measure_output
from stats_typography import emphasis_font, ui_font
from semantic_colors import color_for, building_function_fill
from map_model import building_function_values
from map_canvas import road_style
from map_visibility import operating_paths, operating_leg_indices, route_stop_symbols

MAX_IMAGE_BYTES=160*1024*1024  # Includes A4 at 600 ppi; larger JPG requests fail before allocation.
STRIP_BYTES=16*1024*1024


@dataclass(frozen=True, slots=True)
class TextItem:
    text: str
    rect: tuple
    size: int
    weight: int = 400
    role: str = 'label'
    align: str = 'left'
    display_text: str | None = None


@dataclass(frozen=True, slots=True)
class ExportLayout:
    width: float
    height: float
    map_rect: tuple
    info_rect: tuple
    text_items: tuple
    rules: tuple
    logo_rect: tuple


@dataclass(frozen=True, slots=True)
class ExportResult:
    path: str
    size: object
    format: str


def _check(cancel):
    if cancel is not None and cancel():raise ExportCancelled('已取消导出')


def _font(item):
    font=(emphasis_font(item.size,QFont.Weight(item.weight)) if item.role in
        ('route','number','value') else ui_font(item.size,QFont.Weight(item.weight)))
    if item.role in ('route','number') and hasattr(font,'setVariableAxis'):
        font.setVariableAxis(QFont.Tag('wght'),float(item.weight))
    return font


def _text_height(text,width,size,role='label',weight=400):
    item=TextItem(text,(0,0,width,10000),size,weight,role)
    metrics=QFontMetricsF(_font(item))
    if role in ('number','unit') and metrics.horizontalAdvance(text)<=width:
        return metrics.tightBoundingRect(text).height()+4
    bounds=metrics.boundingRect(QRectF(0,0,width,10000),
        int(Qt.TextFlag.TextWordWrap|Qt.TextFlag.TextWrapAnywhere),text)
    return max(bounds.height()+2,size*1.25)


def _emit_text(items,value,x,y,width,size,role='label',weight=400,align='left',display=None):
    h=_text_height(display or value,width,size,role,weight)
    items.append(TextItem(value,(x,y,width,h),size,weight,role,align,display))
    return h


def _header(items,request,x,y,width,company_size,route_height_limit,logo_side=64):
    company=request.information.company_name+'·'+request.information.mode
    company_width=width-logo_side-24
    while company_size>14 and QFontMetricsF(_font(TextItem(company,(),company_size,600,'heading'))).horizontalAdvance(company)>company_width:
        company_size-=1
    if QFontMetricsF(_font(TextItem(company,(),company_size,600,'heading'))).horizontalAdvance(company)>company_width:
        raise LayoutError('公司抬头无法完整排入当前信息区')
    company_h=_emit_text(items,company,x,y,company_width,company_size,'heading',600)
    logo=(x+width-logo_side,y,logo_side,logo_side)
    y+=max(company_h,logo_side)+8
    direction=request.information.direction if request.metrics.effective_direction!='whole' else ''
    direction_size=20
    direction_metrics=QFontMetricsF(_font(TextItem(direction,(),direction_size,400,'annotation')))
    direction_width=direction_metrics.horizontalAdvance(direction)+4 if direction else 0
    available=width-(direction_width+16 if direction else 0)
    route_size=112
    while route_size>36 and _text_height(request.information.route_name,available,route_size,'route',650)>route_height_limit:
        route_size-=4
    route_item=TextItem(request.information.route_name,(),route_size,650,'route')
    route_metrics=QFontMetricsF(_font(route_item))
    route_width=min(available,route_metrics.horizontalAdvance(route_item.text)+4)
    route_h=_emit_text(items,route_item.text,x,y,route_width,route_size,'route',650)
    if direction:
        direction_h=_text_height(direction,direction_width,direction_size,'annotation')
        direction_y=min(y+route_h-direction_h,y+route_metrics.ascent()-direction_metrics.ascent())
        _emit_text(items,direction,x+route_width+16,direction_y,direction_width,direction_size,'annotation')
    return y+route_h+14,logo


def _number_line(items,value,x,y,width,size):
    number=value.removesuffix(' 人次');unit_size=20
    unit_width=QFontMetricsF(_font(TextItem('人次',(),unit_size,400,'unit'))).horizontalAdvance('人次')+4
    available=width-unit_width-12
    while size>28 and QFontMetricsF(_font(TextItem(number,(),size,600,'number'))).horizontalAdvance(number)+4>available:
        size-=2
    number_width=QFontMetricsF(_font(TextItem(number,(),size,600,'number'))).horizontalAdvance(number)+4
    if number_width>available:raise LayoutError('客流数字无法完整排入当前信息区')
    h=_emit_text(items,number,x,y,number_width,size,'number',600)
    unit_h=_text_height('人次',unit_width,unit_size,'unit')
    _emit_text(items,'人次',x+number_width+12,y+h-unit_h,unit_width,unit_size,'unit')
    return h


def _footer(request,right,width,height):
    text='最后更新日期：'+request.simulated_date
    h=_text_height(text,width,16,'footer')
    return TextItem(text,(right-width,height-20-h,width,h),16,400,'footer','right')


def _portrait_layout(request,width,height):
    """Measure information first; give the remaining rectangle to the map."""
    margin=48.;content_width=width-2*margin
    for body in (22,20,18,16):
        map_top=28.
        items=[];rules=[];y=0.
        def emit(value,x,y,w,size,role='label',weight=400,align='left',display=None):
            h=_text_height(display or value,w,size,role,weight)
            items.append(TextItem(value,(x,y,w,h),size,weight,role,align,display))
            return h
        y,logo=_header(items,request,margin,y,content_width,32,160)
        rules.append((margin,y,content_width));y+=18
        sections=request.information.sections;bottom=y
        # The map/information relationship is vertical. The two independent
        # data categories use the wide lower area without shrinking all text.
        for index,(section_id,title,rows) in enumerate(sections):
            split=section_id=='line_information' and len(rows)>7
            groups=(rows[:(len(rows)+1)//2],rows[(len(rows)+1)//2:]) if split else (rows,)
            if len(sections)==2:
                slot=(content_width-64)/3
                x=margin if index==0 else margin+2*(slot+32)
                category_w=2*slot+32 if index==0 else slot
            else:x=margin;category_w=content_width
            column=(category_w-32)/2 if split else category_w
            primary=next((key for key,_,_ in rows if key in ('今日客流','平均客流')),None) if section_id=='passenger_data' else None
            row_top=y+emit(title,x,y,category_w,26,'heading',600)+(6 if primary else 10)
            section_bottom=row_top
            for group_index,group in enumerate(groups):
              column_x=x+group_index*(column+32);cursor=row_top
              for key,label,value in group:
                if key==primary:
                    cursor+=_number_line(items,value,column_x,cursor,column,76)+12
                    continue
                label_w=column*(.25 if key=='线路车库' else .40 if key in ('开线日期','最近改线日期') else .57)
                value_w=column-label_w-16
                display=value
                if (key in ('开线日期','最近改线日期') and ' ' in value and
                    QFontMetricsF(_font(TextItem(value,(),body+2,500,'value'))).horizontalAdvance(value)>value_w):
                    display=value.replace(' ','\n',1)
                lh=emit(label,column_x,cursor,label_w,body)
                vh=emit(value,column_x+label_w+16,cursor,value_w,body+2,'value',500,'right',display)
                cursor+=max(lh,vh)+4
              section_bottom=max(section_bottom,cursor)
            rules.append((x,section_bottom+6,category_w));bottom=max(bottom,section_bottom+18)
        footer=_footer(request,width-margin,content_width,height)
        information_height=bottom+footer.rect[3]+16
        map_height=height-map_top-20-32-information_height
        if map_height>=height*.30:
            offset=map_top+map_height+32
            translated=tuple(replace(item,rect=(item.rect[0],item.rect[1]+offset,*item.rect[2:])) for item in items)
            return ExportLayout(width,height,(margin,map_top,content_width,map_height),
                (margin,offset,content_width,information_height),translated+(footer,),
                tuple((x,y+offset,w) for x,y,w in rules),(logo[0],logo[1]+offset,*logo[2:]))
    raise LayoutError('文字无法完整排入纵向画幅，请缩短线路名称或减少字段')


def build_layout(request):
    """Measure every glyph; retry typography density without dropping a field."""
    size=measure_output(request.options)
    width=1536.;height=width*size.height_mm/size.width_mm
    if size.height_mm>size.width_mm:return _portrait_layout(request,width,height)
    attempts=tuple((2/3,body) for body in (22,20,18,16,14))+((.52,16),(.52,14),(.45,14))
    for fraction,body in attempts:
        map_width=(width-72-40)*fraction;map_height=height-56
        x=36+map_width+40;right=width-36;column=right-x
        items=[];rules=[];y=16. if body==14 else 28.;dense=body<=18;compact=body<=16
        def text(value,size,role='label',weight=400,rect_width=None,align='left'):
            nonlocal y
            w=column if rect_width is None else rect_width
            h=_text_height(value,w,size,role,weight)
            items.append(TextItem(value,(x,y,w,h),size,weight,role,align))
            y+=h
            return h
        logo_side=56 if body==14 else 64
        try:y,logo=_header(items,request,x,y,column,20 if compact else 24 if dense else 28,
            height*(.09 if compact else .14 if dense else .21),logo_side)
        except LayoutError:continue
        rules.append((x,y,column));y+=16 if dense else 26
        for section_id,title,rows in request.information.sections:
            primary=next((key for key,_,_ in rows if key in ('今日客流','平均客流')),None) if section_id=='passenger_data' else None
            text(title,20 if body==14 else 22 if compact else 24 if dense else 28,'heading',600)
            y+=6 if primary else 4 if body==14 else 8 if dense else 14
            for key,label,value in rows:
                if key==primary:
                    y+=_number_line(items,value,x,y,column,52 if compact else 60 if dense else 76)
                    y+=8 if dense else 12
                    continue
                # Dates and confirmed depot names need more room than their labels.
                label_w=column*(.45 if key in ('开线日期','最近改线日期','线路车库') else .57)
                value_w=column-label_w-14
                label_h=_text_height(label,label_w,body,'label')
                value_size=body if compact else body+2
                display_value=(value.replace(' ','\n',1) if key in ('开线日期','最近改线日期') and ' ' in value else value)
                value_h=_text_height(display_value,value_w,value_size,'value',500)
                h=max(label_h,value_h)
                items.extend((TextItem(label,(x,y,label_w,h),body),
                    TextItem(value,(x+label_w+14,y,value_w,h),value_size,500,'value','right',display_value)))
                y+=h+(2 if compact else 6 if dense else 10)
            y+=4 if body==14 else 8 if dense else 14
            rules.append((x,y,column));y+=4 if body==14 else 8 if compact else 16 if dense else 24
        # y includes trailing space after the final rule; visible content keeps
        # the same >=16 design-unit boundary as the compact header.
        footer=_footer(request,right,column,height)
        if y<=footer.rect[1]-16:
            offset=max(0.,(footer.rect[1]-16-(y+12))/2)
            translated=tuple(replace(item,rect=(item.rect[0],item.rect[1]+offset,*item.rect[2:])) for item in items)
            return ExportLayout(width,height,(36.,28.,map_width,map_height),(x,24.,column,height-48),
                translated+(footer,),tuple((rx,ry+offset,rw) for rx,ry,rw in rules),
                (logo[0],logo[1]+offset,*logo[2:]))
    raise LayoutError('文字无法完整排入当前画幅，请使用纵向 A4 或缩短线路名称')


def _mix(color,background,factor):
    c,b=QColor(color),QColor(background)
    return QColor.fromRgbF(c.redF()*factor+b.redF()*(1-factor),
        c.greenF()*factor+b.greenF()*(1-factor),c.blueF()*factor+b.blueF()*(1-factor))


@dataclass(frozen=True, slots=True)
class _Shape:
    path: object
    pen: object
    brush: object = None


@dataclass(frozen=True, slots=True)
class _Scene:
    request: object
    layout: ExportLayout
    shapes: tuple
    station_points: tuple
    depot_points: tuple
    background: str
    map_background: str
    foreground: str
    muted: str
    rule: str
    brand: str
    line: str
    logo: object
    logo_status: str
    legend_rect: tuple = ()


def _resolve_brand(request,background):
    from company_branding import resolve_company_branding,resolve_brand_assets,derive_brand_colors,render_brand_logo
    branding=request.branding
    if branding is None:
        branding=resolve_company_branding(dict(request.company),logo_source=request.options.logo_source,
            custom_logo=request.options.custom_logo_png,brand_override=request.options.brand_override)
    else:
        branding=replace(branding,brand_override=request.options.brand_override)
        if request.options.logo_source=='none':
            branding=replace(branding,logo_image=None,logo_mask=None,logo_status='hidden')
        elif (request.options.logo_source=='custom' or
                branding.logo_status in ('custom','invalid_custom','hidden')):
            company={'公司标识':branding.company_id,'公司名称':branding.company_name,
                '公司标志':branding.logo_key,'颜色1':branding.color1_argb,'颜色2':branding.color2_argb}
            branding=resolve_company_branding(company,logo_source=request.options.logo_source,
                custom_logo=request.options.custom_logo_png,brand_override=request.options.brand_override)
    branding=resolve_brand_assets(branding)
    colors=derive_brand_colors(branding,request.options.theme,background)
    logo=render_brand_logo(branding,colors)
    return colors.color1,logo.to_qimage() if logo else None,branding.logo_status,


def _prepare_scene(request,cancel=None):
    _check(cancel)
    layout=build_layout(request)
    night=request.options.theme=='night'
    bg='#0B2034' if night else '#FFFFFF'
    map_bg='#0D2539' if night else '#FFFFFF'
    fg='#F3F7FC' if night else '#0A274B'
    muted='#B4CBDD' if night else '#65758A'
    brand,logo,status=_resolve_brand(request,bg)
    line='#20DFF5' if night else color_for('mode',request.route.mode)
    effective=request.metrics.effective_direction
    legs=set(operating_leg_indices(request.route,effective))
    symbols={sid:point for i,sid,point in route_stop_symbols(request.route,{s.id:s for s in request.stops})
             if i==-1 or i in legs}
    station_positions=tuple(symbols.get(s.id,s.position) for s in request.stops) if request.options.show_stops else ()
    points=[p for path in request.paths for p in path]
    points.extend(station_positions)
    if request.options.show_depot_names:points.extend(d.position for d in request.depots)
    xmin,xmax=min(p[0] for p in points),max(p[0] for p in points)
    zmin,zmax=min(p[2] for p in points),max(p[2] for p in points)
    cx,cz=(xmin+xmax)/2,(zmin+zmax)/2
    mx,my,map_width,map_height=layout.map_rect
    has_legend=(request.metrics.effective_direction=='whole' and request.route.direction.kind=='roundtrip'
        and request.route.direction.terminal_index is not None and bool(request.route.leg_paths))
    plot_height=map_height-60 if has_legend else map_height
    # Keep surrounding real geography visible beyond both route ends. The
    # same proportional inset applies to every paper size and orientation.
    inset_x=max(24.,map_width*.06)
    inset_y=max(24.,plot_height*.06)
    scale=min((map_width-2*inset_x)/max(xmax-xmin,1.),
              (plot_height-2*inset_y)/max(zmax-zmin,1.))
    world_xmin,world_xmax=cx-map_width/scale/2,cx+map_width/scale/2
    world_zmin,world_zmax=cz-(map_height-plot_height/2)/scale,cz+plot_height/scale/2
    def project(p):return QPointF(mx+map_width/2+(p[0]-cx)*scale,my+plot_height/2-(p[2]-cz)*scale)
    def path(saved,closed=False):
        _check(cancel)
        if not saved:return None
        # Reject only features entirely outside; never rewrite their coordinates.
        if (max(p[0] for p in saved)<world_xmin or min(p[0] for p in saved)>world_xmax or
            max(p[2] for p in saved)<world_zmin or min(p[2] for p in saved)>world_zmax):return None
        result=QPainterPath(project(saved[0]))
        for i,p in enumerate(saved[1:]):
            if i%128==0:_check(cancel)
            result.lineTo(project(p))
        if closed:result.closeSubpath()
        return result
    shapes=[]
    for b in request.snapshot.buildings:
        p=path(b.polygon,True)
        if p is None:continue
        semantic=(color_for('usage',b.category) if b.category in ('transport','special') else
            building_function_fill(building_function_values(b),True))
        fill=_mix(semantic,map_bg,.34)
        shapes.append(_Shape(p,None,fill))
    road_batches={};road_styles={};road_lookup={r.id:r for r in request.snapshot.roads}
    ranking={'unknown':0,'local':1,'pedestrian':2,'secondary':3,'arterial':4,'express':5,'track':6}
    def road_colors(style):
        return ((('#AE8842' if style.level in ('express','arterial') else '#446580'), '#253F54')
            if night else (style.fill,style.shell))
    for road in request.snapshot.roads:
        style=road_style(road,scale)
        road_styles[road.id]=style;fill,shell=road_colors(style)
        for index,saved in enumerate(road.paths):
            p=path(saved)
            if p is None:continue
            bridge=bool(road.bridge_masks[index]) if index<len(road.bridge_masks) else road.bridge
            tunnel=bool(road.tunnel_masks[index]) if index<len(road.tunnel_masks) else road.tunnel
            layer=0 if tunnel else 2 if bridge else 1
            road_batches.setdefault((layer,ranking[style.level]),[]).append((p,fill,shell,style.width,style.casing))
    # Saved lane/junction connections supply real continuity at intersections.
    for junction in request.snapshot.junctions:
        layer=0 if junction.tunnel else 2 if junction.bridge else 1
        for connection in junction.connections:
            source=road_lookup.get(connection.source_road_id);target=road_lookup.get(connection.target_road_id)
            if source is None or target is None:continue
            styles=(road_styles[source.id],road_styles[target.id])
            style=min(styles,key=lambda s:s.width);fill,shell=road_colors(style)
            width=max(.5,min(s.width/max(2,(r.lanes_a or 0)+(r.lanes_b or 0)) for r,s in zip((source,target),styles)))
            for saved in connection.paths:
                p=path(saved)
                if p is not None:
                    road_batches.setdefault((layer,ranking[style.level]),[]).append((p,fill,shell,width,.3))
    for key in sorted(road_batches):
        batch=road_batches[key]
        for casing in (True,False):
            for p,fill,shell,width,border in batch:
                # A higher bridge stratum must not stamp a circular casing cap
                # backwards across the adjoining lower-stratum road body.
                pen=QPen(QColor(shell if casing else fill),width+border*2 if casing else width,
                    Qt.PenStyle.SolidLine,Qt.PenCapStyle.FlatCap if casing else Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin)
                shapes.append(_Shape(p,pen))
    operating=operating_paths(request.route,effective)
    distinguish=(effective=='whole' and request.route.direction.kind=='roundtrip'
        and request.route.direction.terminal_index is not None and request.route.leg_paths)
    groups=([(operating_paths(request.route,'down'),False,False),
             (operating_paths(request.route,'up'),True,False)] if distinguish else [(operating,False,False)])
    if request.options.include_deadhead:
        groups.append((request.paths[len(operating):],True,True))
    route_paths=[]
    for saved_paths,dashed,deadhead in groups:
        phase=0.
        for saved in saved_paths:
            p=path(saved)
            if p is None:continue
            length=p.length()
            route_paths.append((p,dashed,deadhead,phase))
            phase+=length
    # Complete all casings before route bodies, so saved segment joints remain continuous.
    for color,w in ((bg,8),(line,5)):
        for p,dashed,deadhead,phase in route_paths:
            width=w*.65 if deadhead else w
            stroke=_mix(line,map_bg,.45) if deadhead and w==5 else color
            pen=QPen(QColor(stroke),width,Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.FlatCap if dashed else Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin)
            if dashed:
                dash,gap=(6.,5.) if deadhead else (14.,8.)
                pen.setDashPattern([dash/width,gap/width]);pen.setDashOffset(phase/width)
            shapes.append(_Shape(p,pen))
    stations=tuple(project(position) for position in station_positions)
    depots=tuple((d.name,project(d.position)) for d in request.depots) if request.options.show_depot_names else ()
    return _Scene(request,layout,tuple(shapes),stations,depots,bg,map_bg,fg,muted,
        '#365168' if night else '#E0E0E0',brand or muted,line,logo,status,
        (mx+map_width-232,my+map_height-44,216,32) if has_legend else ())


def _paint(painter,scene,cancel=None,visible=None):
    layout=scene.layout
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.fillRect(QRectF(0,0,layout.width,layout.height),QColor(scene.background))
    painter.save();painter.setClipRect(QRectF(*layout.map_rect))
    painter.fillRect(QRectF(*layout.map_rect),QColor(scene.map_background))
    for index,shape in enumerate(scene.shapes):
        if index%64==0:_check(cancel)
        if visible is not None:
            margin=shape.pen.widthF()/2+2 if shape.pen is not None else 2
            if not shape.path.boundingRect().adjusted(-margin,-margin,margin,margin).intersects(visible):continue
        painter.setPen(shape.pen if shape.pen is not None else Qt.PenStyle.NoPen)
        painter.setBrush(shape.brush if shape.brush is not None else Qt.BrushStyle.NoBrush)
        painter.drawPath(shape.path)
    painter.setPen(QPen(QColor(scene.line),2));painter.setBrush(QColor(scene.background))
    for p in scene.station_points:painter.drawEllipse(p,4.2,4.2)
    painter.setFont(ui_font(16));painter.setPen(QColor(scene.foreground))
    metrics=QFontMetricsF(painter.font());mx,my,mw,mh=layout.map_rect
    for name,p in scene.depot_points:
        x=max(mx+8,min(p.x()+8,mx+mw-metrics.horizontalAdvance(name)-8))
        y=max(my+metrics.ascent()+8,min(p.y()-8,my+mh-8))
        painter.drawText(QPointF(x,y),name)
    if scene.legend_rect:
        lx,ly,lw,lh=scene.legend_rect
        painter.fillRect(QRectF(lx-4,ly-4,lw+8,lh+8),QColor(scene.map_background))
        for index,(caption,dashed) in enumerate((('下行',False),('上行',True))):
            x=lx+index*108
            pen=QPen(QColor(scene.line),3,Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.FlatCap if dashed else Qt.PenCapStyle.RoundCap)
            if dashed:pen.setDashPattern([14/3,8/3])
            painter.setPen(pen);painter.drawLine(QPointF(x,ly+lh/2),QPointF(x+44,ly+lh/2))
            painter.setFont(ui_font(16));painter.setPen(QColor(scene.muted))
            painter.drawText(QRectF(x+52,ly,52,lh),int(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter),caption)
    painter.restore()
    for item in layout.text_items:
        _check(cancel)
        if visible is not None and not QRectF(*item.rect).intersects(visible):continue
        painter.setFont(_font(item))
        painter.setPen(QColor(('#A8A8A8' if scene.request.options.theme=='night' else '#888888')
            if item.role in ('annotation','footer','unit') else scene.muted if item.role in ('muted','label') else
            scene.line if item.role=='number' and scene.request.options.theme=='night' else scene.foreground))
        if item.role in ('number','unit'):
            metrics=QFontMetricsF(painter.font())
            if metrics.horizontalAdvance(item.text)<=item.rect[2]:
                bounds=metrics.tightBoundingRect(item.text)
                # Align the visible digits, rather than their large font
                # ascent/descent box, with the passenger heading above them.
                painter.drawText(QPointF(item.rect[0]-bounds.left(),item.rect[1]-bounds.top()+2),item.text)
                continue
        align=Qt.AlignmentFlag.AlignRight if item.align=='right' else Qt.AlignmentFlag.AlignLeft
        painter.drawText(QRectF(*item.rect),int(align|Qt.AlignmentFlag.AlignTop|
            Qt.TextFlag.TextWordWrap|Qt.TextFlag.TextWrapAnywhere),item.display_text or item.text)
    for x,y,w in layout.rules:
        painter.setPen(QPen(QColor(scene.rule),1.2));painter.drawLine(QPointF(x,y),QPointF(x+w,y))
        painter.setPen(QPen(QColor(scene.brand),3));painter.drawLine(QPointF(x,y),QPointF(x+48,y))
    if scene.logo is not None and not scene.logo.isNull():
        x,y,w,h=layout.logo_rect
        factor=min(w/scene.logo.width(),h/scene.logo.height())
        sw,sh=scene.logo.width()*factor,scene.logo.height()*factor
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(QRectF(x+(w-sw)/2,y+(h-sh)/2,sw,sh),scene.logo)


def _image(scene,width,height,cancel=None,*,offset=0,full_height=None):
    if width*height*4>MAX_IMAGE_BYTES:raise ExportError('图像缓冲超出内存限制，请减小尺寸或精度')
    image=QImage(width,height,QImage.Format.Format_RGB32)
    if image.isNull():raise ExportError('无法分配导出图像缓冲')
    image.fill(QColor(scene.background));painter=QPainter(image)
    try:
        total_height=full_height or height
        factor=min(width/scene.layout.width,total_height/scene.layout.height)
        dx=(width-scene.layout.width*factor)/2;dy=(total_height-scene.layout.height*factor)/2
        painter.translate(dx,dy-offset)
        painter.scale(factor,factor)
        visible=(QRectF(-dx/factor,(offset-dy)/factor,width/factor,height/factor)
            if full_height is not None else None)
        _paint(painter,scene,cancel,visible)
    finally:painter.end()
    return image


def preview(request,target_size=(900,600),cancel=None):
    width,height=(target_size.width(),target_size.height()) if hasattr(target_size,'width') else target_size
    if width<=0 or height<=0:raise ExportError('预览区域尺寸无效')
    scene=_prepare_scene(request,cancel)
    factor=min(width/scene.layout.width,height/scene.layout.height,2048/scene.layout.width,2048/scene.layout.height)
    image=_image(scene,max(1,round(scene.layout.width*factor)),max(1,round(scene.layout.height*factor)),cancel)
    image.setText('logo_status',scene.logo_status)
    return image


def _chunk(stream,name,payload):
    stream.write(struct.pack('>I',len(payload))+name+payload+
        struct.pack('>I',zlib.crc32(name+payload)&0xffffffff))


def _png(scene,path,size,cancel):
    w,h=size.pixels
    # Rasterizing an antialiased path at the image boundary can round coverage
    # differently. Paint guard rows and encode only the interior of each strip.
    guard=2
    rows=max(1,min(512,STRIP_BYTES//(w*4)-guard*2))
    with open(path,'wb') as stream:
        stream.write(b'\x89PNG\r\n\x1a\n')
        _chunk(stream,b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))
        ppm=round(scene.request.options.ppi/0.0254)
        _chunk(stream,b'pHYs',struct.pack('>IIB',ppm,ppm,1))
        compressor=zlib.compressobj(6)
        for offset in range(0,h,rows):
            _check(cancel)
            start=max(0,offset-guard);end=min(h,offset+rows+guard)
            image=_image(scene,w,end-start,cancel,offset=start,full_height=h)
            rgb=image.convertToFormat(QImage.Format.Format_RGB888)
            view=rgb.constBits();stride=rgb.bytesPerLine()
            for y in range(offset-start,min(offset+rows,h)-start):
                _check(cancel)
                data=compressor.compress(b'\0'+bytes(view[y*stride:y*stride+w*3]))
                if data:_chunk(stream,b'IDAT',data)
        data=compressor.flush()
        if data:_chunk(stream,b'IDAT',data)
        _chunk(stream,b'IEND',b'')


def _jpg(scene,path,size,cancel):
    image=_image(scene,*size.pixels,cancel)
    ppm=round(scene.request.options.ppi/0.0254)
    image.setDotsPerMeterX(ppm);image.setDotsPerMeterY(ppm)
    writer=QImageWriter(str(path),b'jpg');writer.setQuality(95)
    _check(cancel)
    if not writer.write(image):raise ExportError(writer.errorString())


def _pdf(scene,path,size,cancel):
    writer=QPdfWriter(str(path));writer.setResolution(scene.request.options.ppi)
    writer.setPageSize(QPageSize(QSizeF(*size.millimetres),QPageSize.Unit.Millimeter))
    writer.setPageMargins(QMarginsF(0,0,0,0))
    painter=QPainter(writer)
    try:
        factor=min(writer.width()/scene.layout.width,writer.height()/scene.layout.height)
        painter.translate((writer.width()-scene.layout.width*factor)/2,
            (writer.height()-scene.layout.height*factor)/2)
        painter.scale(factor,factor)
        _paint(painter,scene,cancel)
    finally:painter.end()


def render_export(request,destination,cancel=None):
    size=measure_output(request.options)
    if request.options.format=='JPG' and size.width_px*size.height_px*4>MAX_IMAGE_BYTES:
        raise ExportError('JPG 尺寸超出内存限制，请减小尺寸或精度')
    scene=_prepare_scene(request,cancel)
    destination=Path(destination)
    if not destination.parent.is_dir():raise ExportError('导出目录不存在')
    fd,name=tempfile.mkstemp(prefix='.'+destination.stem+'-',suffix='.partial',dir=destination.parent)
    os.close(fd)
    staging=Path(name)
    try:
        {'PNG':_png,'JPG':_jpg,'PDF':_pdf}[request.options.format](scene,staging,size,cancel)
        _check(cancel)
        if hasattr(cancel,'commit'):cancel.commit(lambda:os.replace(staging,destination))
        else:os.replace(staging,destination)
    except Exception:
        staging.unlink(missing_ok=True)
        raise
    return ExportResult(str(destination),size,request.options.format)
