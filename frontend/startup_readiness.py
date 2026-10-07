"""Release startup after its destination's complete visible Qt frame is drawn."""
from PySide6.QtCore import QObject, QEvent, QTimer
from shiboken6 import isValid


class FirstFrameGate(QObject):
    def __init__(self, window, ready, *, surface=None):
        super().__init__(window)
        self.window = window
        self.ready = ready
        self._scheduled = False
        self._finished = False
        self.surface = surface if surface is not None else window
        self._painted_size = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._finish)
        self._completed_signal = getattr(self.surface, 'frame_painted', None)
        if self._completed_signal is not None:
            self._completed_signal.connect(self._painted)
        else:
            self.surface.installEventFilter(self)

    def eventFilter(self, watched, event):
        if (watched is self.surface and event.type() == QEvent.Type.Paint
                and event.region().contains(self.surface.rect())):
            # A queued callback runs after QWidget has handled this event.
            self._painted()
        return False

    def _painted(self):
        if (self._finished or not isValid(self.surface) or not self.window.isVisible() or not self.surface.isVisible()
                or self.surface.rect().isEmpty() or self.surface.visibleRegion().isEmpty()):
            return
        # A newer complete frame can arrive before the queued acknowledgement,
        # particularly during resize. Confirm the latest size, not an old one
        # which would be rejected after the last repaint has already happened.
        self._painted_size = self.surface.size()
        if self._scheduled:
            return
        self._scheduled = True
        self._timer.start(0)

    def _finish(self):
        if self._finished:
            return
        if not isValid(self.surface):
            self.cancel()
            return
        if (not self.window.isVisible() or not self.surface.isVisible()
                or self.surface.visibleRegion().isEmpty()
                or self.surface.size() != self._painted_size):
            self._scheduled = False
            return
        self.cancel()
        self.ready()

    def cancel(self):
        if self._finished:
            return
        self._finished = True
        self._timer.stop()
        if isValid(self.surface):
            if self._completed_signal is not None:
                self._completed_signal.disconnect(self._painted)
            else:
                self.surface.removeEventFilter(self)
