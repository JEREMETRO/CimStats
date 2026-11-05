"""A stopped fade must never strand an About dismissal or a reopened surface."""
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QDialog, QGraphicsOpacityEffect, QWidget
import pytest

from about_dialog import AboutDialog
from stats_style import initialize_theme


@pytest.fixture
def about(qt_application, monkeypatch):
    initialize_theme(qt_application)
    monkeypatch.setattr('about_dialog.animations_enabled', lambda: True)
    parent = QWidget()
    parent.resize(960, 680)
    parent.show()
    dialog = AboutDialog(parent)
    dialog.open()
    qt_application.processEvents()
    yield dialog
    dialog.hide()
    parent.close()


@pytest.mark.parametrize('replacement', [False, True], ids=['removed-effect', 'replaced-effect'])
def test_close_completes_when_its_fade_target_is_destroyed(about, replacement):
    finished = QSignalSpy(about.finished)
    QTest.mouseClick(about.yesButton, Qt.MouseButton.LeftButton)
    assert about.isVisible(), 'exercise the animated close before it completes'
    effect = QGraphicsOpacityEffect(about) if replacement else None
    about.setGraphicsEffect(effect)

    assert finished.wait(500), 'destroying the fade target must not strand dismissal'
    assert not about.isVisible()
    assert about.result() == QDialog.DialogCode.Accepted
    if replacement:
        assert about.graphicsEffect() is effect, 'cleanup must preserve a replacement effect'
    QTest.qWait(150)
    assert finished.count() == 1


@pytest.mark.parametrize('remove_effect', [False, True], ids=['running-fade', 'interrupted-fade'])
def test_interrupted_close_cannot_dismiss_a_reopened_about(about, remove_effect):
    finished = QSignalSpy(about.finished)
    QTest.mouseClick(about.yesButton, Qt.MouseButton.LeftButton)
    if remove_effect:
        about.setGraphicsEffect(None)
    about.hide()
    about.open()
    QTest.qWait(250)

    assert about.isVisible(), 'a previous close must not dismiss the new opening'
    assert finished.count() == 0
    QTest.keyClick(about, Qt.Key.Key_Escape)
    assert finished.wait(500)
    assert not about.isVisible()
    assert about.result() == QDialog.DialogCode.Rejected
    assert finished.count() == 1


def test_reduced_motion_close_remains_immediate(about, monkeypatch):
    monkeypatch.setattr('about_dialog.animations_enabled', lambda: False)
    finished = QSignalSpy(about.finished)
    QTest.mouseClick(about.yesButton, Qt.MouseButton.LeftButton)
    assert not about.isVisible()
    assert finished.count() == 1
