"""Compile retained map vertices; navigation changes only GPU view uniforms.

All coordinates use (saved x, -saved z). Widths, lane margins, visibility and
gradient projection remain parameters for the material shader. This module
owns no widget, painter, context or GPU resource.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import math

import numpy as np
from PySide6.QtGui import QColor

from map_vector import _check, VectorMapCancelled
from semantic_colors import canonical_key


def _load_strip():
    try:
        from map_gpu_strip import load_strip
        return load_strip()
    except (ImportError, AttributeError, OSError, RuntimeError, ValueError):
        return None

@dataclass(frozen=True, slots=True)
class GpuCommand:
    start: int
    count: int
    mode: str
    cover_start: int = 0
    cover_count: int = 0
    bounds: tuple[float, float, float, float] = (0., 0., 0., 0.)
    min_zoom: float = 0.
    max_zoom: float = math.inf
    connection_rank: int = -1
    rank_material: int = -1
    owner_tile: tuple[int, int] | None = None
    original_order: int = -1
    connection_members: tuple = ()
    shell_pass: int = -1


@dataclass(frozen=True, slots=True)
class GpuScene:
    vertices: np.ndarray
    materials: np.ndarray
    commands: tuple[GpuCommand, ...]
    indices: np.ndarray | None = None
    visibility: object | None = None


@dataclass(frozen=True, slots=True)
class GpuLayers:
    base: GpuScene
    routes: GpuScene


def _gpu_bounds(bounds):
    return bounds[0], -bounds[3], bounds[2], -bounds[1]


def _bounds(points):
    return (float(points[:, 0].min()), float(points[:, 1].min()),
            float(points[:, 0].max()), float(points[:, 1].max()))


def _union(a, b):
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def _rgba(colour):
    return QColor(colour).getRgbF()


def _road_parameters(road):
    from map_canvas import ROAD_STYLES
    from map_model import road_display_level
    from map_vector import _RANK
    level = road_display_level(road)
    fill, shell, overview, detail = ROAD_STYLES[level]
    physical = road.width if road.width and road.width > 0 and level != 'track' else 0.
    return (overview, detail, physical, _RANK[level]), fill, shell


def _lane_coefficients(road, lane_index):
    """Return each edge's (road-symbol coefficient, saved-world offset)."""
    if not road.width or road.width <= 0:
        return None
    lanes = sorted((lane for lane in road.lanes
                    if lane.type_mask & 0x1f000000 and
                    (lane.type_mask & 3 or lane.type_mask & 4 and lane.turn_directions)),
                   key=lambda lane: lane.offset)
    if len(lanes) < 2:
        return None
    index = next((i for i, lane in enumerate(lanes) if lane.index == lane_index), None)
    if index is None or not lanes[index].type_mask & 0x300:
        return None
    lane = lanes[index]
    low, high = -road.width/2, road.width/2
    sidewalks = [item.offset for item in road.lanes if item.type_mask & 0x10000]
    if sidewalks and road.sidewalk_left is not None and road.sidewalk_right is not None:
        low = min(sidewalks)-road.sidewalk_left/2
        high = max(sidewalks)+road.sidewalk_right/2
    low = (lanes[index-1].offset+lane.offset)/2 if index else low
    high = (lane.offset+lanes[index+1].offset)/2 if index+1 < len(lanes) else high
    result = ((low/road.width, -lane.offset), (high/road.width, -lane.offset))
    return result if lane.type_mask & 0x100 else tuple((-a, -b) for a, b in reversed(result))


def _saved_points(points, cancelled=None):
    values = np.empty((len(points), 2), dtype=np.float64)
    for start in range(0, len(points), 256):
        _check(cancelled)
        values[start:start+256] = [(point[0], -point[2]) for point in points[start:start+256]]
    return values


