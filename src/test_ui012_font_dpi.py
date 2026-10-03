"""Windows glyph raster regression: smooth CJK edges at unchanged UI sizes."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(os.name != 'nt', reason='Requires the Windows DirectWrite backend')
@pytest.mark.parametrize('dpr', ['1', '1.25', '1.5', '2'])
def test_ui012_font_dpi_small_cjk_edges_have_continuous_coverage(dpr):
    # Removing the shared hinting policy must reproduce aliased CJK edges.
    # Use Windows in an isolated process; the ordinary suite uses offscreen.
    script = r'''
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QFontMetricsF
from PySide6.QtCore import QPointF, Qt
from stats_style import initialize_theme
from stats_typography import emphasis_font, tooltip_font
from ui_kit import LegendChip
app = QApplication([])
initialize_theme(app)
label = QLabel('分群体客流')
label.setStyleSheet('font-size:12px;font-weight:400;')
label.ensurePolished()
chip = LegendChip('分群体客流', QColor('blue'))
fonts = [label.font(), chip.font(),
         emphasis_font(14, QFont.Weight.Normal), tooltip_font()]
for font in fonts:
    image = QImage(420, 100, QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(app.devicePixelRatio())
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setFont(font)
    painter.setPen(Qt.GlobalColor.black)
    painter.drawText(QPointF(8, 30), '分群体客流区域数量秋山市')
    painter.end()
    levels = {image.pixelColor(x, y).alpha()
              for y in range(image.height()) for x in range(image.width())}
    assert len(levels) >= 64, (font.toString(), len(levels), app.devicePixelRatio())
assert label.font().pixelSize() == 12
assert label.font().family() == 'Microsoft YaHei UI'
assert app.platformName() == 'windows'
'''
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, QT_QPA_PLATFORM='windows', QT_SCALE_FACTOR=dpr,
                       PYTHONPATH=os.pathsep.join([str(root / 'frontend'), str(root / 'src')]))
    result = subprocess.run([sys.executable, '-c', script], env=environment,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
