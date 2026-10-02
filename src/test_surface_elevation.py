"""Rendered hover and effect ownership regressions, not stylesheet snapshots."""
import os
import sys
import time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtCore import QEvent, QPoint, QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QGraphicsOpacityEffect


def app():
    return QApplication.instance() or QApplication([])


def enter(widget):
    local=QPointF(widget.rect().center())
    QApplication.sendEvent(widget,QEnterEvent(local,
        QPointF(widget.mapTo(widget.window(),local.toPoint())),
        QPointF(widget.mapToGlobal(local.toPoint()))))


def test_company_hover_changes_outer_pixels_without_moving_or_stealing_effect():
    from company_dashboard import KpiCard
    app()
    host = QWidget(); host.resize(400, 180)
    host.setStyleSheet('background: #F4F8FC;')
    card = KpiCard('公司资产', host); card.setGeometry(40, 35, 300, 100)
    opacity = QGraphicsOpacityEffect(card); opacity.setOpacity(.95)
    card.setGraphicsEffect(opacity)
    host.show(); QTest.qWait(60)
    QApplication.sendEvent(card, QEvent(QEvent.Type.Leave)); QTest.qWait(200)
    geometry = card.geometry(); before = host.grab().toImage()
    enter(card); QTest.qWait(220)
    after = host.grab().toImage()
    assert any(before.pixelColor(x, y) != after.pixelColor(x, y)
               for x in range(50, 330) for y in range(136, 142)), 'hover must render outside card'
    assert card.geometry() == geometry and card.graphicsEffect() is opacity
    QApplication.sendEvent(card, QEvent(QEvent.Type.Leave)); QTest.qWait(240)
    assert host.grab().toImage().pixelColor(150, 138) == before.pixelColor(150, 138)
    host.close()


def test_surface_motion_preserves_margins_and_foreign_effect():
    from stats_motion import SurfaceMotion
    app(); widget = QWidget(); layout = QVBoxLayout(widget)
    layout.setContentsMargins(11, 12, 13, 14)
    widget.resize(300, 100); widget.show()
    motion = SurfaceMotion(widget); motion.reveal(float_in=True); QTest.qWait(300)
    assert layout.contentsMargins().top() == 12
    opacity = QGraphicsOpacityEffect(widget); opacity.setOpacity(.8)
    widget.setGraphicsEffect(opacity)
    motion.reveal(); QTest.qWait(300)
    assert widget.graphicsEffect() is opacity and opacity.opacity() == .8
    widget.close()


def test_segmented_reduced_motion_is_immediate(monkeypatch):
    from stats_controls import FluentSegmentedControl
    app(); monkeypatch.setenv('CIM2_REDUCED_MOTION', '1')
    control = FluentSegmentedControl(); control.addItem('a', '默认'); control.addItem('b', '同期')
    control.setCurrentKey('b')
    assert control._animation is None
    assert all(button.graphicsEffect() is None for button in control._buttons.values())
    control.close()