def _subpaths(path, cancelled):
    """Read saved polyline vertices without Qt flattening or simplification."""
    points = []
    for index in range(path.elementCount()):
        if index % 256 == 0:
            _check(cancelled)
        element = path.elementAt(index)
        if element.isMoveTo():
            if points:
                yield np.asarray(points, dtype=np.float64)
            points = []
        elif not element.isLineTo():
            raise ValueError('Prepared map geometry must contain saved polyline vertices')
        points.append((element.x, -element.y))
    if points:
        yield np.asarray(points, dtype=np.float64)


_QUAD = np.asarray(((-1., -1.), (1., -1.), (1., 1.),
                    (-1., -1.), (1., 1.), (-1., 1.)))
_QUAD_CORNERS = _QUAD[[0, 1, 2, 5]]
_QUAD_INDICES = np.asarray((0, 1, 2, 0, 2, 3), dtype=np.uint32)


class _Builder:
    def __init__(self, cancelled):
        self.cancelled = cancelled
        self.chunks = []
        self.index_chunks = []
        self.size = 0
        self.vertex_size = 0
        self.materials = []
        self.material_indices = {}
        self.commands = []
        self.owner_tile = None
        self.connection_member = None
        self.road_cache = {}
        self.lane_cache = {}
        self.colour_cache = {}
        self.mesh_cache = {}
        self.shell_pass = -1
        self.strip_loaded = False
        self.strip_proof = None

    def prove_strip(self, rows, material):
        _check(self.cancelled)
        if (len(rows) > 64 or not (material[2] > 0 and material[6] > 0
                                  and material[3] < 5.5 and material[7] < 5.5)):
            return False
        if not self.strip_loaded:
            self.strip_proof = _load_strip()
            self.strip_loaded = True
            _check(self.cancelled)
        if not callable(self.strip_proof):
            return False
        try:
            proved = bool(self.strip_proof(rows, material, cancelled=self.cancelled))
        except InterruptedError as error:
            raise VectorMapCancelled() from error
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            proved = False
        _check(self.cancelled)
        return proved

    def road_parameters(self, road):
        identity = id(road)
        if identity not in self.road_cache:
            self.road_cache[identity] = _road_parameters(road)
        return self.road_cache[identity]

    def lane_coefficients(self, road, lane):
        key = id(road), lane
        if key not in self.lane_cache:
            self.lane_cache[key] = _lane_coefficients(road, lane)
        return self.lane_cache[key]

    def rgba(self, colour):
        key = colour if isinstance(colour, str) else colour.rgba()
        if key not in self.colour_cache:
            self.colour_cache[key] = _rgba(colour)
        return self.colour_cache[key]

    def make_material(self, *args, **kwargs):
        return _material(*args, **kwargs, _cache=self)

    def material(self, values):
        row = np.asarray(values, dtype=np.float32)
        key = row.tobytes()
        if key not in self.material_indices:
            self.material_indices[key] = len(self.materials)
            self.materials.append(row)
        return self.material_indices[key]

    def append(self, rows):
        _check(self.cancelled)
        start = self.size
        local_indices = None
        if isinstance(rows, tuple):
            rows, local_indices = rows
        rows = np.ascontiguousarray(rows, dtype=np.float32)
        if local_indices is None:
            _, first, local_indices = np.unique(rows.view('V64').ravel(), return_index=True, return_inverse=True)
            unique = rows[first]
        else:
            unique = rows
        self.chunks.append(unique)
        self.index_chunks.append(local_indices.astype(np.uint32)+self.vertex_size)
        self.vertex_size += len(unique)
        self.size += len(local_indices)
        return start

    def triangles(self, rows, bounds, minimum=0., maximum=math.inf, rank_material=-1):
        if not len(rows[1] if isinstance(rows, tuple) else rows):
            return
        start = self.append(rows)
        count = self.size-start
        members = (self.connection_member,) if self.connection_member is not None else ()
        command = GpuCommand(start, count, 'triangles', bounds=bounds,
                             min_zoom=minimum, max_zoom=maximum, rank_material=rank_material,
                             owner_tile=self.owner_tile,
                             original_order=members[0][0] if members else -1, connection_members=members,
                             shell_pass=self.shell_pass)
        return self._record_triangle(command)

    def _record_triangle(self, command):
        if self.commands:
            previous = self.commands[-1]
            if (previous.mode == 'triangles' and previous.connection_rank == -1
                    and previous.start+previous.count == command.start
                    and previous.min_zoom == command.min_zoom and previous.max_zoom == command.max_zoom
                    and previous.owner_tile == command.owner_tile and previous.shell_pass == command.shell_pass):
                common = previous.rank_material
                if common != command.rank_material and (common < 0 or command.rank_material < 0 or
                        not np.array_equal(self.materials[common][:8], self.materials[command.rank_material][:8])):
                    common = -1
                self.commands[-1] = replace(previous, count=previous.count+command.count,
                    bounds=_union(previous.bounds, command.bounds), rank_material=common,
                    connection_members=tuple(dict.fromkeys((*previous.connection_members, *command.connection_members))))
                return command
        self.commands.append(command)
        return command

    def reference(self, command):
        _check(self.cancelled)
        members = (self.connection_member,) if self.connection_member is not None else ()
        command = replace(command, shell_pass=self.shell_pass, owner_tile=self.owner_tile,
                          original_order=members[0][0] if members else -1, connection_members=members)
        if command.mode == 'triangles':
            return self._record_triangle(command)
        self.commands.append(command)
        return command

    def winding(self, fans, material, bounds, minimum=0., maximum=math.inf):
        start = self.size
        for fan in fans:
            self.append(fan)
        count = self.size-start
        cover = np.zeros((4, 16), dtype=np.float32)
        cover[:, :2] = np.where(_QUAD_CORNERS < 0, np.asarray(bounds[:2]), np.asarray(bounds[2:]))
        cover[:, 2:4] = _QUAD_CORNERS
        cover[:, 8] = material
        cover[:, 10] = 4
        cover_start = self.append((cover, _QUAD_INDICES))
        command = GpuCommand(start, count, 'winding', cover_start, 6,
                             bounds, minimum, maximum, shell_pass=self.shell_pass)
        self.commands.append(command)
        return command

    def finish(self):
        _check(self.cancelled)
        vertices = (np.concatenate(self.chunks).astype(np.float32, copy=False)
                    if self.chunks else np.empty((0, 16), dtype=np.float32))
        materials = np.asarray(self.materials, dtype=np.float32).reshape(-1, 40)
        indices = (np.concatenate(self.index_chunks) if self.index_chunks
                   else np.empty(0, dtype=np.uint32))
        for values in (vertices, materials, indices):
            values.setflags(write=False)
        scene = GpuScene(vertices, materials, tuple(self.commands), indices)
        from map_gpu_visibility import cull_commands, SceneVisibility
        commands=cull_commands(scene)
        visibility=SceneVisibility.build(commands,self.cancelled)
        return replace(scene,commands=commands,visibility=visibility)


