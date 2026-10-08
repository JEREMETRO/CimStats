import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor
from map_canvas import MapCanvas
from semantic_colors import METRIC_SCALES, metric_color, metric_legend


@pytest.mark.parametrize('metric', ['interval', 'interval_peak', 'passengers'])
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


@pytest.mark.parametrize('metric,want',[
    ('interval',('5','7.5','12.5','17.5','25','37.5','45')),
    ('interval_peak',('3','4','6.5','10','15','21.5','25')),
    ('passengers',('1','3','7.5','15','25','40','50')),
])
def test_numeric_ticks_use_the_actual_colour_anchor_and_display_unit(metric,want):
    legend=metric_legend(metric,'2013-05-23','today')
    assert legend.labels==want
    assert len(legend.ticks)==len(METRIC_SCALES[metric].anchors)
    stops=legend.gradient_stops
    for position,value,label,colour in legend.ticks:
        assert colour==metric_color(metric,value)
        assert label==f'{value/(1000 if metric=="passengers" else 1):g}'
        assert not any(mark in label for mark in ('–','<','≤','≥'))
        # Verify actual interpolation at the tick coordinate, including endpoint plateaus.
        for (low,first),(high,second) in zip(stops,stops[1:]):
            if low<=position<=high:
                factor=(position-low)/(high-low)
                expected='#'+''.join(f'{round(int(first[i:i+2],16)*(1-factor)+int(second[i:i+2],16)*factor):02X}' for i in (1,3,5))
                assert expected==colour
                break
        else:raise AssertionError('Tick lies outside the gradient')
    legacy=list(legend)
    assert legacy[-1]==('数据缺失',legend.missing_colour)
    assert all(not any(mark in label for mark in ('≤','≥','–')) for label,_ in legacy[:-1])


@pytest.mark.parametrize('metric',('interval','interval_peak','passengers'))
@pytest.mark.parametrize('ratio',(1.25,2.))
def test_rendered_tick_pixel_and_position_match_the_shared_colour_resolver(metric,ratio):
    app=QApplication.instance() or QApplication([])
    canvas=MapCanvas();canvas.resize(504,500)
    legend=metric_legend(metric,'2013-05-23','today');canvas.set_options(legend_items=legend)
    image=QImage(round(canvas.width()*ratio),round(canvas.height()*ratio),QImage.Format.Format_ARGB32)
    image.setDevicePixelRatio(ratio);image.fill(QColor('white'));painter=QPainter(image)
    layout=canvas._metric_legend_layout(painter);canvas._draw_legend(painter);painter.end()
    bar=layout['bar']
    assert len(layout['ticks'])==len(legend.ticks)
    for actual,(position,value,label,colour) in zip(layout['ticks'],legend.ticks):
        x,text=actual
        assert x==pytest.approx(bar.left()+position*bar.width()) and text==label
        painted=image.pixelColor(round(x*ratio),round(bar.center().y()*ratio))
        expected=QColor(colour)
        assert max(abs(a-b) for a,b in zip(painted.getRgb()[:3],expected.getRgb()[:3]))<=4
    for (first,_),(second,_) in zip(layout['labels'],layout['labels'][1:]):
        assert not first.intersects(second)
    canvas.close()
