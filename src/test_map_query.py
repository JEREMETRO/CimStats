from map_model import MapRoute, MapSnapshot, RouteDirection
from map_query import MapQuery, RouteStats

def sample():
    routes=tuple(MapRoute(i, str(i), i, company, company, mode, (), (), RouteDirection('oneway'))
                 for i,company,mode in ((1,'a','bus'),(2,'a','tram'),(3,'b','bus')))
    return MapQuery(MapSnapshot(routes=routes), {1:RouteStats(100,5),2:RouteStats(20,-3),3:RouteStats(None,None)})

def test_filters_are_intersection_with_empty_manual_preserved():
    q=sample()
    assert [x.id for x in q.select({'company_ids':['a'],'modes':['bus','tram']}).routes] == [2,1]
    assert not q.select({'manual_line_ids':[]}).routes
    assert [x.id for x in q.select({'profit_statuses':['missing']}).routes] == [3]
    assert [x.id for x in q.select({'passenger_min':50}).routes] == [1]

def test_zorder_is_independent_and_top_priority_last():
    q=sample()
    a=q.select({'priority_by':'mode','mode_order':['bus','tram']})
    b=q.select({'priority_by':'mode','mode_order':['tram','bus']})
    assert a.routes[-1].mode=='bus' and b.routes[-1].mode=='tram'
    assert a.route_colors == b.route_colors
    assert set(x.id for x in a.routes)==set(x.id for x in b.routes)

def test_all_direction_modes_keep_oneway():
    q=sample()
    for direction in ('whole','up','down'):
        assert len(q.select({'direction':direction}).routes)==3

def test_stable_ids_join_not_display_names():
    from map_query import stats_from_session
    r=sample().snapshot.routes
    s={'lines':[{'对象ID':1,'线路名称':'renamed','原始字段':{'收入_累计':'102400','支出_累计':'0'}}]}
    result=stats_from_session(s,r)
    assert result[1].profit==1 and result[2].profit is None
    assert result[1].passengers is None

def test_individual_route_palette_is_not_eight_repeating_colors():
    q=sample()
    from semantic_colors import color_for
    colors=[color_for('line',i) for i in range(83)]
    assert len(set(colors))==83

def test_options_follow_semantic_social_order_not_alphabetical():
    from map_model import MapBuilding,GroupFunctionCount
    from semantic_colors import SOCIAL
    b=MapBuilding(1,'','',(0,0,0),function_capacities=tuple(GroupFunctionCount(g.key,1,0,0) for g in SOCIAL))
    q=MapQuery(MapSnapshot(buildings=(b,)))
    assert [v['id'] for v in q.panel_options()['building_classes']][:6]==[g.key for g in SOCIAL]

def test_waterbus_is_excluded_only_from_map_feature():
    from dataclasses import replace
    original=sample().snapshot
    water=replace(original.routes[0],id=9,mode='waterbus',name='水上巴士1')
    source=replace(original,routes=(*original.routes,water))
    q=MapQuery(source)
    assert all(r.mode!='waterbus' for r in q.select({}).routes)
    assert all(v['id']!='waterbus' for v in q.panel_options()['modes'])
    assert all(v['id']!=9 for v in q.panel_options()['lines'])
    assert source.routes[-1] is water

def test_stops_follow_actual_visible_routes_and_shared_stops_remain():
    from dataclasses import replace
    from map_model import MapStop
    base=sample().snapshot
    path=(((0.,0.,0.),(20.,0.,0.)),)
    a=replace(base.routes[0],stop_ids=(1,2),paths=path)
    b=replace(base.routes[1],stop_ids=(2,3),paths=path)
    stops=tuple(MapStop(i,str(i),(float(i),0.,0.)) for i in (1,2,3,4))
    q=MapQuery(replace(base,routes=(a,b),stops=stops))
    assert [s.id for s in q.select({'manual_line_ids':[a.id]}).snapshot.stops]==[1,2]
    assert [s.id for s in q.select({'layer_modes':['tram']}).snapshot.stops]==[2,3]
    assert not q.select({'routes':False}).snapshot.stops
    assert not q.select({'manual_line_ids':[]}).snapshot.stops

def test_legend_uses_visible_categories_and_shared_colors():
    q=sample()
    assert q.legend_items({'layer_modes':['bus']}) == (('公交','#1976D2'),)
    assert q.legend_items({'routes':False}) == ()
    assert q.legend_items({'color_by':'line'}) == ()
    assert len(q.legend_items({'color_by':'profit'})) == 4

