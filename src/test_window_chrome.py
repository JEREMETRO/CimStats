"""Application title bars and secondary icon boundaries."""
from datetime import datetime
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_startup_welcome import app, window


def test_main_uses_custom_title_bar_without_version(window):
    from app_metadata import APP_NAME
    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert window.windowTitle() == APP_NAME
    window.show()
    QApplication.instance().processEvents()
    bar = window.titleBar
    assert bar.height() == 32 and bar.iconLabel.isVisible()
    assert window.centralWidget().geometry().top() >= bar.geometry().bottom()


def test_range_picker_uses_custom_dialog_title_bar(app):
    from stats_range_picker import RangePicker
    dialog = RangePicker(datetime(2024, 1, 1), datetime(2024, 1, 2))
    try:
        assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    finally:
        dialog.close()


def test_chinese_dialog_caption_uses_shared_ui_font(app):
    from stats_range_picker import RangePicker
    from stats_tokens import FONT_FAMILY
    dialog = RangePicker(datetime(2024, 1, 1), datetime(2024, 1, 2))
    dialog.show()
    app.processEvents()
    assert dialog.titleBar.titleLabel.font().family() == FONT_FAMILY
    dialog.close()


@pytest.mark.parametrize('family', ['helper', 'about', 'error', 'range'])
def test_secondary_windows_do_not_inherit_application_icon(app, window, family):
    from app_metadata import icon_svg_path
    from startup_splash import IconSplash
    from about_dialog import AboutDialog
    from stats_dialogs import _MessageSurface
    from stats_range_picker import RangePicker
    prior = app.windowIcon()
    app.setWindowIcon(QIcon(str(icon_svg_path())))
    constructors = {
        'helper': lambda: IconSplash(icon_svg_path()),
        'about': lambda: AboutDialog(window),
        'error': lambda: _MessageSurface('错误', '可恢复的诊断', window),
        'range': lambda: RangePicker(datetime(2024, 1, 1), datetime(2024, 1, 2), parent=window),
    }
    dialog = constructors[family]()
    try:
        image = dialog.windowIcon().pixmap(16, 16).toImage()
        assert not image.isNull()
        assert all(image.pixelColor(x, y).alpha() == 0
                   for x in range(image.width()) for y in range(image.height()))
    finally:
        dialog.close()
        app.setWindowIcon(prior)


def test_caption_keyboard_and_drag_region_preserve_window_controls(window):
    window.show()
    QApplication.processEvents()
    bar = window.titleBar
    assert bar.canDrag(bar.titleLabel.geometry().center())
    assert not bar.canDrag(bar.closeBtn.geometry().center())
    QTest.keyClick(bar.maxBtn, Qt.Key.Key_Return)
    assert window.isMaximized() and bar.maxBtn.accessibleName() == '还原窗口'
    QTest.keyClick(bar.maxBtn, Qt.Key.Key_Space)
    assert not window.isMaximized()
    QTest.mouseDClick(bar, Qt.MouseButton.LeftButton, pos=bar.titleLabel.geometry().center())
    assert window.isMaximized()
    window.showNormal()
    QTest.keyClick(bar.minBtn, Qt.Key.Key_Return)
    assert window.isMinimized()
    window.showNormal()


def test_file_picker_uses_custom_chrome_and_preserves_path_contract(app, tmp_path):
    from window_chrome import FluentFileDialog
    from PySide6.QtWidgets import QFileDialog
    directory = tmp_path / 'folder.with.dots'
    directory.mkdir()
    picker = FluentFileDialog(None, '保存文件', str(directory), '*.xlsx')
    try:
        assert picker.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert picker.testOption(QFileDialog.Option.DontUseNativeDialog)
        assert picker.directory().absolutePath() == str(directory).replace('\\', '/')
        assert picker.titleBar.titleLabel.accessibleName() == '保存文件'
    finally:
        picker.close()


