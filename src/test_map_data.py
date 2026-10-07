from dataclasses import FrozenInstanceError
import pytest
from map_model import MapBuilding, GroupCount, group_metric


def test_proportion_without_area_and_known_denominator():
    b = MapBuilding(1, '', '', (0, 0, 0), residents=(GroupCount('a', 2), GroupCount('b', 3), GroupCount('unknown', 1)))
    assert group_metric(b, 'a', 'residents', 'proportion') == pytest.approx(1/3)
    assert group_metric(b, 'a', 'residents', 'density') is None
    with pytest.raises(FrozenInstanceError):
        b.id = 2


def test_combined_groups_default_and_zero():
    b = MapBuilding(1, '', '', (0, 0, 0), combined_groups=(GroupCount('a', 0), GroupCount('b', 4)))
    assert group_metric(b, 'a') == 0
    assert group_metric(b, 'a', metric='proportion') == 0
    assert group_metric(b, 'missing') is None
    with pytest.raises(ValueError):
        group_metric(b, 'a', role='invalid')


def test_unknown_count_not_silently_zero():
    b = MapBuilding(1, '', '', (0, 0, 0), residents=(GroupCount('a', 2), GroupCount('b', None)))
    assert group_metric(b, 'b', 'residents') is None
    assert group_metric(b, 'a', 'residents', 'proportion') == 1


def test_direction_open_closed_reverse_and_elevation():
    from map_analysis import infer_direction
    p = ((0.,0.,0.), (200.,0.,0.), (400.,0.,0.))
    legs = (((p[0],p[1]),), ((p[1],p[2]),))
    assert infer_direction(p, legs).kind == 'one_way'
    q = p + ((200.,0.,0.), (0.,0.,0.))
    legs2 = tuple(((a,b),) for a,b in zip(q,q[1:]))
    assert infer_direction(q, legs2).kind == 'roundtrip'
    assert infer_direction(q, legs2).terminal_index == 2
    circle = ((0.,0.,0.), (200.,0.,0.), (200.,0.,200.), (0.,0.,200.), (0.,0.,0.))
    assert infer_direction(circle, tuple(((a,b),) for a,b in zip(circle,circle[1:]))).kind == 'circular'
    bridge = p + ((200.,30.,0.), (0.,30.,0.))
    direction = infer_direction(bridge, tuple(((a,b),) for a,b in zip(bridge,bridge[1:])))
    assert direction.kind == 'one_way'
    assert infer_direction(q, legs2[:-1]).kind == 'unknown'


def test_names_only_disambiguate_local_ties():
    from map_analysis import choose_turnaround_candidate
    candidates = [dict(index=i,score=.8) for i in (1,2,3)]
    cumulative = [0,100,200,300,400]
    assert choose_turnaround_candidate(candidates,cumulative,200,['','','','东北转车站E2',''])['index'] == 3
    assert choose_turnaround_candidate(candidates,cumulative,200,['枢纽站','','','','火车站'])['index'] == 2
    assert choose_turnaround_candidate([candidates[1]],cumulative,200,['','','','地铁站',''])['index'] == 2


def test_population_identity_union():
    from map_geometry import population_groups
    residents = [(1,0),(1,0),(2,1),(3,None)]
    workers = [(1,0),(4,1),(3,None)]
    r,w,c = population_groups(residents, workers, ('a','b'))
    assert dict((v.group,v.count) for v in r) == {'a':1,'b':1,'unknown':1}
    assert dict((v.group,v.count) for v in c) == {'a':1,'b':2,'unknown':1}


def test_crop_keeps_missing_roads_as_disconnected_paths():
    from map_geometry import route_leg
    roads = {1:dict(id=1,curves=[[[0,0,0],[30,0,0],[70,0,0],[100,0,0]]],start=1,end=2),
             3:dict(id=3,curves=[[[200,0,0],[230,0,0],[270,0,0],[300,0,0]]],start=3,end=4)}
    paths, issues = route_leg([dict(id=1,reverse=False,mask=1),dict(id=2,reverse=False,mask=1),dict(id=3,reverse=False,mask=1)],roads,(0,0,0),(300,0,0))
    assert len(paths) == 2
    assert 'missing_road:2' in issues
    assert paths[0][-1] == (100.,0.,0.)
    assert paths[1][0] == (200.,0.,0.)


