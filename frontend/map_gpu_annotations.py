"""Small CPU annotation layer above retained GPU map geometry."""
from __future__ import annotations

import math
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
import stats_tokens as tokens
from map_scale import detail_fraction, stop_outline, stop_radius
from semantic_colors import canonical_key


class _Occupied:
    """The same rectangle collision rule, with a bounded neighbouring lookup."""
    def __init__(self, rectangles):
        self.cells={}
        for rect in rectangles:
            self.add(rect)

    @staticmethod
    def _keys(rect):
        return ((x,y) for x in range(math.floor(rect.left()/64),math.floor(rect.right()/64)+1)
                for y in range(math.floor(rect.top()/32),math.floor(rect.bottom()/32)+1))

    def add(self, rect):
        for key in self._keys(rect):
            self.cells.setdefault(key,[]).append(rect)

    def intersects(self, rect):
        return any(rect.intersects(other) for key in self._keys(rect)
                   for other in self.cells.get(key,()))


class AnnotationCache:
    """Query-dependent stop membership and reusable glyph outlines."""
    def __init__(self,surface,prepared):
        modes=surface.options['layer_modes']
        self.routes=tuple(r for r in prepared.routes if modes is None or
                          canonical_key('mode',r.mode) in modes) if surface.options['routes'] else ()
        self.stops=surface._display_stops(self.routes,clip=False)
        self.positions=np.asarray([(p[0],p[2]) for _,p in self.stops],dtype=float).reshape(-1,2)
        self.label_candidates=[]
        for route in self.routes:
            candidates=[]
            for paths,_ in surface._route_path_groups(route):
                for path in surface._continuous_paths(paths):
                    if len(path)<2:
                        continue
                    points=[]
                    for fraction in (.5,.3,.7,.15,.85):
                        index=fraction*(len(path)-1);lower=int(index)
                        a,b=path[lower],path[min(lower+1,len(path)-1)]
                        points.append((a[0]+(b[0]-a[0])*(index-lower),
                                       a[2]+(b[2]-a[2])*(index-lower)))
                    candidates.append(tuple(points))
            self.label_candidates.append((route,tuple(candidates)))
        self.glyphs={}
        self.font_key=None
        self._halo=QPen(QColor('#FFFFFF'),3.,Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin)
        self._label_points=np.asarray([point for _,paths in self.label_candidates
                                      for candidates in paths for point in candidates],dtype=float).reshape(-1,2)
        self._label_ranges=[];offset=0
        for route,paths in self.label_candidates:
            ranges=[]
            for candidates in paths:
                ranges.append((offset,offset+len(candidates)));offset+=len(candidates)
            self._label_ranges.append((route,tuple(ranges)))

    def _prepare_labels(self,painter,surface):
        font=painter.font();device=painter.device()
        font_key=(font.toString(),device.logicalDpiX(),device.logicalDpiY(),device.devicePixelRatioF())
        if self.font_key!=font_key:
            self.font_key=font_key;self.glyphs.clear()
        self._font=font;self._metrics=painter.fontMetrics()
        self._width=surface.width();self._height=surface.height()
        self._rect=QRectF(surface.rect())

    def label(self,painter,surface,point,text,occupied,color=tokens.TEXT_PRIMARY):
        self._prepare_labels(painter,surface)
        return self._paint_label(painter,point,text,occupied,color)

    def _paint_label(self,painter,point,text,occupied,color=tokens.TEXT_PRIMARY):
        if point.x() < -250 or point.x()>self._width or point.y()<0 or point.y()>self._height+12:
            return False
        text=str(text)
        if not text.strip():
            return False
        glyph=self.glyphs.get(text)
        if glyph is None:
            metrics=self._metrics;path=QPainterPath()
            path.addText(0,metrics.ascent()+2,self._font,text)
            glyph=(metrics.horizontalAdvance(text)+12,path)
            self.glyphs[text]=glyph
        width,path=glyph
        rect=QRectF(point.x()+7,point.y()-12,width,22)
        if not self._rect.contains(rect) or occupied.intersects(rect):
            return False
        occupied.add(rect.adjusted(-3,-3,3,3))
        painter.save();painter.translate(rect.x()+6,rect.y())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(self._halo)
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(color))
        painter.drawPath(path);painter.restore()
        return True


def paint_annotations(painter,surface,prepared,cache):
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setFont(surface.font())
    rectangles=[QRectF(10,surface.height()-55,180,45),QRectF(surface.width()-45,10,35,65)]
    rectangles.extend(rect.adjusted(-3,-3,3,3) for rect,_,_ in surface._legend_layout(painter))
    cache._prepare_labels(painter,surface)
    occupied=_Occupied(rectangles)
    if surface.options['line_numbers']:
        count=0
        limit=max(3,int(surface.width()*surface.height()/(48000-28000*detail_fraction(surface.zoom,.25))))
        label_points=_screen_points(cache._label_points,surface)
        for route,paths in cache._label_ranges:
            if count>=limit:
                break
            color=surface._route_color(route).name()
            text=surface.route_label(route)
            for start,end in paths:
                if any(cache._paint_label(painter,QPointF(*point),text,occupied,color)
                       for point in label_points[start:end]):
                    count+=1;break
    bounds=surface._viewport_bounds(40.)
    positions=cache.positions
    selected=np.flatnonzero((positions[:,0]>=bounds[0]) & (positions[:,0]<=bounds[2]) &
                            (positions[:,1]>=bounds[1]) & (positions[:,1]<=bounds[3]))
    pen=QPen(QColor(tokens.TEXT_SECONDARY),stop_outline(surface.zoom))
    brush=QColor(tokens.CARD_BG)
    cells=set();radius=stop_radius(surface.zoom)
    screen_points=_screen_points(positions[selected],surface)
    if surface.options['stops']:
        painter.setPen(pen);painter.setBrush(brush)
    for index,screen in zip(selected,screen_points):
        stop,position=cache.stops[index]
        point=QPointF(*screen)
        if surface.options['stops']:
            cell=(int(point.x()/6),int(point.y()/6))
            if surface.zoom>=.15 or cell not in cells:
                cells.add(cell)
                painter.drawEllipse(point,radius,radius)
            if surface.options['stop_names'] and surface.zoom>=.15:
                cache._paint_label(painter,point,stop.name,occupied)
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


def _screen_points(positions,surface):
    """Same double operations and axis convention as world_to_screen."""
    points=(positions-np.asarray(surface.center))*surface.zoom
    points[:,0]=surface.width()/2+points[:,0]
    points[:,1]=surface.height()/2-points[:,1]
    return points
