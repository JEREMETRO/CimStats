"""Keep application windows in the screen's logical desktop work area."""
from PySide6.QtCore import QEvent, QObject, QRect, QSize, QTimer
from PySide6.QtGui import QGuiApplication


def available_workarea(window=None):
    # Offscreen rendering has a synthetic screen, not a desktop/taskbar budget.
    # Geometry tests supply explicit work areas instead of that virtual limit.
    if QGuiApplication.platformName()=='offscreen':
        return None
    screen=window.screen() if window is not None else QGuiApplication.primaryScreen()
    if screen is None:
        screen=QGuiApplication.primaryScreen()
    if screen is None:
        return None
    area=screen.availableGeometry()
    return QRect(area) if not area.isEmpty() else None


def fitted_window_geometry(requested,area):
    """Clamp size and position once; QScreen rectangles already use logical pixels."""
    result=QRect(requested)
    if area is None or area.isEmpty():
        return result
    result.setSize(QSize(min(max(1,result.width()),area.width()),
                         min(max(1,result.height()),area.height())))
    result.moveLeft(max(area.left(),min(result.left(),area.right()-result.width()+1)))
    result.moveTop(max(area.top(),min(result.top(),area.bottom()-result.height()+1)))
    return result


def set_workarea_minimum(window,minimum):
    area=available_workarea(window)
    size=QSize(minimum)
    if area is not None:
        size=size.boundedTo(area.size())
    window.setMinimumSize(size)


def fit_window_to_workarea(window,*,requested_size=None,area=None,center=False):
    """Request a capture/window size without forcing it beyond the real desktop."""
    if window.isMaximized() or window.isFullScreen():
        return QRect(window.geometry())
    if area is None:
        area=available_workarea(window)
    requested=QRect(window.geometry())
    if requested_size is not None:
        requested.setSize(QSize(requested_size))
    if area is not None:
        minimum=window.minimumSize().boundedTo(area.size())
        if minimum!=window.minimumSize():
            window.setMinimumSize(minimum)
        if center:
            requested.moveCenter(area.center())
    fitted=fitted_window_geometry(requested,area)
    if fitted!=window.geometry():
        window.setGeometry(fitted)
    return QRect(window.geometry())


class WindowWorkArea(QObject):
    """Recheck on desktop changes and restore; leave ordinary navigation alone."""
    def __init__(self,window):
        super().__init__(window)
        self.window=window
        self._screen=None
        self._handle=None
        self._applying=False
        self._timer=QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.fit)
        window.installEventFilter(self)

    def _bind_screen(self,*_):
        handle=self.window.windowHandle()
        if handle is not self._handle:
            if self._handle is not None:
                try:self._handle.screenChanged.disconnect(self._bind_screen)
                except RuntimeError:pass
            self._handle=handle
            if handle is not None:
                handle.screenChanged.connect(self._bind_screen)
        screen=self.window.screen()
        if screen is not self._screen:
            if self._screen is not None:
                for name in ('availableGeometryChanged','geometryChanged','logicalDotsPerInchChanged'):
                    try:getattr(self._screen,name).disconnect(self.schedule)
                    except RuntimeError:pass
            self._screen=screen
            if screen is not None:
                for name in ('availableGeometryChanged','geometryChanged','logicalDotsPerInchChanged'):
                    getattr(screen,name).connect(self.schedule)
        self.schedule()

    def schedule(self,*_):
        if not self._applying and not self._timer.isActive():
            self._timer.start(0)

    def fit(self):
        if self._applying or not self.window.isVisible() or self.window.isMinimized():
            return
        self._applying=True
        try:
            area=available_workarea(self.window)
            if area is None:
                return
            minimum=self.window.minimumSize().boundedTo(area.size())
            if minimum!=self.window.minimumSize():
                self.window.setMinimumSize(minimum)
            if not self.window.isMaximized() and not self.window.isFullScreen():
                fit_window_to_workarea(self.window,area=area)
        finally:
            self._applying=False

    def eventFilter(self,watched,event):
        if watched is self.window:
            if event.type()==QEvent.Type.Show:
                self._bind_screen()
            elif event.type() in (QEvent.Type.WindowStateChange,QEvent.Type.DevicePixelRatioChange):
                self.schedule()
            elif event.type()==QEvent.Type.Resize and not self._applying:
                self.schedule()
        return False
