"""One-line applied filter context, with priority given to time and mode."""
from datetime import timedelta

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QLabel
from card_comparisons import baseline_window, baseline_label


def summary_window(window):
    if not window:
        return '未载入存档'
    start, end = window
    if end > start and all(not any((d.hour, d.minute, d.second, d.microsecond)) for d in window):
        last = end - timedelta(days=1)
        end_text = last.strftime('%m-%d' if start.year == last.year else '%Y-%m-%d')
        return f'{start:%Y-%m-%d}—{end_text}'
    precise = any(d.second or d.microsecond for d in window)
    def clock(value):
        return value.time().isoformat(timespec='auto' if precise else 'minutes')
    finish = clock(end) if start.date() == end.date() else f'{end:%Y-%m-%d} {clock(end)}'
    return f'{start:%Y-%m-%d} {clock(start)}—{finish}（结束不含）'


def card_baseline_text(filters):
    return f'卡片基准：{baseline_label(filters.start, filters.end).removeprefix("较")} {summary_window(baseline_window(filters.start, filters.end))}'


class CompactFilterSummary(QLabel):
    """Keep the complete accessible context while eliding the company first."""
    SEPARATOR = '    '

    def __init__(self, parent=None):
        super().__init__(parent)
        self._company = ''
        self._details = []
        self._full = ''
        self.visible_text = ''
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(False)

    def set_summary(self, company, details):
        self._company, self._details = company, list(details)
        self._full = self.SEPARATOR.join(part for part in [company, *details] if part)
        self.setAccessibleName(self._full)
        self._refresh()

    def text(self):
        return self._full

    def _refresh(self):
        metrics = self.fontMetrics()
        width = max(0, self.contentsRect().width())
        details = self.SEPARATOR.join(self._details)
        company = self._company
        if company:
            budget = width - metrics.horizontalAdvance(self.SEPARATOR + details)
            company = metrics.elidedText(company, Qt.TextElideMode.ElideRight, max(0, budget))
        joined = self.SEPARATOR.join(part for part in (company, details) if part)
        shown = metrics.elidedText(joined, Qt.TextElideMode.ElideRight, width)
        self.visible_text = shown
        super().setText(shown)
        if shown != joined:
            tip = self._full
        elif company != self._company:
            tip = self._company
        else:
            tip = ''
        self.setToolTip(tip)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.ApplicationFontChange) and hasattr(self, '_full'):
            self._refresh()
