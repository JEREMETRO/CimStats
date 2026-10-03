"""Network chart cards driven by NetworkChart descriptors and NetworkSnapshot."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QGraphicsOpacityEffect, QVBoxLayout, QWidget

from chart_canvas import ChartData, Series
from stats_charts import ChartPanel, _number
from stats_text import group_label
from stats_controls import FluentSegmentedControl
from statistics_model import period_bounds, summarize_buckets
from ui_kit import LegendChip
import stats_tokens as tokens
import stats_motion as motion_policy

MODE_NAMES = {'line': '趋势', 'trend-bar': '趋势', 'bar': '分布', 'pie': '比例'}
_COMPACT_CATEGORY_NAMES = {
    'bus': '公交', 'tram': '有轨', 'trolley': '无轨', 'metro': '地铁', 'waterbus': '水上', 'misc': '其他',
    'BlueCollar': '蓝领', 'WhiteCollar': '白领', 'BusinessPeople': '商务',
    'Pensioner': '退休', 'Student': '学生', 'Tourist': '游客',
    'single-line': '单线', 'one-zone': '一区', 'two-zones': '二区',
    'three-zones': '三区', 'four-zones': '四区',
}


def network_display_group(mode, company, previous, companies, metric):
    """Keep distinct real companies in distinct columns, also in overall mode."""
    multiple = len(set(companies)) > 1
    if mode == 'period':
        return (company, previous) if multiple else ('comparison' if previous else 'current')
    if mode == 'overall' and not multiple and metric not in ('coverage', 'stopcount'):
        return '__overall__'
    return company


class NetworkChartPanel(ChartPanel):
    """One metric card; descriptor.result is the full trend timeline.

    Quantity bar mode consumes descriptor.bar_result, whose series each hold a
    single model-selected endpoint bucket. The dashboard owns the mode control.
    """

    def __init__(self, parent=None):
        self.descriptor = None
        self.snapshot = None
        self._hidden_categories: set = set()
        self._legend_keys: list = []
        self.company_legend_entries = []
        self._external_mode_control = None
        super().__init__('', parent=parent)
        self._hidden_groups = self._hidden_categories
        self.set_category_palette(tokens.DATA_CATEGORY_COLORS)
        self.summary_label.setStyleSheet(f'color: {tokens.TEXT_SECONDARY}; border: 0; background: transparent;'
                                       f' font-size: {tokens.FONT_SIZE_BODY}px;')
        self._fade_effect = QGraphicsOpacityEffect(self.chart_host)
        self._fade_effect.setOpacity(1)
        self.chart_host.setGraphicsEffect(self._fade_effect)
        self._fade_animation = QPropertyAnimation(self._fade_effect, b'opacity', self)
        self._fade_animation.setDuration(180)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    @property
    def placeholder(self):
        return self.summary_label

    # ---------------------------------------------------------------- API
    def set_mode_control(self, widget: QWidget | None) -> None:
        if self._external_mode_control is not None and self._external_mode_control is not widget:
            self._mode_slot.removeWidget(self._external_mode_control)
            self._external_mode_control.hide()
        self._external_mode_control = widget
        if widget is not None:
            widget.setParent(self)
            self._mode_slot.addWidget(widget)
            widget.show()

    def set_descriptor(self, descriptor, snapshot):
        prior = self.descriptor
        self.descriptor = descriptor
        self.snapshot = snapshot
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
            self._fade_animation.setStartValue(.25)
            self._fade_animation.setEndValue(1.)
            self._fade_animation.start()

    def clear(self):
        self.descriptor = None
        self.snapshot = None
        self.result = None
        self._hidden_categories.clear()
        self._render()

    def set_compact_height(self, height):
        changed = self._compact_height != height
        super().set_compact_height(height)
        if changed:
            self._render()

    def clear_compact_height(self):
        changed = self._compact_height is not None
        super().clear_compact_height()
        if changed:
            self._render()

    # ------------------------------------------------------------- render
    def _render(self):
        if not hasattr(self, 'chart_layout') or not hasattr(self, '_hidden_categories'):
            return
        self._clear_views()
        self._hidden_groups = self._hidden_categories
        self._combined_totals = False
        self.legend_host.clear()
        self.legend_buttons = {}
        self.company_legend_entries = []
        self.series_legend_entries = []
        self.legend_host.hide()
        self.period_label.hide()
        descriptor = self.descriptor
        if descriptor is None:
            self.result = None
        elif self.mode == 'bar' and descriptor.key in ('linecount', 'stopcount', 'vehicles-running'):
            self.result = getattr(descriptor, 'bar_result', None)
        else:
            self.result = descriptor.result
        if self._detailed:
            self.detail_summary.refresh()
        reason = '暂无可用数据' if descriptor is None else (descriptor.reason or
                                                         ('' if self.result is not None else '暂无可用数据'))
        sources = self._sources() if not reason else []
        if not reason and not sources:
            reason = '暂无可用数据'
        self.fullscreen_button.setEnabled(not reason)
        self.chart_host.setVisible(not reason)
        self.placeholder.setVisible(bool(reason))
        if reason:
            self.placeholder.setText(reason)
            return
        builder = {'pie': self._pies, 'bar': self._horizontal_bars, 'trend-bar': self._time_stacks}.get(
            self.mode, self._lines)
        specs = builder(sources)
        self._place_specs(specs)
        self._build_network_legend()
        self._build_company_legend(sources)
        self._build_comparison_legend()
        for entry in self.series_legend_entries:
            if entry['key'] in ('current', 'comparison') and entry['key'] in self._legend_keys:
                self._configure_legend_toggle(entry['key'], entry['widget'])
        self.legend_host.setVisible(bool(self.legend_buttons or self.series_legend_entries or self._group_legend))

    # ------------------------------------------------------------ sources
    def _sources(self):
        """(display column, real company, category, buckets, previous) tuples."""
        result = self.result
        mode = self.snapshot.options.mode
        filters = getattr(self.snapshot, 'filters', None)
        selected = tuple(dict.fromkeys(getattr(filters, 'companies', ()) or self.snapshot.companies or
                                       result.query.companies))
        company_order = {company: index for index, company in enumerate(selected)}
        category_order = {category: index for index, category in enumerate(tokens.DATA_CATEGORY_GROUPS)}

        def order(item):
            company, category = item[0]
            return (company_order.get(company, len(company_order)), company,
                    category_order.get(category, len(category_order)), category)

        owners = [owner for owner, _ in result.series]
        output = [(network_display_group(mode, company, False, owners, self.descriptor.key),
                   company, category, buckets, False)
                  for (company, category), buckets in sorted(result.series.items(), key=order)]
        if mode == 'period':
            output += [(network_display_group(mode, company, True, owners, self.descriptor.key),
                        company, category, buckets, True)
                       for (company, category), buckets in sorted(result.comparison.items(), key=order)]
        return output

    def _group_ids(self, sources):
        groups = list(dict.fromkeys(source[0] for source in sources))
        if self.snapshot.options.mode == 'period' and groups and isinstance(groups[0], tuple):
            companies = list(dict.fromkeys(source[1] for source in sources))
            return sorted(groups, key=lambda group: (companies.index(group[0]), group[1]))
        return groups

    def _category_ids(self, sources):
        rank = {category: index for index, category in enumerate(tokens.DATA_CATEGORY_GROUPS)}
        return sorted({source[2] for source in sources}, key=lambda category: (rank.get(category, len(rank)), category))

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

    def _group_name(self, group):
        if isinstance(group, tuple):
            company, previous = group
            return self._display_company(company) + ' · ' + (
                self.snapshot.options.comparison_label if previous else '本期')
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

    def _status_note(self, bucket, previous):
        parts = []
        if previous and self.snapshot.options.mode == 'period':
            parts.append(f'{self.snapshot.options.comparison_label} {bucket.start:%Y-%m-%d %H:%M}')
        if not bucket.complete:
            parts.append('数据不完整')
        if getattr(bucket, 'partial_period', False):
            parts.append('部分时段')
        return ' · '.join(parts)

    def _legend_key_color(self, key):
        if isinstance(key, tuple):
            return self._company_color(key[0])
        if key in ('__selected__', '__overall__'):
            return QColor(tokens.DATA_COMPANY_COLORS[0])
        if key in ('current', 'comparison'):
            company = (self.descriptor.company_id if self.descriptor is not None else None) or next(
                (part[1] for part in self._sources()), None)
            return self._company_color(company) if company else QColor(tokens.DATA_COMPANY_COLORS[0])
        if key in self.companies:
            return self._company_color(key)
        categories = self._category_ids(self._sources())
        if len(categories) > 1 and key in categories and self.mode in ('bar', 'trend-bar'):
            owners = list(dict.fromkeys(part[1] for part in self._sources()))
            if len(owners) == 1:
                return self._bar_color(owners[0], key, categories)
        return self._category_color(key)

    def _key_name(self, key):
        if isinstance(key, tuple) or key in self.companies or key in (
                '__selected__', '__overall__', 'current', 'comparison'):
            return self._group_name(key)
        return group_label(key)

    def _dates_for(self, sources, count):
        source = next((part[3] for part in sources if part[3] and not part[4]),
                      next((part[3] for part in sources if part[3]), []))
        dates = [bucket.start for bucket in source] or [self.result.current_window[0]]
        while len(dates) < count:
            dates.append(period_bounds(dates[-1], self.result.query.grain)[1])
        return dates[:count]

    # ------------------------------------------------------------- builders
    def _timeline(self, sources):
        count = max([len(source[3]) for source in sources] or [0])
        self._dates = self._dates_for(sources, count)
        return count

    def _time_series(self, sources, *, stacked):
        categories = self._category_ids(sources)
        groups = self._group_ids(sources)
        count = self._timeline(sources)
        series = []
        for group, company, category, buckets, previous in sources:
            if len(categories) > 1:
                key = category
            elif self.snapshot.options.mode == 'overall' and not stacked:
                key = company
            else:
                key = group
            values, notes = [None] * count, [''] * count
            for index, bucket in enumerate(buckets[:count]):
                if bucket.value is not None:
                    values[index] = bucket.value
                    notes[index] = self._status_note(bucket, previous)
            name = group_label(category) if len(categories) > 1 else self._group_name(group)
            if len(categories) > 1 and len(groups) > 1:
                name = f'{self._group_name(group)} · {group_label(category)}'
            color = self._bar_color(company, category, categories) if stacked else self._color(company, category, categories)
            series.append(Series(key=key, name=name, color=color,
                                 values=values, notes=notes, stack=str(group), faded=previous,
                                 dashed=(not stacked) and (previous or (len(categories) > 1 and groups.index(group) > 0))))
        self._legend_keys = categories if len(categories) > 1 else (
            list(dict.fromkeys(item.key for item in series)))
        dates = self._dates
        return ChartData(kind='bar' if stacked else 'line',
                         labels=[self._time_label_text(date, dates) for date in dates],
                         titles=[self._time_title(date) for date in dates], series=series,
                         unit=self.result.metric.unit)

    def _lines(self, sources):
        return [('', self._time_series(sources, stacked=False))]

    def _time_stacks(self, sources):
        return [('', self._time_series(sources, stacked=True))]

    def _horizontal_bars(self, sources):
        categories = self._category_ids(sources)
        groups = self._group_ids(sources)
        visible = [category for category in categories if category not in self._hidden_categories]
        endpoints = {(group, category): self._endpoint_bucket(buckets, previous)
                     for group, _, category, buckets, previous in sources}
        series = []
        for group in groups:
            previous = group[1] if isinstance(group, tuple) else group == 'comparison'
            company = next((part[1] for part in sources if part[0] == group), group)
            colors = [self._bar_color(company, category, categories) for category in visible]
            buckets = [endpoints.get((group, category)) for category in visible]
            series.append(Series(key=str(group), name=self._group_name(group),
                                 color=colors[0] if colors else self._legend_key_color(group), colors=colors,
                                 values=[bucket.value if bucket is not None else None for bucket in buckets],
                                 notes=[self._status_note(bucket, previous) if bucket is not None else ''
                                        for bucket in buckets],
                                 faded=previous and len(groups) > 1 and self.snapshot.options.mode == 'period'))
        self._legend_keys = categories if len(categories) > 1 or len(groups) == 1 else []
        self._group_legend = groups if len(categories) <= 1 and len(groups) > 1 else []
        return [('', ChartData(kind='hbar', labels=[group_label(category) for category in visible],
                               series=series, unit=self.result.metric.unit))]

    def _pies(self, sources):
        groups = self._group_ids(sources)
        share = self.descriptor.key == 'company-passengers'
        if share:
            groups = ['shares']
        specs = []
        for group in groups:
            selected = sources if share else [part for part in sources if part[0] == group]
            slices: dict = {}
            for _, company, category, buckets, previous in selected:
                value = summarize_buckets(buckets, self.result.metric)
                if value is None or value <= 0:
                    continue
                key = company if share else category
                if key not in slices:
                    slices[key] = [self._display_company(company) if share else group_label(category),
                                   Decimal(0),
                                   self._company_color(company) if share else self._category_color(category)]
                slices[key][1] += value
            keys = list(slices)
            labels = [entry[0] for entry in slices.values()]
            values = [entry[1] for entry in slices.values()]
            colors = [entry[2] for entry in slices.values()]
            total = sum(values, Decimal(0))
            caption = '' if share or len(groups) == 1 else self._group_name(group)
            specs.append((caption, ChartData(
                kind='donut', labels=labels, unit=self.result.metric.unit,
                series=[Series(key='share', name=caption or self.title_label.text(), color=QColor(tokens.ACCENT),
                               keys=keys, values=values, colors=colors,
                               faded=any(part[4] for part in selected))],
                center_text=_number(total) if values else '', center_caption=self.result.metric.unit)))
        self._legend_keys = []
        return specs

    def _build_network_legend(self):
        self._group_legend = (getattr(self, '_group_legend', [])
                              if self.mode == 'bar' and self.snapshot.options.mode != 'period' else [])
        keys = list(dict.fromkeys(self._legend_keys))
        if len(keys) > 1:
            for key in keys:
                if self.snapshot.options.mode == 'period' and key in ('current', 'comparison'):
                    continue
                name = self._key_name(key)
                compact = self._compact_height is not None and len(keys) >= 4 and key in _COMPACT_CATEGORY_NAMES
                if key in self.companies or isinstance(key, tuple):
                    chip = self._add_series_legend(key, name, [self._legend_key_color(key)])['widget']
                else:
                    chip = LegendChip(_COMPACT_CATEGORY_NAMES[key] if compact else name,
                                      self._legend_key_color(key), self.legend_host, compact=compact)
                    self.legend_host.flow.addWidget(chip)
                chip.setToolTip(name)
                chip.setAccessibleName(name)
                self._configure_legend_toggle(key, chip)
        for group in self._group_legend:
            self._add_series_legend(group, self._group_name(group), [self._legend_key_color(group)])
        if self.legend_buttons or self._group_legend:
            self.legend_host.show()
            self.legend_host.updateGeometry()

    def _build_company_legend(self, sources):
        self.company_legend_entries = []
        categories = self._category_ids(sources)
        owners = list(dict.fromkeys(part[1] for part in sources))
        if (self.snapshot.options.mode == 'period' or self.mode not in ('bar', 'trend-bar')
                or len(categories) <= 1 or len(owners) <= 1):
            return
        for company in owners:
            colors = {category: self._bar_color(company, category, categories) for category in categories}
            entry = self._add_series_legend(company, self._display_company(company), list(colors.values()))
            self.company_legend_entries.append(dict(company=company, colors=colors, widget=entry['widget']))
        self.legend_host.show()
        self.legend_host.updateGeometry()

    def _comparison_name(self):
        if self.snapshot is None:
            return super()._comparison_name()
        return self.snapshot.options.comparison_label

    def _toggle_category(self, group):
        if group in self._hidden_categories:
            self._hidden_categories.remove(group)
        else:
            self._hidden_categories.add(group)
        self._hidden_groups = self._hidden_categories
        self._apply_category(group)

    # ---------------------------------------------------------- fullscreen
    def _create_clone(self, dialog):
        clone = NetworkChartPanel(dialog)
        clone._hidden_categories = set(self._hidden_categories)
        clone.set_company_palette({key: value.name() for key, value in self._company_palette.items()})
        clone.set_category_palette(self._category_palette)
        clone.set_descriptor(self.descriptor, self.snapshot)
        clone.set_mode(self.mode)
        clone.set_axis_spec(self._axis_override)
        if len(self.descriptor.allowed_modes) > 1:
            selector = FluentSegmentedControl(clone, compact=True)
            for mode in self.descriptor.allowed_modes:
                selector.addItem(mode, MODE_NAMES[mode])
            selector.setCurrentKey(self.mode)
            selector.currentKeyChanged.connect(clone.set_mode)
            clone.set_mode_control(selector)
        return clone

    def _open_fullscreen(self):
        if self.descriptor is None or self.result is None or self.descriptor.reason:
            return
        return super()._open_fullscreen()

    def _adopt_hidden(self, clone):
        if set(clone._hidden_categories) != self._hidden_categories:
            self._hidden_categories = set(clone._hidden_categories)
            self._render()
