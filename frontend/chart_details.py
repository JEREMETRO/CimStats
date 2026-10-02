"""Read-only chart summaries, complete values, and collision-free label layout."""
from __future__ import annotations
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from math import ceil, floor, log10
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QScrollArea, QTableView, QVBoxLayout, QWidget)
from statistics_model import summarize_buckets
from stats_text import group_label
import stats_tokens as tokens
from stats_typography import apply_emphasis_font, emphasis_css


def detail_window(count, zoom=1, first=0):
    length = max(1, min(count, ceil(count / max(1, zoom))))
    start = max(0, min(int(first), count - length))
    return start, start + length


def detail_axis_range(values, zero=False, negative_padding=.05):
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        numbers = [0., 1.]
    low, high = min(numbers), max(numbers)
    magnitude = max(abs(low), abs(high))
    scale, suffix = ((100000000, '亿') if magnitude >= 100000000 else
                     (10000, '万') if magnitude >= 10000 else
                     (1000, '千') if magnitude >= 1000 else (1, ''))
    low, high = low / scale, high / scale
    if zero:
        low, high = min(0., low), max(0., high)
        span = max(high - low, .01)
        # Reserve the label line below negative bars without broadening positive
        # cashflow/passenger ranges. Smaller viewports supply a larger fraction.
        if low < 0:
            low -= span * negative_padding
        high += span * .05
    else:
        padding = max((high - low) * .05, abs(high) * 1e-12, 1e-12)
        if low == high:
            padding = max(abs(high) * .02, .01)
        low, high = low - padding, high + padding
    span = max(high - low, 1e-15)
    power = floor(log10(span / 7))
    options = []
    for exponent in range(power - 1, power + 3):
        for unit in (1, 2, 2.5, 5):
            step = unit * 10 ** exponent
            first, last = floor(low / step) * step, ceil(high / step) * step
            ticks = round((last - first) / step) + 1
            if 4 <= ticks <= 12:
                options.append((0 if ticks >= 6 else 1, (last - first) - span,
                                abs(ticks - 8), first, last, step))
    if options:
        _, _, _, first, last, step = min(options)
    else:
        first, last, step = low, high, span / 7
    step = float(f'{step:.12g}')
    places = max(0, -Decimal(str(step)).normalize().as_tuple().exponent)
    return dict(lower=round(first, places), upper=round(last, places), step=step,
                scale=scale, unit_suffix=suffix)


def detail_axis_values(visuals, first, last, hidden):
    values, zero = [], False
    for visual in visuals:
        if visual['type'] == 'line' and visual['key'] not in hidden:
            values.extend(bucket.value for index, _, bucket in visual['points'] if first <= index < last)
        elif visual['type'] == 'time-bars':
            zero = True
            for entry in visual['sets']:
                if entry['key'] not in hidden:
                    values.extend(bucket.value for bucket in entry['buckets'][first:last]
                                  if bucket is not None and bucket.value is not None)
        elif visual['type'] == 'network-stacks':
            zero = True
            totals = defaultdict(lambda: Decimal(0))
            for part in visual['segments']:
                if first <= part['slot'] < last and part['key'] not in hidden:
                    totals[part['slot'], part['group']] += max(Decimal(0), part['value'])
            values.extend(totals.values())
    return values, zero


def detail_axis_format(step):
    places = max(0, -Decimal(str(step)).normalize().as_tuple().exponent)
    return f'%.{places}f'


def network_display_group(mode, company, previous, companies, metric):
    """Keep distinct real companies in distinct columns, also in overall mode."""
    multiple = len(set(companies)) > 1
    if mode == 'period':
        return (company, previous) if multiple else ('comparison' if previous else 'current')
    if mode == 'overall' and not multiple and metric not in ('coverage', 'stopcount'):
        return '__overall__'
    return company


