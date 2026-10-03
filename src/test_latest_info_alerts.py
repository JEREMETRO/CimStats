"""Homepage alerts: pure day comparisons and isolated offscreen GUI checks."""
import os
from datetime import datetime as D
from decimal import Decimal

import pytest

from dashboard_model import DashboardResult, FilterState
from statistics_model import Alert, HistoryStore, QueryCancelled


def history(metric, before, after, *, company='p1', divider=0, missing=None):
    return [dict(指标=metric, 分组='bus', 模拟时间=D(2024, 1, day, hour).isoformat(),
                 值=str(value), 分母=str(divider), 公司标识=company,
                 公司名称='同名公司', 当前槽位='False')
            for day, value in ((1, before), (2, after)) for hour in range(24)
            if (day, hour) != missing]


def build(rows, *, thresholds=(5, 20, 100), filters=None, cancelled=None):
    from src.latest_info_alerts import build_latest_alerts, default_alert_filters
    store = HistoryStore(rows, D(2024, 1, 3, 14, 37))
    filters = filters or default_alert_filters(store.simulation_time, ('p1',))
    return build_latest_alerts(store, filters, thresholds, cancelled)


@pytest.mark.parametrize('clock,end,start,previous', [
    (D(2024, 1, 3, 14, 37), D(2024, 1, 3), D(2024, 1, 2), D(2024, 1, 1)),
    (D(2024, 3, 1), D(2024, 3, 1), D(2024, 2, 29), D(2024, 2, 28)),
    (D(2024, 1, 1, 0, 0, 1), D(2024, 1, 1), D(2023, 12, 31), D(2023, 12, 30)),
])
def test_default_filters_use_previous_complete_simulation_day(clock, end, start, previous):
    from src.latest_info_alerts import default_alert_filters
    filters = default_alert_filters(clock, ('stable-a', 'stable-b'))
    assert filters == FilterState(('stable-a', 'stable-b'), start, end, 'hour', (previous, start))


def test_home_alerts_need_no_statistics_tab_visit():
    result = build(history('cashflow', 100, 150))
    assert [(a.metric, a.key, a.before, a.after, a.reason) for a in result.alerts] == [
        ('cashflow', ('p1', '总计'), Decimal(24), Decimal(36), '数值明显变化')]
    assert result.alerts[0].start == D(2024, 1, 2)
    assert result.alerts[0].end == D(2024, 1, 3)
    assert result.alerts[0].comparison_start == D(2024, 1, 1)
    assert result.alerts[0].comparison_end == D(2024, 1, 2)


def test_all_company_ids_are_separate_even_with_duplicate_display_names():
    from src.latest_info_alerts import default_alert_filters
    rows = history('cashflow', 100, 150) + history('cashflow', 200, 100, company='p2')
    filters = default_alert_filters(D(2024, 1, 3), ('p1', 'p2'))
    result = build(rows, filters=filters)
    assert sorted((a.key, a.before, a.after) for a in result.alerts) == [
        (('p1', '总计'), Decimal(24), Decimal(36)),
        (('p2', '总计'), Decimal(48), Decimal(24))]
    assert {a.key[0] for a in build(rows).alerts} == {'p1'}


@pytest.mark.parametrize('metric,before,after,divider,thresholds,reason', [
    ('cashflow', 100, -100, 0, (1000, 1000, 100000), '现金流转负'),
    ('cashflow', -100, 0, 0, (1000, 1000, 100000), '现金流转正'),
    ('linecount', 10, 9, 0, (1000, 1000, 100000), '规模缩减'),
    ('monthly-ticket', 20, 25, 100, (5, 1000, 100000), '比例明显变化'),
    ('cashflow', 100, 120, 0, (1000, 20, 100000), '数值明显变化'),
    ('transport-by-type', 10, 15, 0, (1000, 50, 120), '数值明显变化'),
])
def test_existing_real_rules_and_threshold_boundaries(metric, before, after, divider, thresholds, reason):
    result = build(history(metric, before, after, divider=divider), thresholds=thresholds)
    assert [(a.metric, a.reason) for a in result.alerts] == [(metric, reason)]


