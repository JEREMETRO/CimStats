"""Network content contract without depending on the chart renderer's internals."""
import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QWidget

from dashboard_model import FilterState, build_dashboard
from network_dashboard import NetworkDashboard
from network_model import NetworkOptions, build_network_snapshot
from statistics_model import HistoryStore
from test_network_model import NAMES, dashboard, history


class FakePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = None
        self.descriptor = None
        self.palette = None

    def set_company_palette(self, palette):
        self.palette = palette

    def set_descriptor(self, descriptor, snapshot):
        self.descriptor = descriptor

    def set_mode(self, mode):
        self.mode = mode

    def set_mode_control(self, widget):
        self.mode_control = widget

    def set_axis_spec(self, spec):
        self.axis_spec = spec

    def set_compact_height(self, height):
        self.compact_height = height
        self.setFixedHeight(height)


def test_vehicle_switch_keeps_one_title_and_does_not_render_internal_context():
    from decimal import Decimal
    from PySide6.QtWidgets import QLabel
    from network_dashboard import NetworkValueTile
    from network_model import NetworkValue
    QApplication.instance() or QApplication([])
    for selected in ('average', 'maximum'):
        value = NetworkValue('vehicles-running', '最大车辆需求数', '辆', Decimal(459),
                             context='存档当前线路需求，非历史峰值')
        tile = NetworkValueTile(2, value, NetworkOptions(vehicle=selected), '#1677FF')
        tile.resize(230, 120)
        tile.show()
        QApplication.instance().processEvents()
        assert tile.metric_title.text() == '车辆'
        assert tile.number.text() == '459'
        assert not any('存档当前' in label.text() for label in tile.findChildren(QLabel))
        tile.close()


def test_city_journey_tiles_expose_their_scope_in_tooltip_without_extra_label():
    from network_dashboard import NetworkValueTile
    from test_company_journey_union import amount, counters, network, source
    QApplication.instance() or QApplication([])
    snapshot = network(source(counters(), ('a',)))
    for position, metric in ((4, 'trip-types'), (5, 'transfer-coefficient')):
        tile = NetworkValueTile(position, amount(snapshot, metric), snapshot.options, '#1677FF')
        assert '全市公共交通行程' in tile.toolTip()
        assert '不作同期比较' in tile.accessibleDescription()
        tile.close()


def test_network_tile_retains_missing_reason_and_parts_without_repeating_comparison():
    from decimal import Decimal
    from card_comparisons import change
    from network_dashboard import NetworkValueTile
    from network_model import NetworkValue
    QApplication.instance() or QApplication([])
    comparison = change(Decimal(5), Decimal(4), '条', '较上日')
    value = NetworkValue('linecount', '线路', '条', Decimal(5),
                         (('公交', Decimal(5)),), False, '数据不完整', comparison)
    tile = NetworkValueTile(0, value, NetworkOptions(), '#1677FF')
    assert tile.toolTip() == '数据不完整；公交: 5'
    assert comparison.tooltip == tile.comparison_label.toolTip()
    assert comparison.tooltip not in tile.toolTip()
    tile.close()


def _fixture(mode='overall', grain='day', ids=('a', 'b')):
    rows = [history('transport-by-type', company, 0, amount, day=day)
            for company, amount in [('a', 10), ('b', 30)] for day in (1, 2)]
    rows += [history('linecount', company, 0, amount, day=day)
             for company, amount in [('a', 12), ('b', 7)] for day in (1, 2)]
    return build_network_snapshot(dashboard(rows, ids=ids, grain=grain),
                                  NetworkOptions(mode=mode), NAMES)


def _view(snapshot, tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / 'network.ini'), QSettings.Format.IniFormat)
    view = NetworkDashboard(settings)
    monkeypatch.setattr(view, '_make_chart_panel', FakePanel)
    view.set_company_palette({'a': '#397CC3', 'b': '#279D7A'})
    view.set_snapshot(snapshot)
    return view, settings


def test_three_modes_render_visible_summary_and_charts(tmp_path, monkeypatch):
    for mode, summaries, tiles, charts in (('overall', 1, 5, 7), ('companies', 2, 6, 9), ('period', 2, 6, 16)):
        view, _ = _view(_fixture(mode), tmp_path, monkeypatch)
        assert len(view.summary_cards) == summaries
        assert all(len(card.tiles) == tiles for card in view.summary_cards)
        assert len(view.chart_panels) == charts
        assert view.summary_cards[0].tiles[2].metric_title.text() == '车辆'
        if mode == 'overall':
            assert (None, 'coverage') not in view.chart_panels
            view.reflow(1300)
            assert all(view.summary_cards[0].tile_grid.itemAtPosition(0, index) is not None
                       for index in range(5))
        if mode == 'period':
            assert set(company for company, _ in view.chart_panels) == {'a', 'b'}
            assert view.chart_panels[('a', 'linecount')].axis_spec == view.chart_panels[('b', 'linecount')].axis_spec
        view.reflow(780)
        view.reflow(1300)
        view.close()


