"""Render synthetic company/network cards to inspect the opt-in data palette."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'frontend'), str(ROOT / 'src')]

from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QVBoxLayout, QWidget

from network_charts import NetworkChartPanel
from stats_charts import ChartPanel
from stats_controls import FluentSegmentedControl
from test_network_charts import descriptor, endpoint_result, make_result, snapshot
import stats_tokens as tokens


def main():
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    host.setObjectName('paletteQaHost')
    host.setStyleSheet(f'QWidget#paletteQaHost {{ background: {tokens.PAGE_BG}; }}')
    layout = QVBoxLayout(host)
    layout.setContentsMargins(20, 16, 20, 20)
    heading = QLabel('演示数据 · 公司与网络图表配色')
    heading.setStyleSheet(f'color: {tokens.TEXT_PRIMARY}; font-size: 20px; '
                          f'font-family: "{tokens.FONT_FAMILY}"; font-weight: 600;')
    layout.addWidget(heading)
    grid = QGridLayout()
    grid.setSpacing(16)
    layout.addLayout(grid)
    palette = {'a': tokens.DATA_COMPANY_COLORS[0], 'b': tokens.DATA_COMPANY_COLORS[1]}
    categories = ('bus', 'tram', 'trolley', 'metro', 'waterbus', 'misc')
    stop_data = make_result('stopcount', companies=('a',), groups=categories)
    cases = (
        ('分类时间堆积', 'trend-bar', make_result(companies=('a',), groups=categories), None),
        ('分类时间趋势', 'line', make_result(companies=('a',), groups=categories), None),
        ('分类比例', 'pie', make_result(companies=('a',), groups=categories), None),
        ('分类横条', 'bar', stop_data, endpoint_result(stop_data)),
    )
    for index, (title, mode, data, bar_data) in enumerate(cases):
        panel = NetworkChartPanel(host)
        panel.set_company_palette(palette)
        panel.set_descriptor(descriptor(data, key='stopcount' if mode == 'bar' else
                                        'transport-by-type', allowed=(mode,),
                                        bar_result=bar_data),
                             snapshot('overall'))
        panel.title_label.setText(title)
        panel.set_mode(mode)
        grid.addWidget(panel, index // 2, index % 2)
    company = ChartPanel('公司客流趋势', default_mode='line', parent=host)
    company.set_category_palette(tokens.DATA_CATEGORY_COLORS)
    company.set_company_palette(palette)
    company.set_result(make_result(companies=('a', 'b'), groups=('总计',)),
                       {'a': '甲公司', 'b': '乙公司'})
    grid.addWidget(company, 2, 0, 1, 2)
    host.resize(1200, 1120)
    host.show()
    app.processEvents()
    destination = ROOT / 'docs' / 'ui-redesign' / 'evidence' / 'network-charts' / 'data-palette.png'
    if not host.grab().save(str(destination)):
        raise RuntimeError('screenshot failed')
    print(destination)
    host.close()

    narrow = QWidget()
    narrow.setObjectName('paletteQaNarrow')
    narrow.setStyleSheet(f'QWidget#paletteQaNarrow {{ background: {tokens.PAGE_BG}; }}')
    narrow_layout = QVBoxLayout(narrow)
    narrow_layout.setContentsMargins(12, 12, 12, 12)
    narrow_panel = NetworkChartPanel(narrow)
    narrow_panel.set_company_palette(palette)
    narrow_panel.set_descriptor(
        descriptor(stop_data, key='stopcount', allowed=('bar',),
                   bar_result=endpoint_result(stop_data)),
        snapshot('overall'))
    narrow_panel.set_mode('bar')
    narrow_layout.addWidget(narrow_panel)
    narrow.resize(440, 380)
    narrow.show()
    app.processEvents()
    narrow_image = destination.with_name('data-palette-narrow.png')
    if not narrow.grab().save(str(narrow_image)):
        raise RuntimeError('narrow screenshot failed')
    print(narrow_image)
    narrow_panel._open_fullscreen()
    app.processEvents()
    fullscreen_image = destination.with_name('data-palette-fullscreen.png')
    if not narrow_panel._fullscreen_dialog.grab().save(str(fullscreen_image)):
        raise RuntimeError('fullscreen screenshot failed')
    print(fullscreen_image)
    narrow_panel._fullscreen_dialog.close()
    narrow.close()

    period_host = QWidget()
    period_host.setObjectName('paletteQaPeriod')
    period_host.setStyleSheet(f'QWidget#paletteQaPeriod {{ background: {tokens.PAGE_BG}; }}')
    period_layout = QGridLayout(period_host)
    period_layout.setContentsMargins(16, 16, 16, 16)
    period_layout.setSpacing(16)
    for index, company_id in enumerate(('a', 'b')):
        data = make_result('linecount', companies=(company_id,), groups=('bus',),
                           comparison=True)
        panel = NetworkChartPanel(period_host)
        panel.set_company_palette(palette)
        panel.set_descriptor(descriptor(data, key='linecount', allowed=('line',),
                                        company_id=company_id), snapshot('period'))
        panel.title_label.setText('甲公司 · 线路数' if index == 0 else '乙公司 · 线路数')
        period_layout.addWidget(panel, 0, index)
    period_host.resize(1200, 420)
    period_host.show()
    app.processEvents()
    period_image = destination.with_name('data-palette-period.png')
    if not period_host.grab().save(str(period_image)):
        raise RuntimeError('period screenshot failed')
    print(period_image)
    period_host.close()

    compact_host = QWidget()
    compact_host.setObjectName('paletteQaCompact')
    compact_host.setStyleSheet(f'QWidget#paletteQaCompact {{ background: {tokens.PAGE_BG}; }}')
    compact_layout = QGridLayout(compact_host)
    compact_layout.setContentsMargins(8, 8, 8, 8)
    compact_layout.setSpacing(8)
    for index, mode in enumerate(('line', 'bar', 'pie')):
        data = stop_data if mode == 'bar' else make_result(
            companies=('a',), groups=categories)
        panel = NetworkChartPanel(compact_host)
        panel.set_compact_height(190)
        panel.set_company_palette(palette)
        panel.set_descriptor(
            descriptor(data, key='stopcount' if mode == 'bar' else 'transport-by-type',
                       allowed=(mode,),
                       bar_result=endpoint_result(data) if mode == 'bar' else None),
            snapshot('overall'))
        panel.set_mode(mode)
        panel.title_label.setText({'line': '分类趋势', 'bar': '分类分布',
                                   'pie': '分类比例'}[mode])
        compact_layout.addWidget(panel, 0, index)
    compact_host.resize(1260, 206)
    compact_host.show()
    app.processEvents()
    compact_image = destination.with_name('data-palette-compact.png')
    if not compact_host.grab().save(str(compact_image)):
        raise RuntimeError('compact screenshot failed')
    print(compact_image)
    compact_host.close()

    four_host = QWidget()
    four_host.setObjectName('paletteQaFour')
    four_host.setStyleSheet(f'QWidget#paletteQaFour {{ background: {tokens.PAGE_BG}; }}')
    four_layout = QGridLayout(four_host)
    four_layout.setContentsMargins(8, 8, 8, 8)
    four_layout.setSpacing(8)
    for index, mode in enumerate(('line', 'trend-bar', 'bar', 'pie')):
        data = stop_data if mode == 'bar' else make_result(
            companies=('a',), groups=categories)
        panel = NetworkChartPanel(four_host)
        panel.set_compact_height(230)
        panel.set_company_palette(palette)
        modes = ('line', 'bar') if mode in ('line', 'bar') else ('trend-bar', 'pie')
        selector = FluentSegmentedControl(panel, compact=True)
        for choice in modes:
            selector.addItem(choice, {'line': '趋势', 'trend-bar': '趋势',
                                      'bar': '分布', 'pie': '比例'}[choice])
        panel.set_mode_control(selector)
        panel.set_descriptor(
            descriptor(data, key='stopcount' if mode == 'bar' else 'transport-by-type',
                       allowed=modes,
                       bar_result=endpoint_result(data) if mode == 'bar' else None),
            snapshot('overall'))
        panel.set_mode(mode)
        panel.title_label.setText({'line': '平均运行车辆数', 'trend-bar': '时间堆积',
                                   'bar': '分类分布', 'pie': '分类比例'}[mode])
        four_layout.addWidget(panel, 0, index)
    four_host.resize(1168, 246)
    four_host.show()
    app.processEvents()
    four_image = destination.with_name('data-palette-four-column.png')
    if not four_host.grab().save(str(four_image)):
        raise RuntimeError('four-column screenshot failed')
    print(four_image)
    four_host.close()

    company_host = QWidget()
    company_host.setObjectName('paletteQaCompany')
    company_host.setStyleSheet(f'QWidget#paletteQaCompany {{ background: {tokens.PAGE_BG}; }}')
    company_layout = QGridLayout(company_host)
    company_layout.setContentsMargins(8, 8, 8, 8)
    company_layout.setSpacing(8)
    for index, company_id in enumerate(('a', 'b')):
        for row, (metric, mode) in enumerate((('company-value', 'line'),
                                              ('cashflow', 'trend-bar'))):
            panel = ChartPanel('公司价值' if row == 0 else '现金流',
                               default_mode=mode, allowed_modes=(mode,),
                               parent=company_host)
            panel.set_compact_height(200)
            panel.set_company_palette(palette)
            panel.set_result(make_result(metric, companies=(company_id,),
                                         groups=('总计',)),
                             {'a': '甲公司', 'b': '乙公司'})
            company_layout.addWidget(panel, row, index)
    company_host.resize(800, 416)
    company_host.show()
    app.processEvents()
    company_image = destination.with_name('data-palette-company-compact.png')
    if not company_host.grab().save(str(company_image)):
        raise RuntimeError('company compact screenshot failed')
    print(company_image)
    company_host.close()

    company_narrow = QWidget()
    company_narrow.setObjectName('paletteQaCompanyNarrow')
    company_narrow.setStyleSheet(
        f'QWidget#paletteQaCompanyNarrow {{ background: {tokens.PAGE_BG}; }}')
    company_narrow_layout = QVBoxLayout(company_narrow)
    company_narrow_layout.setContentsMargins(8, 8, 8, 8)
    company_panel = ChartPanel('公司价值', default_mode='line',
                               allowed_modes=('line',), parent=company_narrow)
    company_panel.set_compact_height(200)
    company_panel.set_company_palette(palette)
    company_panel.set_result(make_result('company-value', companies=('b',),
                                         groups=('总计',)), {'b': '乙公司'})
    company_narrow_layout.addWidget(company_panel)
    company_narrow.resize(279, 216)
    company_narrow.show()
    app.processEvents()
    company_narrow_image = destination.with_name('data-palette-company-narrow.png')
    if not company_narrow.grab().save(str(company_narrow_image)):
        raise RuntimeError('company narrow screenshot failed')
    print(company_narrow_image)
    company_narrow.close()


if __name__ == '__main__':
    main()
