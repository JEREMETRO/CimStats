"""Coordinate one cancellable homepage snapshot/alert request and its exports."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QFileDialog
from qfluentwidgets import Action, RoundMenu
from shiboken6 import isValid

from frontend.latest_info_alerts import LatestInfoAlertsPanel
from src.latest_info_alerts import build_latest_alerts, default_alert_filters
from latest_info_exports import (build_share_summary, export_latest_info_png,
                                 export_latest_info_xlsx)
from latest_info_model import build_latest_info
from statistics_model import HistoryStore, QueryCancelled


@dataclass(frozen=True)
class _ChartIntent:
    data: object
    session_key: str
    state: dict
    target_scope: tuple[str, str]
    token: int


class LatestInfoTask(QThread):
    ready = Signal(int, object)
    failed = Signal(int, object)

    def __init__(self, token, data, scope, thresholds, enabled, parent=None):
        super().__init__(parent)
        self.token, self.data, self.scope = token, data, scope
        self.thresholds, self.enabled = thresholds, enabled

    def run(self):
        try:
            cancelled = self.isInterruptionRequested
            snapshot = build_latest_info(self.data, *self.scope, cancelled=cancelled)
            alerts = None
            if cancelled():
                raise QueryCancelled()
            if self.enabled and snapshot.simulation_time is not None:
                owners = (snapshot.company_id,) if snapshot.company_id else tuple(key for key, _ in snapshot.companies)
                filters = default_alert_filters(snapshot.simulation_time, owners)
                store = HistoryStore(self.data.get('history', []), snapshot.simulation_time)
                alerts = build_latest_alerts(store, filters, self.thresholds, cancelled=cancelled)
            if not cancelled():
                self.ready.emit(self.token, (snapshot, alerts))
        except QueryCancelled:
            pass
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(self.token, exc)


class LatestInfoController(QObject):
    snapshot_changed = Signal(object)
    query_failed = Signal(object)
    export_failed = Signal(object)
    thresholds_changed = Signal(object)

    def __init__(self, page, settings=None, parent=None):
        super().__init__(parent or page)
        self.page = page
        self.snapshot = self.alerts_snapshot = None
        self._snapshot_data = None
        self._pending_chart_intent = None
        self.data = None
        self.token = 0
        self.workers = []
        self._closing = False
        self.last_error = None
        self.alerts_panel = LatestInfoAlertsPanel(settings, page)
        self.thresholds = self.alerts_panel.thresholds
        self.enabled = self.alerts_panel.alerts_enabled
        page.set_alert_panel(self.alerts_panel)
        self.query_timer = QTimer(self)
        self.query_timer.setSingleShot(True)
        self.query_timer.timeout.connect(self._submit_query)
        page.scope_changed.connect(self.schedule_query)
        page.share_requested.connect(self.show_share_menu)
        page.report_requested.connect(self.show_report_menu)
        self.alerts_panel.thresholds_changed.connect(self._thresholds_changed)
        self.alerts_panel.enabled_changed.connect(self._enabled_changed)
        page.installEventFilter(self)

    def _remember_chart_intent(self):
        session_key = str((self.data or {}).get('save_key') or (self.data or {}).get('session_key') or '')
        intent = self._pending_chart_intent
        if intent is not None and (intent.data is not self.data or intent.session_key != session_key):
            intent = None
        if self.snapshot is not None:
            intent = None
            if self._snapshot_data is self.data and self.snapshot.session_key == session_key:
                state = self.page.capture_chart_state()
                if (state['session_key'] == session_key
                        and tuple(state['scope']) == (self.snapshot.company_id, self.snapshot.mode)):
                    intent = _ChartIntent(self.data, session_key, state, self.page.scope(), self.token)
        return intent

    def _invalidate(self, *, preserve_chart_state=False):
        intent = self._remember_chart_intent() if preserve_chart_state else None
        self.token += 1
        self.query_timer.stop()
        for worker in self.workers:
            worker.requestInterruption()
        self.snapshot = self.alerts_snapshot = None
        self._snapshot_data = None
        self._pending_chart_intent = None
        scope = self.page.scope()
        self.page.clear_session()
        if self.data is not None and not self._closing:
            self.page.set_session(self.data)
            for combo, selected in zip((self.page.company_combo, self.page.mode_combo), scope):
                combo.blockSignals(True)
                combo.setCurrentIndex(max(0, combo.findData(selected)))
                combo.blockSignals(False)
            self._apply_workbook_availability()
            if intent is not None:
                self._pending_chart_intent = replace(intent, target_scope=self.page.scope(), token=self.token)
        self.alerts_panel.clear_session()
        self.snapshot_changed.emit(None)

    def workbook_source(self, kind):
        source = ((self.data or {}).get('outputs') or {}).get(kind)
        return Path(source) if source and Path(source).is_file() else None

    def _apply_workbook_availability(self):
        self.page.set_workbook_availability(self.workbook_source('line_workbook') is not None,
                                            self.workbook_source('company_workbook') is not None)

    def set_session(self, data):
        self.clear_session()
        if self._closing:
            return
        self.data = data
        self.page.set_session(data)
        self.schedule_query()

    def clear_session(self):
        self.data = None
        self._invalidate()

    def schedule_query(self, *_):
        if self._closing or self.data is None:
            return
        self._invalidate(preserve_chart_state=True)
        self.query_timer.start(40)

    def _thresholds_changed(self, thresholds):
        self.thresholds = tuple(thresholds)
        self.thresholds_changed.emit(self.thresholds)
        self.schedule_query()

    def _enabled_changed(self, enabled):
        self.enabled = bool(enabled)
        self.schedule_query()

    def _submit_query(self):
        if self._closing or self.data is None:
            return
        worker = LatestInfoTask(self.token, self.data, self.page.scope(), self.thresholds, self.enabled, self)
        worker.ready.connect(self._receive)
        worker.failed.connect(self._failed)
        worker.finished.connect(lambda w=worker: self._worker_finished(w))
        self.workers.append(worker)
        worker.start()

    @Slot(int, object)
    def _receive(self, token, result):
        if token != self.token or self.data is None or self._closing or not isValid(self.page):
            return
        snapshot, alerts = result
        session_key = str(self.data.get('save_key') or self.data.get('session_key') or '')
        if snapshot.session_key != session_key or (snapshot.company_id, snapshot.mode) != self.page.scope():
            return
        self.snapshot, self.alerts_snapshot = snapshot, alerts
        self._snapshot_data = self.data
        self.page.set_snapshot(snapshot)
        intent = self._pending_chart_intent
        self._pending_chart_intent = None
        if (intent is not None and intent.data is self.data and intent.session_key == snapshot.session_key
                and intent.token == token and intent.target_scope == (snapshot.company_id, snapshot.mode)):
            self.page.restore_chart_state(intent.state,
                allow_scope_change=tuple(intent.state['scope']) != intent.target_scope)
        self._apply_workbook_availability()
        self.alerts_panel.set_snapshot(alerts, snapshot.session_key, dict(snapshot.companies))
        self.last_error = None
        self.snapshot_changed.emit(snapshot)

    @Slot(int, object)
    def _failed(self, token, error):
        if token != self.token or self.data is None or self._closing:
            return
        self._invalidate()
        self.last_error = error
        self.query_failed.emit(error)

    def _worker_finished(self, worker):
        if worker in self.workers:
            self.workers.remove(worker)
        worker.deleteLater()

    def stop_workers(self):
        self._closing = True
        self.clear_session()
        for worker in list(self.workers):
            worker.requestInterruption()
        return all(worker.wait(3000) for worker in list(self.workers))

    def eventFilter(self, watched, event):
        if watched is self.page and event.type() == QEvent.Type.Close:
            self.stop_workers()
        return super().eventFilter(watched, event)

    def copy_summary(self):
        if self.snapshot is not None and not self._closing:
            QApplication.clipboard().setText(build_share_summary(self.snapshot))

    def _menu(self, title, entries):
        snapshot, token = self.snapshot, self.token
        if snapshot is None or self._closing:
            return
        menu = RoundMenu(title, self.page)
        for text, handler in entries:
            action = Action(text, menu)
            def run(_checked=False, callback=handler):
                if self.snapshot is snapshot and self.token == token and not self._closing:
                    callback()
            action.triggered.connect(run)
            menu.addAction(action)
        menu.exec(self.page.mapToGlobal(QPoint(self.page.width() // 2, 56)))

    def show_share_menu(self):
        self._menu('分享', [('复制当前摘要', self.copy_summary), ('导出页面 PNG', lambda: self._export('png'))])

    def show_report_menu(self):
        self._menu('导出报告', [('首页报告 XLSX', lambda: self._export('xlsx')),
                              ('导出页面 PNG', lambda: self._export('png'))])

    def _export(self, kind):
        snapshot, alerts, token, data = self.snapshot, self.alerts_snapshot, self.token, self.data
        if snapshot is None or data is None or self._closing:
            return
        session_key = snapshot.session_key
        suffix = '.' + kind
        try:
            path, _ = QFileDialog.getSaveFileName(self.page, '导出最新信息', '最新信息' + suffix,
                                                 f'{kind.upper()} (*{suffix})')
            if (not path or self._closing or self.snapshot is not snapshot or self.alerts_snapshot is not alerts
                    or self.token != token or self.data is not data
                    or str(self.data.get('save_key') or self.data.get('session_key') or '') != session_key):
                return
            if Path(path).suffix.lower() != suffix:
                path += suffix
            if kind == 'png':
                export_latest_info_png(self.page.export_target(), path)
            elif kind == 'xlsx':
                export_latest_info_xlsx(snapshot, alerts, path)
            else:
                raise ValueError('不支持的报告格式')
            self.last_error = None
        except Exception as exc:
            self.last_error = exc
            self.export_failed.emit(exc)
