"""Native tooltip surface regression, using synthetic text."""
import os
import sys
import time
from pathlib import Path
import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtCore import QPoint, QAbstractAnimation
from PySide6.QtWidgets import QApplication, QLabel, QToolTip
from stats_style import initialize_theme


def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('background', ['transparent', '#000000', '#FFFFFF'])
def test_native_tooltip_opaque_despite_transparent_source_style(background):
    application = app()
    initialize_theme(application)
    source = QLabel('source')
    source.setStyleSheet(f'color:#65758B;background:{background};')
    source.show()
    QToolTip.showText(QPoint(50, 50), '公共交通 52.32%', source)
    application.processEvents()
    tip = next(w for w in application.topLevelWidgets() if w.objectName() == 'qtooltip_label')
    pixel = tip.grab().toImage().pixelColor(10, 10)
    QToolTip.hideText()
    source.close()
    assert pixel.alpha() == 255 and pixel.lightness() > 240


def test_native_tip_resets_emphasized_source_font_and_color():
    from PySide6.QtGui import QFont, QPalette
    application=app();initialize_theme(application)
    source=QLabel('指标');source.setStyleSheet('font-size:28px;font-weight:600;color:#18314F;')
    source.show();QToolTip.showText(QPoint(80,80),'早高峰（07:30-09:30）平均间隔',source)
    application.processEvents()
    tip=next(w for w in application.topLevelWidgets() if w.objectName()=='qtooltip_label')
    assert tip.font().weight()==QFont.Weight.Normal
    assert tip.font().pixelSize()==12
    assert tip.palette().color(QPalette.ColorRole.WindowText).name()=='#1b1b1b'
    pixels=tip.grab().toImage()
    assert sum(pixels.pixelColor(x,y).lightness()<100 for x in range(10,pixels.width()-10)
               for y in range(6,pixels.height()-6))>20
    QToolTip.hideText();source.close()


@pytest.mark.parametrize('kind', ['normal', 'item-view'])
def test_fluent_tip_uses_same_regular_font_and_neutral_color(kind):
    from PySide6.QtGui import QFont, QPalette
    from qfluentwidgets import ToolTip
    from qfluentwidgets.components.widgets.tool_tip import ItemViewToolTip
    application=app();initialize_theme(application)
    source=QLabel('指标');source.setStyleSheet('font-size:28px;font-weight:600;color:#18314F;')
    tip=(ToolTip if kind == 'normal' else ItemViewToolTip)(
        '发班序号：第1班\n完整时刻：00:00\n车型：小型',source)
    tip.show();application.processEvents()
    assert tip.label.font().weight()==QFont.Weight.Normal
    assert tip.label.font().pixelSize()==12
    assert tip.label.palette().color(QPalette.ColorRole.WindowText).name()=='#1b1b1b'
    background = tip.container.grab().toImage().pixelColor(5, 5)
    assert background.name() == '#ffffff' and background.alpha() == 255
    tip.close();source.close()


def test_chart_tip_does_not_inherit_detailed_chart_emphasis():
    from PySide6.QtGui import QFont, QColor
    from chart_canvas import ChartCanvas
    from stats_typography import tooltip_font
    application=app();initialize_theme(application)
    class Painter:
        def __init__(self): self.font=None; self.pen=None; self.text=[]
        def setFont(self,font): self.font=font
        def setPen(self,pen): self.pen=pen
        def drawText(self,*args): self.text.append((args[-1],self.font,self.pen))
        def __getattr__(self,name): return lambda *args:None
    widget=ChartCanvas(detailed=True);widget.resize(500,300)
    painter=Painter()
    widget._paint_tooltip(painter,'2013-05-21',[(QColor('blue'),'公共交通','52.32 %','数据不完整')])
    assert len(painter.text)==4
    assert all(font.weight()==QFont.Weight.Normal and font.pixelSize()==12 for _,font,_ in painter.text)
    assert all(pen.name()=='#1b1b1b' for _,_,pen in painter.text)
    widget.close()


def test_long_native_tip_wraps_inside_width_limit():
    from PySide6.QtCore import QRect, Qt
    application=app();initialize_theme(application)
    source=QLabel('source');source.show()
    QToolTip.showText(QPoint(80,80),'平峰（05:30-07:30、09:30-17:00、19:30-24:00）平均间隔',source)
    application.processEvents()
    tip=next(w for w in application.topLevelWidgets() if w.objectName()=='qtooltip_label')
    assert tip.width()<=320
    needed=tip.fontMetrics().boundingRect(QRect(0,0,tip.width()-20,10000),Qt.TextFlag.TextWordWrap,tip.text()).height()
    assert tip.height()>=needed+14
    QToolTip.hideText();source.close()


