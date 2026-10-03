"""Latest-information behavior and capacity contracts.

Prepared while the Qt execution slot was held. Execution requires the released
offscreen slot, existing Qt fixture and isolated temporary settings.
All fixtures consume package A's actual dataclasses, never a parallel model.
"""
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

import pytest


METRIC_KEYS = (
    'line-count', 'fleet', 'drive-minutes', 'turnover', 'weekly-income',
    'weekly-expense', 'profit', 'interval', 'speed', 'passengers-per-run',
    'passengers-per-km', 'public-transport-share', 'transfer-coefficient',
)
METRIC_TITLES = (
    '线路总数', '车辆总数', '行车总时间', '车辆周转率', '每周收入',
    '每周支出', '净利润', '平均间隔', '平均核定速度', '平均单班人次',
    '平均车公里人次', '公共交通分担率', '平均换乘系数',
)
MODES = ('公交', '有轨电车', '无轨电车', '地铁', '单轨列车', '水上巴士')
HIGHLIGHTS = ('当日最大客流线路', '当日最小客流线路',
              '当日最多班次线路', '当日最少班次线路')
CORE_METRIC_KEYS = ('line-count', 'fleet', 'weekly-income', 'profit')


def snapshot():
    from latest_info_model import (InfoValue, LatestInfoSnapshot, LineHighlight,
                                   LineSummary, ModeCount)
    from statistics_model import Bucket, METRICS, Query, Result
    now = datetime(2024, 6, 10, 10, 30, 13)
    start = now.replace(hour=0, minute=0)
    query = Query('transport-by-type', ('company-a',), None, start, now, 'hour')
    buckets = [
        Bucket(start, start + timedelta(hours=1), Decimal(0), True, False,
               start, 0, None, 1),
        Bucket(start + timedelta(hours=1), start + timedelta(hours=2), None,
               False, False, None, None, None, 0),
        Bucket(start + timedelta(hours=2), start + timedelta(hours=3),
               Decimal(12), True, False, start + timedelta(hours=2), 12, None, 1),
    ]
    trend = Result(query, METRICS[query.metric], {('company-a', 'bus'): buckets},
                   {}, (start, now), None)
    lines = tuple(LineSummary(
        f'line-{i}', f'{i + 1:02d}路·东部交通枢纽至大学城及滨江科技园区环线',
        MODES[i % 6], 'company-a', 100 - i, 20 - i,
        Decimal('4.25'), Decimal('1.75')) for i in range(10))
    metrics = tuple(InfoValue(key, title, Decimal(i + 1),
                             '%' if key == 'public-transport-share' else '',
                             '全市模拟当日' if key == 'public-transport-share'
                             else '所选公司模拟当日')
                    for i, (key, title) in enumerate(zip(METRIC_KEYS, METRIC_TITLES)))
    return LatestInfoSnapshot(
        session_key='session-a', company_id='', mode='综合', city_name='容量测试城市',
        simulation_time=now, population=Decimal(123456), save_name='测试存档.save',
        companies=(('company-a', '同名公司'), ('company-b', '同名公司')),
        modes=MODES, metrics=metrics,
        highlights=tuple(LineHighlight(title, lines[0 if i % 2 == 0 else 9])
                         for i, title in enumerate(HIGHLIGHTS)),
        lines=lines, passenger_top10=lines,
        passenger_modes=tuple(ModeCount(mode, value)
                              for mode, value in zip(MODES, (194, 192, 190, 188, 96, 95))),
        departure_modes=tuple(ModeCount(mode, value)
                              for mode, value in zip(MODES, (34, 32, 30, 28, 16, 15))),
        total_departures=155, trend=trend, scope_text='全部公司 · 综合 · 模拟当日', company_trend=trend,
    )


def session(key='session-a', city='容量测试城市'):
    return dict(save_key=key, save_path='测试存档.save',
                simulation_time='2024-06-10 10:30:13',
                metadata={'地图名称': city, '地图名称来源': 'runtime:m_cityName', '人口': '123456'},
                companies=[{'公司标识': 'company-a', '公司名称': '同名公司'},
                           {'公司标识': 'company-b', '公司名称': '同名公司'}],
                lines=[{'运输制式': mode} for mode in MODES])


