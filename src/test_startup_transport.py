"""Single-window startup and the retained diagnostic transport."""
import json
import socket
import pytest
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


def test_bootstrap_begins_welcome_after_first_paint_without_helper(qt_application, tmp_path, monkeypatch):
    from startup_bootstrap import main
    monkeypatch.setattr(SplashProcess, 'start', lambda *_args: pytest.fail('Normal startup must not create a helper'))

    class WelcomeWindow(QWidget):
        def begin_welcome_transition(self):
            assert self.isVisible() and not self.property('startupHandoffPending')
            QTimer.singleShot(0, self.close)

    trace = tmp_path / 'trace.json'
    assert main(ROOT / 'CIM2_SaveStats.py', window_factory=WelcomeWindow, trace_path=trace) == 0
    events = json.loads(trace.read_text())
    names = [event['event'] for event in events]
    assert names.index('logo_first_paint') <= names.index('window_first_paint') < names.index('welcome_transition_started')
    ids = {event['window_id'] for event in events if 'window_id' in event}
    assert len(ids) == 1
    assert not any(name.startswith('helper_') or name.startswith('splash_') for name in names)
    assert 'token' not in trace.read_text()


def test_cold_startup_paints_logo_before_business_imports_in_one_window(tmp_path):
    import os
    import subprocess
    import sys
    script = tmp_path / 'cold_startup.py'
    script.write_text('''
import json, sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from desktop_app import MainWindow
from startup_bootstrap import main
assert 'qfluentwidgets' not in sys.modules
assert 'openpyxl' not in sys.modules
assert 'statistics_page' not in sys.modules
ids = []
class Probe(MainWindow):
    def initialize_content(self):
        assert self.isVisible() and self._startup_surface.isVisible()
        assert 'qfluentwidgets' not in sys.modules
        assert 'openpyxl' not in sys.modules
        assert len([w for w in QApplication.topLevelWidgets() if w.isVisible()]) == 1
        ids.append(int(self.winId()))
        super().initialize_content()
        ids.append(int(self.winId()))
    def check_install(self):
        pass
    def begin_welcome_transition(self):
        ids.append(int(self.winId()))
        assert len(set(ids)) == 1
        assert self.empty_state.isVisible()
        assert self.empty_state.reveal_progress == 0
        super().begin_welcome_transition()
        QTimer.singleShot(0, self.close)
raise SystemExit(main(Path(sys.argv[1]), window_factory=Probe, trace_path=Path(sys.argv[2])))
''', encoding='utf-8')
    env = os.environ.copy()
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'frontend'), str(ROOT / 'src')))
    trace = tmp_path / 'trace.json'
    result = subprocess.run([sys.executable, str(script), str(ROOT / 'CIM2_SaveStats.py'), str(trace)],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    events = json.loads(trace.read_text())
    names = [event['event'] for event in events]
    assert names.index('logo_first_paint') < names.index('desktop_import_started')
    assert names.index('desktop_import_finished') < names.index('window_first_paint')
    assert len({e['window_id'] for e in events if 'window_id' in e}) == 1


def test_initialization_failure_exits_without_another_window(tmp_path):
    import os
    import subprocess
    import sys
    trace = tmp_path / 'failed.json'
    script = tmp_path / 'failed_startup.py'
    script.write_text('''
from pathlib import Path
import sys
from PySide6.QtWidgets import QWidget
from startup_bootstrap import main
class FailedWindow(QWidget):
    def initialize_content(self):
        raise RuntimeError('test startup failure')
assert main(Path(sys.argv[1]), window_factory=FailedWindow, trace_path=Path(sys.argv[2])) == 1
''', encoding='utf-8')
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'frontend'), str(ROOT / 'src')))
    env['QT_QPA_PLATFORM'] = 'offscreen'
    result = subprocess.run([sys.executable, str(script), str(ROOT / 'CIM2_SaveStats.py'), str(trace)],
                            env=env, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    events = json.loads(trace.read_text())
    assert any(e['event'] == 'startup_failed' and e['reason'] == 'RuntimeError' for e in events)
    assert not any(e['event'] == 'welcome_transition_started' for e in events)
