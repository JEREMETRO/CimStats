"""Map screen-symbol curves; zoom is logical pixels per saved metre."""
import math


def detail_fraction(zoom, midpoint=.75):
    return zoom/(zoom+midpoint)


def route_width(zoom):
    """Readable overview stroke with gentle continued growth in close views."""
    return (1.4+4.6*detail_fraction(zoom)+2.2*math.log2(1+zoom)
            -.55*math.exp(-(zoom/.18)**2))


def stop_radius(zoom):
    return 1.2+2.3*detail_fraction(zoom, .25)+1.1*math.log2(1+zoom)


def stop_outline(zoom):
    return .65+.55*detail_fraction(zoom, .25)
