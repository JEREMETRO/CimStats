"""The page reserves real space for the shared legend instead of covering the plot."""
import pytest
from PySide6.QtCore import QEvent,QSettings
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QWidget,QStackedWidget
from map_canvas import MapCanvas
from map_model import MapSnapshot,MapRoute,RouteDirection
from semantic_colors import MetricLegend


def snapshot():
    route=MapRoute(1,'1',1,'a','甲公司','bus',(),(((0.,0.,0.),(100.,0.,100.)),),RouteDirection('one_way'))
    return MapSnapshot(routes=(route,),bounds=(0.,0.,100.,100.))


def events(application):
    for _ in range(3):application.processEvents()


@pytest.mark.parametrize('legend',[
    MetricLegend('interval','2013-05-23'),MetricLegend('interval_peak','2013-05-23'),
    MetricLegend('passengers','2013-05-23','today'),(('公交','#0067c0'),('有轨电车','#ff0000')),
])
def test_surface_places_every_nonempty_legend_below_the_actual_plot(qt_application,legend):
    from map_page import _MapSurface
    canvas=MapCanvas();surface=_MapSurface(canvas);surface.resize(480,440);surface.show();events(qt_application)
    canvas.set_snapshot(snapshot());canvas.set_options(legend_items=legend);events(qt_application)
    strip=surface.legend_strip
    assert canvas.options['legend_external'] is True
    assert not strip.isHidden() and strip.height()==canvas.legend_strip_height(surface.width())>0
    assert canvas.geometry().bottom()<strip.geometry().top()
    assert strip.geometry().bottom()==surface.height()-1 and strip.width()==surface.width()
    assert canvas.height()+strip.height()==surface.height()
    for overlay in (surface.search,surface.results,surface.controls,surface.loading):
        assert overlay.geometry().bottom()<canvas.height()


def test_legend_change_resize_and_dpi_reflow_keep_the_user_view(qt_application):
    from map_page import _MapSurface
    canvas=MapCanvas();surface=_MapSurface(canvas);surface.resize(520,440);surface.show();events(qt_application)
    canvas.set_snapshot(snapshot());canvas.center=(34.,56.);canvas.zoom=.71;canvas._changed()
    spy=QSignalSpy(canvas.view_changed)
    for width,legend in [(520,MetricLegend('interval','2013-05-23')),
                         (310,MetricLegend('passengers','2013-05-23','average')),
                         (720,(('公交','#0067c0'),)),(720,())]:
        canvas.set_options(legend_items=legend);surface.resize(width,440)
        qt_application.sendEvent(surface,QEvent(QEvent.Type.DevicePixelRatioChange));events(qt_application)
        assert (canvas.center,canvas.zoom)==((34.,56.),.71) and spy.count()==0
        assert canvas.height()+surface.legend_strip.height()==surface.height()
        assert surface.legend_strip.height()==canvas.legend_strip_height(width)
    assert surface.legend_strip.isHidden() and surface.legend_strip.height()==0
    assert canvas.geometry()==surface.rect()


def test_footer_paints_with_the_same_canvas_renderer(qt_application,monkeypatch):
    from map_page import _MapSurface
    canvas=MapCanvas();surface=_MapSurface(canvas);surface.resize(480,440);surface.show()
    canvas.set_options(legend_items=MetricLegend('passengers','2013-05-23','today'))
    calls=[];paint=canvas.paint_legend_strip
    def record(painter,rect):calls.append(rect);paint(painter,rect)
    monkeypatch.setattr(canvas,'paint_legend_strip',record);events(qt_application)
    surface.legend_strip.grab()
    assert calls and calls[-1].toRect()==surface.legend_strip.rect()


@pytest.mark.parametrize('clear',['new_session','cancel'])
def test_clearing_the_source_removes_the_old_legend_and_reserved_height(qt_application,tmp_path,clear):
    from map_page import MapPage
    page=MapPage(QSettings(str(tmp_path/'source.ini'),QSettings.Format.IniFormat))
    page.resize(960,680);page.show();page.set_session({'save_key':'A'})
    page.set_snapshot(snapshot());page.canvas.set_options(legend_items=MetricLegend('passengers','2013-05-23','today'))
    events(qt_application);assert page.surface.legend_strip.height()>0
    if clear=='new_session':page.set_session({'save_key':'B'})
    else:page.cancel_prefetch()
    events(qt_application)
    assert not page.canvas.options['legend_items']
    assert page.surface.legend_strip.isHidden() and page.surface.legend_strip.height()==0
    assert page.canvas.geometry()==page.surface.rect()


def test_hidden_page_prewarms_the_plot_size_and_reuses_the_current_frame(qt_application,tmp_path):
    from map_page import MapPage
    stack=QStackedWidget();stack.resize(1200,800);stack.addWidget(QWidget())
    page=MapPage(QSettings(str(tmp_path/'hidden.ini'),QSettings.Format.IniFormat));stack.addWidget(page)
    stack.show();events(qt_application)
    page.set_session({'save_key':'A','simulation_time':'2013-05-23T23:30:00'})
    page.panel_set.set_state({'color_by':'passengers'})
    page._requested=True;page._loaded(page._generation,snapshot())
    assert not page.isVisible() and page.canvas.width()>700
    assert page.surface.legend_strip.height()==page.canvas.legend_strip_height(page.surface.width())>0
    assert page.canvas.geometry().bottom()<page.surface.legend_strip.geometry().top()
    assert page.canvas.can_export()
    before=(page.canvas.size(),page.canvas._frame_key,page.canvas._frame_view,page.canvas.center,page.canvas.zoom)
    stack.setCurrentWidget(page);events(qt_application)
    assert (page.canvas.size(),page.canvas._frame_key,page.canvas._frame_view,page.canvas.center,page.canvas.zoom)==before
    assert page.canvas.can_export()