@pytest.mark.parametrize('metric,before,after,divider,thresholds', [
    ('monthly-ticket', 20, 24, 100, (5, 1, 0)),
    ('cashflow', 100, 119, 0, (5, 20, 0)),
    ('transport-by-type', 10, 15, 0, (5, 20, 121)),
    ('monthly-ticket', 20, 30, 0, (5, 20, 0)),
])
def test_below_threshold_or_missing_denominator_does_not_alert(metric, before, after, divider, thresholds):
    assert build(history(metric, before, after, divider=divider), thresholds=thresholds).alerts == []


@pytest.mark.parametrize('case', ['unequal', 'incomplete', 'unconfirmed', 'transfer', 'no-comparison'])
def test_uncomparable_period_and_transfer_never_create_fake_alerts(case):
    rows = history('cashflow', 100, 200)
    filters = None
    if case == 'unequal':
        filters = FilterState(('p1',), D(2024, 1, 2), D(2024, 1, 3), 'hour',
                              (D(2024, 1, 1), D(2024, 1, 1, 23)))
    elif case == 'incomplete':
        rows = history('cashflow', 100, 200, missing=(2, 13))
    elif case == 'unconfirmed':
        rows = history('energy-prices', 100, 200, company='')
    elif case == 'transfer':
        # Sources stay below original gates; only the coefficient changes strongly.
        rows = history('transport-by-type', 1, 2) + history('trip-types', 1, 1)
    else:
        filters = FilterState(('p1',), D(2024, 1, 2), D(2024, 1, 3), 'hour')
    assert build(rows, filters=filters).alerts == []


def test_absent_history_has_no_alerts_and_cancellation_propagates():
    assert build([]).alerts == []
    with pytest.raises(QueryCancelled):
        build([], cancelled=lambda: True)


def test_city_alert_is_once_and_does_not_depend_on_company_selection():
    result = build(history('public-transport', 20, 25, company='', divider=100))
    assert [(a.metric, a.key, a.before, a.after) for a in result.alerts] == [
        ('public-transport', ('', '总计'), Decimal(20), Decimal(25))]


def test_empty_company_selection_keeps_city_scope_without_selecting_all_companies():
    from src.latest_info_alerts import default_alert_filters
    rows = history('cashflow', 100, 150) + history('public-transport', 20, 25, company='', divider=100)
    filters = default_alert_filters(D(2024, 1, 3), ())
    assert [(a.metric, a.key) for a in build(rows, filters=filters).alerts] == [
        ('public-transport', ('', '总计'))]


@pytest.fixture(scope='session')
def gui_application():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['CIM2_REDUCED_MOTION'] = '1'
    from PySide6.QtWidgets import QApplication
    application = QApplication.instance() or QApplication([])
    assert application.platformName() == 'offscreen'
    from stats_style import initialize_theme
    initialize_theme(application)
    yield application


@pytest.fixture
def gui_panel(tmp_path, gui_application):
    from PySide6.QtCore import QEvent, QSettings
    from frontend.latest_info_alerts import LatestInfoAlertsPanel
    application = gui_application
    settings = QSettings(str(tmp_path / 'alerts.ini'), QSettings.Format.IniFormat)
    panel = LatestInfoAlertsPanel(settings)
    yield panel, settings, application
    for window in application.topLevelWidgets():
        if window is panel or panel.isAncestorOf(window):
            window.close()
            window.deleteLater()
    application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()


def gui_snapshot(count=1, after=20):
    filters = FilterState(('p1',), D(2024, 1, 2), D(2024, 1, 3), 'hour',
                          (D(2024, 1, 1), D(2024, 1, 2)))
    alerts = [Alert('cashflow', ('p1', f'group-{i}'), '数值明显变化', Decimal(10),
                    Decimal(after + i), filters.start, filters.comparison[0],
                    filters.end, filters.comparison[1]) for i in range(count)]
    return DashboardResult(filters, {}, {}, alerts)