def test_cancel_before_load_never_creates_cache(tmp_path):
    from map_geometry import MapGeometryService, MapCancelled
    source = tmp_path/'fake.save'
    source.write_bytes(b'invalid')
    service = MapGeometryService(cache_dir=tmp_path/'cache')
    with pytest.raises(MapCancelled):
        service.load(source,cancelled=lambda:True)
    assert not (tmp_path/'cache').exists()


def test_road_class_and_actual_oneway_configuration_are_independent():
    from map_geometry import snapshot_from_data
    road=dict(id=1,curves=[[[0,0,0],[30,0,0],[70,0,0],[100,0,0]]],
              asset_id='avenue',name='avenue',lanes_a=3,lanes_b=0,road_class='avenue',
              one_way=True,sidewalk_left=4.,sidewalk_right=4.,platform_width=8.,
              bus_lane=True,parking_lane=False,shoulder=False,pedestrian=False,
              lanes=[dict(index=0,type_mask=0x1000102,turn_directions=1,offset=3.)])
    snapshot=snapshot_from_data(dict(roads={'1':road}))
    r=snapshot.roads[0]
    assert r.road_class=='avenue' and r.one_way
    assert r.lanes_a==3 and r.lanes_b==0
    assert r.platform_width==8 and r.bus_lane
    from map_geometry import _decode_snapshot
    from dataclasses import asdict
    assert _decode_snapshot(asdict(snapshot))==snapshot
    assert r.lanes[0].offset==3.


def test_reversed_projection_is_diagnosed():
    from map_geometry import route_leg
    roads={1:dict(id=1,curves=[[[0,0,0],[30,0,0],[70,0,0],[100,0,0]]],start=1,end=2)}
    paths,issues=route_leg([dict(id=1,mask=1)],roads,(80,0,0),(20,0,0))
    assert 'reversed_station_projection' in issues
    assert paths[0][0]==(0.,0.,0.) and paths[0][-1]==(100.,0.,0.)


def test_nonfinite_curve_rejected():
    from map_geometry import sample_curve
    with pytest.raises(ValueError):
        sample_curve([[0,0,0],[30,0,0],[float('nan'),0,0],[100,0,0]])


def _fake_service(tmp_path):
    from map_geometry import MapGeometryService
    managed=tmp_path/'managed'; managed.mkdir()
    runtime=tmp_path/'runtime'; runtime.mkdir()
    bundles=tmp_path/'bundles'; bundles.mkdir()
    (managed/'Assembly-CSharp.dll').write_bytes(b'original')
    for name in ('Assembly-CSharp.probe.dll','UnityEngine.dll'):
        (runtime/name).write_bytes(b'probe')
    source=tmp_path/'source.save'; source.write_bytes(b'fake source')
    return MapGeometryService(tmp_path/'cache',managed,runtime,bundles),source


def test_cancel_running_worker_and_error_never_publish(tmp_path,monkeypatch):
    import subprocess,sys
    import map_geometry
    service,source=_fake_service(tmp_path)
    marker=tmp_path/'started'
    launched=[]; original=subprocess.Popen
    script=tmp_path/'worker.py'
    script.write_text('import sys,time\nfrom pathlib import Path\nPath(sys.argv[1]).write_text("started")\ntime.sleep(20)\n')
    def launch(*args,**kwargs):
        process=original([sys.executable,str(script),str(marker)],**kwargs)
        launched.append(process); return process
    monkeypatch.setattr(map_geometry.subprocess,'Popen',launch)
    with pytest.raises(map_geometry.MapCancelled):
        service.load(source,cancelled=marker.exists)
    assert launched[0].poll() is not None
    assert not list(service.cache_dir.glob('*.json.gz'))
    assert not list(service.cache_dir.glob('map-job-*'))
    script.write_text('raise SystemExit(3)\n')
    with pytest.raises(RuntimeError,match='extraction failed'):
        service.load(source)
    assert not list(service.cache_dir.glob('*.json.gz'))


