"""Audit serialized line caches against independent runtime reconstruction.

This deliberately reports cache values separately from reconstructed values.
In multiplayer saves, a zero/10-minute/one-vehicle tuple is common for a
line whose Unity path cache was not serialized for the current owner.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SAVE = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT / "data" / "quicksave.76561198362520556-76561198845688243.save"
if not SAVE.is_absolute():
    SAVE = (PROJECT / SAVE).resolve()
sys.argv = [sys.argv[0], str(SAVE)]
import extract_runtime_data as e


def same(a: int, b: int, tol: int = 0) -> bool:
    return abs(a - b) <= tol


def main() -> None:
    root, _ = e.load_root()
    transport = e.field(root, "m_transportManagerData")
    line = e.field(transport, "m_firstLine")
    rows = []; seen = set()
    while line is not None:
        oid = int(e.field(line, "m_objectID") or 0)
        if oid in seen:
            break
        seen.add(oid)
        mode = e.line_mode(line)
        cache_len = int(e.field(line, "m_lineLength") or 0)
        cache_dur = int(e.field(line, "m_estimatedDuration") or 0)
        cache_top = int(e.field(line, "m_vehiclesNeededTop") or 0)
        calc_len = int(e.calculate_segment_length_sum(line))
        # This is intentionally cache-independent for all three values.
        calc_len2, calc_dur, calc_top = e.recompute_runtime_line_values(line, mode, 350000)
        cache_valid = cache_len > 0 and cache_dur > 6_000_000_000 and cache_top > 0
        if cache_valid and same(cache_len, calc_len) and same(cache_dur, calc_dur) and same(cache_top, calc_top):
            status = "缓存与运行时一致"
        elif cache_valid:
            status = "缓存与当前路线不一致"
        else:
            status = "缓存无效，使用重算值"
        rows.append({
            "线路号": int(e.field(line, "m_number") or 0),
            "运输制式": mode,
            "对象ID": oid,
            "缓存里程_km": cache_len / 1024000,
            "运行时里程_km": calc_len / 1024000,
            "缓存预计时间_分钟": cache_dur / 600_000_000,
            "运行时预计时间_分钟": calc_dur / 600_000_000,
            "缓存最大需求": cache_top,
            "运行时最大需求": calc_top,
            "缓存有效": "是" if cache_valid else "否",
            "结论": status,
        })
        line = e.field(line, "m_nextLine")
    out = PROJECT / "exports" / f"CIM2_运行时三项指标审计_{SAVE.stem}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    from collections import Counter
    print("线路", len(rows), "结论", dict(Counter(r["结论"] for r in rows)))
    print("输出", out)


if __name__ == "__main__":
    main()