def test_same_thresholds_and_read_identity_survive_migration_gui(gui_panel):
    import json
    from stats_alerts import _alert_id
    from frontend.latest_info_alerts import LatestInfoAlertsPanel
    panel, settings, application = gui_panel
    snapshot = gui_snapshot()
    settings.setValue('statistics/percentage_points', 7)
    settings.setValue('statistics/relative_percent', 30)
    settings.setValue('statistics/passenger_absolute', 250)
    original_id = _alert_id('save-a', snapshot.alerts[0])
    settings.setValue('stats_alerts/read_ids', json.dumps([original_id]))
    migrated = LatestInfoAlertsPanel(settings, panel)
    migrated.set_snapshot(snapshot, 'save-a', {'p1': '重命名公司'})
    assert migrated.thresholds == (7, 30, 250)
    assert migrated.unread_count == 0
    migrated.set_snapshot(gui_snapshot(after=21), 'save-a', {'p1': '重命名公司'})
    assert migrated.unread_count == 1
    migrated.mark_all_read()
    assert original_id in json.loads(settings.value('stats_alerts/read_ids'))


def test_clear_or_new_session_removes_previous_alerts_gui(gui_panel):
    panel, settings, application = gui_panel
    panel.set_snapshot(gui_snapshot(), 'save-a', {'p1': '旧公司'})
    assert panel.unread_count == 1
    panel.clear_session()
    assert panel.alerts == [] and panel.unread_count == 0
    panel.set_snapshot(None, 'save-b', {})
    assert panel.alerts == [] and panel.session_key == 'save-b'
    panel.set_snapshot(gui_snapshot(), 'save-b', {'p1': '新公司'})
    assert panel.unread_count == 1


def test_panel_caps_summary_but_all_list_keeps_real_unread_total_gui(gui_panel):
    from PySide6.QtWidgets import QPushButton, QWidget
    panel, settings, application = gui_panel
    panel.set_snapshot(gui_snapshot(7), 'save-a', {'p1': '公司'})
    assert len(panel.alerts) == panel.unread_count == 7
    assert len(panel.findChildren(QWidget, 'latestAlertRow')) == 5
    assert not any(b.text() in ('详情', '标为已读', '全部标为已读', '提醒阈值')
                   for b in panel.findChildren(QPushButton) if not b.isHidden())
    assert panel.all_button.text() == '全部' and '7' in panel.all_button.toolTip()
    panel.mark_read(panel.alerts[0])
    assert panel.unread_count == 6
    panel.mark_all_read()
    assert panel.unread_count == 0


def test_threshold_and_enabled_changes_persist_and_emit_gui(gui_panel):
    panel, settings, application = gui_panel
    changed, enabled = [], []
    panel.thresholds_changed.connect(changed.append)
    panel.enabled_changed.connect(enabled.append)
    panel.set_thresholds((8, 40, 300))
    assert panel.thresholds == (8, 40, 300) and changed == [(8, 40, 300)]
    assert float(settings.value('statistics/relative_percent')) == 40
    panel.set_alerts_enabled(False)
    assert panel.alerts_enabled is False and enabled == [False]
    panel.set_snapshot(gui_snapshot(), 'save-a', {'p1': '公司'})
    assert len(panel.alerts) == 1  # Disabling does not alter rule results or IDs.


def test_empty_state_distinguishes_missing_history_and_no_threshold_alert_gui(gui_panel):
    from PySide6.QtWidgets import QLabel
    panel, settings, application = gui_panel
    panel.set_snapshot(None, 'save-a', {})
    assert any('无可比数据' in label.text() for label in panel.findChildren(QLabel))
    panel.set_snapshot(build(history('cashflow', 100, 101)), 'save-a', {'p1': '公司'})
    assert any('无达标提醒' in label.text() for label in panel.findChildren(QLabel))


def inspect_modal(application, action, inspect):
    """Inspect a real modal without blocking the queued test's event loop."""
    from PySide6.QtCore import QTimer
    errors = []
    def check():
        dialog = application.activeModalWidget()
        try:
            assert dialog is not None
            inspect(dialog)
        except Exception as error:
            errors.append(error)
        finally:
            if dialog is not None:
                dialog.accept()
    QTimer.singleShot(0, check)
    action()
    if errors:
        raise errors[0]


