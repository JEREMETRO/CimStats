"""Numeric interval mode sources and controls; no rendered-text parsing."""
from copy import deepcopy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from map_model import MapRoute,MapSnapshot
from map_query import MapQuery,RouteStats,stats_from_session
from semantic_colors import metric_color,metric_legend

H=36_000_000_000

def row(index,hour,mask=62,table=1):
    return {'时刻表序号':table,'发班序号':index,'发班_tick':round(hour*H),
            '运行日掩码':mask,'running_day_valid':True}

def native(rows):
    return {'对象ID':1,'班次数据完整':True,'原始字段':{'时刻表数':1},
            '时刻表':{'all':{'entries':rows}},'平均间隔':'999min','高峰':'999min'}

def calculate(rows,day='2013-05-23T12:00:00',**extra):
    item=native(rows);item.update(extra)
    session={'simulation_time':day,'lines':[item]};original=deepcopy(session)
    route=MapRoute(1,'1',1,'a','Alpha','bus',(),(((0.,0.,0.),(100.,0.,0.)),))
    values=stats_from_session(session,(route,));assert session==original
    return values[1],MapQuery(MapSnapshot(routes=(route,)),values)


def test_daytime_excludes_night_gaps_of_confirmed_all_day_service():
    hours=list(range(6))+[5.5+i/6 for i in range(111)]
    stats,query=calculate([row(i,h) for i,h in enumerate(hours)])
    assert stats.daytime_interval_minutes==10
    assert stats.average_interval_minutes>10
    default=query.select({'color_by':'interval'})
    whole=query.select({'color_by':'interval','interval_mode':'all_day'})
    assert default.route_colors[1]==metric_color('interval',10)
    assert whole.route_colors[1]==metric_color('interval',stats.average_interval_minutes)
    assert default.snapshot.routes is whole.snapshot.routes
    assert query.legend_items({'color_by':'interval'}).title=='平均间隔'
    assert query.legend_items({'color_by':'interval','interval_mode':'all_day'}).title=='平均间隔'


def test_non_all_day_keeps_existing_mean_and_missing_is_not_replaced():
    stats,_=calculate([row(1,8),row(2,8.25)])
    assert stats.daytime_interval_minutes==stats.average_interval_minutes==15
    stats,_=calculate([row(1,8)],班次数据完整=False)
    assert stats.daytime_interval_minutes is None and stats.peak_interval_minutes is None


def test_weekday_peak_mean_is_gap_weighted_and_ignores_weekend_even_on_sunday_save():
    rows=[row(1,7.5,2),row(2,7.5+10/60,2),row(3,7.5+20/60,2),
          row(1,17,4,2),row(2,17.5,4,2),
          row(1,8,64,3),row(2,8.01,64,3)]
    stats,query=calculate(rows,day='2013-05-26T12:00:00')
    assert stats.peak_interval_minutes==pytest.approx(50/3)
    assert stats.average_interval_minutes is None  # No Sunday service.
    state={'color_by':'interval','interval_mode':'peak'}
    assert query.select(state).route_colors[1]==metric_color('interval_peak',50/3)
    legend=query.legend_items(state)
    assert legend.title=='平均间隔'
    assert legend.date=='2013-05-26'
    assert legend.labels==('≤3','3–5','5–8','8–12','12–18','18–25','≥25')


def test_peak_never_connects_windows_or_includes_their_endpoints():
    hours=[7.5,7.6,9.4,9.5,17,17.2,19.4,19.5]
    stats,_=calculate([row(i,h) for i,h in enumerate(hours)])
    # Accepted gaps:6,108 in AM and12,132 in PM; never09:30/19:30 or AM→PM.
    assert stats.peak_interval_minutes==pytest.approx((6+108+12+132)/4)


def test_weekend_only_and_unknown_running_days_have_missing_peak_mean():
    stats,_=calculate([row(1,8,64),row(2,8.1,64)])
    assert stats.peak_interval_minutes is None
    unknown=row(3,8.2);unknown['运行日掩码']=None
    stats,_=calculate([row(1,8),row(2,8.1),unknown])
    assert stats.peak_interval_minutes is None


@pytest.mark.parametrize('value,color',[(3,'#350916'),(4,'#E52222'),(6.5,'#FF8A00'),
    (10,'#F3CF32'),(15,'#A6CE39'),(21.5,'#2E8B57'),(25,'#173D6E')])
def test_peak_representative_scale_and_missing(value,color):
    assert metric_color('interval_peak',value)==color
    assert metric_color('interval_peak',None)=='#98A8B9'
    assert metric_color('interval_peak',0)=='#350916'


def test_peak_scale_remains_continuous_at_every_boundary():
    def rgb(value):return tuple(int(metric_color('interval_peak',value)[i:i+2],16) for i in (1,3,5))
    for value in (3,5,8,12,18,25):
        assert max(abs(a-b) for a,b in zip(rgb(value-.0001),rgb(value+.0001)))<=1


def test_secondary_mode_is_default_daytime_exclusive_visible_only_under_interval():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QSignalSpy
    from map_panels import MapPanelSet
    app=QApplication.instance() or QApplication([]);panel=MapPanelSet()
    from map_docking import MapDockHost
    from PySide6.QtWidgets import QWidget
    host=MapDockHost(QWidget(),panel.panels);host.resize(960,680);host.show()
    host.activate_panel('display');app.processEvents()
    combo=panel.controls['interval_mode']
    assert panel.state()['interval_mode']=='daytime' and combo.currentData()=='daytime'
    assert [combo.itemText(i) for i in range(combo.count())]==['日间平均间隔','高峰平均间隔','全日平均间隔']
    assert not combo.isVisible()
    panel.set_state({'color_by':'interval'});app.processEvents();assert combo.isVisible()
    spy=QSignalSpy(panel.stateChanged);combo.setCurrentIndex(1)
    assert panel.state()['interval_mode']=='peak' and spy.count()==1
    panel.set_options({});assert panel.state()['interval_mode']=='peak'
    panel.set_state({'color_by':'passengers'});app.processEvents();assert not combo.isVisible()
    host.close()
