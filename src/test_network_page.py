import os
import sys
import time
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from statistics_page import StatisticsPage
from test_dashboard_page import session
from test_network_dashboard import FakePanel


def _wait(app, condition):
    deadline = time.monotonic() + 15
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert condition()
    app.processEvents()


def test_network_modes_use_same_snapshot_and_keep_company_mode_isolated(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr('network_dashboard.NetworkDashboard._make_chart_panel',
                        lambda self, parent: FakePanel(parent))
    page = StatisticsPage(QSettings(str(tmp_path / 'network.ini'), QSettings.Format.IniFormat))
    page.set_session(session())
    _wait(app, lambda: page.snapshot is not None)
    source = page.snapshot
    page.tab_bar.setCurrentItem('network')
    _wait(app, lambda: len(page.network_dashboard.chart_panels) == 7)
    assert page.snapshot is source
    assert page.network_snapshot.options.mode == 'overall'
    page.network_mode_control.setCurrentKey('companies')
    _wait(app, lambda: page.network_snapshot is not None and
          page.network_snapshot.options.mode == 'companies')
    assert len(page.network_dashboard.chart_panels) == 9
    assert page.snapshot is source
    page.network_mode_control.setCurrentKey('period')
    _wait(app, lambda: page.snapshot is not None and
          page.snapshot.filters.comparison is not None and
          len(page.network_dashboard.chart_panels) == 16)
    assert page.analysis_mode == 'default'
    page.tab_bar.setCurrentItem('company')
    _wait(app, lambda: page.snapshot is not None and page.snapshot.filters.comparison is None)
    assert page.network_options.mode == 'period'
    assert page.analysis_mode_control.currentKey() == 'default'
    page.close()


def test_network_route_uses_real_chart_panels(tmp_path):
    from network_charts import NetworkChartPanel

    app = QApplication.instance() or QApplication([])
    page = StatisticsPage(QSettings(str(tmp_path / 'real.ini'), QSettings.Format.IniFormat))
    page.set_session(session())
    _wait(app, lambda: page.snapshot is not None)
    page.tab_bar.setCurrentItem('network')
    _wait(app, lambda: len(page.network_dashboard.chart_panels) == 7)
    assert all(isinstance(panel, NetworkChartPanel)
               for panel in page.network_dashboard.chart_panels.values())
    assert page.export_target() is page.network_dashboard
    page.close()


def test_network_companies_mode_survives_selection_dropping_to_one(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr('network_dashboard.NetworkDashboard._make_chart_panel',
                        lambda self, parent: FakePanel(parent))
    page = StatisticsPage(QSettings(str(tmp_path / 'fallback.ini'), QSettings.Format.IniFormat))
    page.set_session(session())
    _wait(app, lambda: page.snapshot is not None)
    page.tab_bar.setCurrentItem('network')
    _wait(app, lambda: len(page.network_dashboard.chart_panels) == 7)
    page.network_mode_control.setCurrentKey('companies')
    _wait(app, lambda: page.network_snapshot is not None and
          page.network_snapshot.options.mode == 'companies')
    page.company_menu.actions()[1].setChecked(False)
    assert page.network_mode_control.currentKey() == 'companies'
    _wait(app, lambda: page.network_snapshot is not None and
          page.network_snapshot.options.mode == 'companies' and
          page.network_snapshot.filters.companies == ('a',))
    assert len(page.network_dashboard.chart_panels) == 9
    page.close()


def test_summary_basis_change_rebuilds_model_without_requerying_history(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr('network_dashboard.NetworkDashboard._make_chart_panel',
                        lambda self, parent: FakePanel(parent))
    page = StatisticsPage(QSettings(str(tmp_path / 'basis.ini'), QSettings.Format.IniFormat))
    page.set_session(session())
    _wait(app, lambda: page.snapshot is not None)
    page.tab_bar.setCurrentItem('network')
    _wait(app, lambda: len(page.network_dashboard.chart_panels) == 7)
    source = page.snapshot
    page.network_dashboard.summary_cards[0].tiles[2].option_control.setCurrentKey('maximum')
    _wait(app, lambda: page.network_snapshot is not None and
          page.network_snapshot.options.vehicle == 'maximum')
    assert page.snapshot is source
    assert len(page.network_dashboard.chart_panels) == 7
    assert page.network_snapshot.summaries[0].values[2].value is None
    assert page.network_snapshot.summaries[0].values[2].reason == '车辆需求数据不完整'
    assert next(c for c in page.network_snapshot.charts if c.key == 'vehicles-running').result is not None
    page.close()


def test_network_png_exports_complete_scroll_content(tmp_path):
    from PySide6.QtGui import QImageReader
    from stats_exports import export_png

    app = QApplication.instance() or QApplication([])
    page = StatisticsPage(QSettings(str(tmp_path / 'png.ini'), QSettings.Format.IniFormat))
    page.resize(1320, 800)
    page.show()
    page.set_session(session())
    _wait(app, lambda: page.snapshot is not None)
    page.tab_bar.setCurrentItem('network')
    _wait(app, lambda: len(page.network_dashboard.chart_panels) == 7)
    path = tmp_path / 'network.png'
    export_png(page.export_target(), path)
    size = QImageReader(str(path)).size()
    assert size.width() >= page.network_scroll.viewport().width()
    assert size.height() >= page.network_scroll.viewport().height()
    assert size.height() >= page.network_dashboard.height()
    page.close()
