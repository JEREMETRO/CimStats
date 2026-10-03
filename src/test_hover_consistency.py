"""Hover regressions: rendered surface and copy, using synthetic values."""
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtCore import QPoint, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QToolTip
from chart_canvas import ChartCanvas, ChartData, Series
from city_dashboard import CityTile
from city_model import CityValue
from qfluentwidgets import FluentIcon
from stats_style import initialize_theme


def app():
    return QApplication.instance() or QApplication([])


class RecordingPainter:
    """Record text passed to the real donut layout/painting method."""
    def __init__(self):
        self.texts = []
    def drawText(self, *args):
        self.texts.append(args[-1])
    def __getattr__(self, name):
        return lambda *args: None


def test_percentage_donut_draws_one_precise_value_and_no_redundant_hover_share():
    app()
    widget = ChartCanvas()
    widget.resize(400, 190)
    widget.set_data(ChartData('donut', ['步行', '公共交通', '私家车'],
        [Series('share', '', QColor('#1677FF'), [26.26, 52.32, 21.42])], unit='%'))
    widget._hover_slice = '私家车'
    painter = RecordingPainter()
    widget._paint_donut(painter)
    assert painter.texts.count('21.42 %') == 1  # Compact legend hides values; hover shows it once.
    assert '21.4%' not in painter.texts
    assert '21.42' not in painter.texts
    widget.detailed = True
    widget._slices = []  # paintEvent clears the geometry before each real paint.
    painter = RecordingPainter()
    widget._paint_donut(painter)
    assert painter.texts.count('21.42 %') == 2  # Detailed legend and hover, once each.
    assert '21.4%' not in painter.texts
    widget.close()


def test_count_donut_keeps_value_and_share_with_hidden_denominator():
    app()
    widget = ChartCanvas()
    widget.resize(400, 190)
    widget.set_data(ChartData('donut', ['A', 'B'],
        [Series('share', '公司 [id-a]', QColor('#1677FF'), [30, 70])], unit='人次'))
    widget.set_hidden({'B'})
    widget._hover_slice = 'A'
    painter = RecordingPainter()
    widget._paint_donut(painter)
    assert '30.0%' in painter.texts and '30 人次' in painter.texts
    assert widget._slices[0]['percent'] == 30
    widget.close()


def test_city_card_preserves_missing_reason_and_date_once():
    app()
    tile = CityTile('人口', FluentIcon.PEOPLE, None)
    tile.set_value(CityValue('人口', None, '人', datetime(2024, 1, 1), False, '缺少有效观测'))
    assert tile.toolTip().count('缺少有效观测') == 1
    assert '2024-01-01 00:00' in tile.toolTip()
    assert '已记录部分；存在部分周期、缺测或未完成小时' not in tile.toolTip()
    tile.close()


def test_city_card_does_not_repeat_a_fully_visible_value_in_another_unit():
    app()
    tile = CityTile('人口', FluentIcon.PEOPLE, None)
    tile.resize(260, 150)
    tile.set_value(CityValue('人口', Decimal(120000), '人', datetime(2024, 1, 1), True))
    tile.show(); QApplication.processEvents(); tile.grab()
    assert '120,000' not in tile.toolTip() and '12 万人' not in tile.toolTip()
    assert '2024-01-01 00:00' in tile.toolTip()
    value_label = tile._baseline_pairs[0][0]
    value_label.setFixedWidth(8); QApplication.processEvents(); tile.grab()
    assert '120,000 人' in tile.toolTip()
    value_label.setFixedWidth(value_label.fontMetrics().horizontalAdvance(value_label.text()) + 2)
    QApplication.processEvents(); tile.grab()
    assert '120,000' not in tile.toolTip()
    tile.set_value(CityValue('人口', Decimal(123456), '人', datetime(2024, 1, 1), True))
    QApplication.processEvents(); tile.grab()
    assert '123,456 人' in tile.toolTip()  # The rounded 万人 display does not expose this exact count.
    tile.close()
    tile.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def test_network_company_identity_matches_statistics_format():
    from network_model import _display_name
    from network_charts import NetworkChartPanel
    names = {'id-a': '公交公司', 'id-b': '公交公司'}
    assert _display_name('id-a', names) == '公交公司 [id-a]'
    assert NetworkChartPanel._display_company(type('Panel', (), {'companies': names})(), 'id-b') == '公交公司 [id-b]'