def _material(mode, source=None, target=None, *, fill=None, shell=None, gradient=None,
              width=0., span=0., area=0., layer=1, tunnel=False, dash=(0., 0.),
              minimum=0., maximum=math.inf, _cache=None):
    values = np.zeros(40, dtype=np.float32)
    parameters_for = _cache.road_parameters if _cache is not None else _road_parameters
    colour_for = _cache.rgba if _cache is not None else _rgba
    if source is not None:
        parameters, source_fill, source_shell = parameters_for(source)
        values[:4] = parameters
        target = target or source
        parameters, target_fill, target_shell = parameters_for(target)
        values[4:8] = parameters
        values[34:36] = [max(2, (road.lanes_a or 0)+(road.lanes_b or 0))
                         for road in (source, target)]
    else:
        source_fill = target_fill = fill or '#FFFFFF'
        source_shell = target_shell = shell or source_fill
    if tunnel:
        source_fill = target_fill = '#E3E9ED'
        source_shell = target_shell = '#C6D0D7'
    values[8:12], values[12:16] = colour_for(source_fill), colour_for(target_fill)
    values[16:20], values[20:24] = colour_for(source_shell), colour_for(target_shell)
    if gradient is not None and source_fill != target_fill:
        values[24:28] = (*gradient[0], *(gradient[-1]-gradient[0]))
    values[28:32] = mode, width, minimum, maximum
    values[32:34] = span, area
    values[36:40] = tunnel, layer, *dash
    return values


