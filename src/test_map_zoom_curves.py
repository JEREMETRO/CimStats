"""Screen symbols remain legible and continuous over the supported map zooms."""
import pytest
from PySide6.QtGui import QImage, QPainter

from map_canvas import MapCanvas, _FrameSurface, MAP_BACKGROUND, road_style
from map_model import MapRoute, MapRoad, MapSnapshot, RouteDirection
from map_vector import build_vector_map, paint_vector_map, _route_plan


def surface(qt_application, zoom, widths=None, count=1):
    path = ((-10000., 0., 0.), (10000., 0., 0.))
    colours = ['#e03030', '#3060e0', '#209040', '#9040b0', '#d08020']
    routes = tuple(MapRoute(i, str(i), i, 'company', 'company', 'bus', (),
                            (path,), RouteDirection('oneway', None)) for i in range(count))
    canvas = MapCanvas()
    canvas.resize(400, 190)
    canvas.set_snapshot(MapSnapshot(routes=routes, bounds=(-10000., -100., 10000., 100.)))
    canvas.center = (0., 0.)
    canvas.zoom = zoom
    canvas.set_options(roads=False, buildings=False, routes=True, stops=False,
                       line_numbers=False, stop_names=False,
                       mode_widths=widths or {},
                       route_colors={i: colours[i] for i in range(count)})
    value = _FrameSurface(canvas)
    canvas.close()
    return value


