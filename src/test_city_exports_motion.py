import os
from pathlib import Path
import sys
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtTest import QTest
from test_city_model import build, r


def test_city_export_keeps_energy_raw_display_and_current_preferences(tmp_path):
    from stats_exports import export_city_xlsx
    from openpyxl import load_workbook
    snapshot = build([r('energy-prices', 'electricity', 0, 50), r('trip-time', 'A', 0, 60, 2)])
    target = tmp_path / 'city.xlsx'
    export_city_xlsx(snapshot, target, {'mode': 'line', 'curves': ['平均'], 'hidden': {}})
    book = load_workbook(target, data_only=True)
    assert book['筛选']['B1'].value == '全市'
    assert book['显示状态']['B1'].value == 'line'
    rows = list(book['原始观测'].values)
    energy = next(row for row in rows[1:] if row[0] == 'energy-prices')
    assert energy[3:5] == (50, 0)
    points = list(book['城市图表'].values)
    assert any(row[0] == '能源价格' and row[5] == .5 and row[6] == '货币' for row in points[1:])
    book.close()


def test_motion_interruption_cleanup_and_reduced_motion(monkeypatch):
    from stats_motion import SurfaceMotion
    QApplication.instance() or QApplication([])
    widget = QWidget()
    widget.resize(300, 100)
    widget.show()
    motion = SurfaceMotion(widget)
    motion.reveal()
    QTest.qWait(40)
    effect = widget.graphicsEffect()
    motion.reveal()
    assert widget.graphicsEffect() is effect
    QTest.qWait(300)
    assert widget.graphicsEffect() is None and not motion.running
    monkeypatch.setattr('stats_motion.animations_enabled', lambda: False)
    motion.reveal()
    assert widget.graphicsEffect() is None and not motion.running
    widget.close()


def test_filter_reverse_starts_at_current_height_and_reuses_effect():
    from statistics_page import StatisticsPage
    QApplication.instance() or QApplication([])
    page = StatisticsPage()
    page.resize(1400, 960)
    page.show()
    QTest.qWait(30)
    page.set_filters_collapsed(True, animate=True)
    QTest.qWait(50)
    heights = (page.toolbar_host.maximumHeight(), page.compact_filter_bar.maximumHeight())
    effects = (page.toolbar_host.graphicsEffect(), page.compact_filter_bar.graphicsEffect())
    page.set_filters_collapsed(False, animate=True)
    assert heights == (page.toolbar_host.maximumHeight(), page.compact_filter_bar.maximumHeight())
    assert effects == (page.toolbar_host.graphicsEffect(), page.compact_filter_bar.graphicsEffect())
    QTest.qWait(350)
    assert not page._filter_animating and not page._filters_collapsed
    assert page.toolbar_host.graphicsEffect() is None
    page.close()
