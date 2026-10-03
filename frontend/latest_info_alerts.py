"""Homepage presentation of the shared, audited alert snapshot."""
from __future__ import annotations

import json
from math import isfinite

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QScrollArea,
                              QSizePolicy, QVBoxLayout, QWidget)
from qfluentwidgets import (Action, CardWidget, DoubleSpinBox, DropDownPushButton,
                           PrimaryPushButton, PushButton, RoundMenu)

from latest_info_charts import font, label as compact_label
from statistics_model import METRICS
from display_rules import format_number, number_places
from stats_alerts import _alert_id
from stats_elevation import attach_card_elevation
from stats_motion import attach_surface_reveal
from stats_text import group_label, label
import stats_tokens as tokens


THRESHOLD_KEYS = ('percentage_points', 'relative_percent', 'passenger_absolute')
ENABLED_KEY = 'latest_info/alerts_enabled'


def _text(text, parent=None, *, bold=False):
    widget = QLabel(str(text), parent)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setFont(font(12, bold))
    widget.setWordWrap(True)
    widget.setStyleSheet(f'color:{tokens.TEXT_PRIMARY};background:transparent;')
    return widget


def _window(start, end):
    return f'[{start.isoformat(sep=" ")}, {end.isoformat(sep=" ")})'


def _summary_number(value, metric=None):
    return format_number(value, number_places(metric))


class AlertMoreButton(DropDownPushButton):
    """Keep management actions accessible through mouse and keyboard alike."""
    def keyReleaseEvent(self, event):
        super().keyReleaseEvent(event)
        if self.isEnabled() and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._showMenu()
            event.accept()


class AlertSummaryRow(QWidget):
    """Neutral, keyboard-accessible summary; no invented priority or severity."""
    activated = Signal()

    def __init__(self, title, subject, value, unread, parent=None):
        super().__init__(parent)
        self.setObjectName('latestAlertRow')
        self.setMinimumWidth(0)
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(
            f'QWidget#latestAlertRow {{background:transparent;border:1px solid transparent;'
            f'border-bottom-color:{tokens.BORDER};border-radius:6px;}} '
            f'QWidget#latestAlertRow:hover {{background:{tokens.SURFACE_SUBTLE};}} '
            f'QWidget#latestAlertRow:focus {{border:1px solid {tokens.FOCUS_RING};}}')
        box = QVBoxLayout(self)
        box.setContentsMargins(6, 6, 6, 6)
        box.setSpacing(2)
        heading = QHBoxLayout()
        heading.setSpacing(6)
        marker = QLabel('●', self)
        marker.setObjectName('alertNeutralMarker')
        marker.setFont(font(8))
        marker.setFixedSize(8, 12)
        marker.setStyleSheet(f'color:{tokens.ACCENT if unread else tokens.TEXT_DISABLED};background:transparent;')
        marker.setToolTip('未读' if unread else '已读')
        heading.addWidget(marker)
        title_label = compact_label(title, size=14, bold=True, parent=self)
        title_label.setMinimumHeight(20)
        heading.addWidget(title_label, 1)
        box.addLayout(heading)
        subject_label = compact_label(subject, parent=self)
        subject_label.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};background:transparent;')
        subject_label.setMinimumHeight(18)
        box.addWidget(subject_label)
        # Only long identities elide; the numerical line stays a real QLabel.
        value_label = _text(value, self)
        value_label.setObjectName('alertSummaryValue')
        value_label.setMinimumHeight(18)
        box.addWidget(value_label)
        # Labels receive hover events for clipped identities and read markers;
        # their unhandled clicks still propagate to the summary row.

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.activated.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activated.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


