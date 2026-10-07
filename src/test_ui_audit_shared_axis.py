from stats_charts import nice_axis


def test_shared_axis_budget_follows_smallest_canvas_and_resizing(qt_application):
    from chart_canvas import ChartCanvas
    from stats_charts import shared_axis_budget
    small, large = ChartCanvas(), ChartCanvas()
    small.resize(228, 140)
    large.resize(960, 540)
    panels = [type('Panel', (), {'chart_views': [small, large]})()]
    budget = shared_axis_budget(panels)
    assert budget == small.axis_tick_budget() < large.axis_tick_budget()
    axis = nice_axis([559591], max_ticks=budget)
    assert axis.upper * axis.scale >= 559591
    assert (axis.upper - axis.lower) / axis.step + 1 <= budget
    small.resize(960, 540)
    assert shared_axis_budget(panels) > budget
    small.deleteLater(); large.deleteLater()

def test_shared_axis_uses_same_tight_tick_grid_as_canvas():
    axis=nice_axis([-7,3])
    assert axis.upper-axis.lower<=12
    assert axis.lower<=-7 and axis.upper>=3 and axis.lower<0<axis.upper

def test_period_stacked_shared_axis_covers_negative_totals(qt_application):
    import copy
    from dataclasses import replace
    from network_model import build_network_snapshot, NetworkOptions
    from test_stats_fluent_page import _loaded_page
    page=_loaded_page()
    try:
        snapshot=copy.deepcopy(page.snapshot)
        network=build_network_snapshot(snapshot,NetworkOptions(mode='period'),page._names())
        for descriptor in network.charts:
            if descriptor.key in ('transport-by-type','transport-by-group','trip-types'):
                for series in descriptor.result.series.values():
                    for b in series:
                        if b.value is not None:b.value=-abs(b.value)-100
        page.network_dashboard.set_snapshot(network)
        panels=[p for (owner,key),p in page.network_dashboard.chart_panels.items() if key=='transport-by-type']
        assert panels
        assert all(p._axis_override is not None and p._axis_override.lower<0 for p in panels)
    finally:
        page.close()
