"""Workload counters match history ring semantics without serializing a graph."""
import ast
import datetime as dt
from pathlib import Path
from types import SimpleNamespace as NS


class Array(list):
    @property
    def Length(self):
        return len(self)


def counter():
    tree = ast.parse(Path(__file__).with_name('extract_runtime_data.py').read_text(encoding='utf-8'))
    node = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'workload_counts'), None)
    assert node is not None, 'workload counter is not implemented'
    namespace = dict(dt=dt, field=lambda obj, name: None if obj is None else obj.get(name),
                     array_values=lambda arr: [] if arr is None else list(arr))
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<workload_counts>', 'exec'), namespace)
    return namespace['workload_counts']


def clock(day, hour=0):
    return NS(Year=2013, Month=1, Day=day, Hour=hour, Minute=0, Second=0)


def test_counts_unfilled_history_total_and_categories_and_departures():
    group = {'m_historyValues': Array([0]*8)}
    history = {'m_name':'coverage', 'm_position':2,
               'm_tempGroups':Array([group, group]), 'm_baseGroup':group}
    root = {'m_simulationStart':clock(1), 'm_simulationTime':clock(1, 2),
            'm_dataManagerData':{'m_historyData':Array([history])}}
    lines = [{'m_timeTables':Array([{'m_rows':Array([1,2,3])}, {'m_rows':Array([4])}])}]
    assert counter()(root, lines) == dict(event='workload', line_count=1, history_rows=9, departure_count=4)


def test_counts_wrapped_ring_and_ignores_missing_arrays():
    group = {'m_historyValues':Array([0]*4)}
    root = {'m_simulationStart':clock(1), 'm_simulationTime':clock(2, 2),
            'm_dataManagerData':{'m_historyData':Array([
                {'m_name':'population', 'm_position':2,
                 'm_tempGroups':Array([group, {'m_historyValues':None}])}])}}
    assert counter()(root, []) == dict(event='workload', line_count=0, history_rows=4, departure_count=0)


def test_empty_graph_workload_is_zero():
    root = {'m_simulationStart':clock(1), 'm_simulationTime':clock(1)}
    assert counter()(root, []) == dict(event='workload', line_count=0, history_rows=0, departure_count=0)
