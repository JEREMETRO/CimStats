"""Persistent single-line browser contracts; fixture catalogs are synthetic."""
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy,QTest
import pytest


def routes(count=3):
    return [dict(id=100+i,name=f'{i+1}路',number=i+1,mode='bus',company_id='private-owner',
                 company_name='公司甲',selectable=i!=2) for i in range(count)]


def panel(app,count=3):
    from map_preset_panels import SingleLineListPanel
    p=SingleLineListPanel();p.resize(360,550);p.set_routes(routes(count));p.show();app.processEvents()
    return p


def test_browser_defaults_to_full_persistent_catalog_with_shared_labels(qt_application):
    p=panel(qt_application);spy=QSignalSpy(p.routeSelected)
    assert p.search.text()=='' and p.route_list.isVisible() and p.route_list.count()==3
    assert p.route_list.item(0).text()=='公交1路'
    assert p.route_list.item(0).font().pixelSize()==14 and not p.route_list.item(0).icon().isNull()
    assert all('\n' not in p.route_list.item(i).text() and p.route_list.item(i).toolTip()=='' for i in range(3))
    p.set_state({'selected_route_id':101})
    assert p.state()=={'selected_route_id':101,'sort_by':'name','sort_desc':False} and spy.count()==0
    assert p.route_list.currentItem().data(Qt.ItemDataRole.UserRole)==101
    assert p.route_list.height()>400


def test_mouse_activation_emits_stable_id_and_browser_remains_visible(qt_application):
    p=panel(qt_application);spy=QSignalSpy(p.routeSelected)
    item=p.route_list.item(1)
    QTest.mouseClick(p.route_list.viewport(),Qt.MouseButton.LeftButton,pos=p.route_list.visualItemRect(item).center())
    assert spy.count()==1 and spy.at(0)[0]==101 and p.state()['selected_route_id']==101
    assert p.route_list.isVisible() and p.route_list.count()==3


def test_arrow_then_enter_confirms_item_and_unique_search_enter_stays_browsable(qt_application):
    p=panel(qt_application);spy=QSignalSpy(p.routeSelected)
    p.route_list.setCurrentRow(0);p.route_list.setFocus()
    QTest.keyClick(p.route_list,Qt.Key.Key_Down);assert spy.count()==0
    QTest.keyClick(p.route_list,Qt.Key.Key_Return)
    assert spy.count()==1 and spy.at(0)[0]==101
    p.search.setText('1路');QTest.keyClick(p.search,Qt.Key.Key_Return)
    assert spy.count()==2 and spy.at(1)[0]==100 and p.route_list.isVisible()
    assert p.search.text()=='1路'
    p.search.clear();assert p.route_list.count()==3 and p.route_list.isVisible()


def test_ambiguous_search_highlights_first_available_then_enter_confirms(qt_application):
    p=panel(qt_application);spy=QSignalSpy(p.routeSelected)
    p.search.setText('公交');QTest.keyClick(p.search,Qt.Key.Key_Return);qt_application.processEvents()
    assert spy.count()==0 and p.route_list.hasFocus()
    assert p.route_list.currentItem().data(Qt.ItemDataRole.UserRole)==100
    QTest.keyClick(p.route_list,Qt.Key.Key_Return)
    assert spy.count()==1 and spy.at(0)[0]==100 and p.route_list.isVisible()


def test_unavailable_route_is_named_disabled_and_cannot_emit(qt_application):
    p=panel(qt_application);spy=QSignalSpy(p.routeSelected)
    item=p.route_list.item(2)
    assert item.text()=='公交3路' and not item.flags()&Qt.ItemFlag.ItemIsEnabled
    assert item.data(Qt.ItemDataRole.AccessibleDescriptionRole)=='无地图路径'
    QTest.mouseClick(p.route_list.viewport(),Qt.MouseButton.LeftButton,pos=p.route_list.visualItemRect(item).center())
    p.search.setText('3路');QTest.keyClick(p.search,Qt.Key.Key_Return)
    assert spy.count()==0 and p.state()['selected_route_id'] is None and p.route_list.isVisible()


