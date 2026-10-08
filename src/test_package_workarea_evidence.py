"""Diagnostic captures report actual logical workarea bounds, not requested sizes."""
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt


def test_smoke_workarea_resize_records_real_screen_and_actual_window(monkeypatch):
    from package_smoke import _resize_for_workarea, _window_workarea_evidence
    import window_workarea
    app = QApplication.instance() or QApplication([])
    window = QWidget(None, Qt.WindowType.FramelessWindowHint)
    # Offscreen has no native workarea; explicitly supply its virtual rectangle.
    monkeypatch.setattr(window_workarea, 'available_workarea', lambda *_: window.screen().availableGeometry())
    window.show()
    _resize_for_workarea(window, 3000, 2400)
    app.processEvents()
    evidence = _window_workarea_evidence(window)
    available = window.screen().availableGeometry()
    frame = window.frameGeometry()
    assert evidence['requested_size'] == [3000, 2400]
    assert evidence['actual_window_size'] == [window.width(), window.height()]
    assert evidence['available_geometry'] == [available.x(), available.y(), available.width(), available.height()]
    assert evidence['frame_geometry'] == [frame.x(), frame.y(), frame.width(), frame.height()]
    assert evidence['dpr'] == window.devicePixelRatioF()
    assert available.contains(frame)
    assert evidence['within_available_geometry'] is True
    window.close()
