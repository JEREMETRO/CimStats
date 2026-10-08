"""Native road-count mileage and saved arrival times for a selected route direction."""
from dataclasses import dataclass
from math import isfinite

from display_rules import display_map_km
from map_model import MapRoute
from map_visibility import operating_leg_indices

TICKS_PER_MINUTE = 600_000_000


@dataclass(frozen=True, slots=True)
class RouteMetrics:
    effective_direction: str
    length_km: float | None
    operating_km: float | None
    deadhead_km: float | None
    duration_minutes: float | None
    speed_kmh: float | None
    approved_duration_ticks: int | None = None
    diagnostics: tuple[str, ...] = ()

    @property
    def total_km(self):
        return self.length_km


def saved_leg_map_length(path, field, array):
    """Original map_length_from_vehicle_route scope, retaining repeated references."""
    if path is None:
        return None
    total = 0
    for segment in array(path)[:-1]:
        road = field(segment, 'm_road')
        if road is None:
            continue
        value = field(road, 'm_length')
        if value is None or int(value) < 0:
            return None
        total += int(value)
    return total


def _km(parts):
    if not parts or any(type(v) is not int or v < 0 for v in parts):
        return None
    return display_map_km(sum(parts) / 1024 / 1000)


def selected_route_metrics(route: MapRoute, direction: str = 'whole', include_depot: bool = False, *,
                           whole_duration_minutes: float | None = None,
                           whole_length_km: float | None = None) -> RouteMetrics:
    """Only whole views may use the original information-page fallback values."""
    if direction not in ('whole', 'up', 'down'):
        raise ValueError(direction)
    effective = direction if route.direction.kind == 'roundtrip' else 'whole'
    issues = []
    terminal = route.direction.terminal_index
    if (effective != 'whole' and (route.direction.kind != 'roundtrip'
            or type(terminal) is not int or not 0 < terminal < len(route.stop_ids)-1)):
        return RouteMetrics(effective, None, None, None, None, None,
                            diagnostics=('direction_terminal_unknown',))
    expected_legs = len(route.stop_ids)-1
    indices = tuple(operating_leg_indices(route, effective, leg_count=max(0,expected_legs)))
    lengths = route.leg_map_length_units
    selected_lengths = ([lengths[i] for i in indices]
                        if expected_legs > 0 and len(lengths) == expected_legs else [])
    operating = _km(selected_lengths)
    depot = route.depot_map_length_units
    depot_indices = (0,1) if effective == 'whole' else (0,) if effective == 'down' else (1,)
    depot_lengths = [depot[i] for i in depot_indices] if len(depot) == 2 else []
    deadhead = _km(depot_lengths)
    # Sum integer native units first, then convert once, including deadhead.
    length = (_km(selected_lengths + depot_lengths)
              if include_depot and operating is not None and deadhead is not None
              else operating if not include_depot else None)
    if operating is None:
        issues.append('native_operating_length_missing')
        if effective == 'whole' and whole_length_km is not None:
            length = whole_length_km
    if include_depot and deadhead is None:
        issues.append('native_deadhead_length_missing')

    duration = ticks = None
    if effective == 'whole':
        if whole_duration_minutes is not None and isfinite(float(whole_duration_minutes)) and whole_duration_minutes >= 0:
            duration = float(whole_duration_minutes)
            ticks = int(duration * TICKS_PER_MINUTE)
    else:
        offsets = route.stop_arrival_offsets_ticks
        start, end = (0, terminal) if effective == 'down' else (terminal, len(route.stop_ids)-1)
        selected = offsets[start:end+1] if len(offsets) == len(route.stop_ids) else ()
        if (selected and all(type(v) is int and v >= 0 for v in selected)
                and all(a <= b for a,b in zip(selected,selected[1:]))):
            difference = selected[-1]-selected[0]
            if difference > 0 or (difference == 0 and operating == 0):
                ticks = difference
                duration = ticks / TICKS_PER_MINUTE
    if duration is None:
        issues.append('approved_arrival_time_missing')
    # Business-stop offsets exclude depot travel. The display switch cannot
    # add depot mileage to that denominator. Whole views use the original
    # full-line mileage with the original full-line approved duration.
    speed_length = operating
    if effective == 'whole':
        speed_length = whole_length_km
        if speed_length is None and operating is not None and deadhead is not None:
            speed_length = _km(selected_lengths + depot_lengths)
    speed = speed_length / duration * 60 if speed_length is not None and duration is not None and duration > 0 else None
    return RouteMetrics(effective,length,operating,deadhead,duration,speed,ticks,tuple(issues))
