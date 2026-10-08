"""Real elapsed-time regressions for surface reveals and content expansion."""
import os
import sys
import time
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
import pytest
from PySide6.QtCore import QEvent, QTimer
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from shiboken6 import isValid
from stats_motion import SurfaceMotion, CollapseMotion


@pytest.fixture
def enabled(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    return app


def test_chart_and_home_card_reveal_on_show(enabled):
    from stats_charts import ChartPanel
    from latest_info_charts import CategoryCard
    for card in (ChartPanel('图表'), CategoryCard('testCategory')):
        card.resize(400, 190)
        card.show()
        assert card.surface_motion.running
        effect = card.graphicsEffect()
        assert 0 < effect.opacity() < 1
        QTest.qWait(55)
        assert .78 < effect.opacity() < 1
        QTest.qWait(250)
        assert card.graphicsEffect() is None
        card.close()


@pytest.mark.parametrize('queued_work_ms', [0, 70])
def test_hidden_expansion_starts_at_zero_and_has_intermediate_height(enabled, queued_work_ms):
    host = QWidget(); layout = QVBoxLayout(host)
    content = QLabel('内容'); content.setMinimumHeight(0)
    layout.addWidget(content); host.resize(300, 180); host.show()
    QTest.qWait(30)
    motion = CollapseMotion(content, lambda: None)
    motion.set_collapsed(True); QTest.qWait(220)
    assert content.isHidden()
    motion.set_collapsed(False)
    assert content.maximumHeight() == 0
    animation = motion.animation
    frames = []
    animation.valueChanged.connect(lambda _value: frames.append(
        (animation.currentTime(), content.maximumHeight())))
    changed, finished = QSignalSpy(animation.valueChanged), QSignalSpy(animation.finished)
    if queued_work_ms:
        QTimer.singleShot(0, lambda: time.sleep(queued_work_ms / 1000))
    # Wall-clock waiting can expire before Qt delivers its first animation tick.
    # Inspect that real tick, including the height applied by the controller.
    assert changed.wait(1000)
    frame_time, frame_height = frames[0]
    assert 0 < frame_time < animation.duration()
    assert 0 < frame_height < content.sizeHint().height()
    if not finished.count():
        assert finished.wait(1000)
    assert content.isVisible() and content.maximumHeight() == 16777215
    host.close()


def test_hidden_surface_stops_immediately_and_destruction_is_safe(enabled):
    host = QWidget(); host.resize(300, 150); host.show()
    motion = SurfaceMotion(host); motion.reveal(True)
    QTest.qWait(30); host.hide()
    assert not motion.running and motion.animation is None and host.graphicsEffect() is None
    host.show(); motion.reveal(True)
    host.deleteLater(); QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QTest.qWait(260)
    assert not isValid(host)


def test_parent_and_child_reveals_share_one_composited_surface(enabled):
    root = QWidget(); layout = QVBoxLayout(root); child = QLabel('可见内容')
    layout.addWidget(child); root.resize(400, 200); root.show()
    outer, inner = SurfaceMotion(root), SurfaceMotion(child)
    inner.reveal(); assert inner.running
    outer.reveal(True)
    assert outer.running and not inner.running and child.graphicsEffect() is None
    inner.reveal()
    assert not inner.running and child.graphicsEffect() is None
    QTest.qWait(300)
    assert root.graphicsEffect() is None
    root.close()

def test_expand_after_reduced_motion_collapse_starts_closed(enabled, monkeypatch):
    host = QWidget(); layout = QVBoxLayout(host)
    content = QLabel('内容'); layout.addWidget(content)
    host.resize(300, 180); host.show(); QTest.qWait(30)
    motion = CollapseMotion(content, lambda: None)
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: False)
    motion.set_collapsed(True)
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    motion.set_collapsed(False)
    assert content.maximumHeight() == 0
    host.close()

def test_owned_detail_window_has_independent_reveal(enabled):
    from PySide6.QtWidgets import QDialog
    root = QWidget(); root.resize(400, 200); root.show()
    outer = SurfaceMotion(root); outer.reveal(True)
    dialog = QDialog(root); dialog.resize(300, 150); dialog.show()
    inner = SurfaceMotion(dialog); inner.reveal(True)
    assert inner.running and outer.running
    outer.reveal()
    assert inner.running
    dialog.close(); root.close()


