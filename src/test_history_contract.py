from datetime import datetime as D

from history_contract import owner_identity, slot_time, valid_slot_indices, coverage_live_total


def test_coverage_live_total_uses_categories_only_for_unwritten_base_pair():
    assert coverage_live_total(0, 0, [(3, 5), (0, 7)]) == (3, 12, '当前分类合成')
    assert coverage_live_total(0, 12, [(3, 5), (0, 7)]) == (0, 12, '原始总组')
    assert coverage_live_total(4, 12, [(3, 5), (0, 7)]) == (4, 12, '原始总组')
    assert coverage_live_total(0, 0, [(3, 5), (None, 7)]) == (0, 0, '原始总组')
    assert coverage_live_total(0, 0, []) == (0, 0, '原始总组')


def test_same_name_company_uses_object_identity():
    a, b = object(), object()
    owners = [(a, 'player-a', 0), (b, 'player-b', 1)]
    assert owner_identity(b, owners) == ('player-b', 1)
    assert owner_identity(a, owners) == ('player-a', 0)


def test_ring_slots_reconstruct_latest_768_hours():
    start = D(2013, 1, 1)
    current = start.replace(day=2, hour=2)
    assert valid_slot_indices(start, current, 2, 4) == [0, 1, 2, 3]
    assert slot_time(current, 2, 3, 4) == D(2013, 1, 1, 23)
    assert slot_time(current, 2, 2, 4) == D(2013, 1, 2, 2)


def test_unfilled_ring_skips_unwritten_slots():
    start = D(2013, 1, 1)
    current = D(2013, 1, 1, 2)
    assert valid_slot_indices(start, current, 2, 4) == [0, 1, 2]
