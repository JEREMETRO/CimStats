"""Welcome animation should repaint its moving composition, not the whole shell."""
import pytest
from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget
from startup_welcome import StartupWelcome


class PaintAreas(QObject):
    def __init__(self, target):
        super().__init__(target)
        self.areas = []
        target.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Paint:
            rect = event.region().boundingRect()
            self.areas.append(rect.width() * rect.height())
        return False


def drain(app):
    for _ in range(3):
        app.processEvents()


@pytest.fixture
def host(qt_application):
    widget = QWidget()
    yield widget
    widget.close()
    widget.deleteLater()


@pytest.mark.parametrize('size', [(960, 648), (1436, 868)])
def test_welcome_frames_only_dirty_the_moving_composition(qt_application, monkeypatch, size, host):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    host.resize(*size)
    welcome = StartupWelcome(host)
    welcome.show()
    host.show()
    drain(qt_application)
    recorder = PaintAreas(welcome)
    welcome.begin_transition()
    for time in (30, 80, 160, 250, 320):
        welcome.animation.setCurrentTime(time)
        drain(qt_application)
    assert recorder.areas
    # The logo and the prompt occupy far less than half the shell. Changing
    # opacity or moving those widgets must not invalidate every background pixel.
    assert max(recorder.areas) < size[0] * size[1] * .5
    assert 0 < welcome.reveal_progress < 1


def test_partial_welcome_backing_store_matches_fresh_render(qt_application, monkeypatch, host):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    host.resize(960, 648)
    welcome = StartupWelcome(host)
    welcome.show()
    host.show()
    drain(qt_application)
    welcome.begin_transition()
    for time in (30, 80, 160, 250, 320, 333):
        if welcome.animation is not None:
            welcome.animation.setCurrentTime(time)
        drain(qt_application)
        # Read the actual backing store before grab() can repaint a reference.
        frame = qt_application.primaryScreen().grabWindow(int(host.winId()))
        if frame.isNull():
            pytest.skip('Platform does not support backing-store readback')
        actual = frame.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        expected = welcome.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        assert actual == expected, f'Stale pixels after animation time {time}'
