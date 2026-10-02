"""Check actual company chart geometry while resizing a two-company save."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QPoint, QSettings
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'docs' / 'ui-redesign'))
import capture_network_real_saves as real
from measure_one_screen import wait_for_visuals


def inspect(window, size, *, verbose=False):
    app = QApplication.instance()
    window.resize(*size)
    page = window.statistics_page
    real.wait_for(app, lambda: window.width() == size[0] and window.height() == size[1] and
                  page.scroll.viewport().width() == size[0] - 272,
                  f'company resize {size}', timeout=8)
    wait_for_visuals(app, page)
    viewport = page.scroll.viewport()
    groups = []
    for group in page.company_dashboard.groups.values():
        group_point = group.mapTo(viewport, QPoint())
        charts = []
        for panel in group.panels.values():
            point = panel.mapTo(viewport, QPoint())
            charts.append([point.x(), point.y(), panel.width(), panel.height(),
                           panel.minimumHeight(), panel.maximumHeight()])
        kpis = []
        for tile in group.kpis.values():
            point = tile.mapTo(viewport, QPoint())
            kpis.append([point.x(), point.y(), tile.width(), tile.height()])
        groups.append({'group_bounds': [group_point.x(), group_point.y(),
                                        group.width(), group.height()],
                       'group_height': group.height(),
                       'minimum_hint': group.minimumSizeHint().height(),
                       'chart_host_height': group.chart_host.height(),
                       'layout_items': [group.layout().itemAt(i).sizeHint().height()
                                        for i in range(group.layout().count())],
                       'layout_margins': [group.layout().contentsMargins().top(),
                                          group.layout().contentsMargins().bottom()],
                       'layout_spacing': group.layout().spacing(),
                       'chart_grid_spacing': group.chart_grid.spacing(),
                       'grid_geometry': [group.chart_grid.geometry().x(),
                                         group.chart_grid.geometry().y(),
                                         group.chart_grid.geometry().width(),
                                         group.chart_grid.geometry().height()],
                       'charts': charts, 'kpis': kpis})
    state = {'window': [window.width(), window.height()],
             'viewport': [viewport.width(), viewport.height()],
             'scroll': [page.scroll.horizontalScrollBar().maximum(),
                        page.scroll.verticalScrollBar().maximum()],
             'groups': groups}
    if verbose:
        print(json.dumps(state, ensure_ascii=False), flush=True)
    for group in groups:
        charts = group['charts']
        assert all(0 <= x and 0 <= y and x + w <= viewport.width() + 1 and
                   y + h <= viewport.height() + 1
                   for x, y, w, h in [group['group_bounds'], *group['kpis']]), state
        assert all(0 <= y and y + h <= viewport.height() + 1
                   for _, y, _, h, _, _ in charts), state
        rows = sorted(set(y for _, y, _, _, _, _ in charts))
        assert all(max(y + h for _, y, _, h, _, _ in charts if y == first) <= second
                   for first, second in zip(rows, rows[1:])), state
        assert group['minimum_hint'] <= group['group_height'] + 1, state
    assert state['scroll'] == [0, 0], state
    return state


def main():
    with tempfile.TemporaryDirectory(prefix='cim2-company-resize-') as temporary:
        temp = Path(temporary)
        runtime = temp / 'runtime'
        runtime.mkdir()
        shutil.copy2(real.ROOT / 'data' / 'UnityEngine.dll', runtime / 'UnityEngine.dll')
        real.desktop_app.RUNTIME_DATA = runtime
        real.desktop_app.JOBS = temp / 'jobs'
        real.desktop_app.MainWindow.check_install = lambda self: None
        real.desktop_app.QSettings = lambda *args: QSettings(
            str(temp / 'visual.ini'), QSettings.Format.IniFormat)
        app = QApplication.instance() or QApplication([])
        window = real.desktop_app.MainWindow()
        window.set_sidebar_collapsed(False)
        window.resize(1920, 1080)
        window.show()
        window.navigate(2)
        save = real.SAVES[1]
        digest = real.digest(save)
        window.start_parse(save)
        real.wait_for(app, lambda: bool(window.data) and
                      Path(window.data.get('save_path', '')).resolve() == save.resolve(),
                      'load two-company save')
        page = window.statistics_page
        real.wait_for(app, lambda: page.snapshot is not None and page.network_snapshot is not None,
                      'dashboard', timeout=60)
        window.navigate(2)
        page.tab_bar.setCurrentItem('company')
        page.analysis_mode_control.setCurrentKey('default')
        widths = list(range(1440, 2561, 16))
        sizes = [(width, round(960 + (width - 1440) * 480 / 1120))
                 for width in (*widths, *widths[-2::-1])]
        for index, size in enumerate(sizes):
            inspect(window, size, verbose=size == (1600, 1029))
            if index == 10:
                output = ROOT / 'docs' / 'ui-redesign' / 'evidence' / 'company-resize'
                output.mkdir(parents=True, exist_ok=True)
                assert window.grab().save(str(output / 'company-default-1600x1029.png'))
        print(json.dumps({'checked_resizes': len(sizes), 'first': sizes[0],
                          'last': sizes[-1]}, ensure_ascii=False), flush=True)
        assert real.digest(save) == digest
        window.close()


if __name__ == '__main__':
    main()
