"""Frozen scalar annotation reference from f55f47a, for exact pixel parity."""
from types import MethodType
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QImage
import stats_tokens as tokens
from map_scale import detail_fraction, stop_outline, stop_radius
from map_gpu_annotations import AnnotationCache, _Occupied, paint_annotations

def _scalar_label(self,painter,surface,point,text,occupied,color=tokens.TEXT_PRIMARY):
    if point.x() < -250 or point.x()>surface.width() or point.y()<0 or point.y()>surface.height()+12:
        return False
    text=str(text)
    if not text.strip():
        return False
    font_key=painter.font().toString()
    if self.font_key!=font_key:
        self.font_key=font_key;self.glyphs.clear()
    glyph=self.glyphs.get(text)
    if glyph is None:
        metrics=painter.fontMetrics();path=QPainterPath()
        path.addText(0,metrics.ascent()+2,painter.font(),text)
        glyph=(metrics.horizontalAdvance(text)+12,path)
        self.glyphs[text]=glyph
    width,path=glyph
    rect=QRectF(point.x()+7,point.y()-12,width,22)
    if not QRectF(surface.rect()).contains(rect) or occupied.intersects(rect):
        return False
    occupied.add(rect.adjusted(-3,-3,3,3))
    painter.save();painter.translate(rect.x()+6,rect.y())
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor('#FFFFFF'),3.,Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
    painter.drawPath(path)
    painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(color))
    painter.drawPath(path);painter.restore()
    return True


def _scalar_paint(painter,surface,prepared,cache):
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setFont(surface.font())
    rectangles=[QRectF(10,surface.height()-55,180,45),QRectF(surface.width()-45,10,35,65)]
    rectangles.extend(rect.adjusted(-3,-3,3,3) for rect,_,_ in surface._legend_layout(painter))
    occupied=_Occupied(rectangles)
    if surface.options['line_numbers']:
        count=0
        limit=max(3,int(surface.width()*surface.height()/(48000-28000*detail_fraction(surface.zoom,.25))))
        for route,paths in cache.label_candidates:
            if count>=limit:
                break
            color=surface._route_color(route).name()
            for candidates in paths:
                if any(cache.label(painter,surface,surface.world_to_screen(point),
                                   surface.route_label(route),occupied,color) for point in candidates):
                    count+=1;break
    bounds=surface._viewport_bounds(40.)
    positions=cache.positions
    selected=np.flatnonzero((positions[:,0]>=bounds[0]) & (positions[:,0]<=bounds[2]) &
                            (positions[:,1]>=bounds[1]) & (positions[:,1]<=bounds[3]))
    pen=QPen(QColor(tokens.TEXT_SECONDARY),stop_outline(surface.zoom))
    brush=QColor(tokens.CARD_BG)
    cells=set();radius=stop_radius(surface.zoom)
    for index in selected:
        stop,position=cache.stops[index]
        point=surface.world_to_screen(position)
        if surface.options['stops']:
            cell=(int(point.x()/6),int(point.y()/6))
            if surface.zoom>=.15 or cell not in cells:
                cells.add(cell);painter.setPen(pen);painter.setBrush(brush)
                painter.drawEllipse(point,radius,radius)
            if surface.options['stop_names'] and surface.zoom>=.15:
                cache.label(painter,surface,point,stop.name,occupied)
    if surface._highlight and surface._highlight[0]!='route':
        kind,identity=surface._highlight
        if kind=='stop':
            position=next((p for stop,p in cache.stops if stop.id==identity),None)
            if position is not None:surface._draw_stop_highlight(painter,position)
        else:
            index=surface._indexes.get(kind+'s')
            if index:
                item=next((box for item,box in index.entries if item.id==identity),None)
                if item is not None:
                    a=surface.world_to_screen(item[:2]);b=surface.world_to_screen(item[2:])
                    painter.setPen(QPen(QColor(tokens.ACCENT),2));painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(QRectF(a,b).normalized().adjusted(-7,-7,7,7),5,5)
    surface._draw_scale(painter)
    surface._draw_legend(painter)