def test_hiding_collapsing_parent_settles_height(enabled):
    host = QWidget(); layout = QVBoxLayout(host)
    content = QLabel('内容'); layout.addWidget(content)
    host.resize(300, 180); host.show(); QTest.qWait(30)
    motion = CollapseMotion(content, lambda: None)
    motion.set_collapsed(True); QTest.qWait(30)
    host.hide()
    assert motion.animation is None
    assert content.isHidden() and content.maximumHeight() == 16777215
    host.close()

@pytest.mark.parametrize('kind', ['line', 'bar', 'hbar', 'donut'])
def test_chart_pixels_change_without_data_geometry_or_export_change(enabled, tmp_path, kind):
    from PySide6.QtGui import QColor, QImage
    from chart_canvas import ChartCanvas, ChartData, Series
    from stats_exports import export_png
    host = QWidget(); host.setStyleSheet('background:white;'); host.resize(400, 190)
    layout = QVBoxLayout(host)
    canvas = ChartCanvas(); canvas.setMinimumHeight(0); layout.addWidget(canvas)
    data = ChartData(kind, ['甲', '乙'], [Series('s', '系列', QColor('#1677ff'), [13, 21])])
    canvas.set_data(data); host.show(); QTest.qWait(30)
    identity, geometry = id(canvas), canvas.geometry()
    reference = tmp_path / 'reference.png'; export_png(host, reference)
    motion = SurfaceMotion(host); motion.reveal(True)
    first = host.grab().toImage()
    effect = host.graphicsEffect(); opacity = effect.opacity()
    mid_export = tmp_path / 'mid.png'; export_png(host, mid_export)
    assert host.graphicsEffect() is effect and effect.opacity() == opacity
    assert QImage(str(reference)) == QImage(str(mid_export))
    QTest.qWait(50)
    middle = host.grab().toImage()
    assert .78 < effect.opacity() < 1
    QTest.qWait(260)
    final = host.grab().toImage()
    assert first != middle and middle != final
    assert canvas.data is data and id(canvas) == identity and canvas.geometry() == geometry
    assert canvas.graphicsEffect() is None and host.graphicsEffect() is None
    assert final.pixelColor(1, 1) == QColor('white')
    host.close()


def test_chart_reduced_motion_show_and_repeated_mode_changes(monkeypatch):
    from test_stats_charts import bucket, result
    from stats_charts import ChartPanel
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('CIM2_REDUCED_MOTION', '1')
    panel = ChartPanel('图表', modes=True)
    panel.set_result(result({('a', 'bus'): [bucket(1, 13), bucket(2, 21)]}), {'a': '公司'})
    panel.show()
    for mode in ['bar', 'line', 'pie', 'line']:
        panel.set_mode(mode)
        assert not panel.surface_motion.running and panel.graphicsEffect() is None
    panel.close()

def test_collapsing_content_clips_rows_without_overlapping_them(enabled):
    host = QWidget(); root = QVBoxLayout(host)
    content = QWidget(); rows = QVBoxLayout(content)
    labels = [QLabel('第一行'), QLabel('第二行')]
    for label in labels:
        label.setFixedHeight(70); rows.addWidget(label)
    root.addWidget(content); host.resize(400, 200); host.show(); QTest.qWait(30)
    motion = CollapseMotion(content, lambda: None)
    positions = [label.pos() for label in labels]
    motion.set_collapsed(True); QTest.qWait(115)
    assert [label.pos() for label in labels] == positions
    motion.set_collapsed(False); QTest.qWait(40)
    assert [label.pos() for label in labels] == positions
    QTest.qWait(300)
    assert rows.isEnabled()
    host.close()

def test_collapsing_page_can_be_deleted_mid_transition(enabled):
    host = QWidget(); root = QVBoxLayout(host)
    content = QWidget(); rows = QVBoxLayout(content)
    rows.addWidget(QLabel('内容')); root.addWidget(content)
    host.resize(400, 200); host.show(); QTest.qWait(20)
    motion = CollapseMotion(content, lambda: None)
    motion.set_collapsed(True); QTest.qWait(25)
    host.deleteLater(); QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QTest.qWait(300)
    assert not isValid(host) and not isValid(motion)


def test_foreign_child_effect_is_preserved_without_nesting(enabled):
    from PySide6.QtWidgets import QGraphicsOpacityEffect
    host = QWidget(); layout = QVBoxLayout(host); child = QLabel('内容')
    layout.addWidget(child); host.show()
    effect = QGraphicsOpacityEffect(child); child.setGraphicsEffect(effect); effect.setOpacity(.8)
    motion = SurfaceMotion(host); motion.reveal(True)
    assert host.graphicsEffect() is None and not motion.running
    assert child.graphicsEffect() is effect and effect.opacity() == .8
    host.close()

