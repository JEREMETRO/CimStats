"""Continuous metric colours must use confirmed native numbers and one legend scale."""
from copy import deepcopy
import pytest
from map_model import MapRoute,MapSnapshot
from map_query import MapQuery,RouteStats,stats_from_session
import semantic_colors


@pytest.mark.parametrize('metric,value,want',[
    ('interval',5,'#5A1020'),('interval',7.5,'#E52222'),
    ('interval',12.5,'#FF8A00'),('interval',17.5,'#F3CF32'),('interval',25,'#A6CE39'),
    ('interval',37.5,'#2E8B57'),('interval',45,'#173D6E'),
    ('passengers',1000,'#173D6E'),('passengers',3000,'#2E8B57'),
    ('passengers',7500,'#F3CF32'),('passengers',15000,'#F2AA24'),
    ('passengers',25000,'#E45F2B'),('passengers',40000,'#D32F2F'),
    ('passengers',50000,'#5A1020'),
])
def test_metric_anchors_match_the_requested_representative_colours(metric,value,want):
    assert callable(getattr(semantic_colors,'metric_color',None))
    assert semantic_colors.metric_color(metric,value)==want


@pytest.mark.parametrize('metric,boundaries',[
    ('interval',(5,10,15,20,30,45)),
    ('passengers',(1000,5000,10000,20000,30000,50000)),
])
def test_metric_colours_have_no_threshold_jumps(metric,boundaries):
    assert callable(getattr(semantic_colors,'metric_color',None))
    def rgb(value):
        colour=semantic_colors.metric_color(metric,value)
        return tuple(int(colour[i:i+2],16) for i in (1,3,5))
    for value in boundaries:
        assert max(abs(a-b) for a,b in zip(rgb(value-.001),rgb(value+.001)))<=1
    low,high=(5,7.5) if metric=='interval' else (1000,3000)
    assert rgb((low+high)/2) not in (rgb(low),rgb(high))


@pytest.mark.parametrize('metric',('interval','passengers'))
def test_zero_missing_invalid_and_saturation_are_distinct(metric):
    assert callable(getattr(semantic_colors,'metric_color',None))
    known_zero='#5A1020' if metric=='interval' else '#173D6E'
    assert semantic_colors.metric_color(metric,0)==known_zero
    assert semantic_colors.metric_color(metric,1e9)==('#173D6E' if metric=='interval' else '#5A1020')
    for value in (None,float('nan'),float('inf'),-1,False,'unknown'):
        assert semantic_colors.metric_color(metric,value)=='#98A8B9'


def route(identity,passengers=None):
    return MapRoute(identity,str(identity),identity,'a','Alpha','bus',(),
                    (((0.,0.,0.),(100.,0.,0.)),),previous_day_passengers=passengers)


def line(identity,rows,**extra):
    return {'对象ID':identity,'原始字段':{'客流_今日':99999,'客流_累计':0,'时刻表数':1},
            '平均间隔':'999min display text must never be parsed','平均客流':0,
            '开线日期':'2013-04-10 05:47','班次数据完整':True,
            '时刻表':{'original':{'entries':rows}},**extra}


def departure(table,row,hours,mask=16):
    return {'时刻表序号':table,'发班序号':row,'发班_tick':round(hours*36_000_000_000),
            '运行日掩码':mask,'running_day_valid':True}


def test_stats_use_confirmed_calendar_day_departures_and_average_before_2300():
    entries=[departure(1,1,8),departure(1,2,8+12.5/60),
             departure(2,1,25,8),departure(3,1,24.5,16)]
    session={'simulation_time':'2013-05-23T12:00:00','lines':[line(1,entries)]}
    original=deepcopy(session)
    stats=stats_from_session(session,(route(1,0),))[1]
    assert getattr(stats,'average_interval_minutes',None)==12.5
    assert getattr(stats,'scheduled_departures',None)==3
    assert getattr(stats,'opened_at',None)=='2013-04-10T05:47:00'
    assert stats.passengers==0 and stats.passenger_source=='average'
    assert route(1,123).previous_day_passengers==123
    assert session==original


