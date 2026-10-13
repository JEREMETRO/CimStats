"""Operating direction selection shared by map queries and painting."""
import math


def usable_paths(paths):
    return any(any(a[0] != b[0] or a[2] != b[2] for a, b in zip(path, path[1:])) for path in paths or ())


def route_has_geometry(route):
    return route is not None and usable_paths(operating_paths(route))


def operating_leg_indices(route, direction='whole', *, leg_count=None):
    terminal = route.direction.terminal_index
    count = len(route.leg_paths) if leg_count is None else leg_count
    indices = range(count)
    if route.direction.kind != 'roundtrip' or terminal is None:
        return indices
    if direction == 'up':
        return range(terminal, count)
    if direction == 'down':
        return range(terminal)
    return indices


def operating_paths(route, direction='whole'):
    if not route.leg_paths:
        return route.paths
    return tuple(path for i in operating_leg_indices(route, direction) for path in route.leg_paths[i])


def visible_route_stop_ids(route, direction='whole'):
    if not route.leg_paths:
        return frozenset(route.stop_ids) if usable_paths(route.paths) else frozenset()
    return frozenset(sid for i in operating_leg_indices(route,direction)
                     if usable_paths(route.leg_paths[i]) for sid in route.stop_ids[i:i+2])


def route_stop_symbols(route, stops):
    """Display anchors on explicit operating-leg endpoints, never change data.

    A line's saved lane range does not record a vehicle's dynamic lane changes.
    Transit symbols use the rendered corridor; native stop positions remain
    authoritative for service coverage. Missing endpoint evidence stays raw.
    """
    incomplete = any(key in (route.diagnostic or '') for key in (
        'missing_road', 'projection_distant', 'reversed_station_projection',
        'missing_stop_position', 'missing_leg', 'invalid_curve', 'empty_road',
        'path_leg_count_mismatch'))
    if incomplete or len(route.stop_ids) != len(route.leg_paths)+1:
        return tuple((-1,sid,stops[sid].position) for sid in route.stop_ids if sid in stops)
    records=[]
    for i,paths in enumerate(route.leg_paths):
        if not usable_paths(paths):
            continue
        usable=tuple(path for path in paths if len(path)>1)
        for sid,position in zip(route.stop_ids[i:i+2],(usable[0][0],usable[-1][-1])):
            stop=stops.get(sid)
            if stop is None:
                continue
            # Reject distant or vertically unrelated endpoints; no global snap.
            if math.dist(stop.position,position)>12 or abs(stop.position[1]-position[1])>.5:
                position=stop.position
            records.append((i,sid,position))
    return tuple(records)
