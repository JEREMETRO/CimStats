"""Behavior and actual painter regressions for the compact data policy."""
import os
import sys
from pathlib import Path
from decimal import Decimal

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

import pytest
from PySide6.QtCore import QSettings, QEvent, Qt
from PySide6.QtGui import QPainter, QFocusEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from statistics_page import StatisticsPage
from chart_canvas import ChartData
from network_model import NetworkOptions, build_network_snapshot
from test_dashboard_page import session
from test_network_page import _wait
from test_network_model import dashboard, history, NAMES, chart, value
from test_chart_canvas import canvas, line


def application():
    return QApplication.instance() or QApplication([])


def test_single_archive_guards_both_modes_and_restored_network_settings(tmp_path):
    app = application()
    settings = QSettings(str(tmp_path / 'guard.ini'), QSettings.Format.IniFormat)
    settings.setValue('network/mode', 'companies')
    page = StatisticsPage(settings)
    data = session()
    data['companies'] = data['companies'][:1] + [{'公司标识': 'a'}, {'公司标识': ''}, {}]
    try:
        page.set_session(data)
        _wait(app, lambda: page.snapshot is not None)
        assert len(page.company_menu.actions()) == 1
        assert not page.analysis_mode_control._buttons['companies'].isEnabled()
        assert not page.network_mode_control._buttons['companies'].isEnabled()
        assert page.network_options.mode == 'overall'
        assert settings.value('network/mode') == 'overall'
        for control in (page.analysis_mode_control, page.network_mode_control):
            with pytest.raises(ValueError, match='disabled'):
                control.setCurrentKey('companies')
            control.setCurrentKey('period')
            assert control.currentKey() == 'period'
        page.analysis_mode_control._current_key = 'companies'
        page._mode_changed()
        assert page.analysis_mode == 'default'
        page.network_mode_control._current_key = 'companies'
        page._network_mode_changed()
        assert page.network_options.mode == 'overall'
    finally:
        page.close()


def test_multi_archive_mode_survives_one_selection_then_replacement_resets(tmp_path):
    app = application()
    page = StatisticsPage(QSettings(str(tmp_path / 'replace.ini'), QSettings.Format.IniFormat))
    try:
        page.set_session(session())
        _wait(app, lambda: page.snapshot is not None)
        page.network_mode_control.setCurrentKey('companies')
        page.analysis_mode_control.setCurrentKey('companies')
        page.company_menu.actions()[1].setChecked(False)
        _wait(app, lambda: page.snapshot is not None)
        assert page.network_options.mode == 'companies'
        assert page.analysis_mode == 'companies'
        assert page.network_snapshot.options.mode == 'companies'
        assert page.network_mode_control._buttons['companies'].isEnabled()
        page.company_menu.actions()[0].setChecked(False)
        _wait(app, lambda: page.snapshot is not None and page.network_snapshot is not None)
        assert page.network_mode_control.currentKey() == 'companies'
        assert page.network_snapshot.options.mode == 'companies'
        assert page.network_snapshot.filters.companies == ()
        assert page.network_snapshot.summaries == ()
        data = session()
        data['companies'] = data['companies'][:1]
        page.set_session(data)
        _wait(app, lambda: page.snapshot is not None)
        assert page.network_options.mode == 'overall'
        assert page.analysis_mode == 'default'
    finally:
        page.close()


@pytest.mark.parametrize('ids,expected', [(('a',), 7), (('b',), 0), (('a', 'b'), 7)])
def test_demand_sums_selected_lines_and_preserves_average_charts(ids, expected):
    rows = [history('vehicles-running', owner, hour, amount * 1024)
            for owner, amount in [('a', 3), ('b', 5)] for hour in (0, 1)]
    source = dashboard(rows, ids)
    lines = ({'公司标识': 'a', '理论最大车辆需求数': 3},
             {'公司标识': 'a', '理论最大车辆需求数': 4},
             {'公司标识': 'b', '理论最大车辆需求数': 0},
             {'公司标识': 'c', '理论最大车辆需求数': 999})
    average = build_network_snapshot(source, NetworkOptions(), NAMES)
    maximum = build_network_snapshot(source, NetworkOptions(vehicle='maximum'), NAMES, lines=lines)
    demand = value(maximum.summaries[0], 2)
    assert demand.title == '车辆' == value(average.summaries[0], 2).title
    assert demand.value == Decimal(expected) and demand.complete
    assert not demand.context
    assert not demand.comparison.text
    assert chart(maximum, 'vehicles-running') == chart(average, 'vehicles-running')