def test_all_dialog_retains_hidden_alerts_and_marks_them_read_gui(gui_panel):
    from PySide6.QtWidgets import QPushButton
    panel, settings, application = gui_panel
    panel.set_snapshot(gui_snapshot(7), 'save-a', {'p1': '公司'})
    all_button = panel.all_button
    def inspect(dialog):
        buttons = dialog.findChildren(QPushButton)
        assert len([b for b in buttons if b.text() == '详情']) == 7
        next(b for b in buttons if b.text() == '全部标为已读').click()
        assert panel.unread_count == 0
    inspect_modal(application, all_button.click, inspect)


@pytest.mark.parametrize('key', ['Key_Return', 'Key_Enter', 'Key_Space'])
def test_details_preserve_company_id_raw_values_windows_and_original_reason_gui(gui_panel, key):
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QLabel, QPushButton
    panel, settings, application = gui_panel
    panel.set_snapshot(gui_snapshot(), 'save-a', {'p1': '同名公司', 'p2': '同名公司'})
    row = panel._rows.itemAt(0).widget()
    def inspect(dialog):
        text = '\n'.join(label.text() for label in dialog.findChildren(QLabel))
        for value in ('同名公司', 'p1', '现金流', '10', '20', '2024-01-01',
                      '2024-01-02', '2024-01-03', '数值明显变化'):
            assert value in text
        next(b for b in dialog.findChildren(QPushButton) if b.text() == '标为已读').click()
        assert panel.unread_count == 0
    inspect_modal(application, lambda: QCoreApplication.sendEvent(
        row, QKeyEvent(QEvent.Type.KeyPress, getattr(Qt.Key, key), Qt.KeyboardModifier.NoModifier)), inspect)


def test_threshold_dialog_cancel_and_apply_emit_only_real_changes_gui(gui_panel):
    from PySide6.QtWidgets import QPushButton
    from qfluentwidgets import DoubleSpinBox
    panel, settings, application = gui_panel
    changed = []
    panel.thresholds_changed.connect(changed.append)
    def cancel(dialog):
        dialog.findChildren(DoubleSpinBox)[0].setValue(9)
        next(b for b in dialog.findChildren(QPushButton) if b.text() == '取消').click()
    # This helper closes with accept after inspection, so cancellation needs its
    # own timer to preserve the dialog result the product observes.
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, lambda: cancel(application.activeModalWidget()))
    panel.threshold_action.trigger()
    assert panel.thresholds == (5, 20, 100) and changed == []
    def apply(dialog):
        for spin, value in zip(dialog.findChildren(DoubleSpinBox), (9, 35, 220)):
            spin.setValue(value)
        next(b for b in dialog.findChildren(QPushButton) if b.text() == '应用').click()
    inspect_modal(application, panel.threshold_action.trigger, apply)
    assert panel.thresholds == (9, 35, 220) and changed == [(9, 35, 220)]


def test_enabled_restart_and_damaged_read_settings_are_isolated_gui(gui_panel):
    from frontend.latest_info_alerts import LatestInfoAlertsPanel
    panel, settings, application = gui_panel
    panel.set_alerts_enabled(False)
    settings.setValue('stats_alerts/read_ids', '{bad json')
    reopened = LatestInfoAlertsPanel(settings, panel)
    assert reopened.alerts_enabled is False
    reopened.set_alerts_enabled(True)
    reopened.set_snapshot(gui_snapshot(), 'save-a', {'p1': '公司'})
    assert reopened.unread_count == 1


