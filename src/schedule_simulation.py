"""Runtime-free timetable write-back simulation.

This module deliberately operates on the normalized JSON/CSV snapshot rather
than emitting a .save file.  It proves the schedule transformation and
validation rules independently from Unity object construction.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SimulatedEdit:
    line_key: str
    timetables: list[dict[str, Any]]


def _validate_table(table: dict[str, Any]) -> None:
    mask = int(table.get("运行日掩码", table.get("active_days", 0)))
    interval = int(table.get("间隔_tick", table.get("interval", 0)))
    start = int(table.get("开始_tick", table.get("start", 0)))
    end = int(table.get("结束_tick", table.get("end", 0)))
    if mask <= 0:
        raise ValueError("排班运行日掩码必须非零")
    if interval <= 0 or interval % 5 != 0:
        raise ValueError("发车间隔必须为 5 分钟倍数")
    if start < 0 or end < start:
        raise ValueError("排班时间范围无效")


def simulate_apply(snapshot: dict[str, Any], edits: list[SimulatedEdit]) -> dict[str, Any]:
    """Apply timetable edits to a normalized snapshot and enforce invariants.

    The input shape is the same line snapshot used by the report layer:
    ``{"lines": {line_key: {"时刻表": [...]}}}``.  No input object is
    mutated.  The result includes a machine-readable validation section.
    """
    before = deepcopy(snapshot)
    after = deepcopy(snapshot)
    lines = after.setdefault("lines", {})
    changed: set[str] = set()
    for edit in edits:
        if edit.line_key not in lines:
            raise KeyError(f"找不到线路对象：{edit.line_key}")
        for table in edit.timetables:
            _validate_table(table)
        lines[edit.line_key]["时刻表"] = deepcopy(edit.timetables)
        changed.add(edit.line_key)

    errors: list[str] = []
    if set(before.get("lines", {})) != set(lines):
        errors.append("线路对象集合发生变化")
    for key, old in before.get("lines", {}).items():
        if key in changed:
            continue
        if old != lines.get(key):
            errors.append(f"非目标线路发生变化：{key}")
    after["validation"] = {
        "status": "ok" if not errors else "rejected",
        "changed_lines": sorted(changed),
        "errors": errors,
        "write_back": False,
        "reason": "模拟层未生成 Unity .save；需运行时序列化器通过后才可写回",
    }
    if errors:
        raise ValueError("模拟写回校验失败：" + "; ".join(errors))
    return after

