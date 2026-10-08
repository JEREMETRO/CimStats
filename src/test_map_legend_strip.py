"""External legend strips must leave the current map viewport untouched."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import QRectF,QSize
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication
from map_canvas import MapCanvas
from map_model import MapRoad,MapSnapshot
from semantic_colors import metric_legend

@pytest.fixture
def canvas():
    app=QApplication.instance() or QApplication([])
    widget=MapCanvas();widget.resize(500,400)
    widget.set_snapshot(MapSnapshot(roads=(MapRoad(1,'road','road',(((0.,0.,0.),(100.,0.,100.)),)),),bounds=(0,0,100,100)))
    widget.show();app.processEvents();widget.prepare_frame()
    assert widget.can_export()
    yield widget
    widget.close()


def test_external_flag_is_internal_and_notifies_only_legend_changes(canvas):
    assert canvas.options['legend_external'] is False
    spy=QSignalSpy(canvas.legend_changed);before=(canvas.center,canvas.zoom)
    canvas.set_options(legend_external=True);assert spy.count()==1
    legend=metric_legend('interval','2013-05-23')
    canvas.set_options(legend_items=legend);assert spy.count()==2
    canvas.set_options(legend_items=legend,legend_external=True);assert spy.count()==2
    canvas.set_options(stop_names=False);assert spy.count()==2
    assert (canvas.center,canvas.zoom)==before
    canvas.set_options(legend_items=());assert spy.count()==3
    assert canvas.legend_strip_height()==0 and canvas.export_size()==canvas.size()


@pytest.mark.parametrize('metric',('interval','interval_peak','passengers'))
@pytest.mark.parametrize('width',(240,500))
def test_strip_is_measured_and_drawn_from_same_numeric_layout(canvas,metric,width):
    canvas.set_options(legend_items=metric_legend(metric,'2013-05-23','today'),legend_external=True)
    height=canvas.legend_strip_height(width)
    image=QImage(width,400+height,QImage.Format.Format_ARGB32);image.fill(QColor('#FF00FF'))
    painter=QPainter(image);rect=QRectF(0,400,width,height)
    layout=canvas._metric_legend_layout(painter,rect)
    canvas.paint_legend_strip(painter,rect);painter.end()
    assert layout['bounds'].bottom()+8==pytest.approx(rect.bottom())
    assert layout['bounds'].right()<=rect.right()-18
    assert image.pixelColor(1,399).name()=='#ff00ff'
    assert image.pixelColor(1,400).name()!='#ff00ff'
    painter=QPainter(image);assert canvas._legend_layout(painter)==[];painter.end()
    for first,second in zip(layout['labels'],layout['labels'][1:]):
        assert not first[0].intersects(second[0])


def test_generic_strip_keeps_the_original_two_row_limit_and_elision(canvas):
    items=tuple((f'Very long company identity {i}', '#123456') for i in range(20))
    canvas.set_options(legend_items=items,legend_external=True)
    width=240;height=canvas.legend_strip_height(width)
    image=QImage(width,height,QImage.Format.Format_ARGB32);painter=QPainter(image)
    labels=canvas._legend_layout(painter,QRectF(0,0,width,height))
    canvas.paint_legend_strip(painter,QRectF(0,0,width,height));painter.end()
    assert 1<=len(labels)<=2 and height<=58
    assert all('…' in label for _,label,_ in labels)
    assert all(rect.bottom()+8<=height and rect.right()<=width-18 for rect,_,_ in labels)


@pytest.mark.parametrize('metric',('interval','interval_peak','passengers'))
def test_external_export_appends_legend_without_repainting_over_any_map_pixel(canvas,tmp_path,metric):
    before=(canvas.center,canvas.zoom);canvas.set_options(legend_external=True,legend_items=())
    canvas.prepare_frame();baseline=tmp_path/'map-only.png';assert canvas.export_image(baseline)
    base=QImage(str(baseline));legend=metric_legend(metric,'2013-05-23','today')
    canvas.set_options(legend_items=legend);canvas.prepare_frame()
    height=canvas.legend_strip_height();assert canvas.export_size()==QSize(canvas.width(),canvas.height()+height)
    path=tmp_path/'map-and-strip.png';assert canvas.export_image(path)
    exported=QImage(str(path));assert exported.size()==canvas.export_size()
    assert exported.copy(0,0,canvas.width(),canvas.height())==base
    assert (canvas.center,canvas.zoom)==before
    painter=QPainter(exported);layout=canvas._metric_legend_layout(painter,QRectF(0,canvas.height(),canvas.width(),height));painter.end()
    bar=layout['bar']
    for position,value,label,colour in legend.ticks:
        pixel=exported.pixelColor(round(bar.left()+position*bar.width()),round(bar.center().y()))
        expected=QColor(colour)
        assert max(abs(a-b) for a,b in zip(pixel.getRgb()[:3],expected.getRgb()[:3]))<=4


def test_standalone_default_export_size_remains_the_plot_size(canvas,tmp_path):
    canvas.set_options(legend_items=metric_legend('interval','2013-05-23'));canvas.prepare_frame()
    assert canvas.legend_strip_height()>0 and canvas.export_size()==canvas.size()
    path=tmp_path/'standalone.png';assert canvas.export_image(path)
    assert QImage(str(path)).size()==canvas.size()
