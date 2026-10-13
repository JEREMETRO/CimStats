"""Export boundaries: physical sizes and frozen direction-aware real facts."""
from dataclasses import FrozenInstanceError, replace
import pytest
from map_model import MapRoute, MapSnapshot, MapStop, RouteDirection


def source():
    a,b,c=(0.,0.,0.),(100.,0.,100.),(200.,0.,0.)
    route=MapRoute(42,'503E',503,'owner','公司','bus',(1,2,3),((a,b),(b,c)),
        RouteDirection('roundtrip',1),(((a,b),),((b,c),)),(),
        leg_map_length_units=(1024000,2048000),stop_arrival_offsets_ticks=(0,600000000,1800000000))
    snapshot=MapSnapshot(routes=(route,),stops=(MapStop(1,'首',a),MapStop(2,'分界',b),MapStop(3,'末',c)))
    session={'simulation_time':'2013-05-23T23:10:00','lines':[{'对象ID':42,
        '公司标识':'owner','公司名称':'公司','运输制式':'公交','线路名称':'503E',
        '地图里程':3.,'单程时间':5.,'站点数':3,'今日客流':0,'当日发班数':70,
        '每周收入':123.,'每周支出':100.}]}
    return session,snapshot


def test_physical_dimensions_round_once_and_lock_aspect():
    from route_export_model import ExportOptions,measure_output
    assert measure_output(ExportOptions(aspect='A4')).pixels==(3508,2480)
    assert measure_output(ExportOptions()).pixels==(3000,2000)
    assert measure_output(ExportOptions(aspect='A4',orientation='portrait')).pixels==(2480,3508)
    assert measure_output(ExportOptions(width_mm=127.)).pixels==(1500,1000)
    assert measure_output(ExportOptions(height_mm=127.)).pixels==(2250,1500)


@pytest.mark.parametrize('ppi,pixels',[(80,(800,533)),(150,(1500,1000)),(300,(3000,2000)),(600,(6000,4000))])
def test_all_supported_precisions_convert_millimetres_to_pixels(ppi,pixels):
    from route_export_model import ExportOptions,measure_output
    assert measure_output(ExportOptions(ppi=ppi)).pixels==pixels


@pytest.mark.parametrize('kwargs',[{'width_mm':0},{'height_mm':float('nan')},
    {'ppi':96},{'direction':'both'},{'format':'SVG'},{'selected_fields':('fake',)}])
def test_invalid_options_rejected_before_allocation(kwargs):
    from route_export_model import ExportOptions,ExportError
    with pytest.raises(ExportError):ExportOptions(**kwargs)


def test_request_freezes_true_direction_and_retains_full_line_operating_facts():
    from route_export_model import ExportOptions,build_export_request,ALL_FIELDS
    session,snapshot=source()
    request=build_export_request(session,snapshot,42,ExportOptions(direction='up',selected_fields=ALL_FIELDS))
    rows={key:(label,value) for _,_,fields in request.information.sections for key,label,value in fields}
    assert rows['地图里程']==('地图里程（上行）','4 km')
    assert rows['单程时间'][1]=='2 min'
    assert rows['核定速度'][1]=='120 km/h'
    assert rows['今日客流']==('今日客流（全线）','0 人次')
    assert rows['当日发班数']==('当日发班（全线）','70 班')
    assert {s.id for s in request.stops}=={2,3}
    assert request.paths==(snapshot.routes[0].leg_paths[1][0],)
    session['lines'][0]['今日客流']=999
    assert rows['今日客流'][1]=='0 人次'
    with pytest.raises(FrozenInstanceError):request.options.ppi=600


def test_one_way_complete_path_missing_values_and_unambiguous_identity():
    from route_export_model import ExportOptions,build_export_request,ExportError,ALL_FIELDS
    session,snapshot=source()
    route=replace(snapshot.routes[0],direction=RouteDirection('one_way'),depot_paths=())
    snapshot=replace(snapshot,routes=(route,))
    request=build_export_request(session,snapshot,42,ExportOptions(direction='up',include_deadhead=True,selected_fields=ALL_FIELDS))
    assert request.metrics.effective_direction=='whole'
    assert request.paths==route.paths
    assert len(request.stops)==3
    assert dict((key,value) for _,_,fields in request.information.sections for key,_,value in fields)['平均客流']=='—'
    with pytest.raises(ExportError):build_export_request(session,replace(snapshot,routes=(route,route)),42,ExportOptions())


def test_saved_depot_segments_select_only_correct_direction_without_connecting_gaps():
    from route_export_model import ExportOptions,build_export_request
    session,snapshot=source()
    outbound=(((0.,0.,-20.),(0.,0.,-10.)),((0.,0.,-10.),(0.,0.,0.)))
    inbound=(((200.,0.,0.),(200.,0.,-10.)),((200.,0.,-10.),(200.,0.,-20.)))
    route=replace(snapshot.routes[0],depot_paths=outbound+inbound,depot_leg_paths=(outbound,inbound),
        depot_id=123,depot_name='真实车库',depot_position=(10.,0.,-30.),depot_map_length_units=(10240,20480))
    snapshot=replace(snapshot,routes=(route,))
    down=build_export_request(session,snapshot,42,ExportOptions(direction='down',include_deadhead=True))
    up=build_export_request(session,snapshot,42,ExportOptions(direction='up',include_deadhead=True))
    assert down.paths==route.leg_paths[0]+outbound
    assert up.paths==route.leg_paths[1]+inbound
    assert up.depots[0].position==(10.,0.,-30.)


def test_legacy_flat_depot_paths_are_not_guessed_into_directions():
    from route_export_model import ExportOptions,build_export_request,ExportError
    session,snapshot=source()
    route=replace(snapshot.routes[0],depot_paths=(((0.,0.,-20.),(0.,0.,0.)),((200.,0.,0.),(200.,0.,-20.))))
    with pytest.raises(ExportError):build_export_request(session,replace(snapshot,routes=(route,)),42,
        ExportOptions(direction='up',include_deadhead=True))


def test_confirmed_unnamed_depot_reuses_the_existing_line_garage_display_name():
    from route_export_model import ExportOptions,build_export_request
    session,snapshot=source();session['lines'][0]['线路车库']='八连交通集团公交车库12'
    route=replace(snapshot.routes[0],depot_id=123,depot_name='',depot_position=(10.,0.,-30.))
    req=build_export_request(session,replace(snapshot,routes=(route,)),42,ExportOptions(show_depot_names=True))
    assert req.depots[0].name=='八连交通集团公交车库12'
    assert req.depots[0].position==(10.,0.,-30.)
    unknown=build_export_request(session,snapshot,42,ExportOptions(show_depot_names=True))
    assert unknown.depots==()
