"""Reproducible dashboard rendering, fixture generation, and geometry evidence.

Run in a separate process for each QT_SCALE_FACTOR. Artifacts are verification
outputs, never application content. No UI copy is inserted by this harness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'frontend'), str(ROOT / 'src')]


def synthetic_session():
    from statistics_model import METRICS
    start = datetime(2024, 1, 1)
    companies = [{'公司标识': 'p1', '公司名称': '滨海市公共交通运营公司'},
                 {'公司标识': 'p2', '公司名称': '滨海市公共交通运营公司'}]
    categories = {
        'transport-by-group': ['BlueCollar', 'WhiteCollar', 'Student', 'Tourist', 'BusinessPeople', 'Pensioner'],
        'transport-by-type': ['bus', 'tram', 'metro', 'trolley', 'waterbus'],
        'trip-types': ['single-line', 'one-zone', 'two-zones', 'three-zones', 'four-zones'],
        'population': ['BlueCollar', 'WhiteCollar', 'Student', 'Tourist', 'BusinessPeople', 'Pensioner'],
        'economy': ['growth', 'interests'], 'energy-prices': ['electricity', 'fuel'],
        'traffic-density': ['Road', 'Track'], 'stopcount': ['bus', 'tram', 'metro'],
        'company-value': ['net-cash', 'infra-value', 'vehicles-value', 'business-value'],
    }
    rows = []
    for hour in range(24 * 14):
        timestamp = (start + timedelta(hours=hour)).isoformat(sep=' ')
        for metric, definition in METRICS.items():
            if metric in ('city-mode-share', 'transfer-coefficient'):
                continue
            groups = categories.get(metric, ['Student'] if definition.scope == 'city' else ['bus'])
            owners = [''] if definition.scope == 'city' else ['p1', 'p2']
            for owner in owners:
                for index, group in enumerate(groups):
                    value, divider = (hour % 24 + 10) * (index + 1), 0
                    if metric == 'cashflow': value = (hour % 24 - 4) * 14500
                    elif metric == 'company-value': value = 800000 + hour * 1800 + index * 100000
                    elif metric == 'population': value = 45000 + hour * 13 + index * 1000
                    elif metric == 'vehicles-running': value = (150 + hour % 24) * 1024
                    elif metric == 'energy-prices': value = 1800 + hour + index * 100
                    elif metric == 'transport-by-group': value = (hour % 24 + 10) * 5
                    elif metric == 'transport-by-type': value = (hour % 24 + 10) * 6
                    elif metric == 'trip-types': value = (hour % 24 + 10) * 2
                    elif definition.kind.startswith('ratio'):
                        value, divider = (25 + hour % 10 + index * 5), 100
                    if owner == 'p2': value = value * 2
                    rows.append({'指标': metric, '分组': group, '公司标识': owner,
                                 '公司名称': companies[0]['公司名称'] if owner else '',
                                 '模拟时间': timestamp, '值': str(value), '分母': str(divider),
                                 '当前槽位': 'False'})
    return {'history': rows, 'simulation_time': '2024-01-15 10:30:00',
            'companies': companies, 'save_key': 'synthetic-ui-v1', 'tag': 'UI-QA'}


def wait_for_snapshot(app, page, timeout=60):
    deadline = time.monotonic() + timeout
    while page.snapshot is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.02)
    if page.snapshot is None:
        raise RuntimeError('Dashboard did not produce a snapshot')
    for _ in range(4):
        app.processEvents()
        time.sleep(.03)


def geometry_report(widget):
    from PySide6.QtWidgets import QWidget, QLabel, QAbstractButton, QComboBox, QDateTimeEdit
    failures = []
    for child in widget.findChildren(QWidget):
        if not isinstance(child, (QLabel, QAbstractButton, QComboBox, QDateTimeEdit)):
            continue
        if not child.isVisible() or not child.parentWidget():
            continue
        parent = child.parentWidget()
        # Charts, scroll viewports and popups intentionally clip their contents.
        if 'qt_' in child.objectName() or parent.inherits('QAbstractScrollArea'):
            continue
        rect = child.geometry()
        if rect.width() <= 0 or rect.height() <= 0:
            failures.append({'kind': 'zero-size', 'class': type(child).__name__, 'name': child.objectName()})
        elif rect.x() < -1 or rect.y() < -1 or rect.right() > parent.width() + 1 or rect.bottom() > parent.height() + 1:
            failures.append({'kind': 'outside-parent', 'class': type(child).__name__,
                             'name': child.objectName(), 'rect': rect.getRect(),
                             'parent': [parent.width(), parent.height()]})
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--job', type=Path)
    parser.add_argument('--tag')
    parser.add_argument('--main-window', action='store_true')
    parser.add_argument('--sizes', default='1920x1080,1600x900,1366x768,1024x768,920x680')
    args = parser.parse_args()
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from statistics_page import StatisticsPage
    app = QApplication.instance() or QApplication([])
    import stats_style
    if hasattr(stats_style, 'initialize_theme'):
        stats_style.initialize_theme(app)
    else:
        app.setStyle('Fusion')
        app.setStyleSheet(stats_style.STYLE)
    args.output.mkdir(parents=True, exist_ok=True)
    settings = QSettings(str(args.output / 'qa-settings.ini'), QSettings.Format.IniFormat)
    if args.job:
        from report_model import load_session
        data = load_session(args.job, args.tag)
    else:
        data = synthetic_session()
    if args.main_window:
        import desktop_app
        desktop_app.QSettings = lambda *a: settings
        desktop_app.MainWindow.check_install = lambda self: None
        window = desktop_app.MainWindow()
        if not args.job:
            from report_model import load_session
            original = load_session(ROOT / 'exports', '望春市_test_运行时')
            original.update(data)
            data = original
        data.setdefault('save_path', (args.tag.removesuffix('_运行时') if args.tag else 'UI-QA') + '.save')
        if not args.job:
            data['metadata'] = {'当前日期': '2024-01-15', '当前时间': '10:30:00', '当前人口数': 311130}
            data['counts']['companies'] = len(data['companies'])
        window.on_completed(data)
        page = window.statistics_page
        window.navigate(2)
    else:
        page = StatisticsPage(settings)
        window = page
        page.set_session(data)
    window.show()
    wait_for_snapshot(app, page)
    evidence = {'scale': os.getenv('QT_SCALE_FACTOR', '1'), 'dpr': window.devicePixelRatioF(),
                'cases': [], 'history_rows': len(data['history'])}
    for size in args.sizes.split(','):
        width, height = map(int, size.split('x'))
        window.resize(width, height)
        for _ in range(8):
            app.processEvents()
            time.sleep(.02)
        filename = args.output / f'dashboard-{size}.png'
        window.grab().save(str(filename))
        board = args.output / f'boards-{size}.png'
        page.board_host.grab().save(str(board))
        evidence['cases'].append({'size': size, 'actual': [window.width(), window.height()],
                                  'content': [page.width(), page.height()],
                                  'viewport': [page.scroll.viewport().width(), page.scroll.viewport().height()],
                                  'scroll_content': [page.scroll.widget().width(), page.scroll.widget().height()],
                                  'horizontal_overflow': max(0, page.scroll.widget().width() - page.scroll.viewport().width()),
                                  'geometry': geometry_report(window), 'screenshot': str(filename),
                                  'sha256': hashlib.sha256(filename.read_bytes()).hexdigest()})
    page.stop_workers()
    window.close()
    (args.output / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'cases': len(evidence['cases']), 'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