_native_stroke = None
_native_stroke_checked = False


def _stroke(points, material, *, round_caps=True, dashed=False, cancelled=None):
    global _native_stroke, _native_stroke_checked
    if not _native_stroke_checked:
        from map_gpu_stroke import load_stroke
        _native_stroke=load_stroke();_native_stroke_checked=True
    if _native_stroke is not None:
        result=_native_stroke(points,material,round_caps=round_caps,dashed=dashed,cancelled=cancelled)
        if result is not None:return result
    return _python_stroke(points,material,round_caps=round_caps,dashed=dashed,cancelled=cancelled)


def _python_stroke(points, material, *, round_caps=True, dashed=False, cancelled=None):
    """Retain independent segment quads and analytic disks, including arc phase."""
    _check(cancelled)
    if len(points) < 2:
        return np.empty((0, 16), dtype=np.float32)
    # Zero-length edges carry no shape or phase. Repeated saved coordinates are
    # still represented by the adjacent real segments, without an invalid unit normal.
    lengths = np.hypot(*np.diff(points, axis=0).T)
    active = np.flatnonzero(lengths > 0)
    if not len(active):
        return np.empty((0, 16), dtype=np.float32)
    arcs = np.r_[0., np.cumsum(lengths)]
    tangent = np.diff(points, axis=0)[active]/lengths[active, None]
    normals = np.column_stack((-tangent[:, 1], tangent[:, 0]))
    selected = np.column_stack((active, active, active+1, active+1)).ravel()
    rows = np.zeros((len(selected), 16), dtype=np.float32)
    rows[:, :2] = points[selected]
    rows[:, 2:4] = np.repeat(normals, 4, axis=0)
    rows[:, 4] = np.tile((-.5, .5, .5, -.5), len(active))
    rows[:, 8] = material
    rows[:, 9] = arcs[selected]
    rows[:, 10] = 1
    chunks = [rows]
    # Remove repeated vertices only for topology; preserve segment endpoints,
    # accumulated arc lengths and every nonzero saved segment above.
    vertices = np.r_[active[0], active+1]
    closed = np.array_equal(points[vertices[0]], points[vertices[-1]])
    joins = vertices[:-1] if closed else vertices[1:-1]
    if len(joins):
        disks = np.zeros((len(joins)*4, 16), dtype=np.float32)
        disks[:, :2] = np.repeat(points[joins], 4, axis=0)
        disks[:, 2:4] = np.tile(_QUAD_CORNERS, (len(joins), 1))
        disks[:, 4] = .5
        disks[:, 8] = material
        disks[:, 9] = np.repeat(arcs[joins], 4)
        disks[:, 10] = 3
        if closed:
            incoming, outgoing = np.roll(tangent, 1, axis=0), tangent
        else:
            incoming, outgoing = tangent[:-1], tangent[1:]
        disks[:, 12:14] = np.repeat(incoming, 4, axis=0)
        disks[:, 14:16] = np.repeat(outgoing, 4, axis=0)
        chunks.append(disks)
    if round_caps and not dashed and not closed:
        caps = np.zeros((8, 16), dtype=np.float32)
        caps[:, :2] = np.repeat(points[vertices[[0, -1]]], 4, axis=0)
        caps[:, 2:4] = np.tile(_QUAD_CORNERS, (2, 1))
        caps[:, 4] = .5
        caps[:, 8] = material
        caps[:, 9] = np.repeat(arcs[vertices[[0, -1]]], 4)
        caps[:, 10] = 2
        chunks.append(caps)
    _check(cancelled)
    vertices = np.concatenate(chunks)
    indices = (_QUAD_INDICES[None, :]+4*np.arange(len(vertices)//4, dtype=np.uint32)[:, None]).ravel()
    return vertices, indices


def _fan(rows):
    if len(rows) < 3:
        return np.empty((0, 16), dtype=np.float32)
    indices = np.column_stack((np.zeros(len(rows)-2, dtype=int),
                               np.arange(1, len(rows)-1), np.arange(2, len(rows)))).ravel()
    return rows, indices


def _lane_fan(template, source, target, material, shell):
    count = len(template.screen_base)
    rows = np.zeros((2*count, 16), dtype=np.float32)
    fraction = template.fractions
    for side, indices in ((0, np.arange(count)), (1, np.arange(2*count-1, count-1, -1))):
        rows[indices, :2] = template.screen_base
        rows[indices, 2:4] = template.normals
        rows[indices, 4] = source[side][0]*(1-fraction)
        rows[indices, 5] = target[side][0]*fraction
        rows[indices, 6] = source[side][1]*(1-fraction)+target[side][1]*fraction
        rows[indices, 7] = (-.5 if side == 0 else .5) if shell else 0.
        rows[indices, 8] = material
    return _fan(rows)


def _cross(a, b):
    return a[0]*b[1]-a[1]*b[0]


def _triangulate(points, cancelled):
    """Ear clip a simple polygon; return None for non-simple input (stencil)."""
    if len(points) > 1 and np.array_equal(points[0], points[-1]):
        points = points[:-1]
    if len(points) < 3:
        return np.empty((0, 2), dtype=np.float64)
    indices = [i for i in range(len(points)) if not np.array_equal(points[i], points[i-1])]
    points = points[indices]
    if len(points) < 3:
        return np.empty((0, 2), dtype=np.float64)
    edges = np.roll(points, -1, axis=0)-points
    turns = np.array([_cross(a, b) for a, b in zip(edges, np.roll(edges, -1, axis=0))])
    # Rectangles and the overwhelmingly common convex footprints avoid O(n²).
    # For >4 vertices equal turn signs alone do not prove simplicity (pentagram).
    if len(points) <= 4 and (np.all(turns >= 0) or np.all(turns <= 0)):
        order = np.column_stack((np.zeros(len(points)-2, dtype=int),
                                 np.arange(1, len(points)-1), np.arange(2, len(points)))).ravel()
        return points[order]
    if np.all(turns > 0) or np.all(turns < 0):
        dots = np.einsum('ij,ij->i', edges, np.roll(edges, -1, axis=0))
        turning = np.arctan2(turns, dots).sum()
        if abs(abs(turning)-2*math.pi) < 1e-8:
            # A strictly convex once-winding polygon clips the first ear each
            # time. Keep that exact triangle order rather than changing fans.
            order = np.column_stack((np.full(len(points)-3, len(points)-1),
                                     np.arange(len(points)-3), np.arange(1, len(points)-2))).ravel()
            order = np.r_[order, len(points)-3, len(points)-2, len(points)-1]
            return points[order]
    for i in range(len(points)):
        _check(cancelled)
        a, b = points[i], points[(i+1) % len(points)]
        end = len(points)-1 if i == 0 else len(points)
        for first in range(i+2, end, 256):
            _check(cancelled)
            selected = np.arange(first, min(first+256, end))
            c, d = points[selected], points[(selected+1) % len(points)]
            ab, ac, ad, cd = b-a, c-a, d-a, d-c
            ca, cb = a-c, b-c
            ab_c = ab[0]*ac[:, 1]-ab[1]*ac[:, 0]
            ab_d = ab[0]*ad[:, 1]-ab[1]*ad[:, 0]
            cd_a = cd[:, 0]*ca[:, 1]-cd[:, 1]*ca[:, 0]
            cd_b = cd[:, 0]*cb[:, 1]-cd[:, 1]*cb[:, 0]
            crossing = (ab_c*ab_d <= 0) & (cd_a*cd_b <= 0)
            crossing &= ((max(a[0], b[0]) >= np.minimum(c[:, 0], d[:, 0])) &
                         (np.maximum(c[:, 0], d[:, 0]) >= min(a[0], b[0])) &
                         (max(a[1], b[1]) >= np.minimum(c[:, 1], d[:, 1])) &
                         (np.maximum(c[:, 1], d[:, 1]) >= min(a[1], b[1])))
            if np.any(crossing):
                return None
    area = sum(_cross(a, b) for a, b in zip(points, np.roll(points, -1, axis=0)))
    if area == 0:
        return None
    sign = 1 if area > 0 else -1
    remaining = list(range(len(points)))
    result = []
    while len(remaining) > 3:
        _check(cancelled)
        for position, index in enumerate(remaining):
            before, after = remaining[position-1], remaining[(position+1) % len(remaining)]
            a, b, c = points[[before, index, after]]
            turn = sign*_cross(b-a, c-b)
            if turn == 0:
                del remaining[position]
                break
            if turn < 0:
                continue
            others = points[[item for item in remaining if item not in (before, index, after)]]
            ab, bc, ca = b-a, c-b, a-c
            ap, bp, cp = others-a, others-b, others-c
            inside = ((sign*(ab[0]*ap[:, 1]-ab[1]*ap[:, 0]) >= 0) &
                      (sign*(bc[0]*bp[:, 1]-bc[1]*bp[:, 0]) >= 0) &
                      (sign*(ca[0]*cp[:, 1]-ca[1]*cp[:, 0]) >= 0))
            if np.any(inside):
                continue
            result.extend((a, b, c))
            del remaining[position]
            break
        else:
            return None
    if len(remaining) == 3:
        result.extend(points[remaining])
    return np.asarray(result, dtype=np.float64).reshape(-1, 2)


def _buildings(builder, prepared):
    builder.owner_tile, builder.connection_member = None, None
    builder.shell_pass = -1
    for building in prepared.buildings:
        for area, path in building.members:
            _check(builder.cancelled)
            for points in _subpaths(path, builder.cancelled):
                bounds = _bounds(points)
                fill = builder.material(builder.make_material(6, fill=building.colour, area=area))
                triangle_points = _triangulate(points, builder.cancelled)
                if triangle_points is None:
                    rows = np.zeros((len(points), 16), dtype=np.float32)
                    rows[:, :2], rows[:, 8], rows[:, 10] = points, fill, 5
                    builder.winding([_fan(rows)], fill, bounds)
                else:
                    rows = np.zeros((len(triangle_points), 16), dtype=np.float32)
                    rows[:, :2], rows[:, 8], rows[:, 10] = triangle_points, fill, 5
                    builder.triangles(rows, bounds)
                edge = builder.material(builder.make_material(7, fill='#C4CDD3', area=area))
                if not np.array_equal(points[0], points[-1]):
                    points = np.vstack((points, points[0]))
                builder.triangles(_stroke(points, edge, round_caps=False, cancelled=builder.cancelled), bounds)


def _roads(builder, prepared):
    builder.owner_tile, builder.connection_member = None, None
    roads = defaultdict(list)
    connections = defaultdict(lambda: defaultdict(list))
    for road in prepared.roads:
        roads[road.layer, road.rank].append(road)
    for order, connection in enumerate(prepared.connections):
        connections[connection.layer][connection.owner_tile].append((order, connection))
    for layer in (0, 1, 2):
        for shell in (True, False):
            builder.shell_pass = int(shell)
            # Connection rank is selected from the narrower style at the
            # current zoom. Retain each range once, reference it in every rank
            # pass, and let the shader/renderer reject its other six passes.
            saved_commands, builder.commands = builder.commands, []
            for tile_items in connections[layer].values():
                _connections(builder, tile_items, shell, layer)
            connection_commands = []
            for command in builder.commands:
                material_indices = ([command.rank_material] if command.rank_material >= 0 else
                                    [member[3] for member in command.connection_members])
                possible_ranks = {int(builder.materials[index][column])
                                  for index in material_indices for column in (3, 7)}
                connection_commands.append((command, possible_ranks))
            builder.commands = saved_commands
            for rank in range(7):
                builder.owner_tile, builder.connection_member = None, None
                for road in roads[layer, rank]:
                    _check(builder.cancelled)
                    for span, path in road.members:
                        topology = layer == 1 and not (shell and road.tunnel)
                        key = 'road', id(road), id(path), span, topology
                        cached = builder.mesh_cache.get(key)
                        if cached is not None:
                            for command in cached[1]:
                                builder.reference(command)
                            continue
                        material = builder.material(builder.make_material(0, road.road,
                            span=span if road.level in ('local', 'pedestrian', 'unknown') else 0.,
                            layer=layer, tunnel=road.tunnel,
                            dash=(6., 4.) if road.tunnel else (0., 0.)))
                        commands = []
                        for points in _subpaths(path, builder.cancelled):
                            command = builder.triangles(_stroke(points, material, round_caps=layer == 1,
                                dashed=shell and road.tunnel, cancelled=builder.cancelled), _gpu_bounds(road.bounds))
                            if command is not None:
                                commands.append(command)
                        builder.mesh_cache[key] = (road, path), tuple(commands)
                for command, possible_ranks in connection_commands:
                    if rank in possible_ranks:
                        builder.commands.append(replace(command, connection_rank=rank))


def _connection_stroke(builder, connection, template, order, bounds, layer, shell, overview):
    topology = layer == 1 and not (shell and connection.tunnel)
    key = 'connection-stroke', id(connection), id(template), topology, overview
    cached = builder.mesh_cache.get(key)
    if cached is not None:
        command = cached[1]
        if command is not None:
            builder.connection_member = (order, bounds, connection.span, command.rank_material)
            builder.reference(command)
        else:
            builder.connection_member = None
        return
    material = builder.material(builder.make_material(8, connection.source, connection.target,
        gradient=template.screen_base[[0, -1]], span=connection.span,
        layer=layer, tunnel=connection.tunnel,
        dash=(6., 4.) if connection.tunnel else (0., 0.),
        maximum=.15 if overview else math.inf))
    builder.connection_member = (order, bounds, connection.span, material)
    rows = _stroke(template.screen_base, material, round_caps=layer == 1,
                   dashed=shell and connection.tunnel, cancelled=builder.cancelled)
    command = builder.triangles(rows, bounds, maximum=.15 if overview else math.inf, rank_material=material)
    builder.mesh_cache[key] = (connection, template), command


def _connections(builder, connections, shell, layer):
    builder.shell_pass = int(shell)
    entries = []
    # Keep overview indices together for compact stroke submission. Member
    # order restores saved paint order alongside strokes used at every scale.
    for order, connection in connections:
        _check(builder.cancelled)
        source = builder.lane_coefficients(connection.source, connection.source_lane)
        target = builder.lane_coefficients(connection.target, connection.target_lane)
        for template in connection.templates:
            valid_lane = source is not None and target is not None and bool(template.fractions[-1])
            bounds = _gpu_bounds(connection.bounds)
            entries.append((order, connection, template, source, target, bounds, valid_lane))
            if not valid_lane:
                continue
            builder.owner_tile = connection.owner_tile
            _connection_stroke(builder, connection, template, order, bounds, layer, shell, True)

    for order, connection, template, source, target, bounds, valid_lane in entries:
        _check(builder.cancelled)
        builder.owner_tile = connection.owner_tile
        if not valid_lane:
            _connection_stroke(builder, connection, template, order, bounds, layer, shell, False)
            continue
        key = 'lane', id(connection), id(template)
        cached = builder.mesh_cache.get(key)
        if cached is not None:
            command = cached[1]
            builder.connection_member = (order, bounds, connection.span, command.rank_material)
            builder.reference(command)
            continue
        material_values = builder.make_material(2, connection.source, connection.target,
            gradient=template.screen_base[[0, -1]], span=connection.span, layer=layer,
            tunnel=connection.tunnel, minimum=.15)
        material = builder.material(material_values)
        member = (order, bounds, connection.span, material)
        builder.connection_member = member
        # The pass uniform applies this retained casing coefficient only when
        # rendering shell, so both passes reference precisely the same rows.
        rows, fan_indices = _lane_fan(template, source, target, material, True)
        if builder.prove_strip(rows, material_values):
            count = len(rows)//2
            left = np.arange(count-1, dtype=np.uint32)
            right = 2*count-1-left
            indices = np.column_stack((left, left+1, right-1, left, right-1, right)).ravel()
            command = builder.triangles((rows, indices), bounds, minimum=.15, rank_material=material)
        else:
            # Independent signed windings must not be summed: opposite signs
            # at an overlap can cancel, including within self-crossing lanes.
            command = builder.winding([(rows, fan_indices)], material, bounds, .15)
            command = replace(command, rank_material=material, owner_tile=connection.owner_tile,
                              original_order=order, connection_members=(member,))
            builder.commands[-1] = command
        builder.mesh_cache[key] = (connection, template), command
    builder.owner_tile, builder.connection_member = None, None


def _routes(builder, surface, prepared):
    builder.owner_tile, builder.connection_member = None, None
    builder.shell_pass = -1
    from map_canvas import continuous_paths
    modes = surface.options['layer_modes']
    routes = [route for route in prepared.routes
              if modes is None or canonical_key('mode', route.mode) in modes] if surface.options['routes'] else []
    if surface.options['deadhead']:
        for route in routes:
            _check(builder.cancelled)
            colour = QColor(surface._route_color(route))
            colour.setAlpha(95)
            width = surface._route_width(route, 2.)
            # Qt's legacy depot DashLine defaults to 4w/2w, unlike the fixed
            # 8/5px operational direction pattern.
            material = builder.material(builder.make_material(5, fill=colour, width=width, dash=(4*width, 2*width)))
            for path in continuous_paths(route.depot_paths):
                points = _saved_points(path, builder.cancelled)
                if len(points) >= 2:
                    builder.triangles(_stroke(points, material, round_caps=False, dashed=True,
                                              cancelled=builder.cancelled), _bounds(points))
    for route in routes:
        _check(builder.cancelled)
        colour = surface._route_color(route)
        width = surface._route_width(route, 0.)
        drawn = set()
        for paths, dashed in surface._route_path_groups(route):
            for path in continuous_paths(paths):
                _check(builder.cancelled)
                if len(path) < 2:
                    continue
                key = (min(tuple(path), tuple(reversed(path))), bool(dashed))
                if key in drawn:
                    continue
                drawn.add(key)
                points = _saved_points(path, builder.cancelled)
                material = builder.material(builder.make_material(4, fill=colour, width=width,
                                                       dash=(8., 5.) if dashed else (0., 0.)))
                builder.triangles(_stroke(points, material, dashed=dashed,
                                          cancelled=builder.cancelled), _bounds(points))


def compile_gpu_scene(surface, prepared, cancelled=None):
    """Compile one prepared/query revision, with no center, zoom or size input."""
    _check(cancelled)
    builder = _Builder(cancelled)
    _buildings(builder, prepared)
    _roads(builder, prepared)
    _routes(builder, surface, prepared)
    return builder.finish()


def compile_gpu_layers(surface, prepared, cancelled=None, base=None):
    """Retain a supplied base verbatim while independently compiling routes."""
    _check(cancelled)
    if base is None:
        builder = _Builder(cancelled)
        _buildings(builder, prepared)
        _roads(builder, prepared)
        base = builder.finish()
    routes = _Builder(cancelled)
    _routes(routes, surface, prepared)
    return GpuLayers(base, routes.finish())
