"""Immutable map records; coordinates are game metres (x, elevation, z)."""
from __future__ import annotations
from dataclasses import dataclass

Point = tuple[float, float, float]
Path = tuple[Point, ...]

@dataclass(frozen=True, slots=True)
class GroupCount:
    group: str
    count: int | None


SOCIAL_GROUPS = ('BlueCollar','WhiteCollar','Student','BusinessPeople','Pensioner','Tourist')


@dataclass(frozen=True, slots=True)
class GroupFunctionCount:
    group: str
    home: int | None
    work: int | None
    leisure: int | None


@dataclass(frozen=True, slots=True)
class BuildingFunctionValues:
    home: int | None
    work: int | None
    leisure: int | None
    denominator: int | None

@dataclass(frozen=True, slots=True)
class MapLane:
    index: int
    type_mask: int
    turn_directions: int
    offset: float


@dataclass(frozen=True, slots=True)
class MapRoad:
    id: int
    asset_id: str
    name: str
    paths: tuple[Path, ...]
    lanes_a: int | None = None
    lanes_b: int | None = None
    express: bool | None = None
    track: bool = False
    bridge: bool = False
    tunnel: bool = False
    width: float | None = None
    road_class: str = 'unknown'
    one_way: bool | None = None
    sidewalk_left: float | None = None
    sidewalk_right: float | None = None
    platform_width: float | None = None
    bus_lane: bool | None = None
    parking_lane: bool | None = None
    shoulder: bool | None = None
    pedestrian: bool | None = None
    bridge_masks: tuple[int, ...] = ()
    tunnel_masks: tuple[int, ...] = ()
    declared_lanes_a: int | None = None
    declared_lanes_b: int | None = None
    bus_lanes_a: int | None = None
    bus_lanes_b: int | None = None
    parking_lanes_a: int | None = None
    parking_lanes_b: int | None = None
    lanes: tuple[MapLane, ...] = ()

@dataclass(frozen=True, slots=True)
class MapBuilding:
    id: int
    asset_id: str
    name: str
    position: Point
    polygon: Path = ()
    category: str = 'unknown'
    residents: tuple[GroupCount, ...] = ()
    workers: tuple[GroupCount, ...] = ()
    area: float | None = None
    combined_groups: tuple[GroupCount, ...] = ()
    function_capacities: tuple[GroupFunctionCount, ...] = ()
    function_population: tuple[GroupFunctionCount, ...] = ()
    game_area_type: int | None = None

@dataclass(frozen=True, slots=True)
class MapStop:
    id: int
    name: str
    position: Point


@dataclass(frozen=True, slots=True)
class MapJunctionConnection:
    id: int
    source_road_id: int
    target_road_id: int
    source_lane: int
    target_lane: int
    type_mask: int
    paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class MapJunction:
    id: int
    position: Point
    road_ids: tuple[int, ...] = ()
    connections: tuple[MapJunctionConnection, ...] = ()
    bridge: bool = False
    tunnel: bool = False
    diagnostic: str | None = None

    @property
    def paths(self) -> tuple[Path, ...]:
        return tuple(p for connection in self.connections for p in connection.paths)

@dataclass(frozen=True, slots=True)
class RouteDirection:
    kind: str = 'unknown'
    terminal_index: int | None = None
    paired_stations: tuple[tuple[int, int], ...] = ()
    score: float | None = None
    geometry_score: float | None = None
    station_score: float | None = None
    terminal_rule: str = 'geometry'

@dataclass(frozen=True, slots=True)
class MapRoute:
    id: int
    name: str
    number: int
    company_id: str
    company_name: str
    mode: str
    stop_ids: tuple[int, ...]
    paths: tuple[Path, ...]
    direction: RouteDirection = RouteDirection()
    leg_paths: tuple[tuple[Path, ...], ...] = ()
    depot_paths: tuple[Path, ...] = ()
    diagnostic: str | None = None
    company_index: int | None = None
    previous_day_passengers: int | None = None
    passenger_date: str | None = None
    passenger_diagnostic: str | None = None