def test_cache_reuses_snapshot_and_invalidates_source_assets_and_schema(tmp_path,monkeypatch):
    import json,subprocess,sys
    import map_geometry
    service,source=_fake_service(tmp_path)
    launched=[]; original=subprocess.Popen
    script=tmp_path/'worker.py'
    script.write_text('import json,sys\nfrom pathlib import Path\nc=json.loads(Path(sys.argv[1]).read_text())\n(Path(c["job"])/"geometry.json").write_text(json.dumps({"roads":{}}))\n')
    def launch(command,**kwargs):
        launched.append(command)
        return original([sys.executable,str(script),command[-1]],**kwargs)
    monkeypatch.setattr(map_geometry.subprocess,'Popen',launch)
    first=service.load(source)
    assert service.load(source) is first
    assert len(launched)==1
    service2=map_geometry.MapGeometryService(service.cache_dir,service.managed,service.runtime_data,service.bundles)
    assert service2.load(source)==first
    assert len(launched)==1
    source.write_bytes(b'different source')
    assert service.load(source).source_hash!=first.source_hash
    assert len(launched)==2
    (service.managed/'Assembly-CSharp.dll').write_bytes(b'different asset')
    assert service.load(source).asset_signature!=first.asset_signature
    assert len(launched)==3
    monkeypatch.setattr(map_geometry,'SCHEMA_VERSION',999)
    assert service.load(source).schema_version==999
    assert len(launched)==4


@pytest.mark.parametrize('number,name,display',[(5029,'502X','502X'),(5003,'5P（早高峰）','5P（早高峰）'),(5004,'5P（晚高峰）','5P（晚高峰）'),(12,'','12路')])
def test_route_display_name_uses_shared_contract(number,name,display):
    from map_geometry import snapshot_from_data
    snapshot=snapshot_from_data(dict(roads={},lines=[dict(id=1,number=number,name=name)]))
    assert snapshot.routes[0].name==display


def test_display_hierarchy_uses_assets_and_actual_lanes():
    from map_model import MapRoad, road_display_level
    make=lambda asset,a,b,**kwargs:MapRoad(1,asset,asset,(),a,b,**kwargs)
    assert road_display_level(make('express-way',4,0,express=True))=='express'
    assert road_display_level(make('avenue',1,1,road_class='avenue'))=='arterial'
    assert road_display_level(make('road',2,2,road_class='ordinary'))=='secondary'
    assert road_display_level(make('road',3,3,road_class='ordinary'))=='arterial'
    assert road_display_level(make('oneway-road',2,0,one_way=True,road_class='ordinary'))=='local'
    assert road_display_level(make('depot-road',2,2,road_class='ordinary'))=='local'
    assert road_display_level(make('pedestrian-street',1,1,pedestrian=True))=='pedestrian'
    assert road_display_level(make('double-tram',1,1,track=True,pedestrian=True))=='track'
    assert road_display_level(make('',None,None))=='unknown'


def test_zero_length_and_two_stop_closed_operating_path():
    from map_analysis import infer_direction
    origin=(0.,0.,0.)
    assert infer_direction((origin,origin,origin),(((origin,origin),),((origin,origin),))).kind=='unknown'
    loop=(origin,(200.,0.,0.),(200.,0.,200.),(0.,0.,200.),origin)
    assert infer_direction((origin,origin),((loop,),)).kind=='circular'


