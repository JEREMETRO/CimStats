"""Fluent network chart cards driven by NetworkChart and NetworkSnapshot."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCharts import (QBarCategoryAxis, QHorizontalBarSeries, QBarSet,
                              QLineSeries, QPieSeries, QValueAxis)
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractButton, QDialog, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout,
                               QLabel, QSizePolicy, QToolTip, QVBoxLayout, QWidget)
from qfluentwidgets import TransparentTogglePushButton

from stats_charts import ChartPanel, _number, nice_axis
from stats_text import group_label
from stats_controls import FluentSegmentedControl
from chart_details import network_display_group
from statistics_model import summarize_buckets
import stats_tokens as tokens
import stats_motion as motion_policy

_COMPACT_CATEGORY_NAMES = {
    'bus': '公交', 'tram': '有轨', 'trolley': '无轨',
    'metro': '地铁', 'waterbus': '水上', 'misc': '其他',
    'BlueCollar': '蓝领', 'WhiteCollar': '白领',
    'BusinessPeople': '商务', 'Pensioner': '退休',
    'Student': '学生', 'Tourist': '游客',
    'single-line': '单线', 'one-zone': '一区',
    'two-zones': '二区', 'three-zones': '三区',
    'four-zones': '四区',
}


class _CompactLegendButton(QAbstractButton):
    """Keep the color dot and both Chinese characters inside a 43 px cell."""

    def __init__(self, color: QColor, short_name: str, parent=None):
        super().__init__(parent)
        self._color = color
        self._short_name = short_name
        self.setFixedSize(43, 18)
        self.setCheckable(True)
        self.setChecked(True)
        font = QFont(tokens.FONT_FAMILY)
        font.setPixelSize(11)
        self.setFont(font)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.underMouse():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens.ACCENT_SOFT))
            painter.drawRoundedRect(self.rect(), 4, 4)
        dot = QColor(self._color)
        if not self.isChecked():
            dot.setAlphaF(.4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot)
        painter.drawEllipse(1, 6, 7, 7)
        painter.setPen(QColor(tokens.TEXT_SECONDARY if self.isChecked()
                              else tokens.TEXT_DISABLED))
        painter.drawText(QRectF(11, 0, 32, 18),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         self._short_name)


class _SegmentItem:
    """Inspectable hit geometry; FluentChartView paints the rounded mark."""

    def __init__(self, segment, owner, logical_x):
        self.segment = segment
        self.owner = owner
        self.logical_x = logical_x

    def rect(self):
        return self.segment.get('rect', QRectF(self.logical_x, 0, 1, 1))

    def toolTip(self):
        return self.segment['tooltip']

    def isVisible(self):
        return self.segment['key'] not in self.owner._hidden_categories


class NetworkChartPanel(ChartPanel):
    """One metric card; descriptor.result is the full trend timeline.

    Quantity bar mode consumes descriptor.bar_result. Its company/category
    series must each contain one model-selected endpoint Bucket with the real
    observed time. The enclosing dashboard owns the mode selector.
    """

    def __init__(self, parent=None):
        self.descriptor = None
        self.snapshot = None
        self._hidden_categories = set()
        self.bar_segments = []
        self._legend_keys = []
        self._compact_pie_body = None
        super().__init__('', parent=parent)
        self.set_category_palette(tokens.DATA_CATEGORY_COLORS)
        self.placeholder = self.summary_label
        self.placeholder.setStyleSheet(f'color: {tokens.TEXT_SECONDARY}; border: 0; '
                                       f'font-size: {tokens.FONT_SIZE_BODY}px;')
        self.period_label.hide()
        self.company_legend_entries = []
        self._company_legend_rows = []
        self.company_legend_host = QWidget(self)
        self.company_legend_host.setObjectName('companyBarLegend')
        self.company_legend_host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
        self.company_legend_layout = QGridLayout(self.company_legend_host)
        self.company_legend_layout.setContentsMargins(0, 0, 0, 0)
        self.company_legend_layout.setHorizontalSpacing(12)
        self.company_legend_layout.setVerticalSpacing(2)
        self._layout.insertWidget(self._layout.indexOf(self.chart_host), self.company_legend_host)
        self.company_legend_host.hide()
        self._external_mode_control = None
        self._external_mode_row_host = QWidget(self)
        self._external_mode_row = QHBoxLayout(self._external_mode_row_host)
        self._external_mode_row.setContentsMargins(0, 0, 0, 0)
        self._external_mode_row.addStretch(1)
        self._layout.insertWidget(1, self._external_mode_row_host)
        self._external_mode_row_host.hide()
        self._fade_effect = QGraphicsOpacityEffect(self.chart_host)
        self._fade_effect.setOpacity(1)
        self.chart_host.setGraphicsEffect(self._fade_effect)
        self._fade_animation = QPropertyAnimation(self._fade_effect, b'opacity', self)
        self._fade_animation.setDuration(180)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_mode_control(self, widget: QWidget | None) -> None:
        """Place the dashboard-owned Fluent selector in this card's header."""
        if widget is not None and not isinstance(widget, QWidget):
            raise TypeError('mode control must be a QWidget or None')
        if self._external_mode_control is not None:
            self._header_layout.removeWidget(self._external_mode_control)
            self._external_mode_row.removeWidget(self._external_mode_control)
            self._external_mode_control.hide()
        self._external_mode_control = widget
        if widget is not None:
            widget.setParent(self)
        self._position_external_mode_control()

    def _position_external_mode_control(self):
        if self._compact_height is not None:
            self.title_label.setWordWrap(False)
            title_font = self.title_label.font()
            target_size = (12 if self.width() < 330 else
                           13 if self.width() < 480 else 14)
            if title_font.pixelSize() != target_size:
                title_font.setPixelSize(target_size)
                self.title_label.setFont(title_font)
            if self.descriptor is not None:
                title = ('运行车辆数' if self.width() < 330 and
                         self.descriptor.key == 'vehicles-running' else
                         self.descriptor.title)
                if self.title_label.text() != title:
                    self.title_label.setText(title)
                self.title_label.setToolTip(self.descriptor.title)
        widget = self._external_mode_control
        if widget is None:
            self._external_mode_row_host.hide()
            return
        needs_separate_row = (self._compact_height is not None and self.width() < 360 and
                              (self.width() < 270 or widget.width() > 120))
        if needs_separate_row:
            self.title_label.setWordWrap(False)
            self._header_layout.removeWidget(widget)
            if self._external_mode_row.indexOf(widget) < 0:
                self._external_mode_row.addWidget(widget)
            self._external_mode_row_host.show()
        else:
            self.title_label.setWordWrap(self._compact_height is None)
            self._external_mode_row.removeWidget(widget)
            if self._header_layout.indexOf(widget) < 0:
                self._header_layout.insertWidget(
                    self._header_layout.indexOf(self.fullscreen_button), widget)
            self._external_mode_row_host.hide()
        if self._compact_height is not None:
            self.setFixedHeight(self._compact_height)

    def set_compact_height(self, height: int) -> None:
        super().set_compact_height(height)
        title_font = self.title_label.font()
        title_font.setPixelSize(14)
        self.title_label.setFont(title_font)
        self.legend_host.setSizePolicy(QSizePolicy.Policy.Ignored,
                                       QSizePolicy.Policy.Preferred)
        self._position_external_mode_control()

    def sizeHint(self):
        size = super().sizeHint()
        if self._compact_height is None:
            size.setHeight(282)
        return size

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_external_mode_row_host'):
            self._position_external_mode_control()
        if self._compact_height is not None and self.mode == 'pie':
            self._arrange_compact_pie()
        if hasattr(self, 'legend_host'):
            self._place_period_legend()
            self._place_period_label()
        if hasattr(self, 'company_legend_host'):
            self._reflow_company_legend()
        if self._compact_height is not None:
            self.setFixedHeight(self._compact_height)

    def set_descriptor(self, descriptor, snapshot):
        prior = self.descriptor
        self.descriptor = descriptor
        self.snapshot = snapshot
        self.result = descriptor.result
        self.companies = snapshot.companies
        self.title_label.setText(descriptor.title)
        if prior is None or prior.key != descriptor.key or self.mode not in descriptor.allowed_modes:
            self.mode = descriptor.allowed_modes[0]
        self._render()

    def set_mode(self, mode: str):
        if self.descriptor is not None and mode not in self.descriptor.allowed_modes:
            raise ValueError(mode)
        if mode not in ('line', 'bar', 'trend-bar', 'pie'):
            raise ValueError(mode)
        changed = mode != self.mode
        self.mode = mode
        self._render()
        if changed and self.isVisible() and motion_policy.animations_enabled():
            self._fade_animation.stop()
            self._fade_effect.setOpacity(0.25)
            self._fade_animation.setStartValue(0.25)
            self._fade_animation.setEndValue(1.0)
            self._fade_animation.start()
        elif changed:
            self._fade_animation.stop()
            self._fade_effect.setOpacity(1.)

    def clear(self):
        self.descriptor = None
        self.snapshot = None
        self.result = None
        self._hidden_categories.clear()
        self._render()

    def _open_fullscreen(self):
        if self.descriptor is None or self.result is None or self.descriptor.reason:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self.descriptor.title)
        dialog.setStyleSheet(f'QDialog {{ background: {tokens.PAGE_BG}; }}')
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        clone = NetworkChartPanel(dialog)
        clone.fullscreen_button.hide()
        clone._hidden_categories = set(self._hidden_categories)
        clone.set_company_palette({key: value.name() for key, value in self._company_palette.items()})
        clone.set_category_palette(self._category_palette)
        clone.set_descriptor(self.descriptor, self.snapshot)
        clone.set_mode(self.mode)
        clone.set_axis_spec(self._axis_override)
        if len(self.descriptor.allowed_modes) > 1:
            selector = FluentSegmentedControl(clone)
            for mode in self.descriptor.allowed_modes:
                selector.addItem(mode, {'line': '趋势', 'trend-bar': '趋势',
                                        'bar': '分布', 'pie': '比例'}[mode])
            selector.setCurrentKey(self.mode)
            selector.currentKeyChanged.connect(clone.set_mode)
            clone.set_mode_control(selector)
        layout.addWidget(clone)
        dialog.resize(1100, 700)
        self._fullscreen_dialog = dialog
        dialog.showMaximized()

    def _toggle_category(self, group):
        if group in self._hidden_categories:
            self._hidden_categories.remove(group)
        else:
            self._hidden_categories.add(group)
        self._hidden_groups = self._hidden_categories
        if group in self.legend_buttons:
            button = self.legend_buttons[group]
            active = group not in self._hidden_categories
            button.setChecked(active)
            if isinstance(button, _CompactLegendButton):
                button.update()
        for view in self.chart_views:
            for visual in view.visuals:
                if visual['type'] == 'network-pie':
                    for key, slice_ in visual.get('qt_slices', []):
                        if key == group:
                            slice_.setBrush(QBrush(QColor(0, 0, 0, 0)))
            view.viewport().update()
        self._refresh_value_content()

    def _fluent_hover(self, hit):
        kind = hit['type']
        if kind == 'network-hit':
            # Dense zero stacks share one baseline mark. Expose every real
            # observation there rather than making subpixel categories unreachable.
            message = ' | '.join(part['tooltip'] for part in hit.get('zero_peers', [hit])
                                 if part['key'] not in self._hidden_categories)
            if self._detailed:
                total = next((row for row in self.numbers.model.rows if row['kind'] == 'stack-total'
                              and row['slot'] == hit['slot'] and row['display_group'] == hit['group']), None)
                if total:
                    message += f" · 合计 {_number(total['visible_total'])} {self.result.metric.unit}"
            color = hit['color']
        elif kind in ('pie-slice-hit', 'network-pie-slice-hit'):
            message = hit['tooltip']
            color = hit['color']
        elif kind == 'time-hit':
            bucket = hit['bucket']
            message = self._tip(hit['company'], hit['group'], bucket,
                                hit['previous'])
            color = hit['color']
        elif kind == 'total-hit':
            message = hit['tooltips'][hit['index']]
            color = hit['colors'][hit['index']]
        else:
            return
        self._show_color_tooltip(message, color)

    def _tip(self, company, category, bucket, previous=False):
        period = ((self.snapshot.options.comparison_label if previous else '本期')
                  if self.snapshot.options.mode == 'period' else '')
        status = '完整' if bucket.complete else '不完整'
        if bucket.partial_period:
            status += ' · 部分时段'
        return ' · '.join(part for part in (
            period, self._display_company(company), group_label(category),
            bucket.start.strftime('%Y-%m-%d %H:%M'),
            f'{_number(bucket.value)} {self.result.metric.unit}', status) if part)

    def _render(self):
        if not hasattr(self, 'chart_layout'):
            return
        descriptor = self.descriptor
        if descriptor is None:
            self.result = None
        elif self.mode == 'bar' and descriptor.key in (
                'linecount', 'stopcount', 'vehicles-running'):
            self.result = getattr(descriptor, 'bar_result', None)
        else:
            self.result = descriptor.result
        self.placeholder = self.summary_label
        self._clear_views()
        self.bar_segments = []
        self.axis_spec = None
        self._base_axis_spec = None
        self._hidden_groups = self._hidden_categories
        self._combined_totals = False
        self._company_count = len(self.companies)
        self._legend_keys = []
        for button in self.legend_buttons.values():
            self.legend_layout.removeWidget(button)
            button.hide()
            button.deleteLater()
        self.legend_buttons = {}
        self.legend_host.hide()
        self.period_label.hide()
        if hasattr(self, 'company_legend_host'):
            self.company_legend_host.hide()
        self.fullscreen_button.setEnabled(False)
        if descriptor is None:
            self.chart_host.hide()
            self.placeholder.setText('暂无可用数据')
            self.placeholder.show()
            self._refresh_value_content()
            return
        if descriptor.reason or self.result is None:
            self.chart_host.hide()
            self.placeholder.setText(descriptor.reason or '暂无可用数据')
            self.placeholder.show()
            self._refresh_value_content()
            return
        self.placeholder.hide()
        self.chart_host.show()
        self.fullscreen_button.setEnabled(True)
        if self.mode == 'pie':
            self._pies()
        elif self.mode == 'bar':
            self._horizontal_bars()
        elif self.mode == 'trend-bar':
            self._time_stacks()
        else:
            self._lines()
        self._show_group_positions()
        self._build_network_legend()
        self._build_company_legend()
        self._arrange_compact_pie()
        self._place_period_legend()
        self._place_period_label()
        self._refresh_value_content()

    def _place_period_legend(self):
        inline = (self._compact_height is not None and self.width() >= 500
                  and self.snapshot is not None
                  and self.snapshot.options.mode == 'period'
                  and self.mode in ('line', 'trend-bar')
                  and self._legend_keys == ['current', 'comparison'])
        if inline and self._header_layout.indexOf(self.legend_host) < 0:
            self._layout.removeWidget(self.legend_host)
            self._header_layout.insertWidget(
                self._header_layout.indexOf(self.fullscreen_button),
                self.legend_host)
            self.legend_host.show()
        elif not inline and self._header_layout.indexOf(self.legend_host) >= 0:
            self._header_layout.removeWidget(self.legend_host)
            self._layout.insertWidget(self._layout.indexOf(self.period_label),
                                      self.legend_host)
            self.legend_host.setVisible(bool(self.legend_buttons))

    def _place_period_label(self):
        if self._compact_height is None:
            return
        controls = [self._external_mode_control, self.fullscreen_button]
        widths = [widget.sizeHint().width() for widget in controls
                  if widget is not None and not widget.isHidden()
                  and self._header_layout.indexOf(widget) >= 0]
        title_width = self.title_label.fontMetrics().horizontalAdvance(
            self.title_label.text())
        label_width = self.period_label.sizeHint().width()
        inline = (not self.period_label.isHidden() and label_width > 0
                  and self.width() >= 380
                  and sum(widths) + title_width + label_width
                  + (len(widths) + 1) * self._header_layout.spacing()
                  + 12 <= self.width())
        if inline and self._header_layout.indexOf(self.period_label) < 0:
            self._layout.removeWidget(self.period_label)
            self._header_layout.insertWidget(
                self._header_layout.indexOf(self.fullscreen_button),
                self.period_label)
        elif not inline and self._header_layout.indexOf(self.period_label) >= 0:
            self._header_layout.removeWidget(self.period_label)
            self._layout.insertWidget(self._layout.indexOf(self.summary_label),
                                      self.period_label)

    def _arrange_compact_pie(self):
        side_by_side = (self._compact_height is not None and self.mode == 'pie'
                        and self.width() >= 480 and len(self.legend_buttons) > 6)
        if side_by_side:
            if self._compact_pie_body is None:
                body = QWidget(self)
                row = QHBoxLayout(body)
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(4)
                self._compact_pie_body = body
            body = self._compact_pie_body
            if self._layout.indexOf(body) < 0:
                self._layout.removeWidget(self.legend_host)
                self._layout.removeWidget(self.chart_host)
                body.layout().addWidget(self.chart_host, 1)
                body.layout().addWidget(self.legend_host)
                self._layout.insertWidget(self._layout.indexOf(self.numbers), body, 1)
            self.legend_host.setMaximumWidth(176)
            body.show()
        elif self._compact_pie_body is not None and self._layout.indexOf(
                self._compact_pie_body) >= 0:
            body = self._compact_pie_body
            self._layout.removeWidget(body)
            body.layout().removeWidget(self.chart_host)
            body.layout().removeWidget(self.legend_host)
            self.legend_host.setMaximumWidth(16777215)
            self._layout.insertWidget(1, self.legend_host)
            self._layout.insertWidget(self._layout.indexOf(self.numbers), self.chart_host, 1)
            body.hide()
        self._reflow_legend()

    def _reflow_legend(self):
        if getattr(self, 'company_legend_entries', ()):
            return self._reflow_company_legend()
        if self._compact_height is None:
            return super()._reflow_legend()
        buttons = tuple(self.legend_buttons.values())
        compact = buttons and all(isinstance(button, _CompactLegendButton)
                                  for button in buttons)
        gap = 1 if compact else 6
        self.legend_layout.setHorizontalSpacing(gap)
        available_width = min(self.width() - 12, self.legend_host.maximumWidth())
        one_row_width = sum(button.width() for button in buttons) + max(0, len(buttons) - 1) * gap
        columns = (len(buttons) if compact and len(buttons) >= 4 and
                   one_row_width <= available_width else
                   3 if len(buttons) >= 4 and available_width >= 270 else 2)
        while self.legend_layout.count():
            self.legend_layout.takeAt(0)
        for index, button in enumerate(buttons):
            self.legend_layout.addWidget(button, index // columns, index % columns)

    def _show_group_positions(self):
        if self._detailed:
            return
        if self.mode == 'pie':
            return
        groups = self._group_ids(self._sources())
        if len(groups) <= 1:
            return
        categories = self._category_ids(self._sources())
        if (self.mode in ('bar', 'trend-bar') and len(categories) > 1
                and self.snapshot.options.mode != 'period'):
            return  # The matching company shade legend identifies each column.
        if (self.snapshot.options.mode == 'period' and len(categories) <= 1
                and self.mode in ('line', 'trend-bar')):
            return  # 本期/对比期 already have their own visible legend controls.
        if self.mode == 'line':
            if self.snapshot.options.mode != 'period' and len(categories) <= 1:
                return  # The company-color legend already identifies these lines.
            styles = ('━', '┄', '┈', '━·━')
            labels = [f'{styles[index % len(styles)]} {self._group_name(group)}'
                      for index, group in enumerate(groups)]
        elif self.snapshot.options.mode != 'period' and self.mode == 'trend-bar' and len(categories) <= 1:
            return  # Each company already has a colored legend button.
        else:
            if len(groups) == 2:
                positions = ('上', '下') if self.mode == 'bar' else ('左', '右')
            else:
                positions = tuple(str(index + 1) for index in range(len(groups)))
            labels = [f'{position} {self._group_name(group)}'
                      for position, group in zip(positions, groups)]
        self.period_label.setText(('  ' if self._compact_height is not None
                                   else '    ').join(labels))
        self.period_label.show()

    def _sources(self):
        """Each item is (display column, real company, category, buckets, prior)."""
        result = self.result
        mode = self.snapshot.options.mode
        filters = getattr(self.snapshot, 'filters', None)
        selected = tuple(dict.fromkeys(
            getattr(filters, 'companies', ()) or self.snapshot.companies or
            result.query.companies))
        company_order = {company: index for index, company in enumerate(selected)}
        category_order = {
            category: index for index, category in enumerate(tokens.DATA_CATEGORY_GROUPS)}

        def order(item):
            company, category = item[0]
            return (company_order.get(company, len(company_order)), company,
                    category_order.get(category, len(category_order)), category)

        output = []
        for (company, category), buckets in sorted(result.series.items(), key=order):
            output.append((network_display_group(mode, company, False,
                                                  [owner for owner, _ in result.series], self.descriptor.key),
                           company, category, buckets, False))
        if mode == 'period':
            for (company, category), buckets in sorted(result.comparison.items(), key=order):
                output.append((network_display_group(mode, company, True,
                                                       [owner for owner, _ in result.series], self.descriptor.key),
                               company, category, buckets, True))
        return output

    def _slots(self):
        sources = self._sources()
        count = max([len(source[3]) for source in sources] or [0])
        return list(range(count))

    def _group_ids(self, sources):
        mode = self.snapshot.options.mode
        if mode == 'overall':
            return list(dict.fromkeys(source[0] for source in sources))
        if mode == 'period':
            groups = list(dict.fromkeys(source[0] for source in sources))
            if groups and isinstance(groups[0], tuple):
                companies = list(dict.fromkeys(source[1] for source in sources))
                return sorted(groups, key=lambda group: (companies.index(group[0]), group[1]))
            return groups
        return list(dict.fromkeys(source[0] for source in sources))

    def _category_ids(self, sources):
        rank = {category: index for index, category in enumerate(tokens.DATA_CATEGORY_GROUPS)}
        return sorted({source[2] for source in sources},
                      key=lambda category: (rank.get(category, len(rank)), category))

    def _color(self, company, category, categories):
        return (self._category_color(category) if len(categories) > 1 else
                QColor(tokens.DATA_COMPANY_COLORS[0]) if company == '__selected__' else
                self._company_color(company))

    def _bar_color(self, company, category, categories):
        color = self._color(company, category, categories)
        owners = sorted(self._company_palette or self.companies or self.result.query.companies)
        if len(categories) <= 1 or company not in owners:
            return color
        index = owners.index(company)
        fraction, place, remainder = 0., .5, index
        while remainder:
            fraction += (remainder % 2) * place
            remainder //= 2
            place /= 2
        factor = .76 * fraction * (1 if index % 2 else -1)
        target = 1. if factor >= 0 else 0.
        channels = [value + (target - value) * abs(factor)
                    for value in (color.redF(), color.greenF(), color.blueF())]
        return QColor.fromRgbF(*channels, color.alphaF())

    def _build_company_legend(self):
        for row in self._company_legend_rows:
            row.hide()
        for entry in self.company_legend_entries:
            self.legend_layout.removeWidget(entry['widget'])
            entry['widget'].hide()
            entry['widget'].deleteLater()
        self.company_legend_entries = []
        self.company_legend_host.hide()
        sources = self._sources()
        categories = self._category_ids(sources)
        owners = list(dict.fromkeys(part[1] for part in sources))
        if self.mode not in ('bar', 'trend-bar') or not categories or len(owners) <= 1:
            return
        if len(categories) == 1 and self.legend_buttons:
            return  # Existing company-color toggles already identify these columns.
        for company in owners:
            colors = {category: self._bar_color(company, category, categories) for category in categories}
            widget = QWidget(self.legend_host)
            row = QHBoxLayout(widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(5)
            sample = QLabel(widget)
            sample.setFixedSize(14, 16)
            pixmap = QPixmap(14, 16)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            for index, category in enumerate(reversed(categories)):
                painter.fillRect(QRectF(1, index * 16 / len(categories), 12, 16 / len(categories)), colors[category])
            painter.end()
            sample.setPixmap(pixmap)
            name = self._display_company(company)
            caption = QLabel(name, widget)
            caption.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};font-size:12px;border:0;')
            caption.setMinimumWidth(0)
            caption.setToolTip(name)
            caption.setAccessibleName(name)
            row.addWidget(sample)
            row.addWidget(caption)
            widget.setToolTip(name)
            self.company_legend_entries.append(dict(company=company, name=name, colors=colors,
                                                    widget=widget, caption=caption))
        self._reflow_company_legend()
        self.legend_host.show()

    def _reflow_company_legend(self):
        entries = self.company_legend_entries
        if not entries:
            return
        width = max(100, self.width() - 32)
        gap = 6
        categories = list(self.legend_buttons.values())
        companies = []
        for entry in entries:
            cell = min(width, 180, entry['caption'].fontMetrics().horizontalAdvance(entry['name']) + 21)
            entry['widget'].setFixedWidth(cell)
            entry['caption'].setText(entry['caption'].fontMetrics().elidedText(
                entry['name'], Qt.TextElideMode.ElideRight, max(10, cell - 21)))
            companies.append(entry['widget'])
        sizes = {widget: min(width, max(widget.minimumWidth(), widget.sizeHint().width()))
                 for widget in categories}
        sizes.update({widget: widget.width() for widget in companies})
        items = categories + companies
        if sum(sizes[widget] for widget in items) + gap * (len(items) - 1) <= width:
            rows = [items]
        else:
            rows = []
            for group in (categories, companies):
                row, used = [], 0
                for widget in group:
                    addition = sizes[widget] + (gap if row else 0)
                    if row and used + addition > width:
                        rows.append(row)
                        row, used = [], 0
                        addition = sizes[widget]
                    row.append(widget)
                    used += addition
                if row:
                    rows.append(row)
        while self.legend_layout.count():
            self.legend_layout.takeAt(0)
        for column in range(len(items) + 2):
            self.legend_layout.setColumnStretch(column, 0)
        self.legend_layout.setHorizontalSpacing(0)
        self.legend_layout.setVerticalSpacing(2)
        for index, widgets in enumerate(rows):
            if index == len(self._company_legend_rows):
                host = QWidget(self.legend_host)
                row = QHBoxLayout(host)
                row.setContentsMargins(0, 0, 0, 0)
                self._company_legend_rows.append(host)
            host = self._company_legend_rows[index]
            row = host.layout()
            while row.count():
                row.takeAt(0)
            row.setSpacing(gap)
            row.addStretch(1)
            for widget in widgets:
                widget.setFixedWidth(sizes[widget])
                row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
                widget.show()
            self.legend_layout.addWidget(host, index, 0)
            host.show()
        for host in self._company_legend_rows[len(rows):]:
            host.hide()

    def _time_axis(self, chart, count):
        sources = self._sources()
        source = next((part[3] for part in sources if part[3] and not part[4]),
                      next((part[3] for part in sources if part[3]), []))
        dates = [bucket.start for bucket in source]
        if not dates:
            dates = [self.result.current_window[0]]
        from statistics_model import period_bounds
        while len(dates) < count:
            dates.append(period_bounds(dates[-1], self.result.query.grain)[1])
        axis = self._time_label_axis(chart, dates)
        self._set_time_labels(axis, dates, min(count, 5))
        chart.addAxis(axis, Qt.AlignmentFlag.AlignBottom)
        return axis

    def _axis(self, chart, values, horizontal=False):
        axis = self._value_axis(values, horizontal=horizontal)
        chart.addAxis(axis, Qt.AlignmentFlag.AlignBottom if horizontal else
                      Qt.AlignmentFlag.AlignLeft)
        return axis

    def _time_stacks(self):
        sources = self._sources()
        groups = self._group_ids(sources)
        categories = self._category_ids(sources)
        count = len(self._slots())
        if not sources or not count:
            self._empty_chart()
            return
        totals = {}
        for group, company, category, buckets, previous in sources:
            for index, bucket in enumerate(buckets):
                if bucket.value is not None and bucket.value > 0:
                    totals[group, index] = totals.get((group, index), Decimal(0)) + bucket.value
        axis = self._axis_override or nice_axis(totals.values())
        chart = self._chart()
        self._time_axis(chart, count)
        self._axis(chart, totals.values())
        self.axis_spec = axis
        segments = []
        for group, company, category, buckets, previous in sources:
            for slot, bucket in enumerate(buckets):
                if bucket.value is None:
                    continue
                key = category if len(categories) > 1 else group
                item = dict(slot=slot, group=group, company=company, category=category,
                            key=key,
                            value=bucket.value, bucket=bucket, previous=previous,
                            color=self._bar_color(company, category, categories),
                            tooltip=self._tip(company, category, bucket, previous))
                item['item'] = _SegmentItem(item, self, slot * len(groups) + groups.index(group))
                segments.append(item)
        self.bar_segments = segments
        self.chart_views[-1].add_visual({'type': 'network-stacks', 'slots': self._slots(),
                                        'groups': groups, 'segments': segments, 'axis': axis})
        self._legend_keys = (categories if len(categories) > 1 else groups)
        self._apply_empty_chart_states_network()

    def _lines(self):
        sources = self._sources()
        categories = self._category_ids(sources)
        count = len(self._slots())
        if not sources or not count:
            self._empty_chart()
            return
        values = [bucket.value for _, _, _, buckets, _ in sources
                  for bucket in buckets if bucket.value is not None]
        chart = self._chart()
        xaxis = self._time_axis(chart, count)
        yaxis = self._axis(chart, values)
        axis = self.axis_spec
        group_ids = self._group_ids(sources)
        styles = (None, Qt.PenStyle.DashLine, Qt.PenStyle.DotLine,
                  Qt.PenStyle.DashDotLine)
        for group, company, category, buckets, previous in sources:
            active = []
            parts = []
            for index, bucket in enumerate(buckets):
                if bucket.value is None:
                    if active:
                        parts.append(active)
                        active = []
                else:
                    active.append((index, bucket))
            if active:
                parts.append(active)
            key = (category if len(categories) > 1 else
                   group if self.snapshot.options.mode != 'overall' else company)
            color = self._color(company, category, categories)
            for part in parts:
                series = QLineSeries()
                for index, bucket in part:
                    series.append(index, float(bucket.value) / axis.scale)
                chart.addSeries(series)
                series.attachAxis(xaxis)
                series.attachAxis(yaxis)
                series.setOpacity(0)
                self.chart_views[-1].add_visual(dict(
                    type='line', points=[(index, float(bucket.value) / axis.scale, bucket)
                                         for index, bucket in part], count=count,
                    axis=axis, color=color, previous=previous,
                    area=len(categories) == 1,
                    line_style=(styles[group_ids.index(group) % len(styles)]
                                if len(categories) > 1 or self.snapshot.options.mode == 'period'
                                else None),
                    company=company, group=category, key=key))
        self._legend_keys = categories if len(categories) > 1 else self._group_ids(sources)
        self._apply_empty_chart_states_network()

    def _horizontal_bars(self):
        sources = self._sources()
        categories = self._category_ids(sources)
        groups = self._group_ids(sources)
        if not categories or not groups:
            self._empty_chart()
            return
        endpoints = {(group, category): self._endpoint_bucket(buckets, previous)
                     for group, _, category, buckets, previous in sources}
        values = [bucket.value for bucket in endpoints.values() if bucket is not None]
        axis = self._axis_override or nice_axis(values)
        chart = self._chart()
        series = QHorizontalBarSeries()
        for group in groups:
            bar = QBarSet(self._group_name(group))
            bar.setColor(self._legend_key_color(group))
            bar.setBrush(QBrush(QColor(0, 0, 0, 0)))
            bar.setBorderColor(QColor(0, 0, 0, 0))
            for category in categories:
                bucket = endpoints.get((group, category))
                bar.append(float(bucket.value) / axis.scale if bucket is not None else 0)
            series.append(bar)
        chart.addSeries(series)
        series.setOpacity(0)
        cat_axis = QBarCategoryAxis()
        cat_axis.append([group_label(category) for category in categories])
        self._style_category_axis(cat_axis)
        chart.addAxis(cat_axis, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(cat_axis)
        value_axis = self._axis(chart, values, horizontal=True)
        series.attachAxis(value_axis)
        self.axis_spec = axis
        chart_view = self.chart_views[-1]
        visual_sets = []
        for group in groups:
            previous = group[1] if isinstance(group, tuple) else group == 'comparison'
            company = next((part[1] for part in sources if part[0] == group), group)
            visual_sets.append(dict(company=company, previous=previous,
                                    colors=[self._bar_color(company, category, categories)
                                            for category in categories],
                                    values=[float(endpoints[group, category].value) / axis.scale
                                            if endpoints.get((group, category)) is not None else None
                                            for category in categories],
                                    raw_values=[endpoints[group, category].value
                                                if endpoints.get((group, category)) is not None else None
                                                for category in categories],
                                    buckets=[endpoints.get((group, category)) for category in categories],
                                    tooltips=[self._endpoint_tip(company, category,
                                                                 endpoints.get((group, category)),
                                                                 previous)
                                              for category in categories]))
        chart_view.add_visual(dict(type='horizontal-bars', names=categories,
                                   sets=visual_sets, axis=axis))
        self._legend_keys = categories
        self._apply_empty_chart_states_network()

    def _pies(self):
        sources = self._sources()
        groups = self._group_ids(sources)
        categories = self._category_ids(sources)
        share = self.descriptor.key == 'company-passengers'
        if share:
            groups = ['shares']
            categories = list(dict.fromkeys(part[1] for part in sources))
        if not sources:
            self._empty_chart()
            return
        for group in groups:
            selected = (sources if share else [part for part in sources if part[0] == group])
            chart = self._chart('' if share or len(groups) == 1
                                else self._group_name(group))
            series = QPieSeries()
            slices = []
            qt_slices = []
            for _, company, category, buckets, previous in selected:
                key = company if share else category
                value = summarize_buckets(buckets, self.result.metric)
                if value is None or value <= 0:
                    continue
                color = self._company_color(company) if share else self._category_color(category)
                name = self._display_company(company) if share else group_label(category)
                slice_ = series.append(name, float(value))
                slice_.setBrush(QBrush(QColor(0, 0, 0, 0)))
                slice_.setPen(QPen(QColor(0, 0, 0, 0)))
                qt_slices.append((key, slice_))
                window = self.result.comparison_window if previous else self.result.current_window
                date_text = (f'{window[0]:%Y-%m-%d}—{window[1]:%Y-%m-%d}'
                             if window else '')
                period = self._group_name(group) if self.snapshot.options.mode == 'period' else ''
                tooltip = ' · '.join(part for part in (
                    period, self._display_company(company),
                    '' if share else name, date_text,
                    f'{_number(value)} {self.result.metric.unit}',
                    '完整' if all(bucket.complete for bucket in buckets) else '不完整') if part)
                slices.append(dict(company=company, group=category, key=key,
                                   previous=previous,
                                   value=value, color=color, tooltip=tooltip))
            if series.count():
                chart.addSeries(series)
                series.setOpacity(0)
                total = sum((item['value'] for item in slices), Decimal(0))
                self.chart_views[-1].add_visual(dict(type='network-pie', slices=slices,
                                                     qt_slices=qt_slices,
                                                     total_text=_number(total),
                                                     unit=self.result.metric.unit))
            else:
                self.chart_views[-1].add_visual({'type': 'empty', 'text': '暂无可用数据'})
        self._legend_keys = categories

    def _group_name(self, group):
        if isinstance(group, tuple):
            company, previous = group
            return self._display_company(company) + ' · ' + (self.snapshot.options.comparison_label if previous else '本期')
        if group in ('__overall__', '__selected__'):
            return '已选公司'
        if group == 'current':
            return '本期'
        if group == 'comparison':
            return self.snapshot.options.comparison_label
        return self._display_company(group)

    def _display_company(self, company):
        if company == '__selected__':
            return '已选公司'
        name = self.companies.get(company, company)
        return f'{name} ({company})' if list(self.companies.values()).count(name) > 1 else name

    def _endpoint_bucket(self, buckets, previous):
        """Consume the model's single selected endpoint without aggregating time."""
        if len(buckets) != 1:
            return None
        bucket = buckets[0]
        window = self.result.comparison_window if previous else self.result.current_window
        if (window is None or bucket.value is None or bucket.observed is None or
                not window[0] <= bucket.observed < window[1]):
            return None
        return bucket

    def _endpoint_tip(self, company, category, bucket, previous):
        if bucket is None:
            return ''
        period = ((self.snapshot.options.comparison_label if previous else '本期')
                  if self.snapshot.options.mode == 'period' else '')
        status = '完整' if bucket.complete else '不完整'
        if bucket.partial_period:
            status += ' · 部分时段'
        return ' · '.join(part for part in (
            period, self._display_company(company), group_label(category),
            bucket.observed.strftime('%Y-%m-%d %H:%M'),
            f'{_number(bucket.value)} {self.result.metric.unit}', status) if part)

    def _legend_key_color(self, key):
        if isinstance(key, tuple):
            return self._company_color(key[0])
        if key == '__selected__':
            return QColor(tokens.DATA_COMPANY_COLORS[0])
        if key in ('current', 'comparison'):
            company = (self.descriptor.company_id if self.descriptor is not None
                       else None) or next((part[1] for part in self._sources()), None)
            return self._company_color(company) if company else QColor(tokens.DATA_COMPANY_COLORS[0])
        categories = self._category_ids(self._sources())
        if len(categories) > 1 and key in categories:
            owners = list(dict.fromkeys(part[1] for part in self._sources()))
            if self.mode in ('bar', 'trend-bar') and len(owners) == 1:
                return self._bar_color(owners[0], key, categories)
            return self._category_color(key)
        if key in self.companies:
            return self._company_color(key)
        return self._category_color(key)

    def _build_network_legend(self):
        keys = list(dict.fromkeys(self._legend_keys))
        if len(keys) <= 1:
            return
        self.legend_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter if
                                        self._compact_height is not None
                                        else Qt.AlignmentFlag.AlignRight)
        for index, key in enumerate(keys):
            color = self._legend_key_color(key)
            compact_legend = self._compact_height is not None and len(keys) >= 4
            name = (self._group_name(key) if isinstance(key, tuple) or key in self.companies or
                    key == '__selected__' or key in ('current', 'comparison')
                    else group_label(key))
            button = (_CompactLegendButton(color, _COMPACT_CATEGORY_NAMES.get(key, name),
                                           self.legend_host) if compact_legend else
                      TransparentTogglePushButton(self.legend_host))
            if not compact_legend:
                button.setText(name)
            button.setAccessibleName(name)
            button.setToolTip(name)
            if not compact_legend:
                button.setIcon(self._legend_icon_for(color))
                button.setIconSize(QSize(12, 12))
            button.setCheckable(True)
            button.setChecked(key not in self._hidden_categories)
            if not compact_legend:
                button.setStyleSheet(f'ToggleButton {{ color: {tokens.TEXT_SECONDARY}; border: 0; '
                                     f'padding: 2px 5px 2px 28px; text-align: left; }} '
                                     f'ToggleButton:hover, ToggleButton:checked {{ background: {tokens.ACCENT_SOFT}; '
                                     f'border-radius: {tokens.RADIUS_CONTROL}px; }} '
                                     f'ToggleButton:!checked {{ color: {tokens.TEXT_DISABLED}; }}')
            button.clicked.connect(lambda checked=False, k=key: self._toggle_category(k))
            self.legend_layout.setHorizontalSpacing(1 if compact_legend else 6)
            self.legend_layout.addWidget(button, index // 3, index % 3)
            self.legend_buttons[key] = button
        self.legend_host.show()

    @staticmethod
    def _legend_icon_for(color):
        from PySide6.QtGui import QIcon, QPainter, QPixmap
        image = QPixmap(12, 12)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 8, 8)
        painter.end()
        return QIcon(image)

    def _empty_chart(self):
        chart = self._chart()
        self.chart_views[-1].add_visual({'type': 'empty', 'text': '暂无可用数据'})

    def _apply_empty_chart_states_network(self):
        if self.chart_views and not any(
                visual['type'] == 'line' and visual['points'] or
                visual['type'] == 'network-stacks' and visual['segments'] or
                visual['type'] == 'horizontal-bars' and any(
                    value is not None for item in visual['sets'] for value in item['values'])
                for view in self.chart_views for visual in view.visuals):
            for view in self.chart_views:
                view.visuals = [{'type': 'empty', 'text': '暂无可用数据'}]
                for axis in view.chart().axes():
                    axis.setVisible(False)
