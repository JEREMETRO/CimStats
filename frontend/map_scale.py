"""Map screen-symbol curves; zoom is logical pixels per saved metre."""


def detail_fraction(zoom, midpoint=.75):
    return zoom/(zoom+midpoint)


def route_width(zoom):
    """Readable overview stroke, smoothly approaching six logical pixels."""
    return 1.4+4.6*detail_fraction(zoom)


def route_gap(zoom):
    return .4+.6*detail_fraction(zoom)


def stop_radius(zoom):
    return 1.2+2.3*detail_fraction(zoom, .25)


def stop_outline(zoom):
    return .65+.55*detail_fraction(zoom, .25)


def bundle_offsets(widths, zoom):
    """Pack distinct colour/direction strokes symmetrically without overlap."""
    gap = route_gap(zoom)
    cursor = -(sum(widths.values())+gap*(len(widths)-1))/2
    offsets = {}
    for identity in sorted(widths):
        width = widths[identity]
        offsets[identity] = cursor+width/2
        cursor += width+gap
    return offsets
