"""Single route export settings, geometry and asynchronous result contracts."""
import pytest


@pytest.fixture
def dialog():
    from PySide6.QtWidgets import QApplication
    from route_export_dialog import RouteExportDialog
    from route_export_model import ExportOptions, build_export_request
    from map_model import MapSnapshot, MapRoute, RouteDirection
    app = QApplication.instance() or QApplication([])
    paths = (((0., 0., 0.), (100., 0., 0.)), ((100., 0., 0.), (0., 0., 0.)))
    route = MapRoute(42, '1', 1, 'c', '公司', 'bus', (), paths,
                     RouteDirection('roundtrip', 1), ((paths[0],), (paths[1],)))
    session = {'save_key': 'a', 'lines': [{'对象ID': 42, '线路名称': '1', '公司标识': 'c'}]}
    snapshot = MapSnapshot(routes=(route,))
    builder = lambda options: build_export_request(session, snapshot, 42, options)
    widget = RouteExportDialog(builder(ExportOptions()), request_builder=builder, start_preview=False)
    yield widget
    widget.reject()
    app.processEvents()


def test_dimensions_and_a4_orientation_follow_shared_measurement():
    from PySide6.QtWidgets import QApplication
    from route_export_dialog import RouteExportDialog
    from route_export_model import ExportOptions, build_export_request
    from map_model import MapSnapshot, MapRoute, RouteDirection
    app = QApplication.instance() or QApplication([])
    route = MapRoute(42, '1', 1, 'c', '公司', 'bus', (), (((0., 0., 0.), (100., 0., 0.)),), RouteDirection('one_way'))
    session = {'save_key': 'a', 'lines': [{'对象ID': 42, '线路名称': '1', '公司标识': 'c'}]}
    builder = lambda options: build_export_request(session, MapSnapshot(routes=(route,)), 42, options)
    dialog = RouteExportDialog(builder(ExportOptions()), request_builder=builder, start_preview=False)
    dialog.width_edit.setValue(127)
    assert abs(dialog.height_edit.value() - 84.67) < .01
    assert dialog.pixel_label.text() == '1500 × 1000 像素'
    dialog.aspect_control.setCurrentKey('A4')
    assert dialog.pixel_label.text() == '3508 × 2480 像素'
    assert not dialog.width_edit.isEnabled()
    dialog.orientation_control.setCurrentKey('portrait')
    assert dialog.pixel_label.text() == '2480 × 3508 像素'
    dialog.reject()
    app.processEvents()


def test_latest_options_invalidate_old_preview_and_closed_results(dialog):
    from PySide6.QtGui import QImage
    old = QImage(8, 8, QImage.Format.Format_RGB32)
    dialog._generation = 1
    dialog.theme_control.setCurrentKey('night')
    dialog._ready(1, old)
    assert dialog.preview.image.isNull()
    dialog._generation = 2
    dialog._ready(2, old)
    assert not dialog.preview.image.isNull()
    dialog.reject()
    dialog.preview.image = QImage()
    dialog._ready(2, old)
    assert dialog.preview.image.isNull()


def test_data_selection_and_direction_rebuild_real_request(dialog):
    dialog._select_fields('none')
    assert dialog._current_request().information.sections == ()
    dialog._select_fields('all')
    dialog.direction_control.setCurrentKey('up')
    request = dialog._current_request()
    assert request.metrics.effective_direction == 'up'
    assert len(request.paths) == 1
    assert len(request.options.selected_fields) == 18


def test_operating_time_defaults_first_and_user_can_explicitly_hide_it(dialog):
    assert next(iter(dialog.field_checks))=='运营时间'
    assert dialog.field_checks['运营时间'].isChecked()
    assert dialog._current_request().information.sections[0][2][0][0]=='运营时间'
    dialog.field_checks['运营时间'].setChecked(False)
    assert all(key!='运营时间' for _,_,rows in dialog._current_request().information.sections
               for key,_,_ in rows)


