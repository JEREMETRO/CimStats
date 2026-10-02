"""Capture real-save Fluent scrollbars and shared card switch styling."""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'docs' / 'ui-redesign'))
import capture_network_real_saves as real
from measure_one_screen import wait_for_visuals
from stats_controls import StatisticsScrollArea


def main():
    output = ROOT / 'docs' / 'ui-redesign' / 'evidence' / 'scroll-style'
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cim2-scroll-style-') as temporary:
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
        window.resize(1440, 960)
        window.show()
        window.navigate(2)
        save = real.SAVES[1]
        original = real.digest(save)
        window.start_parse(save)
        real.wait_for(app, lambda: bool(window.data) and
                      Path(window.data.get('save_path', '')).resolve() == save.resolve(),
                      'load two-company save')
        page = window.statistics_page
        real.wait_for(app, lambda: page.snapshot is not None and page.network_snapshot is not None,
                      'dashboard', timeout=60)
        window.navigate(2)
        assert all(isinstance(scroll, StatisticsScrollArea)
                   for scroll in (page.scroll, page.network_scroll, page.city_scroll))
        page.tab_bar.setCurrentItem('network')
        for mode in ('overall', 'companies', 'period'):
            page.network_mode_control.setCurrentKey(mode)
            real.wait_for(app, lambda mode=mode: page.network_snapshot is not None and
                          page.network_snapshot.options.mode == mode,
                          f'network {mode}', timeout=60)
            wait_for_visuals(app, page)
            controls = [tile.option_control for card in page.network_dashboard.summary_cards
                        for tile in card.tiles if tile.option_control is not None]
            controls += [control for group in page.network_dashboard.chart_controls.values()
                         for control in group]
            assert controls and all(control._subtle for control in controls)
            assert window.grab().save(str(output / f'network-{mode}-1440x960.png'))
            if mode == 'period':
                page.set_filters_collapsed(True)
                wait_for_visuals(app, page)
                assert page.network_scroll.verticalScrollBar().maximum() > 0
                assert page.network_scroll.scrollDelagate.vScrollBar.isVisible()
                assert window.grab().save(str(output / 'network-period-collapsed-1440x960.png'))
                page.set_filters_collapsed(False)
        page.tab_bar.setCurrentItem('city')
        page.analysis_mode_control.setCurrentKey('default')
        wait_for_visuals(app, page)
        assert page.city_scroll.verticalScrollBar().maximum() > 0
        assert page.city_scroll.scrollDelagate.vScrollBar.isVisible()
        assert window.grab().save(str(output / 'city-default-1440x960.png'))
        assert real.digest(save) == original
        window.close()
        print('captured 5 real-save scrollbar and switch screenshots', flush=True)


if __name__ == '__main__':
    main()
