"""Adding the map must retain the main window's native chrome and handle."""
import time

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtOpenGLWidgets import QOpenGLWidget


def test_native_main_window_retains_handle_border_and_shadow_when_map_is_added(qt_application,tmp_path):
    if QApplication.platformName() != 'windows':
        pytest.skip('Requires native Windows window styles and DWM')
    import ctypes
    import win32con, win32gui
    from window_chrome import FluentMainWindow
    from window_workarea import fit_window_to_workarea
    from stats_style import initialize_theme
    initialize_theme(qt_application)
    window = FluentMainWindow()
    window.setWindowTitle('CimStats 原生边框验收')
    window.setCentralWidget(QLabel('Logo first frame',window))
    fit_window_to_workarea(window,requested_size=QSize(960,680))
    handle = int(window.winId())

    def pump():
        end = time.monotonic()+.25
        while time.monotonic()<end:
            qt_application.processEvents(); time.sleep(.002)

    def check():
        assert int(window.winId()) == handle,'Adding the map replaced the visible native window'
        style = win32gui.GetWindowLong(handle,win32con.GWL_STYLE)
        assert style&win32con.WS_CAPTION
        assert style&win32con.WS_THICKFRAME
        enabled = ctypes.c_int()
        result = ctypes.windll.dwmapi.DwmGetWindowAttribute(handle,1,ctypes.byref(enabled),4)
        assert result == 0 and enabled.value == 1,'DWM nonclient rendering was lost'

    try:
        window.show(); pump(); check()
        gl = QOpenGLWidget(window)
        window.setCentralWidget(gl)
        pump(); check()
        # Exercise native resizing without moving the user's system cursor.
        left,top,right,bottom = win32gui.GetWindowRect(handle)
        before = window.width()
        win32gui.SetWindowPos(handle,0,left,top,right-left+64,bottom-top,
                             win32con.SWP_NOZORDER|win32con.SWP_NOACTIVATE)
        pump(); check()
        assert window.width() > before
        qt_application.processEvents()
        window.grab().save(str(tmp_path/'main-window.png'))
        for action in (window.showMaximized,window.showNormal,window.showMinimized,window.showNormal):
            action(); pump(); check()
    finally:
        window.close(); qt_application.processEvents()
