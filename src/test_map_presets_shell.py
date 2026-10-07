"""Shell regressions: independent state, complete lookup and stale navigation."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path/'presets.ini'), QSettings.Format.IniFormat)

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

# Losing empty selections or importing legacy conditions into single would regress migration.
def test_store_migrates_legacy_only_to_network(settings):
    from map_presets import PresetStore
    settings.setValue('map/query/A', json.dumps({'manual_line_ids': [], 'passenger_min': 15}))
    settings.setValue('map/layout', json.dumps({'group_collapsed': True}))
    store = PresetStore(settings, {'manual_line_ids': None, 'passenger_min': None})
    store.load('A')
    assert store.state('network')['query']['manual_line_ids'] == []
    assert store.state('network')['query']['passenger_min'] == 15
    assert store.state('network')['layout']['group_collapsed'] is True
    assert store.state('single')['query']['direction'] == 'up'
    assert store.state('single')['query']['deadhead'] is False
    assert 'passenger_min' not in store.state('single')['query']
    assert store.state('planning')['query']['building_emphasis'] is True
    assert store.current == 'network'

# A save/preset switch must not retain mutable sets, filters or view from another.
def test_store_roundtrip_separates_save_query_and_preset_view(settings):
    from map_presets import PresetStore
    store = PresetStore(settings, {'manual_line_ids': None})
    store.load('A')
    store.update('single', query={'route_id': 10, 'direction': 'down'}, view=[11, 22, .5])
    store.update('planning', query={'selected_ids': {10, 20}})
    store.activate('planning')
    detached = store.state('planning'); detached['query']['selected_ids'].add(30)
    assert store.state('planning')['query']['selected_ids'] == {10, 20}
    store.load('B')
    assert store.state('single')['query']['route_id'] is None
    assert store.state('planning')['query']['selected_ids'] == []
    store.load('A')
    assert store.state('single')['query']['direction'] == 'down'
    assert store.state('single')['view'] == [11, 22, .5]
    assert set(store.state('planning')['query']['selected_ids']) == {10, 20}
    assert store.current == 'planning'

# Layout reset cannot reset route IDs or camera.
def test_store_layout_reset_and_corrupt_settings(settings):
    from map_presets import PresetStore
    settings.setValue('map/presets/A', '{broken')
    settings.setValue('map/preset', 'invalid')
    store = PresetStore(settings, {})
    store.load('A')
    store.update('single', query={'route_id': 8}, view=[1, 2, 3], layout={'group_collapsed': True})
    store.update('single', layout={})
    assert store.state('single')['query']['route_id'] == 8
    assert store.state('single')['view'] == [1, 2, 3]
    assert store.state('single')['layout'] == {}
    assert store.current == 'network'

def routes():
    from map_model import MapRoute, RouteDirection
    return (
        MapRoute(10, 'Central', 10, 'a', 'Same', 'bus', (), (((0.,0.,0.), (100.,0.,0.)),), RouteDirection('one_way')),
        MapRoute(20, 'Hill', 20, 'b', 'Same', 'tram', (), (((300.,0.,300.), (500.,10.,300.)),), RouteDirection('one_way')),
    )

def page_with_map(settings, app):
    from map_page import MapPage
    from map_model import MapSnapshot
    page = MapPage(settings)
    page.resize(960, 680); page.show(); app.processEvents()
    page.set_session({'save_key': 'A'})
    page.set_snapshot(MapSnapshot(routes=routes(), bounds=(0,0,500,500)))
    return page

# The old filtered canvas search would hide a valid single-line navigation target.
def test_single_search_ignores_network_filters_and_preserves_query(settings, app):
    page = page_with_map(settings, app)
    try:
        canvas, query = page.canvas, page.query
        state = page.panel_set.state(); state['manual_line_ids'] = [10]
        page.apply_state(state)
        page.set_preset('single')
        found = page.search('Hill')
        assert [item.id for item in found] == [20]
        assert page.show_route(20, page.save_token)
        assert [route.id for route in page.canvas.snapshot.routes] == [20]
        page.set_preset('network')
        assert [route.id for route in page.canvas.snapshot.routes] == [10]
        assert page.canvas is canvas and page.query is query
    finally: page.close()

# A shared dock/camera would overwrite the inactive preset on a switch/reset.
def test_preset_view_and_dock_roundtrip_are_independent(settings, app):
    page = page_with_map(settings, app)
    try:
        page.canvas.zoom_in(); network_view = (*page.canvas.center, page.canvas.zoom)
        page.dock.set_group_collapsed(True)
        page.set_preset('single')
        page.show_route(20, page.save_token)
        page.canvas.zoom_out(); single_view = (*page.canvas.center, page.canvas.zoom)
        page.dock.float_panel('single')
        page.set_preset('network')
        assert (*page.canvas.center, page.canvas.zoom) == network_view
        assert page.dock.layout_state()['group_collapsed']
        page.set_preset('single')
        assert (*page.canvas.center, page.canvas.zoom) == single_view
        assert page.dock.layout_state()['panels']['single']['floating']
        page.reset_layout.click(); app.processEvents()
        assert (*page.canvas.center, page.canvas.zoom) == single_view
        assert [r.id for r in page.canvas.snapshot.routes] == [20]
    finally: page.close()

# Same save identity with a new generation must invalidate delayed detail events.
def test_show_route_queues_until_geometry_and_rejects_stale_generation(settings, app):
    from map_page import MapPage
    from map_model import MapSnapshot
    page = MapPage(settings)
    try:
        page.set_session({'save_key': 'A'})
        old_token = page.save_token
        assert page.show_route(20, old_token)
        assert page.preset == 'single'
        page.set_snapshot(MapSnapshot(routes=routes(), bounds=(0,0,500,500)))
        assert [r.id for r in page.canvas.snapshot.routes] == [20]
        page.set_session({'save_key': 'A'})
        assert not page.show_route(10, old_token)
        page.set_snapshot(MapSnapshot(routes=routes()))
        assert [r.id for r in page.canvas.snapshot.routes] == [20]
        page.set_session({'save_key': 'B'})
        assert not page.show_route(20, old_token)
        page.set_snapshot(MapSnapshot(routes=routes()))
        assert page.canvas.snapshot.routes == ()
    finally: page.close()

# Merely selecting comparison routes must never reduce default building emphasis.
def test_planning_selection_stays_global_without_recentering(settings, app):
    page = page_with_map(settings, app)
    try:
        page.set_preset('planning')
        before = (*page.canvas.center, page.canvas.zoom)
        page.planning_panel.selectionChanged.emit({10,20})
        assert {r.id for r in page.canvas.snapshot.routes} == {10,20}
        assert page.result.building_emphasis
        assert (*page.canvas.center, page.canvas.zoom) == before
        page.set_preset('single'); page.set_preset('planning')
        assert {r.id for r in page.canvas.snapshot.routes} == {10,20}
    finally: page.close()

def test_line_detail_map_action_carries_identity_and_generation(settings, app, monkeypatch):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    import desktop_app
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *_: settings)
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda _: None)
    window = desktop_app.MainWindow()
    try:
        line = {'key': 'a10', '对象ID': 10, '公司名称': 'Same', '公司标识': 'a', '线路名称': 'Central', '运输制式': 'bus'}
        window.data = {'save_key': 'A', 'lines': [line]}
        window.map_page.set_session(window.data)
        from map_model import MapSnapshot
        window.map_page.set_snapshot(MapSnapshot(routes=routes(), bounds=(0,0,500,500)))
        window.show_line(line)
        assert window.lines_page.map_show_button.isEnabled()
        captured = window.lines_page.map_target
        window.map_page.set_session(window.data)
        assert not window._show_line_on_map(*captured)
        window.show_line(line)
        QTest.mouseClick(window.lines_page.map_show_button, Qt.MouseButton.LeftButton)
        assert window.pages.currentWidget() is window.map_page
        assert window.map_page.preset == 'single'
        window.map_page.set_snapshot(MapSnapshot(routes=routes(), bounds=(0,0,500,500)))
        assert [r.id for r in window.map_page.canvas.snapshot.routes] == [10]
        window._reset_line_page()
        assert not window.lines_page.map_show_button.isEnabled()
    finally: window.close()

# Search results emitted before a reload must not resolve an ID in the replacement save.
def test_old_search_result_cannot_select_same_id_in_replacement_save(settings, app):
    page = page_with_map(settings, app)
    from map_model import MapSnapshot
    try:
        page.set_preset('single')
        old = page.search('Hill')[0]
        page.set_session({'save_key': 'B'})
        page.set_snapshot(MapSnapshot(routes=routes()))
        assert not page._focus_search(old)
        assert page.canvas.snapshot.routes == ()
    finally: page.close()

# Native associations, known empty and unavailable are different inputs to the real menu.
def test_building_menu_uses_original_candidates_and_preserves_global_set(settings, app):
    from map_model import MapBuilding, MapSnapshot, BuildingServiceLines
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from dataclasses import replace
    page = page_with_map(settings, app)
    absent = replace(routes()[0], id=30, name='No geometry', paths=())
    buildings = (
        MapBuilding(1, '', 'Known', (0,0,0), service_lines=BuildingServiceLines(True,(20,30,20),(99,), 'native')),
        MapBuilding(2, '', 'Empty', (0,0,0), service_lines=BuildingServiceLines(True)),
        MapBuilding(3, '', 'Unavailable', (0,0,0)),
    )
    try:
        page.set_snapshot(MapSnapshot(routes=(*routes(), absent), buildings=buildings))
        page.set_preset('planning')
        page.planning_panel.selectionChanged.emit({10})
        before = (*page.canvas.center, page.canvas.zoom)
        assert page.show_building(1, page.surface.mapToGlobal(QPoint(20,60)))
        menu = page.planning_panel.building_menu
        ids = [menu.line_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(menu.line_list.count())]
        assert ids.count(20) == 1 and 10 not in ids
        menu.select_all.click()
        assert {r.id for r in page.canvas.snapshot.routes} == {10,20}
        assert (*page.canvas.center, page.canvas.zoom) == before
        assert page.show_building(2, page.surface.mapToGlobal(QPoint(20,60)))
        assert not page.planning_panel.building_menu.select_all.isEnabled()
        known_empty_text = page.planning_panel.building_menu.status_label.text()
        assert page.show_building(3, page.surface.mapToGlobal(QPoint(20,60)))
        assert page.planning_panel.building_menu.status_label.text() != known_empty_text
        assert {r.id for r in page.canvas.snapshot.routes} == {10,20}
        page.set_session({'save_key':'B'})
        assert not page.planning_panel.building_menu.isVisible()
    finally: page.close()

# Hidden startup must prepare a real frame at the stack's size, even with saved docks.
def test_hidden_prefetch_layout_uses_stack_size(settings, app):
    from PySide6.QtWidgets import QStackedWidget, QWidget
    from map_page import MapPage
    from map_model import MapSnapshot
    stack=QStackedWidget(); stack.resize(1440,960)
    stack.addWidget(QWidget())
    page=MapPage(settings, stack); stack.addWidget(page)
    stack.show(); app.processEvents()
    try:
        page.set_session({'save_key':'A'})
        page._loaded(page._generation, MapSnapshot(routes=routes(), bounds=(0,0,500,500)))
        assert page.canvas.width() > 1000 and page.canvas.height() > 800
        assert not page.canvas._fit_pending
    finally: stack.close()

# An application default must reach GeometryService unchanged; frozen directories are temporary.
def test_default_cache_delegates_to_geometry_service(settings, app, tmp_path):
    from map_page import MapPage
    default=MapPage(settings)
    explicit=MapPage(settings,cache_dir=tmp_path/'cache')
    try:
        assert default.cache_dir is None
        assert explicit.cache_dir == tmp_path/'cache'
    finally: default.close(); explicit.close()

# Clearing a session must clear whole-line facts during the new save's loading phase.
def test_single_facts_clear_when_session_is_replaced_or_cancelled(settings, app):
    page=page_with_map(settings, app)
    try:
        page.set_preset('single'); page.show_route(20,page.save_token)
        assert page.single_panel.fact_labels['geometry_km'].text() != '—'
        page.set_session({'save_key':'B'})
        assert page.single_panel.fact_labels['geometry_km'].text() == '—'
        from map_model import MapSnapshot
        page.set_snapshot(MapSnapshot(routes=routes())); page.show_route(10,page.save_token)
        assert page.single_panel.fact_labels['geometry_km'].text() != '—'
        page.cancel_prefetch()
        assert page.single_panel.fact_labels['geometry_km'].text() == '—'
    finally: page.close()

# Search result activation with Enter must follow the same checked navigation as mouse.
def test_single_search_keyboard_activation(settings, app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    page=page_with_map(settings, app)
    try:
        page.set_preset('single')
        page.surface.search.setText('Hill'); page.surface._search()
        page.surface.results.setCurrentRow(0); page.surface.results.setFocus()
        QTest.keyClick(page.surface.results,Qt.Key.Key_Return)
        assert [r.id for r in page.canvas.snapshot.routes] == [20]
    finally: page.close()

# The time editors must receive the simulated clock when the save has no prior filter.
def test_network_service_time_initializes_from_simulated_clock(settings, app):
    from map_page import MapPage
    from map_model import MapSnapshot
    page=MapPage(settings)
    try:
        page.set_session({'save_key':'A','simulation_time':'2023-02-10 17:50:00'})
        page.set_snapshot(MapSnapshot(routes=routes()))
        from PySide6.QtCore import Qt
        assert page.panel_set.controls['service_start'].dateTime().toString(Qt.DateFormat.ISODate) == '2023-02-10T17:50:00'
        assert page.panel_set.state()['service_time_mode'] == 'off'
        page.panel_set.controls['service_time_mode'].buttons['instant'].click()
        assert page.panel_set.state()['service_start'] == '2023-02-10T17:50:00'
    finally: page.close()

# Updating global selection should keep the current list item and keyboard focus alive.
def test_planning_selection_does_not_rebuild_route_catalog(settings, app):
    page=page_with_map(settings, app)
    try:
        page.set_preset('planning')
        first=page.planning_panel.line_list.item(0)
        page.planning_panel.line_list.setCurrentItem(first)
        page.planning_panel.selectionChanged.emit({10})
        assert page.planning_panel.line_list.item(0) is first
        assert page.planning_panel.line_list.currentItem() is first
    finally: page.close()

# Operating-time changes must refresh BOTH canvas results and network panel candidates.
def test_service_time_refreshes_network_line_results(settings, app):
    from map_page import MapPage
    from map_model import MapSnapshot,RouteService,ServiceTimetable
    from line_schedule import TICKS_PER_SECOND
    from dataclasses import replace
    from PySide6.QtCore import Qt
    hour=3600*TICKS_PER_SECOND
    service=lambda begin:RouteService(True,True,(ServiceTimetable(127,begin*hour,(begin+1)*hour,hour,(begin*hour,(begin+1)*hour)),))
    snapshot=MapSnapshot(routes=(replace(routes()[0],service=service(8)),replace(routes()[1],service=service(11))))
    page=MapPage(settings)
    try:
        page.set_session({'save_key':'A','simulation_time':'2023-02-10 08:30:00'})
        page.set_snapshot(snapshot)
        state=page.panel_set.state(); state['building_emphasis']=False; page.apply_state(state)
        page.panel_set.controls['service_time_mode'].buttons['instant'].click()
        assert [r.id for r in page.canvas.snapshot.routes] == [10]
        listing=page.panel_set.line_list
        assert [listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(listing.count())] == [10]
        page.set_preset('single'); page.show_route(20,page.save_token)
        assert [r.id for r in page.canvas.snapshot.routes] == [20]
    finally: page.close()

# Initial all-class query and visible planning checks must describe the same selection.
def test_planning_default_checks_match_displayed_buildings(settings, app):
    page=page_with_map(settings, app)
    try:
        page.set_preset('planning')
        expected={item['id'] for item in page._panel_options['building_classes']}
        assert page.planning_panel.state()['building_classes'] == expected
        page.planning_panel.selectionChanged.emit({10})
        assert page.planning_panel.state()['building_classes'] == expected
        assert page._current_state()['building_classes'] == expected
    finally: page.close()


# Single facts belong to the simulated current day, not network's previous-day passenger filter.
def test_single_status_uses_fact_day(settings, app):
    from map_page import MapPage
    from map_model import MapSnapshot
    page=MapPage(settings)
    try:
        page.set_session({'save_key':'A','simulation_time':'2023-02-10 08:30:00'})
        page.set_snapshot(MapSnapshot(routes=routes()))
        page.show_route(10,page.save_token)
        assert '2023-02-10' in page.status.text()
        assert '2023-02-09' not in page.status.text()
    finally: page.close()

# Worker must explicitly prevent disk snapshots, even if a service default regresses.
def test_map_worker_disables_disk_snapshot_io(tmp_path, app, monkeypatch):
    import map_geometry
    from map_model import MapSnapshot
    from map_page import MapWorker
    marker=tmp_path/'disk-snapshot'
    class Service:
        def __init__(self,cache_dir):pass
        def load(self,source,cancelled,use_disk_cache=True):
            if use_disk_cache:marker.write_text('snapshot')
            return MapSnapshot()
    monkeypatch.setattr(map_geometry,'MapGeometryService',Service)
    worker=MapWorker(7,tmp_path/'save',tmp_path)
    results=[];errors=[]
    worker.completed.connect(lambda generation,snapshot:results.append((generation,snapshot)))
    worker.failed.connect(lambda generation,message:errors.append(message))
    worker.run()
    assert not errors
    assert len(results)==1 and results[0][0]==7
    assert not marker.exists()
