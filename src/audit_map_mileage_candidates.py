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


def invoke(obj, name, args):
    method = next((m for m in obj.GetType().GetMethods(e.FLAGS) if m.Name == name), None)
    return int(method.Invoke(obj, list(args))) if method is not None else 0


def typed(path):
    if not path:
        return None
    value = e.System.Array.CreateInstance(path[0].GetType(), len(path))
    for index, item in enumerate(path):
        value.SetValue(item, index)
    return value


def main() -> None:
    root, _ = e.load_root()
    transport = e.field(root, "m_transportManagerData")
    line = e.field(transport, "m_firstLine")
    rows = []
    seen = set()
    while line is not None:
        object_id = int(e.field(line, "m_objectID") or 0)
        if object_id in seen:
            break
        seen.add(object_id)
        segment_all = segment_excl = road_all = road_excl = get_all = get_excl = 0
        for line_stop in e.array_values(e.field(line, "m_stops")):
            path = e.array_values(e.field(line_stop, "m_path"))
            path_typed = typed(path)
            for index, segment in enumerate(path):
                segment_length = int(e.field(segment, "m_length") or 0)
                segment_all += segment_length
                road = e.field(segment, "m_road")
                if road is not None:
                    road_length = int(e.field(road, "m_length") or 0)
                    road_all += road_length
                    if index < len(path) - 1:
                        road_excl += road_length
                if path_typed is not None:
                    get_value = invoke(line, "GetRoadLength", (path_typed, e.System.Int32(index)))
                    get_all += get_value
                    if index < len(path) - 1:
                        get_excl += get_value
            segment_excl += sum(int(e.field(item, "m_length") or 0) for item in path[:-1])
        stops = e.array_values(e.field(line, "m_stops"))
        converted = sum(invoke(line, "CalculateSegmentLength", (e.System.Int32(index),)) for index in range(len(stops)))
        rows.append({
            "公司名称": str(e.field(e.field(e.field(line, "m_depot"), "m_owner"), "m_name") or ""),
            "运输制式": e.line_mode(line),
            "线路号": int(e.field(line, "m_number") or 0),
            "缓存线路长度": int(e.field(line, "m_lineLength") or 0),
            "路径段m_length总和": segment_all,
            "路径段m_length非终端": segment_excl,
            "RoadData.m_length总和": road_all,
            "RoadData.m_length非终端": road_excl,
            "GetRoadLength总和": get_all,
            "GetRoadLength非终端": get_excl,
            "CalculateSegmentLength": converted,
            "站点数": len(stops),
        })
        line = e.field(line, "m_nextLine")
    out = PROJECT / "exports" / "CIM2_地图里程候选对照.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("线路", len(rows), "输出", out)
    for number in (151, 161, 201, 301, 327, 901):
        row = next(item for item in rows if item["线路号"] == number)
        print(number, {key: row[key] for key in row if key not in {"公司名称", "运输制式", "线路号"}})


if __name__ == "__main__":
    main()
