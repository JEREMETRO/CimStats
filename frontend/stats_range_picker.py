"""Calendar-based editor for an inclusive day or exact-time statistics range."""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from window_chrome import FluentDialog
from qfluentwidgets import CalendarPicker, CheckBox, DateTimeEdit, PrimaryPushButton, PushButton
from stats_motion import attach_surface_reveal

from stats_tokens import (BORDER, CARD_BG, CONTROL_GAP, ERROR_COLOR,
                          FONT_FAMILY, TEXT_PRIMARY, TEXT_SECONDARY)


class RangePicker(FluentDialog):
    """Return a half-open interval; in date-only mode the last day is included."""

    def __init__(self, start: datetime, end: datetime, *, title: str = '自定义时间', parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName('statsRangePicker')
        self.setMinimumWidth(520)
        attach_surface_reveal(self)
        self.setStyleSheet(
            f'QDialog#statsRangePicker {{ background: {CARD_BG}; color: {TEXT_PRIMARY}; '
            f'font-family: "{FONT_FAMILY}"; }} '
            f'QLabel#rangeError {{ color: {ERROR_COLOR}; }} '
            f'QLabel#rangeHelp {{ color: {TEXT_SECONDARY}; }} '
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)
        self.time_toggle = CheckBox('指定时分', self)
        self.time_toggle.setAccessibleName('指定时分')
        root.addWidget(self.time_toggle)
        self.start_edit = self._edit(start)
        self.end_edit = self._edit(end)
        self.calendars = []
        range_row = QHBoxLayout()
        range_row.setSpacing(12)
        for title_text, edit in (('开始日期', self.start_edit), ('结束日期', self.end_edit)):
            column = QWidget(self)
            column_layout = QVBoxLayout(column)
            column_layout.setContentsMargins(0, 0, 0, 0)
            column_layout.setSpacing(4)
            column_layout.addWidget(QLabel(title_text, column))
            calendar = CalendarPicker(column)
            calendar.setDate(edit.date())
            calendar.setMinimumHeight(36)
            calendar.setDateFormat('yyyy-MM-dd')
            calendar.setAccessibleName(title_text)
            calendar.dateChanged.connect(edit.setDate)
            edit.dateTimeChanged.connect(lambda value, picker=calendar: self._sync_calendar(picker, value.date()))
            column_layout.addWidget(calendar)
            self.calendars.append(calendar)
            column_layout.addWidget(edit)
            range_row.addWidget(column, 1)
        root.addLayout(range_row)
        self.help_label = QLabel('结束日期包含所选当天', self)
        self.help_label.setObjectName('rangeHelp')
        root.addWidget(self.help_label)
        self.error_label = QLabel('', self)
        self.error_label.setObjectName('rangeError')
        root.addWidget(self.error_label)
        actions = QHBoxLayout()
        actions.setSpacing(CONTROL_GAP)
        actions.addStretch()
        self.cancel_button = PushButton('取消', self)
        self.apply_button = PrimaryPushButton('应用', self)
        self.cancel_button.clicked.connect(self.reject)
        self.apply_button.clicked.connect(self._apply)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.apply_button)
        root.addLayout(actions)
        self.time_toggle.toggled.connect(self._time_mode_changed)
        self.start_edit.dateTimeChanged.connect(self._validate)
        self.end_edit.dateTimeChanged.connect(self._validate)
        timed = any(value.hour or value.minute or value.second for value in (start, end))
        self.time_toggle.setChecked(timed)
        self._time_mode_changed(timed)

    def _edit(self, value: datetime) -> DateTimeEdit:
        edit = DateTimeEdit(self)
        edit.setCalendarPopup(False)
        edit.setDisplayFormat('yyyy-MM-dd')
        edit.setMinimumWidth(215)
        edit.setDateTime(value)
        edit.setAccessibleName('开始日期' if not hasattr(self, 'start_edit') else '结束日期')
        edit.setMinimumHeight(36)
        return edit

    def _time_mode_changed(self, enabled: bool) -> None:
        fmt = 'yyyy-MM-dd HH:mm' if enabled else 'yyyy-MM-dd'
        for edit in (self.start_edit, self.end_edit):
            edit.setDisplayFormat(fmt)
            edit.setVisible(enabled)
        for calendar in self.calendars:
            calendar.setVisible(not enabled)
        self.help_label.setText('结束时刻为排他边界' if enabled else '结束日期包含所选当天')
        self._validate()

    def _sync_calendar(self, picker, date):
        if picker.date != date:
            picker.blockSignals(True)
            picker.setDate(date)
            picker.blockSignals(False)

    def selected_range(self) -> tuple[datetime, datetime] | None:
        start = self.start_edit.dateTime().toPython()
        end = self.end_edit.dateTime().toPython()
        if not self.time_toggle.isChecked():
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = end.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return (start, end) if start < end else None

    def _validate(self, *_):
        valid = self.selected_range() is not None
        self.apply_button.setEnabled(valid)
        self.error_label.setText('结束时间必须晚于开始时间' if not valid else '')
        self.error_label.setVisible(not valid)
        border = ERROR_COLOR if not valid else BORDER
        for edit in (self.start_edit, self.end_edit):
            edit.setStyleSheet(f'border-color: {border};')

    def _apply(self):
        if self.selected_range() is not None:
            self.accept()
