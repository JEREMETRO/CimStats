"""Window placement uses logical work areas, never physical screen dimensions."""
import pytest
from PySide6.QtCore import QObject, QRect, QSize, Signal, Qt


@pytest.mark.parametrize('area',[
    QRect(0,40,1920,1040), QRect(0,0,1920,1040),
    QRect(60,0,1860,1080), QRect(0,0,1860,1080),
    QRect(-1600,-900,1600,860), QRect(1920,60,1200,740),
    QRect(-800,24,800,456),
])
def test_fit_respects_every_workarea_edge_and_negative_monitor_origins(area):
    from window_workarea import fitted_window_geometry
    fitted=fitted_window_geometry(QRect(-3000,-1500,2000,1400),area)
    assert area.contains(fitted)
    assert fitted.size()==QSize(min(2000,area.width()),min(1400,area.height()))


def test_fitting_preserves_a_valid_user_window_and_consumes_no_extra_taskbar_margin():
    from window_workarea import fitted_window_geometry
    area=QRect(-1280,40,1280,760);normal=QRect(-1000,90,960,680)
    assert fitted_window_geometry(normal,area)==normal
    assert fitted_window_geometry(QRect(-1280,40,1280,760),area)==area


@pytest.mark.parametrize('ratio',(1.,1.25,1.5,2.,2.5))
def test_geometry_is_already_logical_and_does_not_scale_the_workarea_twice(ratio):
    from window_workarea import fitted_window_geometry
    area=QRect(round(240/ratio),round(60/ratio),round(1920/ratio),round(1240/ratio))
    assert fitted_window_geometry(QRect(-1000,-1000,2400,1600),area)==area


def test_small_startup_workarea_wins_over_the_design_minimum(monkeypatch):
    import startup_surface
    monkeypatch.setattr(startup_surface,'available_workarea',lambda *_:QRect(-640,24,640,456))
    assert startup_surface.initial_window_size()==QSize(640,456)


class Screen(QObject):
    availableGeometryChanged=Signal(object)
    geometryChanged=Signal(object)
    logicalDotsPerInchChanged=Signal(float)

    def __init__(self,area):
        super().__init__();self.area=QRect(area)

    def availableGeometry(self):return QRect(self.area)


def test_workarea_changes_restore_reachability_without_resetting_valid_user_layout(qt_application,monkeypatch):
    import window_workarea
    from window_chrome import FluentWindow
    screen=Screen(QRect(0,0,1440,960))
    monkeypatch.setattr(window_workarea,'available_workarea',lambda *_:screen.availableGeometry())
    window=FluentWindow();monkeypatch.setattr(window,'screen',lambda:screen)
    window.resize(1000,700);window.move(80,90);window.show()
    for _ in range(3):qt_application.processEvents()
    original=QRect(window.geometry())
    screen.logicalDotsPerInchChanged.emit(144.)
    for _ in range(3):qt_application.processEvents()
    assert window.geometry()==original
    screen.area=QRect(40,20,800,520)
    screen.availableGeometryChanged.emit(screen.availableGeometry())
    for _ in range(3):qt_application.processEvents()
    assert screen.area.contains(window.geometry())
    window.showMinimized();screen.area=QRect(-900,50,760,440)
    screen.availableGeometryChanged.emit(screen.availableGeometry())
    window.showNormal()
    for _ in range(3):qt_application.processEvents()
    assert screen.area.contains(window.geometry())
    window.close()


def test_explicit_capture_size_is_constrained_and_returns_actual_geometry(qt_application,monkeypatch):
    import window_workarea
    from window_chrome import FluentWindow
    area=QRect(-800,30,800,550)
    monkeypatch.setattr(window_workarea,'available_workarea',lambda *_:area)
    window=FluentWindow();window.setMinimumSize(960,680)
    actual=window_workarea.fit_window_to_workarea(window,requested_size=QSize(1440,960))
    assert actual==window.geometry() and area.contains(actual)
    assert window.minimumWidth()<=area.width() and window.minimumHeight()<=area.height()
    window.close()


def test_monitor_change_rebinds_workarea_notifications(qt_application,monkeypatch):
    import window_workarea
    from window_chrome import FluentWindow
    first=Screen(QRect(0,0,1400,900));second=Screen(QRect(-1000,40,900,600))
    current=[first]
    monkeypatch.setattr(window_workarea,'available_workarea',lambda *_:current[0].availableGeometry())
    window=FluentWindow();monkeypatch.setattr(window,'screen',lambda:current[0])
    window.resize(1000,700);window.show()
    for _ in range(3):qt_application.processEvents()
    current[0]=second
    window.windowHandle().screenChanged.emit(qt_application.primaryScreen())
    for _ in range(3):qt_application.processEvents()
    assert second.area.contains(window.geometry())
    second.area=QRect(-1000,70,800,500)
    second.availableGeometryChanged.emit(second.availableGeometry())
    for _ in range(3):qt_application.processEvents()
    assert second.area.contains(window.geometry())
    normal=QRect(window.geometry())
    second.area=QRect(-1200,0,1200,900)
    second.availableGeometryChanged.emit(second.availableGeometry())
    for _ in range(3):qt_application.processEvents()
    assert window.geometry()==normal  # More space must not undo the user's layout.
    window.close()


@pytest.mark.parametrize('kind',('main','dialog','file'))
def test_main_and_secondary_windows_fit_a_workarea_smaller_than_their_declared_minimum(
        qt_application,monkeypatch,kind):
    import window_workarea
    from window_chrome import FluentDialog,FluentFileDialog
    area=QRect(20,30,720,450)
    monkeypatch.setattr(window_workarea,'available_workarea',lambda *_:area)
    if kind=='main':
        from desktop_app import MainWindow
        window=MainWindow(defer_startup=True)
    elif kind=='dialog':window=FluentDialog()
    else:window=FluentFileDialog(caption='保存文件')
    window.setMinimumSize(960,680);window.resize(1440,960)
    window.show()
    for _ in range(5):qt_application.processEvents()
    assert area.contains(window.geometry())
    window.hide();window.setGeometry(QRect(-1800,-900,1000,800));window.show()
    for _ in range(5):qt_application.processEvents()
    assert area.contains(window.geometry())
    window.close()


@pytest.mark.parametrize('state',(Qt.WindowState.WindowMaximized,Qt.WindowState.WindowFullScreen))
def test_capture_size_request_preserves_explicit_native_window_states(qt_application,state):
    from window_workarea import fit_window_to_workarea
    from window_chrome import FluentWindow
    window=FluentWindow();window.setWindowState(state)
    geometry=QRect(window.geometry())
    assert fit_window_to_workarea(window,requested_size=QSize(1440,960),
                                 area=QRect(0,0,800,550))==geometry
    assert window.windowState()==state
    window.close()
