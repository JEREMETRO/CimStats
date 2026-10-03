"""In-window chart expansion and read-only company/period summaries."""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from PySide6.QtCore import QEvent, QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtGui import QFontMetricsF
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout,
                               QMainWindow, QVBoxLayout, QWidget)
from shiboken6 import isValid

from statistics_model import summarize_buckets
from stats_text import group_label
from stats_typography import apply_emphasis_font, emphasis_css
import stats_tokens as tokens
import stats_motion


class InlineChartDetail(QFrame):
    """White child surface: expand from the source card, then return in place."""
    finished = Signal()

    def __init__(self, source):
        window = source.window()
        host = window.centralWidget() if isinstance(window, QMainWindow) else window
        super().__init__(host, Qt.WindowType.Widget)
        self.source = source
        self.panel = None
        self.animation = None
        self._elevation_layer = None
        self._returning = False
        self._returned = True
        self.adopt_on_return = True
        self.setObjectName('inlineChartDetail')
        self.setProperty('chartDetailSurface', True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(f'QFrame#inlineChartDetail {{ background:{tokens.CARD_BG};border:0; }}')
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(tokens.SPACE_LG, tokens.SPACE_LG, tokens.SPACE_LG, tokens.SPACE_LG)
        host.installEventFilter(self)
        source.installEventFilter(self)
        source.destroyed.connect(self._source_destroyed)
        self.hide()

    def set_panel(self, panel):
        self.panel = panel
        # Early frames are smaller than a readable detail layout. Clip the
        # natural panel instead of forcing fixed summary rows over the canvas.
        panel.setMinimumHeight(max(panel.minimumHeight(), panel.minimumSizeHint().height()))
        self.layout().addWidget(panel)

    def _source_rect(self):
        host = self.parentWidget()
        if not isValid(self.source):
            return self.geometry()
        rect = QRect(self.source.mapTo(host, QPoint()), self.source.size()).intersected(host.rect())
        return rect if not rect.isEmpty() else host.rect()

    def expand(self):
        for sibling in self.parentWidget().findChildren(InlineChartDetail,
                options=Qt.FindChildOption.FindDirectChildrenOnly):
            if sibling is not self and sibling.isVisible():
                sibling.cancel()
        self._returning = False
        self._returned = False
        self.adopt_on_return = True
        self.setGeometry(self._source_rect())
        self.show()
        # This surface already owns the entry transition; settle the card's
        # shared Show reveal so geometry motion does not also fade its content.
        self.panel.surface_motion.finish()
        # The shared shadow carrier is above the central widget. Covered page
        # shadows must not paint over this detail while hover fades settle.
        layer = getattr(self.window(), '_fluent_elevation_layer', None)
        if layer is not None and isValid(layer) and layer.isVisible():
            self._elevation_layer = layer
            layer.hide()
        self.raise_()
        self.panel.fullscreen_button.setFocus(Qt.FocusReason.OtherFocusReason)
        self._transition(self.parentWidget().rect(), expanding=True)

    def _stop_animation(self):
        if self.animation is not None:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None

    def _transition(self, end, *, expanding):
        self._stop_animation()
        if not stats_motion.animations_enabled() or self.geometry() == end:
            self.setGeometry(end)
            self._transition_finished()
            return
        animation = QPropertyAnimation(self, b'geometry', self)
        animation.setDuration(220 if expanding else 167)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic if expanding else QEasingCurve.Type.InCubic)
        animation.setStartValue(self.geometry())
        animation.setEndValue(end)
        animation.finished.connect(self._transition_finished)
        self.animation = animation
        animation.start()

    def _transition_finished(self):
        self._stop_animation()
        if self._returning:
            self._complete_return()
        else:
            self.setGeometry(self.parentWidget().rect())

    def _complete_return(self):
        if self._returned:
            return
        self._returned = True
        self._stop_animation()
        self.hide()
        layer = self._elevation_layer
        self._elevation_layer = None
        if layer is not None and isValid(layer):
            layer.show()
            layer.refresh()
        self.finished.emit()
        if self.adopt_on_return and isValid(self.source) and self.source.isVisible():
            self.source.fullscreen_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def cancel(self):
        """Source/host replacement is cancellation, not stale selection adoption."""
        self.adopt_on_return = False
        self._complete_return()

    def _source_destroyed(self):
        self.cancel()
        self.deleteLater()

    def closeEvent(self, event):
        if self._returned:
            event.accept()
        else:
            event.ignore()
            if not self._returning:
                self._returning = True
                self._transition(self._source_rect(), expanding=False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
        else:
            super().keyPressEvent(event)

    def focusNextPrevChild(self, forward):
        # The covered page remains alive for state/scroll preservation, but its
        # controls must not enter the active detail's keyboard traversal.
        candidates = []
        widget = self.nextInFocusChain()
        while widget is not self:
            if (self.isAncestorOf(widget) and widget.isVisible() and widget.isEnabled()
                    and widget.focusPolicy() & Qt.FocusPolicy.TabFocus):
                candidates.append(widget)
            widget = widget.nextInFocusChain()
        if not candidates:
            self.setFocus()
            return True
        current = self.focusWidget()
        index = candidates.index(current) if current in candidates else (-1 if forward else 0)
        candidates[(index + (1 if forward else -1)) % len(candidates)].setFocus(
            Qt.FocusReason.TabFocusReason if forward else Qt.FocusReason.BacktabFocusReason)
        return True

    def hideEvent(self, event):
        if not self._returned:
            self.cancel()
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize and not self._returned:
            end = self._source_rect() if self._returning else watched.rect()
            if self.animation is not None:
                self.animation.setEndValue(end)
            else:
                self.setGeometry(end)
        elif watched is self.source and event.type() == QEvent.Type.Hide:
            self.cancel()
        return super().eventFilter(watched, event)


def exact_number(value):
    if value is None:
        return '—'
    text = format(value, ',f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def summary_cards(result, companies, comparison_label='对比', company_name=None):
    if result is None:
        return []
    cards = []
    for previous, source, window in ((False, result.series, result.current_window),
                                     (True, result.comparison, result.comparison_window)):
        grouped = defaultdict(list)
        for (company, group), buckets in source.items():
            value = summarize_buckets(buckets, result.metric) if result.metric.confirmed else None
            grouped[company].append((group, value))
        for company, values in grouped.items():
            name = (company_name(company) if company_name else
                    companies.get(company, {'__selected__': '已选公司', '': '整体'}.get(company, company)))
            card = dict(company=company, name=name, period=comparison_label if previous else '本期',
                        window=window, values=values, unit=result.metric.unit, kind=result.metric.kind)
            if result.metric.kind == 'flow':
                # Missing categories cannot count as zero in a company mean.
                periods = [{(bucket.start, bucket.end): bucket.value for bucket in buckets}
                           for (owner, _), buckets in source.items() if owner == company]
                dates = set().union(*(set(items) for items in periods))
                totals = [sum((items[date] for items in periods), Decimal(0))
                          for date in sorted(dates)
                          if all(items.get(date) is not None for items in periods)]
                average = (sum(totals, Decimal(0)) / len(totals)
                           if totals and result.metric.confirmed else None)
                total = (sum((value for _, value in values), Decimal(0))
                         if all(value is not None for _, value in values) else None)
                label = {'transport-by-type': '客流', 'transport-by-group': '客流',
                         'trip-types': '出行量'}.get(result.query.metric, result.metric.label)
                caption = {'hour': '小时', 'day': '日', 'week': '周', 'month': '月'}[result.query.grain] + '均' + label
                card.update(grain_average=average, average_periods=len(totals),
                            display_values=[('区间' + label, total),
                                            (caption, average.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                                             if average is not None else None)])
            cards.append(card)
    return cards


class DetailSummary(QFrame):
    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._summary_layout = QHBoxLayout(self)
        self._summary_layout.setContentsMargins(0, 0, 0, 0)
        self.cards = []
        self._surfaces = []
        self._reflowing = False
        self.hide()

    def refresh(self):
        compare = self.panel._comparison_name()
        self.cards = summary_cards(self.panel.result, self.panel.companies, compare,
                                   getattr(self.panel, '_display_company', None))
        while self._summary_layout.count():
            item = self._summary_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self._body = QWidget(self)
        self._cards_layout = QGridLayout(self._body)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(10)
        self._surfaces = []
        for card in self.cards:
            display_values = card.get('display_values', card['values'])
            surface = QFrame(self._body)
            surface.setObjectName('detailSummaryCard')
            surface.setMinimumWidth(0)
            surface.setStyleSheet(f'QFrame#detailSummaryCard {{background:{tokens.CARD_BG};'
                                 f'border:1px solid {tokens.BORDER};border-radius:8px;}}')
            box = QVBoxLayout(surface)
            box.setContentsMargins(10, 6, 10, 6)
            box.setSpacing(1)
            heading = QLabel(card['name'] + (' · ' + card['period'] if self.panel.result.comparison else ''), surface)
            heading.setWordWrap(True)
            heading.setStyleSheet(emphasis_css(14) + f'color:{tokens.TEXT_PRIMARY};border:0;')
            apply_emphasis_font(heading, 14)
            if card['window']:
                start, end = card['window']
                heading.setToolTip(f'{start:%Y-%m-%d %H:%M} 至 {end:%Y-%m-%d %H:%M}')
            box.addWidget(heading)
            values = QGridLayout()
            values.setSpacing(18)
            cells = []
            for group, value in display_values:
                cell = QVBoxLayout()
                cell.setSpacing(0)
                if len(display_values) > 1 or group not in ('总计', '__total__', ''):
                    caption = QLabel(group_label(group), surface)
                    caption.setStyleSheet(f'font-size:12px;color:{tokens.TEXT_SECONDARY};border:0;')
                    cell.addWidget(caption)
                number_row = QHBoxLayout()
                number_row.setSpacing(4)
                number = QLabel(exact_number(value), surface)
                number.setObjectName('detailSummaryNumber')
                number.setStyleSheet(emphasis_css(tokens.FONT_SIZE_KPI) + f'color:{tokens.TEXT_PRIMARY};border:0;')
                apply_emphasis_font(number, tokens.FONT_SIZE_KPI)
                number_row.addWidget(number, 0, Qt.AlignmentFlag.AlignBottom)
                unit = QLabel(card['unit'], surface)
                unit.setObjectName('detailSummaryUnit')
                unit.setStyleSheet(f'font-size:12px;color:{tokens.TEXT_SECONDARY};border:0;')
                number.ensurePolished()
                unit.ensurePolished()
                number.setMinimumWidth(number.sizeHint().width())
                unit.setMinimumWidth(unit.sizeHint().width())
                number_metrics = QFontMetricsF(number.font())
                unit_metrics = QFontMetricsF(unit.font())
                baseline_offset = round(number_metrics.descent() - unit_metrics.descent()
                                        + (number_metrics.leading() - unit_metrics.leading()) / 2)
                unit.setContentsMargins(0, 0, 0, max(0, baseline_offset))
                number_row.addWidget(unit, 0, Qt.AlignmentFlag.AlignBottom)
                number_row.addStretch()
                cell.addLayout(number_row)
                cells.append(cell)
            box.addLayout(values)
            surface.setMinimumHeight(80)
            desired = 240 if len(display_values) == 1 else 320
            if 'display_values' in card:
                desired = max(desired, min(420, 2 + len(cells) *
                                           (max(cell.minimumSize().width() for cell in cells) + 18)))
            self._surfaces.append((surface, values, cells, desired))
        self._summary_layout.addWidget(self._body)
        self._reflow_cards()
        self.setVisible(bool(self.cards))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_cards()

    def _reflow_cards(self):
        if self._reflowing or not self._surfaces:
            return
        self._reflowing = True
        try:
            available = max(160, self.panel.width() - 32)
            desired = max(entry[3] for entry in self._surfaces)
            columns = max(1, min(len(self._surfaces), (available + 10) // (desired + 10)))
            width = min(desired, (available - (columns - 1) * 10) // columns)
            layout = self._cards_layout
            while layout.count():
                layout.takeAt(0)
            for index, (surface, values, cells, _) in enumerate(self._surfaces):
                surface.setFixedWidth(width)
                while values.count():
                    values.takeAt(0)
                cell_width = max(cell.minimumSize().width() for cell in cells)
                value_columns = max(1, min(len(cells), (width - 20 + 18) // max(1, cell_width + 18)))
                for number, cell in enumerate(cells):
                    values.addLayout(cell, number // value_columns, number % value_columns)
                values.invalidate()
                surface.layout().invalidate()
                surface.layout().activate()
                surface.updateGeometry()
                layout.addWidget(surface, index // columns, index % columns,
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            for column in range(len(self._surfaces) + 1):
                layout.setColumnStretch(column, 0)
            layout.setColumnStretch(columns, 1)
            layout.invalidate()
            layout.activate()
            self.setFixedHeight(self._body.sizeHint().height())
        finally:
            self._reflowing = False
