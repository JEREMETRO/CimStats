"""Windows native hit testing, separate from Qt-delivered mouse tests."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))


@pytest.mark.skipif(sys.platform != 'win32' or os.environ.get('QT_QPA_PLATFORM') != 'windows',
                    reason='requires the Windows Qt platform; run separately with QT_QPA_PLATFORM=windows')
@pytest.mark.parametrize('surface', ['layer', 'carrier', 'cover'])
def test_native_decoration_hit_test_passes_through(qt_application, surface):
    import ctypes
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
    from stats_elevation import attach_card_elevation

    host = QWidget()
    host.resize(500, 300)
    box = QVBoxLayout(host)
    card = QPushButton('reachable action')
    box.addWidget(card)
    host.show()
    qt_application.processEvents()
    controller = attach_card_elevation(card)
    controller.set_hovered(True)
    qt_application.processEvents()
    if surface == 'cover':
        from loading_overlay import _CoverFade
        decoration = _CoverFade(host)
        decoration.setGeometry(host.rect());decoration.show()
    else:
        decoration = controller.layer if surface == 'layer' else controller.carrier
    hwnd = int(decoration.winId())
    qt_application.processEvents()
    point = decoration.mapToGlobal(QPoint(20, 20))
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    try:
        hit = user32.SendMessageW(hwnd, 0x84, 0, ((point.y() & 0xffff) << 16) | (point.x() & 0xffff))
        assert hit == -1, 'native decoration must return HTTRANSPARENT'
    finally:
        host.close()
        host.deleteLater()
