"""Exercise smoke inputs against real widgets and explicit synthetic geometry."""
import time
import pytest
from PySide6.QtCore import QSettings, QEventLoop, QTimer


@pytest.fixture
def map_page(qt_application, tmp_path):
    from map_page import MapPage
    from map_model import MapSnapshot, MapRoute, MapRoad, MapBuilding, BuildingServiceLines, RouteDirection
    from map_query import RouteStats
    path = (((0.,0.,0.), (100.,0.,100.)),)
    routes = tuple(MapRoute(identity, f'{number}路', number, 'a', '公司7', 'bus', (), path,
                            RouteDirection('one_way')) for identity,number in ((70,7),(170,17),(707,2)))
    building = MapBuilding(10, '', '原生关联测试建筑', (50.,0.,50.),
                           ((44.,0.,44.),(56.,0.,44.),(56.,0.,56.),(44.,0.,56.)),
                           service_lines=BuildingServiceLines(True,(70,170),complete=True))
    page = MapPage(QSettings(str(tmp_path/'map.ini'),QSettings.Format.IniFormat))
    page.set_session({'save_key':'synthetic', 'simulation_time':'2013-05-23T23:59:00'})
    page.resize(960,680); page.show(); qt_application.processEvents()
    page.set_snapshot(MapSnapshot(roads=(MapRoad(1,'road','',path),),routes=routes,buildings=(building,),
                                  bounds=(0.,0.,100.,100.)),stats={
        identity:RouteStats(passengers=value,daytime_interval_minutes=10,peak_interval_minutes=5,
                            average_interval_minutes=15,passenger_source='today')
        for identity,value in ((70,6000),(170,12000),(707,20000))})
    yield page
    page.close()


def settle(ms=20):
    loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()


def wait_until(predicate,timeout=5):
    end=time.perf_counter()+timeout
    while not predicate():
        assert time.perf_counter()<end, 'diagnostic readiness timed out'
        settle()


def test_smoke_passenger_real_return_slider_and_confirm(map_page):
    from package_smoke import _map_passenger_input_case
    evidence=_map_passenger_input_case(map_page,settle,wait_until,lambda *_:None)
    assert evidence['typed_inputs']==['5000','15000']
    assert evidence['typed_positions']==[316,548]
    assert evidence['slider_inputs']==['5024.45','15000']
    assert evidence['draft_preserved_map'] and evidence['confirmed_collapsed']
    assert evidence['confirmed_route_ids']==[70,170]


def test_smoke_map_real_interactions_and_stable_captures(map_page,tmp_path):
    from package_smoke import _exercise_map_inputs
    captures=[]
    def capture(name,*_):
        assert map_page.canvas.can_export()
        assert map_page.grab().save(str(tmp_path/(name+'.png')))
        captures.append(name)
    evidence=_exercise_map_inputs(map_page,map_page,settle,wait_until,capture)
    assert evidence['search']['query']=='7' and set(evidence['search']['matches'])=={70,170}
    assert 707 not in evidence['search']['matches']
    assert evidence['sorting']['selection_preserved']
    assert evidence['building']['candidate_ids']==[70,170]
    assert evidence['building']['selected_ids']==[70,170]
    assert evidence['navigation']['dragged'] and evidence['navigation']['zoomed']
    assert evidence['navigation']['window_size']==[map_page.width(),map_page.height()]
    assert {item['mode'] for item in evidence['metrics']}=={'daytime','peak','all_day','passengers'}
    assert 'map-native-passenger-confirmed' in captures


def test_smoke_binding_failure_is_not_reported_as_success(map_page,monkeypatch):
    from package_smoke import _map_passenger_input_case
    map_page.panel_set.passenger_editor.min_edit.editingFinished.disconnect()
    map_page.panel_set.passenger_editor.max_edit.editingFinished.disconnect()
    with pytest.raises(AssertionError):
        _map_passenger_input_case(map_page,settle,wait_until,lambda *_:None)


def test_smoke_export_records_actual_size_and_rejects_unprepared_view(map_page,tmp_path):
    from package_smoke import _map_current_export
    map_page.canvas.prepare_frame()
    evidence=_map_current_export(map_page,tmp_path/'map.png')
    assert evidence['size']==[map_page.canvas.width(),map_page.canvas.height()]
    map_page.canvas.zoom_out()
    with pytest.raises(AssertionError):
        _map_current_export(map_page,tmp_path/'stale.png')
    assert not (tmp_path/'stale.png').exists()
