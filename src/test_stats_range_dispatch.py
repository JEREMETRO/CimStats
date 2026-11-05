"""Custom date dialogs open after the dropdown's item event has unwound."""
from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow


@pytest.mark.parametrize('selector', ['range_combo', 'compare_combo'])
@pytest.mark.parametrize('accepted', [False, True])
def test_custom_date_dialog_does_not_enter_modal_loop_from_selection(qt_application, monkeypatch, selector, accepted):
    import statistics_page
    from stats_range_picker import RangePicker

    calls = []

    class ObservedPicker(RangePicker):
        def exec(self):
            calls.append(self.parentWidget())
            QTimer.singleShot(0, self, self.accept if accepted else self.reject)
            return super().exec()

    monkeypatch.setattr(statistics_page, 'RangePicker', ObservedPicker)
    page = statistics_page.StatisticsPage()
    window = QMainWindow()
    window.setCentralWidget(page)
    try:
        page.simulation_time = datetime(2013, 6, 1, 23, 59)
        end = datetime(2013, 5, 27)
        start = end - timedelta(days=7)
        page._range_window = (start, end)
        if selector == 'compare_combo':
            page.analysis_mode_control.setCurrentKey('period')
        window.show()
        qt_application.processEvents()
        combo = getattr(page, selector)
        assert combo.isVisible()
        previous = combo.currentData()
        index = combo.findData('custom')
        assert index >= 0 and previous != 'custom'
        combo.setCurrentIndex(index)
        assert not calls, 'A dropdown signal must finish before opening a modal dialog'
        qt_application.processEvents()
        assert calls == [window], 'The dialog must be owned by the existing top-level window'
        assert combo.currentData() == ('custom' if accepted else previous)
        if accepted and selector == 'range_combo':
            assert page._custom_window == (start, end)
        if accepted and selector == 'compare_combo':
            assert page._custom_comparison == (start - timedelta(days=7), start)
    finally:
        page.close()
        window.close()


def test_hiding_statistics_page_discards_unapplied_custom_selection(qt_application):
    from statistics_page import StatisticsPage

    page = StatisticsPage()
    try:
        page.simulation_time = datetime(2013, 6, 1, 23, 59)
        page.show()
        qt_application.processEvents()
        previous = page.range_combo.currentData()
        page.range_combo.setCurrentIndex(page.range_combo.findData('custom'))
        page.hide()
        qt_application.processEvents()
        page.show()
        assert page.range_combo.currentData() == previous == page.range_preset
    finally:
        page.close()
