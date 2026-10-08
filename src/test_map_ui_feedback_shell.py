"""Presentation regressions for the map feedback round; tiny controlled Qt models."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import Qt,QPoint,QRect,QSettings
from PySide6.QtGui import QColor,QPainter
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QLabel
from PySide6.QtTest import QTest
from map_canvas import MapCanvas

@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])

class ColorCanvas(MapCanvas):
    def __init__(self,color):super().__init__();self.color=color
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor(self.color));painter.end()
    def zoom_in(self):pass
    def zoom_out(self):pass
    def reset_view(self):pass
    def search(self,text):return []
    def focus_result(self,result):return False

# A translucent hover/result surface visibly changes when the underlying map changes.
@pytest.mark.parametrize('state',['hover','loading','results'])
def test_map_search_surface_is_opaque_in_each_state(app,state):
    from map_page import _MapSurface
    from map_canvas import MapSearchResult
    pixels=[]
    for color in ('#FF0000','#00FF00'):
        surface=_MapSurface(ColorCanvas(color),search=lambda text:[MapSearchResult('route',10,'Central',(0,0,1,1))])
        surface.resize(440,240);surface.show();app.processEvents()
        try:
            surface.search.clearFocus();QTest.mouseMove(surface,QPoint(430,200))
            if state=='hover':QTest.mouseMove(surface.search,QPoint(140,20))
            if state=='loading':surface.set_loading(True)
            if state=='results':surface.search.setText('Central');surface._search()
            app.processEvents();QTest.qWait(30)
            image=surface.grab().toImage()
            scale=surface.devicePixelRatioF()
            pixels.append(image.pixelColor(round(260*scale),round((130 if state=='results' else 24)*scale)).name())
        finally:surface.close()
    assert pixels==['#ffffff','#ffffff']

# Rail text must not fall back to an internal preset key even without accessible metadata.
def test_dock_titles_are_chinese_for_tab_float_and_rail(app):
    from map_docking import MapDockHost
    for key,wanted in (('lines','线路列表'),('single','线路信息'),('planning','建筑视图与线路比选')):
        panel=QWidget()
        host=MapDockHost(QWidget(),{key:panel});host.resize(960,680);host.show();app.processEvents()
        try:
            assert host.tabs[key].text()==wanted
            assert host.frames[key].title.text()==wanted
            assert host.rail_buttons[key].text().replace('\n','')==wanted
            assert host.rail_buttons[key].accessibleName()==wanted
            host.set_group_collapsed(True);app.processEvents()
            button=host.rail_buttons[key]
            assert button.height()>=button.fontMetrics().lineSpacing()*len(wanted)
            assert host.rect().contains(button.mapTo(host,QPoint()))
        finally:host.close()

# Actual collapse buttons must have intermediate frames and reverse from the current body size.
def test_float_collapse_uses_shared_motion_and_restores_expanded_bounds(app,monkeypatch):
    import stats_motion
    monkeypatch.setattr(stats_motion,'animations_enabled',lambda:True)
    from map_docking import MapDockHost
    panel=QWidget();layout=QVBoxLayout(panel);layout.addWidget(QLabel('Content'))
    host=MapDockHost(QWidget(),{'single':panel});host.resize(960,680);host.show();app.processEvents()
    try:
        host.float_panel('single',QRect(40,60,360,480));frame=host.frames['single']
        frame.collapse_button.click();QTest.qWait(70)
        assert 38<frame.height()<480
        assert host.findChildren(stats_motion.CollapseMotion)
        frame.collapse_button.click();QTest.qWait(280)
        assert not frame.collapsed and frame.geometry()==QRect(40,60,360,480)
        frame.collapse_button.click();QTest.qWait(190)
        assert frame.height()==38
        host.set_panel_collapsed('single',False)
        assert frame.geometry()==QRect(40,60,360,480)
    finally:host.close()

# Dock group motion changes layout only, including hidden/restore/reduced-motion paths.
def test_group_collapse_animation_preserves_camera_and_query(app,tmp_path,monkeypatch):
    import stats_motion
    monkeypatch.setattr(stats_motion,'animations_enabled',lambda:True)
    from map_page import MapPage
    from map_model import MapSnapshot,MapRoute
    page=MapPage(QSettings(str(tmp_path/'motion.ini'),QSettings.Format.IniFormat))
    page.resize(960,680);page.show();app.processEvents()
    route=MapRoute(10,'Central',10,'a','A','bus',(),(((0.,0.,0.),(100.,0.,0.)),))
    page.set_snapshot(MapSnapshot(routes=(route,)));page.canvas.zoom_in()
    query=page.query;camera=(*page.canvas.center,page.canvas.zoom)
    try:
        page.dock.group_button.click();QTest.qWait(70)
        assert page.dock.stack.isVisible()
        assert 0<page.dock.stack.maximumHeight()<page.dock.height()
        QTest.qWait(190)
        assert page.dock.dock.width()==44
        assert (*page.canvas.center,page.canvas.zoom)==camera and page.query is query
        page.dock.group_button.click();QTest.qWait(280)
        assert page.dock.dock.width()==360
        assert (*page.canvas.center,page.canvas.zoom)==camera and page.query is query
        page.dock.group_button.click();page.hide();app.processEvents()
        assert page.dock.dock.width()==44
        page.dock.set_group_collapsed(False)
        assert page.dock.dock.width()==360
    finally:page.close()

# Surface and sidebar must resolve the same native IDs and company display names.
def test_surface_and_single_share_complete_presentation_catalog(app,tmp_path):
    from map_page import MapPage
    from map_model import MapRoute,MapSnapshot
    from report_model import display_company
    page=MapPage(QSettings(str(tmp_path/'catalog.ini'),QSettings.Format.IniFormat))
    routes=(MapRoute(10,'Central',10,'a','raw-a','bus',(),(((0.,0.,0.),(100.,0.,0.)),)),
            MapRoute(20,'Hill',20,'b','raw-b','tram',(),(((200.,0.,0.),(300.,0.,0.)),)))
    page.set_session({'save_key':'A','companies':[{'公司标识':'a','公司名称':'Resolved company'}]})
    page.set_snapshot(MapSnapshot(routes=routes))
    try:
        page.apply_state({**page.panel_set.state(),'manual_line_ids':[20]})
        matches=page.search('Resolved company')
        assert [match.id for match in matches]==[10]
        page.set_preset('single')
        assert {record['id'] for record in page.single_panel._routes}=={10,20}
        record=next(record for record in page.single_panel._routes if record['id']==10)
        assert record['company_name']==display_company('Resolved company')
        assert record['name'] in matches[0].label
        page.show_route(10,page.save_token)
        assert page.single_panel.state()['selected_route_id']==10
    finally:page.close()

# A moved collapsed title expands at its current location, with its saved body size.
def test_moved_collapsed_float_expands_at_current_title_position(app):
    from map_docking import MapDockHost
    host=MapDockHost(QWidget(),{'single':QWidget()});host.resize(960,680);host.show();app.processEvents()
    try:
        host.float_panel('single',QRect(40,60,360,480));host.set_panel_collapsed('single',True)
        frame=host.frames['single']
        QTest.mousePress(frame.title,Qt.MouseButton.LeftButton,pos=QPoint(10,10))
        QTest.mouseMove(frame.title,QPoint(80,40))
        QTest.mouseRelease(frame.title,Qt.MouseButton.LeftButton,pos=QPoint(80,40))
        moved=frame.pos()
        assert moved!=QPoint(40,60)
        host.set_panel_collapsed('single',False)
        assert frame.pos()==moved and frame.size().width()==360 and frame.height()==480
    finally:host.close()

# Reduced-motion and restoring state remain static even though user clicks support motion.
def test_reduced_motion_restore_and_reset_have_terminal_geometry(app,monkeypatch):
    import stats_motion
    monkeypatch.setattr(stats_motion,'animations_enabled',lambda:False)
    from map_docking import MapDockHost
    host=MapDockHost(QWidget(),{'planning':QWidget()});host.resize(960,680);host.show();app.processEvents()
    try:
        host.float_panel('planning',QRect(80,90,360,480));frame=host.frames['planning']
        frame.collapse_button.click()
        assert frame.height()==38 and not frame.animating
        saved=host.layout_state();host.reset_layout();host.restore_layout(saved)
        assert frame.collapsed and frame.height()==38
        frame.collapse_button.click()
        assert frame.height()==480 and not frame.animating
        host.group_button.click()
        assert host.dock.width()==44 and host.group_motion.animation is None
        host.group_button.click()
        assert host.dock.width()==360
    finally:host.close()

# Fluent SearchLineEdit does not connect returnPressed itself; real Enter must submit once.
def test_surface_enter_submits_unique_route_once(app,tmp_path,monkeypatch):
    from map_page import MapPage
    from map_model import MapRoute,MapSnapshot
    page=MapPage(QSettings(str(tmp_path/'enter.ini'),QSettings.Format.IniFormat));page.resize(960,680);page.show();app.processEvents()
    route=MapRoute(10,'Central',10,'a','A','bus',(),(((0.,0.,0.),(100.,0.,0.)),))
    page.set_session({'save_key':'A'});page.set_snapshot(MapSnapshot(routes=(route,)))
    calls=[];original=page.show_route
    def show(identity,token):calls.append(identity);return original(identity,token)
    monkeypatch.setattr(page,'show_route',show)
    try:
        page.surface.search.setText('Central');page.surface.search.setFocus()
        QTest.keyClick(page.surface.search,Qt.Key.Key_Return);app.processEvents()
        assert page.preset=='single' and [route.id for route in page.result.routes]==[10]
        assert calls==[10]
        assert page.surface.search.text()=='Central'
    finally:page.close()

# Multiple matches open a keyboard list; blank/no-match submits never reuse an old item.
def test_surface_enter_multiple_and_empty_results(app,tmp_path):
    from map_page import MapPage
    from map_model import MapRoute,MapSnapshot
    page=MapPage(QSettings(str(tmp_path/'multiple.ini'),QSettings.Format.IniFormat));page.resize(960,680);page.show();app.processEvents()
    routes=tuple(MapRoute(i,'Central',i,'a','A','bus',(),(((0.,0.,0.),(100.,0.,0.)),)) for i in (10,20))
    page.set_session({'save_key':'A'});page.set_snapshot(MapSnapshot(routes=routes))
    try:
        page.surface.search.setText('Central');page.surface.search.setFocus()
        QTest.keyClick(page.surface.search,Qt.Key.Key_Return);app.processEvents()
        assert page.surface.results.isVisible() and page.surface.results.count()==2
        page.surface.results.setCurrentRow(1)
        QTest.keyClick(page.surface.results,Qt.Key.Key_Return);app.processEvents()
        assert page.presets.state('single')['query']['route_id']==20
        page.surface.search.setText('absent');page.surface.search.setFocus()
        QTest.keyClick(page.surface.search,Qt.Key.Key_Return)
        assert page.surface.results.count()==0 and not page.surface.results.isVisible()
        page.surface.search.setText('');QTest.keyClick(page.surface.search,Qt.Key.Key_Return)
        assert page.surface.results.count()==0
    finally:page.close()

# Search entered during geometry loading is bound to that save's epoch and survives handoff.
def test_loading_enter_replays_current_generation_only(app,tmp_path):
    from map_page import MapPage
    from map_model import MapRoute,MapSnapshot
    page=MapPage(QSettings(str(tmp_path/'pending-search.ini'),QSettings.Format.IniFormat));page.resize(960,680);page.show();app.processEvents()
    route=MapRoute(10,'Central',10,'a','A','bus',(),(((0.,0.,0.),(100.,0.,0.)),))
    try:
        page.set_session({'save_key':'A'})
        page.surface.search.setText('Central');QTest.keyClick(page.surface.search,Qt.Key.Key_Return)
        page.set_snapshot(MapSnapshot(routes=(route,)))
        assert page.preset=='single' and page.presets.state('single')['query']['route_id']==10
        assert page.surface.search.text()=='Central'
        page.set_session({'save_key':'A'})
        page.surface.search.setText('Central');QTest.keyClick(page.surface.search,Qt.Key.Key_Return)
        page.set_session({'save_key':'B'});page.set_snapshot(MapSnapshot(routes=(route,)))
        assert page.presets.state('single')['query']['route_id'] is None
        assert page.result.routes==()
    finally:page.close()

# Repeated loading submits replace the queued text; clear cancels the request entirely.
def test_loading_search_latest_submit_and_clear(app,tmp_path):
    from map_page import MapPage
    from map_model import MapRoute,MapSnapshot
    page=MapPage(QSettings(str(tmp_path/'latest-search.ini'),QSettings.Format.IniFormat))
    routes=tuple(MapRoute(i,name,i,'a','A','bus',(),(((0.,0.,0.),(100.,0.,0.)),))
                 for i,name in ((10,'Central'),(20,'Hill')))
    try:
        page.set_session({'save_key':'A'})
        for text in ('Central','Central','Hill'):
            page.surface.search.setText(text);QTest.keyClick(page.surface.search,Qt.Key.Key_Return)
        page.set_snapshot(MapSnapshot(routes=routes))
        assert page.presets.state('single')['query']['route_id']==20
        page.set_session({'save_key':'B'})
        page.surface.search.setText('Central');QTest.keyClick(page.surface.search,Qt.Key.Key_Return)
        page.surface.search.clearButton.click()
        page.set_snapshot(MapSnapshot(routes=routes))
        assert page.presets.state('single')['query']['route_id'] is None
    finally:page.close()

# A menu containing one collision owner must retain the same full-save label as search.
def test_labels_are_single_row_and_collisions_use_complete_save(app,tmp_path,monkeypatch):
    from map_page import MapPage
    from map_model import MapRoute,MapSnapshot,MapBuilding,BuildingServiceLines
    from display_rules import display_mode
    from report_model import display_company
    page=MapPage(QSettings(str(tmp_path/'labels.ini'),QSettings.Format.IniFormat))
    routes=tuple(MapRoute(i,name,1,owner,company,mode,(),(((0.,0.,0.),(100.,0.,0.)),))
                 for i,name,owner,company,mode in ((10,'1路','a','Alpha','bus'),
                    (20,'1路','b','Beta','bus'),(30,'2路','a','Alpha','bus'),
                    (40,'2路','a','Alpha','bus'),(50,'1路','a','Alpha','tram')))
    building=MapBuilding(1,'','Known',(0,0,0),service_lines=BuildingServiceLines(True,(10,)))
    try:
        page.set_session({'save_key':'A'});page.set_snapshot(MapSnapshot(routes=routes,buildings=(building,)))
        labels={result.id:result.label for result in page.search('路')}
        assert labels[10]==display_company('Alpha')+display_mode('bus')+'1路'
        assert labels[20]==display_company('Beta')+display_mode('bus')+'1路'
        assert labels[30]==labels[40]==display_mode('bus')+'2路'
        assert labels[50]==display_mode('tram')+'1路'
        assert all('[' not in label and '\n' not in label for label in labels.values())
        assert [result.id for result in page.search('2路')]==[30,40]
        page.set_preset('planning')
        received=[]
        monkeypatch.setattr(page.planning_panel,'open_building_menu',lambda b,rows,*args,**kw:received.extend(rows))
        page.show_building(1,QPoint())
        assert len(received)==1 and received[0]['display_label']==labels[10]
    finally:page.close()

# The statistics handoff changes session epoch but continues the same native prefetch.
@pytest.mark.parametrize('geometry_first',[False,True])
def test_prefetch_search_survives_same_source_statistics_handoff(app,tmp_path,monkeypatch,geometry_first):
    from PySide6.QtCore import QObject,Signal
    import map_page
    from map_model import MapRoute,MapSnapshot
    class Worker(QObject):
        completed=Signal(int,object);failed=Signal(int,str);finished=Signal()
        def __init__(self,generation,source,cache,parent):super().__init__(parent);self.generation=generation
        def start(self):pass
        def requestInterruption(self):pass
        def isRunning(self):return False
    monkeypatch.setattr(map_page,'MapWorker',Worker)
    page=map_page.MapPage(QSettings(str(tmp_path/'prefetch-search.ini'),QSettings.Format.IniFormat))
    route=MapRoute(10,'Central',10,'a','A','bus',(),(((0.,0.,0.),(100.,0.,0.)),))
    snapshot=MapSnapshot(routes=(route,))
    calls=[];original=page.show_route
    def show(identity,token):calls.append(identity);return original(identity,token)
    monkeypatch.setattr(page,'show_route',show)
    try:
        source=tmp_path/'A.cim'
        page.start_prefetch(source)
        page.surface.search.setText('Central');QTest.keyClick(page.surface.search,Qt.Key.Key_Return)
        if geometry_first:page.workers[-1].completed.emit(page._generation,snapshot)
        page.set_session({'save_key':'A','save_path':str(source)})
        if not geometry_first:page.workers[-1].completed.emit(page._generation,snapshot)
        assert calls==[10] and page.presets.state('single')['query']['route_id']==10
        assert page.surface.search.text()=='Central'
        page.start_prefetch(source)
        page.surface.search.setText('Central');QTest.keyClick(page.surface.search,Qt.Key.Key_Return)
        page.start_prefetch(tmp_path/'B.cim')
        page.set_session({'save_key':'B','save_path':str(tmp_path/'B.cim')})
        page.workers[-1].completed.emit(page._generation,snapshot)
        assert calls==[10] and page.presets.state('single')['query']['route_id'] is None
    finally:page.close()

# The single view consumes the shared formatted fields; it cannot scale values again.
def test_single_view_receives_shared_information_values(app,tmp_path):
    from map_page import MapPage
    from map_model import MapRoute,MapSnapshot
    from map_line_presentation import line_information
    page=MapPage(QSettings(str(tmp_path/'information.ini'),QSettings.Format.IniFormat))
    route=MapRoute(42,'812E',812,'owner','Raw','bus',(),(((0.,0.,0.),(100.,0.,0.)),))
    session={'save_key':'A','lines':[{'对象ID':42,'线路名称':'812E','公司标识':'owner',
        '公司名称':"jeremylin2005's Company",'运输制式':'公交','地图里程':12.345,
        '站点数':14,'单程时间':55.,'今日客流':0,'平均客流':13.456}]}
    try:
        page.set_session(session);page.set_snapshot(MapSnapshot(routes=(route,)));page.show_route(42,page.save_token)
        info=line_information(session,42)
        label=next(row['display_label'] for row in page._presentation_catalog() if row['id']==42)
        assert page.single_panel.route_title.text()==label
        assert page.single_panel.route_identity.text()==info['identity']['company_name']
        assert set(page.single_panel._data_layouts)=={'line_information','passenger_data'}
        for _,_,rows in info['sections']:
            for key,_,value in rows:assert page.single_panel.information_labels[key].text()==value
    finally:page.close()

# A known line without usable geometry remains readable but Enter cannot navigate it.
def test_unavailable_search_row_is_single_line_without_hover_hint(app):
    from map_page import _MapSurface,_SaveSearchResult
    result=_SaveSearchResult('route',10,'公交1路',(0,0,1,1),('A',1),False)
    calls=[]
    surface=_MapSurface(ColorCanvas('#FF0000'),search=lambda text:[result],focus=calls.append)
    surface.resize(440,240);surface.show();app.processEvents()
    try:
        surface.search.setText('1路');QTest.keyClick(surface.search,Qt.Key.Key_Return)
        item=surface.results.item(0)
        assert item.text()=='公交1路' and item.toolTip()==''
        assert item.data(Qt.ItemDataRole.AccessibleDescriptionRole)=='无地图路径'
        assert not item.flags() & Qt.ItemFlag.ItemIsEnabled
        surface.results.setCurrentItem(item);QTest.keyClick(surface.results,Qt.Key.Key_Return)
        assert calls==[] and surface.results.isVisible()
    finally:surface.close()
