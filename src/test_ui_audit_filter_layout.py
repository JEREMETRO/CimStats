import pytest
from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from statistics_page import StatisticsPage

@pytest.mark.parametrize('width',[960,1100,1436])
def test_shared_filter_columns_stay_aligned_across_tabs(qt_application,width):
    page=StatisticsPage();page.resize(width,680);page.show();QTest.qWait(50)
    try:
        original=[(field.mapTo(page.filter_card,QPoint()).x(),field.width()) for field in page._fields[:3]]
        page.tab_bar.setCurrentItem('network');QTest.qWait(50)
        actual=[(field.mapTo(page.filter_card,QPoint()).x(),field.width()) for field in page._fields[:3]]
        assert actual==original
        page.network_mode_control.setCurrentKey('period');QTest.qWait(50)
        assert [(field.mapTo(page.filter_card,QPoint()).x(),field.width()) for field in page._fields[:3]]==original
    finally:
        page.close();page.deleteLater()

def test_960_shell_width_uses_one_primary_filter_row(qt_application):
    page=StatisticsPage();page.resize(864,552);page.show();QTest.qWait(50)
    try:
        positions=[page.toolbar_grid.getItemPosition(page.toolbar_grid.indexOf(f))[0] for f in page._fields[:4]]
        assert positions==[0,0,0,0]
    finally:
        page.close();page.deleteLater()
