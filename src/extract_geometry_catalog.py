from __future__ import annotations

import csv
import glob
import os
from pathlib import Path

import UnityPy

PROJECT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = Path(os.environ.get("CIM2_BUNDLE_ROOT", "")) or (PROJECT / "data" / "Bundles")
TRANSIT_PREFIXES = ("bus-", "tram-", "trolley-", "metro-", "monorail-", "waterbus-")


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def vehicle_rows() -> list[dict]:
    result = {}
    for filename in glob.glob(str(BUNDLE_ROOT / "**" / "*.bundle"), recursive=True):
        try: env = UnityPy.load(filename)
        except Exception: continue
        objects = {o.path_id: o for o in env.objects}
        for obj in env.objects:
            try:
                data = obj.read(); values = getattr(data, "__dict__", {})
                ident = str(values.get("m_id", ""))
                if "m_maxSpeed" not in values or not ident.startswith(TRANSIT_PREFIXES): continue
                generated = values.get("m_generatedInfo")
                generated_obj = objects.get(getattr(generated, "path_id", None))
                dimensions = getattr(generated_obj.read(), "__dict__", {}) if generated_obj else {}
                result.setdefault(ident, {
                    "车型ID": ident, "来源包": os.path.basename(filename),
                    "尺寸单位": "固定点/1024 = 米",
                    "长度_m": round(int(dimensions.get("m_length", 0)) / 1024, 3),
                    "宽度_m": round(int(dimensions.get("m_width", 0)) / 1024, 3),
                    "高度_m": round(int(dimensions.get("m_height", 0)) / 1024, 3),
                    "最大速度_raw": int(values.get("m_maxSpeed", 0) or 0),
                    "加速度_raw": int(values.get("m_acceleration", 0) or 0),
                    "制动_raw": int(values.get("m_braking", 0) or 0),
                    "转向_raw": int(values.get("m_turning", 0) or 0),
                    "容量": int(values.get("m_capacity", 0) or 0),
                    "尺寸等级": int(values.get("m_sizeClass", 0) or 0),
                    "维护需求": int(values.get("m_maintenanceRequirement", 0) or 0),
                    "燃料消耗": int(values.get("m_fuelConsumption", 0) or 0),
                    "电力消耗": int(values.get("m_electricityConsumption", 0) or 0),
                    "质量": int(values.get("m_quality", 0) or 0),
                })
            except Exception:
                continue
    return sorted(result.values(), key=lambda row: row["车型ID"])


def road_rows() -> list[dict]:
    path = BUNDLE_ROOT / "Game" / "Roads.bundle"
    env = UnityPy.load(str(path)); rows = []
    for obj in env.objects:
        try: values = getattr(obj.read(), "__dict__", {})
        except Exception: continue
        infos = values.get("m_roadTypeInfo")
        if not infos: continue
        for info in infos:
            x = getattr(info, "__dict__", {})
            get = lambda name, default=0: x.get(name, getattr(info, name, default))
            road_type = get("m_type", None)
            rt = lambda name, default=0: getattr(road_type, name, default) if road_type is not None else default
            rows.append({
                "道路类型": str(get("m_name", "")), "道路枚举": str(getattr(road_type, "m_type", "")),
                "车道A": int(rt("m_laneCountA", 0) or 0), "车道B": int(rt("m_laneCountB", 0) or 0),
                "左侧人行道_m": round(int(rt("m_sidewalkWidthL", 0) or 0) / 1024, 3),
                "右侧人行道_m": round(int(rt("m_sidewalkWidthR", 0) or 0) / 1024, 3),
                "站台宽度_m": round(int(rt("m_platformWidth", 0) or 0) / 1024, 3),
                "公交专用道": bool(rt("m_busLane", False)), "停车道": bool(rt("m_parkingLane", False)),
                "路肩": bool(rt("m_shoulder", False)), "人行街": bool(rt("m_pedestrianStreet", False)),
                "高速路": bool(rt("m_expressWay", False)), "最大车道数": int(get("m_maxLaneCount", 0) or 0),
                "尺寸单位": "固定点/1024 = 米",
            })
    return rows


def main() -> None:
    vehicles = vehicle_rows(); roads = road_rows()
    write_csv(PROJECT / "exports" / "CIM2_车型尺寸速度目录.csv", vehicles)
    write_csv(PROJECT / "exports" / "CIM2_道路类型宽度目录.csv", roads)
    print("车型", len(vehicles), "道路类型", len(roads))


if __name__ == "__main__": main()