def detail_canvas_plan(visuals, rows, text_width=None, zoom=1):
    """Reserve a real, scrollable column and label lanes for every observation."""
    measure = text_width or (lambda text: len(text) * 8)
    columns, lane_keys, texts = 0, [], []
    for visual in visuals:
        kind = visual['type']
        if kind == 'line':
            columns = max(columns, visual['count'])
            key = (visual['company'], visual['group'], bool(visual['previous']))
            if key not in lane_keys:
                lane_keys.append(key)
            texts.extend(exact_number(bucket.value) for _, _, bucket in visual['points'])
            texts.extend(bucket.start.strftime('%Y-%m-%d %H:%M') for _, _, bucket in visual['points'])
        elif kind == 'time-bars':
            columns = max(columns, len(visual['dates']))
            for entry in visual['sets']:
                key = (entry['company'], entry['group'], bool(entry['previous']))
                if key not in lane_keys:
                    lane_keys.append(key)
                texts.extend(exact_number(bucket.value) for bucket in entry['buckets'] if bucket)
            texts.extend(date.strftime('%Y-%m-%d %H:%M') for date in visual['dates'])
        elif kind == 'network-stacks':
            columns = max(columns, len(visual['slots']) * len(visual['groups']))
            categories = list(dict.fromkeys(part['category'] for part in visual['segments']))
            categories += [row['group'] for row in rows if row['kind'] != 'stack-total'
                           and row['display_group'] in visual['groups'] and row['group'] not in categories]
            lane_keys = ['stack-total', *dict.fromkeys(categories)]
            texts.extend(exact_number(part['value']) for part in visual['segments'])
    if not columns:
        return None
    for row in rows:
        if row['kind'] == 'stack-total':
            texts.append(stack_total_text(row))
    column_width = max(80, max((measure(text) for text in texts), default=0) + 16) * max(1, zoom)
    return dict(columns=columns, column_width=column_width, width=columns * column_width + 120,
                lanes=len(lane_keys), lane_keys=lane_keys, header_height=len(lane_keys) * 26 + 32)


def stack_total_text(row):
    return exact_number(row['visible_total'])


def place_detail_labels(requests, bounds, plot_bounds=None):
    """Canvas width is preallocated; keep all labels in their own column/lane."""
    labels = []
    grid = defaultdict(list)
    cell_width = max((request['size'][0] + 4 for request in requests), default=80)
    def cells(rect):
        return range(floor(rect.left() / cell_width), floor(rect.right() / cell_width) + 1)
    def collides(rect):
        padded = rect.adjusted(-2, -2, 2, 2)
        return any(padded.intersects(other) for cell in cells(padded) for other in grid[cell])
    for request in requests:
        width, height = request['size']
        x = min(max(request['point'].x() - width / 2, bounds.left()), bounds.right() - width)
        y = bounds.top() + 6 + request['lane'] * 26
        candidates = []
        if 'inside_rect' in request:
            candidates.append(request['inside_rect'])
        if plot_bounds is not None:
            point = request['point']
            for offset in range(4):
                # A pair of almost equal peaks may have room beside the labels
                # but not for another row above them. Keep the text near its bar.
                shifts = (0, -8, 8, -16, 16) if request.get('outside_side') else (0,)
                for shift in shifts:
                    shifted_x = min(max(x + shift, plot_bounds.left()), plot_bounds.right() - width)
                    if request.get('outside_side', -1) < 0:
                        candidates.append(QRectF(shifted_x, point.y() - height - 5 - offset * 26, width, height))
                    if request.get('outside_side', 1) > 0:
                        candidates.append(QRectF(shifted_x, point.y() + 5 + offset * 26, width, height))
        fallback = QRectF(x, y, width, height)
        rect = next((candidate for candidate in candidates
                     if bounds.united(plot_bounds).contains(candidate)
                     and (candidate is request.get('inside_rect') or plot_bounds.contains(candidate))
                     and not collides(candidate)), fallback)
        labels.append(dict(request, rect=rect))
        for cell in cells(rect):
            grid[cell].append(rect)
    return labels


def place_pie_labels(requests, bounds, center, radius):
    """Keep slice callouts outside the ring, ordered vertically on each side."""
    labels = {}
    for right in (False, True):
        side = [(index, request) for index, request in enumerate(requests)
                if (request['point'].x() >= center.x()) == right]
        side.sort(key=lambda pair: pair[1]['point'].y())
        if not side:
            continue
        available = ((bounds.right() - center.x() - radius) if right else
                     (center.x() - radius - bounds.left())) - 8
        gap = min((request.get('gap', 4) for _, request in side), default=4)
        if (any(request['size'][0] > available for _, request in side) or
                sum(request['size'][1] for _, request in side) + gap * (len(side) - 1) > bounds.height()):
            return None
        rows, edge = [], bounds.top()
        for index, request in side:
            width, height = request['size']
            y = max(edge, min(request['point'].y() - height / 2, bounds.bottom() - height))
            rows.append([index, request, y])
            edge = y + height + gap
        edge = bounds.bottom()
        for row in reversed(rows):
            row[2] = min(row[2], edge - row[1]['size'][1])
            edge = row[2] - gap
        for index, request, y in rows:
            width, height = request['size']
            x = center.x() + radius + 8 if right else center.x() - radius - 8 - width
            labels[index] = dict(request, rect=QRectF(x, y, width, height),
                                 pie_side=right)
    return [labels[index] for index in range(len(requests))]