@pytest.mark.parametrize('extra',[
    {'班次数据完整':False},
    {'运行日未知班次':[{'发班_tick':0}]},
    {'时刻表':{'bad':{'entries':[departure(1,1,8),{'运行日掩码':16}]}}},
])
def test_incomplete_schedules_never_receive_numeric_average_or_departure_count(extra):
    session={'simulation_time':'2013-05-23T12:00:00','lines':[line(1,[departure(1,1,8),departure(1,2,9)],**extra)]}
    stats=stats_from_session(session,(route(1),))[1]
    assert hasattr(stats,'average_interval_minutes') and stats.average_interval_minutes is None
    assert stats.scheduled_departures is None
    assert stats.passengers==0


def test_duplicate_native_rows_are_not_duplicate_departures_but_equal_clock_rows_are():
    first=departure(1,1,8);second=departure(1,2,8)
    session={'simulation_time':'2013-05-23T12:00:00','lines':[line(1,[first,dict(first),second])]}
    stats=stats_from_session(session,(route(1),))[1]
    assert getattr(stats,'average_interval_minutes',None)==0
    assert stats.scheduled_departures==2


def test_colouring_and_options_preserve_filter_geometry_and_share_values():
    assert hasattr(RouteStats,'average_interval_minutes')
    snapshot=MapSnapshot(routes=(route(1,0),route(2,None)))
    stats=stats_from_session({'simulation_time':'2013-05-23T12:00:00','lines':[
        line(1,[departure(1,1,8),departure(1,2,8+12.5/60)])]},snapshot.routes)
    query=MapQuery(snapshot,stats)
    base=query.select({'color_by':'mode'})
    interval=query.select({'color_by':'interval'})
    assert interval.route_colors[1]=='#FF8A00' and interval.route_colors[2]=='#98A8B9'
    daily=query.select({'color_by':'passengers'})
    assert daily.route_colors[1]=='#173D6E' and daily.route_colors[2]=='#98A8B9'
    assert daily.snapshot.routes is base.snapshot.routes
    assert query.select({'color_by':'passengers','passenger_min':1}).routes==()
    assert query.snapshot.routes[0].previous_day_passengers==0
    options=query.panel_options({'simulation_time':'2013-05-23T12:00:00'})
    assert options['passenger_date']=='2013-05-23'
    assert options['passenger_source']=='average' and options['passenger_label']=='平均客流'
    row=options['lines'][0]
    assert row['passengers']==0 and row['scheduled_departures']==2
    assert row['opened_at']=='2013-04-10T05:47:00'
    legend=query.legend_items({'color_by':'passengers'},daily)
    assert isinstance(legend,semantic_colors.MetricLegend)
    assert legend.date=='2013-05-23' and legend.unit=='千人次'
    assert legend.source=='average' and '平均客流' in legend.heading
    assert legend.labels==('1','3','7.5','15','25','40','50')
    assert legend.missing_colour=='#98A8B9'
    mean=query.legend_items({'color_by':'interval'},interval)
    assert mean.date=='2013-05-23' and mean.unit=='min'
    assert mean.labels==('5','7.5','12.5','17.5','25','37.5','45')
    assert mean.gradient_stops[0][1]=='#5A1020' and mean.gradient_stops[-1][1]=='#173D6E'


@pytest.mark.parametrize('clock,source,want',[
    ('22:59:59','average',3000),('23:00:00','today',50000),
    ('23:59:59','today',50000),('00:00:00','average',3000),
])
def test_passenger_source_switches_at_2300_and_drives_filter_colour_and_legend(clock,source,want):
    item=line(1,[],平均客流=3000)
    item['原始字段'].update(客流_今日=50000,客流_累计=99999)
    session={'simulation_time':'2013-05-23T'+clock,'lines':[item]}
    original=deepcopy(session);snapshot=MapSnapshot(routes=(route(1,123),))
    query=MapQuery(snapshot,stats_from_session(session,snapshot.routes))
    assert query.stats[1].passengers==want and query.stats[1].passenger_source==source
    selected=query.select({'color_by':'passengers','passenger_min':want})
    assert selected.route_colors[1]==semantic_colors.metric_color('passengers',want)
    assert query.select({'passenger_min':want+1}).routes==()
    options=query.panel_options(session)
    assert options['passenger_source']==source and options['passenger_date']=='2013-05-23'
    assert options['lines'][0]['passengers']==want
    legend=query.legend_items({'color_by':'passengers'},selected)
    assert legend.source==source and legend.date=='2013-05-23'
    assert legend.title==('今日客流' if source=='today' else '平均客流')
    assert session==original and snapshot.routes[0].previous_day_passengers==123