def test_single_company_overall_keeps_six_readable_tiles_on_one_wide_row(tmp_path, monkeypatch):
    view, _ = _view(_fixture(ids=('a',)), tmp_path, monkeypatch)
    card = view.summary_cards[0]
    assert len(card.tiles) == 6
    view.reflow(1300)
    assert all(card.tile_grid.itemAtPosition(0, index) is not None for index in range(6))
    assert card.tile_grid.itemAtPosition(1, 0) is None
    vehicle = card.tiles[2]
    assert vehicle.metric_title.text() == '车辆'
    assert vehicle.option_control.width() <= 120
    view.reflow(1154)
    assert all(card.tile_grid.itemAtPosition(0, index) is not None for index in range(6))
    assert card.tile_grid.itemAtPosition(1, 0) is None
    assert vehicle.metric_title.text() == '车辆'
    view.reflow(920)
    assert card.tile_grid.itemAtPosition(1, 0) is not None
    assert vehicle.metric_title.text() == '车辆'
    view.close()


def test_all_card_switches_use_the_same_quiet_selection_in_each_mode(tmp_path, monkeypatch):
    from PySide6.QtGui import QColor
    from stats_tokens import SEGMENT_QUIET_BG, SEGMENT_QUIET_HOVER

    for mode in ('overall', 'companies', 'period'):
        view, _ = _view(_fixture(mode), tmp_path, monkeypatch)
        controls = [tile.option_control for card in view.summary_cards
                    for tile in card.tiles if tile.option_control is not None]
        controls += [control for group in view.chart_controls.values() for control in group]
        assert controls
        assert all(control._subtle and control._compact for control in controls)
        view.resize(1500, 900); view.show(); QApplication.instance().processEvents()
        for control in controls:
            image = control.grab().toImage(); scale = image.devicePixelRatioF()
            button = control._buttons[control.currentKey()]
            assert image.pixelColor(round((button.x()+button.width()/2)*scale), round(4*scale)) in (
                QColor(SEGMENT_QUIET_BG), QColor(SEGMENT_QUIET_HOVER))
            assert all(item.graphicsEffect() is None for item in control._buttons.values())
        view.close()


def test_overall_uses_four_chart_columns_and_compact_summary_toggle(tmp_path, monkeypatch):
    for ids, count in ((('a',), 8), (('a', 'b'), 7)):
        view, _ = _view(_fixture(ids=ids), tmp_path, monkeypatch)
        view.reflow(1154, 666)
        card = view.summary_cards[0]
        assert card.title.text() == '数据摘要'
        assert card.summary_button.accessibleName() == '收起数据摘要'
        assert card.minimumSizeHint().height() <= (226 if len(ids) == 1 else 168)
        assert all(bool(tile.comparison_label.text()) == tile.comparison_label.comparison.available
                   for tile in card.tiles)
        _, grid, charts = view._sections[0]
        assert all(grid.itemAtPosition(0, index) is not None for index in range(4))
        second_positions = (0, 4, 8) if count == 7 else range(4)
        assert all(grid.itemAtPosition(1, index) is not None
                   for index in second_positions)
        if count == 7:
            assert [grid.itemAtPosition(1, index).widget() for index in second_positions] == charts[4:]
        assert grid.itemAtPosition(2, 0) is None
        assert all(180 <= panel.minimumHeight() <= 300
                   for panel in view.chart_panels.values())
        view.close()


def test_overall_summary_budget_keeps_complete_tile_bottom_edges(tmp_path, monkeypatch):
    view, _ = _view(_fixture(), tmp_path, monkeypatch)
    view.resize(1168, 765); view.show(); view.reflow(1168, 765)
    QApplication.instance().processEvents()
    card = view.summary_cards[0]
    assert all(card.tile_host.contentsRect().contains(tile.geometry()) for tile in card.tiles)
    assert all(tile.visibleRegion().contains(tile.rect()) for tile in card.tiles)
    view.close()


def test_companies_attempts_three_by_three_charts_at_wide_sizes(tmp_path, monkeypatch):
    view, _ = _view(_fixture('companies'), tmp_path, monkeypatch)
    view.reflow(1634, 850)
    grid = view._sections[0][1]
    assert all(grid.itemAtPosition(row, column) is not None
               for row in range(3) for column in range(3))
    assert grid.itemAtPosition(3, 0) is None
    assert all(panel.compact_height >= 180 for panel in view.chart_panels.values())
    view.close()


