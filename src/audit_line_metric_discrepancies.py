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


def iv(value):
    try:
        return int(value or 0)
    except Exception:
        return 0


def main() -> None:
    root, _ = e.load_root()
    start = e.field(root, "m_simulationStart")
    now = e.field(root, "m_simulationTime")
    frame = iv(e.field(root, "m_simulationFrame"))
    span = max(1, round((int(now.Ticks) - int(start.Ticks)) / frame)) if start is not None and now is not None and frame else 350000
    transport = e.field(root, "m_transportManagerData")
    line = e.field(transport, "m_firstLine")
    rows = []
    seen = set()
    while line is not None:
        oid = iv(e.field(line, "m_objectID"))
        if oid in seen:
            break
        seen.add(oid)
        stops = e.array_values(e.field(line, "m_stops"))
        paths = [e.array_values(e.field(s, "m_path")) for s in stops]
        mode = e.line_mode(line)
        calc_len, calc_dur, calc_top = e.recompute_runtime_line_values(line, mode, span)
        cache_len = iv(e.field(line, "m_lineLength"))
        cache_dur = iv(e.field(line, "m_estimatedDuration"))
        cache_top = iv(e.field(line, "m_vehiclesNeededTop"))
        _, stop_time = e.VEHICLE_TYPE_PARAMS.get(mode, (3300, 12))
        dwell_count = sum(
            1 for i, s in enumerate(stops) if i > 0 and e.can_stop_here_serialized(e.field(s, "m_stop"))
        )
        rows.append({
            "线路号": iv(e.field(line, "m_number")),
            "运输制式": mode,
            "缓存里程_km": cache_len / 1024000,
            "重算里程_km": calc_len / 1024000,
            "缓存预计时间_分钟": cache_dur / 600000000,
            "重算预计时间_分钟": calc_dur / 600000000,
            "缓存最大需求": cache_top,
            "重算最大需求": calc_top,
            "线路完成": bool(e.field(line, "m_complete")),
            "站点数": len(stops),
            "有路径站点数": sum(bool(p) for p in paths),
            "路径段数": sum(len(p) for p in paths),
            "停站计时数（探针）": dwell_count,
            "停站秒数（车型）": stop_time,
            "路径脏标记数": sum(bool(e.field(s, "m_pathDirty")) for s in stops),
            "里程差内部值": calc_len - cache_len,
            "预计时间差_分钟": calc_dur / 600000000 - cache_dur / 600000000,
            "最大需求差": calc_top - cache_top,
        })
        line = e.field(line, "m_nextLine")
    out = PROJECT / "exports" / f"CIM2_线路指标差异审计_{SAVE.stem}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("线路", len(rows), "frame_time_span", span)
    print("缓存三项均与重算一致", sum(r["里程差内部值"] == 0 and r["预计时间差_分钟"] == 0 and r["最大需求差"] == 0 for r in rows))
    print("输出", out)


if __name__ == "__main__":
    main()
