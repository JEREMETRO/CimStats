"""Transit symbols follow their own visible leg; saved positions stay intact."""
from dataclasses import replace
import pytest
from PySide6.QtGui import QImage, QPainter
from map_canvas import MapCanvas, _FrameSurface, MAP_BACKGROUND
from map_model import MapStop, MapRoute, MapSnapshot, RouteDirection
from map_vector import build_vector_map, paint_vector_map
import stats_tokens as tokens


def scene(qt_application):
    path=((-1000.,0.,0.),(0.,0.,0.),(1000.,0.,0.))
    leg=(path,)
    route=MapRoute(1,'route',1,'c','company','bus',(10,11),(path,),
                   RouteDirection('oneway'),(leg,))
    stop=MapStop(10,'stop',(0.,0.,6.))
    # The clipped departure point is already an explicit operating-leg endpoint.
    route=replace(route,paths=((path[1],path[2]),),leg_paths=(((path[1],path[2]),),))
    canvas=MapCanvas();canvas.resize(400,300)
    canvas.set_snapshot(MapSnapshot(stops=(stop,MapStop(11,'end',path[-1])),
                                   routes=(route,),bounds=(-1000.,-100.,1000.,100.)))
    canvas.set_options(roads=False,buildings=False,stop_names=False,line_numbers=False,
                       route_colors={1:'#d03080'})
    canvas.center=(0.,0.)
    return canvas,stop,route


@pytest.mark.parametrize('zoom',[.25,1.,4.,16.,100.])
def test_actual_symbol_is_on_its_line_at_every_zoom(qt_application,zoom):
    canvas,stop,route=scene(qt_application);canvas.zoom=zoom
    surface=_FrameSurface(canvas);prepared=build_vector_map(surface)
    for vector in (True,False):
        image=QImage(400,300,QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(MAP_BACKGROUND);p=QPainter(image)
        if vector:paint_vector_map(p,surface,prepared,overlays=False)
        else:surface._paint(p,overlays=False)
        p.end()
        assert image.pixelColor(200,150).name() == tokens.CARD_BG.lower()
    assert canvas.snapshot.stops[0].position == (0.,0.,6.)
    assert canvas.snapshot.routes[0] is route
    canvas.close()


def test_search_focus_and_highlight_share_the_visible_symbol(qt_application):
    canvas,stop,route=scene(qt_application)
    canvas.zoom=100.
    assert canvas.focus_result(canvas.search('stop')[0])
    assert canvas.center == (0.,0.)
    surface=_FrameSurface(canvas)
    records=surface._display_stops((route,))
    assert records == ((stop,(0.,0.,0.)),)
    canvas.close()


def test_shared_station_uses_topmost_visible_route_and_direction(qt_application):
    canvas,stop,route=scene(qt_application)
    up=((-1000.,0.,-3.),(0.,0.,-3.))
    down=route.paths[0]
    other=replace(route,id=2,stop_ids=(12,10,11),paths=(up,down),
                  leg_paths=((up,),(down,)),direction=RouteDirection('roundtrip',1))
    canvas.set_snapshot(replace(canvas.snapshot,routes=(route,other),
        stops=canvas.snapshot.stops+(MapStop(12,'far',up[0]),)))
    canvas.center=(0.,0.);canvas.zoom=4.
    canvas.set_options(direction='down')
    positions={s.id:p for s,p in _FrameSurface(canvas)._display_stops((route,other))}
    assert positions[10] == up[-1]
    # Hidden routes cannot supply a marker from a different lane.
    positions={s.id:p for s,p in _FrameSurface(canvas)._display_stops((route,))}
    assert positions[10] == (0.,0.,0.)
    canvas.close()


@pytest.mark.parametrize('position,diagnostic',[
    ((0.,10.,0.),None),((1000.,0.,0.),None),((0.,0.,6.),'leg:1:missing_road:50')])
def test_incomplete_or_unrelated_endpoint_keeps_native_position(qt_application,position,diagnostic):
    canvas,stop,route=scene(qt_application)
    stop=replace(stop,position=position)
    route=replace(route,diagnostic=diagnostic)
    canvas.set_snapshot(replace(canvas.snapshot,stops=(stop,canvas.snapshot.stops[1]),routes=(route,)))
    records=dict((s.id,p) for s,p in _FrameSurface(canvas)._display_stops((route,),clip=False))
    assert records[10] == position
    canvas.close()


def test_anchor_visibility_ignores_native_stop_outside_high_zoom_view(qt_application):
    canvas,stop,route=scene(qt_application);canvas.zoom=100.
    value=_FrameSurface(canvas)
    assert stop not in tuple(value._visible('stops'))
    assert value._display_stops((route,)) == ((stop,(0.,0.,0.)),)
    canvas._highlight=('stop',stop.id)
    value=_FrameSurface(canvas);image=QImage(400,300,QImage.Format.Format_ARGB32_Premultiplied)
    p=QPainter(image);paint_vector_map(p,value,build_vector_map(value),overlays=False);p.end()
    from map_scale import stop_radius
    ring=image.pixelColor(200,round(150-stop_radius(100.)-4))
    assert ring.red()<100 and ring.blue()>100
    canvas.close()