@pytest.mark.parametrize('folder,tag,count', [
    ('D:/test/CIM2_SaveStats/jobs/56dd6b5276cd4c5ba083815f8a30b515', '秋山市n6 (2)_运行时', 4),
    ('D:/test/CIM2_SaveStats/exports', '望春市_test_运行时', 9),
    ('D:/test/CIM2_SaveStats/exports', 'quicksave.76561198362520556-76561198845688243_运行时', 19),
])
def test_real_cached_alerts_mount_into_actual_page_without_extra_scroll_gui(gui_panel, folder, tag, count):
    from pathlib import Path
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QLabel, QPushButton, QWidget
    from src.latest_info_alerts import build_latest_alerts, default_alert_filters
    from latest_info_model import build_latest_info
    from latest_info_page import LatestInfoPage
    from report_model import load_session
    path = Path(folder)
    if not (path / f'CIM2_公司信息_{tag}.csv').exists():
        pytest.skip('Optional authorized real cache is absent')
    panel, settings, application = gui_panel
    data = load_session(path, tag)
    data['save_key'] = f'real-cache:{tag}'
    snapshot = build_latest_info(data)
    store = HistoryStore(data['history'], data['simulation_time'])
    filters = default_alert_filters(store.simulation_time, tuple(key for key, name in snapshot.companies))
    alerts = build_latest_alerts(store, filters)
    assert len(alerts.alerts) == count
    page = LatestInfoPage(settings)
    try:
        page.set_alert_panel(panel)
        page.set_session(data)
        page.set_snapshot(snapshot)
        panel.set_snapshot(alerts, data['save_key'], dict(snapshot.companies))
        page.resize(1200, 852)
        page.show()
        application.processEvents()
        application.processEvents()
        assert panel.width() == 260
        assert panel.height() <= 494
        assert page.scroll.verticalScrollBar().maximum() == 0
        assert panel.unread_count == count
        assert len(panel.findChildren(QWidget, 'latestAlertRow')) == min(count, 5)
        for button in panel.findChildren(QPushButton):
            assert panel.rect().contains(QRect(button.mapTo(panel, QPoint()), button.size()))
        for row in panel.findChildren(QWidget, 'latestAlertRow'):
            assert panel.rect().contains(QRect(row.mapTo(panel, QPoint()), row.size()))
            for text in row.findChildren(QLabel):
                assert text.height() >= text.fontMetrics().height()
            numeric = row.findChild(QLabel, 'alertSummaryValue')
            assert numeric.fontMetrics().horizontalAdvance(numeric.text()) <= numeric.contentsRect().width()
        def inspect(dialog):
            assert len([b for b in dialog.findChildren(QPushButton) if b.text() == '详情']) == count
        inspect_modal(application, panel.all_button.click, inspect)
        print(f'CACHE {tag}: alerts={count}, summary={min(count,5)}, unread={panel.unread_count}, '
              f'panel={panel.width()}x{panel.height()}, board={page.board.width()}x{page.board.height()}, '
              f'scroll={page.scroll.verticalScrollBar().maximum()}')
    finally:
        page.close()
        page.deleteLater()
        application.processEvents()


def test_summary_rows_keep_input_order_neutral_marker_and_grouped_values_gui(gui_panel):
    from PySide6.QtWidgets import QLabel, QWidget
    panel, settings, application = gui_panel
    snapshot = gui_snapshot(7, after=1234567)
    snapshot.alerts.reverse()
    panel.set_snapshot(snapshot, 'save-a', {'p1': '公司'})
    panel.resize(260, 494)
    panel.show()
    application.processEvents()
    rows = panel.findChildren(QWidget, 'latestAlertRow')
    assert len(rows) == 5
    for row, alert in zip(rows, snapshot.alerts[:5]):
        assert 76 <= row.height() <= 88
        assert row.toolTip() == ''
        assert alert.key[1] in row.accessibleName()
        assert f'{alert.after:,.0f}' in row.findChild(QLabel, 'alertSummaryValue').text()
        marker = row.findChild(QLabel, 'alertNeutralMarker')
        assert marker.toolTip() == '未读'
        assert '严重' not in row.accessibleName() and '危险' not in row.accessibleName()
    assert panel.alerts == snapshot.alerts
    assert '前一完整日' in panel.scope_label.text()


