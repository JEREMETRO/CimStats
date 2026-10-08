"""Route searches exclude IDs, dates and unrelated numeric statistics."""
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('query,expected', [('', True), ('7', False), ('77', False),
    ('中央', True), ('公交', True), ('公司七', True), ('7路', False)])
def test_search_uses_only_visible_route_identity(query, expected):
    from line_search import line_matches_search
    record = dict(id=777, name='中央3路', number=3, mode='bus',
                  company_name='公司七', display_label='公交中央3路',
                  opened_at='2017-07-07', passengers=777, color='#1677ff')
    assert line_matches_search(query, record) is expected


def test_numeric_search_does_not_match_company_disambiguation_or_metadata():
    from line_search import line_matches_search
    record = dict(name='中央线', number=3, company_name='交通7公司',
                  display_label='交通7公司 · 公交中央线', id=7)
    assert not line_matches_search('7', record)
    assert line_matches_search('交通7公司', record)
    assert line_matches_search('7', dict(record, number=7))
    assert line_matches_search('7', dict(record, name='中央7路'))


def test_query_names_and_route_codes_remain_searchable():
    from line_search import line_matches_search
    assert line_matches_search('７', {'线路名称': '7路', '线路号': 7})
    assert line_matches_search('503e', {'线路名称': '503E', '线路号': 503})
    assert line_matches_search('7号线', {'线路名称': '默认名称', '线路号': 7}, aliases=('7号线',))


def records():
    return [dict(id=777, name='中央3路', number=3, mode='bus', company_name='八连',
                 company_id='a', display_label='公交中央3路', selectable=True),
            dict(id=20, name='7路', number=7, mode='bus', company_name='八连',
                 company_id='a', display_label='公交7路', selectable=True)]


def test_map_page_search_excludes_partial_object_ids():
    from map_page import MapPage
    owner = SimpleNamespace(query=SimpleNamespace(snapshot=SimpleNamespace(bounds=(0, 0, 100, 100))),
                            _presentation_catalog=records, save_token='test')
    assert [row.id for row in MapPage.search(owner, '7')] == [20]


def test_line_query_search_excludes_dates_and_passenger_numbers():
    from desktop_app import MainWindow
    rows = [dict(key='a', 对象ID=777, 线路名称='3路', 线路号=3,
                 运输制式='公交', 公司名称='八连', 公司标识='a', 今日客流=777, 开线日期='2017-07-07'),
            dict(key='b', 对象ID=20, 线路名称='7路', 线路号=7,
                 运输制式='公交', 公司名称='八连', 公司标识='a')]
    owner = SimpleNamespace(data={'lines': rows}, query=SimpleNamespace(text=lambda: '7'),
        line_company=SimpleNamespace(currentData=lambda: ''),
        line_mode=SimpleNamespace(currentData=lambda: ''), _company_matches=lambda *_: True)
    assert [row['key'] for row in MainWindow.filtered_lines(owner)] == ['b']


def test_network_result_search_uses_the_same_route_names(qt_application):
    from map_panels import MapPanelSet
    panel = MapPanelSet()
    panel.set_options({'lines': records(), 'modes': [{'id': 'bus', 'name': '公交'}]})
    panel.search.setText('7')
    assert panel.line_list.count() == 1
    assert panel.line_list.item(0).text() == '公交7路'
