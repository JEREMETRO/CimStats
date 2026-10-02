"""A responsive icon-only window; imported only in the helper process."""
from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

_QT_IMPORT_STARTED = time.perf_counter()
from PySide6.QtCore import Qt, QRectF, QTimer, QObject, Signal
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget
_QT_IMPORT_FINISHED = time.perf_counter()


class IconSplash(QWidget):
    first_painted = Signal()

    def __init__(self, symbol: Path):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAccessibleName('启动图标')
        self.setFixedSize(144, 144)
        self.renderer = QSvgRenderer(str(symbol), self)
        if not self.renderer.isValid():
            raise ValueError('Startup icon is missing or invalid')
        self._painted = False
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.move(screen.availableGeometry().center() - self.rect().center())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.renderer.render(painter, QRectF(24, 24, 96, 96))
        painter.end()
        if not self._painted:
            self._painted = True
            QTimer.singleShot(0, self.first_painted.emit)


class _Control(QObject):
    closed = Signal()


def run_splash(port: int, token: str, symbol: Path) -> int:
    """No stdout/stdin assumptions; parent EOF closes the window on its Qt thread."""
    channel = None
    reader = None
    try:
        channel = socket.create_connection(('127.0.0.1', port), timeout=5)
        channel.sendall((token + '\n').encode('ascii'))
        channel.settimeout(None)
        app = QApplication([])
        window = IconSplash(symbol)
        control = _Control()
        control.closed.connect(app.quit, Qt.ConnectionType.QueuedConnection)

        def receive():
            try:
                while channel.recv(64):
                    # The parent sends close only. EOF is also terminal.
                    break
            except OSError:
                pass
            control.closed.emit()

        reader = threading.Thread(target=receive, daemon=True)
        reader.start()

        def painted():
            message = {'event': 'splash_first_paint', 'at': time.perf_counter(),
                       'qt_import_ms': (_QT_IMPORT_FINISHED - _QT_IMPORT_STARTED) * 1000}
            try:
                channel.sendall((json.dumps(message) + '\n').encode('utf-8'))
            except OSError:
                app.quit()

        window.first_painted.connect(painted)
        window.show()
        result = app.exec()
        window.close()
        return result
    except (OSError, ValueError):
        return 1
    finally:
        if channel is not None:
            try:
                channel.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            channel.close()
        if reader is not None:
            reader.join(timeout=.5)
