"""Lightweight startup identity shared by helper and in-window welcome.

No Fluent controls or business imports: the helper can paint before desktop
imports, with exactly the same background and logo coordinates as the welcome.
"""
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget

import stats_tokens as tokens

DEFAULT_WINDOW_SIZE = QSize(1600, 1000)
MINIMUM_WINDOW_SIZE = QSize(960, 680)


def initial_window_size():
    screen = QApplication.primaryScreen()
    available = screen.availableGeometry().size() if screen else DEFAULT_WINDOW_SIZE
    return QSize(max(MINIMUM_WINDOW_SIZE.width(), min(DEFAULT_WINDOW_SIZE.width(), available.width())),
                 max(MINIMUM_WINDOW_SIZE.height(), min(DEFAULT_WINDOW_SIZE.height(), available.height())))


def center_startup_window(window):
    screen = QApplication.primaryScreen()
    if screen is not None:
        window.move(screen.availableGeometry().center() - window.rect().center())


class StartupSurface(QWidget):
    def __init__(self, symbol: Path, parent=None, flags=Qt.WindowType.Widget):
        super().__init__(parent, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.renderer = QSvgRenderer(str(symbol), self)
        if not self.renderer.isValid():
            raise ValueError('Startup icon is missing or invalid')
        self.logo_offset = 0.

    def logo_rect(self):
        center = QPointF(self.rect().center())
        return QRectF(center.x() - 48, center.y() - 48 - self.logo_offset, 96, 96)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(tokens.PAGE_BG))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.renderer.render(painter, self.logo_rect())
