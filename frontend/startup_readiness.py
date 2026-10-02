"""Close startup only after the complete visible top-level frame is dispatched."""
from PySide6.QtCore import QObject, QEvent, QTimer


class FirstFrameGate(QObject):
    def __init__(self, window, ready):
        super().__init__(window)
        self.window = window
        self.ready = ready
        self._scheduled = False
        window.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Paint and not self._scheduled:
            self._scheduled = True
            QTimer.singleShot(0, self._finish)
        return False

    def _finish(self):
        if not self.window.isVisible():
            self._scheduled = False
            return
        self.window.removeEventFilter(self)
        self.ready()
