"""Shared enlarged-chart surface and return behavior, including special clones."""
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from test_stats_charts import app, bucket, panel, result
from test_network_charts import descriptor, make_result, snapshot
from test_city_model import build, r


@pytest.fixture(params=['company', 'network', 'city', 'home'])
def source(request):
    app()
    dashboard = None
    if request.param == 'network':
        from network_charts import NetworkChartPanel
        widget = NetworkChartPanel()
        widget.set_descriptor(descriptor(make_result()), snapshot('company'))
    elif request.param == 'city':
        from city_dashboard import CityDashboard
        dashboard = CityDashboard()
        dashboard.set_snapshot(build([r('trip-time', 'WhiteCollar', 0, 100, 2)]))
        widget = dashboard.panels['trip-time']
    else:
        if request.param == 'home':
            from latest_info_page import TodayTrendPanel
            widget = TodayTrendPanel('当日趋势', allowed_modes=('line',))
        else:
            widget = panel('客流', modes=True, default_mode='trend-bar')
        widget.set_result(result({('a', 'bus'): [bucket(1, 10)],
                                  ('a', 'tram'): [bucket(1, 15)]}), {'a': '甲公司'})
    owner = dashboard if dashboard is not None else widget
    owner.show()
    yield widget
    if widget._fullscreen_dialog:
        widget._fullscreen_dialog.close()
    owner.close()


@pytest.mark.parametrize('maximized', [False, True])
def test_detail_renders_white_under_chart_summary_and_frame(source, maximized):
    clone = source._open_fullscreen()
    dialog = source._fullscreen_dialog
    if not maximized:
        dialog.showNormal()
        dialog.resize(960, 680)
    QTest.qWait(30)
    image = dialog.grab().toImage()
    samples = [QPoint(3, 3), clone.mapTo(dialog, QPoint(3, clone.height() // 2))]
    for canvas in clone.chart_views:
        samples.append(canvas.mapTo(dialog, QPoint(2, 2)))
    if clone.detail_summary.isVisible():
        samples.append(clone.detail_summary.mapTo(dialog, QPoint(0, 0)))
    for point in samples:
        color = image.pixelColor(point)
        assert color.getRgb() == (255, 255, 255, 255)


@pytest.mark.parametrize('close_action', ['shrink', 'keyboard', 'escape', 'system'])
def test_detail_return_closes_and_preserves_all_hidden_selection(source, close_action):
    original_mode = source.mode
    original_result = source.result
    clone = source._open_fullscreen()
    dialog = source._fullscreen_dialog
    QTest.qWait(30)
    assert clone.mode == original_mode
    assert clone._hidden_groups == source._hidden_groups
    # An empty visible selection must survive every return path.
    for key, button in list(clone.legend_buttons.items()):
        if button.isChecked():
            button.click()
    selected_hidden = set(clone._hidden_groups)
    action = clone.fullscreen_button
    assert action.isVisible() and action.isEnabled()
    assert '缩小' in action.text()
    assert '缩小' in action.accessibleName()
    assert action.height() >= 32
    assert action.focusPolicy() & Qt.FocusPolicy.TabFocus
    click_point = action.mapTo(dialog, action.rect().center())
    hit = dialog.childAt(click_point)
    assert hit is action or action.isAncestorOf(hit)
    if close_action == 'shrink':
        QTest.mouseClick(action, Qt.MouseButton.LeftButton)
    elif close_action == 'keyboard':
        action.setFocus()
        QTest.keyClick(action, Qt.Key.Key_Space)
    elif close_action == 'escape':
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
    else:
        dialog.close()
    app().processEvents()
    assert not dialog.isVisible()
    assert source.isVisible()
    assert source._hidden_groups == selected_hidden
    assert source.mode == original_mode
    assert source.result is original_result
    reopened = source._open_fullscreen()
    assert reopened._hidden_groups == selected_hidden
    assert reopened.mode == original_mode


def test_shrink_remains_enabled_in_summary_and_empty_detail():
    widget = panel('客流', modes=True)
    widget.set_result(result({('a', 'bus'): [bucket(1, 10)]}), {'a': '甲公司'})
    clone = widget._open_fullscreen()
    try:
        clone.set_mode('summary')
        assert clone.fullscreen_button.isEnabled()
        clone.set_result(None)
        assert clone.fullscreen_button.isEnabled()
        clone.fullscreen_button.click()
        assert not widget._fullscreen_dialog.isVisible()
    finally:
        widget._fullscreen_dialog.close()
        widget.close()


def test_network_shrink_remains_enabled_when_detail_becomes_unavailable():
    from network_charts import NetworkChartPanel
    app()
    widget = NetworkChartPanel()
    widget.set_descriptor(descriptor(make_result()), snapshot('company'))
    clone = widget._open_fullscreen()
    try:
        clone.set_descriptor(descriptor(clone.result, reason='暂无历史记录'), clone.snapshot)
        assert clone.placeholder.isVisible()
        assert clone.fullscreen_button.isVisible() and clone.fullscreen_button.isEnabled()
        clone.fullscreen_button.click()
        assert not widget._fullscreen_dialog.isVisible()
    finally:
        widget._fullscreen_dialog.close()
        widget.close()
