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


def text_ticks(value):
    return e.datetime_text(value) if value is not None else ""


def time_of_day_ticks(value):
    """Timetable departures are offsets from midnight, not DateTime ticks."""
    return e.duration_text(value) if value is not None else ""


def minimum_ticks(values):
    values = [int(v) for v in values if v is not None and int(v) > 0]
    return min(values) if values else 0


def main() -> None:
    root, _ = e.load_root()
    transport = e.field(root, "m_transportManagerData")
    line = e.field(transport, "m_firstLine")
    rows = []
    seen = set()
    while line is not None:
        oid = int(e.field(line, "m_objectID") or 0)
        if oid in seen:
            break
        seen.add(oid)
        stops = e.array_values(e.field(line, "m_stops"))
        stop_builds = []
        for line_stop in stops:
            stop = e.field(line_stop, "m_stop")
            if stop is not None:
                stop_builds.append(e.field(stop, "m_buildTime"))
        vehicle_purchases = []
        for line_vehicle in e.array_values(e.field(line, "m_vehicles")):
            depot_vehicle = e.field(line_vehicle, "m_depotVehicle")
            if depot_vehicle is not None:
                vehicle_purchases.append(e.field(depot_vehicle, "m_purchaseTime"))
        timetables = e.array_values(e.field(line, "m_timeTables"))
        first_departures = []
        for timetable in timetables:
            for row in e.array_values(e.field(timetable, "m_rows")):
                first_departures.append(e.field(row, "m_departure"))
        build = int(e.field(line, "m_buildTime") or 0)
        stop_min = minimum_ticks(stop_builds)
        purchase_min = minimum_ticks(vehicle_purchases)
        departure_min = minimum_ticks(first_departures)
        rows.append({
            "线路号": int(e.field(line, "m_number") or 0),
            "对象ID": oid,
            "线路开线日期_m_buildTime": text_ticks(build),
            "线路开线日期_tick": build,
            "最近改线日期_m_lineEditTime": text_ticks(e.field(line, "m_lineEditTime")),
            "最早站点建造日期": text_ticks(stop_min),
            "最早车辆购买日期": text_ticks(purchase_min),
            "最早发班记录": time_of_day_ticks(departure_min),
            "开线字段存在": "是" if build > 0 else "否",
            "站点早于线路": "是" if stop_min and build and stop_min < build else "否",
            "开线字段来源": "LineData -> ObjectData.m_buildTime",
        })
        line = e.field(line, "m_nextLine")

    out = PROJECT / "exports" / f"CIM2_开线日期来源审计_{SAVE.stem}_运行时.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("线路", len(rows), "字段缺失", sum(r["开线字段存在"] == "否" for r in rows),
          "站点早于线路", sum(r["站点早于线路"] == "是" for r in rows))
    print("输出", out)


if __name__ == "__main__":
    main()
