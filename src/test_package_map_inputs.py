"""Exercise smoke inputs against real widgets and explicit synthetic geometry."""
import json
import os
import time
import pytest
from PySide6.QtCore import QSettings, QEventLoop, QTimer


@pytest.fixture
def map_page(qt_application, tmp_path):
    from stats_style import initialize_theme
    initialize_theme(qt_application)
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
    if expected_dpr := os.environ.get('CIM2_TEST_EXPECTED_DPR'):
        assert page.devicePixelRatioF()==pytest.approx(float(expected_dpr))
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
    from PySide6.QtGui import QColor
    from qfluentwidgets import qconfig
    from stats_tokens import ACCENT
    assert qconfig.get(qconfig.themeColor).rgba()==QColor(ACCENT).rgba()
    captures=[]
    def capture(name,*_):
        assert map_page.canvas.can_export()
        assert map_page.grab().save(str(tmp_path/(name+'.png')))
        captures.append(name)
    evidence=_exercise_map_inputs(map_page,map_page,settle,wait_until,capture)
    (tmp_path/'capture-theme.json').write_text(json.dumps({
        'source':'explicit synthetic geometry',
        'accent':qconfig.get(qconfig.themeColor).name(),
        'actual_dpr':map_page.devicePixelRatioF(),
        'actual_size':[map_page.width(),map_page.height()],
    },indent=2),encoding='utf-8')
    assert evidence['search']['query']=='7' and set(evidence['search']['matches'])=={70,170}
    assert 707 not in evidence['search']['matches']
    assert evidence['sorting']['selection_preserved']
    assert evidence['building']['candidate_ids']==[70,170]
    assert evidence['building']['selected_ids']==[70,170]
    assert evidence['building']['native_indicator_cancelled']
    assert evidence['building']['selected_after_cancel']==evidence['building']['outside_ids']
    assert evidence['navigation']['dragged'] and evidence['navigation']['zoomed']
    assert evidence['navigation']['vector_prepared_reused']
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
    assert evidence['canvas_size']==[map_page.canvas.width(),map_page.canvas.height()]
    assert evidence['legend_height']==map_page.canvas.legend_strip_height()
    assert evidence['legend_height']>0
    assert evidence['size']==[map_page.canvas.width(),map_page.canvas.height()+evidence['legend_height']]
    map_page.canvas.zoom_out()
    with pytest.raises(AssertionError):
        _map_current_export(map_page,tmp_path/'stale.png')
    assert not (tmp_path/'stale.png').exists()


@pytest.fixture
def smoke_window(qt_application, tmp_path, monkeypatch):
    import desktop_app
    from stats_style import initialize_theme
    from test_route_export_model import source
    from test_city_period_modes import observations
    initialize_theme(qt_application)
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *_: QSettings(
        str(tmp_path/'smoke.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda _: None)
    window=desktop_app.MainWindow(); window.resize(960,680); window.show()
    wait_until(lambda: window._welcome_handoff_complete)
    session,snapshot=source()
    session.update(save_key='synthetic-smoke', history=observations(),
                   simulation_time='2024-01-10 00:00:00',
                   companies=[{'公司标识':'owner','公司名称':'公司'}])
    window.data=session
    window.map_page.set_session(session)
    window.map_page.set_snapshot(snapshot)
    window.statistics_page.set_session(session)
    window._refresh_body()
    yield window,snapshot.routes[0]
    window.statistics_page.stop_workers(); window.close()


def test_smoke_single_route_exports_use_actual_entry_preview_and_files(smoke_window,tmp_path):
    from package_smoke import _exercise_route_exports
    from route_export_dialog import FluentFileDialog
    window,route=smoke_window
    picker=FluentFileDialog.__dict__['getSaveFileName']
    captures=[]
    def capture(name,dialog):
        assert not dialog.preview.image.isNull()
        assert dialog.pages.currentIndex()==0 and dialog.format_control.isVisible()
        assert dialog.grab().save(str(tmp_path/(name+'.png')))
        captures.append(name)
    evidence=_exercise_route_exports(window,window.map_page,route,tmp_path,settle,wait_until,capture)
    assert [item['format'] for item in evidence]==['PNG','JPG','PDF']
    assert all(item['route_id']==42 and item['ppi']==80 for item in evidence)
    assert all(item['size']==[400,267] and item['preview_nonempty'] for item in evidence)
    assert all(item['width_mm']==127 and item['bytes']>0 for item in evidence)
    assert len(captures)==3
    assert FluentFileDialog.__dict__['getSaveFileName'] is picker


def test_smoke_city_period_records_current_real_snapshot_and_resets_mode(smoke_window,tmp_path):
    from package_smoke import _exercise_city_period_inputs
    window,_=smoke_window
    captures=[]
    def capture(name):
        assert window.grab().save(str(tmp_path/(name+'.png')))
        captures.append(name)
    evidence=_exercise_city_period_inputs(window,window.statistics_page,settle,wait_until,capture)
    assert {item['mode'] for item in evidence}=={'default','period'}
    assert {tuple(item['requested_size']) for item in evidence}=={(960,680),(1440,960)}
    assert all(item['companies']==[] and item['kpis'] for item in evidence)
    assert all(item['comparison'] is not None for item in evidence if item['mode']=='period')
    assert all(item['comparison'] is None for item in evidence if item['mode']=='default')
    assert len({tuple(item['window']) for item in evidence})==1
    assert len(captures)==4
    assert window.statistics_page.city_mode_control.currentKey()=='default'


@pytest.mark.parametrize('company_count', [1, 2])
def test_smoke_comparison_availability_uses_actual_company_count(smoke_window, company_count):
    from package_smoke import _company_comparison_evidence
    window,_=smoke_window
    session=dict(window.data)
    session['companies']=[{'公司标识':'owner','公司名称':'公司'}]
    if company_count==2:
        session['companies'].append({'公司标识':'other','公司名称':'另一家公司'})
    window.statistics_page.set_session(session)
    evidence=_company_comparison_evidence(window.statistics_page)
    assert evidence==dict(company_count=company_count,comparison_available=company_count>=2)


@pytest.mark.parametrize('failed', [False, True])
def test_smoke_failure_marker_survives_automatic_last_window_exit(tmp_path, monkeypatch, failed):
    import startup_bootstrap
    from package_smoke import main
    source=tmp_path/'session'; source.mkdir()
    output=tmp_path/'output'
    def bootstrap(_launcher, *, window_factory, trace_path):
        trace_path.write_text(json.dumps([
            {'event':name,'window_id':42}
            for name in ('logo_first_paint','desktop_import_started','window_first_paint')]),encoding='utf-8')
        if failed:
            (output/'failure.txt').write_text('original acceptance failed',encoding='utf-8')
        return 0  # Qt can quit when the last window closes before a scheduled exit(1).
    monkeypatch.setattr(startup_bootstrap,'main',bootstrap)
    assert main(tmp_path/'CimStats.exe', ['--job',str(source),'--output',str(output),
                '--expected-dpr','1'])==int(failed)
    if failed:
        assert (output/'failure.txt').read_text(encoding='utf-8')=='original acceptance failed'
