import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from statistics_page import StatisticsPage
from test_city_model import build, r


def test_city_six_charts_five_kpis_defaults_and_switches_use_same_snapshot():
    from city_dashboard import CityDashboard
    QApplication.instance() or QApplication([])
    widget = CityDashboard()
    snap = build([r('trip-time', 'WhiteCollar', 0, 100, 2), r('trip-time', 'BlueCollar', 0, 60, 3)] +
                 [r(name, 'A', 0, n, 10) for name, n in
                  [('walking', 5), ('public-transport', 3), ('private-motoring', 2)]])
    widget.set_snapshot(snap)
    assert len(widget.tiles) == 5 and len(widget.panels) == 6
    panel = widget.panels['trip-time']
    assert set(panel.legend_buttons) == {'平均', 'WhiteCollar', 'BlueCollar'}
    assert panel.curve_control is None
    assert panel.legend_buttons['平均'].isChecked()
    assert not panel.legend_buttons['WhiteCollar'].isChecked()
    assert widget.panels['city-mode-share'].mode == 'pie'
    widget.set_curves(('平均', 'WhiteCollar'))
    assert panel._hidden_groups == {'BlueCollar'}
    widget.set_mode('line')
    assert widget.snapshot is snap and widget.panels['city-mode-share'].mode == 'line'
    assert widget.panels['trip-time'].result.series[('', '平均')][0].value == 32
    widget.reflow(1500, 850)
    assert widget.chart_columns == 3
    widget.reflow(900, 700)
    assert widget.chart_columns == 2
    widget.reflow(600, 700)
    assert widget.chart_columns == 1
    widget.close()


def test_mode_share_card_shows_only_public_transport_comparison():
    from city_dashboard import CityDashboard
    from card_comparison_label import ComparisonLabel
    QApplication.instance() or QApplication([])
    widget = CityDashboard()
    widget.set_snapshot(build([r(name, 'A', 0, amount, 10) for name, amount in
        [('walking', 5), ('public-transport', 3), ('private-motoring', 2)]]))
    tile = widget.tiles['city-mode-share']
    comparisons = [tile.values.itemAt(i).widget() for i in range(tile.values.count())
                   if isinstance(tile.values.itemAt(i).widget(), ComparisonLabel)]
    assert len(comparisons) == 1
    assert comparisons[0].comparison is tile.model.details[1].comparison
    assert tile.values.count() == 4  # Three values and one comparison.
    assert tile.minimumHeight() < 164
    assert len(tile.model.details) == 3
    widget.close()


def test_city_route_hides_company_and_comparison_filters_and_rejects_stale_city():
    QApplication.instance() or QApplication([])
    page = StatisticsPage()
    page.tab_bar.setCurrentItem('city')
    assert page._fields[0].isHidden() and page._fields[3].isHidden() and page.compare_field.isHidden()
    page._receive(page.token - 1, (None, None, build([])))
    assert page.city_snapshot is None
    page.tab_bar.setCurrentItem('company')
    assert not page._fields[0].isHidden() and not page._fields[3].isHidden()
    page.close()


def test_city_filters_use_compact_row_and_restore_company_layout():
    from PySide6.QtWidgets import QBoxLayout
    QApplication.instance() or QApplication([])
    page = StatisticsPage()
    page.resize(1400, 960)
    page.show()
    page.tab_bar.setCurrentItem('city')
    QTest.qWait(30)
    # Every tab shares one filter layout: captioned fields in one row, the
    # actual date range on a caption line below. City hides company and mode.
    grid = page.toolbar_grid
    row_of = lambda widget: grid.getItemPosition(grid.indexOf(widget))[0]
    assert page._fields[0].isHidden() and page._fields[3].isHidden()
    assert page._fields[1].layout().direction() == QBoxLayout.Direction.TopToBottom
    assert row_of(page._fields[1]) == row_of(page._fields[2]) == 0
    assert row_of(page.filter_detail_host) == 1
    assert page.filter_detail_host.layout().indexOf(page._fields[5]) == 0
    assert page._fields[1].width() <= 360 and page._fields[2].width() <= 200
    assert all(tile.height() >= 104 for tile in page.city_dashboard.tiles.values())
    page.tab_bar.setCurrentItem('company')
    QTest.qWait(30)
    assert [row_of(field) for field in page._fields[:4]] == [0, 0, 0, 0]
    assert page.filter_detail_host.layout().indexOf(page._fields[5]) == 0
    page.close()


def test_city_fullscreen_keeps_selected_curves_mode_and_legend():
    from city_dashboard import CityDashboard
    QApplication.instance() or QApplication([])
    widget = CityDashboard()
    widget.set_snapshot(build([r('trip-time', 'WhiteCollar', 0, 100, 2)]))
    widget.set_curves(('平均', 'WhiteCollar'))
    panel = widget.panels['trip-time']
    panel._toggle_category('WhiteCollar')
    panel._open_fullscreen()
    clone = panel._fullscreen_dialog.city_panel
    assert set(clone.result.series) == set(panel.result.series)
    assert clone._hidden_groups == panel._hidden_groups
    assert clone.curve_control is None
    clone.legend_buttons['WhiteCollar'].click()
    assert 'WhiteCollar' not in panel._hidden_groups
    assert set(widget.selected_curves) == {'平均', 'WhiteCollar'}
    assert 'WhiteCollar' not in panel.chart_views[0].hidden
    panel._fullscreen_dialog.close()
    widget.close()


