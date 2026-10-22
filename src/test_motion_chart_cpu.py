"""Redundant work regressions with live Qt layout, paint and pointer events."""
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
import pytest

from chart_canvas import AxisSpec, ChartCanvas, ChartData, Series


def move(canvas, point):
    event = QMouseEvent(QEvent.Type.MouseMove, point,
                       QPointF(canvas.mapToGlobal(point.toPoint())),
                       Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                       Qt.KeyboardModifier.NoModifier)
    return canvas.mouseMoveEvent(event)


class LiveCanvas(ChartCanvas):
    """The same drawing operations sent directly to the widget paint engine."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self._font)
        self._paint_body(painter)
        self._paint_current_tooltip(painter)


def test_filter_ticks_coalesce_and_leave_hidden_dashboard_layouts_dirty(qt_application, monkeypatch):
    from statistics_page import StatisticsPage
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: True)
    page = StatisticsPage()
    page.resize(960, 680)
    page.show()
    QTest.qWait(40)
    calls = {name: [] for name in ('company', 'network', 'city')}
    for name in calls:
        dashboard = getattr(page, name + '_dashboard')
        original = dashboard.reflow
        def record(width, height, *, key=name, reflow=original):
            # The dashboard also handles its own initial resize with height=0;
            # this regression measures StatisticsPage's viewport budget fits.
            if height > 0:
                calls[key].append((width, height))
            return reflow(width, height)
        monkeypatch.setattr(dashboard, 'reflow', record)
    page.set_filters_collapsed(True, animate=True)
    page._filter_animation.pause()
    for tick in (16, 32, 48, 64):
        page._filter_animation.setCurrentTime(tick)
    qt_application.processEvents()
    assert len(calls['company']) == 1
    assert calls['network'] == calls['city'] == []
    # A hidden page receives the final viewport budget synchronously on entry.
    page._filter_animation.setCurrentTime(167)
    qt_application.processEvents()
    page.tab_bar.setCurrentItem('network')
    qt_application.processEvents()
    assert calls['network'][-1] == (page.network_scroll.viewport().width(),
                                   page.network_scroll.viewport().height())
    assert calls['city'] == []
    page.stop_workers()
    page.close()


def test_unchanged_shadow_refresh_does_not_dirty_the_whole_window(qt_application, monkeypatch):
    from stats_elevation import attach_card_elevation
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: False)
    root = QWidget()
    root.resize(600, 400)
    card = QWidget(root)
    card.setGeometry(80, 60, 220, 120)
    controller = attach_card_elevation(card)
    root.show()
    controller.set_hovered(True)
    qt_application.processEvents()
    layer = controller.layer
    calls = []
    original = layer.update
    monkeypatch.setattr(layer, 'update', lambda *args: (calls.append(args), original(*args))[-1])
    layer._refresh_now()
    layer._refresh_now()
    assert calls == []
    card.move(120, 90)
    layer._refresh_now()
    assert calls and all(args for args in calls), 'damage must be a bounded old/new region'
    root.close()


def test_elevation_reparent_with_same_geometry_refreshes_new_carrier(qt_application, monkeypatch):
    from stats_elevation import attach_card_elevation
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: False)
    roots = [QWidget(), QWidget()]
    for root in roots:
        root.resize(600, 400)
        root.setStyleSheet('background:#f4f8fc')
        root.show()
    card = QWidget(roots[0])
    card.setGeometry(80, 60, 220, 120)
    card.show()
    controller = attach_card_elevation(card)
    controller.set_hovered(True)
    qt_application.processEvents()
    geometry = card.geometry()
    card.setParent(roots[1])
    card.setGeometry(geometry)
    card.show()
    controller.set_hovered(True)
    qt_application.processEvents()
    assert controller.carrier.isVisible()
    assert controller.carrier.geometry() == geometry
    for root in roots:
        root.close()


def test_large_chart_does_not_retain_an_unbounded_command_or_input_cache(qt_application):
    canvas = ChartCanvas()
    canvas.resize(400, 190)
    canvas.set_data(ChartData('line', [str(index) for index in range(5000)],
        [Series('a', 'Alpha', QColor('#1677ff'), [index % 20 for index in range(5000)])]))
    canvas.grab()
    assert canvas._body_commands is None and canvas._body_signature is None
    canvas.close()


@pytest.mark.parametrize('location', ['titles', 'nested_titles', 'series_notes'])
def test_oversized_metadata_bypasses_signature_without_traversing_it(qt_application, location):
    class UntraversableList(list):
        def __iter__(self):
            raise AssertionError('oversized metadata must be rejected from len before traversal')
    oversized = UntraversableList(['title'] * 100_000)
    data = ChartData('line', ['A', 'B'], [Series('a', 'Alpha', QColor('#1677ff'), [10, 20])])
    if location == 'titles':
        data.titles = oversized
    elif location == 'nested_titles':
        data.titles = [oversized]
    else:
        data.series[0].notes = [oversized]
    canvas = ChartCanvas()
    canvas.resize(400, 190)
    canvas.set_data(data)
    assert canvas._body_key() is None
    canvas.grab()
    assert canvas._body_commands is None and canvas._body_signature is None
    canvas.close()


@pytest.mark.parametrize('helper,kind', [('_unit_caption', 'line'), ('_metrics', 'line'),
    ('_resolve_axis', 'line'), ('_stack_layout', 'bar')])
def test_static_layout_helper_override_invalidates_retained_pixels(qt_application, monkeypatch, helper, kind):
    from PySide6.QtGui import QFont, QFontMetricsF
    data = ChartData(kind, ['A', 'B'], [Series('a', 'Alpha', QColor('#1677ff'), [10, 20])], unit='people')
    widgets = [ChartCanvas(), LiveCanvas()]
    for canvas in widgets:
        canvas.resize(480, 260)
        canvas.set_data(data)
        canvas.show()
    qt_application.processEvents()
    before = widgets[0].grab().toImage()
    for canvas in widgets:
        original = getattr(canvas, helper)
        if helper == '_unit_caption':
            replacement = lambda: 'A new caption'
        elif helper == '_metrics':
            font = QFont(canvas._font)
            font.setPixelSize(19)
            replacement = lambda *args, font=font: QFontMetricsF(font)
        elif helper == '_resolve_axis':
            replacement = lambda *args: AxisSpec(0, 100, 20)
        else:
            def replacement(original=original):
                stacks, width, gap, total = original()
                return stacks, width / 2, gap, total / 2
        monkeypatch.setattr(canvas, helper, replacement)
    changed = [canvas.grab().toImage() for canvas in widgets]
    assert changed[0] != before
    assert changed[0] == changed[1]
    for canvas in widgets:
        canvas.close()


@pytest.mark.parametrize('kind', ['line', 'bar', 'hbar', 'donut'])
def test_same_hover_reuses_chart_body_but_tooltip_tracks_pointer(qt_application, monkeypatch, kind):
    canvas = ChartCanvas()
    canvas.resize(480, 260)
    canvas.set_data(ChartData(kind, ['A', 'B'],
        [Series('a', 'Alpha', QColor('#1677ff'), [10, 20])], unit='人'))
    canvas.show()
    qt_application.processEvents()
    canvas.grab()
    if kind == 'donut':
        part = canvas._slices[0]
        point = part['center'] + QPointF(-part['outer'] * .75, 0)
    elif kind == 'bar':
        point = canvas._bar_hits[0][2].boundingRect().center()
    elif kind == 'hbar':
        point = QPointF(canvas._plot.center().x(), canvas._plot.top() + canvas._plot.height() / 4)
    else:
        point = QPointF(canvas._slot_center(0), canvas._plot.center().y())
    move(canvas, point)
    canvas.grab()
    method = '_paint_donut' if kind == 'donut' else '_paint_hbar' if kind == 'hbar' else '_paint_cartesian'
    body_calls, tips = [], []
    original_body, original_tip = getattr(canvas, method), canvas._paint_tooltip
    def body(painter):
        body_calls.append(True)
        return original_body(painter)
    def tooltip(painter, *args):
        tips.append(QPointF(canvas._pointer))
        return original_tip(painter, *args)
    monkeypatch.setattr(canvas, method, body)
    monkeypatch.setattr(canvas, '_paint_tooltip', tooltip)
    # Installing a drawing extension must invalidate the retained commands;
    # subsequent pointer movement should reuse that extension's current output.
    canvas.grab()
    canvas.grab()  # Donuts seed retained commands only after a repeated sector.
    body_calls.clear()
    tips.clear()
    point += QPointF(1, 1)
    move(canvas, point)
    canvas.grab()
    assert body_calls == []
    assert tips == [point]
    canvas.close()


@pytest.mark.parametrize('kind', ['line', 'bar', 'hbar'])
def test_slot_changes_reuse_static_chart_geometry(qt_application, monkeypatch, kind):
    canvas = ChartCanvas()
    canvas.resize(480, 260)
    canvas.set_data(ChartData(kind, ['A', 'B'],
        [Series('a', 'Alpha', QColor('#1677ff'), [10, 20])]))
    canvas.show()
    qt_application.processEvents()
    original = canvas._paint_body
    calls = []
    def body(painter):
        calls.append(True)
        return original(painter)
    monkeypatch.setattr(canvas, '_paint_body', body)
    canvas.grab()
    calls.clear()
    for index in (0, 1, 0, 1):
        if kind == 'bar':
            point = next(path.boundingRect().center() for slot, _, path in canvas._bar_hits if slot == index)
        elif kind == 'hbar':
            point = QPointF(canvas._plot.center().x(), canvas._plot.top() + (index + .5) * canvas._plot.height() / 2)
        else:
            point = QPointF(canvas._slot_center(index), canvas._plot.center().y())
        move(canvas, point)
        canvas.grab()
        assert canvas._hover == index
    assert calls == []
    canvas.close()


def test_donut_sector_transitions_do_not_compute_a_cache_signature(qt_application, monkeypatch):
    from math import cos, radians, sin
    canvas = ChartCanvas()
    canvas.resize(480, 260)
    canvas.set_data(ChartData('donut', ['A', 'B'],
        [Series('a', 'Alpha', QColor('#1677ff'), [10, 20])]))
    canvas.show()
    qt_application.processEvents()
    canvas.grab()
    calls = []
    original = canvas._body_key
    def signature():
        calls.append(True)
        return original()
    monkeypatch.setattr(canvas, '_body_key', signature)
    for index in (0, 1, 0, 1):
        part = canvas._slices[index]
        angle = radians(part['start'] + part['span'] / 2)
        radius = (part['inner'] + part['outer']) / 2
        move(canvas, part['center'] + QPointF(cos(angle) * radius, -sin(angle) * radius))
        canvas.grab()
        assert canvas._hover_slice == part['key']
    assert calls == []
    canvas.close()


@pytest.mark.parametrize('kind', ['line', 'bar', 'hbar', 'donut'])
@pytest.mark.parametrize('size,detailed', [((400, 190), False), ((960, 680), True)])
def test_retained_chart_commands_match_live_pixels_through_invalidation(qt_application, monkeypatch, kind, size, detailed):
    data = ChartData(kind, ['First', 'Second', 'Third'], [
        Series('a', 'Alpha', QColor('#1677ff'), [10, 20, 3], stack='together'),
        Series('b', 'Beta', QColor('#ef6b2e'), [4, 8, 6], stack='together', dashed=True)],
        unit='people', center_text='33', center_caption='total', donut_value_labels=True)
    widgets = [ChartCanvas(detailed=detailed), LiveCanvas(detailed=detailed)]
    for canvas in widgets:
        canvas.resize(*size)
        canvas.set_data(data)
        canvas.show()
    qt_application.processEvents()
    def equal_pixels():
        images = [canvas.grab().toImage() for canvas in widgets]
        assert images[0] == images[1]
        assert widgets[0]._bar_hits == widgets[1]._bar_hits
        assert widgets[0]._slices == widgets[1]._slices
    equal_pixels()
    for canvas in widgets:
        if kind == 'donut':
            part = canvas._slices[0]
            point = part['center'] + QPointF(-part['outer'] * .75, 0)
        elif kind == 'bar':
            point = canvas._bar_hits[0][2].boundingRect().center()
        elif kind == 'hbar':
            point = QPointF(canvas._plot.center().x(), canvas._plot.top() + canvas._plot.height() / 6)
        else:
            point = QPointF(canvas._slot_center(0), canvas._plot.center().y())
        move(canvas, point)
    equal_pixels()
    # Same-slot pointer motion must preserve exact tooltip position and pixels.
    for canvas in widgets:
        move(canvas, canvas._pointer + QPointF(2, 3))
    equal_pixels()
    # Input dataclasses are public and mutable; update() must see in-place edits.
    data.series[0].values[0] = 17
    data.series[0].color.setRgb(28, 185, 80)
    data.labels[0] = 'Changed label'
    equal_pixels()
    for canvas in widgets:
        canvas.set_hidden({'a'})
    equal_pixels()
    for canvas in widgets:
        canvas.set_hidden(set())
        canvas.set_linked_index(2)
        canvas.set_axis(AxisSpec(0, 40, 10))
        canvas.resize(size[0] + 15, size[1] + 10)
    equal_pixels()
    for canvas in widgets:
        canvas._font.setPixelSize(15)
        canvas._strong.setPixelSize(15)
    equal_pixels()
    monkeypatch.setattr('stats_tokens.GRID_COLOR', '#a7b2c3')
    monkeypatch.setattr('stats_tokens.TEXT_PRIMARY', '#19252e')
    equal_pixels()
    for canvas in widgets:
        canvas.close()