def exact_number(value):
    if value is None:
        return '—'
    text = format(value, ',f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def value_marker_matches(mark, selected):
    if mark.get('company') != selected['company'] or bool(mark.get('previous')) != selected['previous']:
        return False
    if selected['bucket'] is not None:
        return mark.get('bucket') is selected['bucket']
    if selected['kind'] == 'stack-total':
        return (mark.get('kind') == 'stack-total' and mark.get('slot') == selected['slot']
                and mark.get('display_group') == selected['display_group'])
    return mark.get('group') == selected['group']


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
            card = dict(company=company, name=(company_name(company) if company_name else
                                                     companies.get(company, {'__selected__': '已选公司', '': '整体'}.get(company, company))),
                              period=comparison_label if previous else '本期', window=window,
                              values=values, unit=result.metric.unit, kind=result.metric.kind)
            if result.metric.kind == 'flow':
                # Align real bucket intervals across categories. A missing category
                # cannot count as zero in the company mean; an observed zero can.
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


def _sources(panel):
    if hasattr(panel, '_sources'):
        return panel._sources()
    result = panel.result
    output = [(company, company, group, buckets, False)
              for (company, group), buckets in result.series.items()]
    if panel.mode != 'pie':
        output += [(company, company, group, buckets, True)
                   for (company, group), buckets in result.comparison.items()]
    return output


def value_rows(panel):
    result = panel.result
    if result is None:
        return []
    hidden = getattr(panel, '_hidden_groups', set()) | getattr(panel, '_hidden_categories', set())
    visual_keys = {}
    for view in panel.chart_views:
        for visual in view.visuals:
            if visual['type'] == 'line':
                for _, _, bucket in visual['points']:
                    visual_keys[id(bucket)] = visual['key']
            elif visual['type'] == 'time-bars':
                for entry in visual['sets']:
                    for bucket in entry['buckets']:
                        visual_keys[id(bucket)] = entry['key']
            elif visual['type'] == 'network-stacks':
                for segment in visual['segments']:
                    visual_keys[id(segment['bucket'])] = segment['key']
    rows = []
    sources = _sources(panel)
    categories = {source[2] for source in sources}
    templates = {}
    for display_group, company, group, buckets, previous in sources:
        period = ('对比' if previous else '本期')
        if previous and hasattr(panel, 'snapshot') and panel.snapshot:
            period = panel.snapshot.options.comparison_label
        window = result.comparison_window if previous else result.current_window
        if not window:
            continue
        def row(value, start, end, bucket=None, slot=None):
            fallback = company if getattr(panel, '_combined_totals', False) else group
            if getattr(panel, 'snapshot', None):
                if panel.mode == 'pie':
                    fallback = company if panel.descriptor.key == 'company-passengers' else group
                elif panel.mode != 'bar' and len(categories) == 1:
                    fallback = (company if panel.mode == 'line' and panel.snapshot.options.mode == 'overall'
                                else display_group)
            key = visual_keys.get(id(bucket), fallback)
            if not result.metric.confirmed:
                value = None
            return dict(kind='point' if bucket is not None else 'summary',
                        company=company, name=(panel._display_company(company) if hasattr(panel, '_display_company') else
                                              panel.companies.get(company, {'__selected__': '已选公司', '': '整体'}.get(company, company))),
                        previous=previous, period=period, group=group, key=key,
                        start=start, end=end, value=value, unit=result.metric.unit,
                        bucket=bucket, slot=slot, display_group=display_group,
                        visible=key not in hidden, original_total=None, visible_total=None)
        templates[display_group, company, group, previous] = row(None, *window)
        if panel.mode in ('bar', 'pie', 'summary'):
            if panel.mode == 'bar' and hasattr(panel, '_endpoint_bucket'):
                bucket = panel._endpoint_bucket(buckets, previous)
                rows.append(row(bucket.value if bucket else None,
                                (bucket.observed or bucket.start) if bucket else window[0],
                                bucket.end if bucket else window[1], bucket))
            else:
                rows.append(row(summarize_buckets(buckets, result.metric), *window))
        else:
            rows.extend(row(bucket.value, bucket.start, bucket.end, bucket, index)
                        for index, bucket in enumerate(buckets))
    # A shorter source is unknown at the other columns' actual time slot.
    # Keep an explicit missing row so totals never treat that absence as zero.
    references = {(item['slot'], item['display_group'], item['previous']): item
                  for item in rows if item['kind'] == 'point'}
    missing_keys = set()
    for view in panel.chart_views:
        for visual in view.visuals:
            if visual['type'] != 'network-stacks':
                continue
            for display_group, company, group, buckets, previous in sources:
                if display_group not in visual['groups']:
                    continue
                for slot in visual['slots']:
                    key = display_group, company, group, previous, slot
                    if slot < len(buckets) or key in missing_keys:
                        continue
                    reference = references.get((slot, display_group, previous))
                    window = result.comparison_window if previous else result.current_window
                    if reference is None or window is None or not window[0] <= reference['start'] < window[1]:
                        continue
                    rows.append(dict(templates[key[:4]], kind='missing', slot=slot,
                                     start=reference['start'], end=reference['end']))
                    missing_keys.add(key)
    # Full totals use the original source, including missing and hidden segments.
    grouped_points = defaultdict(list)
    for row in rows:
        if row['kind'] in ('point', 'missing'):
            grouped_points[row['slot'], row['display_group']].append(row)
    for view in panel.chart_views:
        for visual in view.visuals:
            if visual['type'] != 'network-stacks':
                continue
            for slot in visual['slots']:
                for display_group in visual['groups']:
                    parts = grouped_points[slot, display_group]
                    if not parts:
                        continue
                    visible = [part for part in parts if part['visible']]
                    def total(items):
                        return (sum((item['value'] for item in items), Decimal(0))
                                if items and all(item['value'] is not None for item in items) else None)
                    item = dict(parts[0], kind='stack-total', group='整柱合计', bucket=None,
                                name=' / '.join(dict.fromkeys(part['name'] for part in parts)),
                                value=total(parts), original_total=total(parts),
                                visible_total=total(visible), visible=bool(visible))
                    rows.append(item)
    return rows


def place_value_labels(requests, bounds, obstacles=()):
    """Place every request or return None; never return a partial sample."""
    if sum(item['size'][0] * item['size'][1] for item in requests) > bounds.width() * bounds.height() * .75:
        return None
    placed = []
    for request in sorted(requests, key=lambda item: -item['size'][0]):
        point = request['point']
        width, height = request['size']
        if 'outside_side' in request:
            x = min(max(point.x() - width / 2, bounds.left()), bounds.right() - width)
            options = [(x, point.y() + 5 + lane * (height + 3)
                        if request['outside_side'] > 0 else point.y() - height - 5 - lane * (height + 3))
                       for lane in range(4)]
        else:
            options = [(point.x() - width / 2, point.y() - height - 5),
                       (point.x() + 6, point.y() - height / 2),
                       (point.x() - width - 6, point.y() - height / 2),
                       (point.x() - width / 2, point.y() + 5)]
            options += [(point.x() - width / 2, bounds.top() + lane * (height + 3))
                        for lane in range(6)]
        for x, y in options:
            rect = QRectF(x, y, width, height)
            if (bounds.contains(rect) and not any(rect.intersects(obstacle) for obstacle in obstacles) and
                    not any(rect.adjusted(-2, -2, 2, 2).intersects(item['rect']) for item in placed)):
                placed.append(dict(request, rect=rect))
                break
        else:
            return None
    return placed


class ValuesModel(QAbstractTableModel):
    columns = ('值', '单位', '系列', '日期 / 期间', '公司', '周期', '显示', '可见合计', '原总量')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def replace_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return self.columns[section] if orientation == Qt.Orientation.Horizontal else section + 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self.rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            dates = f"{item['start']:%Y-%m-%d %H:%M} — {item['end']:%Y-%m-%d %H:%M}"
            return (exact_number(item['value']), item['unit'], group_label(item['group']), dates,
                    item['name'], item['period'], '可见' if item['visible'] else '已隐藏',
                    exact_number(item['visible_total']) if item['kind'] == 'stack-total' else '',
                    exact_number(item['original_total']) if item['kind'] == 'stack-total' else '')[index.column()]
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor(tokens.TEXT_PRIMARY if item['visible'] else tokens.TEXT_SECONDARY)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignRight
                       if index.column() in (0, 7, 8) else Qt.AlignmentFlag.AlignLeft))


