"""Paint one main-window logo cover before loading its business UI.

Python startup cannot cover a one-file bootloader's pre-interpreter extraction.
Trace timestamps describe painted Qt frames, not OS compositor presentation.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from app_metadata import (APP_NAME, TECHNICAL_APPLICATION_NAME, WINDOWS_APP_ID,
                          application_version, bundle_root, icon_png_paths)


def main(launcher: Path, *, root: Path | None = None, window_factory=None,
         trace_path: Path | None = None):
    root = root or bundle_root()
    events = []
    app = None
    prior_icon = None

    def record(name, **details):
        events.append({'event': name, 'at': time.perf_counter(), **details})

    record('bootstrap_enter')
    try:
        record('parent_qt_import_started')
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QIcon, QPixmap
        from PySide6.QtCore import Qt
        from startup_readiness import FirstFrameGate
        record('parent_qt_import_finished')
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName(TECHNICAL_APPLICATION_NAME)
        app.setApplicationDisplayName(APP_NAME)
        app.setApplicationVersion(application_version(root))
        app.setQuitOnLastWindowClosed(True)
        record('parent_app_created')
        if window_factory is None:
            from desktop_app import MainWindow
            window_factory = MainWindow
        icon = QIcon()
        for _size, path in icon_png_paths(root):
            if path.is_file():
                icon.addFile(str(path))
        # Only the main window owns the app icon; secondary windows do not
        # inherit it from QApplication, even before the full theme loads.
        prior_icon = app.windowIcon()
        empty = QPixmap(16, 16)
        empty.fill(Qt.GlobalColor.transparent)
        app.setWindowIcon(QIcon(empty))
        record('window_construct_started')
        app.setProperty('deferWindowStartup', True)
        try:
            window = window_factory()
        finally:
            app.setProperty('deferWindowStartup', False)
        record('window_construct_finished', window_id=int(window.winId()))
        window.setWindowIcon(icon)
        window.setProperty('startupHandoffPending', True)
        gates = []
        failure = []

        def ready():
            record('window_first_paint', window_id=int(window.winId()))
            window.setProperty('startupHandoffPending', False)
            begin_welcome = getattr(window, 'begin_welcome_transition', None)
            if begin_welcome is not None:
                begin_welcome()
                record('welcome_transition_started', window_id=int(window.winId()))

        def load_content():
            record('logo_first_paint', window_id=int(window.winId()))
            initialize = getattr(window, 'initialize_content', None)
            if initialize is None:
                ready()
                return
            def loaded():
                record('desktop_import_finished', window_id=int(window.winId()))
                gates.append(FirstFrameGate(window, ready, surface=getattr(window, 'empty_state', None)))
                window.update()

            def failed(exc):
                record('startup_failed', reason=type(exc).__name__)
                failure.append(exc)
                window.close()
                app.exit(1)

            try:
                record('desktop_import_started')
                asynchronous = getattr(window, 'initialize_content_async', None)
                if asynchronous is not None:
                    asynchronous(loaded, failed)
                else:
                    initialize()
                    loaded()
            except BaseException as exc:
                failed(exc)

        gates.append(FirstFrameGate(window, load_content, surface=getattr(window, '_startup_surface', None)))
        record('window_show_requested')
        window.show()
        result = app.exec()
        record('application_exit', code=result)
        return 1 if failure else result
    except BaseException as exc:
        record('startup_failed', reason=type(exc).__name__)
        raise
    finally:
        if app is not None and prior_icon is not None:
            app.setWindowIcon(prior_icon)
        destination = trace_path or (Path(os.environ['CIM2_STARTUP_TRACE'])
                                     if os.environ.get('CIM2_STARTUP_TRACE') else None)
        if destination is not None:
            try:
                destination.write_text(json.dumps(events, indent=2), encoding='utf-8')
            except OSError:
                pass
