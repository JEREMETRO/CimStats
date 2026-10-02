"""Controlled Fluent drawing for statistics charts, over QtCharts geometry.

QtCharts supplies axes and data series.  Their shapes are transparent; this view
owns every visible data mark so the card, full screen, and exported PNG agree.
"""
from __future__ import annotations

from math import atan2, cos, degrees, hypot, radians, sin

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtCharts import QChartView
from PySide6.QtWidgets import QFrame, QToolTip
import stats_tokens as tokens
from chart_details import (exact_number, place_value_labels, place_detail_labels, place_pie_labels,
                           stack_total_text, value_marker_matches)
from stats_typography import emphasis_font


def _value_font(text, width, height, total=False):
    """Fit actual glyphs to their available space, with readable size limits."""
    for size in range(15 if total else 13, 11 if total else 9, -1):
        font = emphasis_font(size, QFont.Weight.Bold) if total else QFont(tokens.FONT_FAMILY)
        font.setPixelSize(size)
        metrics = QFontMetrics(font)
        if metrics.horizontalAdvance(text) <= width - 8 and metrics.height() <= height - 4:
            return font
    return font


def _label_color(background):
    """Choose the stronger contrast after compositing translucent series fill."""
    background, surface = QColor(background), QColor(tokens.CARD_BG)
    alpha = background.alphaF()
    channels = [alpha * component + (1 - alpha) * base
                for component, base in zip((background.redF(), background.greenF(), background.blueF()),
                                           (surface.redF(), surface.greenF(), surface.blueF()))]
    def luminance(channels):
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
                  for value in channels]
        return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))
    light = luminance(channels)
    dark = QColor(tokens.TEXT_PRIMARY)
    dark_light = luminance((dark.redF(), dark.greenF(), dark.blueF()))
    dark_ratio = (max(light, dark_light) + .05) / (min(light, dark_light) + .05)
    return QColor('#ffffff') if 1.05 / (light + .05) > dark_ratio else dark


def _grouped_bar_geometry(plot_width, count, groups, detailed):
    """Share company spacing and width limits across cashflow and passenger bars."""
    slot = plot_width / max(1, count)
    gap = min(24. if detailed else 4., max(.8, slot * .075))
    width = min(48. if detailed else 20.,
                max(.6 if detailed else 2., (slot * (.78 if detailed else .72) -
                                            gap * (groups - 1)) / groups))
    return slot, gap, width, groups * width + (groups - 1) * gap


def _period_color(color: QColor, previous: bool = False) -> QColor:
    """Preserve the shared identity color; comparison changes opacity only."""
    source = QColor(color)
    if previous:
        source.setAlphaF(tokens.CHART_COMPARISON_OPACITY)
    return source


def _bar_brush(color: QColor, bar: QRectF, horizontal: bool = False) -> QBrush:
    """Opaque same-hue relief, with the exact identity color at its base."""
    gradient = (QLinearGradient(bar.left(), bar.center().y(), bar.right(), bar.center().y())
                if horizontal else
                QLinearGradient(bar.center().x(), bar.top(), bar.center().x(), bar.bottom()))
    leading = QColor(color)
    hue, saturation, value, alpha = leading.getHsvF()
    leading.setHsvF(hue, saturation, value * tokens.CHART_BAR_GRADIENT_TOP_FACTOR,
                    alpha)
    gradient.setColorAt(0, leading)
    gradient.setColorAt(1, color)
    return QBrush(gradient)


