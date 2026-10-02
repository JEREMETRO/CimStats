"""Deterministic timetable planning models used by the save editor.

The module is deliberately independent from pythonnet and Qt so plans can be
validated and previewed without loading a game assembly.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
from pathlib import Path
from itertools import product

VEHICLE_CODES = {0: ("任", "任意"), 1: ("小", "小型"), 2: ("中", "中型"), 3: ("大", "大型")}
PERIOD_PRIORITY = ("早高峰", "晚高峰", "夜间", "工作日", "周末")


def minutes(value: str | int) -> int:
    if isinstance(value, int):
        result = value
    else:
        parts = [int(x) for x in str(value).strip().split(":")]
        result = parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0] * 60 + parts[1] + parts[2] // 60
    if not 0 <= result < 24 * 60:
        raise ValueError(f"时间超出一天范围: {value}")
    return result


def five_minute(value: int) -> int:
    if value <= 0:
        raise ValueError("间隔必须大于 0")
    return max(5, int(round(value / 5.0)) * 5)


@dataclass
class TimePeriod:
    name: str
    start: int
    end: int
    interval: int
    vehicle_code: int = 0
    day_mask: int = 0
    requested_interval: float = field(init=False, default=0)
    vehicle_preference: str = "任意"

    def __post_init__(self):
        self.start = minutes(self.start); self.end = minutes(self.end)
        self.requested_interval = float(self.interval)
        self.interval = five_minute(self.interval)
        if self.end <= self.start:
            raise ValueError(f"时段结束时间必须晚于开始时间: {self.name}")
        if self.vehicle_code not in VEHICLE_CODES:
            raise ValueError(f"未知车型代码: {self.vehicle_code}")

    def departures(self) -> list[int]:
        return list(range(self.start, self.end + 1, self.interval))


@dataclass
class CapacityProfile:
    averages: dict[int, float] = field(default_factory=dict)
    samples: dict[int, int] = field(default_factory=dict)

    def capacity(self, code: int) -> float:
        if code in self.averages and self.samples.get(code, 0):
            return self.averages[code]
        known = [v for k, v in self.averages.items() if self.samples.get(k, 0)]
        return sum(known) / len(known) if known else 0.0


@dataclass
class TimetableTemplate:
    day_mask: int
    start: int
    end: int
    interval: int
    vehicle_code: int = 0
    train_configuration: int = 0

    def rows(self) -> list[int]:
        return TimePeriod("template", self.start, self.end, self.interval, self.vehicle_code).departures()


@dataclass
class SchedulePlan:
    name: str
    periods: list[TimePeriod] = field(default_factory=list)
    vehicle_policy: str = "任意"
    version: int = 1
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def templates(self) -> list[TimetableTemplate]:
        result = []
        for period in self.periods:
            result.append(TimetableTemplate(period.day_mask, period.start, period.end, period.interval, period.vehicle_code))
        return result

    def to_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: Path) -> "SchedulePlan":
        data = json.loads(path.read_text(encoding="utf-8"))
        data["periods"] = [TimePeriod(**{k: v for k, v in item.items() if k != "requested_interval"}) for item in data.get("periods", [])]
        return cls(**data)


def build_plan(name: str, periods: list[TimePeriod], profile: CapacityProfile | None = None) -> SchedulePlan:
    """Normalize intervals to game-compatible 5-minute slots.

    Periods are retained as separate native timetable templates. This is the
    representation needed to combine the game's six timetable records.
    """
    normalized = []
    for period in periods:
        interval = five_minute(period.interval)
        if profile and period.vehicle_code in (1, 2, 3) and profile.capacity(period.vehicle_code) <= 0:
            raise ValueError(f"车型 {VEHICLE_CODES[period.vehicle_code][1]} 没有可用容量样本")
        normalized.append(TimePeriod(period.name, period.start, period.end, interval, period.vehicle_code, period.day_mask))
    return SchedulePlan(name=name, periods=normalized)


def plan_capacity(plan: SchedulePlan, profile: CapacityProfile) -> dict:
    by_period = []
    total = 0.0
    for period in plan.periods:
        count = len(period.departures())
        capacity = count * profile.capacity(period.vehicle_code)
        total += capacity
        by_period.append({"时段": period.name, "发班数": count, "平均单班运力": profile.capacity(period.vehicle_code), "理论运力": capacity})
    return {"时段": by_period, "全天发班数": sum(x["发班数"] for x in by_period), "全天理论运力": total}


def generate_cim2_templates(periods: list[TimePeriod], *, day_mask: int = 31,
                            max_templates: int = 6) -> list[TimetableTemplate]:
    """Generate native-compatible timetable templates from overlapping periods.

    CIM2 stores each timetable with one constant interval.  Overlapping
    periods are therefore resolved by ``PERIOD_PRIORITY`` and split into
    contiguous runs; requested intervals are rounded to the nearest 5-minute
    slot (7 minutes becomes 5).  The result is capped at the game's six
    timetable records.
    """
    if not periods:
        return []
    ordered = {name: i for i, name in enumerate(PERIOD_PRIORITY)}
    slots: dict[int, TimePeriod] = {}
    for p in periods:
        normalized = TimePeriod(p.name, p.start, p.end, p.interval, p.vehicle_code, day_mask)
        for t in normalized.departures():
            current = slots.get(t)
            if current is None or ordered.get(normalized.name, 99) < ordered.get(current.name, 99):
                slots[t] = normalized
    if not slots:
        return []
    times = sorted(slots)
    runs: list[list[int]] = []
    for t in times:
        p = slots[t]
        if runs and slots[runs[-1][-1]] is p and t - runs[-1][-1] == 5:
            runs[-1].append(t)
        else:
            runs.append([t])
    templates = []
    for run in runs:
        p = slots[run[0]]
        interval = five_minute(p.interval)
        if len(run) == 1:
            end = run[0]
        else:
            end = run[-1]
        templates.append(TimetableTemplate(day_mask, run[0], end, interval, p.vehicle_code))
    if len(templates) > max_templates:
        raise ValueError(f"重叠时段需要 {len(templates)} 张排班表，超过 CIM2 上限 {max_templates} 张")
    return templates


def generate_partitioned_templates(period_periods: list[TimePeriod], *, day_mask: int = 31) -> list[TimetableTemplate]:
    """Partition a base daytime period around peak periods (no duplicate rows)."""
    if not period_periods:
        return []
    base = next((p for p in period_periods if p.name in ("白天", "工作日")), period_periods[0])
    peaks = sorted((p for p in period_periods if p is not base), key=lambda p: p.start)
    boundaries = [base.start] + [x for p in peaks for x in (p.start, p.end)] + [base.end]
    out: list[TimetableTemplate] = []
    for a, b in zip(boundaries, boundaries[1:]):
        if b <= a:
            continue
        owner = next((p for p in peaks if p.start <= a and b <= p.end), base)
        # End points are inclusive in CIM2; leave the boundary departure to
        # the following segment so adjacent tables never duplicate a row.
        end = b if b == base.end else b - 5
        if end >= a:
            out.append(TimetableTemplate(day_mask, a, end, five_minute(owner.interval), owner.vehicle_code))
    if len(out) > 6:
        raise ValueError("切分后排班表超过 CIM2 的六表上限")
    return out


def compose_target_interval(start: int, end: int, target: float, *, day_mask: int = 31,
                            vehicle_code: int = 0) -> list[TimetableTemplate]:
    """Approximate a target headway using CIM2 timetable combinations.

    A target near 7 minutes is represented by two native 15-minute tables
    offset by 5 minutes, producing alternating 5/10-minute gaps (7.5-minute
    mean).  Other targets use the nearest native interval, with a second
    offset table when that materially improves the mean.
    """
    if end <= start or target <= 0:
        raise ValueError("目标时段或间隔无效")
    base = max(5, int(round(target / 5.0)) * 5)
    if target < base and base >= 10:
        base -= 5
    mean_error_single = abs(base - target)
    pair = max(5, int(round(target * 2 / 5.0)) * 5)
    pair_mean = pair / 2
    if pair >= 10 and abs(pair_mean - target) < mean_error_single:
        first = TimetableTemplate(day_mask, start, end, pair, vehicle_code)
        # Five-minute phase offset is the game's native grid and yields
        # alternating 5/10-minute gaps for a 15-minute pair.
        second_start = start + 5
        second = TimetableTemplate(day_mask, second_start, end, pair, vehicle_code)
        return [first, second]
    return [TimetableTemplate(day_mask, start, end, base, vehicle_code)]


def adaptive_departures(start: int, end: int, target: float,
                        vehicle_codes: list[int], profile: CapacityProfile) -> list[dict]:
    """Generate a mixed-vehicle departure sequence for an average headway.

    High-capacity vehicles are deliberately assigned a larger preceding gap;
    low-capacity vehicles receive a smaller gap.  Every departure remains on
    CIM2's five-minute grid and the resulting sequence is deterministic.
    """
    if not vehicle_codes:
        vehicle_codes = [0]
    caps = [profile.capacity(c) or 1.0 for c in vehicle_codes]
    mean_cap = sum(caps) / len(caps)
    out: list[dict] = []
    t = int(start)
    i = 0
    while t <= end:
        code = vehicle_codes[i % len(vehicle_codes)]
        cap = profile.capacity(code) or mean_cap
        # The gap leading to this vehicle is capacity-weighted: a large
        # vehicle receives the larger preceding gap, while the following gap
        # naturally becomes shorter when the next small vehicle departs.
        raw_gap = target * (cap / mean_cap)
        gap = max(5, int(round(raw_gap / 5.0)) * 5)
        out.append({"时刻": t, "车型代码": code, "间隔": gap})
        t += gap
        i += 1
    return out


def preferred_vehicle_codes(preference: str) -> list[int]:
    mapping = {"任意": [0], "小车": [1], "小型": [1], "中车": [2],
               "中型": [2], "大车": [3], "大型": [3]}
    return mapping.get(preference, [0])


def adaptive_for_period(period: TimePeriod, profile: CapacityProfile) -> list[dict]:
    """Generate departures using the period's configured vehicle preference."""
    return adaptive_departures(period.start, period.end, period.requested_interval or period.interval,
                               preferred_vehicle_codes(period.vehicle_preference), profile)


