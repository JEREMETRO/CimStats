"""Profit classification tolerance shares one source across filters and colours."""
from copy import deepcopy
import pytest
from map_model import MapRoute,MapSnapshot
from map_query import MapQuery,RouteStats,stats_from_session
from semantic_colors import color_for

ROUTE=MapRoute(1,'1',1,'a','Alpha','bus',(),(((0.,0.,0.),(100.,0.,0.)),))

def session(income,expense,**extra):
    return {'simulation_time':'2013-05-23T12:00:00','lines':[{'对象ID':1,
        '原始字段':{'收入_累计':income,'支出_累计':expense},**extra}]}


@pytest.mark.parametrize('income,expense,status',[
    (102,100,'zero'),(98,100,'zero'),(101,100,'zero'),(99,100,'zero'),
    (102.1,100,'profit'),(97.9,100,'loss'),(100,100,'zero'),
    (0,0,'zero'),(1,0,'profit'),(-1,0,'loss'),
    (153,150,'zero'),(147,150,'zero'),(51000000,50000000,'zero'),
])
def test_tolerance_boundary_filter_and_map_share_status_without_changing_profit(income,expense,status):
    source=session(income,expense);before=deepcopy(source)
    stats=stats_from_session(source,(ROUTE,));data=stats[1]
    assert data.profit==(income-expense)/102400
    assert data.expense==expense/102400 and data.profit_status==status
    query=MapQuery(MapSnapshot(routes=(ROUTE,)),stats)
    state={'profit_statuses':[status],'color_by':'profit'}
    result=query.select(state)
    assert [r.id for r in result.routes]==[1]
    assert result.route_colors[1]==color_for('profit',status)
    assert query.panel_options(source)['lines'][0]['profit']==status
    assert source==before


@pytest.mark.parametrize('key,value',[
    ('收入_累计',None),('支出_累计',None),('收入_累计',True),('支出_累计',False),
    ('收入_累计',float('nan')),('支出_累计',float('inf')),('支出_累计',-1),
])
def test_missing_or_invalid_native_finance_never_becomes_known_profit(key,value):
    source=session(100,100);source['lines'][0]['原始字段'][key]=value
    stats=stats_from_session(source,(ROUTE,))[1]
    assert stats.profit is None and stats.profit_status=='missing'


@pytest.mark.parametrize('key',('收入_累计','支出_累计'))
def test_explicit_native_availability_false_keeps_finance_missing(key):
    data=stats_from_session(session(100,100,字段可用性={key:False}),(ROUTE,))[1]
    assert data.profit is None and data.profit_status=='missing'


def test_unknown_duplicate_identity_never_uses_a_last_row_financial_counter():
    source=session(100,100);source['lines'].append(deepcopy(source['lines'][0]))
    data=stats_from_session(source,(ROUTE,))[1]
    assert data.profit is None and data.expense is None and data.profit_status=='missing'


def test_expense_is_appended_and_manual_legacy_values_keep_sign_fallback():
    assert RouteStats(100,5).profit_status=='profit'
    assert RouteStats(100,-5).profit_status=='loss'
    assert RouteStats(100,0).profit_status=='zero'
    assert RouteStats(100,None).profit_status=='missing'
    assert RouteStats(100,5,expense=1000).profit_status=='zero'
    assert RouteStats(profit=float('nan')).profit_status=='missing'