@pytest.fixture
def page(qt_application, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    assert qt_application.platformName() == 'offscreen'
    monkeypatch.setenv('CIM2_REDUCED_MOTION', '1')
    from qfluentwidgets import Theme, setTheme, setThemeColor
    from stats_tokens import ACCENT
    from stats_style import initialize_theme
    setTheme(Theme.LIGHT, save=False)
    setThemeColor(ACCENT, save=False)
    initialize_theme(qt_application)
    from latest_info_page import LatestInfoPage
    settings = QSettings(str(tmp_path / 'latest-info-test.ini'), QSettings.Format.IniFormat)
    settings.setValue('ui/reduce_motion', True)
    widget = LatestInfoPage(settings=settings)
    widget.resize(1204, 852)
    widget.show()
    qt_application.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()
    qt_application.processEvents()


def child(page, name):
    from PySide6.QtWidgets import QWidget
    result = page.findChild(QWidget, name)
    assert result is not None, f'Missing visible content: {name}'
    return result


def inside(container, widget):
    from PySide6.QtCore import QPoint, QRect
    return container.rect().contains(QRect(widget.mapTo(container, QPoint()), widget.size()))


def label_texts(widget):
    from PySide6.QtWidgets import QLabel
    return [label.text() for label in widget.findChildren(QLabel)]


def bounds(widget, parent):
    from PySide6.QtCore import QPoint, QRect
    return QRect(widget.mapTo(parent, QPoint()), widget.size())


def test_business_modules_cover_each_metric_once_and_distinguish_numeric_roles(page, qt_application):
    from PySide6.QtWidgets import QFrame
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    expected = {
        'network': ('line-count', 'fleet'),
        'finance': ('weekly-income', 'weekly-expense', 'profit'),
        'operations': ('drive-minutes', 'turnover', 'interval', 'speed'),
        'travel': ('passengers-per-run', 'passengers-per-km', 'public-transport-share', 'transfer-coefficient'),
    }
    found = []
    for group, keys in expected.items():
        module = child(page, f'metricModule-{group}')
        assert module.isVisible() and inside(page.main, module)
        assert [widget.key for widget in module.findChildren(QFrame) if hasattr(widget, 'key')] == list(keys)
        for key in keys:
            metric = child(page, f'metric-{key}')
            assert metric.parent() is module and metric.isVisible()
            value = metric.value
            assert value.font().bold() == (key in CORE_METRIC_KEYS)
            assert value.font().pixelSize() == (28 if group == 'network' else 24 if key in CORE_METRIC_KEYS else 20)
            found.append(key)
    assert len(found) == len(set(found)) == 13 and set(found) == set(METRIC_KEYS)


def test_realistic_numeric_values_are_complete_and_units_stay_next_to_them(page, qt_application):
    data = snapshot()
    amounts = {'line-count': (73, '条'), 'fleet': (605, '辆'),
               'weekly-income': (Decimal('5336336.88'), '货币'),
               'weekly-expense': (Decimal('999888.6'), '货币'),
               'profit': (Decimal('4336448.28'), '货币'),
               'drive-minutes': (433410, '分钟'), 'turnover': (Decimal('11.15'), '班/辆/天'),
               'interval': (Decimal('15.59'), '分钟'), 'speed': (Decimal('15.67'), 'km/h'),
               'passengers-per-run': (Decimal('204.07'), '人次/班'),
               'passengers-per-km': (Decimal('12.28'), '人次/车公里'),
               'public-transport-share': (Decimal('31.16'), '%'), 'transfer-coefficient': (Decimal('2.79'), '倍')}
    page.set_session(session())
    page.set_snapshot(replace(data, metrics=tuple(replace(item, value=amounts[item.key][0], unit=amounts[item.key][1])
                                                 for item in data.metrics)))
    qt_application.processEvents()
    for metric in page.metric_cards.values():
        assert inside(metric, metric.value) and inside(metric, metric.unit)
        assert metric.value.contentsRect().width() >= metric.value.fontMetrics().horizontalAdvance(metric.value.text())
        assert metric.unit.contentsRect().width() >= metric.unit.fontMetrics().horizontalAdvance(metric.unit.text())
        assert 3 <= metric.unit.x() - metric.value.x() - metric.value.fontMetrics().horizontalAdvance(metric.value.text()) <= 6
    assert page.scroll.verticalScrollBar().maximum() == 0


def test_same_name_company_legend_is_unique_and_keeps_full_identity(page, qt_application):
    data = snapshot()
    source = next(iter(data.company_trend.series.values()))
    result = replace(data.company_trend, series={(identity, '总计'): source for identity, _ in data.companies},
                     query=replace(data.company_trend.query, companies=tuple(key for key, _ in data.companies)))
    page.set_session(session())
    page.set_snapshot(replace(data, company_trend=result))
    qt_application.processEvents()
    buttons = page.trend.legend_buttons
    assert set(buttons) == {'company-a', 'company-b'}
    assert len({button.text() for button in buttons.values()}) == 2
    for key, button in buttons.items():
        assert key in button.toolTip() and '同名公司' in button.toolTip()


def test_async_snapshot_and_scope_reset_reflow_long_values_without_resize(page, qt_application):
    data = snapshot()
    size = page.size()
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    normal_height = page.modules_host.height()
    long_data = replace(data, metrics=tuple(replace(item, value=Decimal('1234567890' * 5 + '.12'), unit='货币')
                                           if item.key in ('weekly-income', 'profit') else item for item in data.metrics))
    page.set_snapshot(long_data)
    qt_application.processEvents()
    assert page.size() == size and page.modules_host.height() > normal_height
    for key in ('weekly-income', 'profit'):
        metric = page.metric_cards[key]
        assert inside(metric, metric.value) and inside(metric, metric.unit)
        assert metric.value.contentsRect().width() >= metric.value.fontMetrics().horizontalAdvance(metric.value.text())
        assert metric.value.font().pixelSize() == 24
    page.company_combo.setCurrentIndex(page.company_combo.findData('company-b'))
    qt_application.processEvents()
    assert page.modules_host.height() == normal_height
    page.set_snapshot(replace(data, company_id='company-b'))
    qt_application.processEvents()
    assert page.size() == size and page.modules_host.height() == normal_height
    assert child(page, 'highlightSectionTitle').isVisible()


def test_business_symbols_and_field_spacing_keep_the_same_reading_axis(page, qt_application):
    from qfluentwidgets import IconWidget
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    paddings = []
    for module in page.metric_modules.values():
        icons = module.findChildren(IconWidget)
        assert len(icons) == 1 and icons[0].isVisible() and inside(module, icons[0])
        margins = module.layout().contentsMargins()
        paddings.append((margins.left(), margins.top(), margins.right(), margins.bottom()))
        fields = [metric for metric in page.metric_cards.values() if metric.parent() is module]
        assert len({metric.x() for metric in fields}) == 1
        assert all(right.y() - left.geometry().bottom() - 1 >= 4 for left, right in zip(fields, fields[1:]))
    assert len(set(paddings)) == 1 and all(left == top == right == bottom for left, top, right, bottom in paddings)


def test_four_highlight_surfaces_use_two_consistent_extreme_color_families(page, qt_application):
    import stats_tokens as tokens
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    colors = []
    for index, card in enumerate(page.highlights):
        marker = child(card, f'highlight-marker-{index}')
        assert marker.isVisible() and inside(card, marker)
        assert marker.height() >= card.height() / 2
        assert tokens.CARD_BG in card.styleSheet()
        colors.append(marker.property('extremeColor'))
    assert colors[0] == colors[2] and colors[1] == colors[3] and colors[0] != colors[1]


def test_highlights_separate_primary_value_from_three_auxiliary_fields(page, qt_application):
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    primary_y, auxiliary_y = [], []
    for index, card in enumerate(page.highlights):
        margins = card.layout().contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (12, 8, 12, 8)
        assert card.marker.property('extremeColor') == ('#D13438' if index % 2 == 0 else '#0F9D58')
        assert card.role_label.text() == ('客流最多', '客流最少', '班次最多', '班次最少')[index]
        primary = 0 if index < 2 else 1
        assert card.primary_value is card.values[primary]
        assert card.primary_value.font().pixelSize() == 20
        assert len(card.auxiliary_indices) == 3 and primary not in card.auxiliary_indices
        assert len(card.values) == 4 and all(inside(card, value) for value in card.values)
        primary_y.append(card.primary_value.y())
        auxiliary_y.append(card.values[card.auxiliary_indices[0]].y())
    assert len(set(primary_y)) == len(set(auxiliary_y)) == 1


def test_trend_expands_plot_width_without_changing_shared_rendering(page, qt_application):
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    assert page.trend.width() >= 368
    assert abs(page.passengers.width() - page.departures.width()) <= 1
    canvas = page.trend.chart_views[0]
    canvas.grab()
    assert canvas.plot_rect().width() >= 270


def test_wrapped_line_identity_keeps_all_highlight_primary_and_auxiliary_anchors(page, qt_application):
    from PySide6.QtCore import QRect, Qt
    data = snapshot()
    long_line = replace(data.lines[0], name='市中心专用运营环线')
    data = replace(data, lines=(long_line, *data.lines[1:]),
                   passenger_top10=(long_line, *data.passenger_top10[1:]),
                   highlights=tuple(replace(item, line=long_line) if item.line.key == long_line.key else item
                                    for item in data.highlights))
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    for card in page.highlights:
        name = card.name
        required = name.fontMetrics().boundingRect(QRect(0, 0, name.contentsRect().width(), 10000),
                                                  Qt.TextFlag.TextWordWrap, name.text())
        assert name.isVisible() and required.width() <= name.contentsRect().width()
        assert required.height() <= name.contentsRect().height()
        assert name.font().pixelSize() == 15 and card._line_key == data.highlights[page.highlights.index(card)].line.key
    assert len({card.primary_value.y() for card in page.highlights}) == 1
    assert len({card.values[card.auxiliary_indices[0]].y() for card in page.highlights}) == 1


def test_city_hero_leads_main_area_with_distinct_simulation_context(page, qt_application):
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    hero = child(page, 'cityCard')
    rect = bounds(hero, page)
    cards = [bounds(module, page) for module in page.metric_modules.values()]
    assert abs(rect.left() - min(card.left() for card in cards)) <= 2
    assert abs(rect.right() - max(card.right() for card in cards)) <= 2
    assert rect.bottom() < min(card.top() for card in cards)
    assert rect.right() < bounds(child(page, 'alertHost'), page).left()
    assert child(hero, 'cityName').text() == '容量测试城市'
    assert child(hero, 'cityName').font().pixelSize() in range(28, 33)
    assert child(hero, 'citySimulationTime').text() == '10:30:13'
    assert all(part in child(hero, 'citySimulationDate').text() for part in ('2024-06-10', '周一'))
    assert child(hero, 'cityPopulation').text() == '123,456'
    assert child(hero, 'citySaveName').text() == '测试存档.save'
    fields = [child(hero, name) for name in
              ('cityName', 'citySimulationDate', 'citySimulationTime', 'cityPopulation', 'citySaveName')]
    rectangles = []
    for field in fields:
        assert field.isVisible() and inside(hero, field)
        geometry = bounds(field, hero)
        assert all(not geometry.intersects(previous) for previous in rectangles)
        rectangles.append(geometry)


@pytest.mark.parametrize('metadata,expected', [
    ({'save_path': r'C:\存档\真实城市.save', 'save_name': '旧显示名.save', 'tag': '城市_运行时'}, '真实城市.save'),
    ({'save_path': 'D:/存档/真正城市.save', 'save_name': '旧显示名.save', 'tag': '城市_运行时'}, '真正城市.save'),
    ({'save_name': '明确存档.save', 'tag': '城市_运行时'}, '明确存档.save'),
    ({'tag': '城市_运行时'}, '未提供存档名称'),
])
def test_session_hero_save_name_uses_actual_path_without_runtime_tag(page, metadata, expected):
    data = session()
    data.pop('save_path')
    data.update(metadata)
    page.set_session(data)
    assert child(page, 'citySaveName').text() == expected
    assert not child(page, 'reportAction').isEnabled()


def test_hero_preserves_seconds_separate_clock_and_population_unit(page, qt_application):
    page.set_session(session())
    page.set_snapshot(snapshot())
    clock = child(page, 'citySimulationTime')
    date = child(page, 'citySimulationDate')
    assert clock.text() == '10:30:13' and clock.font().pixelSize() == 21
    assert date.text() == '2024-06-10  周一' and date.font().pixelSize() == 14
    assert all(part in clock.toolTip() for part in ('2024-06-10', '周一', '10:30:13'))
    assert all(part in date.toolTip() for part in ('2024-06-10', '周一', '10:30:13'))
    assert child(page, 'cityPopulation').text() == '123,456'
    assert child(page, 'cityPopulationUnit').text() == '人'
    assert child(page, 'cityPopulationUnit').font().pixelSize() == 12
    qt_application.processEvents()
    population = child(page, 'cityPopulation')
    unit = child(page, 'cityPopulationUnit')
    assert 4 <= unit.x() - population.x() - population.fontMetrics().horizontalAdvance(population.text()) <= 8


def test_business_modules_align_and_finance_keeps_income_expense_profit_together(page, qt_application):
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    modules = [bounds(widget, page) for widget in page.metric_modules.values()]
    assert len({rect.top() for rect in modules}) == 1
    assert len({rect.bottom() for rect in modules}) == 1
    assert all(left.right() < right.left() for left, right in zip(modules, modules[1:]))
    finance = page.metric_modules['finance']
    fields = [child(page, f'metric-{key}') for key in ('weekly-income', 'weekly-expense', 'profit')]
    assert all(field.parent() is finance for field in fields)
    assert all(left.geometry().bottom() < right.geometry().top() for left, right in zip(fields, fields[1:]))


def test_three_charts_use_full_width_below_upper_only_alerts(page, qt_application):
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    trend, top, departures = [bounds(child(page, name), page) for name in
                             ('todayTrend', 'passengerRanking', 'departureStructure')]
    assert len({trend.top(), top.top(), departures.top()}) == 1
    assert (trend.width(), top.width(), departures.width()) == (384, 400, 400)
    assert all(rect.height() == 304 for rect in (trend, top, departures))
    alerts = bounds(child(page, 'alertHost'), page)
    assert alerts.height() == 494 and alerts.bottom() < trend.top()
    assert departures.right() == bounds(page.board, page).right()


def test_upper_budget_preserves_module_axes_and_highlight_hierarchy(page, qt_application):
    from qfluentwidgets import IconWidget
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    assert inside(page, page.main)
    assert page.scope_host.height() == 32
    assert child(page, 'coreSectionTitle').text() == '运营概况'
    auxiliary = [child(page, f'metric-{key}') for key in METRIC_KEYS if key not in CORE_METRIC_KEYS]
    for widget in auxiliary:
        assert not widget.findChildren(IconWidget)
        assert widget.title.x() == widget.value.x()
        assert widget.height() >= widget.title.fontMetrics().height() + widget.value.fontMetrics().height()
    for i, highlight in enumerate(page.highlights):
        assert inside(page.highlights_group, highlight)
        assert snapshot().highlights[i].line.mode in highlight.name.text()
        assert [number.font().pixelSize() for number in highlight.values] == ([20, 13, 13, 13] if i < 2 else [13, 20, 13, 13])
    assert '全市' in child(page, 'metric-public-transport-share').toolTip()


def test_user_removes_explanation_badges_routes_and_merges_metric_surfaces(page, qt_application):
    from PySide6.QtWidgets import QWidget, QPushButton
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    assert not any(button.text() == '说明' for button in page.findChildren(QPushButton))
    assert not any(widget.objectName().endswith('-scope') for widget in page.findChildren(QWidget))
    assert child(page, 'metricModule-network').isAncestorOf(child(page, 'metric-line-count'))
    assert child(page, 'metricModule-operations').isAncestorOf(child(page, 'metric-speed'))
    assert child(page, 'highlightsGroup').isAncestorOf(child(page, 'highlight-0'))
    for highlight in page.highlights:
        assert '枢纽' not in highlight.name.text() and '滨江' not in highlight.name.text()
    page.passengers.ranking_button.click()
    assert all('枢纽' not in row.name.text() for row in page.passengers.visible_ranking_rows())


def test_highlight_all_four_field_and_unit_columns_are_actually_readable(page, qt_application):
    from PySide6.QtWidgets import QLabel
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    titles = ('客流', '班次', '单班人次', '车公里人次')
    units = ('人次', '班', '人次/班', '人次/车公里')
    for highlight in page.highlights:
        for title, field in zip(titles, highlight.field_labels):
            assert field.text().startswith(title)
        assert tuple(unit.text() for unit in highlight.units) == units
        for widget in (*highlight.field_labels, *highlight.units):
            text = widget.text()
            assert widget.isVisible() and inside(highlight, widget)
            assert widget.contentsRect().width() >= widget.fontMetrics().horizontalAdvance(text), (text, widget.width())


def test_highlight_long_auxiliary_values_keep_each_unit_adjacent_without_cross_row_widths(page, qt_application):
    from PySide6.QtCore import QPoint
    data = snapshot()
    line = replace(data.lines[-1], passengers=Decimal('9876543211'), departures=2,
                   passengers_per_departure=Decimal('4938271605.5'),
                   passengers_per_vehicle_km=Decimal('493827160.55'))
    data = replace(data, lines=(*data.lines[:-1], line),
                   highlights=tuple(replace(item, line=line) if item.line.key == line.key else item
                                    for item in data.highlights))
    page.resize(1348, 860)
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    for card in page.highlights:
        for index in card.auxiliary_indices:
            value, unit = card.values[index], card.units[index]
            value_origin = value.mapTo(card, QPoint())
            unit_origin = unit.mapTo(card, QPoint())
            ink_right = value_origin.x() + value.fontMetrics().horizontalAdvance(value.text())
            assert 0 <= unit_origin.x() - ink_right <= 8
            assert inside(card, value) and inside(card, unit), (
                card.objectName(), index, card.size().toTuple(), card.minimumSizeHint().toTuple(),
                value.text(), value_origin.toTuple(), value.size().toTuple(),
                unit.text(), unit_origin.toTuple(), unit.size().toTuple())
            assert value.contentsRect().width() >= value.fontMetrics().horizontalAdvance(value.text())
            assert unit.contentsRect().width() >= unit.fontMetrics().horizontalAdvance(unit.text())
            assert value.font().pixelSize() == 13 and unit.font().pixelSize() == 12


def test_trend_only_exposes_shared_line_renderer(page):
    from stats_charts import ChartPanel
    assert isinstance(page.trend, ChartPanel)
    assert page.trend._allowed_modes == ('line',)
    assert page.trend.mode == 'line' and page.trend.mode_selector is None
    assert not hasattr(page.trend, 'metric_menu_button')


@pytest.mark.parametrize('company_ids', [('company-a', 'company-b'), ('company-a',)])
def test_company_trend_has_one_true_fluent_line_per_selected_company(page, qt_application, company_ids):
    data = snapshot()
    base = data.trend.series[('company-a', 'bus')]
    buckets = [replace(bucket, value=Decimal(i), observed=True) for i, bucket in enumerate(base)]
    result = replace(data.trend, series={(company, '总计'): buckets for company in company_ids},
                     query=replace(data.trend.query, companies=company_ids))
    page.set_session(session())
    if len(company_ids) == 1:
        page.company_combo.setCurrentIndex(page.company_combo.findData(company_ids[0]))
    page.set_snapshot(replace(data, company_id=company_ids[0] if len(company_ids) == 1 else '', company_trend=result))
    qt_application.processEvents()
    assert page.trend.result is result
    assert len(page.trend.chart_views) == 1
    data = page.trend.chart_views[0].data
    assert data.kind == 'line'
    assert len(data.series) == len(company_ids)
    if len(company_ids) > 1:
        assert [item.key for item in data.series] == list(company_ids)
    assert all(not item.dashed and not item.faded for item in data.series)


def test_untrusted_metadata_filename_never_becomes_city_and_snapshot_trace_is_available(page):
    data = session()
    data['metadata'] = {'地图名称': 'quicksave.12345', '场景名称': 'quicksave.12345'}
    page.set_session(data)
    assert child(page, 'cityName').text() == '未提供城市名称'
    snap = replace(snapshot(), city_name='Eixeia', city_source='save-header:m_originalMapName',
                   city_raw_reference=':273831404:Eixeia1.1', city_raw_name='Eixeia1.1',
                   city_internal_id='273831404', city_name_reason='可靠原始来源')
    page.set_snapshot(snap)
    assert child(page, 'cityName').text() == 'Eixeia'
    assert ':273831404:Eixeia1.1' in child(page, 'cityName').toolTip()


def test_home_keeps_all_metrics_highlights_and_chart_sections(page):
    page.set_session(session())
    page.set_snapshot(snapshot())
    assert child(page, 'latestTitle').text() == '最新信息'
    for key, title in zip(METRIC_KEYS, METRIC_TITLES):
        card = child(page, f'metric-{key}')
        assert card.isVisible() and title in label_texts(card)
    for i, title in enumerate(HIGHLIGHTS):
        card = child(page, f'highlight-{i}')
        assert card.isVisible() and card.role_label.text() == ('客流最多', '客流最少', '班次最多', '班次最少')[i]
        assert all(field.text().startswith(text) for text, field in zip(
                   ('客流', '班次', '单班人次', '车公里人次'), card.field_labels))
    assert all(child(page, name).isVisible() for name in
               ('todayTrend', 'passengerRanking', 'departureStructure', 'alertHost'))


def test_top10_and_all_modes_are_visible(page, qt_application):
    from latest_info_charts import short_line_name
    data = snapshot()
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    top = child(page, 'passengerRanking')
    top.ranking_button.click()
    qt_application.processEvents()
    rows = [child(top, f'ranking-row-{i}') for i in range(10)]
    assert all(row.isVisible() and inside(top, row) for row in rows)
    for row, line in zip(rows, data.passenger_top10):
        assert row.name.text() == f'{line.mode} {short_line_name(line.name)}'
        assert row.line.key == line.key and row.line.name == line.name
        assert row.number.text() == f'{line.passengers} 人次'
    modes = child(page, 'departureStructure')
    for i, entry in enumerate(data.departure_modes):
        row = child(modes, f'mode-row-{i}')
        assert row.isVisible() and inside(modes, row)
        assert entry.mode in label_texts(row) and row.number.text() == f'{entry.value} 班'
    assert child(modes, 'departureTotal').text() == '155 班'
    # Hand-checked fixture: 34 / 155 = 21.9%; all counts sum to 155.
    assert '21.9%' in label_texts(child(modes, 'mode-row-0'))


def test_ranking_values_and_mode_percentages_fit_their_visible_rows(page, qt_application):
    from PySide6.QtWidgets import QLabel
    data = snapshot()
    page.set_session(session())
    page.set_snapshot(data)
    page.passengers.ranking_button.click()
    qt_application.processEvents()
    for i, line in enumerate(data.passenger_top10):
        row = child(page, f'ranking-row-{i}')
        value = row.number
        assert inside(row, value), (i, value.geometry(), row.size())
        assert value.contentsRect().width() >= value.fontMetrics().horizontalAdvance(value.text())
    for i, entry in enumerate(data.departure_modes):
        row = child(page, f'mode-row-{i}')
        for value in row.findChildren(QLabel):
            if value.text() in (f'{entry.value} 班', f'{Decimal(entry.value) / 155 * 100:.1f}%'):
                assert inside(row, value), (entry.mode, value.text(), value.geometry(), row.size())
                assert value.contentsRect().width() >= value.fontMetrics().horizontalAdvance(value.text())
    assert all(row.height() >= row.name.fontMetrics().height() for row in page.passengers.visible_ranking_rows())


def test_large_departure_total_stays_clear_of_donut_without_smaller_font(page, qt_application):
    data = snapshot()
    large = replace(data,
                    departure_modes=tuple(replace(item, value=item.value * 1000) for item in data.departure_modes),
                    total_departures=155000,
                    lines=tuple(replace(line, departures=line.departures * 1000) for line in data.lines))
    page.set_session(session())
    page.set_snapshot(large)
    qt_application.processEvents()
    total = page.departures.ring.center_total
    assert total.isVisible() and total.text() == '155,000' and total.font().pixelSize() == 21
    assert page.departures.ring.center_caption.text() == '班'
    assert total.contentsRect().width() >= total.fontMetrics().horizontalAdvance(total.text())


def test_departure_donut_is_left_of_complete_six_mode_list(page, qt_application):
    from PySide6.QtWidgets import QLabel
    data = snapshot()
    page.set_session(session())
    page.set_snapshot(data)
    qt_application.processEvents()
    panel = child(page, 'departureStructure')
    ring = panel.ring
    ring_rect = bounds(ring, panel)
    for i, entry in enumerate(data.departure_modes):
        row = child(panel, f'mode-row-{i}')
        assert ring_rect.right() < bounds(row, panel).left()
        assert row.isVisible() and inside(panel, row)
        name = next(widget for widget in row.findChildren(QLabel) if widget.text() == entry.mode)
        assert name.contentsRect().width() >= name.fontMetrics().horizontalAdvance(entry.mode)
        assert row.number.text() == f'{entry.value} 班'
        assert f'{Decimal(entry.value) / 155 * 100:.1f}%' in label_texts(row)


def test_donut_nonpositive_and_missing_modes_do_not_create_clickable_sectors(page, qt_application):
    from PySide6.QtCore import QPointF, QEvent, Qt
    from PySide6.QtGui import QMouseEvent
    data = snapshot()
    counts = tuple(replace(item, value=10 if item.mode == '地铁' else None if item.mode == '公交' else 0)
                   for item in data.departure_modes)
    page.set_session(session())
    page.set_snapshot(replace(data, departure_modes=counts, total_departures=10))
    qt_application.processEvents()
    ring = page.departures.ring
    assert ring.sectors() == []  # A missing category prevents a fake complete 100% ring.
    counts = tuple(replace(item, value=0 if item.mode == '公交' else item.value) for item in counts)
    page.set_snapshot(replace(data, departure_modes=counts, total_departures=10))
    qt_application.processEvents()
    # Send a local event directly; no QtTest global mouse/focus operations.
    point = QPointF(ring.width() / 2, 8)
    event = QMouseEvent(QEvent.Type.MouseButtonPress, point, point,
                       Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    qt_application.sendEvent(ring, event)
    assert child(page, 'departureRankingMode').currentData() == '地铁'
    child(page, 'departureReturn').click()
    assert child(page, 'mode-row-0').number.text() == '0 班'
    assert child(page, 'mode-row-1').number.text() == '0 班'


@pytest.mark.parametrize('view', ['structure', 'ranking', 'line_share'])
def test_native_font_size_hint_budget_keeps_all_three_cards_in_860px_viewport(page, qt_application, monkeypatch, view):
    from PySide6.QtCore import QPoint, QRect, QSize
    # Measured native Microsoft YaHei UI size hints, not offscreen font metrics.
    # The real 1440x960 DWM frame has a 1436x900 client and 1204x860 page viewport.
    for module in page.metric_modules.values():
        original = module.minimumSizeHint
        monkeypatch.setattr(module, 'minimumSizeHint', lambda original=original: QSize(original().width(), 233))
    for highlight in page.highlights:
        original = highlight.minimumSizeHint
        monkeypatch.setattr(highlight, 'minimumSizeHint', lambda original=original: QSize(original().width(), 132))
    page.highlight_section_title.setFixedHeight(19)
    page.resize(1204, 860)
    page.set_session(session())
    page.set_snapshot(snapshot())
    for chart in (page.passengers, page.departures):
        getattr(chart, 'show_' + view)()
    qt_application.processEvents()
    viewport = page.scroll.viewport()
    assert viewport.size() == QSize(1204, 860)
    assert page.scroll.verticalScrollBar().maximum() == 0
    assert page.scroll.horizontalScrollBar().maximum() == 0
    for chart in (page.trend, page.passengers, page.departures):
        assert chart.height() == 304
        assert viewport.rect().contains(QRect(chart.mapTo(viewport, QPoint()), chart.size()))
    assert len(page.metric_cards) == 13 and sum(len(card.values) for card in page.highlights) == 16
    assert all(metric.value.font().pixelSize() == (28 if metric.key in ('line-count', 'fleet')
               else 24 if metric.key in CORE_METRIC_KEYS else 20) for metric in page.metric_cards.values())
    assert all(value.font().pixelSize() == (20 if index == (0 if position < 2 else 1) else 13)
               for position, card in enumerate(page.highlights) for index, value in enumerate(card.values))


def test_1440_shell_content_budget_has_no_scroll_or_overlap(page, qt_application):
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QAbstractScrollArea
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    for scroll in page.findChildren(QAbstractScrollArea):
        if not scroll.isVisible():
            continue  # Unopened detail tables have not received viewport layout.
        assert scroll.verticalScrollBar().maximum() == 0
        assert scroll.horizontalScrollBar().maximum() == 0, (type(scroll).__name__, scroll.objectName(), scroll.parent().objectName(), scroll.size().toTuple())
    names = [*(f'metric-{key}' for key in METRIC_KEYS),
             *(f'highlight-{i}' for i in range(4)),
             'todayTrend', 'passengerRanking', 'departureStructure', 'alertHost', 'cityCard']
    rectangles = []
    for name in names:
        widget = child(page, name)
        assert widget.isVisible() and inside(page, widget), name
        rect = QRect(widget.mapTo(page, QPoint()), widget.size())
        assert all(not rect.intersects(previous) for previous in rectangles), name
        rectangles.append(rect)
    assert 250 <= child(page, 'alertHost').width() <= 270


def test_missing_values_keep_zero_distinct_and_units_small(page):
    from PySide6.QtWidgets import QLabel
    data = snapshot()
    data = replace(data, metrics=(replace(data.metrics[0], value=0),
                                  replace(data.metrics[1], value=None,
                                          reason='未提供车辆数据'), *data.metrics[2:]))
    page.set_session(session())
    page.set_snapshot(data)
    assert child(page, 'metric-line-count-value').text() == '0'
    assert child(page, 'metric-fleet-value').text() == '—'
    assert '未提供车辆数据' in child(page, 'metric-fleet').toolTip()
    for key in METRIC_KEYS:
        assert child(page, f'metric-{key}-value').font().pixelSize() == (28 if key in ('line-count', 'fleet') else 24 if key in CORE_METRIC_KEYS else 20)
        assert child(page, f'metric-{key}-unit').font().pixelSize() == 12
    assert all(label.height() >= label.fontMetrics().height()
               for label in child(page, 'metric-fleet').findChildren(QLabel)
               if label.isVisible() and label.text())


def test_home_scope_change_keeps_city_context_and_clears_stale_rows(page):
    page.set_session(session())
    page.set_snapshot(snapshot())
    emitted = []
    page.scope_changed.connect(lambda company, mode: emitted.append((company, mode)))
    page.company_combo.setCurrentIndex(page.company_combo.findData('company-b'))
    assert page.scope() == ('company-b', '综合')
    assert emitted == [('company-b', '综合')]
    assert child(page, 'cityName').text() == '容量测试城市'
    assert child(page, 'metric-fleet-value').text() == '—'
    assert not any('滨江科技园区' in text for text in label_texts(child(page, 'passengerRanking')))
    assert not child(page, 'shareAction').isEnabled()
    page.mode_combo.setCurrentIndex(page.mode_combo.findData('地铁'))
    assert emitted[-1] == ('company-b', '地铁')


def test_set_session_is_metadata_only_and_new_save_clears_old_values(page, monkeypatch):
    import latest_info_model
    def forbidden(*args, **kwargs):
        pytest.fail('set_session must not calculate a snapshot in the UI thread')
    monkeypatch.setattr(latest_info_model, 'build_latest_info', forbidden)
    page.set_session(session())
    page.set_snapshot(snapshot())
    page.set_session(session('session-b', '新城市'))
    assert child(page, 'cityName').text() == '新城市'
    assert child(page, 'metric-line-count-value').text() == '—'
    assert not any('滨江科技园区' in text for text in label_texts(page))
    assert not child(page, 'reportAction').isEnabled()


def test_clear_session_retains_empty_structure_and_open_save(page):
    page.set_session(session())
    page.set_snapshot(snapshot())
    page.clear_session()
    assert page.scope() == ('', '综合')
    assert child(page, 'openSaveAction').isEnabled()
    for name in ('shareAction', 'reportAction', 'lineExportAction', 'companyExportAction'):
        assert not child(page, name).isEnabled()
    assert all(child(page, f'metric-{key}').isVisible() for key in METRIC_KEYS)
    assert child(page, 'metric-line-count-value').text() == '—'
    assert not any('滨江科技园区' in text for text in label_texts(page))


def test_previous_save_and_scope_results_cannot_restore_old_values(page):
    data = snapshot()
    page.set_session(session('session-b', '新城市'))
    page.set_snapshot(data)
    assert child(page, 'cityName').text() == '新城市'
    assert child(page, 'metric-line-count-value').text() == '—'
    assert not child(page, 'shareAction').isEnabled()
    page.set_session(session())
    page.company_combo.setCurrentIndex(page.company_combo.findData('company-b'))
    page.set_snapshot(data)
    assert child(page, 'metric-line-count-value').text() == '—'
    page.set_snapshot(replace(data, company_id='company-b'))
    assert child(page, 'metric-line-count-value').text() == '1'
    page.clear_session()
    page.set_snapshot(data)
    assert child(page, 'metric-line-count-value').text() == '—'
    assert not child(page, 'reportAction').isEnabled()


def test_narrow_more_menu_preserves_all_actions_and_disable_state(page, qt_application):
    page.set_session(session())
    page.set_workbook_availability(True, True)
    page.set_snapshot(snapshot())
    page.resize(680, 580)
    qt_application.processEvents()
    events = []
    page.share_requested.connect(lambda: events.append('share'))
    page.report_requested.connect(lambda: events.append('report'))
    page.line_export_requested.connect(lambda: events.append('line'))
    page.company_export_requested.connect(lambda: events.append('company'))
    # Trigger existing menu actions directly without opening a native popup/focus.
    for name in ('lineExportAction', 'companyExportAction', 'shareAction', 'reportAction'):
        assert page.menu_actions[name].isEnabled()
        page.menu_actions[name].trigger()
    assert events == ['line', 'company', 'share', 'report']
    page.clear_session()
    assert all(not action.isEnabled() for action in page.menu_actions.values())


@pytest.mark.parametrize('count', [0, 3])
def test_short_top10_does_not_fill_example_lines(page, count):
    data = snapshot()
    page.set_session(session())
    page.set_snapshot(replace(data, passenger_top10=data.passenger_top10[:count]))
    page.passengers.ranking_button.click()
    from PySide6.QtWidgets import QWidget
    rows = [row for row in child(page, 'passengerRanking').findChildren(QWidget)
            if row.objectName().startswith('ranking-row-') and row.isVisible()]
    assert len(rows) == count


def test_trend_uses_shared_panel_and_preserves_missing_hour(page):
    from stats_charts import ChartPanel
    data = snapshot()
    page.set_session(session())
    page.set_snapshot(data)
    panel = child(page, 'todayTrend')
    assert isinstance(panel, ChartPanel)
    assert panel.result is data.trend
    buckets = panel.result.series[('company-a', 'bus')]
    assert [bucket.value for bucket in buckets] == [Decimal(0), None, Decimal(12)]


def test_aggregate_trend_uses_friendly_company_name_without_changing_identity(page):
    data = snapshot()
    aggregate = replace(data.trend, series={('__selected__', 'bus'): data.trend.series[('company-a', 'bus')]})
    page.set_session(session())
    page.set_snapshot(replace(data, trend=aggregate, company_trend=aggregate))
    panel = child(page, 'todayTrend')
    assert panel.result is aggregate
    assert panel.companies['__selected__'] == '所选公司合计'
    assert '__selected__' not in label_texts(panel)


def test_today_trend_hour_labels_fit_three_card_width(page, qt_application):
    import re
    page.set_session(session())
    page.set_snapshot(snapshot())
    qt_application.processEvents()
    labels = [text for view in child(page, 'todayTrend').chart_views for text in view.data.labels]
    assert labels
    assert all(re.fullmatch(r'\d{2}:\d{2}', text) for text in labels)


def test_actions_emit_once_and_export_target_is_actual_content(page):
    events = []
    for signal, name in ((page.open_save_requested, 'open'),
                         (page.share_requested, 'share'),
                         (page.report_requested, 'report'),
                         (page.line_export_requested, 'line'),
                         (page.company_export_requested, 'company')):
        signal.connect(lambda name=name: events.append(name))
    page.set_session(session())
    page.set_workbook_availability(True, True)
    page.set_snapshot(snapshot())
    for action in ('openSaveAction', 'shareAction', 'reportAction',
                   'lineExportAction', 'companyExportAction'):
        child(page, action).click()
    assert events == ['open', 'share', 'report', 'line', 'company']
    target = page.export_target()
    assert target is page or page.isAncestorOf(target)
    assert target.isVisible() and inside(target, child(page, 'todayTrend'))
    assert inside(target, child(page, 'alertHost'))


def test_alert_panel_mount_replaces_old_panel_and_clears_on_scope_change(page):
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
    class RealPanel(QWidget):
        def __init__(self):
            super().__init__()
            self.label = QLabel('旧提醒', self)
            QVBoxLayout(self).addWidget(self.label)
        def clear_session(self):
            self.label.setText('无可比数据')
    previous, current = RealPanel(), RealPanel()
    page.set_alert_panel(previous)
    page.set_alert_panel(current)
    assert not previous.isVisible()
    assert child(page, 'alertHost').isAncestorOf(current)
    page.set_session(session())
    page.set_snapshot(snapshot())
    current.label.setText('上一公司提醒')
    page.company_combo.setCurrentIndex(page.company_combo.findData('company-b'))
    assert current.label.text() == '无可比数据'


def test_narrow_window_keeps_all_content_reachable(page, qt_application):
    from PySide6.QtWidgets import QAbstractScrollArea
    page.set_session(session())
    page.set_snapshot(snapshot())
    page.resize(680, 580)
    page.passengers.ranking_button.click()
    qt_application.processEvents()
    scrolls = [scroll for scroll in page.findChildren(QAbstractScrollArea) if scroll.isVisible()]
    assert any(scroll.verticalScrollBar().maximum() > 0 for scroll in scrolls)
    assert all(scroll.horizontalScrollBar().maximum() == 0 for scroll in scrolls)
    assert all(not child(page, f'metric-{key}').isHidden() for key in METRIC_KEYS)
    assert not child(page, 'ranking-row-9').isHidden()
    assert not child(page, 'mode-row-5').isHidden()


def test_category_drilldown_return_and_line_identity(page, qt_application):
    data = snapshot()
    page.set_session(session())
    page.set_snapshot(data)
    top = child(page, 'passengerRanking')
    top.ranking_button.click()
    lines = []
    page.line_requested.connect(lines.append)
    child(top, 'ranking-line-0').click()
    assert lines == ['line-0']
    child(top, 'rankingMode').setCurrentIndex(child(top, 'rankingMode').findData('地铁'))
    qt_application.processEvents()
    assert [row.line.key for row in top.visible_ranking_rows()] == ['line-3', 'line-9']
    child(top, 'rankingReturn').click()
    assert top.capture_state() == {'view': 'structure', 'mode': None}
    top.ranking_button.click()
    assert top.visible_ranking_rows()[0].line.key == data.lines[0].key
    departures = child(page, 'departureStructure')
    child(departures, 'departureRankingAction').click()
    qt_application.processEvents()
    assert child(departures, 'departure-ranking-row-9').isVisible()
    child(departures, 'departureReturn').click()
    assert child(departures, 'mode-row-5').isVisible()


def risk_ranking_snapshot(invalid=None, all_missing=False):
    data = snapshot()
    known = replace(data.lines[0], key='known', name='有观测线路', mode='公交',
                    passengers=5, departures=2)
    zero = replace(data.lines[1], key='zero', name='真实零值线路', mode='公交',
                   passengers=0, departures=0)
    missing = replace(data.lines[2], key='missing', name='无有效观测线路', mode='公交',
                      passengers=invalid, departures=invalid)
    lines = (missing,) if all_missing else (known, zero, missing)
    return replace(data, lines=lines, passenger_top10=() if all_missing else (known, zero))


def visible_ranking_rows(panel, prefix):
    from PySide6.QtWidgets import QWidget
    return [widget for widget in panel.findChildren(QWidget)
            if widget.objectName().startswith(f'{prefix}-row-') and widget.isVisible()]


@pytest.mark.parametrize('invalid', [None, Decimal('NaN'), float('inf')])
def test_passenger_mode_ranking_omits_invalid_observations_and_keeps_zero(page, qt_application, invalid):
    page.set_session(session())
    page.set_snapshot(risk_ranking_snapshot(invalid))
    panel = child(page, 'passengerRanking')
    mode = child(panel, 'rankingMode')
    mode.setCurrentIndex(mode.findData('公交'))
    qt_application.processEvents()
    rows = visible_ranking_rows(panel, 'ranking')
    assert len(rows) == 2
    assert rows[0].line.name == '有观测线路' and rows[0].number.text() == '5 人次'
    assert rows[1].line.name == '真实零值线路' and rows[1].number.text() == '0 人次'
    assert child(panel, 'rankingNote').text() == '公交 · 2条 · 人次'
    child(panel, 'rankingReturn').click()
    qt_application.processEvents()
    assert panel.capture_state() == {'view': 'structure', 'mode': None}
    panel.ranking_button.click()
    assert len(visible_ranking_rows(panel, 'ranking')) == 2
    assert '无有效观测线路' not in label_texts(panel)


@pytest.mark.parametrize('invalid', [None, Decimal('NaN'), float('inf')])
def test_departure_overall_and_mode_ranking_omit_invalid_observations(page, qt_application, invalid):
    page.set_session(session())
    page.set_snapshot(risk_ranking_snapshot(invalid))
    panel = child(page, 'departureStructure')
    child(panel, 'departureRankingAction').click()
    qt_application.processEvents()
    rows = visible_ranking_rows(panel, 'departure-ranking')
    assert len(rows) == 2
    assert rows[0].line.name == '有观测线路' and rows[0].number.text() == '2 班'
    assert rows[1].line.name == '真实零值线路' and rows[1].number.text() == '0 班'
    mode = child(panel, 'departureRankingMode')
    mode.setCurrentIndex(mode.findData('公交'))
    qt_application.processEvents()
    assert len(visible_ranking_rows(panel, 'departure-ranking')) == 2
    assert '无有效观测线路' not in label_texts(panel)


@pytest.mark.parametrize('view', ['passenger-mode', 'departure-overall', 'departure-mode'])
def test_all_missing_ranking_shows_no_numbered_rows(page, qt_application, view):
    page.set_session(session())
    page.set_snapshot(risk_ranking_snapshot(all_missing=True))
    if view == 'passenger-mode':
        panel, prefix = child(page, 'passengerRanking'), 'ranking'
        mode = child(panel, 'rankingMode')
        mode.setCurrentIndex(mode.findData('公交'))
    else:
        panel, prefix = child(page, 'departureStructure'), 'departure-ranking'
        child(panel, 'departureRankingAction').click()
        if view == 'departure-mode':
            mode = child(panel, 'departureRankingMode')
            mode.setCurrentIndex(mode.findData('公交'))
    qt_application.processEvents()
    assert visible_ranking_rows(panel, prefix) == []
    assert any('暂无有效' in text for text in label_texts(panel))
    assert '无有效观测线路' not in label_texts(panel)


@pytest.mark.parametrize('time_data,expected_date,expected_clock', [
    ({}, '未提供模拟时间', '—'),
    ({'simulation_time': None}, '未提供模拟时间', '—'),
    ({'metadata': {'当前日期': '2013-05-21', '当前时间': '23:59:13'}}, '2013-05-21  周二', '23:59:13'),
    ({'metadata': {'当前时间': '23:59:13'}}, '未提供模拟时间', '—'),
    ({'simulation_time': '坏时间'}, '未提供模拟时间', '—'),
    ({'simulation_time': '2013-05-21 23:59:13',
      'metadata': {'当前日期': '2024-06-10', '当前时间': '10:30:13'}}, '2013-05-21  周二', '23:59:13'),
    ({'metadata': {'当前日期': '2013-05-21'}}, '2013-05-21  周二', '00:00:00'),
    ({'metadata': {'当前日期': '日期错误', '当前时间': '时钟错误'}}, '未提供模拟时间', '—'),
    ({'simulation_time': '23:59:13',
      'metadata': {'当前日期': '2013-05-21', '当前时间': '23:59:13'}}, '未提供模拟时间', '—'),
])
def test_session_clock_accepts_save_sources_or_displays_unknown(page, time_data, expected_date, expected_clock):
    data = {'save_key': 'clock-risk', **time_data}
    page.set_session(data)
    assert child(page, 'citySimulationDate').text() == expected_date
    assert child(page, 'citySimulationTime').text() == expected_clock
    assert not child(page, 'reportAction').isEnabled()
    assert child(page, 'openSaveAction').isEnabled()
