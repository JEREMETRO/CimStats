"""Measure and capture a synthetic 180 px period network card."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'frontend'), str(ROOT / 'src')]

from PySide6.QtWidgets import QApplication

from network_charts import NetworkChartPanel
from stats_controls import FluentSegmentedControl
from test_network_charts import descriptor, make_result, snapshot


def main():
    app = QApplication.instance() or QApplication([])
    panel = NetworkChartPanel()
    panel.set_compact_height(180)
    control = FluentSegmentedControl(panel, compact=True)
    control.addItem('line', '趋势')
    control.addItem('bar', '分布')
    panel.set_mode_control(control)
    data = make_result('linecount', companies=('a',), groups=('总计',),
                       comparison=True)
    panel.set_descriptor(descriptor(data, key='linecount',
                                    allowed=('line', 'bar'), company_id='a'),
                         snapshot('period'))
    panel.resize(550, 180)
    panel.show()
    app.processEvents()
    view = panel.chart_views[0]
    print({
        'card': (panel.width(), panel.height()),
        'header': panel._header_layout.geometry().height(),
        'mode_row': panel._external_mode_row_host.height()
                    if panel._external_mode_row_host.isVisible() else 0,
        'legend': panel.legend_host.height() if panel.legend_host.isVisible() else 0,
        'period_label': panel.period_label.height()
                        if panel.period_label.isVisible() else 0,
        'view': view.height(),
        'plot': round(view.chart().plotArea().height(), 1),
    })
    destination = (ROOT / 'docs' / 'ui-redesign' / 'evidence' /
                   'network-charts' / 'compact-period-180.png')
    if not panel.grab().save(str(destination)):
        raise RuntimeError('screenshot failed')
    print(destination)
    panel.close()

    categories = NetworkChartPanel()
    categories.set_compact_height(180)
    category_control = FluentSegmentedControl(categories, compact=True)
    category_control.addItem('trend-bar', '趋势')
    category_control.addItem('pie', '比例')
    categories.set_mode_control(category_control)
    category_data = make_result(
        'transport-by-type', companies=('a',),
        groups=('bus', 'tram', 'trolley', 'metro', 'waterbus', 'misc'),
        comparison=True)
    categories.set_descriptor(
        descriptor(category_data, key='transport-by-type',
                   allowed=('trend-bar', 'pie'), company_id='a'),
        snapshot('period'))
    categories.resize(400, 180)
    categories.show()
    app.processEvents()
    view = categories.chart_views[0]
    print({
        'category_card': (categories.width(), categories.height()),
        'header': categories._header_layout.geometry().height(),
        'legend': categories.legend_host.height()
                  if categories.legend_host.isVisible() else 0,
        'period_row': (categories.period_label.height()
                       if categories.period_label.isVisible()
                       and categories._header_layout.indexOf(categories.period_label) < 0
                       else 0),
        'view': view.height(),
        'plot': round(view.chart().plotArea().height(), 1),
    })
    category_destination = destination.with_name('compact-period-categories-180.png')
    if not categories.grab().save(str(category_destination)):
        raise RuntimeError('category screenshot failed')
    print(category_destination)
    categories.close()


if __name__ == '__main__':
    main()
