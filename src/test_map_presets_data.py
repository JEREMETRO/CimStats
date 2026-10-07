"""Behavior contracts for native associations, calendar service and whole-line facts."""
from dataclasses import asdict, replace
from datetime import datetime
import json
import pytest
import map_model as model
import map_geometry

T = 10_000_000
H = 3600*T

def native_route(tables, active=True, complete=True):
    return replace(model.MapRoute(1,'same',1,'company-a','same','bus',(),()),
                   service=model.RouteService(active,complete,tuple(tables)))

def table(start, end, rows, mask=2, interval=H):
    return model.ServiceTimetable(mask,start,end,interval,tuple(rows))

def test_native_associations_keep_unknown_empty_null_and_dangling_distinct():
    data={'roads':{},'buildings':[
        {'id':1,'position':[0,0,0]},
        {'id':2,'position':[0,0,0],'service_lines':{'known':True,'route_ids':[],'unresolved_refs':[],'source':'saved'}},
        {'id':3,'position':[0,0,0],'service_lines':{'known':True,'route_ids':[12,12,13],'unresolved_refs':[99,None,99],'source':'saved'}}]}
    snapshot=map_geometry.snapshot_from_data(data)
    unknown,empty,refs=snapshot.buildings
    assert unknown.service_lines.known is False
    assert empty.service_lines.known is True and empty.service_lines.route_ids==()
    assert refs.service_lines.route_ids==(12,13)
    assert refs.service_lines.unresolved_refs==(99,None,99)
    assert map_geometry._decode_snapshot(json.loads(json.dumps(asdict(snapshot))))==snapshot

def test_service_snapshot_preserves_unfolded_native_rows_and_unknown():
    raw={'roads':{},'lines':[{'id':1,'service':{'active':True,'complete':True,'timetables':[
        {'active_days':2,'start_tick':23*H,'end_tick':H,'interval_tick':H,'departure_ticks':[23*H,24*H,25*H]}]}}]}
    snapshot=map_geometry.snapshot_from_data(raw)
    assert snapshot.routes[0].service.timetables[0].departure_ticks==(23*H,24*H,25*H)
    assert map_geometry._decode_snapshot(json.loads(json.dumps(asdict(snapshot))))==snapshot

@pytest.mark.parametrize('start,end,want',[
    ('2026-10-05T22:59:59',None,False),
    ('2026-10-05T23:30:00',None,True),
    ('2026-10-06T00:30:00',None,True),
    ('2026-10-06T01:00:00',None,True),
    ('2026-10-06T01:00:00.000001',None,False),
    ('2026-10-06T01:00:00','2026-10-06T02:00:00',True),
    ('2026-10-05T22:00:00','2026-10-05T23:00:00',False),
    ('2026-10-06T23:30:00',None,False),
    ('2026-10-04T23:30:00',None,False),
])
def test_cross_midnight_windows_follow_native_running_day_and_last_event(start,end,want):
    from map_service_time import route_operates
    route=native_route([table(23*H,H,[23*H,24*H,25*H])])
    assert route_operates({},1,datetime.fromisoformat(start),datetime.fromisoformat(end) if end else None,route=route) is want

def test_multiple_templates_keep_shutdown_gaps_and_use_last_row_not_template_end():
    from map_service_time import route_operates
    route=native_route([table(6*H,10*H,[6*H,7*H,8*H],interval=2*H),table(18*H,20*H,[18*H,20*H],interval=2*H)])
    assert route_operates({},1,datetime(2026,10,5,7,30),route=route) is True
    assert route_operates({},1,datetime(2026,10,5,8,1),route=route) is False
    assert route_operates({},1,datetime(2026,10,5,15),route=route) is False
    assert route_operates({},1,datetime(2026,10,5,17),datetime(2026,10,5,19),route=route) is True

def test_empty_singleton_disabled_and_unknown_are_not_guessed():
    from map_service_time import route_operates
    now=datetime(2026,10,5,6)
    single=native_route([table(6*H,6*H,[6*H])])
    assert route_operates({},1,now,route=single) is True
    assert route_operates({},1,datetime(2026,10,5,6,1),route=single) is False
    assert route_operates({},1,now,route=native_route([table(6*H,6*H,[],interval=0)])) is False
    assert route_operates({},1,now,route=native_route([table(6*H,7*H,[6*H,7*H])],active=False)) is False
    assert route_operates({},1,now,route=native_route([],complete=False)) is False
    assert route_operates({},1,now,route=native_route([table(6*H,7*H,[6*H,7*H])],active=None)) is None
    assert route_operates({},1,now,route=native_route([table(6*H,7*H,[6*H,None])])) is None
    assert route_operates({},1,now,route=native_route([table(6*H,7*H,[6*H],mask=None)])) is None
    assert route_operates({},1,now) is None

def test_range_validation_does_not_reinterpret_empty_as_instant():
    from map_service_time import route_operates
    route=native_route([]);now=datetime(2026,10,5)
    with pytest.raises(ValueError):route_operates({},1,now,now,route=route)
    with pytest.raises(ValueError):route_operates({},1,now,now.replace(tzinfo=__import__('datetime').timezone.utc),route=route)

