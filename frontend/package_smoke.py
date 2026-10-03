"""Opt-in local GUI acceptance using the actual application and real sessions.

Normal startup never imports this module. Outputs and settings are isolated;
the delivered executable exercises its own startup and parser dispatch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback


def main(launcher: Path, argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--save', type=Path)
    source.add_argument('--job', type=Path)
    parser.add_argument('--tag', default='真实存档验收')
    parser.add_argument('--expected-dpr', type=float, required=True)
    args = parser.parse_args(argv)
    original = args.save or args.job
    if not original.exists():
        parser.error('Save/session does not exist')
    if args.output.exists():
        parser.error('Use a new output directory')
    args.output.mkdir(parents=True)
    from startup_bootstrap import main as bootstrap_main

    def factory():
        from PySide6.QtCore import QSettings, QTimer
        import desktop_app
        settings = QSettings(str(args.output / 'prefs.ini'), QSettings.Format.IniFormat)
        desktop_app.QSettings = lambda *_args: settings
        desktop_app.JOBS = args.output / 'parsed-jobs'
        window = desktop_app.MainWindow()
        window.resize(960, 680)

        def begin():
            if window.property('startupHandoffPending'):
                QTimer.singleShot(30, begin)
                return
            try:
                _exercise(window, desktop_app, args)
                code = 0
            except Exception:
                (args.output / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
                code = 1
            window.statistics_page.stop_workers()
            window.close()
            from PySide6.QtWidgets import QApplication
            QApplication.instance().exit(code)

        QTimer.singleShot(0, begin)
        return window

    return bootstrap_main(launcher, window_factory=factory, trace_path=args.output / 'startup.json')


def _exercise(win, desktop_app, args):
    from dataclasses import replace
    from PySide6.QtCore import QEventLoop, QPoint, QTimer
    from PySide6.QtWidgets import QApplication, QToolTip
    from shiboken6 import isValid
    from report_model import load_session
    from stats_charts import ChartPanel
    app = QApplication.instance()
    records = []

    def settle(ms=300):
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def wait_until(predicate, timeout=120):
        end = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= end:
                raise RuntimeError('Application readiness timed out')
            settle(25)
        settle()

    def capture(name, widget=win):
        settle()
        path = args.output / (name + '.png')
        assert widget.grab().save(str(path))
        composited = None
        if app.platformName() == 'windows':
            widget.window().raise_()
            widget.window().activateWindow()
            settle(80)
            if widget.window().isActiveWindow():
                position = widget.mapToGlobal(QPoint(0, 0))
                composited = args.output / (name + '-composited.png')
                widget.screen().grabWindow(0, position.x(), position.y(),
                                           widget.width(), widget.height()).save(str(composited))
        records.append({'case':name, 'size':[widget.width(), widget.height()],
                        'screenshot':str(path), 'composited':str(composited) if composited else None})

    assert abs(win.devicePixelRatioF() - args.expected_dpr) < .001
    capture('startup-welcome')
    digest = None
    if args.save:
        digest = hashlib.sha256(args.save.read_bytes()).hexdigest()
        errors = []
        win.start_parse(args.save)
        assert win.worker is not None
        win.worker.failed.connect(errors.append)
        capture('actual-save-parsing')
        wait_until(lambda: bool(errors) or (win.worker is None and bool(win.data) and not win._awaiting_dashboards), 360)
        assert not errors, errors
        assert hashlib.sha256(args.save.read_bytes()).hexdigest() == digest
        data = win.data
        job = desktop_app.JOBS / data['manifest']['job_id']
    else:
        job = args.job
        data = load_session(job, args.tag)
        win.on_completed(data)
        wait_until(lambda: not win._awaiting_dashboards)
    page = win.statistics_page
    assert not page.analysis_mode_control._buttons['companies'].isEnabled()
    assert not page.network_mode_control._buttons['companies'].isEnabled()
    for width, height in ((960, 680), (1600, 900)):
        win.resize(width, height)
        for index, label in ((0, 'home'), (1, 'lines'), (2, 'stats')):
            win.navigate(index)
            settle()
            if index == 1 and data.get('lines'):
                win.line_clicked(0, 0)
            if index != 2:
                capture(f'{label}-{width}x{height}')
            else:
                for family in ('company', 'network', 'city'):
                    page.tab_bar.setCurrentItem(family)
                    page._tab_changed(family)
                    capture(f'stats-{family}-{width}x{height}')
        win.navigate(0)
        for _ in range(50):
            win._refresh_exports()
        assert win.header.export_menu.view.count() == 6
        assert len(win.header.export_menu.actions()) == 5
        win.header._show_export_menu()
        capture(f'export-{width}x{height}', win.header.export_menu)
        win.header.export_menu.close()
    win.resize(960, 680)
    win.navigate(2)
    page.tab_bar.setCurrentItem('network')
    page._tab_changed('network')
    wait_until(lambda: page.network_snapshot is not None)
    average_chart = next(c for c in page.network_snapshot.charts if c.key == 'vehicles-running')
    page._network_options_changed(replace(page.network_options, vehicle='maximum'))
    wait_until(lambda: page.network_snapshot is not None)
    demand = next(v for v in page.network_snapshot.summaries[0].values if v.metric_id == 'vehicles-running')
    assert demand.complete and demand.context
    assert next(c for c in page.network_snapshot.charts if c.key == 'vehicles-running') == average_chart
    capture('demand-with-average-trend')
    company = next(p for p in page.company_dashboard.findChildren(ChartPanel) if p.result is not None and p.chart_views)
    compact = ChartPanel(company.title_label.text(), default_mode=company.mode,
                         allowed_modes=company._allowed_modes if company._restricted_modes else None)
    compact.set_company_palette({key:color.name() for key, color in company._company_palette.items()})
    compact.set_category_palette(company._category_palette)
    compact.set_result(company.result, company.companies)
    compact.set_compact_height(190)
    compact.resize(400, 190)
    compact.show()
    capture('compact-400x190', compact)
    compact.close()
    for family in ('company', 'network', 'city', 'home'):
        win.navigate(0 if family == 'home' else 2)
        if family != 'home':
            page.tab_bar.setCurrentItem(family)
            page._tab_changed(family)
        win.resize(960, 680)
        settle()
        if family == 'home':
            source = win.latest_info_page.trend
        elif family == 'city':
            source = page.city_dashboard.panels['population']
        else:
            dashboard = page.company_dashboard if family == 'company' else page.network_dashboard
            source = next(p for p in dashboard.findChildren(ChartPanel) if p.result is not None and p.chart_views)
        ancestor = source.parentWidget()
        while ancestor is not None:
            if callable(getattr(ancestor, 'ensureWidgetVisible', None)):
                ancestor.ensureWidgetVisible(source)
                settle()
                break
            ancestor = ancestor.parentWidget()
        clone = source._open_fullscreen()
        detail = source._fullscreen_dialog
        assert clone is not None and detail is not None and not detail.isWindow()
        settle()
        assert clone.fullscreen_button.isVisible() and clone.fullscreen_button.isEnabled()
        assert clone.geometry().bottom() <= detail.height()
        picture = detail.grab().toImage()
        for point in [QPoint(3, 3), *(c.mapTo(detail, QPoint(2, 2)) for c in clone.chart_views)]:
            assert picture.pixelColor(point).name() == '#ffffff'
        capture('expanded-' + family, detail)
        hidden = set(clone._hidden_groups)
        clone.fullscreen_button.click()
        wait_until(lambda: not isValid(detail) or not detail.isVisible(), 5)
        assert source._hidden_groups == hidden
    win.navigate(0)
    for index, text in enumerate(('查看完整名称', '长标签验证：真实公司的完整名称    前一完整日')):
        QToolTip.showText(win.mapToGlobal(QPoint(260, 180)), text, win)
        settle()
        tooltip = next((w for w in app.topLevelWidgets() if w.objectName() == 'qtooltip_label' and w.isVisible()), None)
        assert tooltip is not None
        assert tooltip.font().pixelSize() == 12 and not tooltip.font().bold()
        capture('native-tooltip-' + str(index), tooltip)
        QToolTip.hideText()
        settle()
    report = {'frozen':bool(getattr(sys, 'frozen', False)), 'executable':sys.executable,
              'scale':os.environ.get('QT_SCALE_FACTOR', '1'), 'dpr':win.devicePixelRatioF(),
              'real_job':str(job), 'real_history_rows':len(data.get('history', [])),
              'current_demand':str(demand.value), 'raw_save':str(args.save) if args.save else None,
              'raw_save_sha256_unchanged':digest, 'synthetic_tooltip_style_probe':True, 'cases':records}
    (args.output / 'evidence.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
