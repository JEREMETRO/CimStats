from datetime import datetime as D
from decimal import Decimal
import os
import time
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dashboard_model import FilterState
from statistics_model import HistoryStore
from test_statistics_model import row


CURRENT = (D(2024, 1, 8), D(2024, 1, 8, 2))
PREVIOUS = (D(2024, 1, 1), D(2024, 1, 1, 3))


def observations():
    rows = []
    for day, values in ((1, (4, 0, 6)), (8, (10, 20))):
        for hour, amount in enumerate(values):
            stamp = D(2024, 1, day, hour)
            rows += [row('trip-number', 'Student', stamp, amount),
                     row('population', 'Student', stamp, 100 + amount),
                     row('energy-prices', 'electricity', stamp, 50 + amount),
                     row('trip-number', 'Student', stamp, 9999, company='a')]
    rows.append(row('trip-time', 'WhiteCollar', D(2024, 1, 1), 30, 2))
    return rows


def snapshot(comparison=PREVIOUS):
    from city_model import build_city_snapshot
    return build_city_snapshot(HistoryStore(observations(), D(2024, 1, 10)),
        FilterState(('a',), *CURRENT, 'hour', comparison))


def test_city_period_keeps_full_city_scope_and_both_real_windows():
    model = snapshot()
    result = model.charts['trip-number']
    assert model.filters.companies == ()
    assert model.filters.comparison == PREVIOUS
    assert result.current_window == CURRENT and result.comparison_window == PREVIOUS
    assert [b.value for b in result.series[('', '总计')]] == [10, 20]
    assert [b.value for b in result.comparison[('', '总计')]] == [4, 0, 6]
    assert [b.start for b in result.comparison[('', '总计')]] == [D(2024, 1, 1, h) for h in range(3)]
    assert model.kpis['trip-number'].comparison.amount == 200
    assert model.kpis['trip-number'].comparison.available
    assert model.kpis['trip-number'].comparison.tooltip.count('2024-01-01') == 2


def test_city_period_retains_previous_only_categories_and_real_missing_values():
    result = snapshot().charts['trip-time']
    assert [b.value for b in result.series[('', 'WhiteCollar')]] == [None, None]
    assert [b.value for b in result.comparison[('', 'WhiteCollar')]] == [Decimal(15), None, None]
    assert result.comparison[('', 'WhiteCollar')][0].raw[0].value == 30


def test_city_default_drops_period_payload_and_does_not_reuse_period_result():
    model = snapshot(None)
    assert model.filters.comparison is None
    assert all(not result.comparison and result.comparison_window is None
               for result in model.charts.values())
    assert model.charts['trip-number'].series[('', '总计')][0].value == 10


def test_city_period_without_previous_observations_keeps_missing_and_no_kpi_growth():
    model = snapshot((D(2023, 12, 1), D(2023, 12, 1, 2)))
    assert not model.kpis['trip-number'].comparison.available
    result = model.charts['trip-number']
    assert [b.value for b in result.comparison[('', '总计')]] == [None, None]
    assert model.kpis['trip-number'].value == 30


def wait_snapshot(page, comparison):
    from PySide6.QtWidgets import QApplication
    end = time.monotonic() + 8
    while time.monotonic() < end:
        QApplication.instance().processEvents()
        if page.city_snapshot is not None and page.city_snapshot.filters.comparison == comparison:
            return
        time.sleep(.005)
    raise AssertionError('city snapshot did not match active comparison')


def test_city_mode_has_only_default_period_and_preserves_range_and_grain():
    from PySide6.QtWidgets import QApplication
    from statistics_page import StatisticsPage
    from stats_style import initialize_theme
    app = QApplication.instance() or QApplication([])
    initialize_theme(app)
    page = StatisticsPage()
    try:
        page.tab_bar.setCurrentItem('city')
        page.set_session({'history': observations(), 'simulation_time': '2024-01-10 00:00:00',
                          'companies': [{'公司标识': 'a', '公司名称': 'A'}]})
        page.range_preset = 'custom'
        page._custom_window = CURRENT
        page._refresh_range_summary()
        page.grain_combo.setCurrentIndex(page.grain_combo.findData('hour'))
        page.city_mode_control.setCurrentKey('period')
        with pytest.raises(KeyError):
            page.city_mode_control.setCurrentKey('companies')
        assert page.city_mode_control.currentKey() == 'period'
        assert page._fields[0].isHidden() and not page._fields[3].isHidden()
        assert not page.compare_field.isHidden()
        page.compare_combo.setCurrentIndex(page.compare_combo.findData('previous_week'))
        wait_snapshot(page, (D(2024, 1, 1), D(2024, 1, 1, 2)))
        assert page.city_snapshot.filters.start == CURRENT[0]
        assert page.city_snapshot.filters.grain == 'hour'
        page.city_mode_control.setCurrentKey('default')
        wait_snapshot(page, None)
        assert page.compare_field.isHidden()
        assert page.city_snapshot.filters.end == CURRENT[1]
        assert page.city_snapshot.filters.grain == 'hour'
        assert page.analysis_mode == 'default' and page.network_options.mode == 'overall'
    finally:
        page.close()


