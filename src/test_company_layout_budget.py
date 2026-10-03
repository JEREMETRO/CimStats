"""Company folds must return released space to existing charts."""
import time
import pytest
from PySide6.QtTest import QTest
from test_stats_fluent_page import _loaded_page


@pytest.mark.parametrize('mode', ['default', 'companies', 'period'])
def test_summary_fold_grows_charts_and_restore_preserves_objects(mode, monkeypatch):
    import stats_motion
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: True)
    page = _loaded_page(); page.resize(1920, 1500); page.show()
    page.analysis_mode_control.setCurrentKey(mode)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    deadline = time.monotonic() + 10
    while (page.query_timer.isActive() or page.workers) and time.monotonic() < deadline:
        app.processEvents(); time.sleep(.01)
    QTest.qWait(350)
    dashboard = page.company_dashboard
    panels = list(dashboard.shared_panels.values()) or [p for g in dashboard.groups.values() for p in g.panels.values()]
    before = [p.height() for p in panels]
    views = [tuple(p.chart_views) for p in panels]
    for p in panels:
        for view in p.chart_views:
            view.grab()
    plots = [(view, view.plot_rect().height()) for p in panels for view in p.chart_views]
    assert plots
    snapshot, token = page.snapshot, page.token
    dashboard.set_summary_collapsed(True)
    samples = []
    for _ in range(10):
        QTest.qWait(25); samples.append(panels[0].height())
    assert all(p.height() > h for p, h in zip(panels, before))
    assert max(p.height() for p in panels) > 520
    assert len(set(samples)) > 2
    assert samples == sorted(samples)
    assert [tuple(p.chart_views) for p in panels] == views
    for view, _ in plots:
        view.grab()
    assert all(view.plot_rect().height() > old for view, old in plots)
    dashboard.set_summary_collapsed(False); QTest.qWait(400)
    assert [p.height() for p in panels] == before
    assert page.snapshot is snapshot and page.token == token
    page.close()


def test_filter_toggle_keeps_identity_and_position_during_reverse(monkeypatch):
    import stats_motion
    from PySide6.QtCore import QPoint
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: True)
    page = _loaded_page(); page.resize(1440, 960); page.show(); QTest.qWait(300)
    toggle = page.filter_toggle
    assert toggle is page.confirm_filters_button is page.expand_filters_button
    original = toggle.mapTo(page.filter_card, QPoint())
    expanded = page.filter_card.height()
    toggle.click()
    animation = page._filter_animation
    assert animation is not None
    animation.setCurrentTime(70)
    assert 40 <= page.filter_card.height() < expanded
    assert toggle.mapTo(page.filter_card, QPoint()) == original
    toggle.click(); QTest.qWait(350)
    assert page.filter_card.height() == expanded
    assert toggle.mapTo(page.filter_card, QPoint()) == original
    page.set_filters_collapsed(True); QTest.qWait(50)
    assert toggle.mapTo(page.filter_card, QPoint()) == original
    assert toggle.accessibleName() == '展开筛选'
    page.close()


@pytest.mark.parametrize('width', [900, 1100, 1440])
def test_period_field_keeps_primary_filters_and_actions_anchored(width):
    from PySide6.QtCore import QPoint
    page = _loaded_page(); page.resize(width, 960); page.show(); page.reflow(width); QTest.qWait(50)
    grid = page.toolbar_grid
    primary = [grid.getItemPosition(grid.indexOf(field)) for field in page._fields[:4]]
    details = grid.getItemPosition(grid.indexOf(page.filter_detail_host))
    physical = [w.mapTo(page.filter_card, QPoint()) for w in page._fields[:4]]
    height = page.filter_card.height()
    page.compare_field.show(); page._layout_signature = None; page.reflow(width); QTest.qWait(50)
    assert [grid.getItemPosition(grid.indexOf(field)) for field in page._fields[:4]] == primary
    assert grid.getItemPosition(grid.indexOf(page.filter_detail_host)) == details
    assert [w.mapTo(page.filter_card, QPoint()) for w in page._fields[:4]] == physical
    assert page.filter_card.height() == height
    page.close()
