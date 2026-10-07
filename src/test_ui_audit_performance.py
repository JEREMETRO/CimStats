"""Behavioral regressions for unnecessary rendering and motion work."""
import copy
from dataclasses import replace
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from test_stats_fluent_page import _loaded_page

def test_restore_does_not_replay_first_entrance(qt_application,monkeypatch):
    import stats_motion
    widget=QWidget()
    reveal=stats_motion.attach_surface_reveal(widget)
    calls=[]
    monkeypatch.setattr(reveal.motion,'reveal',lambda **kwargs:calls.append(kwargs))
    widget.show();qt_application.processEvents()
    widget.hide();widget.show();qt_application.processEvents()
    assert len(calls)==1
    widget.close()

def test_equivalent_chart_setters_do_not_rebuild_and_detect_changed_values(qt_application,monkeypatch):
    page=_loaded_page()
    panel=next(iter(next(iter(page.company_dashboard.groups.values())).panels.values()))
    calls=[]
    original=panel._render
    monkeypatch.setattr(panel,'_render',lambda:calls.append(True) or original())
    try:
        panel.set_result(copy.deepcopy(panel.result),dict(panel.companies))
        panel.set_mode_options(panel._allowed_modes)
        panel.set_mode_labels(dict(panel._mode_labels))
        panel.set_axis_spec(panel._axis_override)
        assert not calls
        changed=copy.deepcopy(panel.result)
        next(iter(changed.series.values()))[0].value += 1
        panel.set_result(changed,panel.companies)
        assert len(calls)==1
    finally:
        page.close()

def test_satisfaction_summary_switch_preserves_fixed_four_charts(qt_application):
    page=_loaded_page();d=page.company_dashboard
    groups=dict(d.groups);panels=[p for g in groups.values() for p in g.panels.values()]
    page.satisfaction_combo.setCurrentIndex(1)
    assert d.groups==groups
    assert [p for g in d.groups.values() for p in g.panels.values()]==panels
    assert all(g.satisfaction_combo.currentData()=='satisfaction-cost' for g in d.groups.values())
    page.close()

def test_network_summary_switch_reuses_canvas_and_legend_selection(qt_application,monkeypatch):
    from network_model import build_network_snapshot
    page=_loaded_page();d=page.network_dashboard
    d.set_snapshot(page.network_snapshot)
    panels=dict(d.chart_panels)
    target=next(p for p in panels.values() if p._legend_keys)
    target._hidden_categories.update(target._legend_keys)
    calls=[]
    for p in panels.values():
        monkeypatch.setattr(p,'_render',lambda:calls.append(True))
    options=replace(page.network_snapshot.options,vehicle='maximum')
    d.set_snapshot(build_network_snapshot(page.snapshot,options,page._names(),lines=page._network_lines))
    assert d.chart_panels==panels
    assert target._hidden_categories==set(target._legend_keys)
    assert not calls
    page.close()

def test_elevation_merges_same_turn_refresh_requests(qt_application,monkeypatch):
    from stats_elevation import _ElevationLayer
    host=QWidget();host.resize(300,200);host.show()
    layer=_ElevationLayer(host)
    updates=[]
    original=layer.update
    monkeypatch.setattr(layer,'update',lambda:updates.append(True) or original())
    for _ in range(30):layer.refresh()
    qt_application.processEvents()
    assert len(updates)<=1
    host.close();host.deleteLater()

def test_collapse_keeps_header_and_content_top_anchors(qt_application,monkeypatch):
    import stats_motion
    from PySide6.QtCore import QPoint
    monkeypatch.setattr(stats_motion,'animations_enabled',lambda:True)
    page=_loaded_page();page.resize(1440,960);page.show();QTest.qWait(350)
    group=next(iter(page.company_dashboard.groups.values()))
    anchor=group.kpi_host.mapTo(group.summary_card,QPoint()).y()
    header=group.name_label.mapTo(group.summary_card,QPoint()).y()
    group.set_summary_collapsed(True)
    animation=group.summary_motion.animation
    try:
        for t in (0,42,84,125,160):
            animation.setCurrentTime(t);qt_application.processEvents()
            assert group.name_label.mapTo(group.summary_card,QPoint()).y()==header
            assert group.kpi_host.mapTo(group.summary_card,QPoint()).y()==anchor
        group.set_summary_collapsed(False);QTest.qWait(300)
        assert group.summary_card.layout().isEnabled()
        assert group.kpi_host.layout().isEnabled()
    finally:
        page.close()

def test_debounce_invalidates_export_without_destroying_stable_charts(qt_application):
    page=_loaded_page();page.network_dashboard.set_snapshot(page.network_snapshot)
    panels=dict(page.network_dashboard.chart_panels)
    page.grain_combo.setCurrentIndex((page.grain_combo.currentIndex()+1)%page.grain_combo.count())
    assert page.snapshot is None and not page.export_button.isEnabled()
    assert page.network_dashboard.chart_panels==panels
    page.close()

def test_equivalent_query_request_keeps_snapshot_and_token(qt_application):
    page=_loaded_page();snapshot=page.snapshot;token=page.token
    page.schedule_query();page.schedule_query()
    assert page.snapshot is snapshot and page.token==token and not page.query_timer.isActive()
    page.close()

def test_multiple_company_motion_updates_share_one_parent_reflow(qt_application,monkeypatch):
    page=_loaded_page();d=page.company_dashboard
    calls=[];original=d.reflow
    monkeypatch.setattr(d,'reflow',lambda *a:calls.append(True) or original(*a))
    for _ in range(5):
        for group in d.groups.values():group._summary_finished()
    qt_application.processEvents()
    assert len(calls)<=1
    page.close()

def test_summary_only_model_preparation_reuses_chart_descriptors(qt_application,monkeypatch):
    import network_model
    page=_loaded_page();prior=page.network_snapshot
    calls=[];original=network_model._chart_result
    monkeypatch.setattr(network_model,'_chart_result',lambda *a,**kw:calls.append(True) or original(*a,**kw))
    page._network_options_changed(replace(page.network_options,vehicle='maximum'))
    deadline=__import__('time').monotonic()+10
    while page.network_workers and __import__('time').monotonic()<deadline:
        QTest.qWait(10)
    assert page.network_snapshot is not None
    assert page.network_snapshot.charts is prior.charts
    assert not calls
    page.close()

def test_failed_query_can_retry_same_filters(qt_application):
    page=_loaded_page()
    page._failed(page.token,'transient preparation failure')
    page.schedule_query()
    assert page.query_timer.isActive()
    page.close()


def test_shared_axis_waits_for_collapse_geometry_to_finish(qt_application, monkeypatch):
    import stats_motion
    page = _loaded_page()
    dashboard = page.company_dashboard
    monkeypatch.setattr(stats_motion, 'animations_enabled', lambda: True)
    page.resize(1440, 960); page.show(); QTest.qWait(350)
    calls = []
    align = dashboard._align_axes
    monkeypatch.setattr(dashboard, '_align_axes', lambda *args: calls.append(True) or align(*args))
    try:
        dashboard.set_summary_collapsed(True)
        for group in dashboard.groups.values():
            assert group.summary_motion.animation is not None
            group.summary_motion.animation.setCurrentTime(80)
        dashboard._axis_budget_signature = None
        dashboard._refresh_axis_budget()
        assert not calls, 'changing tick grids during clipping rebuilds unchanged chart data'
        for group in dashboard.groups.values():
            group.summary_motion.finish()
        for _ in range(3):
            qt_application.processEvents()
        assert calls, 'final natural geometry must still recalculate the shared tick budget'
    finally:
        page.close()
