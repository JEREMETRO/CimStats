"""Normal map completion prepares timetable statistics without blocking Qt."""
import threading
import time
from PySide6.QtCore import QSettings, QTimer
from map_model import MapRoute, MapSnapshot
from map_query import RouteStats
import pytest


def pump_until(app, predicate, timeout=3):
    end=time.perf_counter()+timeout
    while not predicate() and time.perf_counter()<end:
        app.processEvents();time.sleep(.005)
    assert predicate()


def test_normal_map_statistics_leave_gui_responsive_and_deliver_exact_results(qt_application,tmp_path,monkeypatch):
    import map_page
    release=threading.Event();started=threading.Event();threads=[];beats=[]
    expected={1:RouteStats(passengers=123,daytime_interval_minutes=12)}
    def prepare(session,routes,**kwargs):
        threads.append(threading.get_ident());started.set();release.wait(1)
        return expected
    monkeypatch.setattr(map_page,'stats_from_session',prepare)
    page=map_page.MapPage(QSettings(str(tmp_path/'stats.ini'),QSettings.Format.IniFormat))
    page.set_session({'save_key':'A','lines':[{'对象ID':1}]})
    snapshot=MapSnapshot(routes=(MapRoute(1,'1',1,'a','公司','bus',(),(((0.,0.,0.),(100.,0.,0.)),)),))
    timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:beats.append(True));timer.start()
    try:
        start=time.perf_counter();page._loaded(page._generation,snapshot)
        elapsed=time.perf_counter()-start
        assert elapsed<.15
        pump_until(qt_application,lambda:started.is_set() and len(beats)>=3)
        assert threads==[threads[0]] and threads[0]!=threading.get_ident()
        assert page.query is None
        release.set();pump_until(qt_application,lambda:page.query is not None)
        assert page.query.stats==expected
    finally:
        release.set();timer.stop();page.stop_workers()
        pump_until(qt_application,lambda:not any(worker.isRunning() for worker in page.workers))
        page.close()


def test_pending_statistics_cannot_apply_to_a_replacement_save(qt_application,tmp_path,monkeypatch):
    import map_page
    release=threading.Event();started=threading.Event()
    def prepare(session,routes,**kwargs):
        started.set();release.wait(1);return {1:RouteStats(passengers=123)}
    monkeypatch.setattr(map_page,'stats_from_session',prepare)
    page=map_page.MapPage(QSettings(str(tmp_path/'replace.ini'),QSettings.Format.IniFormat))
    page.set_session({'save_key':'A','lines':[{'对象ID':1}]})
    snapshot=MapSnapshot(routes=(MapRoute(1,'1',1,'a','公司','bus',(),(((0.,0.,0.),(100.,0.,0.)),)),))
    try:
        page._loaded(page._generation,snapshot)
        pump_until(qt_application,started.is_set)
        page.set_session({'save_key':'B'})
        release.set();pump_until(qt_application,lambda:not page.workers)
        assert page.query is None
        assert page.canvas.snapshot.routes==()
    finally:
        release.set();page.stop_workers()
        pump_until(qt_application,lambda:not any(worker.isRunning() for worker in page.workers))
        page.close()


def test_statistics_input_preserves_values_and_isolates_native_source_fields():
    from map_query import stats_input_from_session,stats_from_session
    class UnrelatedPayload:
        def __deepcopy__(self,memo):raise AssertionError('Unrelated payload copied')
    row={'时刻表序号':1,'发班序号':1,'发班_tick':8*36_000_000_000,
         '运行日掩码':127,'running_day_valid':True,'vehicles':UnrelatedPayload()}
    line={'对象ID':1,'平均客流':50,'字段可用性':{'客流_今日':True},
          '原始字段':{'客流_今日':123,'客流_累计':500,'收入_累计':1020,'支出_累计':1000,'时刻表数':1},
          '时刻表':{'all':{'entries':[row]}},'运行日未知班次':[], 'other':UnrelatedPayload()}
    session={'simulation_time':'2013-05-23T23:59:00','lines':[line]}
    captured=stats_input_from_session(session)
    # Direct numeric calculation can read native rows, but irrelevant row data must
    # not travel to the shared schedule formatter's deepcopy in the worker.
    assert 'vehicles' not in captured['lines'][0]['时刻表']['native']['entries'][0]
    routes=(MapRoute(1,'1',1,'a','公司','bus',(),()),)
    values=stats_from_session(captured,routes)
    assert values[1].passengers==123 and values[1].profit_status=='zero'
    line['原始字段']['客流_今日']=999
    line['字段可用性']['客流_今日']=False
    row['运行日掩码']=0
    assert stats_from_session(captured,routes)==values


def test_cancellation_does_not_return_a_partial_statistics_result():
    from map_query import stats_from_session
    with pytest.raises(InterruptedError):
        stats_from_session({},(MapRoute(1,'1',1,'a','公司','bus',(),()),),cancelled=lambda:True)


@pytest.mark.parametrize('pending_search',[False,True])
def test_async_handoff_consumes_latest_applied_filter_or_pending_search(qt_application,tmp_path,monkeypatch,pending_search):
    import map_page
    release=threading.Event();started=threading.Event()
    def prepare(session,routes,**kwargs):
        started.set();release.wait(1);return {1:RouteStats(passengers=123)}
    monkeypatch.setattr(map_page,'stats_from_session',prepare)
    page=map_page.MapPage(QSettings(str(tmp_path/'handoff.ini'),QSettings.Format.IniFormat))
    page.set_session({'save_key':'A','lines':[{'对象ID':1}]})
    snapshot=MapSnapshot(routes=(MapRoute(1,'1',1,'a','公司','bus',(),(((0.,0.,0.),(100.,0.,0.)),)),))
    try:
        page._loaded(page._generation,snapshot);pump_until(qt_application,started.is_set)
        if pending_search:
            page.surface.search.setText('1');page.surface._submit_search()
            assert page._pending_search is not None
        else:
            state=page.panel_set.state();state['manual_line_ids']=[];page.apply_state(state)
        release.set();pump_until(qt_application,lambda:page.query is not None)
        if pending_search:
            assert page.preset=='single'
            assert page.presets.state('single')['query']['route_id']==1
            assert page._pending_search is None
        else:assert page.result.routes==()
    finally:
        release.set();page.stop_workers()
        pump_until(qt_application,lambda:not any(worker.isRunning() for worker in page.workers))
        page.close()


def test_map_backend_dependencies_prepare_in_existing_startup_worker(qt_application,tmp_path,monkeypatch):
    import importlib
    import desktop_app
    original=importlib.import_module;observed={}
    def record(name,*args,**kwargs):
        result=original(name,*args,**kwargs)
        if name in ('map_geometry','map_query'):observed[name]=threading.get_ident()
        return result
    monkeypatch.setattr(importlib,'import_module',record)
    monkeypatch.setattr(desktop_app,'QSettings',lambda *_:QSettings(str(tmp_path/'startup.ini'),QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow,'check_install',lambda _:None)
    window=desktop_app.MainWindow(defer_startup=True);ready=[];errors=[]
    try:
        window.initialize_content_async(lambda:ready.append(True),errors.append)
        pump_until(qt_application,lambda:bool(ready or errors),timeout=30)
        assert not errors
        assert set(observed)=={'map_geometry','map_query'}
        assert all(thread!=threading.get_ident() for thread in observed.values())
    finally:window.close()
