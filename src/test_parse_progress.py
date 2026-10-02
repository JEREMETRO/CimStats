"""Displayed progress comes only from actual phase/counter events."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'frontend'))
from parse_progress import ParseProgressEstimator


def event(phase, done, total):
    return dict(event='progress', phase=phase, done=done, total=total)


def test_elapsed_and_rss_never_advance_progress():
    p = ParseProgressEstimator(1, {})
    assert p.update(0, 0, 10) == 0
    assert p.update(10**10, 10**15, 10) == 0
    p.observe(1, event('lines', 10, 20))
    assert p.update(2, 0, 10) == 35
    assert p.update(10**10, 10**15, 10) == 35


def test_actual_counts_and_phases_are_monotonic_below_100():
    p = ParseProgressEstimator()
    values = []
    for phase, done, total in [('payload',1,1),('deserialize',1,1),('lines',1,2),('lines',2,2),('history',100,200),('history',200,200),('csv',15,15),('line_workbook',1,1),('company_workbook',1,1),('validation',2,2),('dashboard',4,4)]:
        p.observe(0, event(phase,done,total)); values.append(p.update(0,0,10))
    assert values == [8,20,35,50,57,65,70,82,90,96,99]
    assert max(values) < 100
    assert p.finish() == 100


def test_stale_or_regressing_events_cannot_move_phase_or_counter_back():
    p = ParseProgressEstimator()
    p.observe(0,event('history',5,10))
    p.observe(0,event('lines',1,1))
    p.observe(0,event('history',1,10))
    assert p.phase == 'history' and p.done == 5
    assert p.update(0,0,10) == 57


def test_bad_events_and_unknown_workload_remain_numeric_and_do_not_advance():
    p = ParseProgressEstimator(10**15,{})
    for bad in [None, {}, event('bogus',1,1), event('history',float('nan'),1), event('history',2,1), event('history',0,0), event('history','1','2'), event('history',True,2), event('history',1.5,2), {'event':'workload','line_count':1000}]:
        p.observe(0,bad)
    assert p.update(10**20,10**15,10) == 0
    assert p.update(0,0,82) == 82
    assert p.update(0,0,99) == 96
    assert p.update(0,0,100) == 100


def test_frozen_runtime_and_other_sizes_use_the_same_actual_protocol(monkeypatch):
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    for size in (0,1,10**15):
        p = ParseProgressEstimator(size,{'enabled':False})
        p.observe(0,event('lines',3,10))
        assert p.update(0,0,10) == 29
