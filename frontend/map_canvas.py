"""Native, read-only map rendering of immutable game geometry in metres."""
from __future__ import annotations

from dataclasses import dataclass
from collections import OrderedDict
import math
import threading
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal, Slot, QTimer, QObject, QRunnable, QThreadPool
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from PySide6.QtWidgets import QWidget, QApplication
from shiboken6 import isValid

import stats_tokens as tokens
from stats_typography import ui_font
from map_model import MapSnapshot, road_display_level
from map_visibility import operating_paths, visible_route_stop_ids
from display_rules import format_line_name
from semantic_colors import MetricLegend
from background_work import CooperativeCancellation

# Public visual interpretation, not Apple-internal style constants. Widths
# below are logical pixel symbols when a measured full road width is missing.
MAP_BACKGROUND = '#F1F4F6'
ROAD_STYLES = {
    'express': ('#F7E4AB','#D7C58F',2.8,8.0),
    'arterial': ('#FFF3D2','#D9D1B9',2.1,6.8),
    'secondary': ('#FFFFFF','#C9D1D7',1.3,5.0),
    'local': ('#FFFFFF','#D0D8DE',.65,3.6),
    'pedestrian': ('#E3E9EC','#C4CFD5',.55,2.4),
    'track': ('#9BA8B1','#E4E9ED',.8,1.5),
    'unknown': ('#D6DEE3','#E6ECEF',.55,1.2),
}


@dataclass(frozen=True, slots=True)
class RoadStyle:
    level: str
    fill: str
    shell: str
    width: float
    casing: float


def road_style(road,zoom):
    """Shared map/legend style in logical pixels; no inferred physical width."""
    level = road_display_level(road)
    fill,shell,overview,detail = ROAD_STYLES[level]
    transition = max(0.,min(1.,(zoom-.10)/.35))
    width = overview+(detail-overview)*transition
    if zoom>.45:
        width = detail*min(2.2,math.sqrt(zoom/.45))
    if road.width is not None and road.width>0 and zoom>=.25 and level!='track':
        width = max(1.,min(48.,road.width*zoom))
    casing = .65 if zoom<.15 else 1.1 if zoom<.5 else 1.6
    if level in ('local','unknown','pedestrian') and zoom<.15:
        casing = .25
    return RoadStyle(level,fill,shell,width,casing)


@dataclass(frozen=True, slots=True)
class MapSearchResult:
    kind: str
    id: int
    name: str
    bounds: tuple[float, float, float, float]

    @property
    def label(self):
        return self.name


def _bounds(points):
    points = tuple(points)
    if not points:
        return None
    xs, zs = [p[0] for p in points], [p[2] for p in points]
    return min(xs), min(zs), max(xs), max(zs)


def continuous_paths(paths):
    """Join ordered curves only at identical saved xyz; never bridge a gap."""
    runs,current = [],[]
    for path in paths:
        if not path:
            if current:
                runs.append(tuple(current))
                current = []
            continue
        if current and current[-1] == path[0]:
            current.extend(path[1:])
        else:
            if current:
                runs.append(tuple(current))
            current = list(path)
    if current:
        runs.append(tuple(current))
    return tuple(runs)


class _IndexCancelled(Exception):
    pass


def _index_check(cancelled):
    if cancelled is not None and cancelled():
        raise _IndexCancelled()


class _SpatialIndex:
    """Uniform world grid with overflow for long features; no geometry copies."""
    def __init__(self, entries, bounds, cancelled=None):
        self.cell = max(1., max(bounds[2]-bounds[0], bounds[3]-bounds[1]) / 32)
        self.bins = {}
        self.large = []
        self.entries = entries
        for i, (_, box) in enumerate(entries):
            _index_check(cancelled)
            a,b,c,d = self._cells(box)
            if (c-a+1)*(d-b+1) > 256:
                self.large.append(i)
            else:
                for x in range(a,c+1):
                    for y in range(b,d+1):
                        self.bins.setdefault((x,y), []).append(i)

    def _cells(self, box):
        return tuple(math.floor(v/self.cell) for v in box)

    def query(self, box):
        a,b,c,d = self._cells(box)
        found = set(self.large)
        if (c-a+1)*(d-b+1) > 4096:
            found.update(range(len(self.entries)))
        else:
            for x in range(a,c+1):
                for y in range(b,d+1):
                    found.update(self.bins.get((x,y), ()))
        for i in sorted(found):
            item, bounds = self.entries[i]
            if bounds[0] <= box[2] and bounds[2] >= box[0] and bounds[1] <= box[3] and bounds[3] >= box[1]:
                yield item


_INDEX_LAYERS = ('roads', 'buildings', 'routes', 'stops', 'junctions')


def _layer_key(snapshot, name):
    return (id(getattr(snapshot, name)), id(snapshot.stops if name == 'routes' else None), snapshot.bounds)


def _index_key(snapshot):
    return (snapshot.source_hash, snapshot.asset_signature, snapshot.bounds,
            *(id(getattr(snapshot, name)) for name in _INDEX_LAYERS))


@dataclass(frozen=True)
class _IndexState:
    snapshot: object
    caches: dict
    indexes: dict
    boxes: dict
    stops: dict
    roads: dict
    connection_boxes: dict


def _prepare_indexes(snapshot, caches, previous=None, cancelled=None, *, cached_only=False):
    """Pure geometry preparation; published structures are never mutated."""
    caches = {name: OrderedDict(caches.get(name, ())) for name in _INDEX_LAYERS}
    if cached_only and any(_layer_key(snapshot, name) not in caches[name] for name in _INDEX_LAYERS):
        return None
    old = previous.snapshot if previous is not None else MapSnapshot()
    stops = (previous.stops if previous is not None and snapshot.stops is old.stops
             else {stop.id:stop for stop in snapshot.stops})
    roads = (previous.roads if previous is not None and snapshot.roads is old.roads
             else {road.id:road for road in snapshot.roads})
    if previous is not None and snapshot.junctions is old.junctions:
        connection_boxes = previous.connection_boxes
    else:
        connection_boxes = {}
        for junction in snapshot.junctions:
            for connection in junction.connections:
                _index_check(cancelled)
                connection_boxes[connection.id] = _bounds(p for path in connection.paths for p in path)
    indexes, boxes = {}, {}
    for name in _INDEX_LAYERS:
        _index_check(cancelled)
        items = getattr(snapshot, name)
        stop_dependency = snapshot.stops if name == 'routes' else None
        cache, key = caches[name], _layer_key(snapshot, name)
        cached = cache.get(key)
        if cached is not None:
            cache.move_to_end(key)
            indexes[name], boxes[name] = cached[2:]
            continue
        entries = []
        for item in items:
            _index_check(cancelled)
            if name in ('roads', 'routes', 'junctions'):
                points = [p for path in item.paths for p in path]
                if name == 'routes':
                    points += [p for path in item.depot_paths for p in path]
                    points += [p for leg in item.leg_paths for path in leg for p in path]
                    points += [stops[sid].position for sid in item.stop_ids if sid in stops]
            elif name == 'buildings':
                points = item.polygon or (item.position,)
            else:
                points = (item.position,)
            box = _bounds(points)
            if box:
                entries.append((item, box))
        indexes[name] = _SpatialIndex(entries, snapshot.bounds, cancelled)
        boxes[name] = {item.id:box for item, box in entries}
        cache[key] = (items, stop_dependency, indexes[name], boxes[name])
        if len(cache) > 4:
            cache.popitem(last=False)
    return _IndexState(snapshot, caches, indexes, boxes, stops, roads, connection_boxes)


