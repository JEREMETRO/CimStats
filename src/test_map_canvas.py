"""Map canvas behavior using explicit synthetic metre geometry (no save edits)."""
from dataclasses import replace
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtGui import QImage, QWheelEvent
from PySide6.QtWidgets import QApplication
from map_model import (MapSnapshot, MapRoad, MapLane, MapBuilding, MapStop, MapRoute, RouteDirection, GroupCount,
                       MapJunction, MapJunctionConnection)
from map_canvas import MapCanvas, MAP_BACKGROUND

P = ((0., 0., 0.), (100., 0., 0.))
Q = ((100., 0., 0.), (100., 0., 100.))

@pytest.fixture
def canvas(qt_application):
    w = MapCanvas()
    w.resize(960, 680)
    w.set_snapshot(MapSnapshot(
        roads=(MapRoad(1, 'road', '道路', (P,)),),
        buildings=(MapBuilding(3, 'house', '市政厅', (30., 0., 30.),
            ((20.,0.,20.), (40.,0.,20.), (40.,0.,40.), (20.,0.,40.))),),
        stops=(MapStop(10, '东站', P[0]), MapStop(11, '北站', Q[-1])),
        routes=(MapRoute(7, '中心线', 12, 'a', '公司', 'bus', (10,11), (P,Q),
                        RouteDirection('roundtrip', 1), ((P,), (Q,))),),
        bounds=(0.,0.,100.,100.)))
    w.show()
    qt_application.processEvents()
    yield w
    w.close()

def test_options_and_snapshot_update_preserve_navigation(canvas):
    canvas.zoom_in()
    old = (canvas.center, canvas.zoom)
    canvas.set_options(routes=False, stop_names=False)
    canvas.set_snapshot(replace(canvas.snapshot, routes=()))
    assert (canvas.center, canvas.zoom) == old
    canvas.reset_view()
    assert canvas.center == (50.,50.)

def test_search_focus_and_export_are_actual_records(canvas, tmp_path):
    assert [(r.kind, r.id) for r in canvas.search('12')] == [('route',7)]
    assert [(r.kind, r.id) for r in canvas.search('市政')] == [('building',3)]
    assert canvas.search('不存在') == []
    canvas.focus_result(canvas.search('东站')[0])
    assert canvas.center == (0.,0.)
    output = tmp_path / 'map.png'
    assert canvas.export_image(output)
    image = QImage(str(output))
    assert not image.isNull() and image.width() == 960

def test_drag_and_zoom_emit_view_changes(canvas):
    spy = QSignalSpy(canvas.view_changed)
    old = canvas.center
    QTest.mousePress(canvas, Qt.LeftButton, pos=QPoint(400,300))
    QTest.mouseMove(canvas, QPoint(460,340))
    QTest.mouseRelease(canvas, Qt.LeftButton, pos=QPoint(460,340))
    assert canvas.center != old
    canvas.zoom_in()
    assert spy.count() >= 2

@pytest.mark.parametrize('kind', ['oneway','loop','unknown','one_way','circular'])
def test_non_roundtrip_direction_keeps_all_geometry(canvas, kind):
    route = replace(canvas.snapshot.routes[0], direction=RouteDirection(kind,1))
    for direction in ('whole','up','down'):
        canvas.set_options(direction=direction)
        assert canvas.route_paths(route) == (P,Q)

def test_roundtrip_selects_real_legs_and_missing_paths_never_connect(canvas):
    route = canvas.snapshot.routes[0]
    canvas.set_options(direction='up')
    assert canvas.route_paths(route) == (Q,)
    canvas.set_options(direction='down')
    assert canvas.route_paths(route) == (P,)
    assert canvas.route_paths(replace(route, paths=(), leg_paths=())) == ()

