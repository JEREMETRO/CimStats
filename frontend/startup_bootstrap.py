"""Show the helper before heavy imports; construct MainWindow on this Qt thread.

Python startup cannot cover a one-file bootloader's pre-interpreter extraction.
Trace timestamps describe painted Qt frames, not OS compositor presentation.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from app_metadata import (APP_NAME, TECHNICAL_APPLICATION_NAME, WINDOWS_APP_ID, application_version, bundle_root,
                          icon_png_paths, icon_svg_path)
from startup_transport import SplashProcess


def main(launcher: Path, *, root: Path | None = None, window_factory=None,
         trace_path: Path | None = None):
    root = root or bundle_root()
    events = []
    owner = SplashProcess()

    def record(name, **details):
        events.append({'event': name, 'at': time.perf_counter(), **details})

    record('bootstrap_enter')
    try:
        record('helper_spawn_started')
        try:
            owner.start(launcher, icon_svg_path(root))
            record('helper_spawn_finished', pid=owner.process.pid)
        except OSError as exc:
            record('splash_unavailable', reason=type(exc).__name__)
        record('parent_qt_import_started')
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QIcon
        from startup_readiness import FirstFrameGate
        record('parent_qt_import_finished')
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName(TECHNICAL_APPLICATION_NAME)
        app.setApplicationDisplayName(APP_NAME)
        app.setApplicationVersion(application_version(root))
        app.setQuitOnLastWindowClosed(False)
        record('parent_app_created')

        # No artificial minimum duration: start business imports as soon as the
        # helper acknowledges its first completed paint. Failure falls back.
        if owner.process is not None:
            if owner.wait_for_first_paint():
                record('splash_first_paint_received')
            else:
                record('splash_unavailable', reason='first_paint_timeout_or_exit')
                owner.close()
        record('desktop_import_started')
        from stats_style import initialize_theme
        initialize_theme(app)
        if window_factory is None:
            from desktop_app import MainWindow
            window_factory = MainWindow
        record('desktop_import_finished')
        icon = QIcon()
        for _size, path in icon_png_paths(root):
            if path.is_file():
                icon.addFile(str(path))
        app.setWindowIcon(icon)
        record('window_construct_started')
        window = window_factory()
        record('window_construct_finished')
        window.setWindowIcon(icon)

        def ready():
            record('window_first_paint')
            app.setQuitOnLastWindowClosed(True)
            owner.dismiss()
            record('splash_dismissed')

        gate = FirstFrameGate(window, ready)
        app.aboutToQuit.connect(owner.dismiss)
        record('window_show_requested')
        window.show()
        result = app.exec()
        record('application_exit', code=result)
        return result
    except BaseException as exc:
        record('startup_failed', reason=type(exc).__name__)
        raise
    finally:
        owner.close()
        record('helper_reaped', code=owner.exit_code)
        events.extend(owner.events)
        destination = trace_path or (Path(os.environ['CIM2_STARTUP_TRACE'])
                                     if os.environ.get('CIM2_STARTUP_TRACE') else None)
        if destination is not None:
            # Never include the token, command line, data, or settings in traces.
            try:
                destination.write_text(json.dumps(sorted(events, key=lambda event: event['at']),
                                                  indent=2), encoding='utf-8')
            except OSError:
                pass