def adaptive_timetable_templates(start: int, end: int, target: float,
                                 vehicle_codes: list[int], profile: CapacityProfile,
                                 *, day_mask: int = 31) -> list[TimetableTemplate]:
    """Pack adaptive departures when representable by native constant-gap tables."""
    rows = adaptive_departures(start, end, target, vehicle_codes, profile)
    groups: dict[tuple[int, int], list[int]] = {}
    for row in rows:
        groups.setdefault((row["车型代码"], row["间隔"]), []).append(row["时刻"])
    if len(groups) > 1:
        raise ValueError("混合车型自适应间隔无法无损压缩为固定间隔排班表；请使用原生多表组合写回")
    templates = []
    for (code, gap), times in sorted(groups.items(), key=lambda x: x[1][0]):
        templates.append(TimetableTemplate(day_mask, times[0], times[-1], gap, code))
    if len(templates) > 6:
        raise ValueError("自适应车型组合超过 CIM2 六张排班表上限")
    return templates


def optimize_period_composition(periods: list[TimePeriod], *, max_tables: int = 6,
                                day_mask: int = 31) -> dict:
    """Enumerate native timetable combinations and choose the closest plan."""
    candidates = []
    for p in periods:
        options = []
        target = p.requested_interval or p.interval
        for interval in range(5, 61, 5):
            for count in (1, 2, 3):
                for offset in range(0, interval, 5):
                    tables = [TimetableTemplate(p.day_mask or day_mask, p.start + (offset if j else 0), p.end, interval, p.vehicle_code) for j in range(count)]
                    rows = sorted({x for t in tables for x in t.rows() if p.start <= x <= p.end})
                    if len(rows) < 2:
                        continue
                    avg = (rows[-1] - rows[0]) / (len(rows) - 1)
                    score = abs(avg - target)
                    options.append((score, len(tables), tables, avg, len(rows)))
        # Also enumerate mixed native intervals (e.g. 20 + 30 = 12-minute
        # average over a two-hour peak window).
        for a in range(5, 61, 5):
            for b in range(a, 61, 5):
                tables = [TimetableTemplate(p.day_mask or day_mask, p.start, p.end, a, p.vehicle_code),
                          TimetableTemplate(p.day_mask or day_mask, p.start, p.end, b, p.vehicle_code)]
                rows = sorted({x for t in tables for x in t.rows() if p.start <= x <= p.end})
                if len(rows) < 2:
                    continue
                avg = (rows[-1] - rows[0]) / (len(rows) - 1)
                score = abs(avg - target)
                options.append((score, 2, tables, avg, len(rows)))
        options.sort(key=lambda x: (x[0], x[1], sum(abs(t.interval - target) for t in x[2]), max(t.interval for t in x[2])))
        shortlist = options[:8]
        singles = [x for x in options if x[1] == 1]
        if singles and all(x[1] != 1 for x in shortlist):
            shortlist.append(singles[0])
        candidates.append(shortlist)
    best = None
    for choice in product(*candidates):
        tables = [t for c in choice for t in c[2]]
        if len(tables) > max_tables:
            continue
        score = sum(c[0] for c in choice) + len(tables) * 0.01
        item = (score, choice, tables)
        if best is None or score < best[0]:
            best = item
    if best is None:
        raise ValueError("没有找到不超过六张 CIM2 排班表的组合")
    return {
        "排班表": [t.__dict__ for t in best[2]],
        "总表数": len(best[2]),
        "时段结果": [{"时段": p.name, "目标间隔": p.requested_interval, "实际平均间隔": c[3], "班次数": c[4], "表数": c[1]} for p, c in zip(periods, best[1])],
        "总误差": best[0],
    }


