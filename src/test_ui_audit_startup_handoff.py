"""Only a completed, visible welcome frame may release the startup cover."""
from PySide6.QtCore import QCoreApplication, QEvent, QRect, QSettings, Qt
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QWidget
import pytest

from app_metadata import icon_svg_path
from startup_readiness import FirstFrameGate
from startup_surface import StartupSurface


def drain(app):
    for _ in range(3):
        app.processEvents()


def test_window_paint_cannot_release_a_specified_hidden_surface(qt_application):
    window = QWidget()
    window.resize(320, 240)
    surface = StartupSurface(icon_svg_path(), window)
    surface.hide()
    calls = []
    gate = FirstFrameGate(window, lambda: calls.append(True), surface=surface)
    window.show()
    drain(qt_application)
    assert calls == []
    surface.setGeometry(window.rect())
    surface.show()
    drain(qt_application)
    assert calls == [True]
    window.close()


def test_empty_paint_event_cannot_acknowledge_a_logo_frame(qt_application):
    window = QWidget()
    surface = StartupSurface(icon_svg_path(), window)
    surface.setGeometry(window.rect())
    window.show()
    drain(qt_application)
    calls = []
    gate = FirstFrameGate(window, lambda: calls.append(True), surface=surface)
    QCoreApplication.sendEvent(surface, QPaintEvent(QRect()))
    drain(qt_application)
    assert calls == []
    surface.update()
    drain(qt_application)
    assert calls == [True]
    window.close()


def test_undrawable_full_paint_cannot_acknowledge_a_logo_frame(qt_application):
    window = QWidget()
    surface = StartupSurface(icon_svg_path(), window)
    surface.setGeometry(window.rect())
    window.show()
    drain(qt_application)
    calls = []
    gate = FirstFrameGate(window, lambda: calls.append(True), surface=surface)
    # sendEvent delivers a Paint message without a QWidget paint engine. Its
    # rectangle looks complete but no actual pixels can have been produced.
    QCoreApplication.sendEvent(surface, QPaintEvent(surface.rect()))
    drain(qt_application)
    assert calls == []
    surface.update()
    drain(qt_application)
    assert calls == [True]
    window.close()


@pytest.mark.parametrize('invalidate', ['hide', 'resize'])
def test_pending_frame_is_rechecked_before_release(qt_application, invalidate):
    window = QWidget()
    window.resize(320, 240)
    surface = StartupSurface(icon_svg_path(), window)
    surface.setGeometry(window.rect())
    window.show()
    drain(qt_application)
    calls = []
    gate = FirstFrameGate(window, lambda: calls.append(True), surface=surface)
    # repaint is synchronous, the handoff callback is queued. Change the
    # destination before dispatching that callback to exercise the race.
    surface.repaint()
    if invalidate == 'hide':
        surface.hide()
    else:
        surface.resize(0, 0)
    drain(qt_application)
    assert calls == []
    surface.setGeometry(window.rect())
    surface.show()
    surface.update()
    drain(qt_application)
    assert calls == [True]
    window.close()


def test_destroying_window_cancels_pending_handoff(qt_application):
    from shiboken6 import isValid
    window = QWidget()
    surface = StartupSurface(icon_svg_path(), window)
    surface.setGeometry(window.rect())
    window.show()
    drain(qt_application)
    calls = []
    gate = FirstFrameGate(window, lambda: calls.append(True), surface=surface)
    surface.repaint()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    drain(qt_application)
    assert not isValid(gate) and calls == []


def test_new_complete_frame_supersedes_queued_old_size(qt_application):
    window = QWidget()
    window.resize(320, 240)
    surface = StartupSurface(icon_svg_path(), window)
    surface.setGeometry(window.rect())
    window.show()
    drain(qt_application)
    calls = []
    gate = FirstFrameGate(window, lambda: calls.append(True), surface=surface)
    surface.repaint()
    surface.resize(300, 200)
    surface.repaint()
    # The new-size frame has already been completed before the queued old
    # acknowledgement. It must supersede that old size, without another paint.
    gate._timer.stop()
    gate._finish()
    assert calls == [True]
    drain(qt_application)
    assert calls == [True]
    window.close()


@pytest.fixture
def deferred_window(qt_application, monkeypatch, tmp_path):
    import desktop_app
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *_: QSettings(
        str(tmp_path / 'startup.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    result = desktop_app.MainWindow(defer_startup=True)
    result.resize(960, 680)
    result.setProperty('startupHandoffPending', True)
    result.show()
    drain(qt_application)
    yield result
    result.close()


def test_cover_survives_construction_until_visible_welcome_paints(deferred_window, qt_application):
    window = deferred_window
    cover = window._startup_surface
    logo = cover.grab().toImage()
    identity = int(window.winId())
    window.initialize_content()
    assert window._startup_surface is cover and cover.isVisible()
    assert window.empty_state.reveal_progress == 0
    ready = []
    window.prepare_welcome_handoff(lambda: ready.append(True))
    assert window._startup_surface is cover
    drain(qt_application)
    assert ready == [True] and window._startup_surface is None
    assert window.empty_state.isVisible() and int(window.winId()) == identity
    assert window.empty_state.grab().toImage() == logo


def test_hidden_welcome_never_releases_cover(deferred_window, qt_application):
    window = deferred_window
    window.initialize_content()
    cover = window._startup_surface
    window.empty_state.hide()
    ready = []
    window.prepare_welcome_handoff(lambda: ready.append(True))
    window.update()
    drain(qt_application)
    assert ready == [] and window._startup_surface is cover
    window.empty_state.show()
    drain(qt_application)
    assert ready == [True] and window._startup_surface is None


def test_opaque_cover_must_not_starve_welcome_paint(deferred_window, qt_application):
    window = deferred_window
    window.initialize_content()
    cover = window._startup_surface
    cover.raise_()
    ready = []
    window.prepare_welcome_handoff(lambda: ready.append(True))
    drain(qt_application)
    assert window.empty_state.isVisible() and window.empty_state.visibleRegion().isEmpty()
    assert ready == [] and window._startup_surface is cover
    cover.stackUnder(window.empty_state)
    window.empty_state.update()
    drain(qt_application)
    assert ready == [True] and window._startup_surface is None


def test_welcome_animation_reuses_content_budget(deferred_window, qt_application, monkeypatch):
    window = deferred_window
    window.initialize_content()
    drain(qt_application)
    welcome = window.empty_state
    calls = []
    original = welcome.content.sizeHint
    monkeypatch.setattr(welcome.content, 'sizeHint', lambda: (calls.append(True), original())[1])
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    welcome.begin_transition()
    for time in (25, 80, 160, 250, 332):
        welcome.animation.setCurrentTime(time)
    assert len(calls) <= 1
    final_rect = welcome.content.geometry()
    welcome.finish_transition()
    assert abs(welcome.content.y() - final_rect.y()) <= 1
    assert welcome.content.graphicsEffect() is None


def test_resize_settles_active_welcome_and_keeps_open_reachable(deferred_window, qt_application, monkeypatch):
    window = deferred_window
    window.initialize_content()
    drain(qt_application)
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    welcome = window.empty_state
    welcome.begin_transition()
    welcome.animation.setCurrentTime(80)
    window.resize(1200, 760)
    drain(qt_application)
    assert welcome.animation is None and welcome.reveal_progress == 1
    assert welcome.content.graphicsEffect() is None
    assert welcome.open_button.isEnabled() and welcome.geometry() == window.centralWidget().rect()
