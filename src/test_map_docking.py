import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QRect, QPoint, Qt
from PySide6.QtTest import QTest

@pytest.fixture(scope='module')
def app(): return QApplication.instance() or QApplication([])

def host():
    from map_docking import MapDockHost
    h=MapDockHost(QWidget(), {'layers':QWidget(),'filters':QWidget(),'display':QWidget()})
    h.resize(960,680); h.show(); QApplication.processEvents(); return h

def test_float_is_child_and_clamped_after_resize_restore(app):
    h=host(); h.float_panel('layers', QRect(2000,2000,500,800))
    f=h.frames['layers']
    assert not f.isWindow() and h.rect().contains(f.geometry())
    state=h.layout_state(); h.resize(720,480); h.restore_layout(state)
    assert h.rect().contains(f.geometry())
    h.reset_layout(); assert not h.layout_state()['panels']['layers']['floating']
    h.close()

def test_pin_prevents_title_drag_but_allows_collapse(app):
    h=host(); h.float_panel('layers',QRect(40,40,300,400)); h.set_pinned('layers',True)
    f=h.frames['layers']; before=f.geometry()
    QTest.mousePress(f.title,Qt.MouseButton.LeftButton,pos=QPoint(20,15))
    QTest.mouseMove(f.title,QPoint(100,80)); QTest.mouseRelease(f.title,Qt.MouseButton.LeftButton,pos=QPoint(100,80))
    assert f.geometry()==before
    f.collapse_button.click(); assert h.layout_state()['panels']['layers']['collapsed']
    h.close()

def test_dock_group_collapse_and_redock_preserve_widget_identity(app):
    h=host(); panel=h.panels['filters']; h.float_panel('filters',QRect(10,10,300,400))
    h.dock_panel('filters'); h.set_group_collapsed(True)
    assert h.panels['filters'] is panel and h.dock.width()<=50
    h.set_group_collapsed(False); assert h.dock.width()==360
    h.close()

def test_title_drag_redocks_and_controls_do_not_move_panel(app):
    h=host(); h.float_panel('layers',QRect(40,40,300,400)); f=h.frames['layers']
    before=f.geometry()
    QTest.mousePress(f.collapse_button,Qt.MouseButton.LeftButton,pos=QPoint(10,10))
    QTest.mouseMove(f.collapse_button,QPoint(80,50)); QTest.mouseRelease(f.collapse_button,Qt.MouseButton.LeftButton,pos=QPoint(80,50))
    assert f.pos()==before.topLeft()
    h.set_panel_collapsed('layers',False)
    title=f.title
    QTest.mousePress(title,Qt.MouseButton.LeftButton,pos=QPoint(10,10))
    QTest.mouseMove(title,QPoint(45,10))
    target=title.mapFrom(h,QPoint(h.width()-10,90))
    QTest.mouseMove(title,target)
    assert h.preview.isVisible()
    QTest.mouseRelease(title,Qt.MouseButton.LeftButton,pos=target)
    assert not f.floating and not h.preview.isVisible()
    h.close()

def test_resize_grip_changes_geometry_and_pin_locks_it(app):
    h=host(); h.float_panel('layers',QRect(20,20,300,300)); f=h.frames['layers']; grip=f.grips[-1]
    QTest.mousePress(grip,Qt.MouseButton.LeftButton,pos=QPoint(4,4)); QTest.mouseMove(grip,QPoint(54,64))
    QTest.mouseRelease(grip,Qt.MouseButton.LeftButton,pos=QPoint(4,4))
    assert f.width()==350 and f.height()==360
    h.set_pinned('layers',True); before=f.geometry()
    QTest.mousePress(grip,Qt.MouseButton.LeftButton,pos=QPoint(4,4)); QTest.mouseMove(grip,QPoint(94,94))
    QTest.mouseRelease(grip,Qt.MouseButton.LeftButton,pos=QPoint(4,4))
    assert f.geometry()==before
    h.close()

def test_tab_drag_detaches_single_panel_and_state_restore_preserves_content(app):
    from map_panels import MapPanelSet
    from test_map_panels import options
    from map_docking import MapDockHost
    p=MapPanelSet(); p.set_options(options()); p.set_state({'direction':'up','manual_line_ids':[]})
    h=MapDockHost(QWidget(),p.panels); h.resize(960,680); h.show(); app.processEvents()
    tab=h.tabs['filters']; QTest.mousePress(tab,Qt.MouseButton.LeftButton,pos=QPoint(20,15))
    QTest.mouseMove(tab,QPoint(-70,55)); QTest.mouseRelease(tab,Qt.MouseButton.LeftButton,pos=QPoint(-70,55))
    assert h.frames['filters'].floating
    assert sum(f.floating for f in h.frames.values())==1
    layout=h.layout_state(); h.reset_layout(); h.restore_layout(layout)
    assert h.frames['filters'].floating
    assert p.state()['direction']=='up' and p.state()['manual_line_ids']==set()
    h.close()

