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
    bounds=QFontMetricsF(_font(item)).boundingRect(QRectF(0,0,width,10000),
        int(Qt.TextFlag.TextWordWrap|Qt.TextFlag.TextWrapAnywhere),text)
    return max(bounds.height()+2,size*1.25)


def _portrait_layout(request,width,height):
    """Portrait pages stack the square map over the complete information area."""
    margin=48.;content_width=width-2*margin
    for map_fraction,body in ((.54,22),(.50,22),(.46,22),(.46,20),(.42,18)):
        side=min(content_width,height*map_fraction)
        map_top=28.;info_top=map_top+side+32
        items=[];rules=[];y=info_top
        def emit(value,x,y,w,size,role='label',weight=400,align='left',display=None):
            h=_text_height(display or value,w,size,role,weight)
            items.append(TextItem(value,(x,y,w,h),size,weight,role,align,display))
            return h
        company_h=emit(request.information.company_name,margin,y,content_width-88,32,'heading',600)
        logo=(width-margin-64,y,64,64)
        y+=max(company_h,64)+8
        route_size=112
        while route_size>44 and _text_height(request.information.route_name,content_width,route_size,'route',650)>160:
            route_size-=4
        y+=emit(request.information.route_name,margin,y,content_width,route_size,'route',650)+6
        mode=f'{request.information.mode} · {request.information.direction}'
        mode_h=emit(mode,margin,y,content_width*.65,32,'heading',600)
        date_h=emit(request.simulated_date,margin+content_width*.70,y,content_width*.30,24,'muted',400,'right')
        y+=max(mode_h,date_h)+18;rules.append((margin,y,content_width));y+=24
        sections=request.information.sections;bottom=y
        # The map/information relationship is vertical. The two independent
        # data categories use the wide lower area without shrinking all text.
        for index,(section_id,title,rows) in enumerate(sections):
            if len(sections)==2:
                left_width=(content_width-40)*.58
                x=margin if index==0 else margin+left_width+40
                column=left_width if index==0 else content_width-left_width-40
            else:x=margin;column=content_width
            cursor=y+emit(title,x,y,column,28,'heading',600)+12
            for key,label,value in rows:
                if key=='今日客流':
                    cursor+=emit(value.removesuffix(' 人次'),x,cursor,column,76,'number',600)
                    cursor+=emit(label+' · 人次',x,cursor,column,body,'muted')+14
                    continue
                label_w=column*(.40 if key in ('开线日期','最近改线日期','线路车库') else .57)
                value_w=column-label_w-16
                display=(value.replace(' ','\n',1) if key in ('开线日期','最近改线日期') and ' ' in value else value)
                lh=emit(label,x,cursor,label_w,body)
                vh=emit(value,x+label_w+16,cursor,value_w,body+2,'value',500,'right',display)
                cursor+=max(lh,vh)+8
            rules.append((x,cursor+6,column));bottom=max(bottom,cursor+18)
        if bottom<=height-28:
            offset=max(0.,(height-(bottom+28))/2)
            translated=tuple(replace(item,rect=(item.rect[0],item.rect[1]+offset,*item.rect[2:])) for item in items)
            return ExportLayout(width,height,((width-side)/2,map_top+offset,side,side),
                (margin,info_top+offset,content_width,bottom-info_top),translated,
                tuple((x,y+offset,w) for x,y,w in rules),(logo[0],logo[1]+offset,*logo[2:]))
    raise LayoutError('文字无法完整排入纵向画幅，请缩短线路名称或减少字段')


