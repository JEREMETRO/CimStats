import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from map_model import MapSnapshot,MapRoute,RouteDirection

def test_page_state_preserves_view_and_empty_manual(tmp_path):
    from map_page import MapPage
    app=QApplication.instance() or QApplication([])
    page=MapPage(QSettings(str(tmp_path/'map.ini'),QSettings.Format.IniFormat))
    page.resize(1350,850);page.show();app.processEvents()
    route=MapRoute(1,'1',1,'a','公司','bus',(),(((0.,0.,0.),(100.,0.,0.)),),RouteDirection('one_way'))
    page.set_snapshot(MapSnapshot(routes=(route,),bounds=(0,0,100,100)))
    page.canvas.zoom_in(); center,zoom=page.canvas.center,page.canvas.zoom
    state=page.panel_set.state();state['manual_line_ids']=[];page.apply_state(state)
    assert not page.canvas.snapshot.routes
    assert (page.canvas.center,page.canvas.zoom)==(center,zoom)
    page.dock.float_panel('display');page.dock.dock_panel('display')
    assert not page.canvas.snapshot.routes
    page.close()

def test_new_navigation_has_independent_map_without_statistics_tabs(tmp_path,monkeypatch):
    import desktop_app
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(desktop_app,'QSettings',lambda *_:QSettings(str(tmp_path/'shell.ini'),QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow,'check_install',lambda _:None)
    window=desktop_app.MainWindow()
    assert [b.text() for b in window.nav_buttons]==['最新信息','地图显示','线路查询','统计数据']
    window.navigate(1)
    assert window.pages.currentWidget() is window.map_page
    assert window.stats_tabs.isHidden()
    window.close()

def test_async_startup_includes_map(tmp_path, monkeypatch):
    import time
    import desktop_app
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(desktop_app,'QSettings',lambda *_:QSettings(str(tmp_path/'async.ini'),QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow,'check_install',lambda _:None)
    window=desktop_app.MainWindow(defer_startup=True)
    ready=[]; errors=[]
    window.initialize_content_async(lambda:ready.append(True),errors.append)
    deadline=time.monotonic()+30
    while not ready and not errors and time.monotonic()<deadline:
        app.processEvents(); time.sleep(.01)
    assert not errors
    assert ready
    assert window.pages.count()==4
    window.navigate(1)
    assert window.pages.currentWidget() is window.map_page
    window.close()

def test_map_worker_scripts_packaged():
    import importlib.util
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('map_package_check',root/'tools/candidate_package.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    bundled={Path(source).relative_to(root).as_posix() for source,_ in module.bundle_data(root)}
    assert 'src/patch_singleton_probe.py' in bundled
    assert 'data/map_assets.json' in bundled

def test_save_filter_state_does_not_leak(tmp_path):
    import json
    from map_page import MapPage
    app=QApplication.instance() or QApplication([])
    settings=QSettings(str(tmp_path/'saves.ini'),QSettings.Format.IniFormat)
    settings.setValue('map/query/A',json.dumps({'profit_statuses':['loss'],'passenger_min':10}))
    page=MapPage(settings)
    page.set_session({'save_key':'A'})
    assert page.panel_set.state()['passenger_min']==10
    page.set_session({'save_key':'B'})
    assert page.panel_set.state()['passenger_min'] is None
    assert page.panel_set.state()['profit_statuses'] is None
    page.set_session({'save_key':'A'})
    assert page.panel_set.state()['passenger_min']==10
    assert page.panel_set.state()['profit_statuses']=={'loss'}
    page.close()

def test_map_icon_resolves_frozen_bundle(monkeypatch,tmp_path):
    import sys
    from map_icon import MAP_ICON
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'_MEIPASS',str(tmp_path),raising=False)
    assert MAP_ICON.path()==str(tmp_path/'frontend/static/cimstats/map.svg')

def test_desktop_map_export_follows_current_frame_and_save(tmp_path, monkeypatch):
    import desktop_app
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(desktop_app,'QSettings',lambda *_:QSettings(str(tmp_path/'export.ini'),QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow,'check_install',lambda _:None)
    window=desktop_app.MainWindow()
    window.navigate(1)
    page=window.map_page
    page.set_session({'save_key':'A'})
    route=MapRoute(1,'1',1,'a','公司','bus',(),(((0.,0.,0.),(100.,0.,0.)),))
    page.set_snapshot(MapSnapshot(routes=(route,),source_hash='A'))
    refresh=[]
    original=window.header.set_exports
    monkeypatch.setattr(window.header,'set_exports',lambda items:(refresh.append(items),original(items)))
    dialogs=[]
    monkeypatch.setattr(desktop_app.QFileDialog,'getSaveFileName',lambda *args:(dialogs.append(True) or ('','')))

    def enabled():return next(item[3] for item in window._export_items() if item[0]=='map-png')

    try:
        assert not page.canvas.can_export()
        assert not enabled()
        window._export_action('map-png')
        assert not dialogs
        page.canvas.prepare_frame()
        assert page.canvas.can_export() and enabled()
        assert refresh and next(item[3] for item in refresh[-1] if item[0]=='map-png')
        page.canvas.zoom_out()
        assert not enabled()
        assert not next(item[3] for item in refresh[-1] if item[0]=='map-png')
        page.canvas._render_timer.stop()
        page.canvas.prepare_frame()
        output=tmp_path/'current.png'
        monkeypatch.setattr(desktop_app.QFileDialog,'getSaveFileName',lambda *args:(str(output),''))
        window._export_action('map-png')
        assert output.is_file()

        stale=tmp_path/'stale.png'
        def change_save(*args):
            page.set_session({'save_key':'B'})
            page.set_snapshot(MapSnapshot(routes=(route,),source_hash='B'))
            page.canvas.prepare_frame()
            return str(stale),''
        monkeypatch.setattr(desktop_app.QFileDialog,'getSaveFileName',change_save)
        window._export_action('map-png')
        assert not stale.exists()
        page.set_session({'save_key':'C'})
        assert not enabled()
    finally:
        window.close(); app.processEvents()


def test_normal_map_open_shows_loading_until_worker_finishes(tmp_path, monkeypatch):
    import map_page
    from PySide6.QtCore import QObject, Signal
    class Worker(QObject):
        completed=Signal(int,object);failed=Signal(int,str);finished=Signal()
        def __init__(self,generation,source,cache,parent):
            super().__init__(parent);self.generation=generation;self.running=False
        def start(self):self.running=True
        def requestInterruption(self):self.running=False
        def isRunning(self):return self.running
    monkeypatch.setattr(map_page,'MapWorker',Worker)
    app=QApplication.instance() or QApplication([])
    source=tmp_path/'normal.save';source.write_bytes(b'save')
    page=map_page.MapPage(QSettings(str(tmp_path/'loading.ini'),QSettings.Format.IniFormat))
    page.set_session({'save_path':str(source),'save_key':'first'})
    assert not page.workers
    page.resize(900,600);page.show();app.processEvents()
    worker=page.workers[0]
    assert page.surface.loading.isVisible()
    worker.completed.emit(worker.generation,MapSnapshot())
    assert page.surface.loading.isHidden()
    worker.running=False;worker.finished.emit();app.processEvents()
    page.set_session({'save_path':str(source),'save_key':'second'})
    current=page.workers[0]
    assert page.surface.loading.isVisible()
    page._failed(current.generation-1,'old failure')
    assert page.surface.loading.isVisible()
    current.failed.emit(current.generation,'read failure')
    assert page.surface.loading.isHidden()
    assert not page._requested
    current.running=False;current.finished.emit();app.processEvents()
    page.close()