class FluentChartView(QChartView):
    def __init__(self, chart, owner, parent=None):
        super().__init__(chart, parent)
        self.owner = owner
        self.visuals: list[dict] = []
        self.unit_text = ''
        self._hit_regions: list[tuple[QRectF, dict]] = []
        self._active_hit = None
        self.value_labels = []
        self.value_label_mode = 'numbers'
        self.detail_plan = None
        self._detail_label_cache = None
        self.setMouseTracking(True)
        self.setViewportUpdateMode(self.ViewportUpdateMode.FullViewportUpdate)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def add_visual(self, visual: dict) -> None:
        self.visuals.append(visual)
        self.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if (getattr(self.owner, '_detailed', False) and
                getattr(self.owner, 'result', None) is not None):
            self.owner._update_detail_axes()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        plot = self.chart().plotArea()
        if plot.width() < 2 or plot.height() < 2:
            return
        self._hit_regions = []
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setClipRect(plot)
        for visual in self.visuals:
            kind = visual['type']
            if kind == 'time-bars':
                self._draw_time_bars(painter, plot, visual)
            elif kind == 'horizontal-bars':
                self._draw_horizontal_bars(painter, plot, visual)
            elif kind == 'line':
                self._draw_line(painter, plot, visual)
            elif kind == 'pie':
                self._draw_pie(painter, plot, visual)
            elif kind == 'network-stacks':
                self._draw_network_stacks(painter, plot, visual)
            elif kind == 'network-pie':
                self._draw_network_pie(painter, plot, visual)
            elif kind == 'empty':
                painter.setPen(QColor(tokens.TEXT_SECONDARY))
                font = painter.font()
                font.setPixelSize(12)
                painter.setFont(font)
                painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, visual['text'])
        painter.restore()
        self.owner._position_hover_markers()
        self._draw_value_labels(painter, plot)
        if self.unit_text and not any(item['type'] == 'pie' for item in self.visuals):
            painter.save()
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            font = painter.font()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(QPointF(plot.left() + 4, plot.top() + 13), self.unit_text)
            painter.restore()

    def _draw_value_labels(self, painter, plot):
        """Detailed temporal canvases reserve a permanent lane for every value."""
        detailed = self.owner._detailed and self.detail_plan is not None
        focus_only = detailed and not self.detail_plan.get('labels', False)
        selected = getattr(self.owner, '_selected_value', None)
        if focus_only and selected is None:
            self.value_labels = []
            self.value_label_mode = 'hover'
            return
        if self.owner.result is not None and not self.owner.result.metric.confirmed and not detailed:
            self.value_labels = []
            self.value_label_mode = 'numbers'
            return
        painter.save()
        bounds = (QRectF(plot.left(), plot.top() - self.detail_plan['header_height'],
                         plot.width(), self.detail_plan['header_height']) if detailed else
                  plot.adjusted(2, 19 if self.unit_text else 2, -2, -2))
        if focus_only:
            bounds = plot.adjusted(2, 19 if self.unit_text else 2, -2, -2)
        painter.setClipRect(QRectF(plot.left(), bounds.top(), plot.width(), plot.bottom() - bounds.top()))
        font = painter.font()
        font.setPixelSize(12)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        requests, columns, obstacles = [], {}, []
        pie_geometry = None
        hidden = self.owner._hidden_groups | getattr(self.owner, '_hidden_categories', set())

        def request(text, point, item):
            if focus_only and not value_marker_matches(item, selected):
                return
            total = item.get('kind') in ('stack-total', 'bar-total')
            first, last = self.detail_plan['window'] if detailed else (0, 1)
            groups = max((len(visual['groups'] if visual['type'] == 'network-stacks' else visual['sets'])
                          for visual in self.visuals if visual['type'] in ('network-stacks', 'time-bars')), default=1)
            width = plot.width() / max(1, (last - first) * groups) if detailed else 100
            if total:
                peers = {rect.center().x() for rect, hit in self._hit_regions
                         if hit['type'] in ('network-hit', 'time-hit') and abs(rect.center().x() - point.x()) > .5}
                if peers:
                    width = min(width, min(abs(center - point.x()) for center in peers) - 2)
            height = 40
            region = item.get('rect')
            if region is not None and not total and region.height() >= 18:
                width, height = min(width, region.width()), min(40, region.height())
            value_font = _value_font(text, width, height, total) if detailed else font
            value_metrics = QFontMetrics(value_font)
            label = dict(text=text, point=point, item=item, font=value_font,
                         size=(value_metrics.horizontalAdvance(text) + 6, value_metrics.height() + 4))
            if detailed and item.get('kind') == 'bar-total':
                label['outside_side'] = 1 if item['bucket'].value < 0 else -1
            if detailed and not focus_only:
                key = ('stack-total' if item.get('kind') == 'stack-total' else
                       item['category'] if item.get('type') == 'network-hit' else
                       (item['company'], item['group'], bool(item.get('previous'))))
                label['lane'] = self.detail_plan['lane_keys'].index(key)
                if item.get('type') == 'network-hit':
                    region = item.get('rect')
                    if region and region.width() >= label['size'][0] + 2 and region.height() >= label['size'][1] + 2:
                        label['inside_rect'] = QRectF(region.center().x() - label['size'][0] / 2,
                                                     region.center().y() - label['size'][1] / 2,
                                                     *label['size'])
                elif item.get('kind') in ('stack-total', 'bar-total'):
                    negative = item.get('kind') == 'bar-total' and item['bucket'].value < 0
                    label['inside_rect'] = QRectF(point.x() - label['size'][0] / 2,
                                                 point.y() + 5 if negative else
                                                 max(plot.top() - 23, point.y() - label['size'][1] - 5),
                                                 *label['size'])
            requests.append(label)

        for region, item in self._hit_regions:
            kind = item['type']
            if kind in ('pie-hit', 'network-pie-hit'):
                first = item['slices'][0]
                center, radius = first['center'], first['outer_radius']
                pie_geometry = center, radius
                if item.get('center_footer') is not None:
                    bounds = bounds.adjusted(0, 0, 0, -28)
                for part in item['slices']:
                    if part['key'] in hidden:
                        continue
                    middle = radians(part['start_angle'] + part['span_angle'] / 2)
                    point = QPointF(part['center'].x() + cos(middle) * radius,
                                    part['center'].y() - sin(middle) * radius)
                    value, percent = exact_number(part['value']), f"{part['percent']:.1f}%"
                    value_font = QFont(tokens.FONT_FAMILY)
                    value_font.setPixelSize(item.get('pie_label_font_size', 13 if self.owner._detailed else 12))
                    value_metrics = QFontMetrics(value_font)
                    text = value + ' · ' + percent
                    size = (value_metrics.horizontalAdvance(text) + 6, value_metrics.height())
                    stacked = self.owner._detailed or size[0] > (plot.width() - 2 * radius) / 2 - 10
                    if stacked:
                        text = value
                        size = (max(value_metrics.horizontalAdvance(value),
                                    value_metrics.horizontalAdvance(percent)) + 6,
                                value_metrics.height() + 17)
                    requests.append(dict(text=text, secondary_text=percent if stacked else '',
                                         point=point, item=part, font=value_font, size=size,
                                         gap=4 if self.owner._detailed else 2))
                continue
            value = item['bucket'].value if kind == 'time-hit' else item.get('value')
            if value is None:
                continue
            point = item.get('hover_point', region.center())
            text = exact_number(value) if self.owner.result.metric.confirmed else '—'
            request(text, point, item)
            if kind == 'network-hit':
                key = item['slot'], item['group']
                top = QPointF(region.center().x(), region.top())
                if key not in columns or top.y() < columns[key].y():
                    columns[key] = top
        for row in self.owner.numbers.model.rows:
            if row['kind'] != 'stack-total' or not row['visible']:
                continue
            point = columns.get((row['slot'], row['display_group']))
            if point is None:
                continue
            text = stack_total_text(row)
            request(text, point, row)
        if pie_geometry is not None:
            labels = place_pie_labels(requests, bounds, *pie_geometry)
        elif detailed and not focus_only:
            signature = (bounds.getRect(), plot.getRect(),
                         tuple((item['text'], item['point'].x(), item['point'].y(),
                                item['size'], item['lane'],
                                item['inside_rect'].getRect() if 'inside_rect' in item else None)
                               for item in requests))
            if self._detail_label_cache and self._detail_label_cache[0] == signature:
                labels = [dict(item, rect=box) for item, box in zip(requests, self._detail_label_cache[1])]
            else:
                labels = place_detail_labels(requests, bounds, plot)
                self._detail_label_cache = (signature, [label['rect'] for label in labels])
        else:
            labels = place_value_labels(requests, bounds, obstacles)
        self.value_label_mode = 'plot' if labels is not None else 'numbers'
        self.value_labels = labels or []
        if selected:
            for item in requests:
                mark = item['item']
                if value_marker_matches(mark, selected):
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor(tokens.ACCENT), 2))
                    painter.drawEllipse(item['point'], 6, 6)
        for label in self.value_labels:
            point, box = label['point'], label['rect']
            if 'pie_side' in label:
                right = label['pie_side']
                end = QPointF(box.left() - 3 if right else box.right() + 3, box.center().y())
                elbow = QPointF(end.x() - 5 if right else end.x() + 5, end.y())
                painter.setPen(QPen(QColor(label['item']['color']), .8))
                painter.drawLine(point, elbow)
                painter.drawLine(elbow, end)
            elif not box.adjusted(-6, -6, 6, 6).contains(point):
                color = label['item'].get('color', QColor(tokens.TEXT_SECONDARY))
                painter.setPen(QPen(QColor(color), .6))
                painter.drawLine(point, box.center())
            painter.setFont(label['font'])
            region = label['item'].get('rect')
            background = QColor(tokens.CARD_BG)
            if region is not None and region.contains(box):
                background = QColor(label['item'].get('color', tokens.CARD_BG))
                if label['item'].get('previous'):
                    background.setAlphaF(tokens.CHART_COMPARISON_OPACITY)
            label['color'] = _label_color(background)
            painter.setPen(label['color'])
            if label.get('secondary_text'):
                painter.drawText(QRectF(box.left(), box.top(), box.width(), box.height() - 17),
                                 Qt.AlignmentFlag.AlignCenter, label['text'])
                secondary_font = QFont(tokens.FONT_FAMILY)
                secondary_font.setPixelSize(11)
                painter.setFont(secondary_font)
                painter.setPen(QColor(tokens.TEXT_SECONDARY))
                painter.drawText(QRectF(box.left(), box.bottom() - 17, box.width(), 17),
                                 Qt.AlignmentFlag.AlignCenter, label['secondary_text'])
            else:
                painter.drawText(box, Qt.AlignmentFlag.AlignCenter, label['text'])
        painter.restore()

    @staticmethod
    def _y(value, axis, plot):
        return plot.bottom() - (value - axis.lower) / (axis.upper - axis.lower) * plot.height()

    @staticmethod
    def _x(value, axis, plot):
        return plot.left() + (value - axis.lower) / (axis.upper - axis.lower) * plot.width()

    def _draw_time_bars(self, painter, plot, visual):
        dates, sets, axis = visual['dates'], visual['sets'], visual['axis']
        if not dates or not sets:
            return
        first, last = self.owner._detail_range if self.owner._detailed else (0, len(dates))
        slot, gap, bar_width, band = _grouped_bar_geometry(plot.width(), last - first,
                                                         len(sets), self.owner._detailed)
        baseline = self._y(0, axis, plot)
        for index in range(first, last):
            left = plot.left() + (index - first + .5) * slot - band / 2
            for offset, item in enumerate(sets):
                if item['key'] in self.owner._hidden_groups:
                    continue
                value = item['values'][index]
                bucket = item['buckets'][index]
                if value is None or bucket is None:
                    continue
                if value == 0:
                    center = QPointF(left + offset * (bar_width + gap) + bar_width / 2,
                                     min(max(baseline, plot.top() + 3), plot.bottom() - 3))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(_period_color(item['color'], item['previous']))
                    painter.drawEllipse(center, 3, 3)
                    self._hit_regions.append((QRectF(center.x() - 4, center.y() - 4,
                                                     8, 8),
                                              dict(item, bucket=bucket, type='time-hit', kind='bar-total',
                                                   hover_point=center)))
                    continue
                end = self._y(value, axis, plot)
                height = abs(end - baseline)
                bar = QRectF(left + offset * (bar_width + gap), min(end, baseline),
                             bar_width, height)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(_bar_brush(_period_color(item['color'], item['previous']), bar))
                radius = min(bar_width / 2, height / 2)
                painter.drawRoundedRect(bar, radius, radius)
                target = dict(item, bucket=bucket, type='time-hit', kind='bar-total', rect=bar,
                              hover_point=QPointF(bar.center().x(), end))
                self._hit_regions.append((bar, target))

    def _draw_network_stacks(self, painter, plot, visual):
        """Draw adjacent company/period stacks without QtCharts' default bars."""
        slots, groups, axis = visual['slots'], visual['groups'], visual['axis']
        if not slots or not groups:
            return
        first, last = self.owner._detail_range if self.owner._detailed else (0, len(slots))
        slot_width, gap, width, band = _grouped_bar_geometry(plot.width(), last - first,
                                                           len(groups), self.owner._detailed)
        for slot in range(first, last):
            left = plot.left() + (slot - first + .5) * slot_width - band / 2
            for offset, group in enumerate(groups):
                bottom = self._y(0, axis, plot)
                pieces = [segment for segment in visual['segments']
                          if segment['slot'] == slot and segment['group'] == group
                          and segment['key'] not in self.owner._hidden_categories]
                total_height = sum(abs(self._y(float(piece['value']) / axis.scale, axis, plot) -
                                       self._y(0, axis, plot)) for piece in pieces)
                stack = QRectF(left + offset * (width + gap), bottom - total_height,
                               width, total_height)
                outline = QPainterPath()
                outline.addRoundedRect(stack, min(width / 2, total_height / 2),
                                       min(width / 2, total_height / 2))
                painter.save()
                painter.setClipPath(outline, Qt.ClipOperation.IntersectClip)
                zeros = []
                for segment in pieces:
                    value = segment['value']
                    if value == 0:
                        zeros.append((segment, QPointF(stack.center().x(),
                                      min(max(bottom, plot.top() + 3), plot.bottom() - 3))))
                        continue
                    height = abs(self._y(float(value) / axis.scale, axis, plot) -
                                 self._y(0, axis, plot))
                    rect = QRectF(left + offset * (width + gap), bottom - height, width, height)
                    segment['rect'] = rect
                    bottom -= height
                    if value < 0:
                        continue
                    color = QColor(segment['color'])
                    if segment['previous']:
                        color.setAlphaF(tokens.CHART_COMPARISON_OPACITY)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(_bar_brush(color, rect))
                    painter.drawRect(rect)
                    self._hit_regions.append((rect,
                                              dict(segment, type='network-hit')))
                painter.restore()
                for zero_index, (segment, center) in enumerate(zeros):
                    lane = width / len(zeros)
                    peers = [piece for piece, point in zeros
                             if abs(point.y() - center.y()) < 1e-6]
                    shared = lane < 2 and len(peers) > 1
                    center.setX(stack.left() + (zero_index + .5) * lane)
                    if shared:
                        center.setX(stack.center().x())
                    radius = 3. if shared else min(3., lane / 2)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(_period_color(segment['color'], segment['previous']))
                    painter.drawEllipse(center, radius, radius)
                    hit_width = 8. if shared else min(8., lane)
                    self._hit_regions.append((QRectF(center.x() - hit_width / 2,
                                                     center.y() - 4, hit_width, 8),
                                              dict(segment, type='network-hit', hover_point=center,
                                                   hit_radius=4 if shared else None,
                                                   zero_peers=peers if shared else [segment])))

    def _pie_diameter(self, plot, visual):
        """Reserve measured callout columns before choosing a ring diameter."""
        slices = visual['slices']
        base = min(plot.width() * .66, plot.height() * .84, 720 if self.owner._detailed else 190)
        total = sum(float(part['value']) for part in slices)
        texts = [(exact_number(part['value']), f"{100 * float(part['value']) / total:.1f}%")
                 for part in slices]
        angle, sides = 90., []
        for part in slices:
            span = 360 * float(part['value']) / total
            sides.append(int(cos(radians(angle + span / 2)) >= 0))
            angle += span
        center_width = QFontMetrics(emphasis_font(10, QFont.Weight.Bold)).horizontalAdvance(visual['total_text'])
        for size in ((13,) if self.owner._detailed else (12, 11, 10)):
            font = QFont(tokens.FONT_FAMILY)
            font.setPixelSize(size)
            metrics = QFontMetrics(font)
            singles = [metrics.horizontalAdvance(value + ' · ' + percent) + 6 for value, percent in texts]
            stacked = self.owner._detailed or max(singles, default=0) > (plot.width() - base) / 2 - 10
            width = (max((max(metrics.horizontalAdvance(value), metrics.horizontalAdvance(percent)) + 6
                          for value, percent in texts), default=0) if stacked else max(singles, default=0))
            diameter = max(24, min(base, plot.width() - 2 * (width + 14)))
            footer = center_width > diameter * .52 and not visual.get('hide_center')
            budget = plot.height() - (28 if footer else 0) - 4
            if footer:
                diameter = min(diameter, max(24, budget * .84))
            available = (plot.width() - diameter) / 2 - 10
            heights, counts = [0, 0], [0, 0]
            for side, single in zip(sides, singles):
                heights[side] += metrics.height() + (17 if self.owner._detailed or single > available else 0)
                counts[side] += 1
            gap = 4 if self.owner._detailed else 2
            if all(height + gap * max(0, count - 1) <= budget for height, count in zip(heights, counts)):
                break
        visual.update(pie_label_font_size=size,
                      center_footer=QRectF(plot.left(), plot.bottom() - 24, plot.width(), 24) if footer else None,
                      pie_center=plot.center() - QPointF(0, 14 if footer else 0))
        return diameter

    def _draw_network_pie(self, painter, plot, visual):
        """Keep slice angles tied to the original denominator when hidden."""
        slices = visual['slices']
        total = sum(float(item['value']) for item in slices)
        if total <= 0:
            return
        diameter = self._pie_diameter(plot, visual)
        center = visual['pie_center']
        outer = QRectF(center.x() - diameter / 2, center.y() - diameter / 2,
                       diameter, diameter)
        inner_radius = diameter * .28
        angle = 90.
        for item in slices:
            span = 360. * float(item['value']) / total
            item.update(start_angle=angle, span_angle=span, center=center,
                        outer_radius=diameter / 2, inner_radius=inner_radius,
                        percent=100 * float(item['value']) / total)
            if item['key'] not in self.owner._hidden_categories:
                wedge = QPainterPath()
                wedge.moveTo(center)
                wedge.arcTo(outer, angle, span)
                wedge.closeSubpath()
                painter.setPen(QPen(QColor(tokens.CARD_BG), 2.))
                painter.setBrush(QColor(item['color']))
                painter.drawPath(wedge)
            angle += span
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens.CARD_BG))
        painter.drawEllipse(center, inner_radius, inner_radius)
        self._draw_pie_center(painter, center, diameter, visual, 12)
        self._hit_regions.append((outer, dict(visual, type='network-pie-hit', slices=slices)))

    @staticmethod
    def _draw_pie_center(painter, center, diameter, visual, minimum=12):
        if visual.get('hide_center'):
            return
        regular_font = painter.font()
        regular_font.setPixelSize(minimum)
        regular_font.setWeight(regular_font.Weight.Normal)
        width = diameter * .52
        maximum = 18 if diameter >= 300 else 14 if diameter >= 110 else minimum
        if visual.get('center_footer') is not None:
            footer = visual['center_footer']
            number_font = emphasis_font(minimum, regular_font.Weight.Bold)
            number_width = QFontMetrics(number_font).horizontalAdvance(visual['total_text']) + 2
            unit_width = QFontMetrics(regular_font).horizontalAdvance(visual['unit']) + 2
            x = footer.center().x() - (number_width + unit_width + 4) / 2
            painter.setFont(number_font)
            painter.setPen(QColor(tokens.TEXT_PRIMARY))
            painter.drawText(QRectF(x, footer.top(), number_width, footer.height()),
                             Qt.AlignmentFlag.AlignCenter, visual['total_text'])
            painter.setFont(regular_font)
            painter.setPen(QColor(tokens.TEXT_SECONDARY))
            painter.drawText(QRectF(x + number_width + 4, footer.top(), unit_width, footer.height()),
                             Qt.AlignmentFlag.AlignCenter, visual['unit'])
            return
        for size in range(maximum, 9, -1):
            number_font = emphasis_font(size, regular_font.Weight.Bold)
            if QFontMetrics(number_font).horizontalAdvance(visual['total_text']) <= width:
                break
        painter.setFont(number_font)
        painter.setPen(QColor(tokens.TEXT_PRIMARY))
        painter.drawText(QRectF(center.x() - width / 2, center.y() - 19, width, 22),
                         Qt.AlignmentFlag.AlignCenter, visual['total_text'])
        painter.setFont(regular_font)
        painter.setPen(QColor(tokens.TEXT_SECONDARY))
        painter.drawText(QRectF(center.x() - width / 2, center.y() + 3, width, 18),
                         Qt.AlignmentFlag.AlignCenter, visual['unit'])

    def _draw_horizontal_bars(self, painter, plot, visual):
        names, sets, axis = visual['names'], visual['sets'], visual['axis']
        if not names or not sets:
            return
        slot = plot.height() / len(names)
        gap = min(3.0, max(1.0, slot * .045))
        bar_height = min(14.0, max(3.0, (slot * .72 - gap * (len(sets) - 1)) / len(sets)))
        band = len(sets) * bar_height + (len(sets) - 1) * gap
        baseline = self._x(0, axis, plot)
        for index, group in enumerate(names):
            if group in self.owner._hidden_groups:
                continue
            top = plot.bottom() - (index + .5) * slot - band / 2
            for offset, item in enumerate(sets):
                value = item['values'][index]
                if value is None:
                    continue
                if value == 0:
                    center = QPointF(min(max(baseline, plot.left() + 3), plot.right() - 3),
                                     top + offset * (bar_height + gap) + bar_height / 2)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(_period_color(item['colors'][index], item['previous']))
                    painter.drawEllipse(center, 3, 3)
                    self._hit_regions.append((QRectF(center.x() - 4, center.y() - 4, 8, 8),
                                              dict(item, type='total-hit', group=group,
                                                   index=index, value=item['raw_values'][index],
                                                   bucket=item.get('buckets', [None] * len(names))[index],
                                                   hover_point=center)))
                    continue
                end = self._x(value, axis, plot)
                width = abs(end - baseline)
                bar = QRectF(min(end, baseline), top + offset * (bar_height + gap),
                             width, bar_height)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(_bar_brush(
                    _period_color(item['colors'][index], item['previous']), bar,
                    horizontal=True))
                radius = min(bar_height / 2, width / 2)
                painter.drawRoundedRect(bar, radius, radius)
                self._hit_regions.append((bar,
                                          dict(item, type='total-hit', group=group, rect=bar,
                                               color=item['colors'][index],
                                               index=index,
                                               bucket=item.get('buckets', [None] * len(names))[index],
                                               value=item['raw_values'][index])))

    def _draw_line(self, painter, plot, visual):
        if visual['key'] in self.owner._hidden_groups:
            return
        points = visual['points']
        if not points:
            return
        count, axis = visual['count'], visual['axis']
        first, last = self.owner._detail_range if self.owner._detailed else (0, count)
        mapped = [(QPointF(plot.left() + (index - first + .5) * plot.width() / max(1, last - first),
                           self._y(value, axis, plot)), bucket)
                  for index, value, bucket in points if first <= index < last]
        if not mapped:
            return
        if visual['area'] and len(mapped) > 1:
            baseline = self._y(0, axis, plot)
            opacity = tokens.CHART_AREA_OPACITY * (
                tokens.CHART_COMPARISON_OPACITY if visual['previous'] else 1)
            for (first, _), (last, _) in zip(mapped, mapped[1:]):
                # Separate polygons at a zero crossing so negative fill never
                # folds over the positive side or invents a different baseline.
                if (first.y() - baseline) * (last.y() - baseline) < 0:
                    fraction = (baseline - first.y()) / (last.y() - first.y())
                    crossing = QPointF(first.x() + fraction * (last.x() - first.x()),
                                       baseline)
                    self._fill_line_segment(painter, first, crossing, baseline,
                                            visual['color'], opacity)
                    self._fill_line_segment(painter, crossing, last, baseline,
                                            visual['color'], opacity)
                else:
                    self._fill_line_segment(painter, first, last, baseline,
                                            visual['color'], opacity)
        path = QPainterPath(mapped[0][0])
        for point, _ in mapped[1:]:
            path.lineTo(point)
        if len(mapped) > 1 and not self.owner._detailed:
            shadow = QColor(visual['color'])
            shadow.setAlphaF(tokens.CHART_SHADOW_OPACITY *
                             (tokens.CHART_COMPARISON_OPACITY if visual['previous'] else 1))
            painter.save()
            painter.translate(0, 1.4)
            shadow_pen = QPen(shadow, tokens.CHART_LINE_WIDTH + 1.6)
            shadow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            shadow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            if visual['previous'] or visual.get('line_style'):
                shadow_pen.setStyle(visual.get('line_style') or Qt.PenStyle.DashLine)
            painter.setPen(shadow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.restore()
        pen = QPen(_period_color(visual['color'], visual['previous']),
                   visual.get('line_width', tokens.CHART_LINE_WIDTH))
        pen.setCapStyle(Qt.PenCapStyle.FlatCap if self.owner._detailed else Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin if self.owner._detailed else Qt.PenJoinStyle.RoundJoin)
        if visual['previous'] or visual.get('line_style'):
            pen.setStyle(visual.get('line_style') or Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        if len(mapped) == 1 or self.owner._detailed:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_period_color(visual['color'], visual['previous']))
            for point, _ in mapped:
                painter.drawEllipse(point, 2.2, 2.2)
        for point, bucket in mapped:
            self._hit_regions.append((QRectF(point.x() - 8, point.y() - 8, 16, 16),
                                      dict(visual, type='time-hit', bucket=bucket,
                                           hover_point=point, hit_radius=8)))

    @staticmethod
    def _fill_line_segment(painter, first, last, baseline, color, opacity):
        edge = (min(first.y(), last.y()) if first.y() <= baseline and last.y() <= baseline
                else max(first.y(), last.y()))
        if abs(edge - baseline) < .01:
            return
        gradient = QLinearGradient(0, edge, 0, baseline)
        upper = QColor(color)
        upper.setAlphaF(opacity)
        lower = QColor(color)
        lower.setAlphaF(0)
        gradient.setColorAt(0, upper)
        gradient.setColorAt(1, lower)
        area = QPainterPath(first)
        area.lineTo(last)
        area.lineTo(QPointF(last.x(), baseline))
        area.lineTo(QPointF(first.x(), baseline))
        area.closeSubpath()
        painter.fillPath(area, QBrush(gradient))

    def _draw_pie(self, painter, plot, visual):
        slices = visual['slices']
        total = sum(float(item['value']) for item in slices)
        if total <= 0:
            return
        diameter = self._pie_diameter(plot, visual)
        center = visual['pie_center']
        outer = QRectF(center.x() - diameter / 2, center.y() - diameter / 2,
                       diameter, diameter)
        inner_radius = diameter * .28
        angle = 90.0
        for item in slices:
            span = 360.0 * float(item['value']) / total
            wedge = QPainterPath()
            wedge.moveTo(center)
            wedge.arcTo(outer, angle, span)
            wedge.closeSubpath()
            painter.setPen(QPen(QColor(tokens.CARD_BG), 2.0))
            painter.setBrush(QColor(item['color']))
            item['start_angle'] = angle
            item['span_angle'] = span
            item['center'] = center
            item['outer_radius'] = diameter / 2
            item['inner_radius'] = inner_radius
            item['percent'] = 100 * float(item['value']) / total
            if item['key'] not in self.owner._hidden_groups:
                painter.drawPath(wedge)
            angle += span
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens.CARD_BG))
        painter.drawEllipse(center, inner_radius, inner_radius)
        self._draw_pie_center(painter, center, diameter, visual, 12)
        self._hit_regions.append((outer, dict(visual, type='pie-hit', slices=slices)))

    def _hit_at(self, point):
        if not self.chart().plotArea().contains(point):
            return None
        hidden = self.owner._hidden_groups | getattr(self.owner, '_hidden_categories', set())
        candidates = []
        for region, item in reversed(self._hit_regions):
            if not region.contains(point):
                continue
            if item['type'] in ('pie-hit', 'network-pie-hit'):
                item = self._pie_slice_at(point, item)
                if item is None:
                    continue
            if item.get('key', item.get('group')) in hidden:
                continue
            distance = 0.
            if item.get('hit_radius') is not None:
                delta = point - item['hover_point']
                distance = hypot(delta.x(), delta.y())
                if distance > item['hit_radius']:
                    continue
            # Zero glyphs are painted above stack rectangles; retain that
            # visual priority before resolving nearby observations by distance.
            priority = 0 if item.get('zero_peers') else 1
            candidates.append((priority, distance, item))
        return min(candidates, key=lambda candidate: candidate[:2])[2] if candidates else None

    def mouseMoveEvent(self, event):
        # QtCharts' transparent series also receive hover on interpolated lines.
        # Only the visible Fluent geometry is an interactive data mark.
        point = self.mapToScene(event.position().toPoint())
        hit = self._hit_at(point)
        signature = (hit['type'], id(hit.get('bucket')), hit.get('company'),
                     hit.get('key'), hit.get('group'), hit.get('previous'),
                     hit.get('slot'), hit.get('index')) if hit else None
        if signature == self._active_hit:
            return
        self._active_hit = signature
        if hit is None:
            QToolTip.hideText()
            self.owner.set_hover_offset(None)
            self.owner.hover_offset_changed.emit(None)
        else:
            self.owner._fluent_hover(hit)

    def mousePressEvent(self, event):
        if self.owner._detailed and event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_at(self.mapToScene(event.position().toPoint()))
            if hit and hit.get('bucket') is not None:
                self.owner._selected_value = dict(kind='point', company=hit['company'],
                                                 previous=bool(hit.get('previous')),
                                                 bucket=hit['bucket'], group=hit.get('group', hit.get('category')))
                self.owner._fluent_hover(hit)
            else:
                self.owner._selected_value = None
            self.viewport().update()
            event.accept()
            return
        super().mousePressEvent(event)

    @staticmethod
    def _pie_slice_at(point, hit):
        center = hit['slices'][0]['center']
        dx, dy = point.x() - center.x(), center.y() - point.y()
        radius = hypot(dx, dy)
        if radius < hit['slices'][0]['inner_radius'] or radius > hit['slices'][0]['outer_radius']:
            return None
        angle = degrees(atan2(dy, dx)) % 360
        return next((dict(item, type='pie-slice-hit') for item in hit['slices']
                     if (angle - item['start_angle']) % 360 < item['span_angle']), None)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        QToolTip.hideText()
        self._active_hit = None
        self.owner.set_hover_offset(None)
        self.owner.hover_offset_changed.emit(None)
