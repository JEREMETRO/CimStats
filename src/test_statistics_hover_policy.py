import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QWidget, QPushButton, QApplication
from PySide6.QtTest import QTest
from qfluentwidgets import ToolTipFilter
from statistics_page import StatisticsPage
from stats_charts import ChartPanel

def test_statistics_non_chart_hover_policy_covers_dynamic_children(qt_application):
    page=StatisticsPage()
    page.resize(1100,700); page.show(); qt_application.processEvents()
    outside=QPushButton('other page');outside.setToolTip('keep outside')
    button=QPushButton('dynamic action',page.filter_body)
    button.setAccessibleName('dynamic action');button.setToolTip('full identity')
    fluent=ToolTipFilter(button,showDelay=1);button.installEventFilter(fluent)
    chart=ChartPanel('chart',parent=page)
    chart_button=QPushButton('chart action',chart)
    chart_button.setToolTip('keep chart')
    try:
        qt_application.processEvents()
        assert button.toolTip()==''
        assert button.accessibleName()=='dynamic action'
        assert button.accessibleDescription()=='full identity'
        QApplication.sendEvent(button,QEvent(QEvent.Type.Enter));QTest.qWait(10)
        assert not fluent.timer.isActive()
        QApplication.sendEvent(button,QHelpEvent(QEvent.Type.ToolTip,QPoint(1,1),button.mapToGlobal(QPoint(1,1))))
        assert fluent._tooltip is None or not fluent._tooltip.isVisible()
        button.setToolTip('refreshed value')
        assert button.toolTip()==''
        assert chart_button.toolTip()=='keep chart'
        assert outside.toolTip()=='keep outside'
    finally:
        page.close();page.deleteLater();outside.close()

def test_shared_header_tooltips_return_when_leaving_statistics(qt_application):
    from PySide6.QtWidgets import QStackedWidget, QVBoxLayout
    host=QWidget();box=QVBoxLayout(host)
    host.header=QWidget(host);button=QPushButton('open',host.header);button.setToolTip('open archive')
    box.addWidget(host.header)
    host.pages=QStackedWidget(host);box.addWidget(host.pages)
    other=QWidget();host.pages.addWidget(other)
    page=StatisticsPage();host.pages.addWidget(page)
    host.show();host.pages.setCurrentWidget(page);qt_application.processEvents()
    try:
        QApplication.sendEvent(button,QEvent(QEvent.Type.Enter))
        assert button.toolTip()==''
        host.pages.setCurrentWidget(other);qt_application.processEvents()
        assert button.toolTip()=='open archive'
    finally:
        host.close();host.deleteLater()