def test_small_window_keeps_fixed_actions_and_scrolls_settings(dialog):
    from PySide6.QtWidgets import QApplication
    dialog._initial_content_sized = True
    dialog.resize(900, 620)
    dialog.show()
    QApplication.processEvents()
    assert dialog.pages.widget(0).verticalScrollBar().maximum() > 0
    assert dialog.cancel_button.isVisible() and dialog.export_button.isVisible()
    assert dialog.export_button.mapTo(dialog, dialog.export_button.rect().bottomRight()).y() < dialog.height() - 16
    assert dialog.preview.width() < 600


@pytest.mark.parametrize('workarea', [(1600, 1000), (960, 680)])
def test_initial_dialog_is_compact_and_fits_available_workarea(dialog, monkeypatch, workarea):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QScreen
    from PySide6.QtWidgets import QApplication
    area = QRect(0, 0, *workarea)
    monkeypatch.setattr(QScreen, 'availableGeometry', lambda _: area)
    dialog.show()
    QApplication.processEvents()
    # Opening the settings must not create a nearly full-height desktop window.
    assert 900 <= dialog.width() <= min(1100, area.width() - 32)
    assert 600 <= dialog.height() <= min(760, area.height() - 32)
    assert area.contains(dialog.geometry())
    assert dialog.pages.widget(0).verticalScrollBar().maximum() > 0
    assert dialog.preview.width() >= 500


