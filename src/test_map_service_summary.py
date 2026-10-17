"""Saved service windows retain masks, native endpoints, gaps and missing state."""
from dataclasses import replace
import pytest
from map_model import MapRoute, RouteService, ServiceTimetable

H=36_000_000_000


def table(mask,start,end,interval=H):
    return ServiceTimetable(mask,start*H,end*H,interval,tuple(range(start*H,end*H+1,interval)))


def summary(tables,**flags):
    from map_service_time import operating_time_text
    route=MapRoute(1,'X',1,'a','A','bus',(),(),service=RouteService(
        flags.get('active',True),flags.get('complete',True),tables))
    return operating_time_text({},1,route=route)


def test_identical_weekday_weekend_times_collapse_without_redundant_labels():
    assert summary((table(62,6,22),table(65,6,22)))=='06:00-22:00'


def test_split_service_preserves_short_shutdown_gap_and_actual_last_departure():
    morning=replace(table(127,6,9),end_tick=10*H)
    afternoon=replace(table(127,10,22),departure_ticks=tuple(range(10*H+H//2,22*H+1,H)))
    assert summary((morning,afternoon))=='06:00-09:00、10:30-21:30'


def test_overlapping_native_templates_merge_only_their_actual_windows():
    assert summary((table(127,6,12),table(127,10,22)))=='06:00-22:00'


def test_exact_saved_weekdays_and_cross_midnight_are_not_relabelled_as_workdays():
    assert summary((table(2,23,25),))=='周一23:00-次日01:00，周二、周三、周四、周五、周六、周日停运'
    assert summary((table(-2147483647,6,8),))=='周一、周二、周三、周四、周五、周六停运，周日06:00-08:00'


@pytest.mark.parametrize('tables,flags,want',[
    (None,{},'—'),((),{},'停运'),((table(0,6,22),),{},'停运'),
    ((table(127,6,22),),{'active':False},'停运'),
    ((table(127,6,22),),{'complete':False},'停运'),
    ((table(127,6,22),),{'active':None},'—'),
    ((replace(table(127,6,22),departure_ticks=None),),{},'—'),
    ((replace(table(127,6,22),departure_ticks=(6*H,None)),),{},'—'),
    ((replace(table(127,6,22),active_days=None),),{},'—'),
    ((replace(table(127,6,22),departure_ticks=()),),{},'停运'),
])
def test_unknown_and_confirmed_no_service_remain_distinct(tables,flags,want):
    assert summary(tables,**flags)==want


def test_saved_session_template_metadata_is_used_without_presentation_group_duplication():
    from map_service_time import operating_time_text
    rows=[{'时刻表序号':1,'发班序号':i,'发班_tick':t*H,
           '时刻表原始字段':{'运行日掩码':127,'开始_tick':6*H,'结束_tick':22*H,'间隔_tick':H}}
          for i,t in enumerate(range(6,23))]
    line={'对象ID':1,'原始字段':{'m_active':True,'m_complete':True},
          '时刻表':{'weekday':{'entries':rows},'weekend':{'entries':rows}}}
    session={'lines':[line]}
    assert operating_time_text(session,1)=='06:00-22:00'
    line['原始字段'].pop('m_active')
    assert operating_time_text(session,1)=='—'
