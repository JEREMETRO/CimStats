"""Enlargement belongs to the existing window, with reversible geometry motion."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from test_chart_detail_surface import source


@pytest.fixture
def host(source, monkeypatch):
    import stats_motion
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: False)
    window = QMainWindow()
    central = QWidget(window)
    window.setCentralWidget(central)
    layout = QVBoxLayout(central)
    layout.addWidget(source)
    window.resize(960, 680)
    window.show()
    QApplication.instance().processEvents()
    yield window
    window.close()


def visible_windows():
    return [widget for widget in QApplication.topLevelWidgets() if widget.isVisible()]


def test_expand_uses_current_window_without_new_toplevel_or_resize(source, host):
    before = visible_windows()
    size = host.size()
    clone = source._open_fullscreen()
    view = source._fullscreen_dialog
    QApplication.instance().processEvents()
    assert not view.isWindow()
    assert view.parentWidget() is host.centralWidget()
    assert view.window() is host and clone.window() is host
    assert set(visible_windows()) == set(before)
    assert host.size() == size
    assert view.geometry() == host.centralWidget().rect()
    assert clone._detailed and clone.detail_summary.isVisible()
    assert source._open_fullscreen() is clone
    clone.fullscreen_button.click()
    assert not view.isVisible() and source.isVisible()
    assert host.size() == size
    assert source.fullscreen_button.hasFocus()


def test_expand_and_shrink_geometry_motion_is_interruptible(source, host, monkeypatch):
    import stats_motion
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: True)
    clone = source._open_fullscreen()
    view = source._fullscreen_dialog
    assert hasattr(view, 'animation') and view.animation is not None
    animation = view.animation
    start = animation.startValue()
    end = animation.endValue()
    assert start != end
    animation.setCurrentTime(animation.duration() // 2)
    assert view.geometry() != start and view.geometry() != end
    mid = view.geometry()
    clone.fullscreen_button.click()
    assert view.animation is not None and view.animation is not animation
    assert view.animation.startValue() == mid
    view.animation.setCurrentTime(view.animation.duration())
    assert not view.isVisible() and view.animation is None
    assert source.fullscreen_button.hasFocus()


def test_expanding_surface_is_opaque_without_second_show_transition(source, host, monkeypatch):
    import stats_motion
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: True)
    host.centralWidget().setStyleSheet('background: #ff0000;')
    clone = source._open_fullscreen()
    view = source._fullscreen_dialog
    view.animation.setCurrentTime(80)
    QApplication.instance().processEvents()
    assert not clone.surface_motion.running
    assert clone.graphicsEffect() is None
    frame = view.grab().toImage()
    assert frame.pixelColor(2, view.height() - 2).name() == '#ffffff'
    clone.fullscreen_button.click()
    view.animation.setCurrentTime(view.animation.duration())


def test_covered_card_shadows_do_not_draw_over_expanding_detail(source, host, monkeypatch):
    import stats_motion
    source._card_elevation.set_hovered(True)
    layer = host._fluent_elevation_layer
    assert layer.isVisible()
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: True)
    source._open_fullscreen()
    view = source._fullscreen_dialog
    layer.refresh()
    assert not layer.isVisible()
    view.animation.setCurrentTime(80)
    view.close()
    view.animation.setCurrentTime(view.animation.duration())
    assert layer.isVisible()


def test_other_chart_open_replaces_active_surface(source, host):
    other = source._create_clone(host.centralWidget())
    host.centralWidget().layout().addWidget(other)
    QApplication.instance().processEvents()
    source._open_fullscreen()
    old = source._fullscreen_dialog
    clone = other._open_fullscreen()
    assert not old.isVisible()
    assert other._fullscreen_dialog.isVisible()
    clone.fullscreen_button.click()


def test_compact_start_clips_detail_instead_of_overlapping_summary_and_chart(source, host, monkeypatch):
    import stats_motion
    source.setFixedHeight(190)
    QApplication.instance().processEvents()
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: True)
    clone = source._open_fullscreen()
    QApplication.instance().processEvents()
    assert clone.detail_summary.geometry().bottom() < clone.chart_host.geometry().top()
    source._fullscreen_dialog.cancel()


@pytest.mark.parametrize('motion', [False, True])
def test_multicompany_comparison_final_layout_fits_current_window(monkeypatch, motion):
    from PySide6.QtCore import QPoint, QRect
    from test_stats_charts import panel, result, bucket
    import stats_motion
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: motion)
    window = QMainWindow()
    central = QWidget(window)
    window.setCentralWidget(central)
    widget = panel('客流', modes=True, default_mode='trend-bar')
    QVBoxLayout(central).addWidget(widget)
    groups = ('BlueCollar', 'WhiteCollar', 'BusinessPeople', 'Pensioner', 'Student', 'Tourist')
    series = {(company, group): [bucket(1, 123.239), bucket(2, 111.112)]
              for company in ('a', 'b') for group in groups}
    original = result(series, metric='transport-by-group', comparison=series)
    widget.set_result(original, {'a': '公司甲', 'b': '公司乙'})
    window.resize(960, 680)
    window.show()
    QApplication.instance().processEvents()
    try:
        clone = widget._open_fullscreen()
        view = widget._fullscreen_dialog
        if motion:
            view.animation.setCurrentTime(view.animation.duration())
        QApplication.instance().processEvents()
        assert view.rect().contains(clone.geometry())
        for canvas in clone.chart_views:
            assert view.rect().contains(QRect(canvas.mapTo(view, QPoint()), canvas.size()))
        assert clone.chart_host.geometry().top() > clone.detail_summary.geometry().bottom()
        assert clone.result is original
        window.resize(800, 600)
        QApplication.instance().processEvents()
        assert view.rect().contains(clone.geometry())
        clone.fullscreen_button.click()
        if motion:
            view.animation.setCurrentTime(view.animation.duration() // 2)
            assert clone.chart_host.geometry().top() > clone.detail_summary.geometry().bottom()
            view.animation.setCurrentTime(view.animation.duration())
        assert not view.isVisible()
    finally:
        window.close()


def test_host_resize_escape_and_source_hide_clean_up_detail(source, host):
    clone = source._open_fullscreen()
    view = source._fullscreen_dialog
    host.resize(1200, 760)
    QApplication.instance().processEvents()
    assert view.geometry() == host.centralWidget().rect()
    QTest.keyClick(clone.fullscreen_button, Qt.Key.Key_Escape)
    assert not view.isVisible()
    source._open_fullscreen()
    view = source._fullscreen_dialog
    source.hide()
    assert not view.isVisible() and view.animation is None


def test_new_result_cancels_old_detail_without_adopting_stale_selection(source, host):
    clone = source._open_fullscreen()
    view = source._fullscreen_dialog
    clone._hidden_groups = {'stale-only'}
    source.clear()
    assert not view.isVisible()
    assert source._hidden_groups != {'stale-only'}


def test_host_close_during_expansion_stops_motion(source, host, monkeypatch):
    import stats_motion
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: True)
    source._open_fullscreen()
    view = source._fullscreen_dialog
    assert view.animation is not None
    view.animation.setCurrentTime(40)
    host.close()
    assert not view.isVisible() and view.animation is None


def test_inline_touch_shrink_runs_once_and_clears_global_touch_owner(source, host):
    from PySide6.QtGui import QInputDevice
    from PySide6.QtTest import QSignalSpy
    # The offscreen virtual screen is only 800px wide: keep the touch target
    # on-screen so Qt can deliver the real device sequence to this child.
    host.resize(640, 480)
    QApplication.instance().processEvents()
    clone = source._open_fullscreen()
    view = source._fullscreen_dialog
    spy = QSignalSpy(view.finished)
    QApplication.instance().processEvents()
    device = QTest.createTouchDevice(QInputDevice.DeviceType.TouchScreen)
    button = clone.fullscreen_button
    sequence = QTest.touchEvent(button, device, False)
    point = button.rect().center()
    sequence.press(0, point, button).commit()
    assert view.isVisible()
    sequence.release(0, point, button).commit()
    assert not view.isVisible() and spy.count() == 1
    assert QApplication.instance()._cimstats_touch_input._mode == 'idle'


@pytest.mark.parametrize('key', [Qt.Key.Key_Tab, Qt.Key.Key_Backtab])
def test_detail_tab_traversal_stays_on_expanded_surface(source, host, key):
    clone = source._open_fullscreen()
    view = source._fullscreen_dialog
    clone.fullscreen_button.setFocus()
    for _ in range(20):
        QTest.keyClick(QApplication.focusWidget(), key)
        assert view.isAncestorOf(QApplication.focusWidget())


def test_source_destroyed_during_expansion_removes_orphan_surface(monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    from shiboken6 import isValid
    from test_stats_charts import panel, result, bucket
    import stats_motion
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: True)
    window = QMainWindow()
    central = QWidget(window)
    window.setCentralWidget(central)
    widget = panel('客流')
    QVBoxLayout(central).addWidget(widget)
    widget.set_result(result({('a', 'bus'): [bucket(1, 10)]}), {'a': '甲'})
    window.show()
    QApplication.instance().processEvents()
    widget._open_fullscreen()
    view = widget._fullscreen_dialog
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.instance().processEvents()
    assert not isValid(view)
    window.close()


def test_source_scroll_position_survives_inline_return(monkeypatch):
    from test_stats_charts import panel, result, bucket
    from stats_controls import StatisticsScrollArea
    import stats_motion
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: False)
    window = QMainWindow()
    scroll = StatisticsScrollArea(window)
    body = QWidget()
    layout = QVBoxLayout(body)
    layout.addSpacing(550)
    widget = panel('客流')
    widget.set_result(result({('a', 'bus'): [bucket(1, 10)]}), {'a': '甲'})
    layout.addWidget(widget)
    layout.addSpacing(800)
    scroll.setWidget(body)
    scroll.setWidgetResizable(True)
    window.setCentralWidget(scroll)
    window.resize(960, 680)
    window.show()
    QApplication.instance().processEvents()
    scroll.verticalScrollBar().setValue(400)
    offset = scroll.verticalScrollBar().value()
    clone = widget._open_fullscreen()
    clone.fullscreen_button.click()
    QApplication.instance().processEvents()
    assert scroll.verticalScrollBar().value() == offset
    window.close()
