"""Persistent read state and presentation of dashboard alerts."""

import hashlib
import json

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from qfluentwidgets import CardWidget, PushButton

from statistics_model import METRICS
from stats_text import group_label, label
from stats_elevation import attach_card_elevation


def _display_number(value):
    return f'{value:.2f}'.rstrip('0').rstrip('.')


def _alert_id(session_key, alert):
    # IDs use source identity and values, never a translated display name.
    parts = (session_key, alert.key[0], alert.key[1], alert.metric,
             alert.start.isoformat(), alert.end.isoformat(),
             alert.comparison_start.isoformat(), alert.comparison_end.isoformat(),
             str(alert.before), str(alert.after))
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode('utf-8')).hexdigest()


class AlertsPanel(CardWidget):
    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        attach_card_elevation(self)
        self.settings = settings if settings is not None else QSettings('CIM2SaveStats', 'Desktop')
        self.alerts = []
        self.session_key = ''
        self.companies = {}
        try:
            saved_ids = json.loads(self.settings.value('stats_alerts/read_ids', '[]'))
            self._read_ids = set(saved_ids) if isinstance(saved_ids, list) else set()
        except (TypeError, ValueError):
            self._read_ids = set()
        self._rows = QVBoxLayout(self)
        self._rows.setContentsMargins(16, 16, 16, 16)
        self._rows.setSpacing(8)
        self.title = QLabel(label('alerts'))
        self.title.setObjectName('panelTitle')
        self._rows.addWidget(self.title)
        self.read_all_button = PushButton(label('read-all'))
        self.read_all_button.clicked.connect(self.mark_all_read)
        self._rows.addWidget(self.read_all_button)

    @property
    def unread_count(self):
        return sum(_alert_id(self.session_key, alert) not in self._read_ids
                   for alert in self.alerts)

    def set_snapshot(self, snapshot, session_key, companies):
        self.alerts = list(snapshot.alerts) if snapshot is not None else []
        self.session_key = str(session_key)
        self.companies = dict(companies or {})
        self._refresh()

    def mark_read(self, alert):
        self._read_ids.add(_alert_id(self.session_key, alert))
        self._save()
        self._refresh()

    def mark_all_read(self):
        self._read_ids.update(_alert_id(self.session_key, alert) for alert in self.alerts)
        self._save()
        self._refresh()

    def _save(self):
        self.settings.setValue('stats_alerts/read_ids', json.dumps(sorted(self._read_ids)))
        self.settings.sync()

    def _refresh(self):
        while self._rows.count() > 2:
            item = self._rows.takeAt(2)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        for alert in self.alerts:
            company, group = alert.key
            name = self.companies.get(company, company)
            if company and list(self.companies.values()).count(name) > 1:
                name = f'{name} [{company}]'
            subject = ' · '.join(part for part in (name, group_label(group), label(alert.metric)) if part)
            unit = METRICS[alert.metric].unit
            value = f'{_display_number(alert.before)} → {_display_number(alert.after)} {unit}'
            row = QWidget(self)
            layout = QVBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            subject_label = QLabel(subject, row)
            subject_label.setObjectName('alertMetric')
            subject_label.setWordWrap(True)
            value_label = QLabel(value, row)
            value_label.setObjectName('muted')
            value_label.setWordWrap(True)
            layout.addWidget(subject_label)
            layout.addWidget(value_label)
            if _alert_id(self.session_key, alert) not in self._read_ids:
                button = PushButton(label('read'), row)
                button.clicked.connect(lambda checked=False, a=alert: self.mark_read(a))
                layout.addWidget(button)
            self._rows.addWidget(row)
        self.read_all_button.setEnabled(self.unread_count > 0)