def test_period_attempts_two_by_four_charts_per_company(tmp_path, monkeypatch):
    view, _ = _view(_fixture('period'), tmp_path, monkeypatch)
    view.reflow(1634, 850)
    assert all(control.width() <= 120 for controls in view.chart_controls.values()
               for control in controls)
    for section, grid, charts in view._sections:
        assert len(charts) == 8
        assert all(grid.itemAtPosition(row, column) is not None
                   for row in range(4) for column in range(2))
        assert grid.itemAtPosition(4, 0) is None
    view.close()


def test_single_company_period_uses_full_width_four_by_two_grid(tmp_path, monkeypatch):
    view, _ = _view(_fixture('period', ids=('a',)), tmp_path, monkeypatch)
    view.reflow(1154, 746)
    assert len(view._sections) == 1
    _, grid, charts = view._sections[0]
    assert len(charts) == 8
    assert all(grid.itemAtPosition(row, column) is not None
               for row in range(2) for column in range(4))
    assert view.summary_cards[0].tile_grid.itemAtPosition(0, 5) is not None
    assert all(panel.compact_height >= 230 for panel in view.chart_panels.values())
    view.close()


def test_summary_option_switch_is_shared_and_emits_network_options(tmp_path, monkeypatch):
    view, _ = _view(_fixture('companies'), tmp_path, monkeypatch)
    seen = []
    view.options_changed.connect(seen.append)
    view.summary_cards[0].tiles[1].option_control.setCurrentKey('stopcount')
    assert seen[-1].facility == 'stopcount'
    assert seen[-1].mode == 'companies'
    view.set_snapshot(build_network_snapshot(
        dashboard([], grain='day'), seen[-1], NAMES))
    assert all(card.tiles[1].option_control.currentKey() == 'stopcount'
               for card in view.summary_cards)
    view.close()


def test_chart_preference_survives_hourly_bar_restriction(tmp_path, monkeypatch):
    view, settings = _view(_fixture(grain='day'), tmp_path, monkeypatch)
    view._set_chart_mode('linecount', 'line')
    assert settings.value('network/linecount/chart_mode') == 'line'
    view.set_snapshot(_fixture(grain='hour'))
    assert view.chart_panels[(None, 'linecount')].mode == 'bar'
    assert settings.value('network/linecount/chart_mode') == 'line'
    view.set_snapshot(_fixture(grain='day'))
    assert view.chart_panels[(None, 'linecount')].mode == 'line'
    view.close()


def test_period_stacked_bars_share_axis_that_fits_full_stack(tmp_path, monkeypatch):
    rows = [history('transport-by-type', company, 0, amount, day=day, group=group)
            for company, values in [('a', (10, 25)), ('b', (30, 45))]
            for day in (1, 2) for group, amount in zip(('bus', 'tram'), values)]
    snapshot = build_network_snapshot(dashboard(rows, grain='day'),
                                      NetworkOptions(mode='period'), NAMES)
    view, _ = _view(snapshot, tmp_path, monkeypatch)
    axes = [view.chart_panels[(company, 'transport-by-type')].axis_spec
            for company in ('a', 'b')]
    assert axes[0] == axes[1]
    assert axes[0].upper >= 75
    view.close()


def test_period_axis_recomputes_from_latest_quantity_bars_after_mode_switch(tmp_path, monkeypatch):
    rows = [history('linecount', company, hour, amount, day=day)
            for company, day, hour, amount in [
                ('a', 1, 0, 80), ('a', 2, 0, 3),
                ('a', 3, 0, 100), ('a', 4, 0, 5),
                ('b', 1, 0, 70), ('b', 2, 0, 2),
                ('b', 3, 0, 90), ('b', 4, 0, 4),
            ]]
    from datetime import datetime as D
    source = build_dashboard(HistoryStore(rows, D(2024, 1, 5)), FilterState(
        ('a', 'b'), D(2024, 1, 3), D(2024, 1, 5), 'day',
        (D(2024, 1, 1), D(2024, 1, 3))))
    snapshot = build_network_snapshot(source, NetworkOptions(mode='period'), NAMES)
    view, _ = _view(snapshot, tmp_path, monkeypatch)
    assert view.chart_panels[('a', 'linecount')].axis_spec.upper >= 100
    view._set_chart_mode('linecount', 'bar')
    assert view.chart_panels[('a', 'linecount')].axis_spec.upper <= 10
    assert (view.chart_panels[('a', 'linecount')].axis_spec ==
            view.chart_panels[('b', 'linecount')].axis_spec)
    view.close()
