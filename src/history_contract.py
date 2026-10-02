"""Identity and clock rules of CIM2's serialized HistoryData ring buffer."""
from datetime import datetime, timedelta


def owner_identity(company, owners):
    if company is None:
        return '', ''
    for candidate, player_id, index in owners:
        if company is candidate:
            return player_id or f'player-index:{index}', index
        try:
            from System import Object
            if Object.ReferenceEquals(company, candidate):
                return player_id or f'player-index:{index}', index
        except ImportError:
            pass
    return '', ''


def slot_time(current: datetime, position: int, index: int, length: int) -> datetime:
    current_hour = current.replace(minute=0, second=0, microsecond=0)
    return current_hour - timedelta(hours=(position - index) % length)


def valid_slot_indices(start: datetime, current: datetime, position: int, length: int):
    elapsed = int((current.replace(minute=0, second=0, microsecond=0)
                   - start.replace(minute=0, second=0, microsecond=0)).total_seconds() // 3600)
    return list(range(length)) if elapsed >= length else list(range(min(position + 1, length)))


def coverage_live_total(base_value: int, base_divider: int,
                        categories: list[tuple[int | None, int | None]]):
    """Resolve an unwritten live base slot from its complete category slots."""
    if (base_value == 0 and base_divider == 0 and categories and
            all(value is not None and divider is not None
                for value, divider in categories)):
        return (sum(value for value, _ in categories),
                sum(divider for _, divider in categories), '当前分类合成')
    return base_value, base_divider, '原始总组'