def test_junction_connections_use_saved_lane_cubic_controls():
    from map_geometry import snapshot_from_data, _decode_snapshot
    from dataclasses import asdict
    controls=[[10,5,0],[15,5,0],[20,5,5],[20,5,10]]
    data=dict(roads={},junctions=[dict(id=10,position=(15,5,5),road_ids=[1,2],bridge=True,tunnel=False,
                                    connections=[dict(id=11,source_road_id=1,target_road_id=2,source_lane=0,target_lane=1,type_mask=1,curves=[controls])])])
    snapshot=snapshot_from_data(data)
    junction=snapshot.junctions[0]
    connection=junction.connections[0]
    assert junction.bridge and not junction.tunnel
    assert junction.road_ids==(1,2)
    assert connection.paths[0][0]==tuple(controls[0])
    assert connection.paths[0][-1]==tuple(controls[-1])
    assert connection.source_road_id==1 and connection.target_road_id==2
    assert junction.paths==connection.paths
    assert _decode_snapshot(asdict(snapshot))==snapshot


def test_actual_lane_counts_exclude_parking_and_walking_and_preserve_bus():
    from map_geometry import actual_lane_attributes
    cars=1<<24;forward=256;backward=512
    lanes=[dict(index=0,type_mask=cars|forward|4,turn_directions=0,offset=11.5),
           dict(index=1,type_mask=cars|forward|2,turn_directions=1,offset=8.5),
           dict(index=2,type_mask=cars|forward|1,turn_directions=1,offset=5.5),
           dict(index=3,type_mask=cars|backward|1,turn_directions=2,offset=-5.5),
           dict(index=4,type_mask=cars|backward|2,turn_directions=2,offset=-8.5),
           dict(index=5,type_mask=cars|backward|4,turn_directions=0,offset=-11.5),
           dict(index=6,type_mask=65536|forward,turn_directions=0,offset=15),
           dict(index=7,type_mask=65536|forward,turn_directions=0,offset=-15)]
    result=actual_lane_attributes(lanes,4.,4.)
    assert result['lanes_a']==result['lanes_b']==2
    assert result['bus_lanes_a']==result['bus_lanes_b']==1
    assert result['parking_lanes_a']==result['parking_lanes_b']==1
    assert result['width']==34
    pedestrian=[dict(index=0,type_mask=cars|forward|8,turn_directions=0,offset=0)]
    assert actual_lane_attributes(pedestrian,4,4)['lanes_a']==0


def test_parallel_return_with_small_terminal_loop_and_repeated_end():
    from map_analysis import infer_direction
    points=((0.,0.,0.),(600.,0.,0.),(1200.,0.,0.),(1220.,0.,20.),
            (1200.,0.,40.),(600.,0.,40.),(0.,0.,0.))
    legs=tuple(((a,b),) for a,b in zip(points,points[1:]))
    direction=infer_direction(points,legs,['','火车站','','','','',''])
    assert direction.kind=='roundtrip'
    assert direction.terminal_index in (2,3,4)
    assert direction.terminal_index!=1
    assert (0,6) in direction.paired_stations


def test_frozen_bundle_root_probe_script_and_default_paths(tmp_path,monkeypatch):
    import sys
    import map_geometry
    bundle=tmp_path/'bundle';bundle.mkdir()
    (bundle/'data').mkdir();(bundle/'data'/'map_assets.json').write_text('{}')
    (bundle/'src').mkdir();(bundle/'src'/'patch_singleton_probe.py').write_text('')
    local=tmp_path/'local'
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'_MEIPASS',str(bundle),raising=False)
    monkeypatch.setattr(map_geometry,'__file__',str(bundle/'map_geometry.py'))
    monkeypatch.setenv('LOCALAPPDATA',str(local))
    for name in ('CIM2_MANAGED_ROOT','CIM2_RUNTIME_DATA_DIR','CIM2_BUNDLES_DIR'):
        monkeypatch.delenv(name,raising=False)
    assert map_geometry.runtime_root()==bundle
    assert map_geometry.probe_script()==bundle/'src'/'patch_singleton_probe.py'
    service=map_geometry.MapGeometryService()
    assert service.runtime_data==bundle/'data'
    assert service.managed==bundle/'game_runtime'/'Managed'
    assert service.asset_catalog==bundle/'data'/'map_assets.json'
    assert service.bundles is None
    assert service.cache_dir==local/'CimStats'/'map-cache'


