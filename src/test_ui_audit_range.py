import sys
from pathlib import Path
from datetime import datetime
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from stats_range_picker import RangePicker

@pytest.mark.parametrize('start,end,expected', [
    (datetime(2013,5,13), datetime(2013,5,19), (datetime(2013,5,13), datetime(2013,5,20))),
    (datetime(2013,5,13,7,31,19), datetime(2013,5,19,20,42,37),
     (datetime(2013,5,13,7,31,19), datetime(2013,5,19,20,42,37))),
])
def test_representation_round_trip_preserves_interval(qt_application, start, end, expected):
    picker = RangePicker(start,end)
    try:
        for timed in (True, False, True, False):
            picker.time_toggle.setChecked(timed)
            assert picker.selected_range() == expected
    finally:
        picker.close()

def test_editing_calendar_replaces_precise_interval_with_inclusive_days(qt_application):
    from PySide6.QtCore import QDate
    picker=RangePicker(datetime(2013,5,13,7,31),datetime(2013,5,19,20,42))
    picker.time_toggle.setChecked(False)
    picker.calendars[1].setDate(QDate(2013,5,21))
    assert picker.selected_range() == (datetime(2013,5,13),datetime(2013,5,22))
    picker.time_toggle.setChecked(True)
    assert picker.end_edit.dateTime().toPython() == datetime(2013,5,22)
    picker.close()
