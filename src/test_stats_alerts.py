import os
from datetime import datetime as D
from decimal import Decimal

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLabel

from dashboard_model import DashboardResult, FilterState
from statistics_model import Alert
from stats_alerts import AlertsPanel


def app():
    return QApplication.instance() or QApplication([])


def snapshot(after=Decimal(20), company='p1'):
    alert = Alert('cashflow', (company, '总计'), '数值明显变化', Decimal(10),
                  after, D(2024, 1, 2), D(2024, 1, 1),
                  D(2024, 1, 3), D(2024, 1, 2))
    filters = FilterState((company,), D(2024, 1, 2), D(2024, 1, 3),
                          comparison=(D(2024, 1, 1), D(2024, 1, 2)))
    return DashboardResult(filters, {}, {}, [alert])


def test_single_read_survives_restart_and_value_change_is_new(tmp_path):
    app()
    settings = QSettings(str(tmp_path / 'alert.ini'), QSettings.Format.IniFormat)
    panel = AlertsPanel(settings)
    panel.set_snapshot(snapshot(), 'save-a', {'p1': 'Same name'})
    assert panel.unread_count == 1
    panel.mark_read(panel.alerts[0])
    assert panel.unread_count == 0
    settings.sync()

    reopened = AlertsPanel(QSettings(str(tmp_path / 'alert.ini'), QSettings.Format.IniFormat))
    reopened.set_snapshot(snapshot(), 'save-a', {'p1': 'Same name'})
    assert reopened.unread_count == 0
    reopened.set_snapshot(snapshot(Decimal(21)), 'save-a', {'p1': 'Same name'})
    assert reopened.unread_count == 1
    reopened.set_snapshot(snapshot(), 'save-b', {'p1': 'Same name'})
    assert reopened.unread_count == 1
    reopened.set_snapshot(snapshot(company='p2'), 'save-a', {'p2': 'Same name'})
    assert reopened.unread_count == 1


def test_mark_all_read_and_filter_change_keeps_independent_ids(tmp_path):
    app()
    settings = QSettings(str(tmp_path / 'alert.ini'), QSettings.Format.IniFormat)
    panel = AlertsPanel(settings)
    first = snapshot()
    second = snapshot(Decimal(30)).alerts[0]
    first.alerts.append(second)
    panel.set_snapshot(first, 'save-a', {'p1': 'Company'})
    assert panel.unread_count == 2
    panel.mark_all_read()
    assert panel.unread_count == 0
    panel.set_snapshot(snapshot(Decimal(40)), 'save-a', {'p1': 'Company'})
    assert panel.unread_count == 1


def test_alert_labels_wrap_and_show_short_values_with_unit(tmp_path):
    app()
    panel = AlertsPanel(QSettings(str(tmp_path / 'alert.ini'), QSettings.Format.IniFormat))
    panel.set_snapshot(snapshot(Decimal('20.123456789')), 'save-a',
                       {'p1': 'A very long company name that must wrap in a narrow panel'})
    row = panel._rows.itemAt(2).widget()
    labels = row.findChildren(QLabel)
    assert len(labels) == 2
    assert all(widget.wordWrap() for widget in labels)
    assert labels[1].text() == '10 → 20.12 货币'
    assert row.layout().spacing() >= 8


def test_damaged_read_state_does_not_block_panel(tmp_path):
    app()
    settings = QSettings(str(tmp_path / 'alert.ini'), QSettings.Format.IniFormat)
    settings.setValue('stats_alerts/read_ids', '{bad json')
    panel = AlertsPanel(settings)
    panel.set_snapshot(snapshot(), 'save-a', {'p1': 'Company'})
    assert panel.unread_count == 1


def test_clearing_snapshot_immediately_hides_previous_alert_rows(tmp_path):
    application = app()
    panel = AlertsPanel(QSettings(str(tmp_path / 'alert.ini'), QSettings.Format.IniFormat))
    panel.set_snapshot(snapshot(), 'save-a', {'p1': 'Previous company'})
    panel.show()
    application.processEvents()
    old_row = panel._rows.itemAt(2).widget()
    assert old_row.isVisible()
    panel.set_snapshot(None, 'save-b', {})
    assert not old_row.isVisible()
    assert panel.unread_count == 0
    panel.close()
