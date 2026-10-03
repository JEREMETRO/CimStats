"""Malformed input must not discard valid observations during indexing."""
from datetime import datetime

import pytest

from statistics_model import HistoryStore


@pytest.mark.parametrize('invalid_time', [[], {}])
def test_history_ignores_malformed_time_and_keeps_valid_rows(invalid_time):
    rows = [
        {'模拟时间': invalid_time, '指标': 'population', '值': '9'},
        {'模拟时间': '2024-01-01 00:00:00', '指标': 'population', '值': '42'},
    ]
    store = HistoryStore(rows, datetime(2024, 1, 2))
    observations = [row for series in store.series.values() for row in series]
    assert len(observations) == 1
    assert observations[0].time == datetime(2024, 1, 1)
    assert observations[0].value == 42