def test_city_comparison_state_is_independent_of_company_and_network_periods():
    from PySide6.QtWidgets import QApplication
    from statistics_page import StatisticsPage
    app = QApplication.instance() or QApplication([])
    page = StatisticsPage()
    try:
        page.tab_bar.setCurrentItem('city')
        page.set_session({'history': observations(), 'simulation_time': '2024-01-10 00:00:00',
                          'companies': [{'公司标识': 'a', '公司名称': 'A'}]})
        page.range_preset = 'custom'
        page._custom_window = CURRENT
        page._refresh_range_summary()
        page.grain_combo.setCurrentIndex(page.grain_combo.findData('hour'))
        page.city_mode_control.setCurrentKey('period')
        page.compare_combo.setCurrentIndex(page.compare_combo.findData('previous_week'))
        city_window = (D(2024, 1, 1), D(2024, 1, 1, 2))
        wait_snapshot(page, city_window)
        for route in ('company', 'network'):
            page.tab_bar.setCurrentItem(route)
            control = page.analysis_mode_control if route == 'company' else page.network_mode_control
            control.setCurrentKey('period')
            page.compare_combo.setCurrentIndex(page.compare_combo.findData('previous_month'))
            wait_snapshot(page, city_window)
            assert page._route_comparison(route) == (D(2023, 12, 8), D(2023, 12, 8, 2))
            assert page.city_comparison_preset == 'previous_week'
        page.tab_bar.setCurrentItem('city')
        wait_snapshot(page, city_window)
        assert page.compare_combo.currentData() == 'previous_week'
        assert page.city_snapshot.kpis['trip-number'].value == 30
        page.city_mode_control.setCurrentKey('default')
        wait_snapshot(page, None)
        assert page.analysis_mode == 'period' and page.network_options.mode == 'period'
    finally:
        page.close()


def test_city_period_export_has_current_comparison_missing_and_raw_observations(tmp_path):
    from openpyxl import load_workbook
    from stats_exports import export_city_xlsx
    target = tmp_path / 'city.xlsx'
    export_city_xlsx(snapshot(), target, {'mode': 'line', 'curves': ['平均', 'WhiteCollar'], 'hidden': {}})
    book = load_workbook(target, data_only=True)
    try:
        info = dict((r[0], r[1:]) for r in book['筛选'].values)
        assert info['范围'] == ('全市',)
        assert info['对比开始'] == (PREVIOUS[0],)
        assert info['对比结束（不含）'] == (PREVIOUS[1],)
        chart_rows = list(book['城市图表'].values)
        columns = {title: index for index, title in enumerate(chart_rows[0])}
        compared = [r for r in chart_rows[1:] if r[columns['周期']] == '对比期']
        assert any(r[columns['图表']] == '出行量' and r[columns['开始']] == D(2024, 1, 1, 1)
                   and r[columns['值']] == 0 for r in compared)
        assert any(r[columns['图表']] == '出行时间' and r[columns['值']] is None for r in compared)
        raw = list(book['原始观测'].values)[1:]
        assert any(r[0] == 'energy-prices' and r[2] == D(2024, 1, 1) and r[3] == 54 for r in raw)
        assert not any(r[3] == 9999 for r in raw)
    finally:
        book.close()


def test_city_period_mode_share_keeps_two_pies_shared_categories_and_dates():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPointF
    from city_dashboard import CityDashboard
    from city_model import build_city_snapshot
    QApplication.instance() or QApplication([])
    rows = [row(key, 'Student', stamp, amount, 10)
            for stamp, amounts in ((CURRENT[0], (5, 3, 2)), (PREVIOUS[0], (6, 2, 2)))
            for key, amount in zip(('walking', 'public-transport', 'private-motoring'), amounts)]
    model = build_city_snapshot(HistoryStore(rows, D(2024, 1, 10)),
        FilterState((), *CURRENT, 'hour', PREVIOUS))
    widget = CityDashboard()
    try:
        widget.resize(1200, 850)
        widget.set_snapshot(model)
        widget.show()
        panel = widget.panels['city-mode-share']
        panel.grab()
        assert panel.mode == 'pie' and len(panel.chart_views) == 2
        assert [v.data.series[0].faded for v in panel.chart_views] == [False, True]
        assert [v.data.labels for v in panel.chart_views] == [['步行', '公共交通', '私家车']] * 2
        assert '2024-01-08' in panel.company_labels[0].text()
        assert '2024-01-01' in panel.company_labels[1].text()
        assert len(panel.legend_buttons) == 3 and len(panel.series_legend_entries) == 2
        for canvas in panel.chart_views:
            canvas.grab()
            assert canvas._slices and not any('legend' in part for part in canvas._slices)
            part = canvas._slices[0]
            assert canvas._slice_at(QPointF(part['center'].x(), part['center'].y() - part['outer'] + 2)) is not None
        panel._open_fullscreen()
        clone = panel._fullscreen_dialog.city_panel
        assert len(clone.chart_views) == 2 and clone.result is panel.result
        assert [view.data.center_text for view in clone.chart_views] == ['30 %', '20 %']
        assert all(view.data.center_caption == '公共交通分担率' for view in clone.chart_views)
        clone.fullscreen_button.click()
    finally:
        widget.close()