def test_batched_annotations_match_released_scalar_pixels(qt_application):
    from map_canvas import MapCanvas, _FrameSurface
    from map_model import MapRoute, MapStop, MapSnapshot
    from map_vector import build_vector_map
    from PySide6.QtCore import QSize
    canvas=MapCanvas();canvas.resize(960,680)
    paths=(((0.,0.,0.),(150.,0.,150.),(350.,0.,200.)),
           ((400.,0.,220.),(600.,0.,320.)))
    routes=(MapRoute(1,'Central',503,'a','A','bus',(1,2,3),paths),
            MapRoute(2,'Cross',5,'b','B','tram',(2,4),(tuple(reversed(paths[0])),)))
    stops=tuple(MapStop(i,'Station '+str(i),p) for i,p in enumerate(
        ((0.,0.,0.),(150.,0.,150.),(151.,0.,151.),(450.,0.,220.)),1))
    canvas.set_snapshot(MapSnapshot(stops=stops,routes=routes,bounds=(-10.,-10.,700.,400.)))
    surface=_FrameSurface(canvas);canvas.close()
    surface.options.update(stops=True,stop_names=True,line_numbers=True)
    prepared=build_vector_map(surface)
    baseline=AnnotationCache(surface,prepared);baseline.label=MethodType(_scalar_label,baseline)
    candidate=AnnotationCache(surface,prepared)
    assert len(candidate.stops)==4 and len(candidate.label_candidates)==2
    for width,height,ratio in ((960,680,1.),(400,300,1.25),(400,300,2.)):
        surface._size=QSize(width,height)
        for zoom in (.0001,.14999999,.15,.15000001,.4,1.,16.,100.):
            surface.center=(150.123456789,150.987654321);surface.zoom=zoom
            for numbers,names in ((True,True),(False,True),(True,False)):
                surface.options.update(line_numbers=numbers,stop_names=names)
                images=[]
                for draw,cache in ((_scalar_paint,baseline),(paint_annotations,candidate)):
                    image=QImage(round(width*ratio),round(height*ratio),QImage.Format.Format_ARGB32_Premultiplied)
                    image.setDevicePixelRatio(ratio);image.fill(QColor('#f1f4f6'))
                    painter=QPainter(image)
                    try:draw(painter,surface,prepared,cache)
                    finally:painter.end()
                    images.append(np.frombuffer(image.constBits(),dtype=np.uint8).copy())
                assert np.array_equal(*images),(width,height,ratio,zoom,numbers,names)


def test_metric_legend_font_setup_preserves_released_label_pixels(qt_application):
    from map_canvas import MapCanvas, _FrameSurface
    from map_model import MapRoute, MapStop, MapSnapshot
    from map_vector import build_vector_map
    from semantic_colors import MetricLegend
    canvas=MapCanvas();canvas.resize(600,400)
    font=canvas.font();font.setPixelSize(22);canvas.setFont(font)
    route=MapRoute(1,'Central',1,'a','A','bus',(1,),
                   (((-100.,0.,0.),(100.,0.,0.)),))
    canvas.set_snapshot(MapSnapshot(routes=(route,),stops=(MapStop(1,'Central Station',(0.,0.,0.)),),
                                    bounds=(-100.,-100.,100.,100.)))
    canvas.set_options(legend_items=MetricLegend('passengers','2026-10-22','today'),legend_external=False)
    surface=_FrameSurface(canvas);canvas.close()
    surface.center=(0.,0.);surface.zoom=1.
    prepared=build_vector_map(surface)
    reference=AnnotationCache(surface,prepared);reference.label=MethodType(_scalar_label,reference)
    candidate=AnnotationCache(surface,prepared)
    images=[]
    for draw,cache in ((_scalar_paint,reference),(paint_annotations,candidate)):
        image=QImage(600,400,QImage.Format.Format_ARGB32_Premultiplied);image.fill(QColor('#f1f4f6'))
        painter=QPainter(image)
        try:draw(painter,surface,prepared,cache)
        finally:painter.end()
        images.append(image)
    assert images[0]==images[1]
