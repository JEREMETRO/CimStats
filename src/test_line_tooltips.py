"""Approved line-query tooltips only supply text lost to clipping."""
import os,sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from PySide6.QtCore import QEvent
from PySide6.QtGui import QHelpEvent
from qfluentwidgets import TableWidget
from stats_style import initialize_theme


def test_line_filter_only_tips_when_text_does_not_fit():
    from line_query_page import LineFilterComboBox
    app=QApplication.instance() or QApplication([]);initialize_theme(app)
    widget=LineFilterComboBox();widget.addItems(['公交','滨海市公共交通运营有限公司'])
    widget.resize(150,36);widget.show();app.processEvents()
    assert widget.toolTip()==''
    widget.setCurrentIndex(1);app.processEvents()
    assert widget.toolTip()=='滨海市公共交通运营有限公司'
    widget.resize(450,36);app.processEvents()
    assert widget.toolTip()==''
    widget.close()


def test_table_suppresses_full_text_but_keeps_truncated_text():
    from line_query_page import ElisionOnlyTableTooltips
    app=QApplication.instance() or QApplication([]);initialize_theme(app)
    table=TableWidget();table.setRowCount(1);table.setColumnCount(1)
    table.resize(230,130);table.setColumnWidth(0,160)
    guard=ElisionOnlyTableTooltips(table)
    table.viewport().installEventFilter(guard)
    item=QTableWidgetItem('1路');item.setToolTip('1路');table.setItem(0,0,item)
    table.show();app.processEvents()
    def help_event():
        point=table.visualItemRect(item).center()
        return QHelpEvent(QEvent.Type.ToolTip,point,table.viewport().mapToGlobal(point))
    assert guard.eventFilter(table.viewport(),help_event()) is True
    item.setText('秋山市机场至市中心公共交通线路');item.setToolTip(item.text())
    assert guard.eventFilter(table.viewport(),help_event()) is False
    table.resize(600,130);table.setColumnWidth(0,540);app.processEvents()
    assert guard.eventFilter(table.viewport(),help_event()) is True
    assert item.toolTip()==item.text()  # Source data remains available.
    table.close()


def test_line_labels_reveal_only_clipped_text_and_preserve_special_reasons():
    from line_query_page import FullTextLabel, SelectionSummaryLabel, MetricValueLabel
    app=QApplication.instance() or QApplication([])
    for cls, text in ((FullTextLabel, '1路 · 八连交通集团'),
                      (SelectionSummaryLabel, '选中：1路'), (MetricValueLabel, '75.00 min')):
        label=cls(text);label.resize(300,30);label.show();app.processEvents()
        assert label.toolTip()==''
        label.resize(25,30);app.processEvents()
        assert label.toolTip()==text
        label.resize(300,30);app.processEvents()
        assert label.toolTip()=='' and label.accessibleName()==text
        label.setToolTip('运行日未确认：2班');label.resize(25,30);app.processEvents()
        assert label.toolTip()=='运行日未确认：2班'
        label.close()


def test_wrapped_garage_name_tips_only_when_height_clips_it():
    from line_query_page import CompactFactCard
    app=QApplication.instance() or QApplication([])
    card=CompactFactCard(('线路车库','八连交通集团公交车库1'))
    card.resize(250,86);card.show();app.processEvents()
    assert card.value.toolTip()==''
    card.resize(85,86);app.processEvents()
    assert card.value.toolTip()==card.value.text()
    card.resize(250,86);app.processEvents()
    assert card.value.toolTip()==''
    card.close()


def test_secondary_metric_explanation_does_not_leak_to_primary_or_card():
    from line_query_page import CompactFactCard
    app=QApplication.instance() or QApplication([])
    card=CompactFactCard(('今日客流',100),('平均客流',80),tooltip='自开线以来的日均客流')
    card.resize(300,86);card.show();app.processEvents()
    assert card.toolTip()=='' and card.value.toolTip()=='' and card.label.toolTip()==''
    assert card.note_label.toolTip()==card.note_value.toolTip()=='自开线以来的日均客流'
    card.close()