@pytest.mark.parametrize('lines', [None, ({'公司标识': 'a'},),
    ({'公司标识': 'a', '理论最大车辆需求数': 3}, {'公司标识': 'a', '理论最大车辆需求数': None}),
    ({'公司标识': 'a', '理论最大车辆需求数': -1},)])
def test_missing_demand_is_not_zero_or_partial_total(lines):
    network = build_network_snapshot(dashboard([], ('a',)), NetworkOptions(vehicle='maximum'), NAMES, lines=lines)
    assert value(network.summaries[0], 2).value is None
    assert not value(network.summaries[0], 2).complete


def test_empty_known_line_scope_is_zero_but_empty_company_selection_is_missing():
    zero = build_network_snapshot(dashboard([], ('a',)), NetworkOptions(vehicle='maximum'), NAMES, lines=())
    assert value(zero.summaries[0], 2).value == 0
    empty = build_network_snapshot(dashboard([], ()), NetworkOptions(vehicle='maximum'), NAMES, lines=())
    assert value(empty.summaries[0], 2).value is None


def test_period_demand_never_compares_current_snapshot_to_itself():
    rows = [history('vehicles-running', 'a', 0, 1024, day=day) for day in (1, 2)]
    network = build_network_snapshot(dashboard(rows, ('a',)), NetworkOptions(mode='period', vehicle='maximum'),
                                     NAMES, lines=({'公司标识': 'a', '理论最大车辆需求数': 8},))
    assert value(network.summaries[0], 2).value == 8
    assert not value(network.summaries[0], 2).comparison.text
    assert chart(network, 'vehicles-running', 'a').result.comparison


@pytest.mark.parametrize('kind', ['line', 'bar', 'hbar', 'donut'])
@pytest.mark.parametrize('detailed', [False, True])
def test_actual_painter_omits_compact_numbers_keeps_detail(monkeypatch, kind, detailed):
    texts = []
    original = QPainter.drawText
    def record(painter, *args):
        if args and isinstance(args[-1], str):
            texts.append(args[-1])
        return original(painter, *args)
    monkeypatch.setattr(QPainter, 'drawText', record)
    widget = canvas(ChartData(kind, ['类别甲', '类别乙'], [line([13.37, 21.19])],
                             center_text='34.56', center_caption='辆'),
                    width=400, height=190, detailed=detailed)
    try:
        numbers = {'13.37', '21.19', '34.56', '38.7%', '61.3%'}
        assert bool(numbers.intersection(texts)) == detailed
        assert any('类别' in text for text in texts)
        if not detailed:
            widget.show_values = True
            texts.clear()
            widget.grab()
            assert not numbers.intersection(texts)
    finally:
        widget.close()


