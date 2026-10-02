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


def refs(root):
    """Collect every object reference that can be reached by the save graph."""
    game = e.field(root, "m_gameState") or root
    manager = e.field(game, "m_objectManager")
    objects = e.field(manager, "m_objects") if manager is not None else None
    return objects


def metric(obj):
    return {
        "objectID": iv(e.field(obj, "m_objectID")),
        "number": iv(e.field(obj, "m_number")),
        "lineLength": iv(e.field(obj, "m_lineLength")),
        "duration": iv(e.field(obj, "m_estimatedDuration")),
        "neededTop": iv(e.field(obj, "m_vehiclesNeededTop")),
        "neededAvg": iv(e.field(obj, "m_vehiclesNeededAvg")),
        "stops": len(e.array_values(e.field(obj, "m_stops"))),
        "vehicles": len(e.array_values(e.field(obj, "m_vehicles"))),
    }


def main():
    root, _ = e.load_root()
    transport = e.field(root, "m_transportManagerData")
    manager_objects = refs(root)
    all_lines = []
    if manager_objects is not None:
        for pair in manager_objects:
            obj = pair.Value
            if obj is not None and obj.GetType().Name == "LineData":
                all_lines.append(("ObjectManager", iv(pair.Key), obj))
    line = e.field(transport, "m_firstLine")
    seen = set()
    while line is not None:
        oid = iv(e.field(line, "m_objectID"))
        if oid in seen:
            break
        seen.add(oid)
        all_lines.append(("TransportManager", oid, line))
        line = e.field(line, "m_nextLine")

    by_number = {}
    rows = []
    for source, key, obj in all_lines:
        n = iv(e.field(obj, "m_number"))
        by_number.setdefault(n, []).append((source, key, obj))
    for n in sorted(by_number):
        entries = by_number[n]
        for source, key, obj in entries:
            m = metric(obj)
            m.update({"线路号": n, "来源": source, "字典键或对象ID": key})
            rows.append(m)
        # Compare distinct instances for the same line number.
        if len(entries) > 1:
            print("DUPLICATE", n, [(source, key, metric(obj)) for source, key, obj in entries])

    out = PROJECT / "exports" / f"CIM2_线路对象来源审计_{SAVE.stem}_运行时.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print("对象中的 LineData", len(rows), "线路号", len(by_number), "重复线路号", sum(len(v) > 1 for v in by_number.values()))
    print("输出", out)


if __name__ == "__main__":
    main()
