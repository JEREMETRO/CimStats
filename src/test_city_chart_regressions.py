"""City chart presentation changes retain the active in-window detail."""
from datetime import datetime as D, timedelta

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication, QMainWindow, QScrollArea

from city_dashboard import CityDashboard
from city_model import build_city_snapshot
from dashboard_model import FilterState
from statistics_model import HistoryStore
from test_city_model import r


def city_snapshot(comparison=False, public=3, grain='hour'):
    rows = [r(name, 'A', hour, amount, 10) for hour in range(3)
            for name, amount in [('walking', 5), ('public-transport', public), ('private-motoring', 5-public)]]
    rows += [r('trip-time', 'WhiteCollar', hour, amount, 2)
             for hour, amount in enumerate((60, 100, 80))]
    before = (D(2024, 1, 1), D(2024, 1, 1, 3)) if comparison else None
    if comparison:
        rows += [{**row, '模拟时间': (D.strptime(row['模拟时间'], '%Y-%m-%d %H:%M:%S')
                 - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')} for row in list(rows)]
    return build_city_snapshot(HistoryStore(rows, D(2024, 1, 4)),
        FilterState((), D(2024, 1, 2), D(2024, 1, 2, 3), grain, before))


def city_window(monkeypatch, comparison=False):
    import stats_motion
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: False)
    window = QMainWindow()
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    window.setCentralWidget(scroll)
    dashboard = CityDashboard()
    scroll.setWidget(dashboard)
    dashboard.set_snapshot(city_snapshot(comparison))
    dashboard.reflow(960, 680)
    window.resize(960, 680)
    window.show()
    QApplication.processEvents()
    return window, dashboard


@pytest.mark.parametrize(('width', 'stacked'), [(720, True), (864, False)])
def test_city_comparison_card_displays_both_rings_after_mode_change(width, stacked):
    app = QApplication.instance() or QApplication([])
    dashboard = CityDashboard()
    try:
        dashboard.resize(width, 1800)
        dashboard.set_snapshot(city_snapshot())
        dashboard.reflow(width, 480)
        dashboard.show()
        app.processEvents()
        dashboard.set_snapshot(city_snapshot(comparison=True), '上一等长区间')
        app.processEvents()
        app.processEvents()
        panel = dashboard.panels['city-mode-share']
        first, second = panel.chart_views
        assert (first.parentWidget().y() < second.parentWidget().y()) == stacked
        if stacked:
            assert panel.legend_host.heightForWidth(panel.legend_host.width()) > panel.legend_host.sizeHint().height()
        for view in panel.chart_views:
            view.grab()
            sector = view._slices[0]
            center, radius = sector['center'], sector['outer']
            ring = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
            assert QRectF(view.visibleRegion().boundingRect()).contains(ring)
    finally:
        dashboard.close()


@pytest.mark.parametrize('comparison', [False, True])
@pytest.mark.parametrize('initial_mode', ['pie', 'line'])
def test_expanded_mode_switch_keeps_surface_and_syncs_source(monkeypatch, comparison, initial_mode):
    window, dashboard = city_window(monkeypatch, comparison)
    dashboard.set_mode(initial_mode)
    source = dashboard.panels['city-mode-share']
    clone = source._open_fullscreen()
    surface = source._fullscreen_dialog
    clone._toggle_category('步行')
    for mode in (('line', 'pie') if initial_mode == 'pie' else ('pie', 'line')):
        clone.mode_control._buttons[mode].click()
        QApplication.processEvents()
        assert surface.isVisible(), 'Changing chart type must keep the expanded surface open'
        assert source._fullscreen_dialog is surface and surface.panel is clone
        expected = dashboard.snapshot.pie_result if mode == 'pie' else dashboard.snapshot.charts['city-mode-share']
        for panel in (source, clone):
            assert panel.mode == mode and panel.mode_control.currentKey() == mode
            assert panel.result is expected
            assert panel._hidden_groups == {'步行'}
            assert len(panel.chart_views) == (2 if mode == 'pie' and comparison else 1)
        assert clone.detail_summary.cards[0]['window'] == (D(2024, 1, 2), D(2024, 1, 2, 3))
        assert bool(clone.result.comparison) is comparison
    surface.close()
    clone = source._open_fullscreen()
    assert clone._hidden_groups == {'步行'}
    window.close()


@pytest.mark.parametrize('public', [3, 4])
def test_new_city_snapshot_cancels_detail_without_adopting_old_selection(monkeypatch, public):
    window, dashboard = city_window(monkeypatch)
    source = dashboard.panels['city-mode-share']
    clone = source._open_fullscreen()
    clone._toggle_category('步行')
    surface = source._fullscreen_dialog
    dashboard.set_snapshot(city_snapshot(public=public))
    assert not surface.isVisible()
    assert not surface.adopt_on_return
    assert '步行' not in source._hidden_groups
    assert source.result is dashboard.snapshot.pie_result
    window.close()


@pytest.mark.parametrize(('grain', 'end_hour', 'value', 'suffix'), [
    ('hour', 1, 30, ''), ('day', 3, 40, ' · 数据不完整'),
    ('week', 3, 40, ' · 数据不完整'), ('month', 3, 40, ' · 数据不完整'),
])
def test_trip_time_chart_points_show_own_period_bounds(grain, end_hour, value, suffix):
    dashboard = CityDashboard()
    try:
        dashboard.set_snapshot(city_snapshot(comparison=True, grain=grain))
        panel = dashboard.panels['trip-time']
        points = [s for s in panel.chart_views[0].data.series if s.key == '平均']
        assert [(s.faded, s.values[0], s.notes[0]) for s in points] == [
            (previous, value,
             f'统计时段 2024-01-0{day} 00:00 至 2024-01-0{day} {end_hour:02}:00{suffix}')
            for previous, day in ((False, 2), (True, 1))
        ]
    finally:
        dashboard.close()


def test_trip_types_detail_summary_names_public_transport_volume():
    from chart_details import summary_cards
    from statistics_model import METRICS, Query
    rows = [r('trip-types', 'single-line', hour, 10, owner='a') for hour in range(3)]
    result = HistoryStore(rows, D(2024, 1, 4)).query(
        Query('trip-types', ('a',), None, D(2024, 1, 2), D(2024, 1, 2, 3), 'hour'))
    assert result.metric.scope == 'company'
    assert summary_cards(result, {'a': '甲公司'})[0]['display_values'] == [
        ('区间公共交通出行量', 30), ('小时均公共交通出行量', 10)]
