"""Comparable card summaries, independent of widgets and chart visibility."""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from math import ceil

from statistics_model import period_bounds, summarize_buckets


@dataclass(frozen=True)
class CardComparison:
    text: str = '暂无可比数据'
    tooltip: str = ''
    direction: int = 0
    available: bool = False
    amount: Decimal | None = None
    unit: str = ''
    rank: int | None = None


def previous_period(start, grain):
    return period_bounds(start - timedelta(microseconds=1), grain)


def baseline_window(start, end):
    """Adjacent complete calendar unit; otherwise preceding matching weekdays."""
    for grain in ('month', 'week', 'day', 'hour'):
        if period_bounds(start, grain) == (start, end):
            return previous_period(start, grain)
    weeks = max(1, ceil((end - start).total_seconds() / (7 * 86400)))
    offset = timedelta(weeks=weeks)
    return start - offset, end - offset


def baseline_label(start, end):
    for grain, title in (('month', '月'), ('week', '周'), ('day', '日'), ('hour', '小时')):
        if period_bounds(start, grain) == (start, end):
            return f'较上{title}'
    return '较同期'


def number(value):
    return f'{value:,.2f}'.rstrip('0').rstrip('.')


def window_text(window):
    return f'{window[0]:%Y-%m-%d %H:%M} 至 {window[1]:%Y-%m-%d %H:%M}' if window else ''


def change(current, baseline, unit, prefix, *, current_window=None, previous_window=None,
           partial=False):
    if current is None or baseline is None:
        return CardComparison(tooltip=f'{prefix}：当前或基准缺少有效数据；缺测不补零')
    delta = current - baseline
    direction = (delta > 0) - (delta < 0)
    if unit == '%':
        amount, suffix = delta, '点'
        body = f'{"+" if delta > 0 else ""}{number(delta)} {suffix}' if delta else '持平'
    elif baseline:
        amount, suffix = delta * 100 / abs(baseline), '%'
        body = f'{"+" if amount > 0 else ""}{number(amount)}%' if delta else '持平'
    else:
        amount, suffix = delta, unit
        body = f'{"增加" if delta > 0 else "减少"} {number(abs(delta))} {unit}' if delta else '持平'
    text = f'{prefix} {body}'
    tooltip = (f'{prefix}；当前 {number(current)} {unit}（{window_text(current_window)}）；'
               f'基准 {number(baseline)} {unit}（{window_text(previous_window)}）；'
               f'绝对差 {number(delta)} {"点" if unit == "%" else unit}。')
    tooltip += ('占比按点数差计算；1 点对应比率差 0.01。' if unit == '%' else
                '相对差=(当前-基准)/|基准|；基准为零时显示绝对差。')
    if partial:
        text += ' *'
        tooltip += '包含部分周期或不完整记录，未进行补齐或年化。'
    return CardComparison(text, tooltip, direction, True, amount, suffix)


def peer_comparisons(values, names, unit, window=None):
    if len(values) < 2:
        return {owner: CardComparison(tooltip='至少选择两家公司才可比较') for owner in values}
    valid = {key: value for key, value in values.items() if value is not None}
    result = {}
    for owner, current in values.items():
        if len(values) == 2:
            other = next(key for key in values if key != owner)
            comparison = change(current, values[other], unit, '', current_window=window, previous_window=window)
            if comparison.available:
                word = '领先' if comparison.direction > 0 else '落后' if comparison.direction < 0 else '持平'
                amplitude = f' {number(abs(comparison.amount))}{comparison.unit}' if comparison.direction else ''
                text = f'{word}对方{amplitude}' if comparison.direction else '与对方持平'
                result[owner] = CardComparison(text,
                    f'对方：{names.get(other, other)}；{comparison.tooltip}', comparison.direction,
                    True, comparison.amount, comparison.unit)
            else:
                result[owner] = comparison
            continue
        if current is None or not valid:
            result[owner] = CardComparison(tooltip='该公司缺少有效数据，不能参与排名')
            continue
        maximum = max(valid.values())
        rank = 1 + sum(value > current for value in valid.values())
        tied = sum(value == current for value in valid.values()) > 1
        leader_ids = [key for key, value in valid.items() if value == maximum]
        comparison = change(current, maximum, unit, '距第一名', current_window=window, previous_window=window)
        text = f'{"并列" if tied else ""}第 {rank} 名'
        if rank > 1:
            text += f' · 落后 {number(abs(comparison.amount))}{comparison.unit}'
        if len(valid) != len(values):
            text += ' *'
        result[owner] = CardComparison(text,
            f'本次所选 {len(values)} 家公司中有 {len(valid)} 家有效；按指标数值从高到低，'
            f'并列采用竞赛排名；第一名：{"、".join(names.get(key, key) for key in leader_ids)}；{comparison.tooltip}',
            comparison.direction, True, comparison.amount, comparison.unit, rank)
    return result


def company_amount(result, owner, source='series'):
    if result is None:
        return None
    buckets = [bucket for (company, _), rows in getattr(result, source).items()
               if company == owner for bucket in rows]
    return summarize_buckets(buckets, result.metric)


def company_comparison(snapshot, mode, key, owner, names):
    result = snapshot.results.get(key)
    if result is None:
        return CardComparison()
    current = company_amount(result, owner)
    if mode == 'companies':
        amounts = {company: company_amount(result, company) for company in snapshot.filters.companies}
        return peer_comparisons(amounts, names, result.metric.unit, result.current_window)[owner]
    previous = (result if mode == 'period' else snapshot.card_previous.get(key))
    baseline = company_amount(previous, owner, 'comparison' if mode == 'period' else 'series')
    previous_window = result.comparison_window if mode == 'period' else previous.current_window if previous else None
    partial = any(not bucket.complete for source in (result.series,
        result.comparison if mode == 'period' else previous.series if previous else {})
        for (company, _), rows in source.items() if company == owner for bucket in rows)
    return change(current, baseline, result.metric.unit,
                  '较同比区间' if mode == 'period' else baseline_label(*result.current_window),
                  current_window=result.current_window, previous_window=previous_window, partial=partial)
