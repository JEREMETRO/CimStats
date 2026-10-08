"""Native colored SVG icons retain vector rendering and survive cyclic GC."""
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor
from qfluentwidgets import FluentIcon


def test_colored_icons_survive_cyclic_gc_in_a_separate_process():
    root = Path(__file__).resolve().parents[1]
    script = """
import gc
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon
from stats_icons import colored_icon
app = QApplication([])
for iteration in range(500):
    icon = colored_icon(FluentIcon.CALENDAR, '#1f71eb')
    holder = {'icon': icon, 'copy': QIcon(icon)}
    holder['self'] = holder
    del holder, icon
    if iteration % 10 == 0:
        gc.collect()
gc.collect()
print('icons collected')
"""
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen',
                       PYTHONPATH=str(root / 'frontend'))
    result = subprocess.run([sys.executable, '-X', 'dev', '-c', script],
                            cwd=root, env=environment, capture_output=True,
                            text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'icons collected' in result.stdout


@pytest.mark.parametrize('ratio', [1.0, 1.25, 1.5, 2.0])
def test_colored_icons_render_the_requested_color_at_each_dpi(qt_application, ratio):
    from stats_icons import colored_icon
    for glyph, requested in ((FluentIcon.CALENDAR, '#1f71eb'),
                             (FluentIcon.PEOPLE, '#a94367')):
        icon = colored_icon(glyph, QColor(requested))
        assert not icon.isNull()
        image = icon.pixmap(QSize(18, 18), ratio).toImage()
        assert image.devicePixelRatio() == ratio
        assert image.width() == int(18 * ratio + .5)
        painted = [image.pixelColor(x, y)
                   for y in range(image.height()) for x in range(image.width())
                   if image.pixelColor(x, y).alpha() >= 200]
        assert painted
        expected = QColor(requested)
        for pixel in painted:
            assert abs(pixel.red() - expected.red()) <= 1
            assert abs(pixel.green() - expected.green()) <= 1
            assert abs(pixel.blue() - expected.blue()) <= 1