class _IndexSignals(QObject):
    completed = Signal(object, object)
    failed = Signal(object, str)


class _IndexJob(QRunnable):
    def __init__(self, snapshot, caches, previous):
        super().__init__()
        self.snapshot, self.key = snapshot, _index_key(snapshot)
        self.caches = {name: OrderedDict(values) for name, values in caches.items()}
        self.previous = previous
        self.cancelled = threading.Event()
        self.signals = _IndexSignals()

    def cancel(self):
        self.cancelled.set()

    def _emit(self, name, *values):
        if isValid(self.signals):
            try:
                getattr(self.signals, name).emit(*values)
            except RuntimeError:
                if isValid(self.signals):
                    raise

    def run(self):
        try:
            state = _prepare_indexes(self.snapshot, self.caches, self.previous,
                                     CooperativeCancellation(self.cancelled.is_set))
        except _IndexCancelled:
            state = None
        except Exception as error:
            self._emit('failed', self.key, str(error))
            return
        self._emit('completed', self.key, state)



class _MapDrawing:
    """Pure image drawing shared by the widget, exports and background frames."""
    def _cooperate(self):
        pass  # Synchronous GUI painting must never sleep.

    def world_to_screen(self, point):
        x,z = (point[0],point[2]) if len(point) == 3 else point
        return QPointF(self.width()/2+(x-self.center[0])*self.zoom,
                       self.height()/2-(z-self.center[1])*self.zoom)


    def screen_to_world(self, point):
        return (self.center[0]+(point.x()-self.width()/2)/self.zoom,
                self.center[1]-(point.y()-self.height()/2)/self.zoom)


    def route_paths(self,route):
        return operating_paths(route,self.options['direction'])


    def _route_path_groups(self,route):
        if (self.options['distinguish_directions'] and self.options['direction']=='whole'
                and route.direction.kind=='roundtrip' and route.direction.terminal_index is not None
                and route.leg_paths):
            return ((operating_paths(route,'down'),False),(operating_paths(route,'up'),True))
        return ((self.route_paths(route),False),)


    def _route_width(self,route,default):
        from semantic_colors import canonical_key
        value = self.options['mode_widths'].get(canonical_key('mode',route.mode),default)
        try:
            value = float(value)
        except (ValueError,TypeError):
            return default
        return value if math.isfinite(value) and value>0 else default


    @staticmethod
    def road_level(road):
        """Display classes from actual asset metadata; elevation is separate."""
        return road_display_level(road)


    @staticmethod
    def route_label(route):
        return format_line_name(route.number,route.name)


    def _visible(self,name):
        if name in self._indexes:
            for item in self._indexes[name].query(self._viewport_bounds()):
                self._cooperate()
                yield item


    def _viewport_bounds(self):
        tl = self.screen_to_world(QPointF(-40,-40))
        br = self.screen_to_world(QPointF(self.width()+40,self.height()+40))
        return tl[0],br[1],br[0],tl[1]


    def _polyline(self,path,offset=0.):
        self._cooperate()
        world = self._world_polygon(path)
        polygon = self._transform().map(world)
        if offset and len(polygon)>1:
            points = list(polygon)
            distances = [0.]
            for a,b in zip(points,points[1:]):
                distances.append(distances[-1]+math.hypot(b.x()-a.x(),b.y()-a.y()))
            total = distances[-1]
            # Interpolate only along already-known screen edges. The style
            # tapers to the exact saved fragment endpoint, never a new bridge.
            limits = sorted({min(12.,total/2),max(total-12.,total/2)})
            expanded,positions = [],[]
            for i,(a,b) in enumerate(zip(points,points[1:])):
                expanded.append(a);positions.append(distances[i])
                span = distances[i+1]-distances[i]
                for limit in limits:
                    if distances[i]<limit<distances[i+1] and span:
                        expanded.append(a+(b-a)*((limit-distances[i])/span))
                        positions.append(limit)
            expanded.append(points[-1]);positions.append(total)
            points = expanded
            shifted = []
            for i,p in enumerate(points):
                tangent = points[min(i+1,len(points)-1)]-points[max(0,i-1)]
                length = math.hypot(tangent.x(),tangent.y()) or 1
                amount = offset*max(0.,min(1.,positions[i]/12,(total-positions[i])/12))
                shifted.append(p+QPointF(-tangent.y()*amount/length,tangent.x()*amount/length))
            return QPolygonF(shifted)
        return polygon


    def _continuous_paths(self,paths):
        paths = tuple(paths)
        key = tuple(id(path) for path in paths)
        if key not in self._continuous_cache:
            # Holding both source and result avoids id reuse by transient runs.
            self._continuous_cache[key] = (paths,continuous_paths(paths))
        return self._continuous_cache[key][1]


    def _lane_margins(self,road,lane_index,style):
        """Partition a road symbol at observed lane midpoints and outer edges.

        These are screen margins around a saved turning curve, not a claimed
        junction footprint. Outermost lanes carry the street's outer margin;
        centring every lane's width on its centreline would shrink the street.
        """
        if not road.width or road.width<=0:
            return None
        lanes = sorted((lane for lane in road.lanes
                        if lane.type_mask&0x1f000000 and
                        (lane.type_mask&3 or lane.type_mask&4 and lane.turn_directions)),
                       key=lambda lane:lane.offset)
        if len(lanes)<2:
            return None
        index = next((i for i,lane in enumerate(lanes) if lane.index==lane_index),None)
        if index is None:
            return None
        lane = lanes[index]
        if not lane.type_mask&0x300:
            return None
        low,high = -road.width/2,road.width/2
        sidewalks = [lane.offset for lane in road.lanes if lane.type_mask&0x10000]
        if sidewalks and road.sidewalk_left is not None and road.sidewalk_right is not None:
            low = min(sidewalks)-road.sidewalk_left/2
            high = max(sidewalks)+road.sidewalk_right/2
        low = (lanes[index-1].offset+lane.offset)/2 if index else low
        high = (lane.offset+lanes[index+1].offset)/2 if index+1<len(lanes) else high
        scale = style.width/road.width
        margins = (low*scale-lane.offset*self.zoom,high*scale-lane.offset*self.zoom)
        # The stored offset follows the road's canonical travel tangent.
        # Backward lanes follow the reverse tangent on their saved turn curve.
        return margins if lane.type_mask&0x100 else (-margins[1],-margins[0])


    def _lane_surface(self,path,start,end,casing):
        polygon = self._polyline(path)
        if len(polygon)<2:
            return None
        arcs = [0.]
        for a,b in zip(polygon,list(polygon)[1:]):
            arcs.append(arcs[-1]+math.hypot(b.x()-a.x(),b.y()-a.y()))
        if not arcs[-1]:
            return None
        left,right,outer_left,outer_right = [],[],[],[]
        for i,point in enumerate(polygon):
            a,b = polygon[max(0,i-1)],polygon[min(len(polygon)-1,i+1)]
            dx,dy = b.x()-a.x(),b.y()-a.y()
            length = math.hypot(dx,dy)
            normal = QPointF(-dy/length,dx/length) if length else QPointF()
            t = arcs[i]/arcs[-1]
            low,high = (start[j]*(1-t)+end[j]*t for j in (0,1))
            left.append(point+normal*low);right.append(point+normal*high)
            outer_left.append(point+normal*(low-casing/2))
            outer_right.append(point+normal*(high+casing/2))
        return (QPolygonF(left+list(reversed(right))),
                QPolygonF(outer_left+list(reversed(outer_right))))


    def _transform(self):
        return QTransform(self.zoom,0.,0.,-self.zoom,
                          self.width()/2-self.center[0]*self.zoom,
                          self.height()/2+self.center[1]*self.zoom)


    def _world_polygon(self,path):
        level = math.floor(math.log2(1/self.zoom))
        identity = (id(path),level)
        world = self._world_polygons.get(identity)
        if world is None:
            points = self._simplify(path,.65*2**level)
            world = QPolygonF([QPointF(p[0],p[2]) for p in points])
            self._world_polygons[identity] = world
        return world


    @staticmethod
    def _simplify(path,tolerance):
        """RDP with <0.65 projected pixel error, endpoints and gaps preserved."""
        if len(path)<3:
            return path
        retained = {0,len(path)-1}
        stack = [(0,len(path)-1)]
        squared = tolerance*tolerance
        while stack:
            first,last = stack.pop()
            a,b = path[first],path[last]
            dx,dz = b[0]-a[0],b[2]-a[2]
            length = dx*dx+dz*dz
            maximum,index = squared,None
            for i in range(first+1,last):
                p = path[i]
                ratio = max(0.,min(1.,((p[0]-a[0])*dx+(p[2]-a[2])*dz)/length)) if length else 0.
                distance = (p[0]-a[0]-ratio*dx)**2+(p[2]-a[2]-ratio*dz)**2
                if distance>maximum:
                    maximum,index = distance,i
            if index is not None:
                retained.add(index)
                stack.extend(((first,index),(index,last)))
        return tuple(path[i] for i in sorted(retained))


    def _path_key(self,path):
        identity = id(path)
        if identity not in self._path_keys:
            canonical = min(tuple(path),tuple(reversed(path)))
            self._path_keys[identity] = (hash(canonical),len(path),canonical[:1],canonical[-1:])
        return self._path_keys[identity]


    def _draw_path(self,painter,path,pen,offset=0.):
        if len(path)<2:
            return QPolygonF()
        polygon = self._polyline(path,offset)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(polygon)
        return polygon


    def _path_visible(self,path,viewport):
        identity=id(path)
        cached=self._path_bounds.get(identity)
        if cached is None:
            cached=(path,_bounds(path))
            self._path_bounds[identity]=cached
        box=cached[1]
        return box is not None and box[0]<=viewport[2] and box[2]>=viewport[0] and box[1]<=viewport[3] and box[3]>=viewport[1]


    def _route_color(self,route):
        colors = self.options['route_colors']
        explicit = colors.get(route.id,colors.get(str(route.id)))
        if explicit:
            return QColor(explicit)
        try:
            from semantic_colors import color_for
            return QColor(color_for('line',route.id))
        except ImportError:
            return QColor(tokens.COMPANY_COLORS[route.id % len(tokens.COMPANY_COLORS)])


    def _label(self,painter,point,text,occupied,color=tokens.TEXT_PRIMARY):
        if point.x() < -250 or point.x()>self.width() or point.y()<0 or point.y()>self.height()+12:
            return False
        if not str(text).strip():
            return False
        width = painter.fontMetrics().horizontalAdvance(str(text))+12
        rect = QRectF(point.x()+7,point.y()-12,width,22)
        if not QRectF(self.rect()).contains(rect) or any(rect.intersects(r) for r in occupied):
            return False
        occupied.append(rect.adjusted(-3,-3,3,3))
        path = QPainterPath()
        metrics = painter.fontMetrics()
        path.addText(rect.x()+6,rect.y()+metrics.ascent()+2,painter.font(),str(text))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor('#FFFFFF'),3.,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPath(path)
        return True


    def _paint_base(self,painter):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(),QColor(MAP_BACKGROUND))
        if self.options['buildings']:
            for building in self._visible('buildings'):
                selected = self.options['building_classes']
                uses = self.options['building_uses']
                groups = building.combined_groups
                present = {c.group for c in groups if c.count is not None and c.count>0}
                if building.category in ('transport','special'):
                    present = {building.category}
                if not present:
                    present = {'unknown'}
                if selected is not None and not present.intersection(selected):
                    continue
                if uses is not None and getattr(building,'usage',building.category) not in uses:
                    continue
                if len(building.polygon)<3:
                    continue
                box = self._boxes['buildings'][building.id]
                if (box[2]-box[0])*(box[3]-box[1])*self.zoom*self.zoom<.8:
                    continue
                polygon = self._polyline(building.polygon)
                if polygon.boundingRect().width()*polygon.boundingRect().height()<.8:
                    continue
                colors = self.options['building_colors']
                painter.setBrush(QColor(colors.get(building.id,colors.get(str(building.id),'#DCE3E8'))))
                painter.setPen(QPen(QColor('#C4CDD3'),.45 if self.zoom<.15 else .7))
                painter.drawPolygon(polygon)
        if self.options['roads']:
            roads = list(self._visible('roads'))
            strata = {0:[],1:[],2:[]}
            ranking = {'unknown':0,'local':1,'pedestrian':2,'secondary':3,'arterial':4,'express':5,'track':6}
            road_styles = {}
            for road in roads:
                levels = self.options['road_levels']
                if levels is not None and self.road_level(road) not in levels:
                    continue
                style = road_style(road,self.zoom)
                road_styles[road.id] = style
                level,fill,shell,width,casing = style.level,style.fill,style.shell,style.width,style.casing
                batches = []
                for i,path in enumerate(road.paths):
                    if len(path)<2:
                        batches.append((None,[]))
                        continue
                    bridge = bool(road.bridge_masks[i]) if i<len(road.bridge_masks) else road.bridge
                    tunnel = bool(road.tunnel_masks[i]) if i<len(road.tunnel_masks) else road.tunnel
                    layer = 0 if tunnel else 2 if bridge else 1
                    if batches and batches[-1][0]==layer:
                        batches[-1][1].append(path)
                    else:
                        batches.append((layer,[path]))
                for layer,paths in batches:
                    for path in self._continuous_paths(paths):
                        polygon = self._polyline(path)
                        if self.zoom<.15 and level in ('local','pedestrian','unknown') and polygon.boundingRect().width()+polygon.boundingRect().height()<1.5:
                            continue
                        strata[layer].append((ranking[level],polygon,fill,shell,width,casing,layer==0,None))
            viewport = self._viewport_bounds()
            for junction in self._visible('junctions'):
                layer = 0 if junction.tunnel else 2 if junction.bridge else 1
                for connection in junction.connections:
                    box = self._connection_boxes.get(connection.id)
                    if box is None or box[0]>viewport[2] or box[2]<viewport[0] or box[1]>viewport[3] or box[3]<viewport[1]:
                        continue
                    source = self._roads.get(connection.source_road_id)
                    target = self._roads.get(connection.target_road_id)
                    if source is None or target is None:
                        continue
                    styles = []
                    for road in (source,target):
                        style = road_styles.get(road.id)
                        if style is None:
                            style = road_style(road,self.zoom)
                            road_styles[road.id] = style
                        styles.append(style)
                    levels = self.options['road_levels']
                    if levels is not None and any(style.level not in levels for style in styles):
                        continue
                    style = min(styles,key=lambda s:s.width)
                    # Saved paths are lane centre curves, not a junction road
                    # polygon. A lane receives only a fraction of its related
                    # road's pixel symbol, never the full road width.
                    widths = [s.width/max(2,(r.lanes_a or 0)+(r.lanes_b or 0)) for r,s in zip((source,target),styles)]
                    width = max(.5,min(widths))
                    casing = .2 if self.zoom<.15 else .45
                    start = self._lane_margins(source,connection.source_lane,styles[0])
                    end = self._lane_margins(target,connection.target_lane,styles[1])
                    for path in self._continuous_paths(connection.paths):
                        if len(path)<2:
                            continue
                        polygon = self._polyline(path)
                        if self.zoom<.15 and polygon.boundingRect().width()+polygon.boundingRect().height()<1.5:
                            continue
                        surface = self._lane_surface(path,start,end,casing) if start is not None and end is not None else None
                        core,edge = surface if surface else (polygon,None)
                        fill = style.fill
                        if styles[0].fill!=styles[1].fill and polygon[0]!=polygon[-1]:
                            gradient = QLinearGradient(polygon[0],polygon[-1])
                            gradient.setColorAt(0.,QColor(styles[0].fill))
                            gradient.setColorAt(1.,QColor(styles[1].fill))
                            fill = QBrush(gradient)
                        strata[layer].append((ranking[style.level],core,fill,style.shell,width,casing,junction.tunnel,edge))
            for layer,items in strata.items():
                items.sort(key=lambda item:item[0])
                painter.setBrush(Qt.BrushStyle.NoBrush)
                # Every shell precedes every fill within its actual elevation
                # layer, so intersecting road ends never cut a dark seam.
                for _,polygon,fill,shell,width,casing,tunnel,edge_polygon in items:
                    self._cooperate()
                    if edge_polygon is not None:
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QColor('#C6D0D7' if tunnel else shell))
                        painter.drawPolygon(edge_polygon,Qt.FillRule.WindingFill)
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        continue
                    # Bridge/tunnel ends are open transitions in a road, not
                    # standalone rounded symbols. Keep only restrained sides;
                    # the bridge's elevation order supplies the crossing cue.
                    cap = Qt.PenCapStyle.RoundCap if layer==1 else Qt.PenCapStyle.FlatCap
                    edge = min(casing,1.2) if layer!=1 else casing
                    pen = QPen(QColor('#C6D0D7' if tunnel else shell),width+edge,
                               Qt.PenStyle.SolidLine,cap,Qt.PenJoinStyle.RoundJoin)
                    if tunnel:
                        # Dash the exposed margins, not the road body. The
                        # pattern stays six/four pixels at every road width.
                        pen.setDashPattern([6/(width+edge),4/(width+edge)])
                    painter.setPen(pen)
                    painter.drawPolyline(polygon)
                for _,polygon,fill,shell,width,casing,tunnel,edge_polygon in items:
                    self._cooperate()
                    brush = (QBrush(QColor('#E3E9ED')) if tunnel else
                             fill if isinstance(fill,QBrush) else QBrush(QColor(fill)))
                    if edge_polygon is not None:
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(brush)
                        painter.drawPolygon(polygon,Qt.FillRule.WindingFill)
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        continue
                    cap = Qt.PenCapStyle.RoundCap if layer==1 else Qt.PenCapStyle.FlatCap
                    painter.setPen(QPen(brush,width,
                                        Qt.PenStyle.SolidLine,cap,Qt.PenJoinStyle.RoundJoin))
                    painter.drawPolyline(polygon)

    def _draw_base(self,painter):
        key=(id(self.snapshot.roads),id(self.snapshot.buildings),id(self.snapshot.junctions),
             self.options['roads'],self.options['buildings'],
             tuple(sorted(self.options['road_levels'] or ())),
             self.options['road_levels'] is None,
             tuple(sorted(self.options['building_classes'] or ())),self.options['building_classes'] is None,
             tuple(sorted(self.options['building_uses'] or ())),self.options['building_uses'] is None,
             id(self.options['building_colors']),self.zoom,self.width(),self.height(),self.ratio if isinstance(self,_FrameSurface) else self.devicePixelRatioF())
        cached=self._base_cache
        margin=192
        if cached is not None:
            old_key,center,image,owners=cached
            dx=(center[0]-self.center[0])*self.zoom
            dy=(self.center[1]-center[1])*self.zoom
        if cached is None or old_key!=key or abs(dx)>margin or abs(dy)>margin:
            surface=_FrameSurface(self)
            surface._size=QSize(self.width()+2*margin,self.height()+2*margin)
            image=QImage(round(surface.width()*surface.ratio),round(surface.height()*surface.ratio),QImage.Format.Format_ARGB32_Premultiplied)
            image.setDevicePixelRatio(surface.ratio)
            base_painter=QPainter(image)
            try:surface._paint_base(base_painter)
            finally:base_painter.end()
            # Keep identity-keyed inputs alive until the cached image is replaced.
            self._base_cache=(key,self.center,image,(self.snapshot,self.options['building_colors']))
            self._world_polygons.update(surface._world_polygons)
            self._continuous_cache.update(surface._continuous_cache)
            dx=dy=0
        painter.drawImage(QPointF(dx-margin,dy-margin),image)

    def _paint(self,painter,overlays=True):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(),QColor(MAP_BACKGROUND))
        painter.setFont(self.font())
        occupied = [QRectF(10,self.height()-55,180,45),QRectF(self.width()-45,10,35,65)]
        occupied.extend(rect.adjusted(-3,-3,3,3) for rect,_,_ in self._legend_layout(painter))
        self._draw_base(painter)
        modes = self.options['layer_modes']
        from semantic_colors import canonical_key
        visible_routes = [r for r in self._visible('routes')
                          if modes is None or canonical_key('mode',r.mode) in modes]
        routes = visible_routes if self.options['routes'] else []
        # Offset only exact shared geometry, stable under route visibility/order changes.
        shared = {}
        route_colors = {r.id:self._route_color(r) for r in routes}
        for route in routes:
            for paths,dashed in self._route_path_groups(route):
                for path in paths:
                    shared.setdefault(self._path_key(path),set()).add((route_colors[route.id].name(),dashed))
        drawn_strokes = set()
        number_count = 0
        number_limit = max(3,int(self.width()*self.height()/(48000 if self.zoom<.15 else 20000)))
        default_width = 1.8 if self.zoom<.15 else 2.3 if self.zoom<.4 else 2.8
        decorations = []
        viewport = self._viewport_bounds()
        if self.options['deadhead']:
            for route in routes:
                muted = QColor(route_colors[route.id])
                muted.setAlpha(95)
                for path in self._continuous_paths(route.depot_paths):
                    if self._path_visible(path,viewport):
                        self._draw_path(painter,path,QPen(muted,self._route_width(route,2),Qt.PenStyle.DashLine))
        for route in routes:
            color = route_colors[route.id]
            line_width = self._route_width(route,default_width)
            drawings = []
            for paths,dashed in self._route_path_groups(route):
                batches = []
                for path in paths:
                    if len(path)<2 or not self._path_visible(path,viewport):
                        batches.append((None,[]))
                        continue
                    colors = sorted(shared[self._path_key(path)])
                    offset = max(-2.,min(2.,(colors.index((color.name(),dashed))-(len(colors)-1)/2)*(1.4 if self.zoom<.15 else 2.2)))
                    if tuple(path) > tuple(reversed(path)):
                        offset *= -1
                    # Labels retain source-curve identity and stable placement.
                    drawings.append(((self._path_key(path),color.name(),abs(offset),dashed),
                                     path,offset))
                    if batches and batches[-1][0]==offset:
                        batches[-1][1].append(path)
                    else:
                        batches.append((offset,[path]))
                for offset,paths in batches:
                    for path in self._continuous_paths(paths):
                        key = (self._path_key(path),color.name(),abs(offset),dashed,line_width)
                        polygon = self._polyline(path,offset)
                        if key not in drawn_strokes:
                            drawn_strokes.add(key)
                            pen = QPen(color,line_width,Qt.PenStyle.SolidLine,
                                       Qt.PenCapStyle.FlatCap if dashed else Qt.PenCapStyle.RoundCap,
                                       Qt.PenJoinStyle.RoundJoin)
                            if dashed:
                                pen.setDashPattern([8/line_width,5/line_width])
                            painter.setPen(pen)
                            painter.setBrush(Qt.BrushStyle.NoBrush)
                            painter.drawPolyline(polygon)
            decorations.append((route,color,drawings))
        # Paint every line body in query priority order before decorations;
        # an earlier route's text halo cannot interrupt a later body.
        for route,color,drawings in decorations:
            number_placed = False
            if not self.options['line_numbers'] or number_count>=number_limit:
                continue
            label=self.route_label(route)
            for key,path,offset in drawings:
                if number_placed:
                    break
                polygon=self._polyline(path,offset)
                if polygon:
                    for fraction in (.5,.3,.7,.15,.85):
                        index = fraction*(len(polygon)-1)
                        lower = int(index)
                        point = polygon[lower]+(polygon[min(lower+1,len(polygon)-1)]-polygon[lower])*(index-lower)
                        if self._label(painter,point,label,occupied,color.name()):
                            number_placed = True
                            number_count += 1
                            break
        stop_ids = {sid for route in routes
                    for sid in visible_route_stop_ids(route,self.options['direction'])}
        stop_cells = set()
        for stop in self._visible('stops'):
            if stop.id not in stop_ids:
                continue
            point = self.world_to_screen(stop.position)
            if self.options['stops']:
                cell = (int(point.x()/6),int(point.y()/6))
                if self.zoom>=.15 or cell not in stop_cells:
                    stop_cells.add(cell)
                    painter.setPen(QPen(QColor(tokens.TEXT_SECONDARY),.8 if self.zoom<.15 else 1.2))
                    painter.setBrush(QColor(tokens.CARD_BG))
                    radius = 1.2 if self.zoom<.15 else max(2.,min(3.5,self.zoom*12))
                    painter.drawEllipse(point,radius,radius)
            if self.options['stops'] and self.options['stop_names'] and self.zoom>=.15:
                self._label(painter,point,stop.name,occupied)
        if self._highlight and self._highlight[0] != 'route':
            kind,identity = self._highlight
            index = self._indexes.get(kind+'s')
            if index:
                for item,box in index.entries:
                    if item.id == identity:
                        a = self.world_to_screen((box[0],box[1]))
                        b = self.world_to_screen((box[2],box[3]))
                        painter.setPen(QPen(QColor(tokens.ACCENT),2))
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawRoundedRect(QRectF(a,b).normalized().adjusted(-7,-7,7,7),5,5)
                        break
        if overlays:
            self._draw_scale(painter)
            self._draw_legend(painter)


    def _legend_layout(self,painter):
        """Caller supplies actual identities; reserve two compact caption rows."""
        if isinstance(self.options['legend_items'],MetricLegend):
            layout=self._metric_legend_layout(painter)
            return [(layout['bounds'],'',None)]
        available = self.width()-210
        if available<40:
            return []
        items = []
        x,row = 190.,0
        metrics = painter.fontMetrics()
        for label,color in self.options['legend_items']:
            label = str(label).strip()
            if not label:
                continue
            text = metrics.elidedText(label,Qt.TextElideMode.ElideRight,max(1,int(available-34)))
            width = metrics.horizontalAdvance(text)+34
            if x+width>self.width()-20:
                row += 1
                x = 190.
            if row>=2:
                break
            rect = QRectF(x,self.height()-52+row*22,width,20)
            items.append((rect,text,color))
            x += width+8
        return items

    def _metric_legend_layout(self,painter):
        legend=self.options['legend_items']
        painter.setFont(ui_font(tokens.FONT_SIZE_CAPTION))
        metrics=painter.fontMetrics()
        left,width=18.,max(1.,self.width()-72.)
        count=len(legend.labels)
        label_width=max(metrics.horizontalAdvance(label) for label in legend.labels)+4
        stagger=label_width>width/count
        top=self.height()-(140. if stagger else 118.)
        missing_width=metrics.horizontalAdvance('数据缺失')+22
        heading_rect=QRectF(left,top,width-missing_width-12,22)
        missing=QRectF(left+width-missing_width,top,missing_width,22)
        bar=QRectF(left,top+28,width,10)
        labels=[]
        for i,label in enumerate(legend.labels):
            span=max(width/count,label_width)
            x=max(left,min(left+width-span,left+(i+.5)*width/count-span/2))
            labels.append((QRectF(x,top+42+(22*(i%2) if stagger else 0),span,22),label))
        return dict(bounds=QRectF(left,top,width,86 if stagger else 64),heading=legend.heading,
                    heading_rect=heading_rect,missing=missing,bar=bar,labels=labels)

    def _draw_metric_legend(self,painter):
        legend=self.options['legend_items']
        layout=self._metric_legend_layout(painter)
        painter.fillRect(layout['bounds'].adjusted(-6,-4,6,4),QColor(tokens.CARD_BG))
        painter.setPen(QColor(tokens.TEXT_SECONDARY))
        painter.drawText(layout['heading_rect'],Qt.AlignmentFlag.AlignVCenter,layout['heading'])
        missing=layout['missing']
        painter.fillRect(QRectF(missing.left(),missing.center().y()-4,12,8),QColor(legend.missing_colour))
        painter.drawText(missing.adjusted(18,0,0,0),Qt.AlignmentFlag.AlignVCenter,'数据缺失')
        bar=layout['bar']
        gradient=QLinearGradient(bar.topLeft(),bar.topRight())
        for position,color in legend.gradient_stops:gradient.setColorAt(position,QColor(color))
        painter.fillRect(bar,gradient)
        for rect,label in layout['labels']:
            painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,label)

    def _draw_legend(self,painter):
        painter.setFont(ui_font(tokens.FONT_SIZE_CAPTION))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if isinstance(self.options['legend_items'],MetricLegend):
            self._draw_metric_legend(painter)
            return
        for rect,label,color in self._legend_layout(painter):
            y = rect.center().y()
            painter.setPen(QPen(QColor(color),3.,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(rect.left()+3,y),QPointF(rect.left()+17,y))
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            painter.drawText(rect.adjusted(24,0,0,0),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,label)


    def _draw_scale(self,painter):
        budget = min(120,max(20,self.width()/4))
        metres = budget/self.zoom
        exponent = 10**math.floor(math.log10(metres))
        length = max(v*exponent for v in (1,2,5) if v*exponent<=metres)
        pixels = length*self.zoom
        x,y = 18.,self.height()-22.
        painter.setPen(QPen(QColor(tokens.TEXT_SECONDARY),1.4))
        painter.drawLine(QPointF(x,y-5),QPointF(x,y))
        painter.drawLine(QPointF(x,y),QPointF(x+pixels,y))
        painter.drawLine(QPointF(x+pixels,y),QPointF(x+pixels,y-5))
        text = f'{length/1000:g} km' if length>=1000 else f'{length:g} m'
        painter.drawText(QRectF(x,y-28,150,20),text)
        x = self.width()-27.
        painter.drawText(QRectF(x-8,12,20,20),Qt.AlignmentFlag.AlignCenter,'N')
        painter.setBrush(QColor(tokens.TEXT_SECONDARY))
        painter.drawPolygon(QPolygonF([QPointF(x,37),QPointF(x-5,50),QPointF(x+5,50)]))



class _FrameSurface(_MapDrawing):
    """Detached values only: the worker never reads a QWidget."""
    def __init__(self,canvas):
        self._ui_thread = canvas._ui_thread if isinstance(canvas, _FrameSurface) else threading.get_ident()
        self._cpu_budget = CooperativeCancellation()
        self._size=QSize(canvas.width(),canvas.height())
        self._font=canvas.font()
        self.ratio=canvas.ratio if isinstance(canvas,_FrameSurface) else canvas.devicePixelRatioF()
        self._base_cache=canvas._base_cache
        for name in ('snapshot','center','zoom','_indexes','_stops','_roads',
                     '_connection_boxes','_boxes','_highlight'):
            setattr(self,name,getattr(canvas,name))
        self.options=dict(canvas.options)
        for name in ('_world_polygons','_continuous_cache','_path_keys','_path_bounds'):
            setattr(self,name,dict(getattr(canvas,name)))

    def width(self):return self._size.width()
    def height(self):return self._size.height()
    def rect(self):return QRect(0,0,self.width(),self.height())
    def font(self):return self._font

    def _cooperate(self):
        if threading.get_ident() != self._ui_thread:
            self._cpu_budget()


class _FrameSignals(QObject):
    completed=Signal(object,object,object,object)
    failed=Signal(object,object,str)


class _FrameJob(QRunnable):
    def __init__(self,surface,key,view):
        super().__init__()
        self.surface,self.key,self.view=surface,key,view
        self.signals=_FrameSignals()

    def _emit(self,name,*values):
        # Application teardown can destroy the signal receiver/source while
        # an independent QImage is finishing. There is then nothing to publish.
        try:
            getattr(self.signals,name).emit(*values)
        except RuntimeError:
            if isValid(self.signals):
                raise

    def run(self):
        surface=self.surface
        image=QImage(round(surface.width()*surface.ratio),round(surface.height()*surface.ratio),QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(surface.ratio)
        painter=QPainter(image)
        try:
            surface._paint(painter,overlays=False)
        except Exception as error:
            self._emit('failed',self.key,self.view,str(error))
            return
        finally:
            painter.end()
        self._emit('completed',self.key,self.view,image,surface)


class MapCanvas(_MapDrawing, QWidget):
    """View changes emit ``(center_x, center_z, pixels_per_metre)``.

    ``set_snapshot`` fits only the first nonempty snapshot; subsequent updates
    preserve navigation. Selection and route ordering belong to the caller.
    """
    view_changed = Signal(float, float, float)
    frame_ready = Signal()
    export_availability_changed = Signal(bool)
    render_failed = Signal(str)
    buildingClicked = Signal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.snapshot = MapSnapshot()
        self.center = (0.,0.)
        self.zoom = 1.
        self._loaded = False
        self._fit_pending = False
        self._drag = None
        self._indexes = {}
        self._index_cache = {}
        self._index_state = None
        self._index_job = None
        self._indexes_ready = True
        self._index_failed_key = None
        self._index_closed = False
        self._pending_focus = None
        self._stops = {}
        self._highlight = None
        self._world_polygons = {}
        self._continuous_cache = {}
        self._path_keys = {}
        self._path_bounds = {}
        self._boxes = {}
        self._roads = {}
        self._connection_boxes = {}
        self._revision = 0
        self._frame = None
        self._frame_key = None
        self._frame_view = None
        self._frame_job = None
        self._base_cache = None
        self._async_render = False
        self._failed_frame_key = None
        self._failed_frame_view = None
        self._export_available = False
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self.update)
        self.options = dict(roads=True, buildings=True, routes=True, direction='whole',
                            stops=True, stop_names=True, line_numbers=True, deadhead=False,
                            road_levels=None, building_classes=None, building_uses=None,
                            layer_modes=None, route_colors={}, building_colors={},legend_items=(),
                            mode_widths={},distinguish_directions=False)
        self.setFont(ui_font(tokens.FONT_SIZE_CAPTION))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def set_snapshot(self, snapshot):
        previous=self.snapshot
        self.snapshot = snapshot
        if (snapshot.source_hash != previous.source_hash or snapshot.asset_signature != previous.asset_signature
                or snapshot.roads is not previous.roads or snapshot.junctions is not previous.junctions
                or not any((snapshot.roads,snapshot.buildings,snapshot.routes,snapshot.stops,snapshot.junctions))):
            self._index_cache.clear()
        self._revision += 1
        self._notify_export_availability()
        self._async_render=sum(len(getattr(snapshot,name)) for name in ('roads','buildings','routes','junctions'))>1000
        if snapshot.roads is not previous.roads:
            self._world_polygons={}
            self._continuous_cache={}
            self._path_keys={}
            self._path_bounds={}
        if _index_key(snapshot) != _index_key(previous):
            self._pending_focus = None
            self._index_failed_key = None
            if (snapshot.source_hash, snapshot.asset_signature) != (previous.source_hash, previous.asset_signature):
                self._highlight = None
            if self._index_job is not None:
                self._index_job.cancel()
        self._indexes_ready = False
        state = _prepare_indexes(snapshot, self._index_cache, self._index_state,
                                 cached_only=self._async_render)
        if state is not None:
            self._publish_indexes(state)
        else:
            self._start_index_job()
        if not self._loaded and any((snapshot.roads,snapshot.buildings,snapshot.routes,snapshot.stops)):
            self._loaded = True
            self.fit_to_map()
            self._fit_pending = not self.isVisible()
        self.update()

    def _publish_indexes(self, state):
        self._index_state = state
        self._index_cache = state.caches
        self._indexes, self._boxes = state.indexes, state.boxes
        self._stops, self._roads = state.stops, state.roads
        self._connection_boxes = state.connection_boxes
        self._indexes_ready = True

    def _start_index_job(self):
        if (self._index_closed or self._indexes_ready or self._index_job is not None
                or self._index_failed_key == _index_key(self.snapshot)):
            return
        job = _IndexJob(self.snapshot, self._index_cache, self._index_state)
        job.signals.completed.connect(self._indexes_completed)
        job.signals.failed.connect(self._indexes_failed)
        self._index_job = job
        QThreadPool.globalInstance().start(job)

    @Slot(object, object)
    def _indexes_completed(self, key, state):
        self._index_job = None
        if self._index_closed:
            return
        if state is not None and key == _index_key(self.snapshot):
            self._publish_indexes(state)
            pending, self._pending_focus = self._pending_focus, None
            if pending is not None and pending[0] == key:
                self.focus_result(pending[1])
            self.prepare_frame()
            self.update()
        else:
            self._start_index_job()

    @Slot(object, str)
    def _indexes_failed(self, key, message):
        self._index_job = None
        if self._index_closed:
            return
        if key == _index_key(self.snapshot):
            self._index_failed_key = key
            self._notify_export_availability()
            self.render_failed.emit(message)
        else:
            self._start_index_job()

    def closeEvent(self, event):
        self._index_closed = True
        self._notify_export_availability()
        if self._index_job is not None:
            self._index_job.cancel()
        super().closeEvent(event)

    def showEvent(self, event):
        self._index_closed = False
        self._start_index_job()
        super().showEvent(event)
        self._notify_export_availability()

    def set_options(self, **options):
        unknown = set(options) - self.options.keys()
        if unknown:
            raise TypeError('Unknown map options: ' + ', '.join(sorted(unknown)))
        if 'direction' in options and options['direction'] not in ('whole','up','down'):
            raise ValueError('direction must be whole, up or down')
        self.options.update(options)
        self._revision += 1
        self._notify_export_availability()
        self.update()

    def _changed(self,interactive=False):
        self._fit_pending = False
        self._notify_export_availability()
        if interactive:
            self._render_timer.start(100)
        else:
            self._render_timer.stop()
        self.view_changed.emit(*self.center,self.zoom)
        self.update()

    def _fit_bounds(self, bounds):
        x,z,xx,zz = bounds
        self.center = ((x+xx)/2,(z+zz)/2)
        self.zoom = min(max(1,self.width()-80)/max(1,xx-x),
                        max(1,self.height()-80)/max(1,zz-z))
        self.zoom = max(.0001,min(100.,self.zoom))
        self._changed()

    def fit_to_map(self):
        self._fit_bounds(self.snapshot.bounds)

    reset_view = fit_to_map



    def _zoom(self, factor, anchor=None):
        anchor = anchor or QPointF(self.width()/2,self.height()/2)
        before = self.screen_to_world(anchor)
        self.zoom = max(.0001,min(100.,self.zoom*factor))
        after = self.screen_to_world(anchor)
        self.center = (self.center[0]+before[0]-after[0],self.center[1]+before[1]-after[1])
        self._changed(interactive=True)

    def zoom_in(self):
        self._zoom(1.35)

    def zoom_out(self):
        self._zoom(1/1.35)

    def wheelEvent(self,event):
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta:
            self._zoom(2 ** (delta/480),event.position())
            event.accept()

    def mousePressEvent(self,event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = (event.position(),self.center)
            self._drag_moved = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self,event):
        if self._drag:
            origin,center = self._drag
            delta = event.position()-origin
            if delta.manhattanLength() >= QApplication.startDragDistance():
                self._drag_moved = True
            self.center = (center[0]-delta.x()/self.zoom,center[1]+delta.y()/self.zoom)
            self._changed(interactive=True)
            event.accept()

    def mouseReleaseEvent(self,event):
        if event.button() == Qt.MouseButton.LeftButton:
            clicked = self._drag is not None
            if self._drag:
                self.mouseMoveEvent(event)
                clicked = not self._drag_moved
            self._drag = None
            self._render_timer.stop()
            self.update()
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            if clicked:
                building = self.building_at(event.position())
                if building is not None:
                    self.buildingClicked.emit(building.id, event.globalPosition().toPoint())

    def building_at(self, position):
        """Hit only visible saved footprints; a bounding box is not a building."""
        if not self._indexes_ready or not self.options.get('buildings', True):
            return None
        index = self._indexes.get('buildings')
        if index is None:
            return None
        x, z = self.screen_to_world(position)
        hits = []
        for building in index.query((x, z, x, z)):
            if len(building.polygon) < 3:
                continue
            polygon = QPolygonF([QPointF(p[0], p[2]) for p in building.polygon])
            if polygon.containsPoint(QPointF(x, z), Qt.FillRule.OddEvenFill):
                hits.append(building)
        return max(hits, key=lambda b: (b.position[1], b.id), default=None)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self._fit_pending:
            self.fit_to_map()
        self._notify_export_availability()

    def search(self,text):
        if not self._indexes_ready:
            return []
        needle = str(text).strip().casefold()
        if not needle:
            return []
        results = []
        for kind,name in (('route','routes'),('stop','stops'),('building','buildings')):
            boxes = {item.id:box for item,box in self._indexes.get(name,_SpatialIndex([],self.snapshot.bounds)).entries}
            for item in getattr(self.snapshot,name):
                label = self.route_label(item) if kind == 'route' else item.name
                if needle in label.casefold() or needle == str(item.id) or (kind=='route' and needle==str(item.number)):
                    results.append(MapSearchResult(kind,item.id,label,boxes.get(item.id,self.snapshot.bounds)))
        return results

    def focus_result(self,result):
        if not self._indexes_ready:
            if any(item.id == result.id for item in getattr(self.snapshot, result.kind+'s', ())):
                self._pending_focus = (_index_key(self.snapshot), result)
                return True
            return False
        # Resolve again against the current snapshot rather than stale result bounds.
        for item,box in self._indexes.get(result.kind+'s',_SpatialIndex([],self.snapshot.bounds)).entries:
            if item.id == result.id:
                self._highlight = (result.kind,result.id)
                if result.kind == 'route':
                    self._fit_bounds(box)
                else:
                    self.center = ((box[0]+box[2])/2,(box[1]+box[3])/2)
                    self.zoom = max(self.zoom,1.5)
                    self._changed()
                return True
        return False




















    def _render_key(self):
        return (self._revision,self.width(),self.height(),self.devicePixelRatioF(),self.font().toString(),self._highlight)

    def prepare_frame(self):
        """Prewarm hidden map pages using their current layout, without blocking."""
        self._notify_export_availability()
        if not self._indexes_ready:
            self._start_index_job()
            return
        key=self._render_key()
        view = (*self.center,self.zoom)
        if key==self._failed_frame_key and view==self._failed_frame_view:
            return
        if self._frame is None or key!=self._frame_key or (view!=self._frame_view and (self._async_render or not self._render_timer.isActive())):
            if self._async_render:
                if self._frame_job is None:
                    job=_FrameJob(_FrameSurface(self),key,view)
                    job.signals.completed.connect(self._frame_completed)
                    job.signals.failed.connect(self._frame_failed)
                    self._frame_job=job
                    self._notify_export_availability()
                    QThreadPool.globalInstance().start(job)
            else:
                self._render_frame(key,view)

    def paintEvent(self,event):
        self.prepare_frame()
        painter = QPainter(self)
        key=self._render_key()
        painter.fillRect(self.rect(),QColor(MAP_BACKGROUND))
        if self._frame is not None and key==self._frame_key:
            painter.save()
            x,z,zoom = self._frame_view
            factor = self.zoom/zoom
            painter.translate(self.width()/2*(1-factor)+(x-self.center[0])*self.zoom,
                              self.height()/2*(1-factor)+(self.center[1]-z)*self.zoom)
            painter.scale(factor,factor)
            painter.drawImage(QPointF(0,0),self._frame)
            painter.restore()
        painter.setFont(self.font())
        self._draw_scale(painter)
        self._draw_legend(painter)
        painter.end()

    @Slot(object,object,object,object)
    def _frame_completed(self,key,view,frame,surface):
        self._frame_job=None
        if key==self._render_key():
            self._frame,self._frame_key,self._frame_view=frame,key,view
            self._base_cache=surface._base_cache
            for name in ('_world_polygons','_continuous_cache','_path_keys','_path_bounds'):
                setattr(self,name,getattr(surface,name))
            self._notify_export_availability()
            if view==(*self.center,self.zoom):
                self.frame_ready.emit()
        else:
            self._notify_export_availability()
        self.update()
        if not self.isVisible() and (key!=self._render_key() or view!=(*self.center,self.zoom)):
            self.prepare_frame()

    @Slot(object,object,str)
    def _frame_failed(self,key,view,message):
        self._frame_job=None
        if self._index_closed:
            return
        if key==self._render_key() and view==(*self.center,self.zoom):
            self._failed_frame_key=key
            self._failed_frame_view=view
            self._notify_export_availability()
            self.render_failed.emit(message)
        else:
            self.prepare_frame()

    def _render_frame(self,key,view):
        ratio = self.devicePixelRatioF()
        frame = QImage(round(self.width()*ratio),round(self.height()*ratio),QImage.Format.Format_ARGB32_Premultiplied)
        frame.setDevicePixelRatio(ratio)
        painter = QPainter(frame)
        self._paint(painter,overlays=False)
        painter.end()
        self._frame,self._frame_key,self._frame_view = frame,key,view
        self._notify_export_availability()
        self.frame_ready.emit()





    def can_export(self):
        """Whether a complete frame exists for the exact current viewport."""
        if (self._index_closed or not self._indexes_ready or self._frame is None
                or self._frame_job is not None
                or self._frame_view != (*self.center, self.zoom)
                or not any((self.snapshot.roads, self.snapshot.buildings,
                            self.snapshot.routes, self.snapshot.stops, self.snapshot.junctions))):
            return False
        key = self._render_key()
        return (self._frame_key == key
                and (self._failed_frame_key, self._failed_frame_view) != (key, self._frame_view)
                and self._index_failed_key != _index_key(self.snapshot))

    def _notify_export_availability(self):
        available = self.can_export()
        if available != self._export_available:
            self._export_available = available
            self.export_availability_changed.emit(available)

    def export_image(self,path):
        """Export the current viewport, with the exact same rendering/options."""
        if not self.can_export():
            return False
        image = QImage(self.size(),QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        self._paint(painter)
        painter.end()
        return image.save(str(Path(path)))