def test_route_and_building_colors_reach_painted_pixels(canvas):
    canvas.set_options(roads=False, routes=False, stops=False, stop_names=False,
                       line_numbers=False, building_colors={3:'#cc9988'})
    image = canvas.grab().toImage()
    p = canvas.world_to_screen((30.,30.)).toPoint()
    assert image.pixelColor(p).name() == '#cc9988'
    canvas.set_options(buildings=False, routes=True, route_colors={7:'#dd3366'})
    image = canvas.grab().toImage()
    p = canvas.world_to_screen((50.,0.)).toPoint()
    c = image.pixelColor(p)
    assert c.red() > 180 and c.green() < 100

def test_stops_hide_when_all_associated_route_strokes_are_hidden(canvas):
    canvas.set_options(roads=False, buildings=False, routes=False, stops=True,
                       stop_names=False, line_numbers=False)
    image = canvas.grab().toImage()
    assert image.pixelColor(canvas.world_to_screen(P[0]).toPoint()).name() == MAP_BACKGROUND.lower()

def test_geometryless_route_remains_searchable_without_invented_path(canvas):
    route = replace(canvas.snapshot.routes[0], paths=(), leg_paths=())
    canvas.set_snapshot(replace(canvas.snapshot, routes=(route,)))
    assert [(r.kind,r.id) for r in canvas.search('12')] == [('route',7)]
    assert canvas.focus_result(canvas.search('12')[0])
    assert canvas.route_paths(route) == ()

def test_building_social_class_filter_reads_actual_people(canvas):
    building = replace(canvas.snapshot.buildings[0], category='residential',
                       combined_groups=(GroupCount('Student',2),GroupCount('WhiteCollar',0)))
    canvas.set_snapshot(replace(canvas.snapshot, buildings=(building,)))
    canvas.set_options(roads=False, routes=False, stops=False, stop_names=False,
                       building_classes={'Student'}, building_uses={'residential'},
                       building_colors={3:'#cc9988'})
    p = canvas.world_to_screen((30.,30.)).toPoint()
    assert canvas.grab().toImage().pixelColor(p).name() == '#cc9988'
    canvas.set_options(building_classes={'WhiteCollar'})
    assert canvas.grab().toImage().pixelColor(p).name() != '#cc9988'

def test_real_path_gaps_and_depot_toggle_reach_pixels(canvas):
    route = replace(canvas.snapshot.routes[0], paths=(
        ((0.,0.,50.),(30.,0.,50.)), ((70.,0.,50.),(100.,0.,50.))),
        depot_paths=(((0.,0.,70.),(100.,0.,70.)),))
    canvas.set_snapshot(replace(canvas.snapshot,routes=(route,)))
    canvas.set_options(roads=False,buildings=False,stops=False,stop_names=False,
                       line_numbers=False,route_colors={7:'#dd3366'})
    image = canvas.grab().toImage()
    gap = canvas.world_to_screen((50.,50.)).toPoint()
    depot = canvas.world_to_screen((20.,70.)).toPoint()
    assert image.pixelColor(gap).name() == MAP_BACKGROUND.lower()
    assert image.pixelColor(depot).name() == MAP_BACKGROUND.lower()
    canvas.set_options(deadhead=True)
    image = canvas.grab().toImage()
    assert any(image.pixelColor(depot.x()+dx,depot.y()).name() != MAP_BACKGROUND.lower() for dx in range(-12,13))

def test_viewport_index_excludes_distant_geometry(canvas):
    far = MapBuilding(99,'house','远建筑',(10000.,0.,10000.),
                      ((9990.,0.,9990.),(10010.,0.,9990.),(10010.,0.,10010.)))
    canvas.set_snapshot(replace(canvas.snapshot,buildings=canvas.snapshot.buildings+(far,)))
    assert [b.id for b in canvas._visible('buildings')] == [3]

def test_empty_layer_modes_hides_route_ink_but_preserves_query_records(canvas):
    canvas.set_options(roads=False, buildings=False, stops=False, stop_names=False,
                       line_numbers=False, layer_modes=set())
    p = canvas.world_to_screen((50.,0.)).toPoint()
    assert canvas.grab().toImage().pixelColor(p).name() == MAP_BACKGROUND.lower()
    assert [(r.kind,r.id) for r in canvas.search('12')] == [('route',7)]

