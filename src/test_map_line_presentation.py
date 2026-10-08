"""Map information must use the line page's display and availability rules."""
from dataclasses import replace
from types import SimpleNamespace
import pytest


def test_direction_lengths_use_the_shared_information_page_scale_once():
    from display_rules import display_map_km
    from map_line_facts import geometry_lengths
    from map_model import MapRoute, RouteDirection
    down = ((0., 0., 0.), (3000., 4000., 0.))
    up = tuple(reversed(down))
    depot = ((0., 0., 0.), (0., 0., 2000.))
    route = MapRoute(1, 'A', 1, 'a', 'A', 'bus', (), (down, up),
                     RouteDirection('roundtrip', 1), ((down,), (up,)), (depot,))
    assert geometry_lengths(route, 'up').operating_km == display_map_km(5.)
    assert geometry_lengths(route, 'both', True).total_km == display_map_km(12.)
    assert geometry_lengths(route, 'down', True).deadhead_km == display_map_km(2.)
    assert route.paths == (down, up) and route.depot_paths == (depot,)
    assert geometry_lengths(replace(route, paths=(), leg_paths=())).operating_km is None


def test_information_reuses_line_page_values_and_preserves_stable_identity():
    from map_line_presentation import line_information
    from line_query_page import shown, line_display_value
    line = {'对象ID': 42, '公司标识': 'original-owner', '公司名称': "jeremylin2005's Company",
            '运输制式': '公交', '线路名称': '812E', '线路车库': '东库',
            '开线日期': '2013-05-01', '最近改线日期': '2013-05-20',
            '地图里程': 12.345, '站点数': 14, '单程时间': 55., '核定速度': 13.467,
            '当日发班数': 85, '平均间隔': '15 min', '理论最大车辆需求数': 7,
            '平均车辆需求数': 6.234, '每周收入': 102.999, '每周支出': 100.,
            '今日客流': 0, '平均客流': 13.456, '今日平均单班人次': 0,
            '今日平均车公里人次': 0}
    session = {'lines': [line]}
    result = line_information(session, 42)
    assert result['identity'] == {'id': 42, 'name': '812E', 'mode': '公交',
                                 'company_name': '八连交通集团', 'company_id': 'original-owner'}
    assert [(key, title) for key, title, _ in result['sections']] == [
        ('line_information', '线路信息'), ('passenger_data', '客流数据')]
    fields = {key: text for _, _, rows in result['sections'] for key, _, text in rows}
    for key, unit in [('地图里程', 'km'), ('站点数', '站'), ('单程时间', 'min'),
                      ('核定速度', 'km/h'), ('当日发班数', '班'),
                      ('理论最大车辆需求数', '辆'), ('每周收入', ''), ('每周支出', ''),
                      ('今日客流', '人次'), ('今日平均单班人次', ''), ('今日平均车公里人次', '')]:
        assert fields[key] == shown(line_display_value(line, key, session['lines']), unit)
    assert line['公司名称'] == "jeremylin2005's Company"
    assert fields['今日客流'] == '0 人次'
    assert line_information(session, 999) is None
    assert line_information({'lines': [line, dict(line)]}, 42) is None


def test_information_keeps_unavailable_and_incomplete_metrics_unknown():
    from map_line_presentation import line_information
    line = {'对象ID': 2, '地图里程': 0, '核定速度': 0, '当日发班数': 0,
            '今日平均单班人次': 0, '今日平均车公里人次': 0,
            '字段可用性': {'地图里程': False}, '班次数据完整': False}
    fields = {key: text for _, _, rows in line_information({'lines': [line]}, 2)['sections']
              for key, _, text in rows}
    assert all(fields[key] == '—' for key in (
        '地图里程', '核定速度', '当日发班数', '今日平均单班人次', '今日平均车公里人次'))


def test_map_departures_caption_is_plain_without_a_plan_qualifier():
    from map_line_presentation import line_information
    result=line_information({'lines':[{'对象ID':2,'当日发班数':0}]},2)
    rows={key:(label,text) for _,_,fields in result['sections'] for key,label,text in fields}
    assert rows['当日发班数']==('当日发班','0 班')


@pytest.mark.parametrize('direction,duration,speed,label',[
    ('up',23.9115,21.34,'上行'),('down',23.411,23.09,'下行'),('whole',47.3225,22.201,'全线')])
