"""Absent comparisons stay discoverable without consuming a card row."""
from decimal import Decimal


def test_missing_comparison_releases_row_and_recovers_valid_comparison():
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
    from card_comparison_label import ComparisonLabel
    from card_comparisons import CardComparison, change
    app = QApplication.instance() or QApplication([])
    card = QWidget(); layout = QVBoxLayout(card)
    value = QLabel('—', card); layout.addWidget(value)
    comparison = ComparisonLabel(parent=card, tooltip_target=value)
    layout.addWidget(comparison)
    missing = CardComparison(tooltip='基准缺少有效数据；缺测不补零')
    comparison.set_comparison(missing)
    card.show(); app.processEvents()
    assert comparison.isHidden() and layout.itemAt(1).isEmpty()
    assert not comparison.text() and value.text() == '—'
    assert value.toolTip() == value.accessibleDescription() == missing.tooltip
    comparison.set_comparison(change(Decimal(0), Decimal(0), '人', '较上日'))
    app.processEvents()
    assert not comparison.isHidden() and not layout.itemAt(1).isEmpty()
    assert '持平' in comparison.full_text
    comparison.set_comparison(missing); comparison.set_comparison(missing)
    assert value.toolTip() == missing.tooltip
    card.close()
