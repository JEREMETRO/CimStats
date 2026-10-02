"""Delayed layout callbacks must tolerate closed pages and deleted viewports."""
import os,sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'frontend')]
import pytest
from PySide6.QtCore import QAbstractAnimation,QEvent,QTimer,QVariantAnimation
from PySide6.QtWidgets import QApplication,QScrollArea,QWidget
from statistics_page import StatisticsPage


class ReflowProbe(StatisticsPage):
    def __init__(self):
        QWidget.__init__(self)
        self._closing=False;self.calls=[]
        for scroll_name,board_name in (('scroll','company_dashboard'),
                ('network_scroll','network_dashboard'),('city_scroll','city_dashboard')):
            setattr(self,scroll_name,QScrollArea(self))
            board=QWidget(self)
            board.reflow=lambda width,height:self.calls.append((width,height))
            setattr(self,board_name,board)
        self.query_timer=QTimer(self)
        self.token=self.network_model_token=0
        self.workers=[];self.network_workers=[]
        self._filter_animation=None;self._filter_animating=False

    def resizeEvent(self,event):
        QWidget.resizeEvent(self,event)


@pytest.fixture
def probe():
    application=QApplication.instance() or QApplication([])
    page=ReflowProbe()
    yield page
    page.stop_workers();page.deleteLater()
    application.sendPostedEvents(None,QEvent.Type.DeferredDelete)


@pytest.mark.parametrize('scroll_name,callback',[
    ('scroll','_reflow_company'),('network_scroll','_reflow_network'),('city_scroll','_reflow_city')])
def test_reflow_after_scroll_deletion_is_a_safe_noop(probe,scroll_name,callback):
    getattr(probe,scroll_name).deleteLater()
    QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    getattr(probe,callback)()
    assert probe.calls==[]


@pytest.mark.parametrize('callback',['_reflow_company','_reflow_network','_reflow_city'])
def test_closed_page_does_not_reflow(probe,callback):
    probe._closing=True
    getattr(probe,callback)()
    assert probe.calls==[]


@pytest.mark.parametrize('scroll_name,callback',[
    ('scroll','_reflow_company'),('network_scroll','_reflow_network'),('city_scroll','_reflow_city')])
def test_live_viewport_still_reflows(probe,scroll_name,callback):
    viewport=getattr(probe,scroll_name).viewport()
    getattr(probe,callback)()
    assert probe.calls==[(viewport.width(),viewport.height())]


def test_close_stops_filter_animation_before_waiting_for_workers(probe):
    animation=QVariantAnimation(probe)
    animation.setStartValue(0.);animation.setEndValue(1.);animation.setDuration(250)
    probe._filter_animation=animation;probe._filter_animating=True
    animation.start()
    assert animation.state()==QAbstractAnimation.State.Running
    probe.stop_workers()
    assert animation.state()==QAbstractAnimation.State.Stopped
    assert probe._filter_animation is None and not probe._filter_animating
