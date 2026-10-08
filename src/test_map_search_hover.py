import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from map_page import MapPage
from map_model import MapRoute, MapSnapshot, RouteDirection


def test_selected_route_search_expands_on_hover_and_keeps_input_focus(tmp_path):
    app = QApplication.instance() or QApplication([])
    page = MapPage(QSettings(str(tmp_path/'hover.ini'), QSettings.Format.IniFormat))
    page.resize(960, 680); page.show(); app.processEvents()
    surface = page.surface
    assert surface.search.isHidden()
    route = MapRoute(7, '7路', 7, 'a', '公司', 'bus', (),
        (((0.,0.,0.), (100.,0.,0.)),), RouteDirection('one_way'))
    page.set_snapshot(MapSnapshot(routes=(route,), bounds=(0,0,100,100)))
    assert page.show_route(7)
    assert surface.search.isHidden()
    assert not surface.search_button.isHidden()
    app.sendEvent(surface.search_button, QEvent(QEvent.Type.Enter))
    assert not surface.search.isHidden()
    surface.search.setFocus(); surface.search.setText('17'); app.processEvents()
    surface._collapse_search_if_idle()
    assert not surface.search.isHidden()
    assert surface.search.text() == '17'
    surface.search.clearFocus()
    surface._collapse_search()
    assert surface.search.isHidden()
    surface._expand_search()
    assert surface.search.text() == '17'
    app.sendEvent(surface.search,QEvent(QEvent.Type.Leave))
    QTest.qWait(160)
    assert surface.search.isHidden()
    surface.search_button.click(); app.processEvents()
    assert surface.search.hasFocus()
    assert not surface.search.isHidden()
    page.set_preset('network')
    surface.search.clearFocus();surface._collapse_search_if_idle()
    assert surface.search.isHidden()
    assert not surface.search_button.isHidden()
    page.close()


@pytest.mark.parametrize('preset', ('single', 'network', 'planning'))
def test_every_preset_defaults_to_search_button_through_load_and_clear(tmp_path, preset):
    app = QApplication.instance() or QApplication([])
    page = MapPage(QSettings(str(tmp_path/f'{preset}.ini'), QSettings.Format.IniFormat))
    page.resize(960,680);page.show();app.processEvents()
    try:
        page.set_preset(preset)
        assert page.surface.search.isHidden() and not page.surface.search_button.isHidden()
        page.set_session({'save_key':'A'})
        page.surface.set_loading(True)
        assert page.surface.search.isHidden() and not page.surface.search_button.isHidden()
        route = MapRoute(7,'7路',7,'a','公司','bus',(),
            (((0.,0.,0.),(100.,0.,0.)),),RouteDirection('one_way'))
        page.set_snapshot(MapSnapshot(routes=(route,),bounds=(0,0,100,100)))
        assert page.surface.search.isHidden() and not page.surface.search_button.isHidden()
        page.cancel_prefetch()
        assert page.surface.search.isHidden() and not page.surface.search_button.isHidden()
        page.set_session(None)
        assert page.surface.search.isHidden() and not page.surface.search_button.isHidden()
    finally:page.close()


@pytest.mark.parametrize('preset', ('single', 'network', 'planning'))
def test_keyboard_search_expands_and_locates_the_same_record(tmp_path,preset):
    app = QApplication.instance() or QApplication([])
    page = MapPage(QSettings(str(tmp_path/f'keyboard-{preset}.ini'),QSettings.Format.IniFormat))
    page.resize(960,680);page.show();app.processEvents()
    try:
        route=MapRoute(7,'7路',7,'a','公司','bus',(),
            (((0.,0.,0.),(100.,0.,0.)),),RouteDirection('one_way'))
        page.set_snapshot(MapSnapshot(routes=(route,),bounds=(0,0,100,100)))
        page.set_preset(preset)
        button=page.surface.search_button
        assert not button.isHidden() and button.focusPolicy()!=Qt.FocusPolicy.NoFocus
        button.setFocus();app.processEvents()
        assert page.surface.search.isHidden()
        QTest.keyClick(button,Qt.Key.Key_Space);app.processEvents()
        assert page.surface.search.hasFocus() and not page.surface.search.isHidden()
        QTest.keyClicks(page.surface.search,'7');QTest.keyClick(page.surface.search,Qt.Key.Key_Return)
        assert page.preset=='single' and page.presets.state('single')['query']['route_id']==7
        assert page.surface.search.isHidden() and page.surface.search.text()=='7'
    finally:page.close()


