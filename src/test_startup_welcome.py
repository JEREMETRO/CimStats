"""Startup footprint, connected welcome motion and retry lifecycle regressions."""
import os
from pathlib import Path

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, QSettings, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch, tmp_path):
    import desktop_app
    monkeypatch.setattr(desktop_app, 'QSettings',
                        lambda *_args: QSettings(str(tmp_path / 'startup.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.QMessageBox, 'critical', lambda *_args: None)
    result = desktop_app.MainWindow()
    result.resize(960, 680)
    yield result
    result.close()
    app.processEvents()


def test_helper_covers_application_footprint_and_uses_centered_logo(app):
    from app_metadata import icon_svg_path
    from startup_splash import IconSplash
    splash = IconSplash(icon_svg_path())
    assert splash.width() >= 960 and splash.height() >= 680
    assert not splash.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert splash.logo_rect().center() == QPointF(splash.surface.rect().center())
    splash.close()


def test_import_cover_crossfades_without_blocking_destination(window, app, monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    window.show()
    app.processEvents()
    overlay = window.loading_overlay
    overlay.begin('准备读取存档')
    assert overlay.isVisible() and overlay.cancel_button.isEnabled()
    fade = overlay.transition
    assert fade.isVisible() and fade.animation is not None
    fade.animation.setCurrentTime(80)
    assert 0 < fade.opacity < 1
    assert fade.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    overlay.finish()
    assert not overlay.isVisible() and fade.isVisible()
    window._refresh_body()
    assert fade.isVisible()
    fade.animation.setCurrentTime(220)
    assert not fade.isVisible() and fade.snapshot is None
    overlay.begin('再次读取')
    window.centralWidget().resize(900, 600)
    assert fade.animation is None and fade.snapshot is None
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: False)
    overlay.begin('关闭动画')
    assert not fade.isVisible() and fade.animation is None
    overlay.finish()
    assert not fade.isVisible()


def test_welcome_covers_shell_and_reveals_open_without_blocking(window, app, monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    window.show()
    app.processEvents()
    welcome = window.empty_state
    assert welcome.geometry() == window.centralWidget().rect()
    assert welcome.isVisible()
    assert welcome.open_button.isEnabled()
    assert welcome.animation is not None
    center_y = welcome.height() / 2
    welcome.animation.setCurrentTime(welcome.animation.duration() // 2)
    assert welcome.logo_rect().center().y() < center_y
    assert 0 < welcome.reveal_progress < 1
    QTest.qWait(400)
    assert welcome.animation is None and welcome.reveal_progress == 1
    opened = []
    welcome.open_requested.connect(lambda: opened.append(True))
    monkeypatch.setattr('desktop_app.QFileDialog.getOpenFileName', lambda *_args: ('', ''))
    welcome.open_button.click()
    assert opened and welcome.isVisible()


def test_reduced_motion_and_resize_reach_stable_welcome(window, app, monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: False)
    window.show()
    app.processEvents()
    welcome = window.empty_state
    assert welcome.reveal_progress == 1 and welcome.animation is None
    window.resize(1200, 760)
    app.processEvents()
    assert welcome.geometry() == window.centralWidget().rect()
    assert welcome.logo_rect().center().y() < welcome.height() / 2
    button_rect = QRect(welcome.open_button.mapTo(welcome, QPoint()), welcome.open_button.size())
    assert welcome.rect().contains(button_rect)


@pytest.mark.parametrize('message', ['已取消解析', '读取失败'])
def test_failed_import_returns_to_retry_even_before_worker_finished(window, app, monkeypatch, message):
    from types import SimpleNamespace
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: False)
    window.show()
    app.processEvents()
    window.worker = SimpleNamespace(deleteLater=lambda: None, isRunning=lambda: False)
    window.loading_overlay.begin('读取存档')
    window.on_failed(message)
    assert window.empty_state.isVisible() and not window.loading_overlay.isVisible()
    assert window.empty_state.open_button.isEnabled()
    assert bool(window.empty_state.note.text()) == (message != '已取消解析')
    window.worker_finished()
    assert window.empty_state.isVisible()


def test_logo_cover_matches_initial_welcome_in_same_window(app, monkeypatch):
    from desktop_app import MainWindow
    monkeypatch.setattr(MainWindow, 'check_install', lambda self: None)
    window = MainWindow(defer_startup=True)
    window.resize(960, 680)
    window.setProperty('startupHandoffPending', True)
    window.show()
    app.processEvents()
    identity = int(window.winId())
    logo_rect = window._startup_surface.logo_rect()
    logo_frame = window._startup_surface.grab().toImage()
    window.initialize_content()
    app.processEvents()
    assert int(window.winId()) == identity
    welcome = window.empty_state
    assert welcome.reveal_progress == 0 and welcome.animation is None
    assert welcome.logo_rect() == logo_rect
    assert welcome.grab().toImage() == logo_frame
    window.close()


def test_legacy_helper_surface_matches_main_content_without_secondary_icon(window, app):
    from app_metadata import icon_svg_path
    from startup_splash import IconSplash
    window.setProperty('startupHandoffPending', True)
    window.show()
    app.processEvents()
    welcome = window.empty_state
    helper = IconSplash(icon_svg_path())
    helper.resize(window.size())
    helper.show()
    app.processEvents()
    assert welcome.reveal_progress == 0 and welcome.animation is None
    assert welcome.logo_rect() == helper.logo_rect()
    assert welcome.grab().toImage() == helper.surface.grab().toImage()
    helper.close()


def test_success_interrupts_transition_without_retaining_effect(window, app, monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    window.show()
    app.processEvents()
    welcome = window.empty_state
    assert welcome.animation is not None
    window.data = {'save_path': 'ready.save'}
    window._refresh_body()
    assert not welcome.isVisible() and welcome.animation is None
    assert welcome.content.graphicsEffect() is None
    window.data = {}
    window._refresh_body()
    assert welcome.isVisible() and welcome.reveal_progress == 1


def test_reduced_motion_environment_skips_welcome_motion(window, app, monkeypatch):
    monkeypatch.setenv('CIM2_REDUCED_MOTION', '1')
    window.show()
    app.processEvents()
    assert window.empty_state.reveal_progress == 1
    assert window.empty_state.content.graphicsEffect() is None


def test_parse_start_covers_shell_and_worker_cleanup_keeps_preparation_visible(window, app, monkeypatch, tmp_path):
    from PySide6.QtCore import QObject, Signal
    import desktop_app

    class ControlledWorker(QObject):
        progress = Signal(int, str)
        log = Signal(str)
        completed = Signal(dict)
        failed = Signal(str)
        finished = Signal()
        cancel_requested = False
        process = None

        def __init__(self, *_args):
            super().__init__()

        def start(self):
            pass

        def isRunning(self):
            return False

    monkeypatch.setattr(desktop_app, 'locate_managed', lambda *_: tmp_path)
    monkeypatch.setattr(desktop_app, 'ParseWorker', ControlledWorker)
    window.show()
    app.processEvents()
    window.start_parse(tmp_path / 'city.save')
    assert window.empty_state.isVisible() and window.loading_overlay.isVisible()
    assert window.loading_overlay.geometry() == window.centralWidget().rect()
    window.data = {'save_path': 'city.save'}
    window._awaiting_dashboards = True
    window.worker.finished.emit()
    assert window.worker is None and window.loading_overlay.isVisible()
    assert window.empty_state.isVisible()
    window._awaiting_dashboards = False
    window.loading_overlay.finish()
    window._refresh_body()
    assert not window.empty_state.isVisible()


def test_invalid_drop_does_not_leave_drag_highlight(window, app):
    window.show()
    app.processEvents()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile('invalid.txt')])
    drop = QDropEvent(QPointF(30, 30), Qt.DropAction.CopyAction, mime,
                      Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.empty_state.set_drag_active(True)
    window.dropEvent(drop)
    assert not drop.isAccepted() and not window.empty_state.drag_active
    assert window.empty_state.isVisible()


def test_welcome_tooltip_only_supplies_truncated_error_copy(window):
    welcome = window.empty_state
    welcome.set_note('读取失败')
    assert welcome.note.toolTip() == ''
    long_message = '读取失败：' + '很长的后端路径或异常消息' * 30
    welcome.set_note(long_message)
    assert welcome.note.text() != long_message
    assert welcome.note.toolTip() == long_message


def test_welcome_tab_stays_on_visible_controls(window, app, monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: False)
    window.show()
    window.activateWindow()
    app.processEvents()
    welcome = window.empty_state
    welcome.open_button.setFocus()
    for _ in range(12):
        QTest.keyClick(window, Qt.Key.Key_Tab)
        assert welcome.isAncestorOf(app.focusWidget()) or window.titleBar.isAncestorOf(app.focusWidget())


def test_dialog_and_drop_reach_parser_from_welcome(window, app, monkeypatch, tmp_path):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: False)
    target = tmp_path / '城市.save'
    called = []
    monkeypatch.setattr(window, 'start_parse', lambda path: called.append(path))
    monkeypatch.setattr('desktop_app.QFileDialog.getOpenFileName', lambda *_args: (str(target), ''))
    window.show()
    app.processEvents()
    window.empty_state.open_button.click()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(target))])
    drag = QDragEnterEvent(QPoint(30, 30), Qt.DropAction.CopyAction, mime,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.dragEnterEvent(drag)
    assert drag.isAccepted() and window.empty_state.drag_active
    drop = QDropEvent(QPointF(30, 30), Qt.DropAction.CopyAction, mime,
                      Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.dropEvent(drop)
    assert drop.isAccepted() and not window.empty_state.drag_active
    assert called == [target, target]


def test_loaded_ready_state_hides_welcome_but_pending_dashboard_keeps_it(window, app, monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: False)
    window.show()
    app.processEvents()
    window.data = {'save_path': 'loaded.save'}
    window._awaiting_dashboards = True
    window._refresh_body()
    assert window.empty_state.isVisible()
    window._awaiting_dashboards = False
    window._refresh_body()
    assert not window.empty_state.isVisible() and window.body.currentIndex() == 0
    assert window.sidebar.isEnabled() and window.content_host.isEnabled()
