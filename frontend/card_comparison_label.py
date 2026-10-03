"""Consistent, accessible comparison line below KPI values."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics, QTextDocument
from PySide6.QtWidgets import QLabel
from html import escape
import re
from card_comparisons import CardComparison
from stats_tokens import FONT_SIZE_CAPTION, TEXT_SECONDARY
from stats_typography import emphasis_html, emphasis_css, apply_emphasis_font


_AMOUNT = re.compile(r'[+-]?\d[\d,]*(?:\.\d+)?(?:\s*(?:万人|人次|货币|分钟|评分|百分点|%|点|辆|次|人|条|个|倍))?')


def _rich_text(text):
    parts, start = [], 0
    for match in _AMOUNT.finditer(text):
        parts.extend((escape(text[start:match.start()]), emphasis_html(match.group(), FONT_SIZE_CAPTION)))
        start = match.end()
    parts.append(escape(text[start:]))
    return ''.join(parts)


class ComparisonLabel(QLabel):
    def __init__(self, comparison=CardComparison(), parent=None, *, tooltip_target=None):
        super().__init__(parent)
        self.tooltip_target = tooltip_target
        self.setWordWrap(False)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setMinimumHeight(16)
        self.set_comparison(comparison)

    def set_comparison(self, comparison):
        self.comparison = comparison
        arrow = '↑ ' if comparison.direction > 0 else '↓ ' if comparison.direction < 0 else ''
        self.full_text = arrow + comparison.text if comparison.available else ''
        self.setToolTip(comparison.tooltip)
        if self.tooltip_target is not None:
            self.tooltip_target.setToolTip(comparison.tooltip)
            self.tooltip_target.setAccessibleDescription(comparison.tooltip)
        self.setVisible(comparison.available)
        self.setAccessibleName(self.full_text or comparison.tooltip)
        color = '#008660' if comparison.direction > 0 else '#C63845' if comparison.direction < 0 else TEXT_SECONDARY
        self.setStyleSheet(f'color:{color};{emphasis_css(FONT_SIZE_CAPTION, 400)}')
        apply_emphasis_font(self, FONT_SIZE_CAPTION, 400)
        self._update_text()

    def _update_text(self):
        document = QTextDocument()
        document.setDocumentMargin(0)
        document.setDefaultFont(self.font())
        def fits(text):
            document.setHtml(_rich_text(text))
            return document.idealWidth() <= self.width()
        text = self.full_text
        if self.width() > 0 and not fits(text):
            low, high = 0, len(text)
            while low < high:
                middle = (low + high + 1) // 2
                if fits(text[:middle] + '…'):
                    low = middle
                else:
                    high = middle - 1
            text = text[:low] + '…'
        self.setText(_rich_text(text))

    def minimumSizeHint(self):
        return QSize(0, max(16, QFontMetrics(self.font()).height()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_text()