def test_file_picker_cancel_has_static_api_result(app, monkeypatch):
    from window_chrome import FluentFileDialog
    from PySide6.QtWidgets import QDialog
    monkeypatch.setattr(FluentFileDialog, 'exec', lambda _self: QDialog.DialogCode.Rejected)
    assert FluentFileDialog.getOpenFileName() == ('', '')
    assert FluentFileDialog.getSaveFileName() == ('', '')
    assert FluentFileDialog.getExistingDirectory() == ''


def test_file_picker_retries_declined_overwrite_and_returns_selected_filter(app, monkeypatch, tmp_path):
    from window_chrome import FluentFileDialog
    from stats_dialogs import FluentMessageBox
    from PySide6.QtWidgets import QDialog
    target = tmp_path / 'existing.xlsx'
    target.write_bytes(b'original')
    monkeypatch.setattr(FluentFileDialog,'exec',lambda _self:QDialog.DialogCode.Accepted)
    monkeypatch.setattr(FluentFileDialog,'selectedFiles',lambda _self:[str(target)])
    monkeypatch.setattr(FluentFileDialog,'selectedNameFilter',lambda _self:'工作簿 (*.xlsx)')
    choices=iter((FluentMessageBox.StandardButton.No,FluentMessageBox.StandardButton.Yes))
    monkeypatch.setattr(FluentMessageBox,'warning',lambda *_args:next(choices))
    assert FluentFileDialog.getSaveFileName(filter='工作簿 (*.xlsx)') == (str(target),'工作簿 (*.xlsx)')
    assert target.read_bytes() == b'original'


def test_main_title_and_content_share_unbroken_surface(window):
    from stats_tokens import PAGE_BG
    window.show()
    QApplication.processEvents()
    image = window.grab().toImage()
    ratio = window.devicePixelRatioF()
    assert image.pixelColor(round(400 * ratio), round(12 * ratio)).name().lower() == PAGE_BG.lower()
    assert image.pixelColor(round(400 * ratio), round(40 * ratio)).name().lower() == PAGE_BG.lower()


def test_about_contains_text_identity_without_secondary_brand_symbol(window):
    from about_dialog import AboutDialog
    from PySide6.QtSvgWidgets import QSvgWidget
    dialog = AboutDialog(window)
    assert not dialog.findChildren(QSvgWidget)
    assert dialog.metadata.name and dialog.metadata.version
    dialog.close()


def test_range_dialog_fits_content_instead_of_frame_default(app):
    from stats_range_picker import RangePicker
    dialog = RangePicker(datetime(2024, 1, 1), datetime(2024, 1, 2))
    dialog.resize(dialog.width(),500)  # Native frameless base's constructor budget.
    dialog.show()
    app.processEvents()
    assert dialog.width() >= 520
    assert dialog.height() < 350
    assert dialog.apply_button.geometry().bottom() < dialog.height()
    dialog.time_toggle.setChecked(True)
    app.processEvents()
    assert dialog.height() < 350 and dialog.start_edit.isVisible()
    dialog.close()


def test_short_reminder_dialog_does_not_expand_into_large_empty_area(window):
    from frontend.latest_info_alerts import LatestInfoAlertsPanel
    from PySide6.QtWidgets import QLabel
    panel = LatestInfoAlertsPanel(window.settings,window)
    dialog, box = panel._dialog('提醒详情')
    box.addWidget(QLabel('提醒内容',dialog))
    dialog.resize(dialog.width(),500)
    dialog.show()
    QApplication.processEvents()
    assert dialog.height() < 260
    assert dialog.titleBar.titleLabel.accessibleName() == '提醒详情'
    dialog.close()
    panel.close()


def test_parented_about_mask_uses_parent_coordinates_after_window_move(window):
    from about_dialog import AboutDialog
    from PySide6.QtCore import QPoint, QRect
    window.move(80,80)
    window.show()
    QApplication.processEvents()
    dialog = AboutDialog(window)
    dialog.show()
    QApplication.processEvents()
    visible = QRect(window.mapToGlobal(QPoint()),window.size()).intersected(window.screen().availableGeometry())
    expected = visible.topLeft() if dialog.isWindow() else window.mapFromGlobal(visible.topLeft())
    assert dialog.geometry().topLeft() == expected
    dialog.close()
