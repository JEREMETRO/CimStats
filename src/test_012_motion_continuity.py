"""Continuous visible geometry across reveal interruption and re-entry."""
from PySide6.QtWidgets import QWidget
import pytest
from stats_motion import SurfaceMotion

@pytest.fixture
def surface(monkeypatch, qt_application):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    widget = QWidget()
    widget.resize(400, 190)
    widget.show()
    qt_application.processEvents()
    yield widget
    widget.close()


def test_012_motion_first_float_frame_never_moves_down(surface):
    motion = SurfaceMotion(surface)
    motion.reveal(True)
    initial = surface.graphicsEffect().offset
    motion.animation.setCurrentTime(16)
    next_offset = surface.graphicsEffect().offset
    assert initial > 0
    assert 0 <= next_offset <= initial


def test_012_motion_fade_interrupt_preserves_current_float_position(surface):
    motion = SurfaceMotion(surface)
    motion.reveal(True)
    motion.animation.setCurrentTime(50)
    previous = surface.graphicsEffect().offset
    opacity = surface.graphicsEffect().opacity()
    motion.reveal(False)
    assert surface.graphicsEffect().offset == previous
    assert surface.graphicsEffect().opacity() == opacity
    motion.animation.setCurrentTime(16)
    assert 0 < surface.graphicsEffect().offset < previous


def test_012_motion_float_finishes_without_position_jump(surface):
    motion = SurfaceMotion(surface)
    motion.reveal(True)
    offsets = [surface.graphicsEffect().offset]
    for t in (16, 32, 48, 80, 120, 180, 215):
        motion.animation.setCurrentTime(t)
        offsets.append(surface.graphicsEffect().offset)
    assert all(a >= b >= 0 for a, b in zip(offsets, offsets[1:]))
    assert len(set(offsets)) > 5
    motion.animation.setCurrentTime(250)
    assert surface.graphicsEffect() is None


def test_012_motion_drawn_card_first_frames_move_only_up(qt_application, monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    host = QWidget()
    host.resize(320, 180)
    host.setStyleSheet('background:#202020;')
    card = QWidget(host)
    card.setStyleSheet('background:white;')
    card.setGeometry(60, 40, 180, 100)
    host.show()
    qt_application.processEvents()
    motion = SurfaceMotion(card)
    motion.reveal(True)
    tops = []
    for t in (0, 16, 32, 48, 80, 120, 180, 220):
        if motion.animation is not None:
            motion.animation.setCurrentTime(t)
        im = host.grab().toImage()
        x = round(100 * im.devicePixelRatio())
        tops.append(next(y for y in range(im.height()) if im.pixelColor(x, y).red() > 100))
    assert tops[0] > tops[-1]
    assert tops == sorted(tops, reverse=True)
    host.close()


def test_012_motion_repeat_resize_and_policy_interrupt_reach_clean_final(surface, monkeypatch):
    motion = SurfaceMotion(surface)
    for index in range(10):
        motion.reveal(index % 2 == 0)
        motion.animation.setCurrentTime(16)
        offset, opacity = surface.graphicsEffect().offset, surface.graphicsEffect().opacity()
        surface.resize(400 + index * 5, 190 + index * 2)
        assert surface.graphicsEffect().offset == offset
        motion.reveal(True)
        assert surface.graphicsEffect().offset == offset
        assert surface.graphicsEffect().opacity() == opacity
    monkeypatch.undo()
    monkeypatch.setenv('CIM2_REDUCED_MOTION', '1')
    motion.reveal(True)
    assert surface.graphicsEffect() is None and motion.animation is None
    assert not motion.running

def test_012_motion_opening_summary_keeps_closed_first_frame_height(qt_application, monkeypatch):
    from PySide6.QtWidgets import QVBoxLayout
    from company_dashboard import CompanyGroup
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    host = QWidget()
    host.resize(960, 680)
    layout = QVBoxLayout(host)
    group = CompanyGroup('a', '测试公司', '#1677ff', charts=False)
    group.reflow(3, 1)
    layout.addWidget(group)
    layout.addStretch()
    host.show()
    qt_application.processEvents()
    expanded_height = group.summary_card.height()
    group.set_summary_collapsed(True)
    group.summary_motion.animation.setCurrentTime(166)
    qt_application.processEvents()
    group.summary_motion.animation.setCurrentTime(167)
    qt_application.processEvents()
    closed_height = group.summary_card.height()
    group.set_summary_collapsed(False)
    qt_application.processEvents()
    assert group.summary_card.height() == closed_height
    group.summary_motion.animation.setCurrentTime(50)
    qt_application.processEvents()
    assert closed_height < group.summary_card.height() < expanded_height
    host.close()

def test_012_motion_float_preserves_drawn_bottom_outside_source_rect(qt_application, monkeypatch):
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    host = QWidget()
    host.resize(320, 180)
    host.setStyleSheet('background:#202020;')
    card = QWidget(host)
    card.setStyleSheet('background:white;')
    card.setGeometry(60, 40, 180, 100)
    host.show()
    qt_application.processEvents()
    motion = SurfaceMotion(card)
    motion.reveal(True)
    motion.animation.setCurrentTime(16)
    im = host.grab().toImage()
    scale = im.devicePixelRatio()
    assert im.pixelColor(round(100 * scale), round(142 * scale)).red() > 100
    host.close()


@pytest.mark.parametrize('enabled', [False, True])
def test_012_motion_windows_policy_controls_surface(qt_application, monkeypatch, enabled):
    import ctypes
    import os
    if os.name != 'nt':
        pytest.skip('Windows client animation policy')
    def read_policy(action, size, output, flags):
        ctypes.cast(output, ctypes.POINTER(ctypes.c_int)).contents.value = int(enabled)
        return 1
    monkeypatch.delenv('CIM2_REDUCED_MOTION', raising=False)
    monkeypatch.setattr(ctypes.windll.user32, 'SystemParametersInfoW', read_policy)
    host = QWidget()
    host.show()
    motion = SurfaceMotion(host)
    motion.reveal(True)
    assert motion.running == enabled
    assert (host.graphicsEffect() is not None) == enabled
    host.close()


def test_012_motion_city_detail_returns_after_animation(qt_application, monkeypatch):
    from city_dashboard import CityDashboard
    from test_city_model import build, r
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    dashboard = CityDashboard()
    dashboard.resize(960, 680)
    dashboard.set_snapshot(build([r('trip-time', 'WhiteCollar', 0, 100, 2)]))
    dashboard.show()
    qt_application.processEvents()
    source = dashboard.panels['trip-time']
    clone = source._open_fullscreen()
    detail = source._fullscreen_dialog
    detail.animation.setCurrentTime(220)
    for button in clone.legend_buttons.values():
        if button.isChecked():
            button.click()
    hidden = set(clone._hidden_groups)
    detail.close()
    assert detail.isVisible() and detail.animation is not None
    detail.animation.setCurrentTime(80)
    assert detail.isVisible()
    detail.animation.setCurrentTime(167)
    assert not detail.isVisible() and detail.animation is None
    assert source._hidden_groups == hidden
    dashboard.close()