def test_company_without_routes_keeps_cross_page_palette():
    from semantic_colors import company_palette
    route=MapRoute(2,'2',2,'b','B','bus',(),(),RouteDirection('one_way'))
    q=MapQuery(MapSnapshot(routes=(route,)),company_ids=['a','b'])
    expected=company_palette(['a','b'])['b']
    assert q.route_color(route,{'color_by':'company'})==expected
    assert q.select({'color_by':'company','company_ids':['b']}).route_colors[2]==expected

def test_direction_hides_only_stops_of_hidden_operating_legs():
    from dataclasses import replace
    from map_model import MapStop
    p=((0.,0.,0.),(20.,0.,0.))
    route=MapRoute(1,'1',1,'a','A','bus',(1,2,3,4,1),(p,)*4,RouteDirection('roundtrip',terminal_index=2),((p,),)*4)
    stops=tuple(MapStop(i,str(i),(float(i),0.,0.)) for i in (1,2,3,4))
    q=MapQuery(MapSnapshot(routes=(route,),stops=stops))
    assert {s.id for s in q.select({'direction':'down'}).snapshot.stops}=={1,2,3}
    assert {s.id for s in q.select({'direction':'up'}).snapshot.stops}=={1,3,4}
    loop=replace(route,id=2,stop_ids=(2,4),direction=RouteDirection('circular'),leg_paths=((p,),),paths=(p,))
    q=MapQuery(MapSnapshot(routes=(route,loop),stops=stops))
    assert {s.id for s in q.select({'direction':'up'}).snapshot.stops}=={1,2,3,4}
    assert {s.id for s in q.select({'direction':'up','manual_line_ids':[1]}).snapshot.stops}=={1,3,4}


def test_building_emphasis_defaults_to_actual_visible_operating_paths():
    from dataclasses import replace
    base=sample().snapshot.routes[0]
    p=((0.,0.,0.),(20.,0.,0.))
    route=replace(base,paths=(p,))
    q=MapQuery(MapSnapshot(routes=(route,)))
    assert q.select({}).building_emphasis is False
    for state in ({'routes':False}, {'manual_line_ids':[]}, {'layer_modes':[]}):
        assert q.select(state).building_emphasis is True
    assert q.select({'building_emphasis':True}).building_emphasis is True
    assert q.select({'routes':False,'building_emphasis':False}).building_emphasis is False
    assert MapQuery(MapSnapshot(routes=(base,))).select({}).building_emphasis is True
    split=replace(route,direction=RouteDirection('roundtrip',terminal_index=1),leg_paths=((p,),()))
    query=MapQuery(MapSnapshot(routes=(split,)))
    assert query.select({'direction':'up'}).building_emphasis is True
    assert query.select({'direction':'down'}).building_emphasis is False
    assert query.panel_options(state={'direction':'up'})['building_emphasis_effective'] is True


def test_building_function_colors_follow_selected_capacity_not_observed_population():
    from map_model import MapBuilding,GroupFunctionCount,SOCIAL_GROUPS
    from semantic_colors import map_fill
    records=tuple(GroupFunctionCount(g,100 if g=='BlueCollar' else 0,
                                     100 if g=='Student' else 0,0) for g in SOCIAL_GROUPS)
    b=MapBuilding(1,'','',(0,0,0),function_capacities=records)
    q=MapQuery(MapSnapshot(buildings=(b,)))
    home=q.select({'building_classes':['BlueCollar']})
    work=q.select({'building_classes':['Student']})
    assert home.building_colors[1]==map_fill('usage','residential',.85)
    assert work.building_colors[1]==map_fill('usage','work',.85)
    assert not q.select({'building_classes':['Tourist']}).snapshot.buildings
    assert not q.select({'building_classes':[]}).snapshot.buildings
    assert q.select({'building_classes':['BlueCollar'],'building_color_by':'use',
                     'building_uses':[]}).building_colors==home.building_colors
    subdued=q.select({'building_classes':['BlueCollar'],'building_emphasis':False})
    assert subdued.building_colors[1]==map_fill('usage','residential',.24)
    assert ('住宅',__import__('semantic_colors').color_for('usage','residential')) in q.legend_items(
        {'building_classes':['BlueCollar'],'routes':False})
    assert not q.legend_items({'routes':False,'buildings':False})
