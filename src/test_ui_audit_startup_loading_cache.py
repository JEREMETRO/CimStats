"""Loading cache must avoid static redraws while reflecting live changes."""
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QAbstractAnimation, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect, QLabel, QPushButton
from PySide6.QtTest import QTest
from loading_overlay import _CoverFade, LoadingOverlay
from stats_tokens import PAGE_BG


class Background(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.paints = 0
        self.color = QColor('white')
        self.on_paint = None

    def paintEvent(self, event):
        self.paints += 1
        if self.on_paint is not None:
            self.on_paint()
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.color)


@pytest.fixture
def scene(qt_application, monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    window = QWidget()
    window.resize(600, 400)
    source = Background(window)
    source.setGeometry(0, 0, 600, 400)
    window.show()
    for _ in range(3):
        qt_application.processEvents()
    yield window, source
    window.close()
    window.deleteLater()


def test_static_loading_background_is_rendered_once(scene, qt_application):
    window, source = scene
    fade = _CoverFade(source)
    previous = source.grab()
    source.paints = 0
    fade.begin(previous)
    for _ in range(3):
        qt_application.processEvents()
    for time in (15, 35, 60, 90, 130, 170):
        fade.animation.setCurrentTime(time)
        for _ in range(3):
            qt_application.processEvents()
    assert source.paints <= 2
    fade.finish()


def test_loading_cache_reflects_live_source_change(scene, qt_application):
    window, source = scene
    fade = _CoverFade(source)
    previous = source.grab()
    fade.begin(previous)
    for _ in range(3):
        qt_application.processEvents()
    fade.animation.setCurrentTime(170)
    for _ in range(3):
        qt_application.processEvents()
    source.color = QColor('red')
    source.update()
    fade.animation.setCurrentTime(180)
    for _ in range(4):
        qt_application.processEvents()
    actual = qt_application.primaryScreen().grabWindow(int(window.winId())).toImage()
    if actual.isNull():
        pytest.skip('Platform does not support backing-store readback')
    assert actual.pixelColor(300, 200).green() < 180
    fade.finish()
    assert source.graphicsEffect() is None and fade._background_cache is None


def test_loading_cache_preserves_an_existing_effect(scene, qt_application):
    window, source = scene
    effect = QGraphicsOpacityEffect(source)
    effect.setOpacity(.8)
    source.setGraphicsEffect(effect)
    fade = _CoverFade(source)
    fade.begin(source.grab())
    assert fade._background_cache is None and source.graphicsEffect() is effect
    fade.finish()
    assert source.graphicsEffect() is effect


def test_child_enabled_change_requires_only_one_background_refresh(scene, qt_application):
    window, source = scene
    label = QLabel('实时内容', source)
    label.setGeometry(20, 20, 200, 40)
    label.show()
    fade = _CoverFade(source)
    fade.begin(source.grab())
    for _ in range(3):
        qt_application.processEvents()
    source.paints = 0
    label.setEnabled(False)
    for time in (80, 120):
        fade.animation.setCurrentTime(time)
        for _ in range(3):
            qt_application.processEvents()
    assert source.paints == 1
    fade.finish()


def test_opaque_loading_blend_keeps_live_button_target_and_callback(scene, qt_application):
    window, source = scene
    button = QPushButton('实时操作', source)
    button.setGeometry(20, 120, 180, 44)
    button.show()
    clicks = []
    button.clicked.connect(lambda: clicks.append(True))
    fade = _CoverFade(source)
    fade.begin(source.grab())
    for _ in range(3):
        qt_application.processEvents()
    fade.animation.setCurrentTime(80)
    target = qt_application.widgetAt(button.mapToGlobal(button.rect().center()))
    assert target is button
    QTest.mouseClick(target, Qt.MouseButton.LeftButton)
    assert clicks == [True]
    fade.finish()


def test_destination_paints_before_fade_clock_starts(scene, qt_application):
    window, source = scene
    fade = _CoverFade(source)
    previous = source.grab()
    states = []
    source.on_paint = lambda: states.append(
        fade.animation is not None and fade.animation.state() == QAbstractAnimation.State.Running)
    fade.begin(previous)
    for _ in range(3):
        qt_application.processEvents()
    assert states and states[0] is False
    assert fade.animation is not None and fade.animation.currentTime() == 0
    fade.finish()


def test_loading_finishes_preparing_destination_under_opaque_cover(scene, qt_application):
    window, source = scene
    calls = []
    overlay = None
    def prepare():
        calls.append(overlay.isVisible())
        source.color = QColor('red')
        source.update()
    overlay = LoadingOverlay(source, lambda: None, prepare_destination=prepare)
    overlay.begin('准备图表')
    overlay.finish()
    assert calls == [True] and overlay.transition.animation is not None
    for _ in range(3):
        qt_application.processEvents()
    overlay.transition.animation.setCurrentTime(180)
    for _ in range(3):
        qt_application.processEvents()
    frame = qt_application.primaryScreen().grabWindow(int(window.winId())).toImage()
    if frame.isNull():
        pytest.skip('Platform does not support backing-store readback')
    assert frame.pixelColor(5, 5).green() < 180
    overlay.transition.finish()


def test_progress_snapshot_does_not_render_the_covered_destination(scene):
    window, source = scene
    overlay = LoadingOverlay(source, lambda: None)
    overlay.begin('准备图表')
    states = []
    source.on_paint = lambda: states.append(overlay.isVisible())
    overlay.finish()
    assert not any(states)
    overlay.transition.finish()


def test_loading_snapshot_and_blend_keep_opaque_page_background(scene, qt_application):
    window, source = scene
    source.color = QColor(PAGE_BG)
    source.update()
    overlay = LoadingOverlay(source, lambda: None)
    overlay.begin('读取存档')
    for _ in range(3):
        qt_application.processEvents()
    overlay.transition.finish()
    snapshot = overlay.grab().toImage()
    assert snapshot.pixelColor(5, 5) == QColor(PAGE_BG)
    overlay.finish()
    for _ in range(3):
        qt_application.processEvents()
    overlay.transition.animation.setCurrentTime(80)
    for _ in range(3):
        qt_application.processEvents()
    frame = qt_application.primaryScreen().grabWindow(int(window.winId())).toImage()
    if frame.isNull():
        pytest.skip('Platform does not support backing-store readback')
    assert frame.pixelColor(5, 5) == QColor(PAGE_BG)
    overlay.transition.finish()


def test_deferred_destination_update_precedes_the_fade_clock(scene, qt_application):
    window, source = scene
    fade = _CoverFade(source)
    previous = source.grab()
    states = []
    source.on_paint = lambda: states.append(
        fade.animation is not None and fade.animation.state() == QAbstractAnimation.State.Running)
    fade.begin(previous)
    source.color = QColor('red')
    source.update()
    for _ in range(3):
        qt_application.processEvents()
    assert states and not any(states)
    fade.finish()


@pytest.mark.parametrize('end', ['resize', 'hide', 'destroy'])
def test_loading_cache_releases_on_source_lifecycle(scene, qt_application, end):
    window, source = scene
    fade = _CoverFade(source)
    fade.begin(source.grab())
    assert fade._background_cache is not None
    if end == 'resize':
        source.resize(500, 350)
    elif end == 'hide':
        source.hide()
    else:
        source.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    for _ in range(3):
        qt_application.processEvents()
    assert fade.animation is None and fade.snapshot is None
    assert fade._background_cache is None and not fade.isVisible()