def test_city_legend_toggle_can_hide_all_and_persists_without_changing_average(tmp_path):
    from city_dashboard import CityDashboard
    from PySide6.QtCore import QSettings
    QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / 'legend.ini'), QSettings.Format.IniFormat)
    snap = build([r('trip-time', 'WhiteCollar', 0, 100, 2)])
    widget = CityDashboard(settings)
    widget.set_snapshot(snap)
    panel = widget.panels['trip-time']
    panel.legend_buttons['平均'].click()
    assert widget.selected_curves == ()
    assert set(panel.legend_buttons) == {'平均', 'WhiteCollar'}
    assert panel.chart_views[0].hidden == {'平均', 'WhiteCollar'}
    assert not panel.chart_views[0].visible_series()
    assert widget.tiles['trip-time'].model.value == 50
    widget.close()
    restored = CityDashboard(settings)
    restored.set_snapshot(snap)
    panel = restored.panels['trip-time']
    assert all(not button.isChecked() for button in panel.legend_buttons.values())
    panel.legend_buttons['WhiteCollar'].click()
    assert restored.selected_curves == ('WhiteCollar',)
    assert panel.legend_buttons['WhiteCollar'].isChecked()
    assert restored.snapshot is snap
    restored.close()


def test_city_summary_releases_chart_space_continuously_without_rebuilding(monkeypatch):
    from city_dashboard import CityDashboard
    import stats_motion
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: True)
    app = QApplication.instance() or QApplication([])
    widget = CityDashboard()
    widget.resize(1200, 900)
    widget.show()
    widget.reflow(1200, 900)
    app.processEvents()
    panel = widget.panels['population']
    expanded = (widget.summary.height(), panel.height())
    def unexpected_rebuild(*args):
        raise AssertionError('height-only motion must preserve chart contents')
    for chart in widget.panels.values():
        monkeypatch.setattr(chart, 'set_compact_height', unexpected_rebuild)
    try:
        widget.set_summary_collapsed(True)
        animation = widget.summary_motion.animation
        animation.setCurrentTime(animation.duration() // 2)
        app.processEvents()
        middle = (widget.summary.height(), panel.height())
        animation.setCurrentTime(animation.duration())
        app.processEvents()
        collapsed = (widget.summary.height(), panel.height())
        assert expanded[0] > middle[0] > collapsed[0]
        assert expanded[1] < middle[1] < collapsed[1]
        assert max(s + 2 * h for s, h in (expanded, middle, collapsed)) - min(
            s + 2 * h for s, h in (expanded, middle, collapsed)) <= 2
        widget.set_summary_collapsed(False)
        animation = widget.summary_motion.animation
        animation.setCurrentTime(animation.duration() // 2)
        app.processEvents()
        assert collapsed[1] > panel.height() > expanded[1]
        animation.setCurrentTime(animation.duration())
        app.processEvents()
        assert (widget.summary.height(), panel.height()) == expanded
    finally:
        widget.close()


def test_city_summary_preserves_rendered_views_and_preferences_with_motion_on_and_off(monkeypatch):
    from city_dashboard import CityDashboard
    import stats_motion
    app = QApplication.instance() or QApplication([])
    snapshot = build([
        r('population', 'A', 0, 100), r('trip-number', 'A', 0, 20),
        r('trip-time', 'WhiteCollar', 0, 60, 2),
        r('economy', 'growth', 0, 100, 10000),
        r('energy-prices', 'electricity', 0, 50),
        *[r(name, 'A', 0, amount, 10) for name, amount in
          [('walking', 5), ('public-transport', 3), ('private-motoring', 2)]]])
    for enabled in (False, True):
        monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: enabled)
        widget = CityDashboard()
        widget.resize(1200, 900)
        widget.show()
        widget.set_snapshot(snapshot)
        widget.set_curves(('WhiteCollar',))
        widget.reflow(1200, 900)
        app.processEvents()
        original_views = {key: tuple(panel.chart_views) for key, panel in widget.panels.items()}
        assert all(original_views.values())
        state = widget.display_state()
        try:
            for collapsed in (True, False):
                widget.set_summary_collapsed(collapsed)
                animation = widget.summary_motion.animation
                if enabled:
                    assert animation is not None
                    duration = animation.duration()
                    animation.setCurrentTime(duration // 2)
                    app.processEvents()
                    assert {key: tuple(panel.chart_views) for key, panel in widget.panels.items()} == original_views
                    animation.setCurrentTime(duration)
                else:
                    assert animation is None
                app.processEvents()
                assert {key: tuple(panel.chart_views) for key, panel in widget.panels.items()} == original_views
                assert widget.snapshot is snapshot and widget.display_state() == state
        finally:
            widget.close()
