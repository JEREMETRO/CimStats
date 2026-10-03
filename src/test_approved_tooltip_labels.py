"""Approved first-batch text tooltips; synthetic identities."""
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor
from ui_kit import LegendChip, SeriesLegend
from app_shell import ElidedText
from statistics_page import CompanyTag


def test_full_and_elided_legends_follow_actual_paint_width():
    app = QApplication.instance() or QApplication([])
    for cls in (LegendChip, SeriesLegend):
        color = QColor('#1677FF')
        widget = cls('公共交通', [color] if cls is SeriesLegend else color)
        widget.resize(220, 22); widget.show(); app.processEvents()
        assert widget.toolTip() == ''
        widget.resize(42, 22); app.processEvents()
        assert widget.toolTip() == '公共交通'
        widget.resize(220, 22); app.processEvents()
        assert widget.toolTip() == ''
        assert widget.accessibleName() == '公共交通'
        widget.close()


def test_save_text_and_company_tag_only_explain_elision():
    app = QApplication.instance() or QApplication([])
    label = ElidedText('秋山市.save'); label.resize(300, 25); label.show(); app.processEvents()
    assert label.toolTip() == ''
    label.resize(35, 25); app.processEvents()
    assert label.toolTip() == '秋山市.save'
    label.resize(300, 25); app.processEvents()
    assert label.toolTip() == ''
    short = CompanyTag('公交', lambda: None)
    long = CompanyTag('滨海市公共交通运营有限公司', lambda: None)
    assert short.name_label.toolTip() == ''
    assert long.name_label.toolTip() == '滨海市公共交通运营有限公司'
    duplicate = CompanyTag('滨海市公共交通运营有限公司 [p1]', lambda: None, company_id='p1')
    assert duplicate.name_label.toolTip() == '滨海市公共交通运营有限公司\n公司标识：p1'
    duplicate.close()
    label.close(); short.close(); long.close()


def test_company_disambiguation_uses_only_missing_identity():
    app = QApplication.instance() or QApplication([])
    chip = SeriesLegend('公交公司', [QColor('#1677FF')])
    chip.set_company_identity('公交公司', 'p1')
    chip.resize(220, 22); chip.show(); app.processEvents()
    assert chip.toolTip() == '公司标识：p1'
    chip.resize(42, 22); app.processEvents()
    assert chip.toolTip() == '公交公司\n公司标识：p1'
    chip.setText('公交公司 [p1]'); chip.resize(220, 22); app.processEvents()
    assert chip.toolTip() == ''
    chip.close()
