"""Map navigation must use the shared header and a browsable single-line catalog."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import QSettings,Qt,QPoint
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path/'navigation.ini'),QSettings.Format.IniFormat)


def snapshot():
    from map_model import MapRoute,MapSnapshot
    routes=tuple(MapRoute(i,name,i,'a','Alpha','bus',(),(((float(i),0.,0.),(100.+i,0.,0.)),))
                 for i,name in ((10,'Central'),(20,'Hill')))
    return MapSnapshot(routes=routes,bounds=(0.,0.,150.,100.),source_hash='A')


# Catch duplicate page tabs, divergent header sizing, and the wrong narrow-window row.
@pytest.mark.parametrize('width,height',[(1440,960),(960,680)])
def test_map_subtabs_share_statistics_header_placement(app,settings,monkeypatch,width,height):
    import desktop_app
    monkeypatch.setattr(desktop_app,'QSettings',lambda *_:settings)
    monkeypatch.setattr(desktop_app.MainWindow,'check_install',lambda _:None)
    window=desktop_app.MainWindow();window.resize(width,height);window.show();app.processEvents()
    try:
        window.navigate(3);app.processEvents()
        window.stats_tabs.setEnabled(True)
        statistics_stacked=window.header._stacked_tabs
        statistics_height=window.header.height()
        statistics_tab_height=window.stats_tabs.height()
        statistics_tab_y=window.stats_tabs.mapTo(window.header,QPoint()).y()
        statistics_tab_x=window.stats_tabs.mapTo(window.header,QPoint()).x()
        statistics_tab_width=window.stats_tabs.width()
        reference=window.stats_tabs.items['company']
        window.navigate(1);app.processEvents()
        tabs=window.map_page.preset_pivot
        assert window.header._page_widget is tabs
        assert tabs.parentWidget() is window.header.page_slot_host
        assert window.map_page.layout().indexOf(tabs)==-1
        assert tabs.isVisibleTo(window) and window.stats_tabs.isHidden()
        assert window.header._stacked_tabs==statistics_stacked
        assert window.header.height()==statistics_height
        assert tabs.minimumHeight()==40 and tabs.height()==statistics_tab_height
        assert tabs.mapTo(window.header,QPoint()).y()==statistics_tab_y
        assert tabs.mapTo(window.header,QPoint()).x()==statistics_tab_x
        assert tabs.width()==statistics_tab_width
        for key,tab in tabs.items.items():
            assert tab.width()==118 and tab.minimumHeight()==36
            assert tab.font().pixelSize()==14
            assert tab.iconSize().width()==18 and not tab.icon().isNull()
            assert tab.styleSheet()==reference.styleSheet()
            assert window.header.rect().contains(tab.mapTo(window.header,QPoint()))
        for selected in (reference,tabs.items['network']):
            image=QImage(selected.size(),QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(QColor('white'));selected.render(image)
            assert any(image.pixelColor(x,y).name()=='#0067c0'
                       for x in range(34,image.width()-4) for y in range(4,image.height()-4))
        window.map_page.set_preset('planning')
        icon=tabs.items['planning'].icon().pixmap(18,18).toImage()
        assert any(icon.pixelColor(x,y).name()=='#0067c0'
                   for x in range(icon.width()) for y in range(icon.height()))
        QTest.mouseClick(tabs.items['single'],Qt.MouseButton.LeftButton);app.processEvents()
        assert window.map_page.preset=='single'
        window.navigate(3);app.processEvents()
        assert tabs.isHidden() and window.header._page_widget is window.stats_tabs
        window.navigate(1);app.processEvents()
        assert window.header._page_widget is tabs and window.map_page.preset=='single'
    finally:window.close();app.processEvents()


# The default catalog remains complete despite an excluding network query.
def test_single_catalog_is_default_and_selection_opens_information(app,settings):
    from map_page import MapPage
    page=MapPage(settings);page.resize(960,680);page.show();app.processEvents()
    page.set_session({'save_key':'A'});page.set_snapshot(snapshot())
    page.apply_state({**page.panel_set.state(),'manual_line_ids':[10]})
    page.set_preset('single');app.processEvents()
    try:
        host=page.dock
        assert [tab.text() for tab in host.tabs.values()]==['线路列表','线路信息']
        assert host.layout_state()['active']=='lines'
        listing=page.single_list_panel
        identities=[listing.route_list.item(i).data(Qt.ItemDataRole.UserRole)
                    for i in range(listing.route_list.count())]
        assert identities==[10,20]
        item=listing.route_list.item(1)
        QTest.mouseClick(listing.route_list.viewport(),Qt.MouseButton.LeftButton,
                         pos=listing.route_list.visualItemRect(item).center())
        app.processEvents()
        assert page.presets.state('single')['query']['route_id']==20
        assert host.layout_state()['active']=='single'
        assert [route.id for route in page.result.routes]==[20]
        assert page.canvas.center==(70.,0.)
        query=page.query;indexes=page.canvas._index_state;view=(*page.canvas.center,page.canvas.zoom)
        QTest.mouseClick(host.tabs['lines'],Qt.MouseButton.LeftButton);app.processEvents()
        assert host.layout_state()['active']=='lines'
        assert listing.route_list.currentItem().data(Qt.ItemDataRole.UserRole)==20
        assert page.query is query and (*page.canvas.center,page.canvas.zoom)==view
        assert page.canvas._index_state is indexes
        page.canvas.center=(40.,50.);page.canvas.zoom=.7;page.canvas._changed()
        retained_snapshot=page.canvas.snapshot
        QTest.keyClick(listing.route_list,Qt.Key.Key_Return)
        assert host.layout_state()['active']=='single'
        assert (*page.canvas.center,page.canvas.zoom)==(40.,50.,.7)
        assert page.canvas.snapshot is retained_snapshot and page.canvas._index_state is indexes
    finally:page.close()


# A detail jump made before the page is shown must override a pending saved list tab.
def test_hidden_route_jump_keeps_information_active_after_layout_restore(app,settings):
    from map_page import MapPage
    page=MapPage(settings);page.resize(960,680)
    page.set_session({'save_key':'A'});page.set_snapshot(snapshot())
    saved={'active':'lines','dock_width':360,'group_collapsed':False,
           'panels':{'single':{'floating':False},'lines':{'floating':False}}}
    page.presets.update('single',layout=saved)
    try:
        assert page.show_route(20,page.save_token)
        page.show();app.processEvents();QTest.qWait(20)
        assert page.dock.layout_state()['active']=='single'
        assert page.presets.state('single')['query']['route_id']==20
        page.dock.activate_panel('lines')
        assert page.dock.layout_state()['active']=='lines'
        page.surface.search.setText('Central');QTest.keyClick(page.surface.search,Qt.Key.Key_Return)
        assert page.dock.layout_state()['active']=='single'
        assert page.presets.state('single')['query']['route_id']==10
    finally:page.close()


# Adding a tab must preserve the old saved information frame and preset query/view.
def test_legacy_single_layout_preserves_information_geometry_and_preset_state(app,settings):
    from map_page import MapPage
    page=MapPage(settings);page.resize(960,680);page.show();app.processEvents()
    page.set_session({'save_key':'A'});page.set_snapshot(snapshot())
    page.presets.update('single',query={'route_id':20},view=[25.,40.,.5],layout={
        'active':'single','panels':{'single':{'floating':True,'pinned':True,
            'geometry':[40,60,300,400],'expanded_geometry':[40,60,300,400]}}})
    try:
        page.set_preset('single');app.processEvents();QTest.qWait(20)
        assert set(page.dock.frames)=={'lines','single'}
        frame=page.dock.frames['single']
        assert frame.floating and frame.pinned
        assert frame.geometry().getRect()==(40,60,300,400)
        assert page.presets.state('single')['query']['route_id']==20
        assert (*page.canvas.center,page.canvas.zoom)==(25.,40.,.5)
        page.dock.activate_panel('lines')
        assert page.single_list_panel.route_list.currentItem().data(Qt.ItemDataRole.UserRole)==20
    finally:page.close()


# Moving desktop tabs into its header must not remove standalone page navigation.
def test_standalone_map_keeps_its_preset_navigation(app,settings):
    from map_page import MapPage
    page=MapPage(settings);page.resize(960,680);page.show();app.processEvents()
    try:
        assert page.layout().indexOf(page.preset_pivot)>=0
        QTest.mouseClick(page.preset_pivot.items['planning'],Qt.MouseButton.LeftButton)
        assert page.preset=='planning'
    finally:page.close()


# Reusing a single dock across saves must not leave an empty information tab selected.
def test_new_save_defaults_to_list_but_queued_detail_jump_opens_information(app,settings):
    from map_page import MapPage
    page=MapPage(settings);page.resize(960,680);page.show();app.processEvents()
    page.set_session({'save_key':'A'});page.set_snapshot(snapshot());page.show_route(20,page.save_token)
    try:
        page.set_session({'save_key':'B'})
        assert page.dock.layout_state()['active']=='lines'
        assert page.single_list_panel.route_list.count()==0
        assert page.single_list_panel.state()['selected_route_id'] is None
        assert page.show_route(20,page.save_token)
        assert page.dock.layout_state()['active']=='single'
        page.set_snapshot(snapshot())
        assert page.dock.layout_state()['active']=='single'
        assert page.presets.state('single')['query']['route_id']==20
        assert page.single_list_panel.route_list.currentItem().data(Qt.ItemDataRole.UserRole)==20
    finally:page.close()


# A restored route without an old dock layout can open its information directly.
def test_existing_route_opens_information_when_single_dock_is_first_created(app,settings):
    from map_page import MapPage
    page=MapPage(settings);page.resize(960,680);page.show();app.processEvents()
    page.set_session({'save_key':'A'});page.set_snapshot(snapshot())
    page.presets.update('single',query={'route_id':20},view=[25.,40.,.5])
    try:
        page.set_preset('single')
        assert page.dock.layout_state()['active']=='single'
        assert page.single_list_panel.state()['selected_route_id']==20
        assert (*page.canvas.center,page.canvas.zoom)==(25.,40.,.5)
    finally:page.close()


# Extracting styles must preserve the statistics page's original standalone font.
def test_standalone_statistics_pivot_keeps_existing_dimensions_and_font(app,settings):
    from statistics_page import StatisticsPage
    page=StatisticsPage(settings)
    try:
        for item in page.tab_bar.items.values():
            assert item.font().pixelSize()==18
            assert item.width()==148 and item.minimumHeight()==40
        assert page.tab_bar.minimumHeight()==40
    finally:page.close()
