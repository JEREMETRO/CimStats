"""Preset changes retain loading feedback until the new current frame exists."""
import pytest
from PySide6.QtCore import QSettings
from map_model import MapRoad,MapRoute,MapSnapshot
from map_page import MapPage


@pytest.mark.parametrize('previous',['single','planning'])
def test_network_switch_waits_for_its_current_frame(qt_application,tmp_path,monkeypatch,previous):
    page=MapPage(QSettings(str(tmp_path/'map.ini'),QSettings.Format.IniFormat))
    page.resize(960,680)
    page.set_session({'save_key':'preset-loading'})
    page.set_preset(previous)
    path=((0.,0.,0.),(100.,0.,100.))
    snapshot=MapSnapshot(roads=(MapRoad(1,'r','R',(path,),width=12.,road_class='ordinary'),),
        routes=(MapRoute(7,'7',7,'a','A','bus',(),(path,)),),bounds=(0.,0.,100.,100.))
    page._requested=True
    page.set_snapshot(snapshot)
    page.show();qt_application.processEvents();page.canvas.prepare_frame()
    try:
        assert page.canvas.can_export()
        assert not page.surface.loading.isVisible()
        monkeypatch.setattr(page.canvas,'prepare_frame',lambda:None)
        page.set_preset('network')
        assert not page.canvas.can_export()
        assert page._awaiting_frame and page.surface.loading.isVisible()
        # A stale completion cannot dismiss the current request's indicator.
        page.canvas.frame_ready.emit()
        assert page._awaiting_frame and page.surface.loading.isVisible()
        page.canvas._render_frame(page.canvas._render_key(),(*page.canvas.center,page.canvas.zoom))
        assert page.canvas.can_export()
        assert not page._awaiting_frame and not page.surface.loading.isVisible()
    finally:page.close()


def test_successful_same_geometry_refresh_recovers_after_index_failure(qt_application):
    from map_canvas import MapCanvas, _index_key
    canvas = MapCanvas()
    canvas.resize(400, 300)
    path = ((0., 0., 0.), (100., 0., 100.))
    snapshot = MapSnapshot(roads=(MapRoad(1, 'r', 'Road', (path,)),),
                           source_hash='retry-index', bounds=(0., 0., 100., 100.))
    try:
        canvas.set_snapshot(snapshot)
        canvas._indexes_failed(_index_key(snapshot), 'temporary failure')
        assert not canvas.can_export()
        # Reapplying the same selection is an explicit retry, with unchanged geometry.
        canvas.set_snapshot(snapshot)
        canvas.prepare_frame()
        assert canvas.can_export(), 'A successful retry must not retain the earlier failure marker'
    finally:
        canvas.close()
