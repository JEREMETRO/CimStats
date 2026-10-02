from parse_events import ProgressReporter


def test_throttling_preserves_actual_first_and_final_counts():
    events, now = [], [0.0]
    reporter = ProgressReporter(events.append, lambda: now[0])
    reporter.start('lines')
    reporter.progress('lines', 1, 10)
    reporter.progress('lines', 2, 10)
    now[0] = .11
    reporter.progress('lines', 3, 10)
    reporter.progress('lines', 10, 10)
    assert [e['done'] for e in events if e['event'] == 'progress'] == [1, 3, 10]


def test_known_empty_phase_reports_completion_without_division():
    events = []
    ProgressReporter(events.append).progress('lines', 0, 0)
    assert events == [dict(event='phase', phase='lines', status='end')]


def test_invalid_counter_cannot_be_emitted():
    import pytest
    events = []
    with pytest.raises(ValueError):
        ProgressReporter(events.append).progress('history', 2, 1)
    assert events == []


def test_nonzero_completed_count_cannot_claim_empty_phase():
    import pytest
    with pytest.raises(ValueError):
        ProgressReporter(lambda _: None).progress('lines', 1, 0)
