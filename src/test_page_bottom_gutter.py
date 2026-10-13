import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def test_each_primary_page_keeps_one_shared_bottom_gutter(monkeypatch, tmp_path):
    from PySide6.QtCore import QPoint, QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    import desktop_app
    from app_shell import PAGE_GUTTER
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(desktop_app, 'QSettings',
        lambda *_: QSettings(str(tmp_path / 'window.ini'), QSettings.Format.IniFormat))
    monkeypatch.setattr(desktop_app.MainWindow, 'check_install', lambda self: None)
    window = desktop_app.MainWindow()
    try:
        window.show()
        for width, height in ((1440, 960), (960, 680), (1100, 720)):
            window.resize(width, height)
            for route in range(4):
                window.navigate(route)
                QTest.qWait(300)
                page = window.pages.currentWidget()
                bottom = page.mapTo(window.content_host, QPoint(0, page.height())).y()
                assert window.content_host.height() - bottom == PAGE_GUTTER
                assert page.width() > 0 and page.height() > 0
    finally:
        window.close()