def test_collision_names_resolve_from_complete_catalog_even_after_search(qt_application):
    from map_preset_panels import SingleLineListPanel
    catalog=[dict(id=4,name='1路',number=1,mode='bus',company_id='private-a',company_name='公司甲',selectable=True),
             dict(id=9,name='1路',number=1,mode='bus',company_id='private-b',company_name='公司乙',selectable=True)]
    p=SingleLineListPanel();p.set_routes(catalog)
    assert [p.route_list.item(i).text() for i in range(2)]==['公司甲公交1路','公司乙公交1路']
    p.search.setText('公司乙');assert p.route_list.count()==1 and p.route_list.item(0).text()=='公司乙公交1路'


def test_revisit_with_same_catalog_preserves_query_selection_scroll_and_items(qt_application):
    p=panel(qt_application,80);spy=QSignalSpy(p.routeSelected)
    p.search.setText('公交');p.set_state({'selected_route_id':120})
    item=p.route_list.currentItem();bar=p.route_list.verticalScrollBar();bar.setValue(bar.maximum()//2)
    before=bar.value();assert before>0
    p.hide();p.set_routes(routes(80));p.set_state({'selected_route_id':120});p.show();qt_application.processEvents()
    assert p.search.text()=='公交' and p.route_list.currentItem() is item
    assert bar.value()==before and spy.count()==0 and p.route_list.isVisible()


def test_replacement_catalog_cannot_activate_stale_same_name_identity(qt_application):
    p=panel(qt_application);p.set_state({'selected_route_id':100});spy=QSignalSpy(p.routeSelected)
    p.set_routes([dict(routes()[0],id=900)]);p.search.setText('1路')
    QTest.keyClick(p.search,Qt.Key.Key_Return)
    assert spy.count()==1 and spy.at(0)[0]==900
    copied=p.state();copied['selected_route_id']=777
    assert p.state()['selected_route_id']==900


def test_empty_catalog_has_no_stale_selection_or_activation(qt_application):
    p=panel(qt_application);p.set_state({'selected_route_id':100});p.set_routes([]);spy=QSignalSpy(p.routeSelected)
    QTest.keyClick(p.search,Qt.Key.Key_Return)
    assert p.route_list.count()==0 and p.route_list.currentItem() is None and spy.count()==0


def test_reconfirming_current_route_still_requests_information_navigation(qt_application):
    p=panel(qt_application);p.set_state({'selected_route_id':101});spy=QSignalSpy(p.routeSelected)
    QTest.keyClick(p.route_list,Qt.Key.Key_Return)
    assert spy.count()==1 and spy.at(0)[0]==101 and p.route_list.isVisible()


def test_browser_preserves_non_numeric_stable_identity_without_exposing_it(qt_application):
    from map_preset_panels import SingleLineListPanel
    p=SingleLineListPanel();identity='stable-private-line-42'
    p.set_routes([dict(routes()[0],id=identity)]);p.resize(360,550);p.show();qt_application.processEvents()
    spy=QSignalSpy(p.routeSelected);QTest.keyClick(p.search,Qt.Key.Key_Return)
    assert spy.count()==1 and spy.at(0)[0]==identity
    assert p.route_list.item(0).text()=='公交1路' and p.state()['selected_route_id']==identity


def test_revisited_setter_restores_active_route_after_unconfirmed_keyboard_browse(qt_application):
    p=panel(qt_application);p.set_state({'selected_route_id':101});spy=QSignalSpy(p.routeSelected)
    p.route_list.setCurrentRow(0)
    p.hide();p.set_state({'selected_route_id':101});p.show();qt_application.processEvents()
    assert p.route_list.currentItem().data(Qt.ItemDataRole.UserRole)==101 and spy.count()==0


def sorting_routes():
    # Metadata is supplied by the catalog, never inferred from the visible text.
    return [dict(routes()[0], id=1, name='10路', opened_at='2013-05-03', passengers=12, scheduled_departures=5),
            dict(routes()[0], id=2, name='2路', mode='tram', opened_at='2013-05-01', passengers=0, scheduled_departures=0),
            dict(routes()[0], id=3, name='7路', opened_at='2013-05-02', passengers=50, scheduled_departures=9),
            dict(routes()[0], id=4, name='11路', mode=None, opened_at=None, passengers=None, scheduled_departures=None),
            dict(routes()[0], id=5, name='20路', mode='', opened_at='invalid', passengers=float('nan'), scheduled_departures=-1)]


@pytest.mark.parametrize('key,ascending,descending', [
    ('mode', [3,1,2,4,5], [2,3,1,4,5]),
    ('name', [2,3,1,4,5], [5,4,1,3,2]),
    ('opened_at', [2,3,1,4,5], [1,3,2,4,5]),
    ('passengers', [2,1,3,4,5], [3,1,2,4,5]),
    ('scheduled_departures', [2,1,3,4,5], [3,1,2,4,5]),
])
def test_browser_sorts_supplied_metadata_naturally_with_unknowns_always_last(qt_application,key,ascending,descending):
    from map_preset_panels import SingleLineListPanel
    p=SingleLineListPanel();p.set_routes(sorting_routes());spy=QSignalSpy(p.routeSelected)
    p.set_state({'selected_route_id':3,'sort_by':key,'sort_desc':False})
    def ids():return [p.route_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(p.route_list.count())]
    assert ids()==ascending
    p.sort_order_button.click()
    assert ids()==descending and p.state()['sort_desc'] is True
    assert p.route_list.currentItem().data(Qt.ItemDataRole.UserRole)==3 and spy.count()==0


def test_sort_controls_keep_search_active_identity_items_and_a_visible_scroll_anchor(qt_application):
    p=panel(qt_application,80);p.search.setText('公交');p.set_state({'selected_route_id':120})
    spy=QSignalSpy(p.routeSelected);item=p.route_list.currentItem()
    bar=p.route_list.verticalScrollBar();bar.setValue(bar.maximum()//2);qt_application.processEvents()
    from PySide6.QtCore import QPoint
    anchor=p.route_list.itemAt(QPoint(10,10));assert anchor is not None
    anchor_id=anchor.data(Qt.ItemDataRole.UserRole)
    p.sort_order_button.click();qt_application.processEvents()
    assert p.search.text()=='公交' and p.route_list.currentItem() is item and spy.count()==0
    assert p.route_list.itemAt(QPoint(10,10)).data(Qt.ItemDataRole.UserRole)==anchor_id
    assert 0<bar.value()<=bar.maximum()
    saved=p.state();p.hide();p.set_routes(routes(80));p.set_state(saved);p.show();qt_application.processEvents()
    assert p.route_list.currentItem() is item and p.state()==saved and spy.count()==0


def test_sort_selector_switches_metadata_without_changing_route_selection(qt_application):
    from map_preset_panels import SingleLineListPanel
    p=SingleLineListPanel();p.set_routes(sorting_routes());p.set_state({'selected_route_id':3})
    spy=QSignalSpy(p.routeSelected)
    p.sort_combo.setCurrentIndex(p.sort_combo.findData('opened_at'))
    assert p.state()['sort_by']=='opened_at'
    assert [p.route_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(5)]==[2,3,1,4,5]
    assert p.route_list.currentItem().data(Qt.ItemDataRole.UserRole)==3 and spy.count()==0


def test_browser_numeric_search_ignores_stable_ids_company_digits_and_numeric_facts(qt_application):
    from map_preset_panels import SingleLineListPanel
    p=SingleLineListPanel();p.set_routes([
        dict(routes()[0],id=701,name='2路',number=2,company_name='公司7',opened_at='2013-07-01',passengers=777,scheduled_departures=7,display_label='公司7公交2路'),
        dict(routes()[0],id=9,name='7路',number=7,company_name='公司甲',display_label='公交7路')])
    p.search.setText('7')
    assert p.route_list.count()==1 and p.route_list.item(0).data(Qt.ItemDataRole.UserRole)==9
    p.search.setText('公司7')
    assert p.route_list.count()==1 and p.route_list.item(0).data(Qt.ItemDataRole.UserRole)==701