def test_city_period_chart_row_aligns_to_top_beside_taller_paired_pie():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPoint
    from city_dashboard import CityDashboard
    from city_model import build_city_snapshot
    app = QApplication.instance() or QApplication([])
    rows = [row(key, 'Student', stamp, amount, 10)
            for stamp in (CURRENT[0], PREVIOUS[0])
            for key, amount in (('walking', 5), ('public-transport', 3), ('private-motoring', 2))]
    widget = CityDashboard()
    try:
        widget.resize(1200, 850)
        widget.set_snapshot(build_city_snapshot(HistoryStore(rows, D(2024, 1, 10)),
            FilterState((), *CURRENT, 'hour', PREVIOUS)))
        widget.reflow(1200, 850)
        widget.show()
        app.processEvents()
        tops = [widget.panels[key].mapTo(widget.chart_host, QPoint()).y()
                for key in ('population', 'trip-number', 'city-mode-share')]
        assert len(set(tops)) == 1
    finally:
        widget.close()


@pytest.mark.parametrize('transport,expected', [(3, '30 %'), (0, '0 %')])
def test_city_share_center_is_painted_only_in_detail_and_tracks_legend_visibility(transport, expected):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QRect
    from chart_canvas import ChartCanvas
    from city_dashboard import CityDashboard
    from city_model import build_city_snapshot
    app = QApplication.instance() or QApplication([])
    rows = [row(key, 'Student', CURRENT[0], amount, 10) for key, amount in
            (('walking', 8 - transport), ('public-transport', transport), ('private-motoring', 2))]
    dashboard = CityDashboard()
    canvas = ChartCanvas()
    try:
        model = build_city_snapshot(HistoryStore(rows, D(2024, 1, 10)),
                                   FilterState((), *CURRENT, 'hour'))
        dashboard.set_snapshot(model)
        data = dashboard.panels['city-mode-share'].chart_views[0].data
        assert data.center_text == expected and data.center_key == '公共交通'
        assert model.kpis['city-mode-share'].details[1].value == transport * 10
        canvas.resize(650, 450)
        canvas.set_data(data)
        canvas.show()
        app.processEvents()
        ordinary = canvas.grab().toImage()
        center = canvas._slices[0]['center']
        half_width = min(90, round(canvas._slices[0]['inner'] * .6))
        half_height = min(40, round(canvas._slices[0]['inner'] * .3))
        region = QRect(round(center.x()) - half_width, round(center.y()) - half_height,
                       half_width * 2, half_height * 2)
        def ink(image):
            return sum(image.pixelColor(x, y).lightness() < 170
                       for y in range(region.top(), region.bottom() + 1)
                       for x in range(region.left(), region.right() + 1))
        assert ink(ordinary) == 0
        assert not any(part.get('value_label') for part in canvas._slices)
        canvas.detailed = True
        canvas.update()
        detailed = canvas.grab().toImage()
        assert ink(detailed) > 100
        assert [part.get('value_label') for part in canvas._slices] == (
            ['50 %', '30 %', '20 %'] if transport else ['80 %', '20 %'])
        percentages = [part['percent'] for part in canvas._slices]
        canvas.set_hidden({'公共交通'})
        hidden = canvas.grab().toImage()
        assert ink(hidden) == 0
        assert [part['percent'] for part in canvas._slices] == percentages
        assert data.center_text == expected
        assert not any(part.get('value_label') for part in canvas._slices if part['key'] == '公共交通')
    finally:
        canvas.close()
        dashboard.close()


def test_city_period_missing_share_center_keeps_missing_instead_of_zero():
    from PySide6.QtWidgets import QApplication
    from city_dashboard import CityDashboard
    from city_model import build_city_snapshot
    from stats_text import label
    QApplication.instance() or QApplication([])
    rows = [row(key, 'Student', CURRENT[0], amount, 10) for key, amount in
            (('walking', 5), ('public-transport', 3), ('private-motoring', 2))]
    dashboard = CityDashboard()
    try:
        dashboard.set_snapshot(build_city_snapshot(HistoryStore(rows, D(2024, 1, 10)),
                               FilterState((), *CURRENT, 'hour', PREVIOUS)))
        views = dashboard.panels['city-mode-share'].chart_views
        assert [view.data.center_text for view in views] == ['30 %', label('missing')]
        assert all(value is None for value in views[1].data.series[0].values)
    finally:
        dashboard.close()


