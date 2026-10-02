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


def main() -> None:
    root, _ = e.load_root()
    transport = e.field(root, "m_transportManagerData")
    line = e.field(transport, "m_firstLine")
    seen = set()
    rows = []
    while line is not None:
        oid = int(e.field(line, "m_objectID") or 0)
        if oid in seen:
            break
        seen.add(oid)
        stops = e.array_values(e.field(line, "m_stops"))
        raw = e.map_length_from_vehicle_route(line)
        converted = e.calculate_segment_length_sum(line)
        euclidean = []
        for i, current in enumerate(stops):
            following = stops[(i + 1) % len(stops)]
            a = e.field(e.field(current, "m_stop"), "m_position")
            b = e.field(e.field(following, "m_stop"), "m_position")
            euclidean.append(e.fixed_vector_length3d(a, b))
        rows.append({
            "公司名称": str(e.field(e.field(e.field(line, "m_depot"), "m_owner"), "m_name") or ""),
            "运输制式": e.line_mode(line),
            "线路号": int(e.field(line, "m_number") or 0),
            "站点数": len(stops),
            "原始有效道路里程_km": round(raw / 1024000, 6),
            "游戏显示折算里程_km": round(converted / 1024000, 6),
            "站点直线闭环里程_km": round(sum(euclidean) / 1024000, 6),
            "平均站间直线距离_m": round(sum(euclidean) / len(euclidean) / 1024, 3) if euclidean else 0,
            "最大站间直线距离_m": round(max(euclidean) / 1024, 3) if euclidean else 0,
            "站点m_types可读": any(e.field(e.field(s, "m_stop"), "m_types") is not None for s in stops),
        })
        line = e.field(line, "m_nextLine")
    out = PROJECT / "exports" / "CIM2_站点覆盖半径与里程口径审计.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("线路", len(rows), "输出", out)


if __name__ == "__main__":
    main()