def test_source_layout_uses_repository_root(tmp_path,monkeypatch):
    import sys
    import map_geometry
    monkeypatch.setattr(sys,'frozen',False,raising=False)
    monkeypatch.setattr(map_geometry,'__file__',str(tmp_path/'src'/'map_geometry.py'))
    assert map_geometry.runtime_root()==tmp_path
    assert map_geometry.probe_script()==tmp_path/'src'/'patch_singleton_probe.py'


def test_connected_route_uses_real_lane_range_and_junction_curve():
    from map_geometry import route_leg
    roads={1:dict(id=1,start=0,end=10,curves=[[[0,0,0],[3,0,0],[7,0,0],[10,0,0]]],
                  lanes=[dict(index=0,type_mask=0x1000101,offset=1.5)]),
           2:dict(id=2,start=10,end=20,curves=[[[14,0,4],[14,0,7],[14,0,11],[14,0,14]]],
                  lanes=[dict(index=0,type_mask=0x1000101,offset=1.5)])}
    curve=[[10,0,-1.5],[13,0,-1.5],[15.5,0,1],[15.5,0,4]]
    connections={(1,2):[dict(id=50,source_road_id=1,target_road_id=2,source_lane=0,target_lane=0,type_mask=1<<24,curves=[curve])]}
    refs=[dict(id=1,mask=33,min_lane=0,max_lane=0),dict(id=2,mask=33,min_lane=0,max_lane=0)]
    paths,issues=route_leg(refs,roads,connections=connections,mode='bus')
    assert not issues
    assert len(paths)==3
    assert paths[0][-1]==paths[1][0]==(10.,0.,-1.5)
    assert paths[1][-1]==paths[2][0]==(15.5,0.,4.)
    assert paths[1][0]==tuple(curve[0]) and paths[1][-1]==tuple(curve[-1])
    # A disallowed saved lane may not be silently used to bridge a gap.
    refs[1]['min_lane']=refs[1]['max_lane']=1
    _,issues=route_leg(refs,roads,connections=connections,mode='bus')
    assert issues


def test_joined_lane_geometry_does_not_invent_missing_connection():
    from map_geometry import route_leg
    road=dict(id=1,start=1,end=2,curves=[[[0,0,0],[3,0,0],[7,0,0],[10,0,0]]],
              lanes=[dict(index=0,type_mask=0x1000101,offset=0)])
    other=road|dict(id=2,start=2,end=3,curves=[[[20,0,0],[23,0,0],[27,0,0],[30,0,0]]])
    refs=[dict(id=i,mask=33,min_lane=0,max_lane=0) for i in (1,2)]
    paths,issues=route_leg(refs,{1:road,2:other},connections={},mode='bus')
    assert any('missing_lane_connection' in issue for issue in issues)
    assert len(paths)==2 and paths[0][-1]!=(paths[1][0])


def test_operating_lane_chain_stays_continuous_across_shared_stop():
    from map_geometry import snapshot_from_data
    def road(i,start,end,a,b,lanes):
        return dict(id=i,start=start,end=end,curves=[[[a,0,0],[a+(b-a)/3,0,0],[a+2*(b-a)/3,0,0],[b,0,0]]],
                    lanes=[dict(index=k,type_mask=0x1000101,turn_directions=0,offset=o) for k,o in enumerate(lanes)])
    roads={'1':road(1,0,10,0,10,[0]),'2':road(2,10,20,20,40,[0,3]),'3':road(3,20,30,50,60,[0])}
    def conn(i,a,b,sl,tl,curve):return dict(id=i,source_road_id=a,target_road_id=b,source_lane=sl,target_lane=tl,type_mask=1<<24,curves=[curve])
    junctions=[dict(id=10,position=(15,0,0),road_ids=[1,2],connections=[conn(10,1,2,0,1,[[10,0,0],[15,0,0],[16,0,-3],[20,0,-3]])]),
               dict(id=20,position=(45,0,0),road_ids=[2,3],connections=[conn(20,2,3,0,0,[[40,0,0],[43,0,0],[47,0,0],[50,0,0]]),conn(21,2,3,1,0,[[40,0,-3],[43,0,-3],[47,0,0],[50,0,0]])])]
    ref=lambda i:dict(id=i,mask=33,min_lane=0,max_lane=1 if i==2 else 0)
    line=dict(id=1,number=1,mode='bus',stops=[dict(id=100,position=(0,0,0)),dict(id=101,position=(0,0,0)),dict(id=102,position=(30,0,-3)),dict(id=103,position=(60,0,0))],
              legs=[dict(roads=[ref(1)]),dict(roads=[ref(1),ref(2)]),dict(roads=[ref(2),ref(3)]),dict(roads=[ref(3)])])
    s=snapshot_from_data(dict(roads=roads,junctions=junctions,lines=[line],buildings=[dict(id=100,kind='DepotData',position=(0,0,0))]))
    r=s.routes[0]
    assert r.diagnostic is None
    assert r.leg_paths[0][-1][-1]==r.leg_paths[1][0][0]==(30.,0.,-3.)


