"""Keep Qt windows and deferred deletions isolated between GUI tests."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid


@pytest.fixture(scope='session')
def qt_application():
    # Keep a Python owner alive for the whole session, including mixed subsets.
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def clean_qt_test_windows(qt_application):
    original = set(qt_application.topLevelWidgets())
    yield
    native = qt_application.platformName() == 'windows'
    if native:
        from PySide6.QtOpenGLWidgets import QOpenGLWidget
        from startup_bootstrap import _dispose_window
    for window in qt_application.topLevelWidgets():
        if isValid(window) and window not in original:
            if native and window.findChild(QOpenGLWidget) is not None:
                # Match application shutdown: release Python-owned GL objects
                # while their native widget/context is still alive.
                _dispose_window(window)
            else:
                window.close()
                window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_application.processEvents()