def test_unknown_and_transport_class_buildings_remain_visible(canvas):
    canvas.set_snapshot(replace(canvas.snapshot,buildings=(replace(canvas.snapshot.buildings[0],category='transport'),)))
    canvas.set_options(roads=False, routes=False, stops=False, stop_names=False,
                       building_classes={'transport'},building_colors={3:'#cc9988'})
    assert canvas.grab().toImage().pixelColor(canvas.world_to_screen((30.,30.)).toPoint()).name() == '#cc9988'

def test_number_label_is_not_repeated_for_every_real_path_segment(canvas):
    paths=tuple(((10.,0.,float(z)),(90.,0.,float(z))) for z in range(5,100,5))
    route=replace(canvas.snapshot.routes[0],paths=paths)
    canvas.set_snapshot(replace(canvas.snapshot,routes=(route,)))
    canvas.set_options(roads=False,buildings=False,stops=False,stop_names=False,
                       line_numbers=True,route_colors={7:'#dd3366'})
    image=canvas.grab().toImage()
    # One number has a small text halo; segment repetition creates many halos.
    whites=sum(image.pixelColor(x,y).red()>248 and image.pixelColor(x,y).green()>248
               for x in range(250,810) for y in range(50,640))
    assert 30 < whites < 2000

def test_road_class_visibility_uses_real_lane_and_asset_flags(canvas):
    road=replace(canvas.snapshot.roads[0],road_class='ordinary',lanes_a=1,lanes_b=1,express=False)
    canvas.set_snapshot(replace(canvas.snapshot,roads=(road,)))
    canvas.set_options(routes=False,buildings=False,stops=False,stop_names=False,
                       road_levels={'local'})
    p=canvas.world_to_screen((50.,0.)).toPoint()
    assert canvas.grab().toImage().pixelColor(p).name() != MAP_BACKGROUND.lower()
    canvas.set_options(road_levels={'express'})
    assert canvas.grab().toImage().pixelColor(p).name() == MAP_BACKGROUND.lower()

def test_many_shared_routes_use_only_slight_screen_offset(canvas):
    routes=tuple(replace(canvas.snapshot.routes[0],id=i,paths=(P,),stop_ids=()) for i in range(20))
    canvas.set_snapshot(replace(canvas.snapshot,routes=routes))
    canvas.set_options(roads=False,buildings=False,stops=False,stop_names=False,line_numbers=False,
                       route_colors={i:('#dd3366' if i%2 else '#1166cc') for i in range(20)})
    p=canvas.world_to_screen((50.,0.)).toPoint()
    image=canvas.grab().toImage()
    assert image.pixelColor(p.x(),p.y()+16).name() == MAP_BACKGROUND.lower()

def test_drag_preview_and_final_frame_keep_geometry_at_current_coordinates(canvas):
    canvas.set_options(roads=False,buildings=False,stops=False,stop_names=False,line_numbers=False,
                       route_colors={7:'#dd3366'})
    canvas.grab()
    QTest.mousePress(canvas,Qt.LeftButton,pos=QPoint(400,300))
    QTest.mouseMove(canvas,QPoint(460,260))
    p=canvas.world_to_screen((50.,0.)).toPoint()
    assert canvas.grab().toImage().pixelColor(p).red()>180
    QTest.mouseRelease(canvas,Qt.LeftButton,pos=QPoint(460,260))
    assert canvas.grab().toImage().pixelColor(p).green()<100

