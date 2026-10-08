import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor
from map_canvas import MapCanvas
from semantic_colors import metric_legend


@pytest.mark.parametrize('metric', ['interval', 'passengers'])
@pytest.mark.parametrize('ratio', [1., 1.25, 2.])
def test_complete_metric_legend_has_separate_scale_and_control_space(metric, ratio):
    app = QApplication.instance() or QApplication([])
    canvas = MapCanvas(); canvas.resize(500, 500)
    legend = metric_legend(metric, '2013-05-23', 'today')
    canvas.set_options(legend_items=legend)
    image = QImage(round(500*ratio), round(500*ratio), QImage.Format.Format_ARGB32)
    image.setDevicePixelRatio(ratio); image.fill(QColor('#FFFFFF'))
    painter = QPainter(image)
    layout = canvas._metric_legend_layout(painter)
    widths = [(label, rect.width(), painter.fontMetrics().horizontalAdvance(label))
              for rect, label in layout['labels']]
    canvas._draw_legend(painter); painter.end()
    assert layout['heading'] == legend.heading
    assert [label for _, label in layout['labels']] == list(legend.labels)
    assert layout['bounds'].bottom() < 450  # scale caption starts at height-50
    assert layout['bounds'].right() < 452  # native zoom buttons start width-48
    assert all(width >= text_width for _, width, text_width in widths), widths
    bar = layout['bar']
    left = image.pixelColor(round((bar.left()+2)*ratio), round(bar.center().y()*ratio))
    right = image.pixelColor(round((bar.right()-2)*ratio), round(bar.center().y()*ratio))
    assert left.name().upper() == legend.gradient_stops[0][1]
    assert right.name().upper() == legend.gradient_stops[-1][1]
    canvas.close()