def test_summary_left_click_opens_details_and_more_keeps_management_actions_gui(gui_panel):
    from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QLabel
    panel, settings, application = gui_panel
    panel.set_snapshot(gui_snapshot(), 'save-a', {'p1': '公司'})
    row = panel._rows.itemAt(0).widget()
    def inspect(dialog):
        assert any('现金流' in text.text() for text in dialog.findChildren(QLabel))
    inspect_modal(application, lambda: QCoreApplication.sendEvent(row, QMouseEvent(
        QEvent.Type.MouseButtonRelease, QPointF(10, 10), QPointF(10, 10),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)), inspect)
    assert panel.more_button.accessibleName() == '更多提醒操作'
    assert {action.text() for action in panel.more_menu.actions()} >= {
        '开启提醒', '提醒阈值', '全部标为已读'}
    panel.read_all_action.trigger()
    assert panel.unread_count == 0
    panel.enable_action.trigger()
    assert panel.alerts_enabled is False
    assert panel.empty_label.text() == '提醒已关闭'


@pytest.mark.parametrize('kind', ['details', 'all', 'thresholds'])
def test_new_session_rejects_old_dialogs_and_stale_read_actions_gui(gui_panel, kind):
    import json
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog
    from qfluentwidgets import DoubleSpinBox
    from stats_alerts import _alert_id
    panel, settings, application = gui_panel
    old = gui_snapshot().alerts[0]
    panel.set_snapshot(gui_snapshot(), 'save-old', {'p1': '旧公司'})
    errors = []
    def replace():
        dialog = application.activeModalWidget()
        try:
            assert dialog is not None
            if kind == 'thresholds':
                dialog.findChildren(DoubleSpinBox)[0].setValue(999)
            panel.set_snapshot(gui_snapshot(after=123), 'save-new', {'p1': '新公司'})
            assert dialog.result() == QDialog.DialogCode.Rejected
            panel.mark_read(old)
            assert panel.unread_count == 1
            assert _alert_id('save-new', old) not in json.loads(settings.value('stats_alerts/read_ids', '[]'))
        except Exception as error:
            errors.append(error)
            if dialog is not None:
                dialog.reject()
    QTimer.singleShot(0, replace)
    if kind == 'details':
        panel._rows.itemAt(0).widget().activated.emit()
    elif kind == 'all':
        panel.all_button.click()
    else:
        panel.threshold_action.trigger()
    if errors:
        raise errors[0]
    assert panel.thresholds == (5, 20, 100)
    assert panel.session_key == 'save-new' and panel._dialogs == []


def test_more_menu_opens_locally_and_exposes_checked_state_gui(gui_panel):
    from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt, QTimer
    from PySide6.QtGui import QMouseEvent
    panel, settings, application = gui_panel
    panel.set_snapshot(gui_snapshot(), 'save-a', {'p1': '公司'})
    panel.resize(260, 494)
    panel.show()
    application.processEvents()
    observed, errors = [], []
    def inspect():
        try:
            observed.append(panel.more_menu.isVisible())
            assert panel.enable_action.isChecked()
            assert panel.read_all_action.isEnabled()
            panel.read_all_action.trigger()
            assert panel.unread_count == 0
        except Exception as error:
            errors.append(error)
        finally:
            panel.more_menu.close()
    QTimer.singleShot(0, inspect)
    # Fluent opens its dropdown from mouseReleaseEvent, whereas QPushButton.click
    # only emits clicked. Send a real local event without global cursor/input.
    QCoreApplication.sendEvent(panel.more_button, QMouseEvent(
        QEvent.Type.MouseButtonRelease, QPointF(10, 10), QPointF(10, 10),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    application.processEvents()
    if errors:
        raise errors[0]
    assert observed == [True]


@pytest.mark.parametrize('key', ['Key_Return', 'Key_Space'])
def test_more_keyboard_activation_opens_same_management_menu_gui(gui_panel, key):
    from PySide6.QtCore import QCoreApplication, QEvent, Qt, QTimer
    from PySide6.QtGui import QKeyEvent
    panel, settings, application = gui_panel
    panel.resize(260, 494)
    panel.show()
    application.processEvents()
    observed = []
    def inspect():
        observed.append(panel.more_menu.isVisible())
        panel.more_menu.close()
    QTimer.singleShot(0, inspect)
    for event in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QCoreApplication.sendEvent(panel.more_button, QKeyEvent(
            event, getattr(Qt.Key, key), Qt.KeyboardModifier.NoModifier))
    application.processEvents()
    assert observed == [True]
