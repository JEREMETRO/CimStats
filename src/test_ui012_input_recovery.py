"""Qt-delivered mixed-input and cover lifecycle checks; no physical-device claims."""
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtCore import QEvent, QPoint, QSettings, Qt
from PySide6.QtGui import QInputDevice, QTouchEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout
from stats_style import initialize_theme


def test_mixed_mouse_touch_drag_hold_cancel_and_activation_recovers(qt_application):
    app = qt_application
    initialize_theme(app)
    device = QTest.createTouchDevice(QInputDevice.DeviceType.TouchScreen)
    host = QWidget(); box = QVBoxLayout(host)
    button = QPushButton('action'); box.addWidget(button)
    button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    host.resize(260, 180); host.show(); app.processEvents()
    clicks, holds = [], []
    button.clicked.connect(lambda: clicks.append(True))
    button.customContextMenuRequested.connect(holds.append)
    events = QTest.touchEvent(host, device, False)
    point = button.mapTo(host, button.rect().center())
    def tap():
        events.press(0, point, host).commit()
        events.release(0, point, host).commit()
    try:
        for cycle in range(30):
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            tap()
        assert len(clicks) == 60
        for interrupted in ('cancel', 'hide', 'deactivate', 'multitouch', 'drag', 'hold'):
            before = len(clicks)
            events.press(0, point, host).commit()
            if interrupted == 'cancel':
                QApplication.sendEvent(button, QTouchEvent(QEvent.Type.TouchCancel, device))
            elif interrupted == 'hide':
                host.hide()
            elif interrupted == 'deactivate':
                QApplication.sendEvent(host, QEvent(QEvent.Type.WindowDeactivate))
            elif interrupted == 'multitouch':
                events.stationary(0).press(1, point + QPoint(20, 0), host).commit()
                events.release(1, point + QPoint(20, 0), host).stationary(0).commit()
            elif interrupted == 'drag':
                events.move(0, point + QPoint(50, 0), host).commit()
            else:
                from PySide6.QtCore import QEventLoop, QTimer
                loop = QEventLoop()
                QTimer.singleShot(QApplication.styleHints().mousePressAndHoldInterval() + 100, loop.quit)
                loop.exec()
                assert app._cimstats_touch_input._mode == 'held'
            events.release(0, point, host).commit()
            assert len(clicks) == before
            host.show(); app.processEvents()
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            tap()
            assert len(clicks) == before + 2
            assert not button.isDown()
            assert app._cimstats_touch_input._mode == 'idle'
            assert QWidget.mouseGrabber() is None
            assert QApplication.activeModalWidget() is None
        assert len(holds) == 1
    finally:
        host.close()


