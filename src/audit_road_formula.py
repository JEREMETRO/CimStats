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


def invoke_method(obj, name, args=()):
    method = next((m for m in obj.GetType().GetMethods(e.FLAGS) if m.Name == name), None)
    return method.Invoke(obj, list(args)) if method is not None else None


def road_formula(path, index):
    seg = path[index]
    road = e.field(seg, "m_road")
    if road is None:
        return 0, 0, "no-road"
    road_type = e.field(road, "m_type")
    road_length = int(e.field(road, "m_length") or 0)
    express = bool(e.field(road_type, "m_expressWay")) if road_type is not None else False
    value = road_length // 2 if express else road_length
    detail = "express-half" if express else "full-road"
    # IL branches directly to return after the expressway half-length path;
    # express segments receive no junction surcharge.
    if express:
        return value, value, detail
    if index + 1 >= len(path):
        return value, value, detail
    # The game tests the current path segment's direction mask when choosing
    # the junction endpoint, after merely checking that a following segment
    # exists.
    type_mask = invoke_method(seg, "get_TypeMask")
    static_flags = (e.System.Reflection.BindingFlags.Static |
                    e.System.Reflection.BindingFlags.Public |
                    e.System.Reflection.BindingFlags.NonPublic)
    forward_field = path[index].GetType().GetField("Forward", static_flags)
    forward = forward_field.GetValue(None) if forward_field is not None else None
    is_forward = bool(type_mask & forward) if forward is not None else False
    junction = e.field(road, "m_endJunction" if is_forward else "m_startJunction")
    roads = e.array_values(e.field(junction, "m_roads")) if junction is not None else []
    if not roads:
        return value, value, detail + ";no-junction"
    lights = e.field(junction, "m_trafficLights")
    if len(roads) <= 2:
        penalty = 0x2800
        rule = "roads<=2"
    # pythonnet exposes a null reference field as numeric zero for this
    # value-type-backed probe, so truthiness matches the IL brfalse here.
    elif lights:
        penalty = len(roads) * 0x23 << 10
        rule = "traffic-lights"
    else:
        penalty = len(roads) * 0x14 << 10
        rule = "roads>2"
    return value + penalty, value + penalty, detail + ";" + rule + f";forward={is_forward};roads={len(roads)}"


def main():
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
        number = int(e.field(line, "m_number") or 0)
        manual_total = 0
        direct_total = 0
        endpoint_total = 0
        segments = 0
        debug = number in {310, 326, 901}
        for line_stop in e.array_values(e.field(line, "m_stops")):
            path = e.array_values(e.field(line_stop, "m_path"))
            if path:
                # Construct a correctly typed array for the serialized path.
                typed = e.System.Array.CreateInstance(path[0].GetType(), len(path))
                for j, item in enumerate(path):
                    typed.SetValue(item, j)
                direct = 0
                for j in range(len(path)):
                    direct += int(invoke_method(line, "GetRoadLength", (typed, e.System.Int32(j))) or 0)
                manual = 0
                for j in range(len(path)):
                    value, road_value, _ = road_formula(path, j)
                    direct_seg = int(invoke_method(line, "GetRoadLength", (typed, e.System.Int32(j))) or 0)
                    if debug and direct_seg != value:
                        print("mismatch", number, j, "direct", direct_seg, "manual", value, "detail", road_formula(path, j)[2])
                    manual += value
                    segments += 1
                manual_total += manual
                direct_total += direct
        # CalculateSegmentLength is direct ground truth for this serialized line.
        calc = sum(int(invoke_method(line, "CalculateSegmentLength", (e.System.Int32(i),)) or 0) for i in range(len(e.array_values(e.field(line, "m_stops")))))
        endpoint_total = calc - direct_total
        rows.append({"线路号": number, "GetRoadLength总和": direct_total, "手工道路公式总和": manual_total, "端点直线距离": endpoint_total, "手工公式+端点": manual_total + endpoint_total, "CalculateSegmentLength": calc, "道路公式差异": manual_total - direct_total, "总公式差异": manual_total + endpoint_total - calc, "分段数": segments})
        line = e.field(line, "m_nextLine")
    out = PROJECT / "exports" / "CIM2_道路公式逐段审计.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print("线路", len(rows), "最大道路公式差异", max(abs(r["道路公式差异"]) for r in rows), "最大总公式差异", max(abs(r["总公式差异"]) for r in rows))
    print("输出", out)


if __name__ == "__main__":
    main()
