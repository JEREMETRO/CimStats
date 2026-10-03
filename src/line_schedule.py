"""Read-only timetable presentation and interval calculations.

``prepare_schedule(entries, period_rules=None)`` copies every departure and
preserves its source metadata. Non-all-day schedules mark times before 05:00
as the next operating day; all-day schedules start at midnight on one day.
Intervals use .NET ticks when available, never the rounded HH:mm label.
The returned interval numbers are minutes; compact labels retain whole seconds.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re

TICKS_PER_SECOND = 10_000_000
DAY_TICKS = 86400 * TICKS_PER_SECOND
OPERATING_DAY_START = 5 * 3600 * TICKS_PER_SECOND
STOP_GAP_TICKS = 180 * 60 * TICKS_PER_SECOND
WEEKDAY_MASK = 0x7F

# Confirmed query periods. Every range is half-open [start, end).
PERIOD_RULES = {
    'morning_peak': (('07:30', '09:30'),),
    'evening_peak': (('17:00', '19:30'),),
    'peak': (('07:30', '09:30'), ('17:00', '19:30')),
    'offpeak': (('05:30', '07:30'), ('09:30', '17:00'), ('19:30', '24:00')),
    'night': (('00:00', '05:30'),),
}
PERIOD_LABELS = {'morning_peak': '早高峰', 'evening_peak': '晚高峰',
                 'peak': '高峰', 'offpeak': '平峰', 'night': '夜间'}


def optional_integer(value):
    """Parse integer source fields without defaulting an unknown value to zero."""
    if value is None or str(value).strip() == '':
        return None
    try:
        result = Decimal(str(value))
        if result.is_finite() and result == result.to_integral_value():
            return int(result)
    except (InvalidOperation, ValueError, TypeError):
        pass
    return None


def running_day_mask(value):
    """Read the game's Int32 field while preserving bits outside its seven days.

    TimeTable.m_activeDays is Int32, not an enum constrained to 0..127.
    CalculateNeededVehicles checks only bits 0..6; signed/high flag bits
    must not cause otherwise usable weekday records to become unknown.
    """
    mask = optional_integer(value)
    return mask if mask is not None and -(1 << 31) <= mask < (1 << 31) else None


def timetable_entry_inactive(entry):
    """Only explicit source status disables a row; zero times/counts do not."""
    mask = running_day_mask(entry.get('运行日掩码', entry.get('时刻表_运行日掩码')))
    return (not mask & WEEKDAY_MASK if mask is not None
            else entry.get('运行日状态') == '未启用')


def _clock_tick(value):
    text = str(value or '').strip().removeprefix('次日').strip()
    # The extractor emits "1d 01:30:00" for clocks beyond midnight.
    match = re.fullmatch(r'(?:(\d+)d\s+)?(\d{1,3}):(\d{2})(?::(\d{2}(?:\.\d+)?))?', text)
    if not match:
        return None
    days, hours, minutes, seconds = match.groups()
    seconds = Decimal(seconds or '0')
    if int(minutes) >= 60 or seconds >= 60:
        return None
    total = ((int(days or 0) * 24 + int(hours)) * 3600 + int(minutes) * 60) * TICKS_PER_SECOND
    return total + int(seconds * TICKS_PER_SECOND)


def departure_tick(entry):
    """Return the serialized departure tick, falling back to its clock text."""
    for key in ('发班_tick', 'tick'):
        tick = optional_integer(entry.get(key))
        if tick is not None and tick >= 0:
            return tick
    for key in ('发班时间', 'time'):
        tick = _clock_tick(entry.get(key))
        if tick is not None:
            return tick
    return None


def _clock_label(tick):
    seconds = tick // TICKS_PER_SECOND
    return f'{seconds // 3600:02d}:{seconds % 3600 // 60:02d}'


def interval_text(minutes):
    """Render a mean to the nearest second, without dropping seconds early."""
    if minutes is None:
        return '—'
    seconds = int(Decimal(str(minutes)) * 60 + Decimal('0.5'))
    whole_minutes, seconds = divmod(seconds, 60)
    return f'{whole_minutes}m{seconds}s'


def _mean_minutes(gaps):
    return sum(gaps) / len(gaps) / TICKS_PER_SECOND / 60 if gaps else None


def _ranges(rules, period):
    ranges = []
    for pair in rules.get(period, ()):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        start, end = (_clock_tick(value) for value in pair)
        if start is None or end is None or start >= DAY_TICKS or end > DAY_TICKS:
            continue
        if end <= start:
            end += DAY_TICKS
        ranges.append((start, end, f'{_clock_label(start)}–{_clock_label(end % DAY_TICKS) if end > DAY_TICKS else _clock_label(end)}'))
    return ranges


def _pair_in_range(start, gap, lower, upper):
    # Both endpoints and the complete gap must lie in one confirmed window.
    return any(lower <= start + shift and start + shift + gap < upper
               for shift in (-DAY_TICKS, 0, DAY_TICKS))


def prepare_schedule(entries, period_rules=None) -> dict:
    """Prepare a schedule, its service segments and precise period averages.

    Output: entries, first/last (display strings), segments with first/last/count/
    text, all_day, count, valid_count, service_text, average_interval (minutes or
    None), average_interval_text/tooltip, period texts, *_tooltip values and
    period_diagnostics with departure/interval counts and absence status.
    ``period_rules={}`` explicitly means unconfirmed periods.
    Invalid clock rows remain visible as — with time_valid=False; their presence
    makes averages unavailable instead of silently undercounting departures.
    All-day grid order starts at 00:00 with no next-day cells. Other grid order
    uses 05:00, while service segments start only after real circular
    stop gaps. Summary labels unfold each complete segment from its operating-
    day start; crossing 05:00 does not reset that segment's day offset.
    """
    rules = PERIOD_RULES if period_rules is None else period_rules
    period_ranges = {period: _ranges(rules, period) for period in PERIOD_LABELS}
    normalized = []
    for source in entries or ():
        row = deepcopy(source)
        raw_tick = departure_tick(row)
        tick = raw_tick % DAY_TICKS if raw_tick is not None else None
        next_day = tick is not None and tick < OPERATING_DAY_START
        original_time = row.get('original_time', row.get('发班时间', row.get('time', '')))
        time = _clock_label(tick) if tick is not None else '—'
        diagnostics = [str(row['diagnostic'])] if row.get('diagnostic') else []
        if tick is None:
            diagnostics.append(f'无法解析发班时间：{original_time or "缺失"}')
        classifications = {period for period, ranges in period_ranges.items()
                           if tick is not None and any(_pair_in_range(tick, 0, lower, upper)
                                                       for lower, upper, _ in ranges)}
        period = next((key for key in PERIOD_LABELS if key in classifications), 'unknown')
        row.update(time=time, next_day=next_day, time_valid=tick is not None,
                   period=period, period_label=PERIOD_LABELS.get(period, '时段未确认'),
                   morning_peak='morning_peak' in classifications,
                   evening_peak='evening_peak' in classifications,
                   original_time=original_time,
                   diagnostic='；'.join(dict.fromkeys(diagnostics)),
                   display_time=('次日' if next_day else '') + time,
                   clock_seconds=tick / TICKS_PER_SECOND if tick is not None else None,
                   operating_seconds=(tick + (DAY_TICKS if next_day else 0)) / TICKS_PER_SECOND if tick is not None else None)
        normalized.append((tick, row))
    normalized.sort(key=lambda item: (item[1]['operating_seconds'] is None,
                                      item[1]['operating_seconds'] or 0))
    valid = [(tick, row) for tick, row in normalized if tick is not None]
    calendar = sorted(valid, key=lambda item: item[0])
    pairs = []
    if len(calendar) >= 2:
        for index, (tick, _) in enumerate(calendar):
            end = calendar[(index + 1) % len(calendar)][0]
            if index == len(calendar) - 1:
                end += DAY_TICKS
            pairs.append((tick, end - tick))
    running_days_complete = all(row.get('running_day_valid', True) for _, row in normalized)
    complete = len(valid) == len(normalized) and running_days_complete
    all_day = bool(pairs) and complete and all(gap < STOP_GAP_TICKS for _, gap in pairs)
    if all_day:
        normalized = calendar
        valid = calendar
        for _, row in normalized:
            row.update(next_day=False, display_time=row['time'], operating_seconds=row['clock_seconds'])
    gaps = [gap for _, gap in pairs if gap < STOP_GAP_TICKS] if complete else []
    average = _mean_minutes(gaps)
    segments = []
    if all_day:
        segments = [dict(first='00:00', last='24:00', count=len(valid), text='00:00–24:00')]
    elif valid and running_days_complete:
        starts = [(index + 1) % len(calendar) for index, (_, gap) in enumerate(pairs)
                  if gap >= STOP_GAP_TICKS]
        if not starts:
            # A single valid row, or incomplete data without a known stop gap.
            starts = [min(range(len(calendar)), key=lambda index:
                          calendar[index][0] + (DAY_TICKS if calendar[index][0] < OPERATING_DAY_START else 0))]
        starts.sort(key=lambda index: calendar[index][0] +
                    (DAY_TICKS if calendar[index][0] < OPERATING_DAY_START else 0))
        for start in starts:
            first_tick = calendar[start][0]
            unfolded_tick = first_tick + (DAY_TICKS if first_tick < OPERATING_DAY_START else 0)
            first_unfolded = unfolded_tick
            count = 1
            for offset in range(1, len(calendar)):
                preceding = (start + offset - 1) % len(calendar)
                gap = pairs[preceding][1]
                if gap >= STOP_GAP_TICKS:
                    break
                unfolded_tick += gap
                count += 1
            labels = []
            for tick in (first_unfolded, unfolded_tick):
                day, clock = divmod(tick, DAY_TICKS)
                prefix = '' if day == 0 else '次日' if day == 1 else '后日' if day == 2 else f'{day}日后'
                labels.append(prefix + _clock_label(clock))
            first, last = labels
            segments.append(dict(first=first, last=last, count=count,
                                 text=first if count == 1 else f'{first}–{last}'))
    first = segments[0]['first'] if segments else '—'
    last = segments[-1]['last'] if segments else '—'
    average_note = ('按真实发班 tick（缺失时使用原始时钟）计算循环24小时的相邻班次间隔；'
                    '排除≥180分钟停运间隔，保留重复班次的0秒间隔。')
    average_note += f'有效间隔{len(gaps)}个；均值{interval_text(average)}。'
    if not running_days_complete:
        average_note += '运行日未知，无法确认记录是否属于同一天，数据不足。'
    if len(valid) != len(normalized):
        average_note += '存在无法解析的发班时间，数据不足。'
    elif average is None and running_days_complete:
        average_note += '数据不足：没有可计算的相邻班次间隔。'
    result = dict(entries=[row for _, row in normalized], first=first, last=last,
                  segments=segments, all_day=all_day, count=len(normalized), valid_count=len(valid),
                  data_complete=complete,
                  service_text='；'.join(s['text'] for s in segments) or '—',
                  average_interval=average, average_interval_text=interval_text(average),
                  average_interval_tooltip=average_note)
    result['diagnostics'] = [row['diagnostic'] for _, row in normalized if row['diagnostic']]
    result['invalid_count'] = len(normalized) - len(valid)
    service_note = (f"运营区间：{result['service_text']}；" +
                   ("全天运营，网格从00:00按当日时钟排序，所有班次为同日。" if all_day else
                    "网格按05:00运营日分界排序并标记次日。") +
                    "摘要首末班是按圆周≥180分钟停运空档确定的完整连续段起止，不是网格的首末条；"
                    "完整段跨05:00仍连续，摘要中的次日标记沿段内时间递增延续。")
    if result['invalid_count']:
        service_note += f"另有{result['invalid_count']}班时间无法解析，原记录保留为—。"
    if not running_days_complete:
        service_note += '运行日未知，不能假定这些记录属于同一天，首末班及运营段显示—。'
    result['first_tooltip'] = result['last_tooltip'] = service_note
    result['period_diagnostics'] = {}
    for period, label in PERIOD_LABELS.items():
        ranges = period_ranges[period]
        window_counts = [sum(_pair_in_range(tick, 0, lower, upper) for tick, _ in calendar)
                         for lower, upper, _ in ranges]
        departure_count = sum(any(_pair_in_range(tick, 0, lower, upper)
                                  for lower, upper, _ in ranges) for tick, _ in calendar)
        period_gaps = [gap for start, gap in pairs if gap < STOP_GAP_TICKS and
                       any(_pair_in_range(start, gap, lower, upper) for lower, upper, _ in ranges)] if complete else []
        mean = _mean_minutes(period_gaps)
        result[period] = interval_text(mean)
        if not ranges:
            status = 'unconfirmed'
            note = f'{label}时间范围未确认，不能据时刻表编号或间隔推定。'
        else:
            if not complete:
                status = 'incomplete_data'
            elif mean is not None:
                status = 'computed'
            elif not departure_count:
                status = 'no_departures'
            elif all(count < 2 for count in window_counts):
                status = 'insufficient_departures'
            else:
                status = 'stoppage_only'
            note = f"{label}时段：{'、'.join(text for _, _, text in ranges)}；半开区间，结束时刻归下一时段。"
            note += f'按真实秒精度相邻发班计算，排除≥180分钟停运间隔，不跨不连续时段；有效间隔{len(period_gaps)}个。'
            if mean is None:
                note += '数据不足，显示—。'
        result['period_diagnostics'][period] = dict(
            status=status, departure_count=departure_count, window_departure_counts=window_counts,
            interval_count=len(period_gaps))
        result[f'{period}_tooltip'] = note
    return result


def weekly_vehicle_average(entries, duration_tick):
    """Mirror the game's 7×288-slot fixed-point mean, including endpoint wrap.

    This is the confirmed SelectionPanel algorithm also used by the extractor:
    both endpoints wrap into 2016 slots, then only start < end is counted.
    Slot sums are left-shifted by 10 and integer-divided before display scaling.
    """
    duration = optional_integer(duration_tick)
    if duration is None or duration <= 0:
        return None
    slot_ticks = 3_000_000_000
    occupied_slots = 0
    for row in entries:
        mask = running_day_mask(row.get('运行日掩码', row.get('时刻表_运行日掩码')))
        if mask is None:
            return None
        if not mask & WEEKDAY_MASK:
            continue
        tick = departure_tick(row)
        if tick is None:
            return None
        for day in range(7):
            if mask & (1 << day):
                start = (day * 288 + tick // slot_ticks) % 2016
                end = (day * 288 + (tick + duration) // slot_ticks) % 2016
                occupied_slots += max(0, end - start)
    return ((occupied_slots << 10) // 2016) / 1024