def test_search_descendant_focus_and_result_focus_keep_the_input_open(tmp_path):
    app=QApplication.instance() or QApplication([])
    page=MapPage(QSettings(str(tmp_path/'child-focus.ini'),QSettings.Format.IniFormat))
    page.resize(960,680);page.show();app.processEvents()
    try:
        surface=page.surface;surface._activate_search();surface.search.setText('7')
        child=surface.search.searchButton;child.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        child.setFocus();app.processEvents();assert child.hasFocus()
        surface._collapse_search_if_idle()
        assert not surface.search.isHidden() and surface.search.text()=='7'
        from PySide6.QtWidgets import QListWidgetItem
        surface.results.addItem(QListWidgetItem('7路'));surface.results.show()
        surface.results.setFocus();app.processEvents();assert surface.results.hasFocus()
        surface._collapse_search_if_idle()
        assert not surface.search.isHidden() and not surface.results.isHidden()
        page.canvas.setFocus();app.sendEvent(surface.results,QEvent(QEvent.Type.Leave));QTest.qWait(160)
        assert surface.search.isHidden() and surface.results.isHidden() and surface.search.text()=='7'
    finally:page.close()


def test_apply_and_loading_keep_active_input_but_new_source_collapses_it(tmp_path):
    app=QApplication.instance() or QApplication([])
    page=MapPage(QSettings(str(tmp_path/'active.ini'),QSettings.Format.IniFormat))
    page.resize(960,680);page.show();app.processEvents()
    try:
        route=MapRoute(7,'7路',7,'a','公司','bus',(),(((0.,0.,0.),(100.,0.,0.)),))
        page.set_session({'save_key':'A'});page.set_snapshot(MapSnapshot(routes=(route,)))
        surface=page.surface;surface._activate_search();QTest.keyClicks(surface.search,'17')
        page.apply_state(page.panel_set.state());surface.set_loading(True);app.processEvents()
        assert not surface.search.isHidden() and surface.search.hasFocus() and surface.search.text()=='17'
        page.set_session({'save_key':'B'});app.processEvents()
        assert surface.search.isHidden() and surface.search.text()=='17'
        surface.search_button.click();app.processEvents()
        assert surface.search.hasFocus() and surface.search.text()=='17'
    finally:page.close()


def test_same_prefetch_handoff_keeps_active_search_and_its_pending_token(tmp_path,monkeypatch):
    from PySide6.QtCore import QObject,Signal
    import map_page
    class Worker(QObject):
        completed=Signal(int,object);failed=Signal(int,str);finished=Signal()
        def __init__(self,generation,source,cache,parent):super().__init__(parent)
        def start(self):pass
        def requestInterruption(self):pass
        def isRunning(self):return False
    monkeypatch.setattr(map_page,'MapWorker',Worker)
    app=QApplication.instance() or QApplication([])
    page=MapPage(QSettings(str(tmp_path/'same-prefetch.ini'),QSettings.Format.IniFormat))
    page.resize(960,680);page.show();app.processEvents()
    try:
        source=tmp_path/'A.cim';page.start_prefetch(source)
        surface=page.surface;surface._activate_search();QTest.keyClicks(surface.search,'17')
        QTest.keyClick(surface.search,Qt.Key.Key_Return);pending=page._pending_search
        assert pending is not None
        page.set_session({'save_key':'A','save_path':str(source)});app.processEvents()
        assert surface.search.hasFocus() and not surface.search.isHidden()
        assert surface.search.text()=='17' and page._pending_search==pending
        assert page._search_token()==pending[0]
        page.cancel_prefetch()
        assert surface.search.isHidden() and page._search_token()!=pending[0]
    finally:page.close()