def score_overlay(tables: list[TimetableTemplate], start: int, end: int, target: float) -> dict:
    """Score an overlay without deduplicating departures (duplicates are bursts)."""
    rows = sorted(x for t in tables for x in t.rows() if start <= x <= end)
    gaps = [b - a for a, b in zip(rows, rows[1:])]
    duplicate_count = sum(1 for g in gaps if g == 0)
    avg = (end - start) / max(1, len(rows) - 1)
    return {"平均间隔": avg, "重复班次": duplicate_count,
            "误差": abs(avg - target),
            "评分": duplicate_count * 1000 + abs(avg - target)}


def optimize_overlay(base: TimePeriod, peak: TimePeriod, target: float) -> dict:
    """Search 5-minute start/end offsets for a base+peak overlay."""
    best = None
    for shift in range(-10, 11, 5):
        p = TimetableTemplate(peak.day_mask or base.day_mask, peak.start + shift,
                              peak.end + shift, peak.interval, peak.vehicle_code)
        result = score_overlay([
            TimetableTemplate(base.day_mask, base.start, base.end, base.interval, base.vehicle_code), p
        ], peak.start, peak.end, target)
        if best is None or result["评分"] < best[0]:
            best = (result["评分"], p, result)
    return {"增强表": best[1].__dict__, "评估": best[2], "重复保留": True}
