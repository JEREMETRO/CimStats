"""Native tooltip surface regression, using synthetic text."""
import os
import sys
from pathlib import Path
import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QLabel, QToolTip
from stats_style import initialize_theme


def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('background', ['transparent', '#000000', '#FFFFFF'])
def test_native_tooltip_opaque_despite_transparent_source_style(background):
    application = app()
    initialize_theme(application)
    source = QLabel('source')
    source.setStyleSheet(f'color:#65758B;background:{background};')
    source.show()
    QToolTip.showText(QPoint(50, 50), '公共交通 52.32%', source)
    application.processEvents()
    tip = next(w for w in application.topLevelWidgets() if w.objectName() == 'qtooltip_label')
    pixel = tip.grab().toImage().pixelColor(10, 10)
    QToolTip.hideText()
    source.close()
    assert pixel.alpha() == 255 and pixel.lightness() > 240