def test_wheel_zoom_keeps_pointer_world_location_fixed(canvas):
    anchor=QPointF(300,220)
    before=canvas.screen_to_world(anchor)
    old_zoom=canvas.zoom
    event=QWheelEvent(anchor,QPointF(canvas.mapToGlobal(anchor.toPoint())),QPoint(),QPoint(0,120),
                      Qt.NoButton,Qt.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
    QApplication.sendEvent(canvas,event)
    assert canvas.zoom>old_zoom
    assert canvas.screen_to_world(anchor)==pytest.approx(before)
    QTest.qWait(120)

@pytest.mark.parametrize('metadata,level',[
    ({'road_class':'expressway','lanes_a':2,'lanes_b':0},'express'),
    ({'road_class':'avenue','lanes_a':2,'lanes_b':0},'arterial'),
    ({'road_class':'ordinary','lanes_a':3,'lanes_b':3},'arterial'),
    ({'road_class':'ordinary','lanes_a':2,'lanes_b':2},'secondary'),
    ({'road_class':'ordinary','lanes_a':2,'lanes_b':0},'local'),
    ({'road_class':'pedestrian','lanes_a':1,'lanes_b':1},'pedestrian'),
    ({'road_class':'rail','lanes_a':1,'lanes_b':1},'track'),
    ({'road_class':'unknown','asset_id':'unclassified','lanes_a':4,'lanes_b':4},'unknown')])
def test_road_grade_respects_actual_class_before_declared_lane_total(canvas,metadata,level):
    assert canvas.road_level(replace(canvas.snapshot.roads[0],**metadata)) == level

@pytest.mark.parametrize('number,name,label',[(5029,'502X','502X'),(5003,'5P（早高峰）','5P（早高峰）'),
    (502,'E','502E'),(912,'X','912X'),(12,'中心线','12路·中心线')])
def test_route_labels_use_serialized_code_instead_of_hidden_internal_number(canvas,number,name,label):
    route=replace(canvas.snapshot.routes[0],number=number,name=name)
    canvas.set_snapshot(replace(canvas.snapshot,routes=(route,)))
    assert canvas.route_label(route) == label
    assert canvas.search(label)[0].id == route.id

def test_ground_road_fills_join_without_later_road_shell_cutting_junction(canvas):
    horizontal=replace(canvas.snapshot.roads[0],road_class='ordinary',lanes_a=1,lanes_b=1)
    vertical=replace(horizontal,id=2,paths=(((50.,0.,-20.),(50.,0.,20.)),))
    canvas.set_snapshot(replace(canvas.snapshot,roads=(horizontal,vertical)))
    canvas.set_options(routes=False,buildings=False,stops=False,stop_names=False,line_numbers=False)
    p=canvas.world_to_screen((50.,0.)).toPoint()
    image=canvas.grab().toImage()
    assert image.pixelColor(p.x()+3,p.y()).red()>245

def test_junction_draws_only_saved_lane_curve_without_straight_gap_fill(canvas):
    road=replace(canvas.snapshot.roads[0],road_class='ordinary',lanes_a=1,lanes_b=1,
                 paths=(((0.,0.,50.),(40.,0.,50.)),))
    other=replace(road,id=2,paths=(((60.,0.,50.),(100.,0.,50.)),))
    curve=((40.,0.,50.),(45.,0.,55.),(50.,0.,55.),(55.,0.,55.),(60.,0.,50.))
    connection=MapJunctionConnection(100,1,2,0,0,1,(curve,))
    junction=MapJunction(10,(50.,0.,50.),(1,2),(connection,))
    canvas.set_snapshot(replace(canvas.snapshot,roads=(road,other),junctions=(junction,)))
    canvas.set_options(routes=False,buildings=False,stops=False,stop_names=False,line_numbers=False)
    image=canvas.grab().toImage()
    saved=canvas.world_to_screen((50.,55.)).toPoint()
    invented=canvas.world_to_screen((50.,50.)).toPoint()
    assert image.pixelColor(saved).red()>245
    assert image.pixelColor(invented).name() == MAP_BACKGROUND.lower()
    assert image.pixelColor(saved.x(),saved.y()+3).name() == MAP_BACKGROUND.lower()
    canvas.set_options(road_levels=set())
    assert canvas.grab().toImage().pixelColor(saved).name() == MAP_BACKGROUND.lower()

def test_actual_legend_color_is_in_canvas_and_export_without_changing_view(canvas,tmp_path):
    old=(canvas.center,canvas.zoom)
    canvas.set_options(roads=False,buildings=False,routes=False,stops=False,stop_names=False,
                       legend_items=(('公交','#dd3366'),('公司甲','#1166cc')))
    assert (canvas.center,canvas.zoom)==old
    image=canvas.grab().toImage()
    # Legend uses the band right of the reserved scale and above bottom edge.
    assert any(image.pixelColor(x,y).name()=='#dd3366' for x in range(185,235) for y in range(620,675))
    output=tmp_path/'legend.png'
    assert canvas.export_image(output)
    exported=QImage(str(output))
    assert any(exported.pixelColor(x,y).name()=='#dd3366' for x in range(185,235) for y in range(620,675))
    canvas.set_options(legend_items=())
    assert not any(canvas.grab().toImage().pixelColor(x,y).name()=='#dd3366' for x in range(185,235) for y in range(620,675))

@pytest.mark.parametrize('selection',['routes_off','modes_empty','manual_empty','filtered_out','missing_paths'])
def test_station_and_name_require_a_visible_line_with_operating_geometry(canvas,selection):
    canvas.set_options(roads=False,buildings=False,stops=True,stop_names=True,line_numbers=False)
    p=canvas.world_to_screen(P[0]).toPoint()
    if selection=='routes_off':
        canvas.set_options(routes=False)
    elif selection=='modes_empty':
        canvas.set_options(layer_modes=set())
    elif selection in ('manual_empty','filtered_out'):
        from map_query import MapQuery
        state={'manual_line_ids':set()} if selection=='manual_empty' else {'modes':{'tram'}}
        canvas.set_snapshot(MapQuery(canvas.snapshot).select(state).snapshot)
    else:
        canvas.set_snapshot(replace(canvas.snapshot,routes=(replace(canvas.snapshot.routes[0],paths=(),leg_paths=()),)))
    image=canvas.grab().toImage()
    assert image.pixelColor(p).name()==MAP_BACKGROUND.lower()
    assert all(image.pixelColor(x,y).name()==MAP_BACKGROUND.lower() for x in range(p.x()+6,p.x()+60) for y in range(p.y()-13,p.y()+12))

def test_shared_station_survives_one_line_hidden_and_station_toggle_is_independent(canvas):
    bus=canvas.snapshot.routes[0]
    tram=replace(bus,id=8,mode='tram')
    canvas.set_snapshot(replace(canvas.snapshot,routes=(bus,tram)))
    canvas.set_options(roads=False,buildings=False,stop_names=False,line_numbers=False,layer_modes={'tram'})
    p=canvas.world_to_screen(P[0]).toPoint()
    assert canvas.grab().toImage().pixelColor(p).name()=='#ffffff'
    canvas.set_options(stops=False)
    assert canvas.grab().toImage().pixelColor(p).name()!='#ffffff'

def test_station_toggle_pauses_name_paint_and_preserves_name_selection(canvas,tmp_path):
    canvas.set_options(roads=False,buildings=False,line_numbers=False,stops=True,stop_names=True)
    p=canvas.world_to_screen(Q[-1]).toPoint()
    def name_pixels(image):
        return tuple(image.pixelColor(x,y).rgba()
                     for x in range(p.x()+6,p.x()+90) for y in range(p.y()-14,p.y()+14))
    visible=name_pixels(canvas.grab().toImage())
    canvas.set_options(stop_names=False)
    assert visible!=name_pixels(canvas.grab().toImage())  # Name actually painted.
    canvas.set_options(stops=False)
    hidden_baseline=name_pixels(canvas.grab().toImage())
    canvas.set_options(stop_names=True)
    assert canvas.options['stop_names'] is True
    assert name_pixels(canvas.grab().toImage())==hidden_baseline
    output=tmp_path/'hidden-station-names.png'
    assert canvas.export_image(output)
    assert name_pixels(QImage(str(output)))==hidden_baseline
    canvas.set_options(stops=True)
    assert canvas.options['stop_names'] is True
    assert name_pixels(canvas.grab().toImage())==visible

@pytest.mark.parametrize('direction,hidden', [('up',10),('down',11)])
def test_direction_hides_other_leg_station_in_actual_paint_and_keeps_terminal(canvas,direction,hidden):
    terminal=MapStop(12,'终点',(100.,0.,0.))
    route=replace(canvas.snapshot.routes[0],stop_ids=(10,12,11))
    canvas.set_snapshot(replace(canvas.snapshot,routes=(route,),stops=canvas.snapshot.stops+(terminal,)))
    canvas.set_options(roads=False,buildings=False,line_numbers=False,stop_names=False,direction=direction)
    image=canvas.grab().toImage()
    stop=next(s for s in canvas.snapshot.stops if s.id==hidden)
    assert image.pixelColor(canvas.world_to_screen(stop.position).toPoint()).name()==MAP_BACKGROUND.lower()
    assert image.pixelColor(canvas.world_to_screen(terminal.position).toPoint()).name()=='#ffffff'

def test_junction_lane_symbol_scales_with_observed_road_width_and_zoom(canvas):
    road=replace(canvas.snapshot.roads[0],road_class='ordinary',lanes_a=2,lanes_b=2,width=20.,
                 paths=(((0.,0.,50.),(40.,0.,50.)),))
    other=replace(road,id=2,paths=(((60.,0.,50.),(100.,0.,50.)),))
    curve=((40.,0.,50.),(45.,0.,55.),(55.,0.,55.),(60.,0.,50.))
    junction=MapJunction(10,(50.,0.,50.),(1,2),(MapJunctionConnection(100,1,2,0,0,1,(curve,)),))
    canvas.set_snapshot(replace(canvas.snapshot,roads=(road,other),junctions=(junction,)))
    canvas.set_options(routes=False,buildings=False,stops=False,stop_names=False,line_numbers=False)
    p=canvas.world_to_screen((50.,55.)).toPoint()
    image=canvas.grab().toImage()
    assert image.pixelColor(p.x(),p.y()+4).red()>245
    assert image.pixelColor(p.x(),p.y()+9).name()==MAP_BACKGROUND.lower()  # Individual lane, not full road.

def test_continuous_strokes_merge_only_existing_exact_three_dimensional_endpoints():
    from map_canvas import continuous_paths
    other_height=((100.,5.,100.),(200.,5.,100.))
    gap=((300.,0.,100.),(400.,0.,100.))
    assert continuous_paths((P,Q,other_height,gap)) == ((P[0],P[1],Q[1]),other_height,gap)
    assert continuous_paths((P,(),Q)) == (P,Q)

def test_fragment_screen_offset_converges_to_real_endpoint_without_connecting_gap(canvas):
    polygon=canvas._polyline(P,2.)
    assert polygon[0] == canvas.world_to_screen(P[0])
    assert polygon[-1] == canvas.world_to_screen(P[-1])
    assert any(abs(p.y()-canvas.world_to_screen(P[0]).y())>1 for p in list(polygon)[1:-1])


@pytest.mark.parametrize('structure',['bridge','tunnel'])
def test_bridge_and_tunnel_have_open_road_ends_instead_of_capsules(canvas,structure):
    road=replace(canvas.snapshot.roads[0],road_class='ordinary',width=12.,**{structure:True})
    canvas.set_snapshot(replace(canvas.snapshot,roads=(road,)))
    canvas.set_options(routes=False,buildings=False,stops=False,stop_names=False,line_numbers=False)
    start=canvas.world_to_screen(P[0]).toPoint()
    image=canvas.grab().toImage()
    assert image.pixelColor(start.x()-3,start.y()).name()==MAP_BACKGROUND.lower()
    assert image.pixelColor(start.x()+3,start.y()).name()!=MAP_BACKGROUND.lower()


def test_tunnel_road_body_is_continuous_while_only_edges_are_dashed(canvas):
    road=replace(canvas.snapshot.roads[0],road_class='ordinary',width=12.,tunnel=True)
    canvas.set_snapshot(replace(canvas.snapshot,roads=(road,)))
    canvas.set_options(routes=False,buildings=False,stops=False,stop_names=False,line_numbers=False)
    image=canvas.grab().toImage()
    start,end=canvas.world_to_screen(P[0]).toPoint(),canvas.world_to_screen(P[-1]).toPoint()
    assert all(image.pixelColor(x,start.y()).name()!=MAP_BACKGROUND.lower() for x in range(start.x()+3,end.x()-3))


def test_route_decorations_wait_until_all_route_bodies_are_painted(canvas,monkeypatch):
    from PySide6.QtGui import QPainter
    first=replace(canvas.snapshot.routes[0],paths=(P,),leg_paths=())
    second=replace(first,id=8,paths=(Q,))
    canvas.set_snapshot(replace(canvas.snapshot,routes=(first,second)))
    canvas.set_options(roads=False,buildings=False,stops=False,stop_names=False,line_numbers=True,
                       route_colors={7:'#2266ff',8:'#ee3366'})
    image=QImage(canvas.size(),QImage.Format.Format_ARGB32)
    sampled=[]
    point=canvas.world_to_screen((100.,50.)).toPoint()
    def sample_label(*args):
        sampled.append(image.pixelColor(point).name())
        return True
    monkeypatch.setattr(canvas,'_label',sample_label)
    painter=QPainter(image)
    canvas._paint(painter)
    painter.end()
    assert sampled and all(color=='#ee3366' for color in sampled)


def test_bus_routes_do_not_add_direction_arrows(canvas,monkeypatch):
    arrows=[]
    if hasattr(canvas,'_arrows'):
        monkeypatch.setattr(canvas,'_arrows',lambda *args:arrows.append(args))
    canvas.set_options(roads=False,buildings=False,stops=False,stop_names=False,line_numbers=False)
    image=canvas.grab().toImage()
    assert not arrows
    start,end=canvas.world_to_screen(P[0]).toPoint(),canvas.world_to_screen(P[-1]).toPoint()
    assert all(image.pixelColor(x,start.y()+3).name()==MAP_BACKGROUND.lower() for x in range(start.x()+10,end.x()-10))


@pytest.mark.parametrize('backward',[False,True])
def test_saved_lane_connection_surfaces_meet_full_road_edges_without_a_neck(canvas,backward):
    lanes=(MapLane(0,0x1000101,1,1.5),MapLane(1,0x1000201 if backward else 0x1000101,1,-1.5))
    road=replace(canvas.snapshot.roads[0],road_class='ordinary',width=14.,lanes_a=2,lanes_b=0,lanes=lanes,
                 paths=(((0.,0.,50.),(40.,0.,50.)),))
    other=replace(road,id=2,paths=(((60.,0.,50.),(100.,0.,50.)),))
    connections=[]
    for i,z in enumerate((48.5,51.5)):
        curve=((40.,0.,z),(50.,0.,z),(60.,0.,z))
        reverse=backward and i==1
        connections.append(MapJunctionConnection(100+i,2 if reverse else 1,1 if reverse else 2,i,i,0x1000000,
                           (tuple(reversed(curve)) if reverse else curve,)))
    connections=tuple(connections)
    junction=MapJunction(10,(50.,0.,50.),(1,2),connections)
    canvas.set_snapshot(replace(canvas.snapshot,roads=(road,other),junctions=(junction,)))
    canvas.center=(50.,50.);canvas.zoom=1.
    canvas.set_options(routes=False,buildings=False,stops=False,stop_names=False,line_numbers=False)
    image=canvas.grab().toImage()
    assert all(image.pixelColor(canvas.world_to_screen((50.,z)).toPoint()).red()>245 for z in range(44,57))
    assert image.pixelColor(canvas.world_to_screen((50.,59.)).toPoint()).name()==MAP_BACKGROUND.lower()


def test_mode_width_changes_only_matching_route_symbol_in_actual_paint(canvas):
    canvas.set_options(roads=False,buildings=False,stops=False,stop_names=False,line_numbers=False,
                       mode_widths={'bus':8.},route_colors={7:'#2266ff'})
    p=canvas.world_to_screen((50.,0.)).toPoint()
    assert canvas.grab().toImage().pixelColor(p.x(),p.y()+3).name()=='#2266ff'
    canvas.set_options(mode_widths={'tram':8.})
    assert canvas.grab().toImage().pixelColor(p.x(),p.y()+3).name()==MAP_BACKGROUND.lower()


@pytest.mark.parametrize('kind,dashed',[('roundtrip',True),('loop',False),('oneway',False)])
def test_optional_direction_style_dashes_only_whole_roundtrip_up(canvas,kind,dashed):
    route=replace(canvas.snapshot.routes[0],direction=RouteDirection(kind,1))
    canvas.set_snapshot(replace(canvas.snapshot,routes=(route,)))
    canvas.set_options(roads=False,buildings=False,stops=False,stop_names=False,line_numbers=False,
                       direction='whole',distinguish_directions=True,route_colors={7:'#2266ff'})
    image=canvas.grab().toImage()
    start,end=canvas.world_to_screen(Q[0]).toPoint(),canvas.world_to_screen(Q[-1]).toPoint()
    colors=[image.pixelColor(start.x(),y).name() for y in range(end.y()+5,start.y()-5)]
    assert (MAP_BACKGROUND.lower() in colors)==dashed
    assert '#2266ff' in colors
    canvas.set_options(direction='up')
    image=canvas.grab().toImage()
    assert all(image.pixelColor(start.x(),y).name()=='#2266ff' for y in range(end.y()+5,start.y()-5))


def test_mixed_road_connection_color_transitions_from_actual_source_to_target(canvas):
    source=replace(canvas.snapshot.roads[0],road_class='expressway',express=True,width=14.,lanes_a=1,lanes_b=1,
                   paths=(((0.,0.,50.),(20.,0.,50.)),))
    target=replace(source,id=2,road_class='ordinary',express=False,paths=(((80.,0.,50.),(100.,0.,50.)),))
    curve=((20.,0.,50.),(80.,0.,50.))
    junction=MapJunction(10,(50.,0.,50.),(1,2),(MapJunctionConnection(100,1,2,0,0,0x1000000,(curve,)),))
    canvas.set_snapshot(replace(canvas.snapshot,roads=(source,target),junctions=(junction,)))
    canvas.center=(50.,50.);canvas.zoom=1.
    canvas.set_options(routes=False,buildings=False,stops=False,stop_names=False,line_numbers=False)
    image=canvas.grab().toImage()
    assert image.pixelColor(canvas.world_to_screen((40.,50.)).toPoint()).blue()<220
    assert image.pixelColor(canvas.world_to_screen((60.,50.)).toPoint()).blue()>220


def test_whole_direction_styles_remain_distinct_on_exact_reverse_shared_geometry(canvas):
    reverse=tuple(reversed(P))
    route=replace(canvas.snapshot.routes[0],paths=(P,reverse),leg_paths=((P,),(reverse,)))
    canvas.set_snapshot(replace(canvas.snapshot,routes=(route,)))
    canvas.set_options(roads=False,buildings=False,stops=False,stop_names=False,line_numbers=False,
                       direction='whole',distinguish_directions=True,mode_widths={'bus':5.},route_colors={7:'#2266ff'})
    image=canvas.grab().toImage()
    start,end=canvas.world_to_screen(P[0]).toPoint(),canvas.world_to_screen(P[-1]).toPoint()
    colors=[image.pixelColor(x,start.y()+3) for x in range(start.x()+20,end.x()-20)]
    assert any(color.name()==MAP_BACKGROUND.lower() for color in colors)
    assert any(color.blue()>240 and color.red()<180 for color in colors)

