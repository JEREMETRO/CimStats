"""Render marked demo QtCharts cards for visual QA; never used by the app."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'frontend'), str(ROOT / 'src')]

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QVBoxLayout, QWidget
from PySide6.QtGui import QAction
from qfluentwidgets import RoundMenu

from statistics_model import Bucket, METRICS, Query, Result
from stats_charts import ChartPanel
import stats_tokens as tokens


def demo_result(metric, companies, previous=False, count=14):
    start = datetime(2024, 2, 19)
    end = start + timedelta(days=count)
    comparison = (start - timedelta(days=count), start) if previous else None
    series, earlier = {}, {}
    for number, company in enumerate(companies):
        def buckets(first, compare=False):
            output = []
            for index in range(count):
                time = first + timedelta(days=index)
                raw = ((80 if metric == 'cashflow' else 1900) +
                       number * (48 if metric == 'cashflow' else 950) +
                       index * (7 if metric == 'cashflow' else 90) +
                       (index % 4) * (13 if metric == 'cashflow' else 130))
                value = None if index == count // 2 else Decimal(raw * (.72 if compare else 1))
                if metric == 'cashflow' and index == count - 4:
                    value = Decimal(-24 if not compare else -12)
                if metric == 'cashflow' and index == count - 2:
                    value = Decimal(0)
                output.append(Bucket(time, time + timedelta(days=1), value,
                                     value is not None, False, time if value is not None else None,
                                     None, None, 24))
            return output
        series[(company, '总计')] = buckets(start)
        if previous:
            earlier[(company, '总计')] = buckets(comparison[0], True)
    query = Query(metric, tuple(companies), '__total__', start, end, 'day', comparison)
    return Result(query, METRICS[metric], series, earlier, (start, end), comparison)


def capture(title, cards, output, *, with_modes=False, with_menu=False,
            mode_options=None, compact_layout=False, width=1120, height=None):
    host = QWidget()
    host.setObjectName('qaHost')
    host.setStyleSheet(f'QWidget#qaHost {{ background: {tokens.PAGE_BG}; }}')
    layout = QVBoxLayout(host)
    layout.setContentsMargins(20, 20, 20, 20)
    heading = QLabel('演示数据 · ' + title)
    heading.setStyleSheet(f'color: {tokens.TEXT_PRIMARY}; font-family: "{tokens.FONT_FAMILY}"; '
                          'font-size: 20px; font-weight: 600;')
    layout.addWidget(heading)
    grid = QGridLayout()
    grid.setSpacing(16)
    layout.addLayout(grid, 1)
    palette = {'a': tokens.COMPANY_COLORS[0], 'b': tokens.COMPANY_COLORS[1]}
    for index, (name, mode, data) in enumerate(cards):
        panel = ChartPanel(name, modes=with_modes, default_mode=mode, parent=host,
                           allowed_modes=mode_options)
        if compact_layout:
            panel.set_compact_layout(True)
        if with_menu:
            menu = RoundMenu(parent=panel)
            menu.addAction(QAction('公司价值', menu))
            menu.addAction(QAction('满意度', menu))
            panel.set_metric_menu(menu)
        panel.set_company_palette(palette)
        panel.set_result(data, {'a': '八达交通集团', 'b': '海港公共交通'})
        columns = 1 if width < 720 else 2
        grid.addWidget(panel, index // columns, index % columns)
    host.resize(width, height or (470 if len(cards) <= 2 else 800))
    host.show()
    QApplication.instance().processEvents()
    host.grab().save(str(output))
    if with_menu:
        menu.popup(panel.metric_menu_button.mapToGlobal(QPoint(0, panel.metric_menu_button.height())))
        QApplication.instance().processEvents()
        menu.grab().save(str(output.with_name('05-metric-menu-demo.png')))
        menu.hide()
        panel.fullscreen_button.click()
        QApplication.instance().processEvents()
        panel._fullscreen_dialog.grab().save(str(output.with_name('06-fullscreen-demo.png')))
        panel._fullscreen_dialog.close()
    host.close()


def main():
    app = QApplication.instance() or QApplication([])
    output = ROOT / 'docs' / 'ui-redesign' / 'evidence' / 'charts'
    output.mkdir(parents=True, exist_ok=True)
    capture('多公司同图横比', [
        ('现金流', 'trend-bar', demo_result('cashflow', ('a', 'b'))),
        ('公司价值', 'line', demo_result('company-value', ('a', 'b'))),
    ], output / '01-overlay-demo.png')
    capture('每家公司同期对比', [
        ('现金流', 'trend-bar', demo_result('cashflow', ('a',), True)),
        ('公司价值', 'line', demo_result('company-value', ('a',), True)),
    ], output / '02-period-demo.png')
    capture('轻面积折线与断点', [
        ('公司价值', 'line', demo_result('company-value', ('a',), True)),
    ], output / '03-area-demo.png')
    capture('指标菜单与 Fluent 图卡', [
        ('公司价值', 'line', demo_result('company-value', ('a',), True)),
    ], output / '04-mode-control-demo.png', with_menu=True,
    mode_options=('line',), width=600)
    capture('窄卡图例', [
        ('公司价值', 'line', demo_result('company-value', ('a', 'b'))),
    ], output / '07-narrow-demo.png', width=400)
    capture('窄卡轻面积折线', [
        ('公司价值', 'line', demo_result('company-value', ('a',), True)),
    ], output / '08-narrow-mode-demo.png', mode_options=('line',), width=400)
    capture('单公司紧凑现金流', [
        ('现金流', 'trend-bar', demo_result('cashflow', ('a',))),
    ], output / '09-compact-cashflow-demo.png', compact_layout=True,
    mode_options=('trend-bar',), width=700, height=320)
    capture('七个时间桶 · 正负零与缺测', [
        ('现金流', 'trend-bar', demo_result('cashflow', ('a',), count=7)),
    ], output / '13-sparse-seven-demo.png', compact_layout=True,
    mode_options=('trend-bar',), width=700, height=320)
    capture('密集时间桶 · 宽度自适应', [
        ('现金流', 'trend-bar', demo_result('cashflow', ('a', 'b'), count=42)),
    ], output / '14-dense-forty-two-demo.png', width=1120, height=420)
    categories = demo_result('transport-by-type', ('a',))
    sole = categories.series[('a', '总计')]
    categories.series = {('a', group): [Bucket(bucket.start, bucket.end,
                                                bucket.value * factor if bucket.value is not None else None,
                                                bucket.complete, bucket.partial_period, bucket.observed,
                                                bucket.numerator, bucket.denominator, bucket.effective_hours)
                                         for bucket in sole]
                         for group, factor in (('bus', 1), ('tram', Decimal('.65')),
                                               ('metro', Decimal('.85')))}
    capture('分类横条与环形饼', [
        ('分类客流', 'bar', categories), ('分类占比', 'pie', categories),
    ], output / '15-category-and-pie-demo.png', width=1120, height=420)
    compared_categories = demo_result('transport-by-type', ('a',), True)
    compared_categories.series = categories.series
    compared_categories.comparison = {
        key: [Bucket(bucket.start - timedelta(days=14), bucket.end - timedelta(days=14),
                     bucket.value * Decimal('.7') if bucket.value is not None else None,
                     bucket.complete, bucket.partial_period,
                     bucket.observed - timedelta(days=14) if bucket.observed else None,
                     bucket.numerator, bucket.denominator, bucket.effective_hours)
              for bucket in buckets]
        for key, buckets in categories.series.items()
    }
    capture('分类横条同期对比', [
        ('分类客流', 'bar', compared_categories),
    ], output / '16-category-period-demo.png', width=700, height=420)
    capture('单公司紧凑趋势', [
        ('公司价值', 'line', demo_result('company-value', ('a',))),
    ], output / '10-compact-line-demo.png', compact_layout=True,
    mode_options=('line',), width=700, height=320)
    capture('窄卡紧凑趋势', [
        ('公司价值', 'line', demo_result('company-value', ('a',))),
    ], output / '11-compact-narrow-demo.png', compact_layout=True,
    mode_options=('line',), width=400, height=360)
    crossing = demo_result('cashflow', ('a',), count=7)
    for bucket, value in zip(crossing.series[('a', '总计')],
                             (90, 40, -30, -50, 0, None, 75)):
        bucket.value = None if value is None else Decimal(value)
        bucket.complete = value is not None
        bucket.observed = bucket.start if value is not None else None
    capture('轻面积折线 · 穿越零线与缺测', [
        ('符号跨越验证', 'line', crossing),
    ], output / '17-line-cross-zero-demo.png', width=700, height=350)
    revision = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'],
                                       cwd=ROOT, text=True).strip()
    (output / 'README.json').write_text(json.dumps({
        'source': 'fixed demo fixture in src/qa_stats_charts.py',
        'screenshots': {
            '01-overlay-demo.png': {'logical_size': [1120, 470], 'mode': 'companies'},
            '02-period-demo.png': {'logical_size': [1120, 470], 'mode': 'period'},
            '03-area-demo.png': {'logical_size': [1120, 470], 'mode': 'light area line with missing gap'},
            '04-mode-control-demo.png': {'logical_size': [600, 470], 'mode': 'light area line with metric menu'},
            '05-metric-menu-demo.png': {'logical_size': [122, 98], 'mode': 'metric menu popup'},
            '06-fullscreen-demo.png': {'logical_size': [796, 796], 'mode': 'area fullscreen'},
            '07-narrow-demo.png': {'logical_size': [400, 470], 'mode': 'companies in narrow card'},
            '08-narrow-mode-demo.png': {'logical_size': [400, 470], 'mode': 'light area line in narrow card'},
            '09-compact-cashflow-demo.png': {'logical_size': [700, 320], 'mode': 'compact cashflow'},
            '10-compact-line-demo.png': {'logical_size': [700, 320], 'mode': 'compact light area line'},
            '11-compact-narrow-demo.png': {'logical_size': [400, 360], 'mode': 'compact narrow light area line'},
            '13-sparse-seven-demo.png': {'logical_size': [700, 320], 'mode': 'seven buckets, negative, zero, missing'},
            '14-dense-forty-two-demo.png': {'logical_size': [1120, 420], 'mode': '42 buckets, grouped companies'},
            '15-category-and-pie-demo.png': {'logical_size': [1120, 420], 'mode': 'horizontal categories and pie'},
            '16-category-period-demo.png': {'logical_size': [700, 420], 'mode': 'horizontal category period comparison'},
            '17-line-cross-zero-demo.png': {'logical_size': [700, 350], 'mode': 'line area, zero crossing and missing gap'},
        },
        'dpi': app.primaryScreen().logicalDotsPerInch(), 'code_revision': revision,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
