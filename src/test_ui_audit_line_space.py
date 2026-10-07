"""Viewport-driven timetable regressions for UI-03 and A-01."""
import pytest
import time
from PySide6.QtCore import QPoint, QRect
from PySide6.QtTest import QTest
from line_schedule_view import SchedulePanel
from stats_style import initialize_theme


def entries(count):
    return [dict(time=f'{i // 60:02d}:{i % 60:02d}', vehicle_type='任意') for i in range(count)]


@pytest.fixture
def panel(qt_application):
    initialize_theme(qt_application)
    widget = SchedulePanel()
    widget.resize(1320, 560)
    widget.show()
    yield widget
    widget.close()
    widget.deleteLater()


@pytest.mark.parametrize('count', [0, 1, 29, 139, 140, 141, 144, 199, 200, 201])
def test_spacious_viewport_shows_all_times_without_count_threshold(panel, count):
    height = 700 if count >= 199 else 560
    panel.resize(1320, height)
    panel.set_line({'班次': {'周一': entries(count)}})
    QTest.qWait(30)
    assert panel.height() == height, 'entry count must not force parent growth'
    assert panel.matrix.display_count == count
    assert panel.matrix_scroll.verticalScrollBar().maximum() == 0
    assert panel.overflow_label.isHidden()
    if count:
        cell = panel.matrix.cell_rect(count - 1)
        viewport = panel.matrix_scroll.viewport()
        assert viewport.rect().contains(QRect(panel.matrix.mapTo(viewport, cell.topLeft()), cell.size()))
        # Full final time is actually painted, not only present in the model.
        image = panel.matrix.grab(cell).toImage()
        assert sum(image.pixelColor(x, y).name() == '#242b32'
                   for x in range(image.width()) for y in range(image.height())) > 3


def test_nearby_counts_keep_stride_and_scroll_continuous(panel):
    strides = []
    for count in (139, 140, 141, 144):
        panel.set_line({'班次': {'周一': entries(count)}})
        QTest.qWait(30)
        strides.append(panel.matrix.row_height)
    assert max(strides) - min(strides) <= 3
    assert strides[-1] > panel.matrix.minimum_row_height


@pytest.mark.parametrize('count', [29, 139, 140, 141, 144, 199, 200, 201, 1500])
def test_narrow_real_overflow_is_local_and_last_time_reachable(panel, count):
    panel.resize(400, 560)
    panel.set_line({'班次': {'周一': entries(count)}})
    QTest.qWait(40)
    assert panel.height() == 560
    assert panel.minimumHeight() < 560
    matrix, scroll = panel.matrix, panel.matrix_scroll
    assert matrix.columns < 10
    assert matrix.cell_rect(0).width() >= matrix.fontMetrics().horizontalAdvance('23:59') + 12
    assert matrix.row_height >= matrix.fontMetrics().height() + 4
    overflow = scroll.verticalScrollBar().maximum() > 0
    assert panel.overflow_label.isVisible() == overflow
    if overflow:
        assert '滚动' in panel.overflow_label.text()
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    QTest.qWait(30)
    assert count - 1 in matrix.visible_indices()
    assert scroll.horizontalScrollBar().maximum() == 0


def test_sparse_rows_are_more_spacious_and_overflow_clears_on_resize(panel):
    panel.set_line({'班次': {'周一': entries(29)}})
    QTest.qWait(30)
    sparse = panel.matrix.row_height
    panel.set_line({'班次': {'周一': entries(201)}})
    QTest.qWait(30)
    assert sparse > panel.matrix.row_height
    panel.resize(400, 560)
    QTest.qWait(30)
    assert panel.overflow_label.isVisible()
    panel.resize(1320, 700)
    # Nested QScrollArea range notifications and the coalesced hint update
    # settle naturally; fixed 30ms is not an animation/layout contract.
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        QTest.qWait(10)
        if panel.matrix_scroll.verticalScrollBar().maximum() == 0 and panel.overflow_label.isHidden():
            break
    assert panel.matrix.display_count == 201
    assert panel.matrix_scroll.verticalScrollBar().maximum() == 0
    assert panel.overflow_label.isHidden()
    panel.clear()
    QTest.qWait(30)
    assert panel.matrix.total_count == 0
    assert panel.matrix_scroll.verticalScrollBar().maximum() == 0


def test_overflow_hint_updates_after_expansion_and_shrink(panel):
    panel.resize(904, 400)
    panel.set_line({'班次': {'周一': entries(128)}})
    QTest.qWait(40)
    assert panel.overflow_label.isVisible()
    panel.set_expanded(True)
    panel.resize(904, 796)
    QTest.qWait(100)
    assert panel.matrix_scroll.verticalScrollBar().maximum() == 0
    assert panel.overflow_label.isHidden()
    panel.resize(400, 560)
    QTest.qWait(40)
    assert panel.overflow_label.isVisible()