def test_summary_surface_height_has_intermediate_frame_and_reverses(monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    from company_dashboard import CompanyGroup
    app(); host = QWidget(); host.resize(600, 400)
    group = CompanyGroup('1', '公司', '#1677FF', charts=False, parent=host)
    group.resize(560, 360);host.show();QTest.qWait(50)
    before = group.summary_card.height()
    started=time.monotonic()
    group.set_summary_collapsed(True);QTest.qWait(80)
    intermediate = group.summary_card.height()
    assert 40 < intermediate < before, dict(height=intermediate,before=before,
        elapsed_ms=round((time.monotonic()-started)*1000,1),
        animation_ms=group.summary_motion.animation.currentTime() if group.summary_motion.animation else 'finished',
        content_max=group.kpi_host.maximumHeight())
    group.set_summary_collapsed(False);QTest.qWait(320)
    assert not group.kpi_host.isHidden() and group.kpi_host.maximumHeight() == 16777215
    host.close()


def test_summary_reduced_motion_reaches_correct_state_immediately(monkeypatch):
    from company_dashboard import CompanyGroup
    app();monkeypatch.setattr('stats_motion.animations_enabled', lambda: False)
    host=QWidget();host.resize(600,400)
    group=CompanyGroup('1','公司','#1677FF',charts=False,parent=host)
    host.show()
    group.set_summary_collapsed(True)
    assert group.kpi_host.isHidden() and group.summary_motion.animation is None
    group.set_summary_collapsed(False)
    assert not group.kpi_host.isHidden() and group.summary_motion.animation is None
    host.close()


def test_summary_chevron_keeps_icon_and_reverses_from_current_angle(monkeypatch):
    from stats_controls import SummaryToggleButton
    app();monkeypatch.setattr('stats_motion.animations_enabled',lambda:True)
    button=SummaryToggleButton();button.show();QTest.qWait(20)
    original=button._icon
    button.set_collapsed(True);QTest.qWait(80)
    assert button._icon is original and 0 < button.chevron_angle < 180
    angle=button.chevron_angle
    button.set_collapsed(False)
    assert button.chevron_angle == angle
    QTest.qWait(300)
    assert button.chevron_angle == 180
    button.close()


def test_hover_shadow_is_clipped_to_scroll_viewport(monkeypatch):
    from PySide6.QtWidgets import QScrollArea, QFrame
    from stats_elevation import attach_card_elevation
    app();monkeypatch.setattr('stats_motion.animations_enabled',lambda:False)
    root=QWidget();root.resize(600,340);root.setStyleSheet('background:#F4F8FC;')
    scroll=QScrollArea(root);scroll.setGeometry(40,40,410,180)
    content=QWidget();content.resize(390,600);scroll.setWidget(content)
    card=QFrame(content);card.setGeometry(30,110,300,100)
    card.setStyleSheet('background:white;border:1px solid #DDE5ED;border-radius:8px;')
    attach_card_elevation(card);root.show();QTest.qWait(30)
    QApplication.sendEvent(card,QEvent(QEvent.Type.Leave));before=root.grab().toImage()
    enter(card);QTest.qWait(30)
    after=root.grab().toImage()
    assert all(before.pixelColor(x,y)==after.pixelColor(x,y)
               for x in range(70,380) for y in range(224,280)), 'shadow escaped viewport'
    assert any(before.pixelColor(x,y)!=after.pixelColor(x,y)
               for x in range(64,70) for y in range(166,205)), 'visible edge needs real shadow'
    root.close()


def test_shadow_carrier_is_destroyed_with_hovered_card(monkeypatch):
    from PySide6.QtWidgets import QFrame
    from stats_elevation import attach_card_elevation
    from shiboken6 import isValid
    app();monkeypatch.setattr('stats_motion.animations_enabled',lambda:True)
    root=QWidget();root.resize(400,180)
    card=QFrame(root);card.setGeometry(40,35,300,100)
    controller=attach_card_elevation(card);root.show();enter(card);QTest.qWait(20)
    carrier=controller.carrier
    card.deleteLater();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    root._fluent_elevation_layer.refresh()
    assert not isValid(card) and not isValid(carrier)
    root.deleteLater();QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)


def test_forced_collapse_finish_stops_old_animation_before_deferred_delete(monkeypatch):
    from company_dashboard import CompanyGroup
    from PySide6.QtCore import QAbstractAnimation
    app();monkeypatch.setattr('stats_motion.animations_enabled',lambda:True)
    root=QWidget();root.resize(600,400)
    group=CompanyGroup('1','公司','#1677FF',charts=False,parent=root)
    root.show();QTest.qWait(20)
    group.set_summary_collapsed(True);QTest.qWait(40)
    interrupted=group.summary_motion.animation
    assert interrupted.state()==QAbstractAnimation.State.Running
    group.summary_motion.finish()
    assert interrupted.state()==QAbstractAnimation.State.Stopped
    QTest.qWait(250)
    assert group.kpi_host.isHidden() and group.kpi_host.maximumHeight()==16777215
    root.close()
