"""Reusable world geometry and native vector replay for the map canvas.

Preparation is detached from widgets.  Only value records and Qt paint values
are retained; every viewport is painted as geometry, never a stretched image.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections import defaultdict, OrderedDict
from bisect import bisect_left
from types import MappingProxyType
import math
import os
import sys
import time
import numpy as np

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QLinearGradient, QPainter, QPainterPath,
                           QPainterPathStroker, QPen, QPolygonF)

import stats_tokens as tokens
from map_scale import (detail_fraction, route_width,
                       stop_outline, stop_radius)
from semantic_colors import canonical_key, is_non_social_building
from map_visibility import visible_route_stop_ids


_RANK = {'unknown': 0, 'local': 1, 'pedestrian': 2, 'secondary': 3,
         'arterial': 4, 'express': 5, 'track': 6}
_TILE = 512.
_PROFILE = bool(os.environ.get('CIM_MAP_VECTOR_PROFILE'))


def _zoom_key(zoom):
    # Wheel round-trips differ by a few floating point ulps. Twelve decimals
    # retain far more precision than a screen pixel at supported map scales.
    return round(zoom, 12)


class VectorMapCancelled(InterruptedError):
    """The caller invalidated an unfinished preparation."""


@dataclass(frozen=True, slots=True)
class _RoadBatch:
    layer: int
    rank: int
    level: str
    measured_width: float | None
    tunnel: bool
    path: QPainterPath
    bounds: tuple[float, float, float, float]
    road: object
    span_min: float
    span_max: float
    members: tuple


@dataclass(frozen=True, slots=True)
class _BuildingBatch:
    colour: str
    area_min: float
    area_max: float
    path: QPainterPath
    bounds: tuple[float, float, float, float]
    members: tuple


@dataclass(frozen=True, slots=True)
class _Connection:
    layer: int
    source: object
    target: object
    source_lane: int
    target_lane: int
    paths: tuple
    templates: tuple
    bounds: tuple[float, float, float, float]
    span: float
    tunnel: bool
    owner_tile: tuple[int, int]


@dataclass(frozen=True, slots=True, eq=False)
class _LaneTemplate:
    """Read-only metres, unit screen normals, and relative saved arc length."""
    screen_base: np.ndarray
    normals: np.ndarray
    fractions: np.ndarray


@dataclass(frozen=True, slots=True)
class _ConnectionPaint:
    rank: int
    width: float
    casing: float
    core: QPolygonF
    edge: QPolygonF | None
    fill: QBrush
    shell: str
    tunnel: bool
    tile: tuple[int, int]


@dataclass(frozen=True, slots=True)
class PreparedVectorMap:
    """A view independent, paint-only map template."""
    roads: tuple[_RoadBatch, ...]
    buildings: tuple[_BuildingBatch, ...]
    connections: tuple[_Connection, ...]
    road_tiles: dict
    building_tiles: dict
    connection_tiles: dict
    routes: tuple
    stops: tuple


def _check(cancelled):
    if cancelled is not None:
        if callable(cancelled):
            if cancelled():
                raise VectorMapCancelled()
        elif cancelled.is_set():
            raise VectorMapCancelled()


def _box(path):
    if not path:
        return None
    xs = [p[0] for p in path]
    zs = [p[2] for p in path]
    return min(xs), min(zs), max(xs), max(zs)


def _intersects(a, b):
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def _expand_bounds(box,padding):
    return box[0]-padding,box[1]-padding,box[2]+padding,box[3]+padding


def _road_world_margin(road,level):
    if road.width is None or road.width<=0 or level=='track':
        return 0.
    return road.width/2


def _tiles(box):
    return ((x, z) for x in range(math.floor(box[0]/_TILE), math.floor(box[2]/_TILE)+1)
            for z in range(math.floor(box[1]/_TILE), math.floor(box[3]/_TILE)+1))


def _owner_tile(box):
    return (math.floor((box[0]+box[2])/(2*_TILE)),
            math.floor((box[1]+box[3])/(2*_TILE)))


def _path(points, close=False):
    path = QPainterPath()
    if points:
        path.moveTo(points[0][0], points[0][2])
        for point in points[1:]:
            path.lineTo(point[0], point[2])
        if close:
            path.closeSubpath()
    return path


def _lane_template(points):
    coords = np.asarray([(point[0], point[2]) for point in points], dtype=np.float64)
    screen_base = coords * np.array((1., -1.))
    before = coords[np.maximum(np.arange(len(coords))-1, 0)]
    after = coords[np.minimum(np.arange(len(coords))+1, len(coords)-1)]
    tangent = after-before
    lengths = np.hypot(tangent[:, 0], tangent[:, 1])
    normals = np.zeros_like(coords)
    np.divide(tangent[:, 1], lengths, out=normals[:, 0], where=lengths > 0)
    np.divide(tangent[:, 0], lengths, out=normals[:, 1], where=lengths > 0)
    arcs = np.r_[0., np.cumsum(np.hypot(np.diff(coords[:, 0]), np.diff(coords[:, 1])))]
    fractions = arcs/arcs[-1] if arcs[-1] else np.zeros(len(coords))
    for array in (screen_base, normals, fractions):
        array.setflags(write=False)
    return _LaneTemplate(screen_base, normals, fractions)


def _bulk_lane_templates(paths):
    """Calculate all immutable saved-curve bases in a few NumPy operations."""
    if not paths:
        return ()
    sizes = np.fromiter((len(path) for path in paths), dtype=np.int64, count=len(paths))
    ends = np.cumsum(sizes)
    starts = ends-sizes
    coords = np.asarray([(point[0], point[2]) for path in paths for point in path],
                        dtype=np.float64)
    index = np.arange(len(coords))
    first = np.repeat(starts, sizes)
    last = np.repeat(ends-1, sizes)
    before = coords[np.maximum(index-1, first)]
    after = coords[np.minimum(index+1, last)]
    tangent = after-before
    lengths = np.hypot(tangent[:, 0], tangent[:, 1])
    normals = np.zeros_like(coords)
    np.divide(tangent[:, 1], lengths, out=normals[:, 0], where=lengths > 0)
    np.divide(tangent[:, 0], lengths, out=normals[:, 1], where=lengths > 0)
    step = np.zeros(len(coords), dtype=np.float64)
    step[1:] = np.hypot(np.diff(coords[:, 0]), np.diff(coords[:, 1]))
    step[starts] = 0.
    cumulative = np.cumsum(step)
    arcs = cumulative-cumulative[first]
    totals = arcs[last]
    fractions = np.zeros(len(coords), dtype=np.float64)
    np.divide(arcs, totals, out=fractions, where=totals > 0)
    screen_base = coords*np.array((1., -1.))
    for array in (screen_base, normals, fractions):
        array.setflags(write=False)
    return tuple(_LaneTemplate(screen_base[start:end], normals[start:end],
                               fractions[start:end])
                 for start, end in zip(starts, ends))


def _qpolygon(points):
    return QPolygonF([QPointF(float(x), float(y)) for x, y in points])


def _lane_polygons(template, zoom, start, end, casing):
    base = template.screen_base*zoom
    if start is None or end is None or not template.fractions[-1]:
        return _qpolygon(base), None
    t = template.fractions
    low = start[0]*(1-t)+end[0]*t
    high = start[1]*(1-t)+end[1]*t
    normal = template.normals
    left = base+normal*low[:, None]
    right = base+normal*high[:, None]
    outer_left = base+normal*(low-casing/2)[:, None]
    outer_right = base+normal*(high+casing/2)[:, None]
    return (_qpolygon(np.concatenate((left, right[::-1]))),
            _qpolygon(np.concatenate((outer_left, outer_right[::-1]))))


def _freeze_tiles(items):
    buckets = defaultdict(list)
    for index, item in enumerate(items):
        for tile in _tiles(item.bounds):
            buckets[tile].append(index)
    return {tile: tuple(indices) for tile, indices in buckets.items()}


def _freeze_connection_tiles(items):
    buckets = defaultdict(list)
    for index, item in enumerate(items):
        for tile in _tiles(item.bounds):
            buckets[tile].append((item.span, index))
    result = {}
    for tile, entries in buckets.items():
        entries.sort()
        result[tile] = (tuple(span for span, _ in entries),
                        tuple(index for _, index in entries))
    return result


def _union_box(a, b):
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def _batch_roads(items, cancelled=None):
    """Group same-style curves per spatial tile before any viewport exists."""
    groups = {}
    for item in items:
        _check(cancelled)
        span = item.span_min
        key = (_owner_tile(item.bounds), item.layer, item.rank, item.level,
               item.measured_width, item.tunnel)
        group = groups.get(key)
        if group is None:
            groups[key] = [QPainterPath(item.path), item.bounds, item.road,
                           span, span, [(span, item.path)]]
        else:
            group[0].addPath(item.path)
            group[1] = _union_box(group[1], item.bounds)
            group[3] = min(group[3], span)
            group[4] = max(group[4], span)
            group[5].append((span, item.path))
    batches = []
    for key, (path, box, road, low, high, members) in groups.items():
        _, layer, rank, level, width, tunnel = key
        batches.append(_RoadBatch(layer, rank, level, width, tunnel, path, box, road,
                                  low, high, tuple(members)))
    return tuple(batches), MappingProxyType(_freeze_tiles(batches))


def _batch_buildings(items, cancelled=None):
    groups = []
    for item in items:
        _check(cancelled)
        key = (_owner_tile(item.bounds), item.colour, math.floor(math.log2(item.area_min)))
        if groups and groups[-1][0] == key and not any(_intersects(item.bounds, box)
                                                         for box in groups[-1][6]):
            group = groups[-1]
            group[1].addPath(item.path)
            group[2] = _union_box(group[2], item.bounds)
            group[3] = min(group[3], item.area_min)
            group[4] = max(group[4], item.area_max)
            group[5].append((item.area_min, item.path))
            group[6].append(item.bounds)
        else:
            path = QPainterPath(item.path)
            path.setFillRule(Qt.FillRule.WindingFill)
            groups.append([key, path, item.bounds, item.area_min, item.area_max,
                           [(item.area_min, item.path)], [item.bounds]])
    batches = tuple(_BuildingBatch(key[1], minimum, maximum, path, box, tuple(members))
                    for key, path, box, minimum, maximum, members, _ in groups)
    return batches, MappingProxyType(_freeze_tiles(batches))


def build_vector_map(surface, cancelled=None) -> PreparedVectorMap:
    """Build immutable geometry at original metre precision, regardless of fit view."""
    from map_canvas import continuous_paths
    profile = {} if _PROFILE else None
    started = time.perf_counter() if profile is not None else None
    roads = []
    levels = surface.options['road_levels']
    if surface.options['roads']:
        for road in surface.snapshot.roads:
            _check(cancelled)
            level = surface.road_level(road)
            if levels is not None and level not in levels:
                continue
            segments = []
            for i, points in enumerate(road.paths):
                if len(points) < 2:
                    segments.append((None, []))
                    continue
                bridge = bool(road.bridge_masks[i]) if i < len(road.bridge_masks) else road.bridge
                tunnel = bool(road.tunnel_masks[i]) if i < len(road.tunnel_masks) else road.tunnel
                layer = 0 if tunnel else 2 if bridge else 1
                if segments and segments[-1][0] == layer:
                    segments[-1][1].append(points)
                else:
                    segments.append((layer, [points]))
            for layer, paths in segments:
                if layer is None:
                    continue
                for points in continuous_paths(paths):
                    box = _box(points)
                    span = (box[2]-box[0])+(box[3]-box[1])
                    path = _path(points)
                    paint_box = _expand_bounds(box,_road_world_margin(road,level))
                    roads.append(_RoadBatch(layer, _RANK[level], level, road.width, layer == 0,
                                            path, paint_box, road, span, span, ((span, path),)))

    buildings = []
    if profile is not None:
        profile['prepare_roads_ms'] = 1000*(time.perf_counter()-started)
        started = time.perf_counter()
    if surface.options['buildings']:
        selected = surface.options['building_classes']
        uses = surface.options['building_uses']
        colours = surface.options['building_colors']
        for building in surface.snapshot.buildings:
            _check(cancelled)
            if not is_non_social_building(building):
                present = {c.group for c in building.combined_groups if c.count is not None and c.count > 0}
                if not present:
                    present = {'unknown'}
                if selected is not None and not present.intersection(selected):
                    continue
                if uses is not None and getattr(building, 'usage', building.category) not in uses:
                    continue
            points = building.polygon
            if len(points) < 3:
                continue
            box = _box(points)
            area = (box[2]-box[0])*(box[3]-box[1])
            if area <= 0:
                continue
            colour = colours.get(building.id, colours.get(str(building.id), '#DCE3E8'))
            path = _path(points, close=True)
            buildings.append(_BuildingBatch(colour, area, area, path, box, ((area, path),)))

    connections = []
    if profile is not None:
        profile['prepare_buildings_ms'] = 1000*(time.perf_counter()-started)
        started = time.perf_counter()
    if surface.options['roads']:
        road_by_id = {road.id: road for road in surface.snapshot.roads}
        for junction in surface.snapshot.junctions:
            _check(cancelled)
            layer = 0 if junction.tunnel else 2 if junction.bridge else 1
            owner_tile = (math.floor(junction.position[0]/_TILE),
                          math.floor(junction.position[2]/_TILE))
            for connection in junction.connections:
                source = road_by_id.get(connection.source_road_id)
                target = road_by_id.get(connection.target_road_id)
                if source is None or target is None:
                    continue
                if levels is not None and (surface.road_level(source) not in levels or
                                           surface.road_level(target) not in levels):
                    continue
                for points in continuous_paths(connection.paths):
                    if len(points) >= 2:
                        box = _box(points)
                        span = (box[2]-box[0])+(box[3]-box[1])
                        margin = max(_road_world_margin(road,surface.road_level(road))+
                                     max((abs(lane.offset) for lane in road.lanes),default=0.)
                                     for road in (source,target))
                        paint_box = _expand_bounds(box,margin)
                        connections.append(_Connection(layer, source, target,
                                                       connection.source_lane, connection.target_lane,
                                                       (points,), (),
                                                       paint_box, span,
                                                       junction.tunnel, owner_tile))
    templates = _bulk_lane_templates(tuple(connection.paths[0] for connection in connections))
    connections = [replace(connection, templates=(template,))
                   for connection, template in zip(connections, templates)]
    road_batches, road_tiles = _batch_roads(roads, cancelled)
    if profile is not None:
        profile['prepare_connections_ms'] = 1000*(time.perf_counter()-started)
        started = time.perf_counter()
    building_batches, building_tiles = _batch_buildings(buildings, cancelled)
    prepared = PreparedVectorMap(road_batches, building_batches, tuple(connections),
                             road_tiles, building_tiles, MappingProxyType(_freeze_connection_tiles(connections)),
                             tuple(surface.snapshot.routes), tuple(surface.snapshot.stops))
    if profile is not None:
        profile['prepare_batches_tiles_ms'] = 1000*(time.perf_counter()-started)
        profile['raw_roads'] = len(roads)
        profile['road_batches'] = len(road_batches)
        profile['raw_buildings'] = len(buildings)
        profile['building_batches'] = len(building_batches)
        profile['connections'] = len(connections)
        started = time.perf_counter()
    # The first fitted view is usually painted immediately after publication.
    # Warm only its visible vector junctions on this detached surface.
    from map_canvas import road_style
    _connection_paints(surface, prepared, surface._viewport_bounds(), road_style, cancelled)
    if profile is not None:
        profile['warm_connections_ms'] = 1000*(time.perf_counter()-started)
        print('CIM_MAP_VECTOR_BUILD_PROFILE '+repr(profile), file=sys.stderr, flush=True)
    _check(cancelled)
    return prepared


def _visible_items(items, buckets, box):
    seen = set()
    for tile in _query_tiles(buckets,box):
        for index in buckets.get(tile, ()):
            seen.add(index)
    for index in sorted(seen):
        item = items[index]
        if _intersects(item.bounds, box):
            yield item


def _visible_connections(prepared, box, zoom):
    # The original overview draws only saved curves spanning at least 1.5 px.
    # Sorted tile spans avoid even visiting tiny curves at city-wide scales.
    minimum = 1.5/zoom if zoom < .15 else 0.
    seen = set()
    for tile in _query_tiles(prepared.connection_tiles,box):
        spans, indices = prepared.connection_tiles.get(tile, ((), ()))
        seen.update(indices[bisect_left(spans, minimum):])
    for index in sorted(seen):
        item = prepared.connections[index]
        if _intersects(item.bounds, box):
            yield item


def _query_tiles(buckets,box):
    """Bound far-overview work by stored tiles rather than empty world area."""
    left,bottom,right,top = (math.floor(value/_TILE) for value in box)
    cells = (right-left+1)*(top-bottom+1)
    if cells > max(64,2*len(buckets)):
        return (tile for tile in buckets if left<=tile[0]<=right and bottom<=tile[1]<=top)
    return _tiles(box)


def _cosmetic_pen(brush, width, cap=Qt.PenCapStyle.RoundCap, dashed=False):
    pen = QPen(brush, width, Qt.PenStyle.SolidLine, cap, Qt.PenJoinStyle.RoundJoin)
    pen.setCosmetic(True)
    if dashed:
        pen.setDashPattern([6/width, 4/width])
    return pen


def _paint_buildings(painter, surface, prepared, viewport):
    painter.save()
    painter.setWorldTransform(surface._transform(), False)
    pen = _cosmetic_pen(QColor('#C4CDD3'), .45 if surface.zoom < .15 else .7)
    for item in _visible_items(prepared.buildings, prepared.building_tiles, viewport):
        scale = surface.zoom*surface.zoom
        if item.area_max*scale < .8:
            continue
        painter.setPen(pen)
        painter.setBrush(QColor(item.colour))
        if item.area_min*scale >= .8:
            painter.drawPath(item.path)
        else:
            for area, path in item.members:
                if area*scale >= .8:
                    painter.drawPath(path)
    painter.restore()


def _connection_cache(surface, prepared):
    if getattr(surface, '_vector_connection_cache_owner', None) is not prepared:
        surface._vector_connection_cache_owner = prepared
        surface._vector_connection_cache = OrderedDict()
    cache = surface._vector_connection_cache
    zoom = _zoom_key(surface.zoom)
    values = cache.get(zoom)
    if values is None:
        values = {}
        cache[zoom] = values
        if len(cache) > 2:
            cache.popitem(last=False)
    else:
        cache.move_to_end(zoom)
    return values


def _connection_paints(surface, prepared, viewport, road_style, cancelled=None):
    result = {0: [], 1: [], 2: []}
    cache = _connection_cache(surface, prepared)
    styles_by_road = cache.setdefault('__road_styles__', {})
    margins_by_lane = cache.setdefault('__lane_margins__', {})
    overview = surface.zoom < .15
    for connection in _visible_connections(prepared, viewport, surface.zoom):
        _check(cancelled)
        identity = id(connection)
        paints = cache.get(identity)
        if paints is not None:
            result[connection.layer].extend(paints)
            continue
        styles = []
        margins = []
        for road, lane in ((connection.source, connection.source_lane),
                           (connection.target, connection.target_lane)):
            road_identity = id(road)
            road_styling = styles_by_road.get(road_identity)
            if road_styling is None:
                road_styling = road_style(road, surface.zoom)
                styles_by_road[road_identity] = road_styling
            styles.append(road_styling)
            if not overview:
                lane_identity = (road_identity, lane)
                if lane_identity not in margins_by_lane:
                    margins_by_lane[lane_identity] = surface._lane_margins(road, lane, road_styling)
                margins.append(margins_by_lane[lane_identity])
        style = min(styles, key=lambda s: s.width)
        widths = [s.width/max(2, (road.lanes_a or 0)+(road.lanes_b or 0))
                  for road, s in zip((connection.source, connection.target), styles)]
        width = max(.5, min(widths))
        casing = .2 if surface.zoom < .15 else .45
        start, end = margins if not overview else (None, None)
        paints = []
        for template in connection.templates:
            # At overview scale lane boundaries are subpixel; the saved turn
            # curve remains a vector stroke. Detailed scales restore the
            # authentic tapered lane polygons from the same world template.
            core, edge = ((_qpolygon(template.screen_base*surface.zoom), None)
                          if overview else
                          _lane_polygons(template, surface.zoom, start, end, casing))
            fill = QBrush(QColor(style.fill))
            endpoints = template.screen_base[[0, -1]]*surface.zoom
            if styles[0].fill != styles[1].fill and not np.array_equal(endpoints[0], endpoints[1]):
                gradient = QLinearGradient(QPointF(*endpoints[0]), QPointF(*endpoints[1]))
                gradient.setColorAt(0., QColor(styles[0].fill))
                gradient.setColorAt(1., QColor(styles[1].fill))
                fill = QBrush(gradient)
            paints.append(_ConnectionPaint(_RANK[style.level], width, casing, core, edge,
                                           fill, style.shell, connection.tunnel,
                                           connection.owner_tile))
        cache[identity] = tuple(paints)
        result[connection.layer].extend(paints)
    for layer in result:
        result[layer].sort(key=lambda entry: entry.rank)
    return result


def _road_pen(road, zoom, road_style, shell=False):
    style = road_style(road.road, zoom)
    width = style.width
    cap = Qt.PenCapStyle.RoundCap if road.layer == 1 else Qt.PenCapStyle.FlatCap
    if shell:
        edge = min(style.casing, 1.2) if road.layer != 1 else style.casing
        width += edge
        colour = '#C6D0D7' if road.tunnel else style.shell
        return _cosmetic_pen(QColor(colour), width, cap, road.tunnel)
    return _cosmetic_pen(QColor('#E3E9ED' if road.tunnel else style.fill), width, cap)


def _connection_runs(items, shell, layer):
    """Batch adjacent same-style saved curves while retaining their draw order."""
    runs = []
    run_count = 0
    cap = Qt.PenCapStyle.RoundCap if layer == 1 else Qt.PenCapStyle.FlatCap
    for item in items:
        if item.edge is not None:
            polygon = item.edge if shell else item.core
            brush = (QBrush(QColor('#C6D0D7' if item.tunnel else item.shell)) if shell else
                     QBrush(QColor('#E3E9ED')) if item.tunnel else item.fill)
            gradient = brush.gradient() is not None
            key = None if gradient else ('area', brush.color().name())
            pen = None
        else:
            polygon = item.core
            width = item.width
            if shell:
                width += min(item.casing, 1.2) if layer != 1 else item.casing
                brush = QBrush(QColor('#C6D0D7' if item.tunnel else item.shell))
            else:
                brush = QBrush(QColor('#E3E9ED')) if item.tunnel else item.fill
            gradient = brush.gradient() is not None
            key = None if gradient else ('line', brush.color().name(), width, cap, shell and item.tunnel)
            pen = _cosmetic_pen(brush, width, cap, shell and item.tunnel)
        if key is not None and runs and runs[-1][0] == key and run_count < 96:
            runs[-1][1].addPolygon(polygon)
            run_count += 1
        else:
            path = QPainterPath()
            if item.edge is not None:
                path.setFillRule(Qt.FillRule.WindingFill)
            path.addPolygon(polygon)
            runs.append((key, path, pen, brush))
            run_count = 1
    return runs


def _cached_connection_runs(surface, prepared, items, shell, layer, rank):
    # Exact same zoom and selected saved curves recur during small pans and
    # expose the same screen-space lane surfaces at a translated origin.
    zoom_cache = _connection_cache(surface, prepared)
    runs = zoom_cache.setdefault('__runs__', OrderedDict())
    key = (layer, rank, shell, items[0].tile, tuple(id(item) for item in items))
    value = runs.get(key)
    if value is None:
        value = tuple(_connection_runs(items, shell, layer))
        runs[key] = value
        if len(runs) > 2048:
            runs.popitem(last=False)
    else:
        runs.move_to_end(key)
    return value


def _route_polygon(surface, prepared, path, offset):
    """Cache precise screen-width route offsets without tying them to a pan."""
    if getattr(surface, '_vector_route_polygon_owner', None) is not prepared:
        surface._vector_route_polygon_owner = prepared
        surface._vector_route_polygons = OrderedDict()
    zooms = surface._vector_route_polygons
    zoom_key = _zoom_key(surface.zoom)
    cache = zooms.get(zoom_key)
    if cache is None:
        cache = OrderedDict()
        zooms[zoom_key] = cache
        if len(zooms) > 2:
            zooms.popitem(last=False)
    else:
        zooms.move_to_end(zoom_key)
    key = (id(path), offset)
    record = cache.get(key)
    if record is not None and record[0] is path:
        cache.move_to_end(key)
        return record[1]
    polygon = surface._polyline(path, offset)
    transform = surface._transform()
    origin = QPointF(transform.m31(), transform.m32())
    local = QPolygonF([point-origin for point in polygon])
    cache[key] = (path, local)
    if len(cache) > 8192:
        cache.popitem(last=False)
    return local


def _route_outline(surface, prepared, path, offset, width, dashed):
    if getattr(surface, '_vector_route_outline_owner', None) is not prepared:
        surface._vector_route_outline_owner = prepared
        surface._vector_route_outlines = OrderedDict()
    zooms = surface._vector_route_outlines
    zoom_key = _zoom_key(surface.zoom)
    cache = zooms.get(zoom_key)
    if cache is None:
        cache = OrderedDict()
        zooms[zoom_key] = cache
        if len(zooms) > 2:
            zooms.popitem(last=False)
    else:
        zooms.move_to_end(zoom_key)
    key = (id(path), offset, width, dashed)
    record = cache.get(key)
    if record is not None and record[0] is path:
        cache.move_to_end(key)
        return record[1]
    polygon = _route_polygon(surface, prepared, path, offset)
    line = QPainterPath()
    if polygon:
        line.moveTo(polygon[0])
        for index in range(1, len(polygon)):
            line.lineTo(polygon[index])
    stroker = QPainterPathStroker()
    stroker.setWidth(width)
    stroker.setCapStyle(Qt.PenCapStyle.FlatCap if dashed else Qt.PenCapStyle.RoundCap)
    stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    if dashed:
        stroker.setDashPattern([8/width, 5/width])
    outline = stroker.createStroke(line)
    cache[key] = (path, outline)
    if len(cache) > 8192:
        cache.popitem(last=False)
    return outline


def _route_plan(surface, prepared, routes, colors):
    """Keep exact saved route geometry; overlapping lines have no lane shift."""
    if getattr(surface, '_vector_route_plan_owner', None) is not prepared:
        surface._vector_route_plan_owner = prepared
        surface._vector_route_plans = OrderedDict()
    cache = surface._vector_route_plans
    key = (tuple(route.id for route in routes), surface.options['direction'],
           surface.options['distinguish_directions'])
    value = cache.get(key)
    if value is None:
        groups = {route.id: surface._route_path_groups(route) for route in routes}
        offsets = {(route.id, id(path), dashed): 0.
                   for route in routes for paths, dashed in groups[route.id] for path in paths}
        value = groups, offsets
        cache[key] = value
        if len(cache) > 4:
            cache.popitem(last=False)
    else:
        cache.move_to_end(key)
    return value


def _paint_roads(painter, surface, prepared, viewport, profile=None):
    from map_canvas import road_style
    started = time.perf_counter() if profile is not None else None
    roads = {layer: defaultdict(list) for layer in (0, 1, 2)}
    for road in _visible_items(prepared.roads, prepared.road_tiles, viewport):
        path = road.path
        if surface.zoom < .15 and road.level in ('local', 'pedestrian', 'unknown'):
            if road.span_max*surface.zoom < 1.5:
                continue
            if road.span_min*surface.zoom < 1.5:
                path = QPainterPath()
                for span, member in road.members:
                    if span*surface.zoom >= 1.5:
                        path.addPath(member)
        roads[road.layer][road.rank].append((road, path))
    if profile is not None:
        profile['road_select_ms'] = 1000*(time.perf_counter()-started)
        started = time.perf_counter()
    connections = _connection_paints(surface, prepared, viewport, road_style)
    if profile is not None:
        profile['connection_select_material_ms'] = 1000*(time.perf_counter()-started)
        profile['roads_visible'] = sum(len(rank) for layer in roads.values() for rank in layer.values())
        profile['connections_visible'] = sum(len(layer) for layer in connections.values())
        started = time.perf_counter()
    transform = surface._transform()
    screen_origin = (transform.m31(), transform.m32())
    run_ms = 0.
    road_draw_ms = 0.
    connection_draw_ms = 0.
    for layer in (0, 1, 2):
        for shell in (True, False):
            for rank in range(len(_RANK)):
                draw_started = time.perf_counter() if profile is not None else None
                painter.save()
                painter.setWorldTransform(surface._transform(), False)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for road, path in roads[layer].get(rank, ()):
                    painter.setPen(_road_pen(road, surface.zoom, road_style, shell))
                    painter.drawPath(path)
                painter.restore()
                if profile is not None:
                    road_draw_ms += 1000*(time.perf_counter()-draw_started)
                materials = [item for item in connections[layer] if item.rank == rank]
                if materials:
                    draw_started = time.perf_counter() if profile is not None else None
                    painter.save()
                    painter.translate(*screen_origin)
                    by_tile = defaultdict(list)
                    for item in materials:
                        by_tile[item.tile].append(item)
                    for tile_items in by_tile.values():
                        run_started = time.perf_counter() if profile is not None else None
                        runs = _cached_connection_runs(surface, prepared, tile_items, shell, layer, rank)
                        if profile is not None:
                            run_ms += 1000*(time.perf_counter()-run_started)
                        for _, path, pen, brush in runs:
                            if pen is None:
                                painter.setPen(Qt.PenStyle.NoPen)
                                painter.setBrush(brush)
                            else:
                                painter.setPen(pen)
                                painter.setBrush(Qt.BrushStyle.NoBrush)
                            painter.drawPath(path)
                    painter.restore()
                    if profile is not None:
                        connection_draw_ms += 1000*(time.perf_counter()-draw_started)
    if profile is not None:
        profile['road_draw_ms'] = road_draw_ms
        profile['connection_draw_ms'] = connection_draw_ms-run_ms
        profile['connection_run_compile_ms'] = run_ms


def _paint_routes_and_stops(painter, surface, prepared, profile=None):
    started = time.perf_counter() if profile is not None else None
    modes = surface.options['layer_modes']
    query_routes = [r for r in prepared.routes
                    if modes is None or canonical_key('mode', r.mode) in modes] if surface.options['routes'] else []
    colors = {r.id: surface._route_color(r) for r in query_routes}
    # A route sharing a visible saved curve also intersects this viewport.
    # Preparing all query routes therefore preserves on-screen offsets while
    # avoiding a full topology rescan whenever a route leaves the viewport.
    groups, offsets = _route_plan(surface, prepared, query_routes, colors)
    maximum_width = max((surface._route_width(r,route_width(surface.zoom)) for r in query_routes),default=0.)
    padding = max(40.,max((abs(offset) for offset in offsets.values()),default=0.)+maximum_width/2+2.)
    viewport = surface._viewport_bounds(padding)
    visible = {r.id for r in surface._visible('routes',viewport)}
    routes = [r for r in query_routes if r.id in visible]
    if profile is not None:
        profile['route_setup_ms'] = 1000*(time.perf_counter()-started)
        profile['routes_visible'] = len(routes)
        started = time.perf_counter()
    occupied = [QRectF(10, surface.height()-55, 180, 45), QRectF(surface.width()-45, 10, 35, 65)]
    occupied.extend(rect.adjusted(-3, -3, 3, 3) for rect, _, _ in surface._legend_layout(painter))
    default_width = route_width(surface.zoom)
    number_limit = max(3, int(surface.width()*surface.height()/(48000-28000*detail_fraction(surface.zoom,.25))))
    decorations = []
    transform = surface._transform()
    route_origin = QPointF(transform.m31(), transform.m32())
    painter.save()
    painter.translate(route_origin)
    if surface.options['deadhead']:
        for route in routes:
            muted = QColor(colors[route.id]); muted.setAlpha(95)
            for path in surface._continuous_paths(route.depot_paths):
                if surface._path_visible(path, viewport):
                    polygon = _route_polygon(surface, prepared, path, 0.)
                    painter.setPen(QPen(muted, surface._route_width(route, 2), Qt.PenStyle.DashLine))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPolyline(polygon)
    if profile is not None:
        profile['route_deadhead_ms'] = 1000*(time.perf_counter()-started)
        started = time.perf_counter()
    for route in routes:
        # Repeated source pieces within a route are redundant. Later routes
        # must still paint in query order, including a repeated earlier colour.
        drawn_strokes = set()
        color = colors[route.id]
        line_width = surface._route_width(route, default_width)
        drawings = []
        for paths, dashed in groups[route.id]:
            batches = []
            for path in paths:
                if len(path) < 2 or not surface._path_visible(path, viewport):
                    batches.append((None, [])); continue
                offset = offsets[(route.id, id(path), dashed)]
                drawings.append((path, offset))
                if batches and batches[-1][0] == offset:
                    batches[-1][1].append(path)
                else:
                    batches.append((offset, [path]))
            for offset, group in batches:
                for path in surface._continuous_paths(group):
                    key = (surface._path_key(path), color.name(), abs(offset), dashed, line_width)
                    if key in drawn_strokes:
                        continue
                    drawn_strokes.add(key)
                    if dashed:
                        pen = QPen(color, line_width, Qt.PenStyle.SolidLine,
                                   Qt.PenCapStyle.FlatCap, Qt.PenJoinStyle.RoundJoin)
                        pen.setDashPattern([8/line_width, 5/line_width])
                        painter.setPen(pen)
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawPolyline(_route_polygon(surface, prepared, path, offset))
                    else:
                        outline = _route_outline(surface, prepared, path, offset,
                                                 line_width, dashed)
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(color)
                        painter.drawPath(outline)
        decorations.append((route, color, drawings))
    painter.restore()
    if profile is not None:
        profile['route_strokes_ms'] = 1000*(time.perf_counter()-started)
        started = time.perf_counter()
    if surface.options['line_numbers']:
        count = 0
        for route, color, drawings in decorations:
            if count >= number_limit:
                break
            label = surface.route_label(route)
            for path, offset in drawings:
                polygon = _route_polygon(surface, prepared, path, offset)
                if not polygon:
                    continue
                for fraction in (.5, .3, .7, .15, .85):
                    index = fraction*(len(polygon)-1)
                    lower = int(index)
                    point = (polygon[lower]+(polygon[min(lower+1, len(polygon)-1)]-polygon[lower])*
                             (index-lower)+route_origin)
                    if surface._label(painter, point, label, occupied, color.name()):
                        count += 1
                        break
                else:
                    continue
                break
    if profile is not None:
        profile['route_labels_ms'] = 1000*(time.perf_counter()-started)
        started = time.perf_counter()
    stop_ids = {sid for route in routes for sid in visible_route_stop_ids(route, surface.options['direction'])}
    stop_cells = set()
    visible_stops = {s.id for s in surface._visible('stops')}
    for stop in prepared.stops:
        if stop.id not in visible_stops or stop.id not in stop_ids:
            continue
        point = surface.world_to_screen(stop.position)
        if surface.options['stops']:
            cell = (int(point.x()/6), int(point.y()/6))
            if surface.zoom >= .15 or cell not in stop_cells:
                stop_cells.add(cell)
                painter.setPen(QPen(QColor(tokens.TEXT_SECONDARY), stop_outline(surface.zoom)))
                painter.setBrush(QColor(tokens.CARD_BG))
                radius = stop_radius(surface.zoom)
                painter.drawEllipse(point, radius, radius)
        if surface.options['stops'] and surface.options['stop_names'] and surface.zoom >= .15:
            surface._label(painter, point, stop.name, occupied)
    if profile is not None:
        profile['stops_ms'] = 1000*(time.perf_counter()-started)
        started = time.perf_counter()
    if surface._highlight and surface._highlight[0] != 'route':
        kind, identity = surface._highlight
        index = surface._indexes.get(kind+'s')
        if index:
            for item, box in index.entries:
                if item.id == identity:
                    a = surface.world_to_screen((box[0], box[1]))
                    b = surface.world_to_screen((box[2], box[3]))
                    painter.setPen(QPen(QColor(tokens.ACCENT), 2))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(QRectF(a, b).normalized().adjusted(-7, -7, 7, 7), 5, 5)
                    break
    if profile is not None:
        profile['highlight_ms'] = 1000*(time.perf_counter()-started)


def paint_vector_map(painter: QPainter, surface, prepared: PreparedVectorMap, overlays: bool = True) -> None:
    """Paint vector geometry at the current centre and zoom on any QPaintDevice."""
    from map_canvas import MAP_BACKGROUND
    profile = {} if _PROFILE else None
    started = time.perf_counter() if profile is not None else None
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillRect(surface.rect(), QColor(MAP_BACKGROUND))
    painter.setFont(surface.font())
    viewport = surface._viewport_bounds()
    _paint_buildings(painter, surface, prepared, viewport)
    if profile is not None:
        profile['background_buildings_ms'] = 1000*(time.perf_counter()-started)
    _paint_roads(painter, surface, prepared, viewport, profile)
    started = time.perf_counter() if profile is not None else None
    _paint_routes_and_stops(painter, surface, prepared, profile)
    if profile is not None:
        profile['routes_stops_ms'] = 1000*(time.perf_counter()-started)
        started = time.perf_counter()
    if overlays:
        surface._draw_scale(painter)
        surface._draw_legend(painter)
    if profile is not None:
        profile['overlays_ms'] = 1000*(time.perf_counter()-started)
        print('CIM_MAP_VECTOR_PROFILE '+repr(profile), file=sys.stderr, flush=True)