def test_whole_line_facts_preserve_zero_unknown_and_previous_day_unfolded_departures():
    from map_line_facts import line_facts
    session={'simulation_time':'2026-10-06 00:30:00','lines':[{'对象ID':1,'原始字段':{'单程时间_tick':7200*T,'客流_今日':0},
       '时刻表':{'week':{'entries':[{'时刻表序号':1,'发班序号':1,'发班_tick':23*H,'运行日掩码':2},
       {'时刻表序号':1,'发班序号':2,'发班_tick':24*H,'运行日掩码':2},
       {'时刻表序号':1,'发班序号':3,'发班_tick':25*H,'运行日掩码':2}]}}}]}
    facts=line_facts(session,1)
    assert facts.approved_duration_ticks==7200*T
    assert facts.today_passengers==0
    assert facts.scheduled_departures==2
    assert str(facts.simulated_date)=='2026-10-06' and facts.complete
    assert line_facts(session,999).today_passengers is None
    session['lines'][0]['原始字段']['客流_今日']=''
    assert line_facts(session,1).today_passengers is None

def test_geometry_lengths_use_selected_3d_operating_paths_and_actual_depot_only():
    from map_line_facts import geometry_lengths
    route=replace(model.MapRoute(1,'x',1,'a','x','bus',(1,2,1),()),direction=model.RouteDirection('roundtrip',1),
                  leg_paths=(( ((0,0,0),(3000,4000,0)), ),( ((3000,4000,0),(0,0,0)), )),
                  depot_paths=(((0,0,0),(0,0,2000)),))
    assert geometry_lengths(route,'up').operating_km==5
    assert geometry_lengths(route,'both',True).total_km==12
    assert geometry_lengths(route,'down',True).deadhead_km==2
    assert geometry_lengths(replace(route,leg_paths=(),paths=(),diagnostic='missing')).operating_km is None

def test_missing_schedule_and_duplicate_object_ids_never_default_to_zero():
    from map_line_facts import line_facts
    session={'simulation_time':'2026-10-05 06:00:00','lines':[{'对象ID':1,'原始字段':{'单程时间_tick':0,'客流_今日':0}}]}
    assert line_facts(session,1).scheduled_departures is None
    session['lines'][0].update({'时刻表':{},'原始字段':{'时刻表数':1}})
    assert line_facts(session,1).scheduled_departures is None
    session['lines'].append({'对象ID':1,'今日客流':999})
    assert line_facts(session,1).today_passengers is None

def test_calendar_count_deduplicates_presentation_groups_but_keeps_duplicate_departures():
    from map_line_facts import line_facts
    rows=[{'时刻表序号':1,'发班序号':i,'发班_tick':6*H,'运行日掩码':127} for i in (1,2)]
    session={'simulation_time':'2026-10-05 06:00:00','lines':[{'对象ID':1,'原始字段':{'单程时间_tick':0,'客流_今日':0},
        '时刻表':{'weekday':{'entries':rows},'sunday':{'entries':rows}}}]}
    assert line_facts(session,1).scheduled_departures==2
    rows[0]['运行日掩码']=None
    assert line_facts(session,1).scheduled_departures is None

def test_service_long_ranges_sunday_signed_mask_and_ten_nanosecond_terminal():
    from map_service_time import route_operates
    sunday=native_route([table(6*H,7*H,[6*H,7*H],mask=-2147483647)])
    assert route_operates({},1,datetime(2026,10,4,6,30),route=sunday) is True
    assert route_operates({},1,datetime(2026,10,5,6,30),route=sunday) is False
    assert route_operates({},1,datetime(2026,10,5),datetime(2027,1,1),route=sunday) is True
    event=native_route([table(6*H,6*H,[6*H+1])])
    assert route_operates({},1,datetime(2026,10,5,6),route=event) is False
    assert route_operates({},1,datetime(2026,10,5,6),datetime(2026,10,5,6,0,0,1),route=event) is True
    assert route_operates({},1,datetime(2026,10,5,6,0,0,1),route=event) is False

def test_legacy_session_filter_remains_unknown_when_native_enable_flags_are_absent():
    from map_service_time import route_operates
    rows=[{'时刻表序号':1,'发班序号':i,'发班_tick':hour*H,'运行日掩码':2,
           '时刻表原始字段':{'运行日掩码':2,'开始_tick':6*H,'结束_tick':7*H,'间隔_tick':H}} for i,hour in [(1,6),(2,7)]]
    session={'lines':[{'对象ID':1,'时刻表':{'weekday':{'entries':rows}},'原始字段':{}}]}
    now=datetime(2026,10,5,6,30)
    assert route_operates(session,1,now) is None
    session['lines'][0]['原始字段'].update(m_active=True,m_complete=True)
    assert route_operates(session,1,now) is True
    assert route_operates(session,2,now) is None