def test_compact_dialog_scrolls_to_last_settings_and_data_without_moving_actions(dialog):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    dialog._initial_content_sized = True
    dialog.resize(960, 680)
    dialog.show()
    QTest.qWait(30)
    action_rect = dialog.action_bar.geometry()
    settings = dialog.pages.widget(0)
    settings.ensureWidgetVisible(dialog.reset_colors)
    QTest.qWait(30)
    assert settings.verticalScrollBar().value() > 0
    assert settings.viewport().rect().contains(dialog.reset_colors.mapTo(settings.viewport(), QPoint()))
    assert settings.viewport().rect().contains(
        dialog.reset_colors.mapTo(settings.viewport(), dialog.reset_colors.rect().bottomRight()))
    dialog.color_edits[0].setText('#123456')
    dialog.color_edits[0].textEdited.emit('#123456')
    QTest.mouseClick(dialog.reset_colors, Qt.MouseButton.LeftButton)
    assert dialog.options().brand_override is None
    QTest.mouseClick(dialog.tabs.items['data'], Qt.MouseButton.LeftButton)
    data = dialog.pages.widget(1)
    last_field = next(reversed(dialog.field_checks.values()))
    data.ensureWidgetVisible(last_field)
    QTest.qWait(30)
    assert data.viewport().rect().contains(last_field.mapTo(data.viewport(), last_field.rect().bottomRight()))
    before = last_field.isChecked()
    QTest.mouseClick(last_field, Qt.MouseButton.LeftButton, pos=QPoint(10, last_field.height() // 2))
    assert last_field.isChecked() != before
    assert dialog.action_bar.geometry() == action_rect
    for button in (dialog.cancel_button, dialog.export_button):
        assert dialog.rect().contains(button.mapTo(dialog, button.rect().bottomRight()))


def test_tab_clicks_repeatedly_return_to_settings_with_matching_selection(dialog):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    dialog._initial_content_sized = True
    dialog.resize(960, 680)
    dialog.show()
    QTest.qWait(30)
    for key, index in (('data', 1), ('settings', 0)) * 4:
        QTest.mouseClick(dialog.tabs.items[key], Qt.MouseButton.LeftButton)
        assert dialog.pages.currentIndex() == index
        assert dialog.tabs.currentRouteKey() == key
        assert dialog.pages.currentWidget().isVisible()


@pytest.mark.parametrize('key', ['settings', 'data'])
def test_text_only_tab_label_is_centered_over_selected_indicator(dialog, key):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QStyle, QStyleOptionButton
    dialog._initial_content_sized = True
    dialog.resize(960, 680)
    dialog.show()
    item = dialog.tabs.items[key]
    QTest.mouseClick(item, Qt.MouseButton.LeftButton)
    QTest.qWait(600)
    option = QStyleOptionButton()
    item.initStyleOption(option)
    contents = item.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, option, item)
    text_center = item.x() + contents.center().x()
    indicator_center = dialog.tabs.slideAni.geometry.center().x()
    assert abs(text_center - indicator_center) <= 1


@pytest.mark.parametrize('aspect,dimensions,pixel_text', [
    ('16:9', (254., 451.56), '3000 × 5333 像素'),
    ('16:10', (254., 406.4), '3000 × 4800 像素'),
    ('3:2', (254., 381.), '3000 × 4500 像素'),
    ('A4', (210., 297.), '2480 × 3508 像素'),
])
def test_portrait_is_visible_and_clickable_for_every_aspect(dialog, aspect, dimensions, pixel_text):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    dialog._initial_content_sized = True
    dialog.resize(960, 680)
    dialog.show()
    QTest.qWait(30)
    assert dialog.orientation_control.isVisible()
    assert dialog.orientation_control.isEnabled()
    QTest.mouseClick(dialog.aspect_control._buttons[aspect], Qt.MouseButton.LeftButton)
    QTest.mouseClick(dialog.orientation_control._buttons['portrait'], Qt.MouseButton.LeftButton)
    assert dialog.options().orientation == 'portrait'
    assert (dialog.width_edit.value(), dialog.height_edit.value()) == dimensions
    assert dialog.pixel_label.text() == pixel_text
    assert dialog._current_request().options.orientation == 'portrait'
    QTest.mouseClick(dialog.orientation_control._buttons['landscape'], Qt.MouseButton.LeftButton)
    assert dialog.width_edit.value() > dialog.height_edit.value()
    assert dialog.width_edit.isEnabled() == (aspect != 'A4')


def test_oversize_output_shows_error_and_disables_export(dialog):
    dialog.width_edit.setValue(1000)
    dialog.ppi_control.setCurrentKey('600')
    assert not dialog.export_button.isEnabled()
    assert not dialog.error_label.isHidden()
    dialog.width_edit.setValue(254)
    assert dialog.export_button.isEnabled()


def test_preview_layout_error_blocks_export_until_settings_change(dialog):
    dialog._generation = 3
    dialog._failed(3, '当前画幅无法容纳所选字段')
    assert not dialog.export_button.isEnabled()
    assert dialog.error_label.text() == '当前画幅无法容纳所选字段'
    dialog._select_fields('default')
    assert dialog.export_button.isEnabled()


def test_brand_hex_editor_updates_visible_swatch_and_request(dialog):
    dialog.color_edits[0].setText('#1A2B3C')
    dialog.color_edits[0].textEdited.emit('#1A2B3C')
    assert dialog.options().brand_override[0] == '#1A2B3C'
    assert dialog.color_buttons[0].color.name() == '#1a2b3c'
    assert dialog._current_request().options.brand_override[0] == '#1A2B3C'
    dialog._reset_colors()
    assert dialog.options().brand_override is None


def test_field_picker_labels_do_not_claim_another_direction(dialog):
    dialog.direction_control.setCurrentKey('up')
    assert dialog.field_checks['地图里程'].text() == '地图里程'
    assert dialog.field_checks['单程时间'].text() == '核定时间'
    rows = [row for _, _, fields in dialog._current_request().information.sections for row in fields]
    assert next(row[1] for row in rows if row[0] == '地图里程') == '地图里程'


def test_closing_export_also_rejects_open_color_picker(dialog):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog
    fallback_used = []
    timer = QTimer()
    timer.setSingleShot(True)
    def fallback():
        fallback_used.append(True)
        for child in dialog.findChildren(QDialog):child.reject()
    timer.timeout.connect(fallback)
    timer.start(500)
    QTimer.singleShot(0, dialog.reject)
    dialog._choose_color(0)
    timer.stop()
    assert not fallback_used
    assert dialog._closed
    assert dialog.options().brand_override is None


def test_real_background_preview_coalesces_option_changes(dialog):
    import time
    from PySide6.QtWidgets import QApplication
    dialog._generation = None
    dialog.theme_control.setCurrentKey('night')
    dialog._select_fields('none')
    dialog.ppi_control.setCurrentKey('150')
    deadline = time.monotonic() + 5
    while dialog.preview.image.isNull() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(.01)
    assert not dialog.preview.image.isNull()
    assert dialog._controller.generation == 1
    assert dialog.options().theme == 'night' and dialog.options().selected_fields == ()
    assert not dialog.error_label.isVisible()


def test_dialog_exports_through_background_and_closes_on_success(dialog, tmp_path, monkeypatch):
    import time
    from PySide6.QtWidgets import QApplication
    from route_export_dialog import FluentFileDialog
    from PySide6.QtGui import QImage
    output = tmp_path / 'route.png'
    monkeypatch.setattr(FluentFileDialog, 'getSaveFileName', lambda *args: (str(output), ''))
    dialog.width_edit.setValue(25.4)
    dialog.ppi_control.setCurrentKey('80')
    results = []
    dialog.exported.connect(results.append)
    dialog._export()
    assert not dialog.export_button.isEnabled()
    deadline = time.monotonic() + 5
    while not results and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(.01)
    assert len(results) == 1 and dialog._closed
    image = QImage(str(output))
    assert image.width() == 80 and image.height() == 53


def test_single_route_entry_requires_real_selected_line(tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from map_page import MapPage
    from map_model import MapSnapshot, MapRoute, RouteDirection
    app = QApplication.instance() or QApplication([])
    page = MapPage(QSettings(str(tmp_path / 'entry.ini'), QSettings.Format.IniFormat))
    page.resize(960, 680)
    page.show()
    app.processEvents()
    page.set_session({'save_key': 'a', 'lines': [{'对象ID': 42, '线路名称': '1'}]})
    route = MapRoute(42, '1', 1, 'c', '公司', 'bus', (), (((0.,0.,0.),(100.,0.,0.)),), RouteDirection('one_way'))
    page.set_snapshot(MapSnapshot(routes=(route,)))
    page.set_preset('single')
    page.canvas.prepare_frame()
    assert not page.can_export()
    page.show_route(42, page.save_token)
    import time
    deadline = time.monotonic() + 3
    while not page.can_export() and time.monotonic() < deadline:
        app.processEvents()
        page.canvas.prepare_frame()
        time.sleep(.01)
    assert page.can_export()
    request = page.route_export_request()
    assert request.route_id == 42 and request.options.direction == 'up'
    from dataclasses import replace
    original = page.query.snapshot
    page.query.snapshot = replace(original, routes=(route, route))
    assert not page.can_export()
    page.query.snapshot = original
    dialog = page.open_route_export()
    assert dialog is not None
    before = page.presets.state('single')
    dialog._select_fields('none')
    assert page.presets.state('single') == before
    page.set_session({'save_key': 'b'})
    assert dialog._closed and page._route_export_dialog is None
    assert not page.can_export()
    page.close()
    app.processEvents()


def test_desktop_export_action_opens_single_route_settings(tmp_path, monkeypatch, dialog):
    import desktop_app
    import time
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QSettings
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *_: QSettings(str(tmp_path / 'desktop.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda _: None)
    window = desktop_app.MainWindow()
    try:
        window.resize(960, 680)
        window.show()
        window.navigate(1)
        page = window.map_page
        session = {'save_key': 'a', 'lines': [{'对象ID': 42, '线路名称': '1', '公司标识': 'c'}]}
        window.data = session
        page.set_session(session)
        page.set_snapshot(dialog._request.snapshot)
        page.show_route(42, page.save_token)
        deadline = time.monotonic() + 3
        while not page.can_export() and time.monotonic() < deadline:
            QApplication.processEvents()
            page.canvas.prepare_frame()
            time.sleep(.01)
        item = next(item for item in window._export_items() if item[0] == 'map-png')
        assert item[1] == '单线线路图' and item[3]
        window._export_action('map-png')
        opened = page._route_export_dialog
        assert opened is not None and opened.isVisible()
        assert opened._request.route_id == 42
        page.set_session({'save_key': 'b'})
        assert opened._closed and page._route_export_dialog is None
    finally:
        window.close()
        QApplication.processEvents()