def test_direction_information_uses_arrival_duration_and_speed_without_halving_full_facts(direction,duration,speed,label):
    from map_line_presentation import line_information
    line={'对象ID':42,'地图里程':17.570164,'单程时间':80,'核定速度':13.17,
          '今日客流':823,'当日发班数':70}
    metrics=SimpleNamespace(effective_direction=direction,duration_minutes=duration,speed_kmh=speed)
    result=line_information({'lines':[line]},42,direction_metrics=metrics)
    rows={key:(title,text) for _,_,fields in result['sections'] for key,title,text in fields}
    assert result['direction']==direction
    assert rows['单程时间']==(f'核定时间（{label}）',{'up':'23.91 min','down':'23.41 min','whole':'80 min'}[direction])
    assert rows['核定速度']==(f'核定速度（{label}）',{'up':'21.34 km/h','down':'23.09 km/h','whole':'13.17 km/h'}[direction])
    assert ('地图里程' in rows)==(direction=='whole')
    assert rows['今日客流']==('今日客流','823 人次') and rows['当日发班数']==('当日发班','70 班')
    assert line['单程时间']==80 and line['核定速度']==13.17


def test_missing_direction_metrics_never_fall_back_to_whole_duration_or_speed():
    from map_line_presentation import line_information
    line={'对象ID':42,'地图里程':17.57,'单程时间':80,'核定速度':13.17}
    info=line_information({'lines':[line]},42,direction_metrics={
        'effective_direction':'down','duration_minutes':None,'speed_kmh':None})
    rows={key:(title,text) for _,_,fields in info['sections'] for key,title,text in fields}
    assert rows['单程时间']==('核定时间（下行）','—')
    assert rows['核定速度']==('核定速度（下行）','—') and '地图里程' not in rows


def test_whole_information_preserves_original_shared_speed_precision_and_availability():
    from map_line_presentation import line_information
    lines=[{'对象ID':42,'地图里程':17.570164,'单程时间':55.,'核定速度':19.17},
           {'对象ID':43,'单程时间':55.,'核定速度':19.17,'字段可用性':{'核定速度':False}}]
    metrics=SimpleNamespace(effective_direction='whole',duration_minutes=54.999,speed_kmh=19.16745)
    for line,expected in [(lines[0],'19.17 km/h'),(lines[1],'—')]:
        info=line_information({'lines':lines},line['对象ID'],direction_metrics=metrics)
        rows={key:text for _,_,fields in info['sections'] for key,title,text in fields}
        assert rows['单程时间']=='55 min' and rows['核定速度']==expected


def test_company_legend_and_options_use_information_page_names_without_changing_ids():
    from map_model import MapRoute, MapSnapshot
    from map_query import MapQuery
    route = MapRoute(7, '7', 7, 'owner', "jeremylin2005's Company", 'bus', (), ())
    query = MapQuery(MapSnapshot(routes=(route,)))
    assert query.panel_options()['companies'][0]['name'] == '八连交通集团'
    assert query.panel_options()['companies'][0]['id'] == 'owner'
    assert query.legend_items({'color_by': 'company'})[0][0] == '八连交通集团'
    assert query.snapshot.routes[0].company_name == route.company_name


def test_company_context_from_the_same_session_is_used_across_network_options_and_legend():
    from map_model import MapRoute, MapSnapshot
    from map_query import MapQuery
    routes = (MapRoute(7, '1', 1, 'a', 'native A', 'bus', (), ()),
              MapRoute(8, '1', 1, 'b', 'native B', 'bus', (), ()))
    query = MapQuery(MapSnapshot(routes=routes))
    session = {'companies': [{'公司标识': 'a', '公司名称': '甲公司'},
                              {'公司标识': 'b', '公司名称': '乙公司'}]}
    options = query.panel_options(session)
    assert {row['id']: row['name'] for row in options['companies']} == {'a': '甲公司', 'b': '乙公司'}
    assert {row['id']: row['display_label'] for row in options['lines']} == {
        7: '甲公司公交1路', 8: '乙公司公交1路'}
    assert {title for title, _ in query.legend_items({'color_by': 'company'})} == {'甲公司', '乙公司'}
    assert routes[0].company_name == 'native A'
