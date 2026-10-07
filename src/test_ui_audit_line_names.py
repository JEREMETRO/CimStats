"""Display-only numbering and mode disambiguation; original rows remain intact."""
import copy
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from line_query_page import line_display_value
from test_line_query_layout import lines_window


def line(mode,name,company='company-a',number=1,key=None):
    return {'key':key or f'{company}|{mode}|{name}', '公司标识':company,
            '公司名称':'公司', '运输制式':mode, '线路号':number, '线路名称':name}


def name(row,all_lines):
    return line_display_value(row,'线路名称',all_lines)


def test_same_company_cross_mode_numbered_names_are_disambiguated_without_mutating_rows():
    rows=[line('公交','1路'),line('有轨电车','1号线'),line('水上巴士','1')]
    originals=copy.deepcopy(rows)
    assert [name(row,rows) for row in rows]==['1路','有轨电车1号线','水上巴士1号线']
    assert rows==originals


@pytest.mark.parametrize('mode',['地铁','单轨'])
@pytest.mark.parametrize('raw',['1','1路','1号线'])
def test_unique_rail_numbers_use_numbered_line_form_without_mode_prefix(mode,raw):
    row=line(mode,raw,number=99)
    assert name(row,[row])=='1号线', 'name number must not be invented from a different raw ID'


@pytest.mark.parametrize('mode',['有轨电车','无轨电车','水上巴士'])
@pytest.mark.parametrize('raw,expected',[('101','101路'),('101路','101路'),('101号线','101号线')])
def test_unique_non_rail_routes_keep_existing_route_suffix(mode,raw,expected):
    row=line(mode,raw,number=99)
    assert name(row,[row])==expected


@pytest.mark.parametrize('raw',['1','1路','1号线','公交1路'])
def test_bus_retains_route_form_and_permitted_mode_omission(raw):
    row=line('公交',raw)
    assert name(row,[row,line('有轨电车','1')])=='1路'


def test_numbered_mode_prefixes_are_not_duplicated():
    rows=[line('公交','1路'),line('地铁','地铁1号线'),line('单轨列车','单轨1路')]
    assert [name(row,rows) for row in rows]==['1路','地铁1号线','单轨1号线']


def test_existing_monorail_alias_is_normalized_once():
    rows=[line('公交','1路'),line('单轨列车','单轨列车1路')]
    assert name(rows[1],rows)=='单轨1号线'


def test_collision_context_keeps_other_modes_even_if_the_table_filter_hides_them():
    tram=line('有轨电车','1路')
    full_set=[line('公交','1号线'),tram]
    assert name(tram,full_set)=='有轨电车1号线'
    assert name(tram,[tram])=='1路'


def test_same_number_across_companies_uses_existing_company_context():
    bus=line('公交','1路','company-a')
    tram=line('有轨电车','1路','company-b')
    assert bus['公司名称']==tram['公司名称']
    assert name(bus,[bus,tram])=='1路'
    assert name(tram,[bus,tram])=='1路'


def test_same_mode_duplicates_do_not_get_fabricated_numbers_or_company_suffixes():
    rows=[line('地铁','1','company-a',key='one'),line('地铁','1路','company-a',key='two')]
    assert [name(row,rows) for row in rows]==['1号线','1号线']
    assert [row['key'] for row in rows]==['one','two']


@pytest.mark.parametrize('custom',['机场快线','1路·机场快线','1路-快线','5P（早高峰）','环城3号观光线','1号线支线'])
def test_real_custom_names_are_not_rewritten_just_because_they_contain_numbers(custom):
    row=line('地铁',custom)
    assert name(row,[line('公交','1路'),row])==custom


def test_number_letter_routes_keep_bus_code_and_disambiguate_other_modes():
    rows=[line('公交','812E'),line('有轨电车','812E号线')]
    assert [name(row,rows) for row in rows]==['812E','有轨电车812E号线']


def test_missing_name_uses_real_number_with_mode_appropriate_suffix():
    row=line('地铁','',number=17)
    assert name(row,[row])=='17号线'


def test_model_preformatted_custom_name_stays_untouched():
    from display_rules import format_line_name
    raw=format_line_name(17,'机场快线')
    row=line('地铁',raw,number=17)
    assert name(row,[row])==raw=='17路·机场快线'


def test_default_display_value_keeps_export_and_legacy_callers_unchanged():
    row=line('地铁','1路')
    assert line_display_value(row,'线路名称')=='1路'
    row['字段可用性']={'线路名称':False}
    assert name(row,[row]) is None


def test_query_list_detail_footer_and_search_use_full_save_collision_context(lines_window):
    w=lines_window
    base=copy.deepcopy(w.data['lines'][0])
    rows=[]
    for mode,raw,key in [('公交','1路','bus-one'),('有轨电车','1号线','tram-one'),
                         ('水上巴士','1','ferry-one'),('无轨电车','101路','trolley-101')]:
        row=copy.deepcopy(base)
        row.update(key=key,运输制式=mode,线路名称=raw,线路号=1)
        rows.append(row)
    originals=copy.deepcopy(rows)
    w.data['lines']=rows
    w._selected_line=None;w.selected_key=''
    w.refresh_lines();QTest.qWait(50)
    displayed={w.line_table.item(i,0).data(Qt.ItemDataRole.UserRole):w.line_table.item(i,2).text()
               for i in range(w.line_table.rowCount())}
    assert displayed=={'bus-one':'1路','tram-one':'有轨电车1号线','ferry-one':'水上巴士1号线',
                      'trolley-101':'101路'}
    index=next(i for i in range(w.line_table.rowCount())
               if w.line_table.item(i,0).data(Qt.ItemDataRole.UserRole)=='tram-one')
    QTest.mouseClick(w.line_table.viewport(),Qt.MouseButton.LeftButton,
                     pos=w.line_table.visualItemRect(w.line_table.item(index,2)).center())
    QTest.qWait(20)
    assert w.selected_key=='tram-one'
    assert w.detail_title.text()==f"有轨电车1号线 · {base['公司名称']}"
    assert w.lines_page.list_footer.text()=='选中：有轨电车1号线'
    w.line_mode.setCurrentText('有轨电车');QTest.qWait(20)
    assert w.line_table.rowCount()==1
    assert w.line_table.item(0,2).text()=='有轨电车1号线'
    w.lines_page.query.setText('有轨电车1号线');QTest.qWait(20)
    assert w.line_table.rowCount()==1
    assert w.line_table.item(0,0).data(Qt.ItemDataRole.UserRole)=='tram-one'
    w.line_mode.setCurrentText('无轨电车')
    w.lines_page.query.setText('101路');QTest.qWait(20)
    assert w.line_table.rowCount()==1
    assert w.line_table.item(0,2).text()=='101路'
    QTest.mouseClick(w.line_table.viewport(),Qt.MouseButton.LeftButton,
                     pos=w.line_table.visualItemRect(w.line_table.item(0,2)).center())
    QTest.qWait(20)
    assert w.selected_key=='trolley-101'
    assert w.detail_title.text()==f"101路 · {base['公司名称']}"
    assert w.lines_page.list_footer.text()=='选中：101路'
    assert w.data['lines']==originals
