"""Exercise the actual helper handshake, authentication and cleanup."""
import json
import socket
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from app_metadata import icon_svg_path
from startup_readiness import FirstFrameGate
from startup_transport import SplashProcess

ROOT = Path(__file__).resolve().parents[1]


def test_real_helper_paints_then_reaps_after_dismiss():
    owner = SplashProcess()
    try:
        owner.start(ROOT / 'CIM2_SaveStats.py', icon_svg_path())
        process = owner.process
        assert owner.wait_for_first_paint(timeout=8)
        assert owner.connected.is_set()
        assert any(event['event'] == 'splash_first_paint' for event in owner.events)
        owner.dismiss()
        owner.close()
        assert process.poll() == 0
        assert owner.process is None and owner.exit_code == 0
    finally:
        owner.close()


def test_failed_helper_exits_without_waiting_for_readiness(tmp_path):
    owner = SplashProcess()
    try:
        owner.start(ROOT / 'CIM2_SaveStats.py', tmp_path / 'missing.svg')
        process = owner.process
        assert not owner.wait_for_first_paint(timeout=8)
        owner.close()
        assert process.poll() == 1 and owner.exit_code == 1
    finally:
        owner.close()


def test_untrusted_peer_cannot_acknowledge_startup():
    owner = SplashProcess()
    owner.listen()
    try:
        with socket.create_connection(('127.0.0.1', owner.port)) as rogue:
            rogue.sendall(b'wrong-token\n' + json.dumps({'event': 'splash_first_paint'}).encode() + b'\n')
        assert not owner.first_paint.wait(.05)
        with socket.create_connection(('127.0.0.1', owner.port)) as trusted:
            trusted.sendall((owner.token + '\n').encode())
            trusted.sendall(json.dumps({'event': 'splash_first_paint', 'at': 1.}).encode() + b'\n')
            assert owner.first_paint.wait(2)
    finally:
        owner.close()


def test_main_frame_gate_fires_once_after_visible_paint(qt_application):
    window = QWidget()
    calls = []
    gate = FirstFrameGate(window, lambda: calls.append(window.isVisible()))
    window.show()
    qt_application.processEvents()
    qt_application.processEvents()
    assert calls == [True]
    window.update()
    qt_application.processEvents()
    assert calls == [True]
    window.close()


def test_opaque_startup_surface_can_acknowledge_frame_without_outer_paint(qt_application):
    from app_metadata import icon_svg_path
    from startup_surface import StartupSurface
    window = QWidget()
    surface = StartupSurface(icon_svg_path(), window)
    surface.setGeometry(window.rect())
    window.show()
    qt_application.processEvents()
    calls = []
    # Install after the initial paint: only a repaint of the opaque child is
    # requested, matching native Qt's omission of the covered outer Paint.
    gate = FirstFrameGate(window, lambda: calls.append(True), surface=surface)
    surface.update()
    qt_application.processEvents()
    qt_application.processEvents()
    assert calls == [True]
    window.close()


def test_bootstrap_begins_welcome_after_first_paint_and_reaps_helper(qt_application, tmp_path):
    from startup_bootstrap import main

    class WelcomeWindow(QWidget):
        def begin_welcome_transition(self):
            assert self.isVisible() and not self.property('startupHandoffPending')
            QTimer.singleShot(0, self.close)

    trace = tmp_path / 'trace.json'
    assert main(ROOT / 'CIM2_SaveStats.py', window_factory=WelcomeWindow, trace_path=trace) == 0
    events = json.loads(trace.read_text())
    names = [event['event'] for event in events]
    assert names.index('window_first_paint') < names.index('splash_dismissed') < names.index('welcome_transition_started')
    assert next(event['code'] for event in events if event['event'] == 'helper_reaped') == 0
    assert 'token' not in trace.read_text()