@pytest.mark.parametrize('source,key,raw_key,clock',[
    ('average','平均客流','客流_累计','12:00:00'),
    ('today','今日客流','客流_今日','23:00:00'),
])
@pytest.mark.parametrize('kind',('zero','missing','unavailable','invalid','ambiguous'))
def test_missing_source_never_falls_back_to_other_counter(source,key,raw_key,clock,kind):
    item=line(1,[],平均客流=123)
    item['原始字段'].update(客流_今日=999,客流_累计=1000)
    if kind=='zero':
        item['原始字段'][raw_key]=0;item[key]=0
    elif kind=='missing':item['原始字段'].pop(raw_key)
    elif kind=='unavailable':item['字段可用性']={key:False}
    elif kind=='invalid':item['原始字段'][raw_key]=float('nan')
    rows=[item,item] if kind=='ambiguous' else [item]
    session={'simulation_time':'2013-05-23T'+clock,'lines':rows}
    stats=stats_from_session(session,(route(1,888),))[1]
    assert stats.passengers==(0 if kind=='zero' else None)
    assert stats.passenger_source==source


@pytest.mark.parametrize('clock',(None,'','bad','2013-05-23'))
def test_unknown_save_time_never_guesses_passenger_source(clock):
    item=line(1,[],平均客流=123)
    session={'simulation_time':clock,'lines':[item]}
    snapshot=MapSnapshot(routes=(route(1,888),))
    query=MapQuery(snapshot,stats_from_session(session,snapshot.routes))
    assert query.stats[1].passengers is None and query.stats[1].passenger_source is None
    assert query.panel_options(session)['passenger_source'] is None
    assert query.select({'color_by':'passengers'}).route_colors[1]=='#98A8B9'


@pytest.mark.parametrize('value',(None,'0','12人次',True,-1,float('nan')))
def test_average_requires_existing_numeric_daily_average_not_display_text(value):
    item=line(1,[],平均客流=value)
    session={'simulation_time':'2013-05-23T12:00:00','lines':[item]}
    assert stats_from_session(session,(route(1),))[1].passengers is None


def test_metric_choices_are_exclusive_and_survive_option_refresh():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QSignalSpy
    from map_panels import MapPanelSet
    app=QApplication.instance() or QApplication([])
    panel=MapPanelSet();query=MapQuery(MapSnapshot(routes=(route(1),)),
        {1:RouteStats(passengers=3000,average_interval_minutes=12.5,daytime_interval_minutes=12.5)})
    panel.set_options(query.panel_options());spy=QSignalSpy(panel.stateChanged)
    for mode in ('interval','passengers'):
        panel.controls['color_by'].buttons[mode].click()
        assert panel.state()['color_by']==mode
        assert sum(button.isChecked() for button in panel.controls['color_by'].buttons.values())==1
        assert query.select(panel.state()).route_colors[1]==semantic_colors.metric_color(
            mode,12.5 if mode=='interval' else 3000)
        panel.set_options(query.panel_options(state=panel.state()))
        assert panel.state()['color_by']==mode
    assert spy.count()==2
    panel.panels['display'].deleteLater();app.processEvents()


def test_opening_sort_metadata_retains_native_seconds_and_empty_schedule_keeps_zero():
    item=line(1,[])
    item['原始字段']['开线日期']='2013-04-10 05:47:38'
    item['原始字段']['时刻表数']=0  # Confirmed native empty, not a missing exported table.
    session={'simulation_time':'2013-05-23T12:00:00','lines':[item]}
    stats=stats_from_session(session,(route(1),))[1]
    assert stats.opened_at=='2013-04-10T05:47:38'
    assert stats.scheduled_departures==0 and stats.average_interval_minutes is None
    item['字段可用性']={'开线日期':False}
    assert stats_from_session(session,(route(1),))[1].opened_at is None


def test_small_interval_representatives_and_yellow_green_are_visibly_distinct():
    def rgb(value):
        color=semantic_colors.metric_color('interval',value)
        return tuple(int(color[i:i+2],16) for i in (1,3,5))
    for low,high in ((5,7.5),(7.5,12.5),(12.5,17.5),(17.5,25)):
        assert max(abs(a-b) for a,b in zip(rgb(low),rgb(high)))>=64  # At least one-quarter of an 8-bit channel.
    yellow,green=rgb(17.5),rgb(25)
    assert yellow[0]>green[0] and green[1]>green[0]