class ChartNumbers(QFrame):
    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setObjectName('chartNumbers')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 0)
        layout.setSpacing(3)
        self.heading = QLabel('全部数值', self)
        self.heading.setStyleSheet(f'font-size:12px; color:{tokens.TEXT_SECONDARY}; border:0;')
        layout.addWidget(self.heading)
        self.table = QTableView(self)
        font = QFont(tokens.FONT_FAMILY)
        font.setPixelSize(13 if panel._detailed else 12)
        self.table.setFont(font)
        self.model = ValuesModel(self)
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(28)
        # The detail table is hidden by default. Autosizing a hidden header
        # still scans its model on queued layout requests and delays animation.
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setStyleSheet(f'QTableView {{background:{tokens.CARD_BG};color:{tokens.TEXT_PRIMARY};'
                                 f'border:1px solid {tokens.BORDER};selection-background-color:{tokens.ACCENT_SOFT};}}')
        self.table.setMinimumHeight(84 if panel._detailed else 68)
        self.table.setMaximumHeight(112 if panel._detailed else 88)
        self.table.clicked.connect(self._selected)
        layout.addWidget(self.table)
        self.hide()

    def refresh(self):
        rows = value_rows(self.panel)
        self.model.replace_rows(rows)
        minimum, limit = (84, 112) if self.panel._detailed else (68, 88)
        desired = self.table.horizontalHeader().height() + min(len(rows), 7) * 28 + 20
        self.table.setMaximumHeight(min(limit, max(minimum, desired)))
        self.heading.setText(f'全部数值 · {len(rows)} 项')
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self.table.resizeColumnsToContents()

    def _selected(self, index):
        item = self.model.rows[index.row()]
        if item['value'] is None or not item['visible']:
            return
        self.panel._selected_value = item
        if self.panel._detailed and item.get('slot') is not None:
            first, last = self.panel._detail_range
            if not first <= item['slot'] < last:
                self.panel._detail_first = item['slot']
                self.panel._configure_detail_canvas()
        for view in self.panel.chart_views:
            view.viewport().update()
        target = next((target for target in self.panel._hover_targets
                       if target['bucket'] is item['bucket'] and target['company'] == item['company']), None)
        if target is not None:
            self.panel._hide_hover_markers()
            self.panel._show_hover_target(target)


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
        compare = (self.panel.snapshot.options.comparison_label
                   if getattr(self.panel, 'snapshot', None) else '对比')
        self.cards = summary_cards(self.panel.result, self.panel.companies, compare,
                                   getattr(self.panel, '_display_company', None))
        while self._summary_layout.count():
            item = self._summary_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        body = QWidget(self)
        self._body = body
        layout = QGridLayout(body)
        self._cards_layout = layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self._surfaces = []
        for card in self.cards:
            display_values = card.get('display_values', card['values'])
            surface = QFrame(body)
            surface.setObjectName('detailSummaryCard')
            surface.setMinimumWidth(0)
            surface.setStyleSheet(f'QFrame#detailSummaryCard {{background:{tokens.CARD_BG};'
                                 f'border:1px solid {tokens.BORDER};border-radius:8px;}}')
            box = QVBoxLayout(surface)
            box.setContentsMargins(10, 6, 10, 6)
            box.setSpacing(1)
            heading = QLabel(card['name'] + (' · ' + card['period'] if self.panel.result.comparison else ''), surface)
            heading.setStyleSheet(emphasis_css(14) + f'color:{tokens.TEXT_PRIMARY};border:0;')
            apply_emphasis_font(heading, 14)
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
                if 'display_values' in card and (group, value) == display_values[1]:
                    number.setToolTip(f"按 {card['average_periods']} 个有完整类别数值的实际时段计算；"
                                      '零值计入，缺失时段排除。显示至多两位小数。')
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
                # Totals with cents need more room than integer passenger counts.
                # Give all cards the measured width before resorting to wrapping.
                desired = max(desired, min(420, 2 + len(cells) *
                                           (max(cell.minimumSize().width() for cell in cells) + 18)))
            self._surfaces.append((surface, values, cells, desired))
        self._summary_layout.addWidget(body)
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
                # Recalculate the card before measuring the outer grid. Its old
                # narrow layout may have stacked cells and a cached taller hint.
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