def test_pivot_focus_ring_only_follows_keyboard_focus(tmp_path):
    app = application()
    page = StatisticsPage(QSettings(str(tmp_path / 'focus.ini'), QSettings.Format.IniFormat))
    try:
        item = page.tab_bar.items['network']
        app.sendEvent(item, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.MouseFocusReason))
        assert item.property('keyboardFocus') is False
        app.sendEvent(item, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
        assert item.property('keyboardFocus') is True
        app.sendEvent(item, QMouseEvent(QEvent.Type.MouseButtonPress, item.rect().center(),
                      item.mapToGlobal(item.rect().center()), Qt.MouseButton.LeftButton,
                      Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        assert item.property('keyboardFocus') is False
        app.sendEvent(item, QFocusEvent(QEvent.Type.FocusOut))
        assert item.property('keyboardFocus') is False
    finally:
        page.close()


@pytest.mark.parametrize('raw,expected', [('', None), (None, None), ('bad', None), ('0', 0), ('12', 12)])
def test_normalized_demand_preserves_missing_raw_field(tmp_path, monkeypatch, raw, expected):
    from test_line_schedule import session_fixture
    data = session_fixture(tmp_path, monkeypatch, departures=[], line_extra={'最大配车数': raw})
    assert data['lines'][0]['理论最大车辆需求数'] == expected


def test_highlight_hover_border_is_stable_and_keyboard_focus_remains_visible():
    from latest_info_page import HighlightCard
    from PySide6.QtTest import QTest
    app = application()
    card = HighlightCard(0)
    card.resize(300, 210)
    card.show()
    app.processEvents()
    try:
        QTest.mouseMove(card, card.rect().topLeft() - card.rect().bottomRight())
        resting = card.grab().toImage()
        QTest.mouseMove(card, card.rect().center())
        hovering = card.grab().toImage()
        border = [(x, y) for y in range(3) for x in range(20, 100)]
        assert [resting.pixelColor(x, y) for x, y in border] == [
            hovering.pixelColor(x, y) for x, y in border]
        app.sendEvent(card, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
        assert card.property('keyboardFocus') is True
        keyboard = card.grab().toImage()
        assert any(keyboard.pixelColor(x, y) != resting.pixelColor(x, y) for x, y in border)
        app.sendEvent(card, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.MouseFocusReason))
        assert card.property('keyboardFocus') is False
    finally:
        card.close()


def test_demand_export_matches_selected_snapshot_and_context(tmp_path):
    from stats_exports import export_xlsx
    from openpyxl import load_workbook
    source = dashboard([], ('a',))
    network = build_network_snapshot(source, NetworkOptions(vehicle='maximum'), NAMES,
        lines=({'公司标识': 'a', '理论最大车辆需求数': 7},
               {'公司标识': 'b', '理论最大车辆需求数': 99}))
    path = tmp_path / 'demand.xlsx'
    export_xlsx(source, path, NAMES, network)
    rows = list(load_workbook(path, data_only=True)['网络摘要'].values)
    row = next(row for row in rows[1:] if row[7] == '车辆')
    assert row[8] == 7 and row[9] == '辆'
    assert not row[16] and not value(network.summaries[0], 2).context


def test_home_custom_charts_omit_numeric_labels_preserve_values_and_drillthrough(monkeypatch):
    from latest_info_page import LatestInfoPage
    from test_latest_info_page import session as home_session, snapshot
    app = application()
    page = LatestInfoPage()
    page.resize(960, 680)
    page.set_session(home_session())
    page.set_snapshot(snapshot())
    page.show()
    app.processEvents()
    painted = []
    original = QPainter.drawText
    def record(painter, *args):
        if isinstance(args[-1], str):
            painted.append(args[-1])
        return original(painter, *args)
    monkeypatch.setattr(QPainter, 'drawText', record)
    try:
        for panel in (page.passengers, page.departures):
            panel.show_structure()
            assert panel.ring.center_total.isHidden()
            assert panel.total_label.isHidden()
            for row in panel.visible_mode_rows():
                assert row.number.isHidden() and row.share.isHidden()
                assert row.toolTip() == ''
            painted.clear()
            panel.grab()
            assert panel.ring.center_total.text() not in painted
            assert all(row.number.text() not in painted and row.share.text() not in painted
                       for row in panel.visible_mode_rows())
            panel.show_ranking()
            rows = panel.visible_ranking_rows()
            assert rows and all(row.number.isHidden() for row in rows)
            assert all(row.track.toolTip() == '' and row.number.text() in row.accessibleName() for row in rows)
            painted.clear()
            panel.grab()
            assert all(row.number.text() not in painted for row in rows)
            emissions = []
            panel.line_requested.connect(emissions.append)
            rows[0].action.click()
            assert emissions == [rows[0].line.key]
            panel.show_line_share()
            assert panel.share_ring.center_total.isHidden() and panel.total_label.isHidden()
            assert all(row.number.isHidden() and row.share.isHidden() for row in panel.visible_share_rows())
    finally:
        page.close()


@pytest.mark.parametrize('opacity', [1.0, .2])
def test_compact_png_renders_values_during_fade_and_restores_effect(tmp_path, opacity):
    from stats_exports import export_png
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsOpacityEffect
    app = application()
    host = QWidget()
    layout = QVBoxLayout(host)
    plot = canvas(ChartData('bar', ['甲', '乙'], [line([13.37, 21.19])]))
    layout.addWidget(plot)
    host.resize(400, 190)
    host.show()
    app.processEvents()
    effect = QGraphicsOpacityEffect(plot)
    effect.setOpacity(opacity)
    plot.setGraphicsEffect(effect)
    try:
        path = tmp_path / 'compact.png'
        export_png(host, path)
        image = QImage(str(path))
        colored = sum(image.pixelColor(x, y).blue() - image.pixelColor(x, y).red() > 80
                      for y in range(0, image.height(), 2) for x in range(0, image.width(), 2))
        assert colored > 100
        assert plot.graphicsEffect() is effect and effect.isEnabled() and effect.opacity() == opacity
    finally:
        host.close()