def test_native_function_values_keep_full_denominator_and_unknown_separate():
    from map_model import GroupFunctionCount,building_function_values
    groups=('BlueCollar','WhiteCollar','Student','BusinessPeople','Pensioner','Tourist')
    capacities=tuple(GroupFunctionCount(g,10 if g=='BlueCollar' else 0,20 if g=='WhiteCollar' else 0,5 if g=='Student' else 0) for g in groups)
    b=MapBuilding(1,'','',(0,0,0),function_capacities=capacities)
    one=building_function_values(b,['BlueCollar'])
    assert (one.home,one.work,one.leisure,one.denominator)==(10,0,0,20)
    many=building_function_values(b,['BlueCollar','WhiteCollar','BlueCollar'])
    assert (many.home,many.work,many.leisure,many.denominator)==(10,20,0,20)
    empty=building_function_values(b,[])
    assert (empty.home,empty.work,empty.leisure,empty.denominator)==(0,0,0,20)
    assert building_function_values(MapBuilding(1,'','',(0,0,0))).denominator is None
    zero=MapBuilding(1,'','',(0,0,0),function_capacities=tuple(GroupFunctionCount(g,0,0,0) for g in groups))
    assert building_function_values(zero).denominator==0


def test_native_capacity_profile_uses_ruleset_q10_and_ceil_without_normalizing():
    from map_geometry import native_function_capacities,native_distribution_tables
    from pathlib import Path
    tables=native_distribution_tables(Path(__file__).resolve().parents[1]/'game_runtime/Managed/Assembly-CSharp.dll')
    rows=native_function_capacities(dict(area_type=11,homes=10,work=10,recreation=10),1536,tables)
    assert [r['home'] for r in rows]==[3,3,3,2,4,2]
    assert [r['leisure'] for r in rows]==[3,3,2,1,2,1]
    assert next(r for r in rows if r['group']=='WhiteCollar')['work']==9
    assert sum(r['work'] for r in rows)==19  # ceil(15*.3)+ceil(15*.6)+ceil(15*.3), not renormalized120%.
    assert native_function_capacities(None,1536,tables)[0]['home'] is None
    unknown=native_function_capacities(dict(area_type=11,homes=10,work=0,recreation=10),None,tables)
    assert unknown[0]['home'] is None and unknown[0]['work']==0


def test_native_citizen_multiplier_distinguishes_missing_ruleset_and_default():
    from map_geometry import native_citizen_multiplier
    assert native_citizen_multiplier(None) is None
    assert native_citizen_multiplier([])==512
    assert native_citizen_multiplier([('general','citizen-amount',300)])==1536
    assert native_citizen_multiplier([('general','car-amount',300)])==512
    assert native_citizen_multiplier([('general','citizen-amount',101)])==517


def test_native_capacity_missing_area_is_unknown_except_known_zero():
    from map_geometry import native_function_capacities
    rows=native_function_capacities(dict(homes=20,work=0,recreation=4),512,{})
    assert all(r['home'] is None and r['work']==0 and r['leisure'] is None for r in rows)
