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


def method(obj, name):
    return next((m for m in obj.GetType().GetMethods(e.FLAGS) if m.Name == name), None)


def typed_path(path):
    items = e.array_values(path)
    if not items:
        return items, None
    result = e.System.Array.CreateInstance(items[0].GetType(), len(items))
    for i, item in enumerate(items):
        result.SetValue(item, i)
    return items, result


def panel_distance(line, index, use_getroad):
    stops = e.array_values(e.field(line, "m_stops"))
    current = stops[index]
    following = stops[(index + 1) % len(stops)]
    path = e.field(current, "m_path")
    if path is None:
        a = e.field(e.field(current, "m_stop"), "m_position")
        b = e.field(e.field(following, "m_stop"), "m_position")
        return e.fixed_vector_length3d(a, b), "vector"
    items, typed = typed_path(path)
    total = 0
    get = method(line, "GetRoadLength")
    for j in range(max(0, len(items) - 1)):
        road = e.field(items[j], "m_road")
        if road is None:
            continue
        if use_getroad and get is not None:
            total += int(get.Invoke(line, [typed, e.System.Int32(j)]))
        else:
            total += int(e.field(road, "m_length") or 0)
    a = e.field(current, "m_stop")
    b = e.field(following, "m_stop")
    try:
        total += int(b.GetQuickPosition()) - int(a.GetQuickPosition())
    except Exception:
        pass
    return max(0, total), "getroad" if use_getroad else "raw-road"


def can_stop(stop):
    prefab = e.field(stop, "m_prefabObject")
    if prefab is not None:
        return e.field(prefab, "m_waypoint") is None
    return int(e.field(stop, "m_lineCount") or 0) > 0


def duration(line, mode, span, use_getroad):
    params = e.VEHICLE_TYPE_PARAMS.get(mode, (3300, 12))
    speed, stop_time = params
    stops = e.array_values(e.field(line, "m_stops"))
    total = 0
    for i in range(len(stops)):
        d, _ = panel_distance(line, i, use_getroad)
        total += ((d * 16) // speed) * span
        if i > 0 and can_stop(e.field(stops[i], "m_stop")):
            total += (stop_time * 60) * span
    five = 3_000_000_000
    if total > 0:
        total = max(6_000_000_000, ((total + five - 1) // five) * five)
    return total


def main():
    root, _ = e.load_root()
    start = e.field(root, "m_simulationStart")
    now = e.field(root, "m_simulationTime")
    frame = int(e.field(root, "m_simulationFrame") or 0)
    span = 350000
    try:
        span = max(1, int(round((now - start).Ticks / frame)))
    except Exception:
        pass
    transport = e.field(root, "m_transportManagerData")
    line = e.field(transport, "m_firstLine")
    seen = set(); rows = []
    while line is not None:
        oid = int(e.field(line, "m_objectID") or 0)
        if oid in seen:
            break
        seen.add(oid)
        number = int(e.field(line, "m_number") or 0)
        mode = e.line_mode(line)
        cached = int(e.field(line, "m_estimatedDuration") or 0)
        raw = duration(line, mode, span, False)
        getroad = duration(line, mode, span, True)
        rows.append({
            "线路号": number,
            "运输制式": mode,
            "缓存分钟": cached / 600_000_000,
            "面板原始道路分钟": raw / 600_000_000,
            "带GetRoadLength分钟": getroad / 600_000_000,
            "原始差分钟": (raw - cached) / 600_000_000,
            "GetRoad差分钟": (getroad - cached) / 600_000_000,
        })
        line = e.field(line, "m_nextLine")
    out = PROJECT / "exports" / "CIM2_预计时间距离分支审计.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print("span", span, "lines", len(rows), "raw exact", sum(abs(r["原始差分钟"]) < 1e-9 for r in rows), "getroad exact", sum(abs(r["GetRoad差分钟"]) < 1e-9 for r in rows))
    print(out)


if __name__ == "__main__":
    main()