def build_layout(request):
    """Measure every glyph; retry typography density without dropping a field."""
    size=measure_output(request.options)
    width=1536.;height=width*size.height_mm/size.width_mm
    if size.height_mm>size.width_mm:return _portrait_layout(request,width,height)
    attempts=tuple((2/3,body) for body in (22,20,18,16,14))+((.52,16),(.52,14),(.45,14))
    for fraction,body in attempts:
        side=min(height,width*fraction)
        x=side+40;right=width-36;column=right-x
        items=[];rules=[];y=16. if body==14 else 28.;dense=body<=18;compact=body<=16
        def text(value,size,role='label',weight=400,rect_width=None,align='left'):
            nonlocal y
            w=column if rect_width is None else rect_width
            h=_text_height(value,w,size,role,weight)
            items.append(TextItem(value,(x,y,w,h),size,weight,role,align))
            y+=h
            return h
        company_w=column-80;company_top=y
        text(request.information.company_name,20 if compact else 24 if dense else 28,'heading',600,company_w)
        logo_side=56 if body==14 else 64
        logo=(right-logo_side,company_top,logo_side,logo_side)
        y=max(y+8,logo[1]+logo_side+(4 if dense else -6))
        route_size=112
        # Preserve the entire route identity including a long Chinese suffix.
        while route_size>36 and _text_height(request.information.route_name,column,route_size,'route',650)>height*(.09 if compact else .14 if dense else .21):
            route_size-=4
        text(request.information.route_name,route_size,'route',650)
        y+=6
        text(f'{request.information.mode} · {request.information.direction}',24 if compact else 26 if dense else 32,'heading',600)
        y+=6;text(request.simulated_date,18 if compact else 20 if dense else 24,'muted');y+=8 if compact else 14 if dense else 24
        rules.append((x,y,column));y+=16 if dense else 26
        for section_id,title,rows in request.information.sections:
            text(title,20 if body==14 else 22 if compact else 24 if dense else 28,'heading',600)
            y+=4 if body==14 else 8 if dense else 14
            for key,label,value in rows:
                if key=='今日客流':
                    number=value.removesuffix(' 人次')
                    # Keep displayed unit and scope in a separate measured caption.
                    h=text(number,52 if compact else 60 if dense else 76,'number',600)
                    text(label+' · 人次',body,'muted');y+=8 if dense else 12
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
        if y<=height-16:
            block_height=max(side,y+12)
            offset=max(0.,(height-block_height)/2)
            map_y=offset+(block_height-side)/2
            translated=tuple(replace(item,rect=(item.rect[0],item.rect[1]+offset,*item.rect[2:])) for item in items)
            return ExportLayout(width,height,(0.,map_y,side,side),(x,24.,column,height-48),
                translated,tuple((rx,ry+offset,rw) for rx,ry,rw in rules),
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
    map_bg='#0D2539' if night else '#F4F7F8'
    fg='#F3F7FC' if night else '#0A274B'
    muted='#B4CBDD' if night else '#65758A'
    brand,logo,status=_resolve_brand(request,bg)
    line='#20DFF5' if night else color_for('mode',request.route.mode)
    points=[p for path in request.paths for p in path]
    if request.options.show_depot_names:points.extend(d.position for d in request.depots)
    xmin,xmax=min(p[0] for p in points),max(p[0] for p in points)
    zmin,zmax=min(p[2] for p in points),max(p[2] for p in points)
    span=max(xmax-xmin,zmax-zmin,1.)*1.15
    cx,cz=(xmin+xmax)/2,(zmin+zmax)/2
    mx,my,side,_=layout.map_rect
    scale=side/span
    def project(p):return QPointF(mx+side/2+(p[0]-cx)*scale,my+side/2-(p[2]-cz)*scale)
    def path(saved,closed=False):
        _check(cancel)
        if not saved:return None
        # Reject only features entirely outside; never rewrite their coordinates.
        if (max(p[0] for p in saved)<cx-span/2 or min(p[0] for p in saved)>cx+span/2 or
            max(p[2] for p in saved)<cz-span/2 or min(p[2] for p in saved)>cz+span/2):return None
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
    route_paths=tuple(p for saved in request.paths if (p:=path(saved)) is not None)
    # Complete all casings before route bodies, so saved segment joints remain continuous.
    for color,w in ((bg,8),(line,5)):
        for p in route_paths:
            shapes.append(_Shape(p,QPen(QColor(color),w,Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin)))
    stations=tuple(project(s.position) for s in request.stops) if request.options.show_stops else ()
    depots=tuple((d.name,project(d.position)) for d in request.depots) if request.options.show_depot_names else ()
    return _Scene(request,layout,tuple(shapes),stations,depots,bg,map_bg,fg,muted,
        '#365168' if night else '#DDE4EB',brand or muted,line,logo,status)


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
    for name,p in scene.depot_points:painter.drawText(p+QPointF(8,-8),name)
    painter.restore()
    for item in layout.text_items:
        _check(cancel)
        if visible is not None and not QRectF(*item.rect).intersects(visible):continue
        painter.setFont(_font(item))
        painter.setPen(QColor(scene.muted if item.role in ('muted','label') else
            scene.line if item.role=='number' and scene.request.options.theme=='night' else scene.foreground))
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