@pytest.mark.parametrize('update', ['showText', 'setText'])
def test_visible_native_tip_reuse_resizes_and_resets_font(update):
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QFont
    from PySide6.QtTest import QTest
    application = app()
    initialize_theme(application)
    bold = QLabel('强调指标')
    bold.setStyleSheet('font-size:28px;font-weight:600;background:transparent;')
    normal = QLabel('普通指标')
    bold.show(); normal.show()
    application.processEvents()
    QToolTip.showText(QPoint(80, 80), '短提示', bold)
    QTest.qWait(30)
    tip = next(w for w in application.topLevelWidgets() if w.objectName() == 'qtooltip_label')
    initial_width = tip.width()
    long = '平峰（05:30-07:30、09:30-17:00、19:30-24:00）平均间隔；分时段运营线路的完整运营时间说明'
    try:
        for text, source in ((long, bold), ('普通提示', normal)):
            assert tip.isVisible()
            if update == 'showText':
                QToolTip.showText(QPoint(80, 80), text, source)
            else:
                tip.setFont(source.font())
                tip.setText(text)
            QTest.qWait(30)
            assert tip.isVisible() and tip.text() == text
            assert tip.font().weight() == QFont.Weight.Normal
            assert tip.font().pixelSize() == 12
            needed = tip.fontMetrics().boundingRect(
                QRect(0, 0, tip.width() - 20, 10000), Qt.TextFlag.TextWordWrap, text).height()
            assert tip.height() >= needed + 14
            assert tip.width() <= 320
            assert tip.width() > initial_width if text == long else tip.width() < 100
    finally:
        QToolTip.hideText(); bold.close(); normal.close()


@pytest.mark.parametrize('kind', ['normal', 'item-view'])
def test_fluent_short_tip_stays_on_one_line_and_long_tip_wraps(kind):
    from qfluentwidgets import ToolTip
    from qfluentwidgets.components.widgets.tool_tip import ItemViewToolTip
    application = app()
    initialize_theme(application)
    tip = (ToolTip if kind == 'normal' else ItemViewToolTip)('公共交通 52.32%')
    try:
        tip.show()
        application.processEvents()
        assert tip.label.width() >= tip.label.fontMetrics().horizontalAdvance(tip.text())
        assert tip.label.height() < 2 * tip.label.fontMetrics().lineSpacing()
        tip.hide()
        tip.setText('平峰（05:30-07:30、09:30-17:00、19:30-24:00）平均间隔；'
                    '晚高峰（17:00-19:30）平均间隔；分时段运营线路的完整运营时段说明')
        tip.show()
        application.processEvents()
        assert tip.label.width() <= 300
        assert tip.label.fontMetrics().horizontalAdvance(tip.text()) > 300
        assert tip.label.height() > tip.label.fontMetrics().lineSpacing()
        tip.hide()
        tip.setText('收起导航')
        tip.show()
        application.processEvents()
        assert tip.label.width() < 100
        assert tip.label.height() < 2 * tip.label.fontMetrics().lineSpacing()
    finally:
        tip.close()


def test_navigation_menu_tip_tracks_expanded_and_collapsed_states(tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    from PySide6.QtTest import QTest
    import desktop_app
    application = app()
    monkeypatch.setattr(desktop_app, 'QSettings', lambda *args: QSettings(
        str(tmp_path / 'navigation.ini'), QSettings.Format.IniFormat))
    window = desktop_app.MainWindow()
    try:
        panel = window.sidebar.panel
        def wait_navigation():
            deadline = time.monotonic() + 3
            while panel.expandAni.state() == QAbstractAnimation.State.Running and time.monotonic() < deadline:
                QTest.qWait(10)
            assert panel.expandAni.state() == QAbstractAnimation.State.Stopped
        panel.collapse()
        wait_navigation()
        assert panel.menuButton.toolTip() == '展开导航'
        panel.expand(useAni=False)
        application.processEvents()
        assert panel.menuButton.toolTip() == '收起导航'
        panel.collapse()
        wait_navigation()
        assert panel.menuButton.toolTip() == '展开导航'
        panel.expand()
        wait_navigation()
        assert panel.menuButton.toolTip() == '收起导航'
        panel.collapse()
        wait_navigation()
        assert panel.menuButton.toolTip() == '展开导航'
    finally:
        window.close()


@pytest.mark.parametrize('kind', ['normal', 'item-view'])
def test_fluent_visible_short_long_short_reuse_has_no_clipping(kind):
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QFont
    from PySide6.QtTest import QTest
    from qfluentwidgets import ToolTip
    from qfluentwidgets.components.widgets.tool_tip import ItemViewToolTip
    application = app(); initialize_theme(application)
    tip = (ToolTip if kind == 'normal' else ItemViewToolTip)('短提示')
    tip.show(); QTest.qWait(30)
    short_size = tip.size()
    try:
        for text in ('平峰（05:30-07:30、09:30-17:00、19:30-24:00）平均间隔；'
                     '晚高峰（17:00-19:30）平均间隔；分时段运营线路的完整运营时段说明', '短提示'):
            tip.setText(text); QTest.qWait(30)
            assert tip.isVisible()
            assert tip.label.font().pixelSize() == 12 and tip.label.font().weight() == QFont.Weight.Normal
            needed = tip.label.fontMetrics().boundingRect(
                QRect(0, 0, tip.label.width(), 10000), Qt.TextFlag.TextWordWrap, text).height()
            assert tip.label.height() >= needed
            assert tip.label.width() <= 300
            pixel = tip.container.grab().toImage().pixelColor(5, 5)
            assert pixel.name() == '#ffffff' and pixel.alpha() == 255
        assert tip.size() == short_size
    finally:
        tip.close()