def test_loading_cover_cancel_reopen_and_fade_leave_mouse_and_touch_reachable(qt_application, monkeypatch, tmp_path):
    import desktop_app
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *_: QSettings(str(tmp_path / 'input.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    monkeypatch.setattr(desktop_app.QMessageBox, 'critical', lambda *_: None)
    window = desktop_app.MainWindow(); window.resize(960, 680); window.show()
    app = qt_application; app.processEvents(); QTest.qWait(400)
    device = QTest.createTouchDevice(QInputDevice.DeviceType.TouchScreen)
    opened = []
    monkeypatch.setattr(desktop_app.QFileDialog, 'getOpenFileName', lambda *_: (opened.append(True) or ('', '')))
    try:
        for cycle in range(5):
            overlay = window.loading_overlay
            overlay.begin('读取存档')
            app.processEvents()
            point = overlay.cancel_button.mapToGlobal(overlay.cancel_button.rect().center())
            assert QApplication.widgetAt(point) is overlay.cancel_button
            window.on_failed('已取消解析' if cycle % 2 == 0 else '测试读取失败')
            app.processEvents()
            button = window.empty_state.open_button
            assert QApplication.widgetAt(button.mapToGlobal(button.rect().center())) is button
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            events = QTest.touchEvent(window.centralWidget(), device, False)
            point = button.mapTo(window.centralWidget(), button.rect().center())
            events.press(0, point, window.centralWidget()).commit()
            events.release(0, point, window.centralWidget()).commit()
            assert len(opened) == 2 * (cycle + 1)
            assert QWidget.mouseGrabber() is None
            assert QApplication.activeModalWidget() is None
        QTest.qWait(300)
        assert not window.loading_overlay.transition.isVisible()
    finally:
        window.close()


def test_cancel_entry_rejects_completion_already_queued_to_ui(qt_application, monkeypatch, tmp_path):
    import threading
    import desktop_app
    from PySide6.QtCore import QThread, Signal
    queued = threading.Event()
    class QueuedParser(QThread):
        progress = Signal(int, str)
        log = Signal(str)
        completed = Signal(dict)
        failed = Signal(str)
        def __init__(self, path, managed, parent):
            super().__init__(parent)
            self.cancel_requested = False
            self.process = None
        def run(self):
            self.completed.emit({'stale_cancelled_result': True})
            queued.set()
        def cancel(self):
            self.cancel_requested = True
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *_: QSettings(str(tmp_path / 'cancel.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    monkeypatch.setattr(desktop_app, 'ParseWorker', QueuedParser)
    monkeypatch.setattr(desktop_app, 'locate_managed', lambda *_: tmp_path)
    window = desktop_app.MainWindow()
    received = []
    monkeypatch.setattr(window, 'on_completed', received.append)
    try:
        window.start_parse(tmp_path / 'queued.save')
        assert queued.wait(2)
        window.cancel_parse()
        qt_application.processEvents()
        assert received == [] and window.data == {}
        assert not window.loading_overlay.isVisible()
        window.open_dialog = lambda: None
    finally:
        window.close()


@pytest.mark.parametrize('cancel', [False, True])
def test_placeholder_read_delay_stays_off_ui_and_failure_can_reopen(qt_application, monkeypatch, tmp_path, cancel):
    """An injected cloud-provider delay is simulation, not a cloud-service run."""
    import threading
    import desktop_app
    from PySide6.QtCore import QEventLoop, QTimer, QThread
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *_: QSettings(str(tmp_path / 'placeholder.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    monkeypatch.setattr(desktop_app, 'locate_managed', lambda *_: tmp_path)
    monkeypatch.setattr(desktop_app.QMessageBox, 'critical', lambda *_: None)
    window = desktop_app.MainWindow()
    window.show()
    qt_application.processEvents()
    path = tmp_path / 'cloud.save'
    entered, release = threading.Event(), threading.Event()
    ui_thread = QThread.currentThread()
    original_exists = Path.exists
    def delayed_exists(candidate):
        if candidate == path:
            assert QThread.currentThread() is not ui_thread
            entered.set()
            release.wait(2)
            raise OSError('simulated provider read failure')
        return original_exists(candidate)
    monkeypatch.setattr(Path, 'exists', delayed_exists)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *_: (str(path), ''))
    try:
        window.open_dialog()
        assert entered.wait(2)
        if cancel:
            window.cancel_parse()
        ticks = []
        loop = QEventLoop()
        QTimer.singleShot(20, lambda: ticks.append(True))
        QTimer.singleShot(60, loop.quit)
        loop.exec()
        assert ticks and window.data == {}
        release.set()
        poll = QTimer(); poll.setInterval(10)
        poll.timeout.connect(lambda: loop.quit() if window.worker is None else None)
        poll.start(); QTimer.singleShot(3000, loop.quit); loop.exec(); poll.stop()
        assert window.worker is None and not window.data
        assert not window.loading_overlay.isVisible()
        assert window.status_text == ('已取消解析' if cancel else 'simulated provider read failure')
        reopened = []
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *_: (reopened.append(True) or ('', '')))
        window.open_dialog()
        assert reopened == [True]
    finally:
        release.set()
        window.close()