@pytest.mark.parametrize('embedded_legend', [False, True])
def test_detailed_city_share_labels_use_raw_percentages_and_avoid_tiny_slice_overlap(embedded_legend):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor
    from PySide6.QtCore import QRectF
    from chart_canvas import ChartCanvas, ChartData, Series
    import stats_tokens as tokens
    QApplication.instance() or QApplication([])
    canvas = ChartCanvas(detailed=True)
    try:
        canvas.resize(650, 450) if embedded_legend else canvas.resize(443, 358)
        canvas.set_data(ChartData(kind='donut', labels=['步行', '公共交通', '私家车'], unit='%',
            series=[Series('share', '本期', QColor('#1677ff'),
                           [Decimal('99.97'), Decimal('.01'), Decimal('.01')],
                           keys=['步行', '公共交通', '私家车'])],
            donut_legend=embedded_legend, donut_value_labels=True))
        image = canvas.grab().toImage()
        assert [part['value_label'] for part in canvas._slices] == ['99.97 %', '0.01 %', '0.01 %']
        boxes = [part['value_label_box'] for part in canvas._slices]
        assert all(part['value_label_box'].center().x() > part['center'].x() + part['outer']
                   for part in canvas._slices if part['span'] < 20)
        assert all(QRectF(canvas.rect()).contains(box) for box in boxes)
        assert all(not first.intersects(second) for i, first in enumerate(boxes) for second in boxes[i + 1:])
        assert all(not box.intersects(part['legend']) for box in boxes
                   for part in canvas._slices if 'legend' in part)
        target = QColor(tokens.TEXT_PRIMARY)
        for box in boxes:
            region = box.toAlignedRect()
            assert sum(all(abs(image.pixelColor(x, y).getRgb()[channel] - target.getRgb()[channel]) < 20
                           for channel in range(3))
                       for y in range(region.top(), region.bottom() + 1)
                       for x in range(region.left(), region.right() + 1)) > 15
    finally:
        canvas.close()


def test_city_period_compact_pies_and_dates_fit_inside_400_by_190_card():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPoint
    from city_dashboard import CityChartPanel
    from city_model import build_city_snapshot
    app = QApplication.instance() or QApplication([])
    rows = [row(key, 'Student', stamp, amount, 10)
            for stamp in (CURRENT[0], PREVIOUS[0])
            for key, amount in (('walking', 5), ('public-transport', 3), ('private-motoring', 2))]
    model = build_city_snapshot(HistoryStore(rows, D(2024, 1, 10)),
                               FilterState((), *CURRENT, 'hour', PREVIOUS))
    panel = CityChartPanel('city-mode-share')
    try:
        panel.set_mode('pie')
        panel.set_result(model.pie_result)
        panel.set_compact_height(190)
        panel.resize(400, 190)
        panel.show()
        app.processEvents()
        for view in panel.chart_views:
            view.grab()
            assert view.mapTo(panel, QPoint(0, view.height())).y() <= panel.height() - 8
            assert view._slices
            assert not any(part.get('value_label') for part in view._slices)
    finally:
        panel.close()


def test_city_period_cards_share_height_and_regular_width_pies_are_side_by_side():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPoint
    from city_dashboard import CityDashboard
    from city_model import build_city_snapshot
    app = QApplication.instance() or QApplication([])
    rows = [row(key, 'Student', stamp, amount, 10)
            for stamp in (CURRENT[0], PREVIOUS[0])
            for key, amount in (('walking', 5), ('public-transport', 3), ('private-motoring', 2))]
    widget = CityDashboard()
    try:
        widget.resize(900, 1100)
        widget.set_snapshot(build_city_snapshot(HistoryStore(rows, D(2024, 1, 10)),
            FilterState((), *CURRENT, 'hour', PREVIOUS)))
        widget.reflow(900, 700)
        widget.show()
        app.processEvents()
        widget.reflow(900, 700)
        app.processEvents()
        assert len({panel.height() for panel in widget.panels.values()}) == 1
        panel = widget.panels['city-mode-share']
        positions = [view.mapTo(panel, QPoint()) for view in panel.chart_views]
        assert positions[0].y() == positions[1].y() and positions[0].x() < positions[1].x()
        assert min(view.height() for view in panel.chart_views) >= 140
        diameters = []
        for view in panel.chart_views:
            view.grab()
            diameters.append(round(view._slices[0]['outer'] * 2))
        assert min(diameters) >= 140 and len(set(diameters)) == 1
    finally:
        widget.close()