def pixels(value):
    prepared = build_vector_map(value)
    image = QImage(value._size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(MAP_BACKGROUND)
    painter = QPainter(image)
    try:
        paint_vector_map(painter, value, prepared, overlays=False)
    finally:
        painter.end()
    return image, prepared


def test_automatic_line_stroke_grows_through_street_scales(qt_application):
    # Measure coverage of the actual rasterized vector stroke, including AA.
    widths = []
    for zoom in (.02, .05, .1, .25, .5, 1., 2., 4., 16., 100.):
        image, _ = pixels(surface(qt_application, zoom))
        base = image.pixelColor(0, 0).green()
        widths.append(sum((base-image.pixelColor(200, y).green())/(base-48)
                          for y in range(image.height())))
    assert all(a <= b+.05 for a, b in zip(widths, widths[1:])), widths
    assert widths[7] > widths[5]+1., widths
    assert widths[-1] <= 6.1, widths


@pytest.mark.parametrize('threshold', [.15, .4])
def test_line_stroke_has_no_old_zoom_threshold_jump(qt_application, threshold):
    before, _ = pixels(surface(qt_application, threshold-1e-7))
    after, _ = pixels(surface(qt_application, threshold+1e-7))
    assert before.bits().tobytes() == after.bits().tobytes()


@pytest.mark.parametrize('zoom', [.05, .14999, .15, .25, 1., 4., 16., 100.])
def test_five_shared_lines_keep_all_colours_and_clear_gaps(qt_application, zoom):
    value = surface(qt_application, zoom, count=5)
    image, prepared = pixels(value)
    colours = {r.id: value._route_color(r) for r in prepared.routes}
    _, offsets = _route_plan(value, prepared, prepared.routes, colours)
    locations = sorted(offsets[(r.id, id(r.paths[0]), False)] for r in prepared.routes)
    assert len(set(locations)) == 5
    # Sub-two-pixel AA strokes can cover a pixel only partially. Each colour
    # must still have a nearly full coverage pixel rather than being overpainted.
    column = [image.pixelColor(200,y) for y in range(image.height())]
    for colour in colours.values():
        distance = min(max(abs(a-b) for a,b in zip(pixel.getRgb()[:3],colour.getRgb()[:3]))
                       for pixel in column)
        assert distance <= 32, (zoom, colour.name(), locations, distance)


@pytest.mark.parametrize('zoom', [.05, 1., 4., 100.])
def test_manual_pixel_width_retains_its_meaning_at_every_zoom(qt_application, zoom):
    image, _ = pixels(surface(qt_application, zoom, widths={'bus': 8.}))
    assert image.pixelColor(200, 98).name() == '#e03030'
    assert image.pixelColor(200, 101).name() == MAP_BACKGROUND.lower()


def test_saved_physical_road_width_does_not_collapse_at_high_zoom():
    road = MapRoad(1, 'road', 'asset', (((0., 0., 0.), (100., 0., 0.)),),
                   width=12., lanes_a=1, lanes_b=1, road_class='ordinary')
    assert road_style(road, 20.).width == pytest.approx(240.)


def test_automatic_curves_have_finite_smooth_derivatives_and_documented_anchors():
    from map_scale import route_width, route_gap, stop_radius
    for function in (route_width, route_gap, stop_radius):
        for zoom in (.0001, .05, .1, .15, .25, .4, 1., 4., 100.):
            h = zoom*1e-5
            left = (function(zoom)-function(zoom-h))/h
            right = (function(zoom+h)-function(zoom))/h
            assert left == pytest.approx(right, rel=1e-3, abs=1e-6)
    assert route_width(.05) == pytest.approx(1.6875)
    assert route_width(1.) == pytest.approx(4.028571428571429)
    assert route_width(4.) == pytest.approx(5.273684210526316)
    assert route_width(100.) < 6.


def test_far_overview_checks_populated_tiles_instead_of_millions_of_empty_cells(qt_application,monkeypatch):
    import map_vector
    from map_model import MapJunction, MapJunctionConnection
    road = MapRoad(1,'road','asset',(((0.,0.,0.),(100.,0.,0.)),))
    connection = MapJunctionConnection(2,1,1,0,0,1,(((0.,0.,0.),(100.,0.,0.)),))
    canvas = MapCanvas(); canvas.resize(400,190)
    canvas.set_snapshot(MapSnapshot(roads=(road,),junctions=(
        MapJunction(3,(50.,0.,0.),(1,),(connection,)),),bounds=(0.,0.,100.,100.)))
    value = _FrameSurface(canvas); canvas.close()
    prepared = build_vector_map(value)
    def empty_grid_walk(_):
        raise AssertionError('The far overview enumerates empty world tiles')
    monkeypatch.setattr(map_vector,'_tiles',empty_grid_walk)
    huge = (-1e7,-1e7,1e7,1e7)
    assert len(tuple(map_vector._visible_items(prepared.roads,prepared.road_tiles,huge))) == 1
    assert tuple(map_vector._visible_connections(prepared,huge,.0001)) == ()


def test_high_zoom_road_edge_is_visible_when_its_centerline_is_outside_view(qt_application):
    road = MapRoad(1,'road','asset',(((-100.,0.,7.75),(100.,0.,7.75)),),
                   width=12.,lanes_a=1,lanes_b=1,road_class='ordinary')
    canvas = MapCanvas();canvas.resize(400,190)
    canvas.set_snapshot(MapSnapshot(roads=(road,),bounds=(-100.,-100.,100.,100.)))
    canvas.set_options(routes=False,buildings=False,stops=False)
    canvas.center=(0.,0.);canvas.zoom=20.
    value=_FrameSurface(canvas);canvas.close()
    image,_=pixels(value)
    assert image.pixelColor(200,10).name() == '#ffffff'
    value.center=(0.,1.)
    image,_=pixels(value)
    assert image.pixelColor(200,10).name() == '#ffffff'


def test_large_shared_route_bundle_enters_view_before_its_centerline(qt_application):
    path=((-1000.,0.,155.),(1000.,0.,155.))
    routes=tuple(MapRoute(i,str(i),i,'c','company','bus',(),(path,)) for i in range(12))
    canvas=MapCanvas();canvas.resize(400,190)
    canvas.set_snapshot(MapSnapshot(routes=routes,bounds=(-1000.,-1000.,1000.,1000.)))
    canvas.set_options(roads=False,buildings=False,stops=False,stop_names=False,line_numbers=False,
                       mode_widths={'bus':12.},route_colors={i:f'#{i+1:02x}44cc' for i in range(12)})
    canvas.center=(0.,0.);canvas.zoom=1.
    value=_FrameSurface(canvas);canvas.close()
    image,prepared=pixels(value)
    colour=image.pixelColor(200,10)
    assert colour.green()<100
    value.center=(0.,20.)
    image2,prepared2=pixels(value)
    assert image2.pixelColor(200,30) == colour


def test_wide_connection_footprint_remains_visible_above_view(qt_application):
    from map_model import MapJunction,MapJunctionConnection
    road=MapRoad(1,'road','asset',(((100.,0.,0.),(150.,0.,0.)),),
                 width=60.,lanes_a=1,lanes_b=1,road_class='ordinary')
    other=MapRoad(2,'road','asset',(((-150.,0.,0.),(-100.,0.,0.)),),
                  width=60.,lanes_a=1,lanes_b=1,road_class='ordinary')
    curve=((-100.,0.,7.75),(100.,0.,7.75))
    junction=MapJunction(3,(0.,0.,7.75),(1,2),(
        MapJunctionConnection(4,1,2,0,0,1,(curve,)),))
    canvas=MapCanvas();canvas.resize(400,190)
    canvas.set_snapshot(MapSnapshot(roads=(road,other),junctions=(junction,),bounds=(-150.,-100.,150.,100.)))
    canvas.set_options(routes=False,buildings=False,stops=False)
    canvas.center=(0.,0.);canvas.zoom=20.
    value=_FrameSurface(canvas);canvas.close()
    image,_=pixels(value)
    assert image.pixelColor(200,10).name() == '#ffffff'
