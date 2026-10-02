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
    current = e.field(root, "m_simulationTime")
    current_ticks = iv(current.Ticks) if current is not None else 0
    transport = e.field(root, "m_transportManagerData")
    line = e.field(transport, "m_firstLine")
    rows = []
    seen = set()
    while line is not None:
        oid = iv(e.field(line, "m_objectID"))
        if oid in seen:
            break
        seen.add(oid)
        build_ticks = iv(e.field(line, "m_buildTime"))
        elapsed = max((current_ticks - build_ticks) >> 10, 1) if build_ticks else 1
        total = iv(e.field(line, "m_totalTransported"))
        # Exact order from InfoTool.FormatObjectInfo:
        # ((total * 864000000000) / elapsed) -> Int32 -> FormatNumberFixed.
        average_fixed = (total * 864000000000) // elapsed
        rows.append({
            "线路号": iv(e.field(line, "m_number")),
            "运输制式": e.line_mode(line),
            "对象ID": oid,
            "线路启用": bool(e.field(line, "m_active")),
            "线路完成": bool(e.field(line, "m_complete")),
            "m_buildTime_tick": build_ticks,
            "m_buildTime": e.datetime_text(build_ticks),
            "m_lineEditTime": e.datetime_text(e.field(line, "m_lineEditTime")),
            "当前模拟时间": e.datetime_text(current_ticks),
            "平均客流公式分母": elapsed,
            "累计客流": total,
            "今日客流": iv(e.field(line, "m_transportedToday")),
            "平均客流_固定点": average_fixed,
            "平均客流_游戏显示值": round(average_fixed / 1024, 2),
            "首个站点建造时间": e.datetime_text(min(
                (iv(e.field(e.field(s, "m_stop"), "m_buildTime")) for s in e.array_values(e.field(line, "m_stops")) if e.field(s, "m_stop") is not None),
                default=0,
            )),
        })
        line = e.field(line, "m_nextLine")
    out = PROJECT / "exports" / f"CIM2_开线日期与平均客流公式审计_{SAVE.stem}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("线路", len(rows), "无开线字段", sum(not r["m_buildTime_tick"] for r in rows), "未启用", sum(not r["线路启用"] for r in rows))
    print("输出", out)


if __name__ == "__main__":
    main()
