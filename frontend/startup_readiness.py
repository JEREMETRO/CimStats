"""Close startup only after the complete visible top-level frame is dispatched."""
from PySide6.QtCore import QObject, QEvent, QTimer


class FirstFrameGate(QObject):
    def __init__(self, window, ready, *, surface=None):
        super().__init__(window)
        self.window = window
        self.ready = ready
        self._scheduled = False
        # Native Qt may omit an outer Paint when an opaque child covers it
        # completely. The startup surface itself then owns the complete frame.
        self._targets = [window] if surface is None else [window, surface]
        for target in self._targets:
            target.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Paint and not self._scheduled:
            self._scheduled = True
            QTimer.singleShot(0, self._finish)
        return False

    def _finish(self):
        if not self.window.isVisible():
            self._scheduled = False
            return
        for target in self._targets:
            target.removeEventFilter(self)
        self.ready()
