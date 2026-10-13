"""MapCanvas facade contracts shared by the three map presets.

These widget tests exercise Qt input and the independent legend renderer. A
native Windows smoke run must also check OpenGL composition and screenshots.
"""

import pytest
from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtTest import QSignalSpy, QTest

from map_model import BuildingServiceLines, MapBuilding, MapRoute, MapSnapshot, RouteDirection
from map_page import MapPage
from semantic_colors import MetricLegend


def _snapshot():
    routes = (
        MapRoute(1, 'First', 1, 'a', '甲', 'bus', (),
                 (((0., 0., 0.), (100., 0., 0.)),), RouteDirection('one_way')),
        MapRoute(2, 'Second', 2, 'b', '乙', 'tram', (),
                 (((0., 0., 100.), (100., 0., 100.)),), RouteDirection('one_way')),
    )
    building = MapBuilding(
        42, 'depot', 'Triangle', (20., 0., 20.),
        ((0., 0., 0.), (100., 0., 0.), (0., 0., 100.)),
        category='transport',
        service_lines=BuildingServiceLines(True, (2,), source='native', complete=True),
    )
    return MapSnapshot(routes=routes, buildings=(building,), bounds=(0., 0., 100., 100.), source_hash='ui-contract')


@pytest.fixture
def page(qt_application, tmp_path):
    widget = MapPage(QSettings(str(tmp_path / 'vector-ui.ini'), QSettings.Format.IniFormat))
    widget.resize(960, 680)
    widget.show()
    qt_application.processEvents()
    widget.set_session({'save_key': 'vector-ui'})
    widget.set_snapshot(_snapshot())
    qt_application.processEvents()
    yield widget
    widget.close()


@pytest.mark.parametrize('preset,panels', [
    ('single', {'lines', 'single'}),
    ('network', {'layers', 'filters', 'display'}),
    ('planning', {'planning'}),
])
def test_each_preset_keeps_live_canvas_search_and_zoom_controls(page, qt_application, preset, panels):
    canvas, surface, query = page.canvas, page.surface, page.query
    page.set_preset(preset)
    qt_application.processEvents()
    assert page.canvas is canvas and page.surface is surface and page.query is query
    assert surface.parentWidget() is page.dock
    assert set(page.dock.panels) == panels
    assert surface.search.isHidden() and surface.search_button.isVisible()

    view = (canvas.center, canvas.zoom)
    if preset != 'planning':
        for key in panels:
            QTest.mouseClick(page.dock.tabs[key], Qt.MouseButton.LeftButton)
            qt_application.processEvents()
            assert page.dock.stack.currentWidget() is page.dock.frames[key]
            assert (canvas.center, canvas.zoom) == view
    if preset == 'network':
        state = page.panel_set.state()
        state['manual_line_ids'] = [1]
        page.apply_state(state)
        assert [route.id for route in canvas.snapshot.routes] == [1]
    elif preset == 'planning':
        page.planning_panel.selectionChanged.emit({1})
        assert [route.id for route in canvas.snapshot.routes] == [1]
        assert (canvas.center, canvas.zoom) == view

    zoom = canvas.zoom
    zoom_button = surface.controls.layout().itemAt(0).widget()
    QTest.mouseClick(zoom_button, Qt.MouseButton.LeftButton)
    assert canvas.zoom > zoom  # The overlay receives input above the map.

    QTest.mouseClick(surface.search_button, Qt.MouseButton.LeftButton)
    assert surface.search.isVisible() and surface.search.hasFocus()
    QTest.keyClicks(surface.search, 'Second')
    QTest.keyClick(surface.search, Qt.Key.Key_Return)
    qt_application.processEvents()
    assert page.preset == 'single'
    assert page.presets.state('single')['query']['route_id'] == 2
    assert [route.id for route in canvas.snapshot.routes] == [2]
    assert surface.search.isHidden() and surface.search_button.isVisible()


def test_external_legend_is_painted_below_plot_and_reflows_without_navigation(page, qt_application):
    canvas, surface = page.canvas, page.surface
    canvas.center = (35., 45.)
    canvas.zoom = .7
    canvas._changed()
    view = (canvas.center, canvas.zoom)
    legend = MetricLegend('passengers', '2013-05-23', 'today')
    canvas.set_options(legend_items=legend)
    qt_application.processEvents()

    strip = surface.legend_strip
    assert canvas.options['legend_external'] is True
    assert strip.isVisible() and strip.height() == canvas.legend_strip_height(surface.width()) > 0
    assert canvas.height() + strip.height() == surface.height()
    assert canvas.geometry().bottom() < strip.geometry().top()
    painted = strip.grab().toImage()
    assert not painted.isNull()
    middle_y = painted.height() // 2
    assert len({painted.pixelColor(x, middle_y).name() for x in range(0, painted.width(), 4)}) > 8

    for width in (480, 600):
        page.resize(width + page.dock.dock.width(), 680)
        qt_application.sendEvent(surface, QEvent(QEvent.Type.DevicePixelRatioChange))
        qt_application.processEvents()
        assert (canvas.center, canvas.zoom) == view
        assert canvas.height() + strip.height() == surface.height()
        assert strip.height() == canvas.legend_strip_height(surface.width())

    canvas.set_options(legend_items=())
    qt_application.processEvents()
    assert strip.isHidden() and strip.height() == 0
    assert canvas.geometry() == surface.rect()


def test_planning_building_click_uses_polygon_and_opens_native_line_menu(page, qt_application):
    page.set_preset('planning')
    qt_application.processEvents()
    canvas = page.canvas
    hits = QSignalSpy(canvas.buildingClicked)
    outside = canvas.world_to_screen((80., 80.)).toPoint()  # Inside bbox, outside triangle.
    inside = canvas.world_to_screen((20., 20.)).toPoint()
    assert canvas.rect().contains(outside) and canvas.rect().contains(inside)
    assert canvas.building_at(outside) is None
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=outside)
    assert hits.count() == 0
    assert canvas.building_at(inside).id == 42
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=inside)
    qt_application.processEvents()
    assert hits.count() == 1 and hits.at(0)[0] == 42
    menu = page.planning_panel.building_menu
    assert menu is not None and menu.isVisible()
    assert [menu.line_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(menu.line_list.count())] == [2]
    assert menu.line_list.item(0).flags() & Qt.ItemFlag.ItemIsEnabled
