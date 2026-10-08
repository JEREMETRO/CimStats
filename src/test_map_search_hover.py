import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QEvent, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from map_page import MapPage
from map_model import MapRoute, MapSnapshot, RouteDirection


def test_selected_route_search_expands_on_hover_and_keeps_input_focus(tmp_path):
    app = QApplication.instance() or QApplication([])
    page = MapPage(QSettings(str(tmp_path/'hover.ini'), QSettings.Format.IniFormat))
    page.resize(960, 680); page.show(); app.processEvents()
    surface = page.surface
    assert not surface.search.isHidden()
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
    assert not surface.search.isHidden()
    assert surface.search_button.isHidden()
    page.close()