def test_float_title_moves_on_first_threshold_crossing(app):
    h=host(); h.float_panel('layers',QRect(20,20,300,400)); f=h.frames['layers']
    title=f.title
    QTest.mousePress(title,Qt.MouseButton.LeftButton,pos=QPoint(10,10))
    QTest.mouseMove(title,QPoint(60,40)); QTest.mouseRelease(title,Qt.MouseButton.LeftButton,pos=QPoint(60,40))
    assert f.x()==70 and f.y()==50
    h.close()

def test_collapsed_float_restores_expanded_rect_and_clamps_to_new_window(app):
    h=host(); h.float_panel('display',QRect(200,100,400,500)); h.set_panel_collapsed('display',True)
    saved=h.layout_state(); h.reset_layout(); h.resize(800,600); h.restore_layout(saved)
    frame=h.frames['display']
    assert frame.height()==38 and frame.collapsed
    h.set_panel_collapsed('display',False)
    assert frame.width()==400 and frame.height()==500
    assert h.rect().contains(frame.geometry())
    h.close()

@pytest.mark.parametrize('collapsed',[False,True])
def test_map_page_restart_preserves_saved_float_until_real_layout(app,tmp_path,collapsed):
    import json
    from PySide6.QtCore import QSettings
    from map_page import MapPage
    path=str(tmp_path/'map-restart.ini')
    settings=QSettings(path,QSettings.Format.IniFormat)
    first=MapPage(settings); first.resize(1440,960); first.show(); app.processEvents()
    expected=QRect(500,200,360,520)
    first.dock.float_panel('layers',expected); first.dock.set_pinned('layers',True)
    if collapsed:first.dock.set_panel_collapsed('layers',True)
    saved=json.loads(settings.value('map/layout')); settings.sync(); first.close()
    restored=MapPage(QSettings(path,QSettings.Format.IniFormat))
    # Constructor-sized host must never persist a smaller rectangle.
    assert restored.dock.layout_state()['panels']['layers']['expanded_geometry']==[500,200,360,520]
    assert json.loads(restored.settings.value('map/layout'))==saved
    restored.resize(1440,960); restored.show(); app.processEvents(); app.processEvents()
    frame=restored.dock.frames['layers']
    assert frame.floating and frame.pinned
    assert frame.expanded_geometry==expected
    assert frame.geometry()==(QRect(500,200,360,38) if collapsed else expected)
    if collapsed:
        frame.collapse_button.click()
        QTest.qWait(280)  # User-triggered expansion now follows shared Fluent motion.
        assert frame.geometry()==expected
    restored.close()

def test_hidden_restore_waits_for_final_parent_size_before_clamping(app,tmp_path):
    import json
    from PySide6.QtCore import QSettings
    from map_page import MapPage
    settings=QSettings(str(tmp_path/'deferred.ini'),QSettings.Format.IniFormat)
    original={'panels':{'layers':{'floating':True,'geometry':[500,200,360,520],
                                'expanded_geometry':[500,200,360,520]}}}
    settings.setValue('map/layout',json.dumps(original))
    page=MapPage(settings); page.resize(640,360); app.processEvents()
    assert json.loads(settings.value('map/layout'))==original
    page.resize(1440,960); page.show(); app.processEvents(); app.processEvents()
    assert page.dock.frames['layers'].geometry()==QRect(500,200,360,520)
    page.close()

def test_deferred_map_page_restore_clamps_to_final_viewport_only(app,tmp_path):
    import json
    from PySide6.QtCore import QSettings
    from map_page import MapPage
    settings=QSettings(str(tmp_path/'outside.ini'),QSettings.Format.IniFormat)
    saved={'panels':{'layers':{'floating':True,'geometry':[2500,1500,360,520],
                             'expanded_geometry':[2500,1500,360,520]}}}
    settings.setValue('map/layout',json.dumps(saved))
    page=MapPage(settings)
    assert page.dock.layout_state()['panels']['layers']['geometry']==[2500,1500,360,520]
    page.resize(960,680); page.show(); app.processEvents(); app.processEvents()
    frame=page.dock.frames['layers']
    assert frame.width()==360 and frame.height()==520
    assert page.dock.rect().contains(frame.geometry())
    persisted=json.loads(settings.value('map/layout'))['panels']['layers']
    assert persisted['geometry']==[frame.x(),frame.y(),360,520]
    page.close()
