"""Operating direction selection shared by map queries and painting."""


def operating_leg_indices(route, direction='whole'):
    terminal = route.direction.terminal_index
    indices = range(len(route.leg_paths))
    if route.direction.kind != 'roundtrip' or terminal is None:
        return indices
    if direction == 'up':
        return range(terminal, len(route.leg_paths))
    if direction == 'down':
        return range(terminal)
    return indices


def operating_paths(route, direction='whole'):
    if not route.leg_paths:
        return route.paths
    return tuple(path for i in operating_leg_indices(route, direction) for path in route.leg_paths[i])


def visible_route_stop_ids(route, direction='whole'):
    def usable(paths):
        return any(any(a[0] != b[0] or a[2] != b[2] for a,b in zip(path,path[1:])) for path in paths)
    if not route.leg_paths:
        return frozenset(route.stop_ids) if usable(route.paths) else frozenset()
    return frozenset(sid for i in operating_leg_indices(route,direction)
                     if usable(route.leg_paths[i]) for sid in route.stop_ids[i:i+2])
