"""Preset widgets: real Qt interactions and selection identity contracts."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QWidget

from map_model import MapRoute, RouteDirection


def routes():
    path = (((0., 0., 0.), (100., 0., 0.)),)
    return [MapRoute(12, '12 中央线', 12, 'a', '同名公司', 'bus', (), path,
                     RouteDirection('roundtrip'), depot_paths=path),
            MapRoute(23, '23 环线', 23, 'b', '同名公司', 'tram', (), path,
                     RouteDirection('ring')),
            MapRoute(34, '34 无地图路径', 34, 'c', '公司丙', 'bus', (), ())]


def test_single_defaults_direction_geometry_and_only_whole_fallback_duration(qt_application):
    from map_preset_panels import SingleLinePanel
    p = SingleLinePanel()
    facts = SimpleNamespace(duration_minutes=83.599, transported_today=0, scheduled_departures=None)
    p.set_routes(routes()); p.set_route(routes()[0], facts, 2.345, .654)
    assert p.state()['direction'] == 'up' and not p.state()['deadhead']
    assert p.fact_labels['geometry_km'].text() == '2.34 km'
    assert p.fact_labels['duration_minutes'].text() == '—'
    assert p.fact_labels['transported_today'].text() == '0 人次'
    assert p.fact_labels['scheduled_departures'].text() == '—'
    before = [p.fact_labels[k].text() for k in ('transported_today', 'scheduled_departures')]
    spy = QSignalSpy(p.directionChanged)
    p.direction_buttons['both'].click(); p.deadhead_check.click()
    assert spy.at(0)[0] == 'whole'
    assert p.fact_labels['geometry_km'].text() == '2.99 km'
    assert p.fact_labels['duration_minutes'].text() == '83.59 分钟'
    assert [p.fact_labels[k].text() for k in ('transported_today', 'scheduled_departures')] == before
    p.set_route(routes()[1], facts, 3., None)
    assert all(not b.isEnabled() for b in p.direction_buttons.values())
    assert not p.deadhead_check.isEnabled()


def test_single_search_is_full_catalog_and_unavailable_path_cannot_select(qt_application):
    from map_preset_panels import SingleLinePanel
    p = SingleLinePanel(); spy = QSignalSpy(p.routeSelected)
    p.set_routes(routes()); p.set_state({'selected_route_id': 12})
    assert spy.count() == 0
    assert p.route_list.item(0).text()=='公交12 中央线'
    p.search.setText('23'); assert p.route_list.count() == 1
    p.route_list.setCurrentRow(0); p.route_list.itemActivated.emit(p.route_list.item(0))
    assert spy.at(0)[0] == 23
    p.search.setText('34'); item = p.route_list.item(0)
    assert not item.flags() & Qt.ItemFlag.ItemIsEnabled
    p.route_list.itemActivated.emit(item); assert spy.count() == 1


def test_planning_main_and_menu_share_selection_scoped_to_search(qt_application):
    from map_preset_panels import PlanningPanel
    host = QWidget(); host.resize(960, 680); host.show()
    p = PlanningPanel(host); p.set_popup_host(host)
    p.set_routes(routes(), {99}); spy = QSignalSpy(p.selectionChanged)
    p.open_building_menu({'id': 1, 'name': '中央大厦'}, routes(), {99}, host.mapToGlobal(QPoint(930, 640)), source_known=True)
    menu = p.building_menu; menu.search.setText('12'); menu.select_all.click()
    assert p.state()['selected_line_ids'] == {12, 99}
    assert spy.at(0)[0] == {12, 99}
    spy.at(0)[0].add(777); assert 777 not in p.state()['selected_line_ids']
    menu.search.setText('23'); menu.select_all.click()
    menu.search.setText('12'); menu.clear_selection.click()
    assert p.state()['selected_line_ids'] == {23, 99}
    p.search.setText('23'); p.clear_selection.click()
    assert p.state()['selected_line_ids'] == {99}
    assert menu.line_list.item(0).checkState() == Qt.CheckState.Unchecked
    menu.close_button.click()
    p.open_building_menu({'id': 2, 'name': '另一建筑'}, [routes()[1]], {99}, host.mapToGlobal(QPoint(10, 10)), source_known=True)
    assert p.state()['selected_line_ids'] == {99}
    assert p.state()['building_emphasis'] is True
    assert menu.parentWidget() is host and not menu.isWindow()
    assert host.rect().contains(menu.geometry())


def test_planning_native_unknown_empty_unresolved_and_unavailable_are_distinct(qt_application):
    from map_preset_panels import PlanningPanel
    host = QWidget(); host.resize(960, 680); host.show()
    p = PlanningPanel(host); p.set_routes(routes(), set())
    p.open_building_menu({'name': '建筑'}, None, set(), host.mapToGlobal(QPoint(30, 30)))
    m = p.building_menu
    assert m.status_label.text() == '线路信息暂不可用'
    assert m.line_list.count() == 0 and not m.select_all.isEnabled()
    p.open_building_menu({'name': '建筑','service_lines':{'known':True,'complete':True,'route_ids':(),'unresolved_refs':()}}, [], set(), host.mapToGlobal(QPoint(30, 30)), source_known=True)
    assert m.status_label.text() == '无服务线路'
    p.open_building_menu({'name': '建筑'}, [routes()[2], routes()[2]], set(), host.mapToGlobal(QPoint(30, 30)), source_known=True, unresolved_refs=(808, 808))
    assert m.line_list.count() == 1
    assert '无地图路径' in m.line_list.item(0).text()
    assert m.source_unresolved_refs == (808,) and m.status_label.text()=='线路信息暂不可用'
    assert all(not m.line_list.item(i).flags() & Qt.ItemFlag.ItemIsEnabled for i in range(m.line_list.count()))
    m.select_all.click(); assert p.state()['selected_line_ids'] == set()


def test_unknown_menu_before_catalog_load_has_no_active_bulk_actions(qt_application):
    from map_preset_panels import PlanningPanel
    host = QWidget(); host.resize(960, 680); host.show()
    p = PlanningPanel(host)
    p.open_building_menu({'name': '建筑'}, None, set(), host.mapToGlobal(QPoint(20, 20)))
    assert not p.building_menu.select_all.isEnabled()
    assert not p.building_menu.clear_selection.isEnabled()


def test_silent_setters_preserve_planning_emphasis_and_classes(qt_application):
    from map_preset_panels import PlanningPanel
    p = PlanningPanel(); selection = QSignalSpy(p.selectionChanged)
    view = QSignalSpy(p.buildingViewChanged); classes = QSignalSpy(p.buildingClassesChanged)
    p.set_options({'building_classes': [{'id': 'Student', 'name': '学生', 'color': '#0067C0'}, {'id': 'BlueCollar', 'name': '工人', 'color': '#00AA00'}]})
    p.set_state({'selected_line_ids': {12}, 'building_view': 'work', 'building_classes': set()})
    p.set_routes(routes(), {12})
    assert selection.count() == view.count() == classes.count() == 0
    assert p.state()['building_classes'] == set()
    p.building_view_buttons['leisure'].click(); assert view.at(0)[0] == 'leisure'
    p.class_grid.buttons['Student'].click(); assert classes.at(0)[0] == {'Student'}
    p.emphasis_check.click(); p.set_routes(routes(), {23})
    assert p.state()['building_emphasis'] is False
    assert not any(w.toolTip() for w in p.findChildren(QWidget))


def test_planning_none_classes_initializes_all_without_erasing_explicit_empty(qt_application):
    from map_preset_panels import PlanningPanel
    p = PlanningPanel(); p.set_options({'building_classes': [{'id': 'Student', 'name': '学生'}, {'id': 'BlueCollar', 'name': '工人'}]})
    p.set_state({'building_classes': set()})
    assert not any(b.isChecked() for b in p.class_grid.buttons.values())
    p.set_state({'building_classes': None})
    assert p.state()['building_classes'] == {'Student', 'BlueCollar'}
    assert all(b.isChecked() for b in p.class_grid.buttons.values())


def test_same_catalog_refresh_preserves_item_keyboard_focus_and_scroll(qt_application):
    from map_preset_panels import PlanningPanel
    p = PlanningPanel(); p.resize(360, 680); p.show()
    catalog = [dict(id=i, name=f'{i} 线路', selectable=True) for i in range(100)]
    p.set_routes(catalog, {90}); qt_application.processEvents()
    p.line_list.setCurrentRow(90); p.line_list.setFocus(); p.line_list.scrollToItem(p.line_list.item(90))
    qt_application.processEvents()
    old_item = p.line_list.currentItem(); old_scroll = p.line_list.verticalScrollBar().value()
    p.set_routes([dict(v) for v in catalog], {12, 90}); qt_application.processEvents()
    assert p.line_list.currentItem() is old_item
    assert p.line_list.hasFocus() and p.line_list.verticalScrollBar().value() == old_scroll
    assert p.line_list.item(12).checkState() == Qt.CheckState.Checked
    QTest.keyClick(p.line_list, Qt.Key.Key_Space)
    assert p.state()['selected_ids'] == {12}


def test_popup_keyboard_close_and_containment_after_resize(qt_application):
    from map_preset_panels import PlanningPanel
    host = QWidget(); host.resize(960, 680); host.show()
    p = PlanningPanel(host); p.set_popup_host(host); p.set_routes(routes(), set())
    p.open_building_menu({'name': '建筑'}, routes(), set(), host.mapToGlobal(QPoint(940, 660)), source_known=True)
    m = p.building_menu; qt_application.processEvents()
    host.resize(500, 420); qt_application.processEvents()
    assert host.rect().contains(m.geometry())
    QTest.keyClick(m.search, Qt.Key.Key_Escape)
    assert not m.isVisible() and p.state()['selected_line_ids'] == set()


def test_network_time_uses_simulated_clock_and_valid_cross_midnight(qt_application):
    from map_panels import MapPanelSet
    p = MapPanelSet(); spy = QSignalSpy(p.stateChanged)
    p.set_options({'simulated_datetime': '2030-01-02T23:30:00'})
    assert spy.count() == 0 and p.state()['service_time_mode'] == 'off'
    assert p.controls['service_start'].text() == '23:30'
    p.controls['service_time_mode'].buttons['instant'].click()
    p.filter_apply_buttons['service'].click()
    assert p.state()['service_start'] == '2030-01-02T23:30:00'
    p.controls['service_time_mode'].buttons['range'].click()
    p.controls['service_end'].setText('01:00')
    p.filter_apply_buttons['service'].click()
    assert p.state()['service_time_mode'] == 'range'
    assert p.state()['service_end'] == '2030-01-03T01:00:00'
    before = p.state(); n = spy.count()
    p.controls['service_end'].setText('25:99')
    assert p.state() == before and spy.count() == n and p.service_error.text()
    p.reset_filters.click(); assert p.state()['service_time_mode'] == 'off'


def test_network_result_list_intersects_proven_service_match_and_other_filters(qt_application):
    from map_panels import MapPanelSet
    p = MapPanelSet()
    options = {'simulated_datetime': '2031-02-01T12:00:00', 'modes': [{'id': 'bus', 'name': '公交'}, {'id': 'tram', 'name': '电车'}],
               'lines': [{'id': 1, 'name': '1', 'mode': 'bus', 'service_matches': True},
                         {'id': 2, 'name': '2', 'mode': 'bus', 'service_matches': False},
                         {'id': 3, 'name': '3', 'mode': 'bus', 'service_matches': None},
                         {'id': 4, 'name': '4', 'mode': 'tram', 'service_matches': True}]}
    p.set_options(options)
    p.set_state({'service_time_mode': 'instant', 'service_start': '2031-02-01T12:00:00', 'modes': {'bus'}})
    assert [p.line_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(p.line_list.count())] == [1]
    p.set_state({'service_time_mode': 'range', 'service_start': '2031-02-01T23:00:00', 'service_end': '2031-02-02T01:00:00', 'modes': {'tram'}})
    assert [p.line_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(p.line_list.count())] == [4]
    p.set_state({'service_time_mode': 'off', 'modes': {'bus'}})
    assert p.line_list.count() == 3


def test_network_bulk_selection_keeps_existing_result_items_and_focus(qt_application):
    from map_panels import MapPanelSet
    from map_docking import MapDockHost
    p = MapPanelSet(); p.set_options({'lines': [{'id': 1, 'name': '1'}, {'id': 2, 'name': '2'}]})
    host = MapDockHost(QWidget(), p.panels); host.resize(960, 680); host.show(); host.activate_panel('filters')
    qt_application.processEvents()
    item = p.line_list.item(0); p.line_list.setCurrentItem(item); p.line_list.setFocus()
    qt_application.processEvents(); assert p.line_list.hasFocus()
    p.manual_none.click(); qt_application.processEvents()
    assert p.line_list.item(0) is item and p.line_list.currentItem() is item
    assert p.line_list.hasFocus()
    assert all(p.line_list.item(i).checkState() == Qt.CheckState.Unchecked for i in range(2))
    p.manual_all.click(); assert p.state()['manual_line_ids'] == {1, 2}


def test_candidate_dict_needs_proven_selectable_path(qt_application):
    from map_preset_panels import PlanningPanel
    p = PlanningPanel()
    p.set_routes([{'id': 1, 'name': '无几何记录'}, {'id': 2, 'name': '可靠记录', 'selectable': True}], set())
    p.select_all.click()
    assert p.state()['selected_ids'] == {2}


def test_leg_paths_allow_native_candidate_without_flattened_paths(qt_application):
    from map_preset_panels import PlanningPanel
    from dataclasses import replace
    route = replace(routes()[0], paths=(), leg_paths=((((0., 0., 0.), (100., 0., 0.)),),))
    p = PlanningPanel(); p.set_routes([route], set()); p.select_all.click()
    assert p.state()['selected_ids'] == {12}


def test_single_native_ticks_are_whole_duration_and_selected_row_tracks_setter(qt_application):
    from map_preset_panels import SingleLinePanel
    p = SingleLinePanel(); p.set_routes(routes())
    p.set_route(routes()[1], SimpleNamespace(approved_duration_ticks=49_800_000_000, today_passengers=None, scheduled_departures=0), 0., 0.)
    assert p.fact_labels['duration_minutes'].text() == '83 分钟'
    assert p.fact_labels['transported_today'].text() == '—'
    assert p.fact_labels['scheduled_departures'].text() == '0 班次'
    assert p.route_list.currentItem().data(Qt.ItemDataRole.UserRole) == 23


def test_network_restored_range_and_missing_simulated_clock_do_not_use_wall_clock(qt_application):
    from map_panels import MapPanelSet
    p = MapPanelSet(); spy = QSignalSpy(p.stateChanged)
    p.controls['service_time_mode'].buttons['instant'].click()
    assert p.state()['service_time_mode'] == 'off' and spy.count() == 0
    p.set_state({'service_time_mode': 'range', 'service_start': '2031-02-01T23:00:00', 'service_end': '2031-02-02T01:00:00'})
    p.set_options({})
    assert p.controls['service_start'].text() == '23:00'
    assert p.controls['service_end'].text() == '01:00'
    assert p.state()['service_start'] == '2031-02-01T23:00:00'
    assert p.state()['service_end'] == '2031-02-02T01:00:00'
    assert spy.count() == 0


def test_invalid_restored_time_never_activates_arbitrary_qt_date(qt_application):
    from map_panels import MapPanelSet
    p = MapPanelSet()
    p.set_state({'service_time_mode': 'range', 'service_start': 'bad', 'service_end': '2031-02-02T01:00:00'})
    assert p.state()['service_time_mode'] == 'off'
    assert p.state()['service_start'] is None
    p.set_state({'service_time_mode': 'range', 'service_start': '2031-02-03T01:00:00', 'service_end': '2031-02-02T01:00:00'})
    assert p.state()['service_time_mode'] == 'off'


def test_popup_check_keyboard_scroll_and_outside_click_preserve_other_selection(qt_application):
    from map_preset_panels import PlanningPanel
    from PySide6.QtGui import QWheelEvent
    class Host(QWidget):
        wheels = 0
        def wheelEvent(self, event):
            self.wheels += 1
    host = Host(); host.resize(960, 680); host.show()
    p = PlanningPanel(host); p.set_popup_host(host); p.set_routes(routes(), {99})
    p.open_building_menu({'name': '建筑'}, routes(), {99}, host.mapToGlobal(QPoint(30, 30)), source_known=True)
    m = p.building_menu; qt_application.processEvents()
    m.line_list.setCurrentRow(0); m.line_list.setFocus()
    QTest.keyClick(m.line_list, Qt.Key.Key_Space)
    assert p.state()['selected_ids'] == {12, 99}
    wheel = QWheelEvent(QPoint(5, 5), m.mapToGlobal(QPoint(5, 5)), QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    qt_application.sendEvent(m, wheel)
    assert host.wheels == 0
    QTest.mouseClick(host, Qt.MouseButton.LeftButton, pos=QPoint(900, 600))
    assert not m.isVisible() and p.state()['selected_ids'] == {12, 99}