@dataclass(frozen=True, slots=True)
class MapSnapshot:
    roads: tuple[MapRoad, ...] = ()
    buildings: tuple[MapBuilding, ...] = ()
    stops: tuple[MapStop, ...] = ()
    routes: tuple[MapRoute, ...] = ()
    source_hash: str = ''
    asset_signature: str = ''
    diagnostics: tuple[str, ...] = ()
    bounds: tuple[float, float, float, float] = (0., 0., 1., 1.)
    schema_version: int = 9
    junctions: tuple[MapJunction, ...] = ()

class MapModel:
    """Pure identity lookup; renderer and query layer share this snapshot."""
    def __init__(self, snapshot: MapSnapshot):
        self.snapshot = snapshot
        self.roads = {record.id: record for record in snapshot.roads}
        self.buildings = {record.id: record for record in snapshot.buildings}
        self.stops = {record.id: record for record in snapshot.stops}
        self.routes = {record.id: record for record in snapshot.routes}
        self.junctions = {record.id: record for record in snapshot.junctions}

    def route(self, route_id: int) -> MapRoute | None:
        return self.routes.get(route_id)

    def stop_sequence(self, route_id: int) -> tuple[MapStop, ...]:
        route = self.route(route_id)
        return tuple(self.stops[sid] for sid in route.stop_ids if sid in self.stops) if route else ()


def polygon_area(polygon: Path) -> float | None:
    if len(polygon) < 3:
        return None
    area = abs(sum(a[0]*b[2]-b[0]*a[2] for a,b in zip(polygon, polygon[1:]+polygon[:1]))) / 2
    return area if area > 0 else None


def building_function_values(building: MapBuilding, selected_groups=None) -> BuildingFunctionValues:
    """Native home/work/leisure capacities with a fixed all-group denominator.

    Actual associated population lives separately in function_population.
    Any missing native capacity remains unknown, never an invented zero.
    """
    records={r.group:r for r in building.function_capacities}
    selected=SOCIAL_GROUPS if selected_groups is None else tuple(dict.fromkeys(selected_groups))
    def total(groups,role):
        values=[getattr(records[g],role) if g in records else None for g in groups]
        return None if any(v is None for v in values) else sum(values)
    full=[total(SOCIAL_GROUPS,role) for role in ('home','work','leisure')]
    denominator=None if any(v is None for v in full) else max(full)
    return BuildingFunctionValues(*(total(selected,role) for role in ('home','work','leisure')),denominator)


def road_display_level(road: MapRoad) -> str:
    """Map drawing hierarchy derived from real asset + saved lane attributes.

    This is a presentation mapping, not a claimed game functional road grade.
    Direction, bridge and tunnel flags remain independent of the hierarchy.
    """
    if road.track or road.road_class in ('rail','tram_track','monorail_track'):
        return 'track'
    if road.express or road.road_class == 'expressway':
        return 'express'
    if road.pedestrian or road.road_class == 'pedestrian':
        return 'pedestrian'
    if road.road_class == 'avenue' or road.asset_id == 'avenue':
        return 'arterial'
    if road.lanes_a is None or road.lanes_b is None:
        return 'unknown'
    # Depot access is local even when its saved template has multiple lanes.
    if road.asset_id.startswith('depot-road'):
        return 'local'
    if road.road_class == 'ordinary' or road.asset_id in ('road','oneway-road','single-trolley','double-trolley'):
        lanes=road.lanes_a+road.lanes_b
        return 'arterial' if lanes >= 6 else 'secondary' if lanes >= 4 else 'local'
    return 'unknown'


def group_metric(building: MapBuilding, group: str, role: str = 'combined', metric: str = 'count') -> float | None:
    if role not in ('combined', 'residents', 'workers'):
        raise ValueError(f'Unknown population role: {role}')
    if metric not in ('count', 'density', 'proportion'):
        raise ValueError(f'Unknown map metric: {metric}')
    counts = getattr(building, 'combined_groups' if role == 'combined' else role)
    selected = next((c.count for c in counts if c.group == group), None)
    if selected is None:
        return None
    if metric == 'count':
        return float(selected)
    if metric == 'density':
        return selected / building.area if building.area else None
    if metric == 'proportion':
        total = sum(c.count for c in counts if c.count is not None)
        return selected / total if total else 0.
    raise ValueError(f'Unknown map metric: {metric}')