def _clear_rows(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            widget = item.widget()
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()


def _comparable(snapshot):
    """Describe the empty state; alert decisions stay entirely in the model."""
    if snapshot is None:
        return False
    for result in snapshot.results.values():
        if not result.metric.confirmed or result.query.metric == 'transfer-coefficient':
            continue
        current, previous = result.current_window, result.comparison_window
        if not previous or current[1] - current[0] != previous[1] - previous[0]:
            continue
        for key, buckets in result.series.items():
            compared = result.comparison.get(key, [])
            if (buckets and compared and len(buckets) == len(compared)
                    and all(b.complete and b.value is not None for b in buckets + compared)):
                return True
    return False


class LatestInfoAlertsPanel(CardWidget):
    thresholds_changed = Signal(object)
    enabled_changed = Signal(bool)

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings if settings is not None else QSettings('CIM2SaveStats', 'Desktop')
        self.setObjectName('latestInfoAlerts')
        self.setMinimumWidth(0)
        self.setMaximumHeight(494)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setFont(font(12))
        attach_card_elevation(self)
        self.alerts = []
        self.session_key = ''
        self.companies = {}
        self._snapshot = None
        self._dialogs = []
        self._list_dialog = None
        self._read_ids = self._saved_read_ids()
        values = []
        for key, default in zip(THRESHOLD_KEYS, (5, 20, 100)):
            try:
                value = float(self.settings.value('statistics/' + key, default))
                values.append(value if isfinite(value) and value >= 0 else default)
            except (TypeError, ValueError):
                values.append(default)
        self._thresholds = tuple(values)
        self._enabled = str(self.settings.value(ENABLED_KEY, True)).lower() not in ('false', '0')
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)
        heading = QHBoxLayout()
        heading.setSpacing(6)
        self.title = compact_label(label('alerts'), size=14, bold=True, parent=self)
        self.unread_label = _text('', self)
        self.unread_label.setWordWrap(False)
        heading.addWidget(self.title, 1)
        heading.addWidget(self.unread_label)
        self.all_button = PushButton('全部', self)
        self.all_button.setFont(font(12))
        self.all_button.setFixedSize(46, 24)
        self.all_button.clicked.connect(self._show_all)
        heading.addWidget(self.all_button)
        root.addLayout(heading)
        context = QHBoxLayout()
        context.setSpacing(4)
        self.scope_label = compact_label('', parent=self)
        self.scope_label.setStyleSheet(f'color:{tokens.TEXT_SECONDARY};background:transparent;')
        context.addWidget(self.scope_label, 1)
        self.more_button = AlertMoreButton('更多', self)
        self.more_button.setFont(font(12))
        self.more_button.setFixedSize(62, 22)
        self.more_button.setAccessibleName('更多提醒操作')
        self.more_menu = RoundMenu(parent=self.more_button)
        self.enable_action = Action('开启提醒', self.more_menu)
        self.enable_action.setCheckable(True)
        self.enable_action.setChecked(self._enabled)
        self.enable_action.toggled.connect(self.set_alerts_enabled)
        self.threshold_action = Action(label('thresholds'), self.more_menu)
        self.threshold_action.triggered.connect(self._show_thresholds)
        self.read_all_action = Action(label('read-all'), self.more_menu)
        self.read_all_action.triggered.connect(self.mark_all_read)
        for action in (self.enable_action, self.threshold_action, self.read_all_action):
            self.more_menu.addAction(action)
        self.more_button.setMenu(self.more_menu)
        context.addWidget(self.more_button)
        root.addLayout(context)
        self.empty_label = _text('', self)
        root.addWidget(self.empty_label)
        self._rows = QVBoxLayout()
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(4)
        root.addLayout(self._rows)
        self._refresh()

    @property
    def thresholds(self):
        return self._thresholds

    @property
    def alerts_enabled(self):
        return self._enabled

    @property
    def unread_count(self):
        return sum(_alert_id(self.session_key, alert) not in self._read_ids for alert in self.alerts)

    def _saved_read_ids(self):
        try:
            ids = json.loads(self.settings.value('stats_alerts/read_ids', '[]'))
            return {value for value in ids if isinstance(value, str)} if isinstance(ids, list) else set()
        except (TypeError, ValueError):
            return set()

    def set_thresholds(self, thresholds):
        values = tuple(float(value) for value in thresholds)
        if len(values) != 3 or any(not isfinite(value) or value < 0 for value in values):
            raise ValueError('提醒阈值必须为三个非负有限数值')
        if values == self._thresholds:
            return
        self._thresholds = values
        for key, value in zip(THRESHOLD_KEYS, values):
            self.settings.setValue('statistics/' + key, value)
        self.settings.sync()
        self.thresholds_changed.emit(values)

    def set_alerts_enabled(self, enabled):
        enabled = bool(enabled)
        self.enable_action.blockSignals(True)
        self.enable_action.setChecked(enabled)
        self.enable_action.blockSignals(False)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        self.settings.setValue(ENABLED_KEY, enabled)
        self.settings.sync()
        self._close_dialogs()
        self._refresh()
        self.enabled_changed.emit(enabled)

    def set_snapshot(self, snapshot, session_key, companies):
        self._close_dialogs()
        self._snapshot = snapshot
        self.alerts = list(snapshot.alerts) if snapshot is not None else []
        self.session_key = str(session_key)
        self.companies = dict(companies or {})
        self._read_ids.update(self._saved_read_ids())
        self._refresh()

    def clear_session(self):
        self.set_snapshot(None, '', {})

    def mark_read(self, alert):
        if alert not in self.alerts:
            return
        self._read_ids.add(_alert_id(self.session_key, alert))
        self._save_reads()

    def mark_all_read(self):
        self._read_ids.update(_alert_id(self.session_key, alert) for alert in self.alerts)
        self._save_reads()

    def _save_reads(self):
        self._read_ids.update(self._saved_read_ids())
        self.settings.setValue('stats_alerts/read_ids', json.dumps(sorted(self._read_ids)))
        self.settings.sync()
        self._refresh()
        if self._list_dialog is not None:
            self._populate_all(self._list_dialog)

    def _company(self, alert):
        company, group = alert.key
        if not company:
            return '全市'
        name = self.companies.get(company, company)
        return f'{name} [{company}]' if list(self.companies.values()).count(name) > 1 else name

    def _row(self, alert, parent, *, expanded=False):
        title = label(alert.metric)
        company = f'{self._company(alert)} · {group_label(alert.key[1])}'
        unit = METRICS[alert.metric].unit
        value = f'{_summary_number(alert.before, alert.metric)} → {_summary_number(alert.after, alert.metric)} {unit}'.strip()
        if not expanded:
            unread = _alert_id(self.session_key, alert) not in self._read_ids
            row = AlertSummaryRow(title, company, value, unread, parent)
            row.activated.connect(lambda a=alert: self._show_details(a))
            row.setAccessibleName(f'{company}\n{title}\n{value}\n{alert.reason}\n{"未读" if unread else "已读"} · 点击或按 Enter 查看详情')
            return row
        row = QWidget(parent)
        row.setObjectName('latestAlertRow')
        row.setMinimumWidth(0)
        row.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.setStyleSheet(f'QWidget#latestAlertRow {{background:{tokens.SURFACE_SUBTLE};'
                         f'border-radius:6px;}}')
        box = QVBoxLayout(row)
        box.setContentsMargins(8, 6, 8, 6)
        box.setSpacing(2)
        for text, bold in ((title, True), (company, False)):
            widget = _text(text, row, bold=bold) if expanded else compact_label(text, bold=bold, parent=row)
            widget.setMinimumHeight(18)
            box.addWidget(widget)
        value_label = _text(value, row) if expanded else compact_label(value, parent=row)
        value_label.setMinimumHeight(18)
        box.addWidget(value_label)
        actions = QHBoxLayout()
        detail = PushButton('详情', row)
        detail.setFixedHeight(26)
        detail.clicked.connect(lambda checked=False, a=alert: self._show_details(a))
        read = PushButton(label('read'), row)
        read.setFixedHeight(26)
        read.setEnabled(_alert_id(self.session_key, alert) not in self._read_ids)
        read.clicked.connect(lambda checked=False, a=alert: self.mark_read(a))
        actions.addWidget(detail)
        actions.addWidget(read)
        box.addLayout(actions)
        row.setAccessibleName(f'{company}\n{title}\n{value}\n{alert.reason}')
        return row

    def _refresh(self):
        self.unread_label.setText(f'未读 {self.unread_count}')
        self.all_button.setToolTip(f'查看全部 {len(self.alerts)} 条提醒')
        self.all_button.setAccessibleName(self.all_button.toolTip())
        self.all_button.setEnabled(self._enabled and bool(self.alerts))
        self.read_all_action.setEnabled(self._enabled and self.unread_count > 0)
        self.scope_label.setText('公司及全市 · 前一完整日' if self._snapshot is not None else '未载入可比数据')
        if self._snapshot is not None:
            filters = self._snapshot.filters
            from company_labels import company_selection_name
            company_name = company_selection_name(self.companies, filters.companies)
            tooltip = f'公司：{company_name}\n城市指标：全市\n统计时间：' + _window(filters.start, filters.end)
            if filters.comparison:
                before, end = filters.comparison
                tooltip += '\n对比 ' + _window(before, end)
            self.scope_label.setToolTip(tooltip)
        _clear_rows(self._rows)
        if self._enabled:
            # Preserve the supplied audited order; no claim of importance.
            for alert in self.alerts[:5]:
                row = self._row(alert, self)
                self._rows.addWidget(row)
                row.show()
        self.empty_label.setVisible(not self._enabled or not self.alerts)
        self.empty_label.setText('提醒已关闭' if not self._enabled else
                                 '当前窗口无达标提醒' if _comparable(self._snapshot) else
                                 '当前窗口无可比数据')

    def _dialog(self, title, *, width=520):
        dialog = QDialog(self.window())
        dialog.setWindowTitle(title)
        dialog.setFont(font(12))
        dialog.setMinimumWidth(width)
        dialog.setStyleSheet(f'QDialog {{background:{tokens.CARD_BG};color:{tokens.TEXT_PRIMARY};}}')
        box = QVBoxLayout(dialog)
        box.setContentsMargins(20, 20, 20, 20)
        box.setSpacing(12)
        box.addWidget(_text(title, dialog, bold=True))
        attach_surface_reveal(dialog)
        return dialog, box

    def _exec_dialog(self, dialog):
        self._dialogs.append(dialog)
        try:
            return dialog.exec()
        finally:
            self._dialogs.remove(dialog)
            dialog.deleteLater()

    def _close_dialogs(self):
        self.more_menu.close()
        for dialog in tuple(self._dialogs):
            dialog.reject()

    def _show_thresholds(self):
        dialog, box = self._dialog(label('thresholds'))
        spins = []
        for title, value in zip(('threshold-points', 'threshold-percent', 'threshold-passengers'), self.thresholds):
            row = QHBoxLayout()
            row.addWidget(_text(label(title), dialog), 1)
            spin = DoubleSpinBox(dialog)
            spin.setRange(0, 1000000)
            spin.setValue(value)
            spin.setAccessibleName(label(title))
            row.addWidget(spin)
            box.addLayout(row)
            spins.append(spin)
        actions = QHBoxLayout()
        cancel, apply = PushButton('取消', dialog), PrimaryPushButton('应用', dialog)
        cancel.clicked.connect(dialog.reject)
        apply.clicked.connect(dialog.accept)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(apply)
        box.addLayout(actions)
        if self._exec_dialog(dialog) == QDialog.DialogCode.Accepted:
            self.set_thresholds(tuple(spin.value() for spin in spins))

    def _show_details(self, alert):
        if alert not in self.alerts:
            return
        dialog, box = self._dialog('提醒详情')
        unit = METRICS[alert.metric].unit
        for text in (f'指标：{label(alert.metric)}',
                     f'公司：{self._company(alert)}', f'公司标识：{alert.key[0] or "全市"}',
                     f'分组：{group_label(alert.key[1])}',
                     f'对比原值：{_summary_number(alert.before, alert.metric)} {unit}',
                     f'本期原值：{_summary_number(alert.after, alert.metric)} {unit}',
                     '本期窗口：' + _window(alert.start, alert.end),
                     '对比窗口：' + _window(alert.comparison_start, alert.comparison_end),
                     '原因：' + alert.reason):
            box.addWidget(_text(text, dialog))
        actions = QHBoxLayout()
        read, close = PushButton(label('read'), dialog), PrimaryPushButton('关闭', dialog)
        read.setEnabled(_alert_id(self.session_key, alert) not in self._read_ids)
        def mark():
            self.mark_read(alert)
            read.setEnabled(False)
        read.clicked.connect(mark)
        close.clicked.connect(dialog.accept)
        actions.addStretch()
        actions.addWidget(read)
        actions.addWidget(close)
        box.addLayout(actions)
        self._exec_dialog(dialog)

    def _populate_all(self, dialog):
        _clear_rows(dialog.alert_rows)
        dialog.unread.setText(f'共 {len(self.alerts)} 条 · 未读 {self.unread_count}')
        dialog.read_all.setEnabled(self.unread_count > 0)
        for alert in self.alerts:
            row = self._row(alert, dialog.alert_body, expanded=True)
            dialog.alert_rows.addWidget(row)
            row.show()

    def _show_all(self):
        if not self._enabled or not self.alerts:
            return
        dialog, box = self._dialog('全部提醒', width=560)
        dialog.unread = _text('', dialog)
        box.addWidget(dialog.unread)
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(360)
        scroll.setMaximumHeight(540)
        dialog.alert_body = QWidget()
        dialog.alert_rows = QVBoxLayout(dialog.alert_body)
        dialog.alert_rows.setContentsMargins(0, 0, 0, 0)
        dialog.alert_rows.setSpacing(8)
        scroll.setWidget(dialog.alert_body)
        box.addWidget(scroll)
        actions = QHBoxLayout()
        dialog.read_all, close = PushButton(label('read-all'), dialog), PrimaryPushButton('关闭', dialog)
        dialog.read_all.clicked.connect(self.mark_all_read)
        close.clicked.connect(dialog.accept)
        actions.addStretch()
        actions.addWidget(dialog.read_all)
        actions.addWidget(close)
        box.addLayout(actions)
        self._list_dialog = dialog
        self._populate_all(dialog)
        try:
            self._exec_dialog(dialog)
        finally:
            self._list_dialog = None
