from datetime import datetime as D
from decimal import Decimal

import pytest

from statistics_model import HistoryStore, Query
from test_statistics_model import row


@pytest.mark.parametrize('simulation_time,preset,expected', [
    (D(2024, 3, 1, 13), 'previous_full_week', (D(2024, 2, 19), D(2024, 2, 26))),
    (D(2024, 3, 4), 'previous_full_week', (D(2024, 2, 26), D(2024, 3, 4))),
    (D(2024, 1, 1, 12), 'previous_full_week', (D(2023, 12, 25), D(2024, 1, 1))),
    (D(2024, 3, 1, 13), 'previous_full_day', (D(2024, 2, 29), D(2024, 3, 1))),
    (D(2024, 1, 1), 'previous_full_day', (D(2023, 12, 31), D(2024, 1, 1))),
])
def test_preset_window_uses_complete_simulation_periods(simulation_time, preset, expected):
    from stats_view_model import preset_window

    assert preset_window(simulation_time, preset) == expected
    assert preset_window(simulation_time.isoformat(), preset) == expected


def test_preset_window_rejects_unknown_choice():
    from stats_view_model import preset_window

    with pytest.raises(ValueError):
        preset_window(D(2024, 3, 1), 'custom')


@pytest.mark.parametrize('start,end,preset,expected', [
    (D(2024, 3, 1, 8), D(2024, 3, 3, 8), 'previous',
     (D(2024, 2, 28, 8), D(2024, 3, 1, 8))),
    (D(2024, 3, 1, 8), D(2024, 3, 3, 8), 'previous_week',
     (D(2024, 2, 23, 8), D(2024, 2, 25, 8))),
    (D(2024, 3, 31, 8), D(2024, 4, 2, 8), 'previous_month',
     (D(2024, 2, 29, 8), D(2024, 3, 2, 8))),
])
def test_resolve_comparison_uses_existing_calendar_rules(start, end, preset, expected):
    from stats_view_model import resolve_comparison

    assert resolve_comparison(start, end, preset) == expected


def test_resolve_comparison_allows_unequal_custom_interval_without_clipping():
    from stats_view_model import resolve_comparison

    custom = (D(2023, 12, 28, 12), D(2024, 1, 1))
    assert resolve_comparison(D(2024, 3, 1), D(2024, 3, 2), 'custom', custom) == custom


@pytest.mark.parametrize('start,end,preset,custom', [
    (D(2024, 3, 1), D(2024, 3, 1), 'previous', None),
    (D(2024, 3, 2), D(2024, 3, 1), 'previous_week', None),
    (D(2024, 3, 30), D(2024, 3, 31), 'previous_month', None),
    (D(2024, 3, 1), D(2024, 3, 2), 'custom', None),
    (D(2024, 3, 1), D(2024, 3, 2), 'custom', (D(2024, 1, 1), D(2024, 1, 1))),
    (D(2024, 3, 1), D(2024, 3, 2), 'custom', (D(2024, 1, 2), D(2024, 1, 1))),
])
def test_resolve_comparison_rejects_invalid_ranges(start, end, preset, custom):
    from stats_view_model import resolve_comparison

    with pytest.raises(ValueError):
        resolve_comparison(start, end, preset, custom)


def test_resolve_comparison_rejects_unknown_choice():
    from stats_view_model import resolve_comparison

    with pytest.raises(ValueError):
        resolve_comparison(D(2024, 3, 1), D(2024, 3, 2), 'unknown')


def two_company_result():
    rows = []
    for company, day, hour, value in [
        ('id-a', 1, 0, 50), ('id-b', 1, 0, 400),
        ('id-a', 2, 0, -100), ('id-b', 2, 0, 100), ('id-b', 2, 1, 200),
    ]:
        record = row('cashflow', 'bus', D(2024, 1, day, hour), value, company=company)
        record['公司名称'] = '同名公司'
        rows.append(record)
    return HistoryStore(rows, D(2024, 1, 3)).query(Query(
        'cashflow', (), None, D(2024, 1, 2), D(2024, 1, 2, 2), 'hour',
        (D(2024, 1, 1), D(2024, 1, 1, 2))))


def test_company_result_filters_by_id_without_changing_source_or_bucket_metadata():
    from stats_view_model import company_result

    original = two_company_result()
    selected = company_result(original, ('id-a',))

    assert selected is not original and selected.query is not original.query
    assert selected.query.companies == ('id-a',)
    assert set(selected.series) == set(selected.comparison) == {('id-a', 'bus')}
    assert set(original.series) == set(original.comparison) == {('id-a', 'bus'), ('id-b', 'bus')}
    assert original.query.companies == ()
    assert selected.current_window == original.current_window
    assert selected.comparison_window == original.comparison_window
    assert selected.metric is original.metric
    assert selected.metric.unit == '货币'
    buckets = selected.series[('id-a', 'bus')]
    assert [(b.value, b.complete, b.effective_hours) for b in buckets] == [
        (Decimal('-1'), True, 1), (None, False, 0)]
    assert selected.comparison[('id-a', 'bus')][0].value == Decimal('0.5')


def test_company_result_empty_selection_means_no_company():
    from stats_view_model import company_result

    original = two_company_result()
    selected = company_result(original, ())
    assert selected.query.companies == ()
    assert selected.series == selected.comparison == {}
    assert len(original.series) == len(original.comparison) == 2


def test_company_result_can_clear_comparison_and_its_metadata():
    from stats_view_model import company_result

    original = two_company_result()
    selected = company_result(original, ('id-b',), include_comparison=False)
    assert set(selected.series) == {('id-b', 'bus')}
    assert selected.comparison == {}
    assert selected.query.comparison is None
    assert selected.comparison_window is None
    assert original.query.comparison == (D(2024, 1, 1), D(2024, 1, 1, 2))
    assert len(original.comparison) == 2
