"""Normalized data model shared by the desktop UI and report checks.

The parser emits fixed-point CSV values.  This module owns display conversions
and composite-key joins so the UI never needs to duplicate workbook logic.
"""
from __future__ import annotations

import csv
import math
from datetime import datetime
from pathlib import Path

LINE_LENGTH_SCALE = 1_024_000
LINE_MONEY_SCALE = 102_400
MAP_LENGTH_MULTIPLIER = 2.0

COMPANY_NAMES = {
    "826272703's Company": "六进公交",
    "jeremylin2005's Company": "八连交通集团",
}
from display_rules import MODE_NAMES, display_mode, format_line_name, format_garage
from line_schedule import WEEKDAY_MASK, optional_integer, prepare_schedule, running_day_mask, weekly_vehicle_average
MODES = ["公交", "单轨列车", "地铁", "无轨电车", "有轨电车", "水上巴士"]
DAY_GROUPS = ("周一至周四", "周五", "周六", "周日")
DAY_BITS = (("周一", 2), ("周二", 4), ("周三", 8), ("周四", 16),
            ("周五", 32), ("周六", 64), ("周日", 1))
VEHICLE_DISPLAY = {
    0: ("任", "任意", "#2F80ED"),
    1: ("小", "小型", "#27AE60"),
    2: ("中", "中型", "#F2C94C"),
    3: ("大", "大型", "#EB5757"),
}


def number(value, default=0.0):
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def integer(value, default=0):
    try:
        return int(float(value or default))
    except (TypeError, ValueError, OverflowError):
        return default


def _measurement_available(value, *, whole=False):
    """Track missing/invalid physical fields without changing numeric consumers."""
    if value is None or str(value).strip() == '':
        return False
    if whole:
        parsed = optional_integer(value)
        return parsed is not None and parsed >= 0
    try:
        parsed = float(value)
        return math.isfinite(parsed) and parsed >= 0
    except (TypeError, ValueError, OverflowError):
        return False


def display_company(value: str) -> str:
    return COMPANY_NAMES.get(value, value or "未命名公司")


def parse_datetime(value: str) -> datetime | None:
    value = (value or "").strip()
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def clock_minutes(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if ":" in value:
        clock = value.split()[-1]
        parts = clock.split(":")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    return value


def display_date(value: str) -> str:
    parsed = parse_datetime(value)
    return parsed.strftime("%Y-%m-%d %H:%M") if parsed else ""


def duration_minutes(row: dict[str, str], field_name: str = "单程时间") -> float:
    ticks = integer(row.get(f"{field_name}_tick", "0"))
    if ticks:
        return ticks / 10_000_000 / 60
    value = row.get(field_name, "")
    parts = value.split(":")
    if len(parts) == 3:
        return integer(parts[0]) * 60 + integer(parts[1]) + integer(parts[2]) / 60
    return number(value)


def line_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("公司标识") or row.get("玩家ID") or row.get("公司序号", ""),
            row.get("线路类型", ""), row.get("线路号", ""))


def public_key(row: dict) -> str:
    return "|".join((row.get("公司标识") or row.get("玩家ID") or row.get("公司序号") or row.get("公司名称", ""), display_mode(row.get("线路类型", "")), str(row.get("线路号", ""))))


def current_day_bit(value: datetime) -> int:
    return 1 << ((value.weekday() + 1) % 7)


def date_groups(mask: int) -> list[str]:
    groups = []
    if mask & 30 == 30:
        groups.append("周一至周四")
    else:
        groups.extend(day for day, bit in DAY_BITS[:4] if mask & bit)
    if mask & 32:
        groups.append("周五")
    if mask & 64:
        groups.append("周六")
    if mask & 1:
        groups.append("周日")
    return groups or ["未启用"]


def read_csv(export_dir: Path, stem: str, tag: str) -> list[dict[str, str]]:
    path = export_dir / f"{stem}_{tag}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _line_metrics(row, departures, day_bit, map_km):
    day_departures = [x for x in departures if integer(x.get("运行日掩码", x.get("时刻表_运行日掩码"))) & day_bit]
    count = len(day_departures)
    passenger = integer(row.get("客流_今日"))
    duration = duration_minutes(row)
    vehicle_km = count * map_km
    return {
        "当日发班数": count,
        "行车总时间": round(count * duration, 2),
        "行车总里程": round(vehicle_km, 6),
        "今日平均单班人次": round(passenger / count, 2) if count else 0,
        "今日平均车公里人次": round(passenger / vehicle_km, 2) if vehicle_km else 0,
    }


def _schedule_groups(departures):
    """Collapse Monday–Thursday only when the complete departures match."""
    daily = {day: [] for day, _ in DAY_BITS}
    unknown, disabled = [], []
    for dep in departures:
        mask = running_day_mask(dep.get("运行日掩码"))
        size = optional_integer(dep.get("首选车型"))
        code, vehicle_type, color = VEHICLE_DISPLAY.get(size, ("?", "未知", "#94A3B8"))
        entry = {**dep, "time": dep.get("发班时间", ""), "vehicle_code": code,
                 "vehicle_type": vehicle_type, "color": color,
                 "running_day_valid": mask is not None,
                 "运行日状态": "未知" if mask is None else "未启用" if not mask & WEEKDAY_MASK else "已确认"}
        if mask is None:
            entry["diagnostic"] = ("运行日掩码缺失或无效，无法确定星期；"
                                   f"时刻表{dep.get('时刻表序号') or '未知'}，发班{dep.get('发班序号') or '未知'}。")
            unknown.append(entry)
            continue
        if not mask & WEEKDAY_MASK:
            disabled.append(entry)
            continue
        for day, bit in DAY_BITS:
            if mask & bit:
                daily[day].append(entry)
    weekdays = [day for day, _ in DAY_BITS[:4]]
    common = all(daily[day] == daily[weekdays[0]] for day in weekdays[1:])
    day_groups = list(DAY_GROUPS) if common else [day for day, _ in DAY_BITS]
    # Keep old four keys for older consumers; a divergent weekday union must
    # never be presented as one day's schedule.
    groups = {group: [] for group in DAY_GROUPS}
    if common:
        groups[DAY_GROUPS[0]] = daily[weekdays[0]]
    for day in day_groups:
        if day in daily:
            groups[day] = daily[day]
    for label, entries in (("未启用", disabled), ("运行日未知", unknown)):
        if entries:
            day_groups.append(label)
            groups[label] = entries
    schedules = {day: prepare_schedule(entries) for day, entries in groups.items()}
    groups = {day: schedule["entries"] for day, schedule in schedules.items()}
    return day_groups, groups, schedules


def _vehicle_average(row, departures):
    cached = optional_integer(row.get("平均车辆需求数_缓存_fixed"))
    masks = [running_day_mask(dep.get("运行日掩码")) for dep in departures]
    unknown = sum(mask is None for mask in masks)
    active = any(mask & WEEKDAY_MASK for mask in masks if mask is not None)
    if cached is not None and (cached > 0 or cached == 0 and not unknown and not active):
        note = "游戏原字段m_vehiclesNeededAvg÷1024；按7天×288个五分钟槽计算的周平均所需车辆，固定点缩放。"
        if unknown:
            note += f"另有{unknown}班运行日未知，保留原字段值，不能用这些记录独立复算。"
        return cached / 1024, note
    if unknown:
        return None, f"周平均车辆需求：{unknown}班运行日未知，不能确定7天分配，无法复算；缺失或零缓存不作为真实零值，显示—。"
    ticks = optional_integer(row.get("单程时间_tick"))
    if ticks is None or ticks <= 0:
        minutes = duration_minutes(row)
        ticks = round(minutes * 60 * 10_000_000) if minutes > 0 else None
    value = weekly_vehicle_average(departures, ticks)
    note = "平均车辆需求数为周平均：缓存缺失或无效，按真实7天运行日班次及单程时间，复用游戏7×288个五分钟槽算法；槽位总数左移10位后整除2016，再÷1024。"
    if value is None:
        note += "运行日、发班时间或单程时间不足，显示—。"
    return value, note


def load_session(export_dir: Path, tag: str, catalog_dir: Path | None = None) -> dict:
    """Load one parser job directory into JSON-safe dictionaries."""
    export_dir = Path(export_dir)
    company_rows = read_csv(export_dir, "CIM2_公司信息", tag)
    type_rows = read_csv(export_dir, "CIM2_公司车型数据", tag)
    lines_raw = read_csv(export_dir, "CIM2_线路客流_完整导出", tag)
    timetable_rows = read_csv(export_dir, "CIM2_发班信息_完整导出", tag)
    departure_rows = read_csv(export_dir, "CIM2_发班记录_完整导出", tag)
    stop_rows = read_csv(export_dir, "CIM2_线路站点客流分布_当前", tag)
    vehicle_rows = read_csv(export_dir, "CIM2_配车信息_完整导出", tag)
    history_rows = read_csv(export_dir, "CIM2_城市历史指标_完整", tag)
    if not history_rows:  # Older jobs exported only the core subset.
        history_rows = read_csv(export_dir, "CIM2_城市历史核心指标", tag)
    metadata_rows = read_csv(export_dir, "CIM2_城市历史元数据", tag)
    metadata = metadata_rows[0] if metadata_rows else {}
    current = parse_datetime(metadata.get("模拟当前时间", "")) or datetime.now()
    start = parse_datetime(metadata.get("模拟开始", "")) or current
    day_bit = current_day_bit(current)

    # Normalize ownership before any joins. Display aliases are never identity keys.
    identities_by_id, identities_by_index, identities_by_name = {}, {}, {}
    def register(mapping, key, identity):
        if key is not None and str(key) != "":
            mapping.setdefault(str(key), set()).add(identity)

    company_rows = [dict(raw) for raw in company_rows]
    for index, raw in enumerate(company_rows):
        identity = str(raw.get("公司标识") or raw.get("玩家ID") or
                       f"player-index:{raw.get('公司序号', index)}")
        raw["公司标识"] = identity
        raw["原始公司名称"] = raw.get("公司名称", "")
        register(identities_by_id, identity, identity)
        register(identities_by_id, raw.get("玩家ID"), identity)
        register(identities_by_index, raw.get("公司序号", index), identity)
        register(identities_by_name, raw.get("公司名称"), identity)

    def unique(mapping, key):
        matches = mapping.get(str(key), set())
        return next(iter(matches)) if len(matches) == 1 else None

    def normalize(rows, source):
        normalized = []
        for index, raw in enumerate(rows):
            raw = dict(raw)
            name = raw.get("公司名称", "")
            explicit = raw.get("公司标识") or raw.get("玩家ID")
            if explicit:
                identity = unique(identities_by_id, explicit) or str(explicit)
            elif raw.get("公司序号") not in (None, ""):
                identity = (unique(identities_by_index, raw["公司序号"]) or
                            f"unresolved:{source}:{index}")
            elif name:
                identity = unique(identities_by_name, name) or f"unresolved:{source}:{index}"
            else:
                identity = ""  # City observations have no owner.
            raw["公司标识"] = identity
            raw["原始公司名称"] = name
            normalized.append(raw)
        return normalized

    type_rows = normalize(type_rows, "types")
    lines_raw = normalize(lines_raw, "lines")
    timetable_rows = normalize(timetable_rows, "timetables")
    departure_rows = normalize(departure_rows, "departures")
    stop_rows = normalize(stop_rows, "stops")
    vehicle_rows = normalize(vehicle_rows, "vehicles")
    history_rows = normalize(history_rows, "history")

    timetable_by_key = {}
    for row in timetable_rows:
        timetable_by_key[line_key(row) + (row.get("时刻表序号", ""),)] = row
    departures_by_line: dict[tuple[str, str, str], list[dict]] = {}
    for raw in departure_rows:
        key = line_key(raw)
        joined = dict(raw)
        timetable = timetable_by_key.get(key + (raw.get("时刻表序号", ""),), {})
        joined["运行日掩码"] = running_day_mask(timetable.get("运行日掩码")) if timetable else running_day_mask(raw.get("时刻表_运行日掩码"))
        joined["首选车型"] = optional_integer(timetable.get("首选车型")) if timetable else optional_integer(raw.get("时刻表_首选车型"))
        joined["时刻表原始字段"] = dict(timetable)
        departures_by_line.setdefault(key, []).append(joined)
    for values in departures_by_line.values():
        values.sort(key=lambda x: (x.get("发班时间", ""), integer(x.get("发班_tick"))))

    stops_by_line: dict[tuple[str, str, str], list[dict]] = {}
    for raw in stop_rows:
        stops_by_line.setdefault(line_key(raw), []).append(raw)
    vehicles_by_line: dict[tuple[str, str, str], list[dict]] = {}
    for raw in vehicle_rows:
        vehicles_by_line.setdefault(line_key(raw), []).append(raw)
    lines = []
    for raw in lines_raw:
        key = line_key(raw)
        map_km = number(raw.get("地图里程")) / LINE_LENGTH_SCALE * MAP_LENGTH_MULTIPLIER
        converted_km = number(raw.get("折算里程", raw.get("线路长度"))) / LINE_LENGTH_SCALE
        duration = duration_minutes(raw)
        deps = departures_by_line.get(key, [])
        metrics = _line_metrics(raw, deps, day_bit, map_km)
        day_groups, groups, schedules = _schedule_groups(deps)
        today_schedule = prepare_schedule([dep for dep in deps if integer(dep.get("运行日掩码")) & day_bit])
        unknown_departures = groups.get("运行日未知", [])
        today_note = f"模拟当日{current:%Y-%m-%d}，按当天运行日掩码对应的真实班次计算；" + today_schedule["average_interval_tooltip"]
        if unknown_departures:
            today_schedule["average_interval_text"] = "—"
            today_note += f"另有{len(unknown_departures)}班运行日未知，无法确认是否属于模拟当日，数据不足，平均间隔显示—。"
        vehicle_average, vehicle_average_note = _vehicle_average(raw, deps)
        opened = parse_datetime(raw.get("开线日期", ""))
        edited = parse_datetime(raw.get("最近改线日期", ""))
        company_name = display_company(raw.get("公司名称", ""))
        mode_name = display_mode(raw.get("线路类型", ""))
        line_number = integer(raw.get("线路号"))
        line = {
            "key": public_key(raw), "公司名称": company_name,
            "公司标识": raw["公司标识"], "原始公司名称": raw["原始公司名称"],
            "运输制式": mode_name, "线路号": line_number,
            "线路名称": format_line_name(line_number, raw.get("线路名称", "")),
            "开线日期": opened.strftime("%Y-%m-%d %H:%M") if opened else "",
            "最近改线日期": edited.strftime("%Y-%m-%d %H:%M") if edited else "",
            "线路车库": format_garage(company_name, mode_name, raw.get("线路车库名称") or raw.get("线路车库", "")),
            "单程时间": round(duration, 2) if duration else "",
            "地图里程": round(map_km, 6), "折算里程": round(converted_km, 6),
            "核定速度": round(map_km / duration * 60, 2) if duration else "", "站点数": integer(raw.get("站点数")),
            "理论最大车辆需求数": integer(raw.get("最大配车数")), "累计客流": integer(raw.get("客流_累计")),
            "今日客流": integer(raw.get("客流_今日")), "当前配车数": integer(raw.get("配车数")),
            "每周收入": round(integer(raw.get("收入_累计")) / LINE_MONEY_SCALE, 2),
            "每周支出": round(integer(raw.get("支出_累计")) / LINE_MONEY_SCALE, 2),
            "平均客流": round(integer(raw.get("客流_累计")) / max((current - (opened or start)).total_seconds() / 86400, 1), 2),
            **metrics,
            "平均间隔": today_schedule["average_interval_text"],
            "平均间隔Tooltip": today_note,
            "平均车辆需求数": vehicle_average, "平均车辆需求数Tooltip": vehicle_average_note,
            "原始字段": dict(raw), "日组": day_groups, "时刻表": schedules,
            "字段可用性": {
                "地图里程": _measurement_available(raw.get("地图里程")),
                "折算里程": _measurement_available(raw.get("折算里程", raw.get("线路长度"))),
                "站点数": _measurement_available(raw.get("站点数"), whole=True),
            },
            "运行日未知班次": unknown_departures,
            "班次数据完整": not unknown_departures and all(schedule["data_complete"] for schedule in schedules.values()),
            "班次诊断": list(dict.fromkeys(note for schedule in schedules.values() for note in schedule["diagnostics"])),
            "已确认当日发班数": metrics["当日发班数"],
            "当日发班数Tooltip": (f"按已确认运行日统计的模拟当日班次数；另有{len(unknown_departures)}班运行日未知，不能推定其所属星期。"
                                   if unknown_departures else "模拟当日完整运行日班次计数。"),
            "日组发班数量": {day: len(groups[day]) for day in day_groups},
            "周一至周四发班数量": len(groups["周一至周四"]), "周五发班数量": len(groups["周五"]),
            "周六发班数量": len(groups["周六"]), "周日发班数量": len(groups["周日"]),
            "班次": groups,
            "站点客流": [{"站点序号": integer(x.get("站点序号")), "站点名称": x.get("站点名称", ""), "今日客流": integer(x.get("站点客流_今日")), "候车人数": integer(x.get("线路当前候车人数"))} for x in stops_by_line.get(key, [])],
            "车辆": [{"车辆编号": integer(x.get("车辆编号")), "车辆名称": x.get("车辆名称", ""), "今日客流": integer(x.get("车辆客流_今日")), "累计客流": integer(x.get("车辆客流_累计")), "下次发车": clock_minutes(x.get("下次发车", ""))} for x in vehicles_by_line.get(key, [])],
        }
        lines.append(line)

    companies = []
    line_by_company = {}
    for line in lines:
        line_by_company.setdefault(line["公司标识"], []).append(line)
    def summarize_line_rows(rows):
        """Aggregate the line-level operating metrics used by the overview."""
        passenger = sum(number(x.get("今日客流")) for x in rows)
        departures = sum(number(x.get("当日发班数")) for x in rows)
        total_minutes = sum(number(x.get("行车总时间")) for x in rows)
        max_demand = sum(number(x.get("理论最大车辆需求数")) for x in rows)
        fleet = sum(number(x.get("当前配车数")) for x in rows)
        mileage = sum(number(x.get("地图里程")) for x in rows)
        return {
            "线路数": len(rows), "当日总客流": int(passenger), "当日发班数": int(departures),
            "行车总时间": round(total_minutes, 2), "理论最大车辆需求数": int(max_demand),
            "当前配车数": int(fleet), "地图里程": round(mileage, 3),
            "车辆周转率": round(departures / fleet, 2) if fleet else 0,
            "平均单班人次": round(passenger / departures, 2) if departures else 0,
            "平均车公里人次": round(passenger / sum(number(x.get("当日发班数")) * number(x.get("地图里程")) for x in rows), 2) if sum(number(x.get("当日发班数")) * number(x.get("地图里程")) for x in rows) else 0,
        }

    for company_index, raw in enumerate(company_rows):
        name = display_company(raw.get("公司名称", ""))
        company_lines = line_by_company.get(raw["公司标识"], [])
        company = {
            "公司名称": name, "公司标识": raw["公司标识"],
            "原始公司名称": raw["原始公司名称"],
            "公司序号": integer(raw.get("公司序号"), company_index),
            "资金": round(number(raw.get("资金")) / 100, 2),
            "公司价值": round(number(raw.get("公司价值")) / 100, 2),
            "基础设施价值": round(number(raw.get("基础设施价值")) / 100, 2),
            "车辆价值": round(number(raw.get("车辆价值")) / 100, 2),
            "业务价值": round(number(raw.get("业务价值")) / 100, 2),
            "声誉": round(number(raw.get("声誉")) / 10000, 4),
            "车辆总数": integer(raw.get("车辆总数")),
            "车队": {mode: integer(raw.get(f"车辆总数_{mode}")) for mode in MODES},
            "线路数": len(company_lines), "总客流": sum(x["今日客流"] for x in company_lines),
            "待付运营支出": round(number(raw.get("待付运营支出")) / 100, 2),
            "待付杂项支出": round(number(raw.get("待付杂项支出")) / 100, 2),
            "司机工资": round(number(raw.get("司机工资")) / 100, 2),
            "维护工资": round(number(raw.get("维护工资")) / 100, 2),
            "检查员工资": round(number(raw.get("检查员工资")) / 100, 2),
            "检查员数量": integer(raw.get("检查员数量")),
            "拥挤度": round(number(raw.get("拥挤度")) / 100, 2),
            "逃票累计": integer(raw.get("逃票累计")),
            "双车行程客流": integer(raw.get("双车行程客流")),
            "线路概览": summarize_line_rows(company_lines),
        }
        companies.append(company)
    type_by_key = {(x["公司标识"], display_mode(x.get("车型类型", ""))): x for x in type_rows}
    for company in companies:
        company["制式"] = []
        for mode in MODES:
            raw = type_by_key.get((company["公司标识"], mode), {})
            mode_lines = [x for x in line_by_company.get(company["公司标识"], []) if x["运输制式"] == mode]
            company["制式"].append({
                "运输制式": mode, "每周收入": round(integer(raw.get("收入累计")) / 100, 2),
                "每周支出": round(integer(raw.get("支出累计")) / 100, 2),
                "能源支出": round(integer(raw.get("电力估算")) / 100, 2),
                "燃料支出": round(integer(raw.get("燃料估算")) / 100, 2),
                "维护支出": round(integer(raw.get("维护估算")) / 100, 2),
                "驾驶员支出": round(integer(raw.get("司机估算")) / 100, 2),
                "待付支出": round(integer(raw.get("待付支出")) / 100, 2),
                "维护需求": integer(raw.get("维护需求")), "电力消耗": integer(raw.get("电力消耗")),
                "燃料消耗": integer(raw.get("燃料消耗")), "司机需求": integer(raw.get("司机需求")),
                "单线票价": round(number(raw.get("单线票价")) / 100, 2),
                "一区票价": round(number(raw.get("一区票价")) / 100, 2),
                "二区票价": round(number(raw.get("二区票价")) / 100, 2),
                "全区票价": round(number(raw.get("全区票价")) / 100, 2),
                "运行车辆数": round(integer(raw.get("运行车辆数")) / 1024, 2),
                "线路统计": summarize_line_rows(mode_lines),
            })

        # A single, explicit total makes the finance and operations charts
        # useful even when the save has several transport modes.
        mode_rows = company["制式"]
        company["财务汇总"] = {
            "每周收入": round(sum(x["每周收入"] for x in mode_rows), 2),
            "每周支出": round(sum(x["每周支出"] for x in mode_rows), 2),
            "能源支出": round(sum(x["能源支出"] for x in mode_rows), 2),
            "燃料支出": round(sum(x["燃料支出"] for x in mode_rows), 2),
            "维护支出": round(sum(x["维护支出"] for x in mode_rows), 2),
            "驾驶员支出": round(sum(x["驾驶员支出"] for x in mode_rows), 2),
            "待付支出": round(sum(x["待付支出"] for x in mode_rows), 2),
        }

        # Shared chart payloads: the UI only chooses a scope and renders it.
        overview_by_scope = {"综合": company["线路概览"]}
        passenger_rankings = {"综合": []}
        departure_rankings = {"综合": []}
        for line in line_by_company.get(company["公司标识"], []):
            passenger_rankings["综合"].append({"label": f"{line['运输制式']}{line['线路号']}", "line_number": line["线路号"], "mode": line["运输制式"], "value": line.get("今日客流", 0)})
            departure_rankings["综合"].append({"label": f"{line['运输制式']}{line['线路号']}", "line_number": line["线路号"], "mode": line["运输制式"], "value": line.get("当日发班数", 0)})
        for mode in MODES:
            mode_lines = [x for x in line_by_company.get(company["公司标识"], []) if x["运输制式"] == mode]
            if not mode_lines:
                continue
            overview_by_scope[mode] = summarize_line_rows(mode_lines)
            passenger_rankings[mode] = [{"label": str(x["线路号"]), "line_number": x["线路号"], "mode": mode, "value": x.get("今日客流", 0)} for x in mode_lines]
            departure_rankings[mode] = [{"label": str(x["线路号"]), "line_number": x["线路号"], "mode": mode, "value": x.get("当日发班数", 0)} for x in mode_lines]
        for values in passenger_rankings.values():
            values.sort(key=lambda x: x["value"], reverse=True)
        for values in departure_rankings.values():
            values.sort(key=lambda x: x["value"], reverse=True)
        company["概览"] = overview_by_scope
        company["客流排行"] = passenger_rankings
        company["班次排行"] = departure_rankings
        company["非零制式"] = [mode for mode in MODES if mode in overview_by_scope]

    trends = []
    for raw in history_rows:
        trends.append({"时间": raw.get("模拟时间", ""), "指标": raw.get("指标", ""),
                       "分组": raw.get("分组", ""), "公司名称": display_company(raw.get("公司名称", "")) if raw.get("公司名称") else "",
                       "公司标识": raw.get("公司标识") or raw.get("玩家ID") or "",
                       "值": number(raw.get("值")), "分母": number(raw.get("分母")),
                       "值/分母": number(raw.get("值/分母"))})
    catalog = []
    catalog_dir = Path(catalog_dir) if catalog_dir else export_dir.parent
    catalog_path = catalog_dir / "CIM2_车型尺寸速度目录.csv"
    if catalog_path.exists():
        with catalog_path.open(encoding="utf-8-sig", newline="") as handle:
            catalog = list(csv.DictReader(handle))
    population = integer(metadata.get("当前人口数"))
    if not population:
        population = sum(integer(x.get("值")) for x in history_rows
                     if x.get("指标") == "population" and str(x.get("当前槽位", "")).lower() == "true")
    if not population:
        population = sum(integer(x.get("值")) for x in read_csv(export_dir, "CIM2_城市历史核心指标", tag)
                          if x.get("指标") == "population" and str(x.get("当前槽位", "")).lower() == "true")
    metadata_display = {
        "当前日期": current.strftime("%Y-%m-%d"), "当前时间": current.strftime("%H:%M:%S"),
        "模拟开始": start.strftime("%Y-%m-%d %H:%M:%S"), "当前人口数": population,
        # Do not substitute a multiplayer Steam quicksave filename for the
        # map name.  Empty means the save did not serialize a map label.
        "地图名称": metadata.get("地图名称", "") or metadata.get("场景名称", ""),
        "地图原始引用": metadata.get("地图原始引用", ""),
        "地图原始名称": metadata.get("地图原始名称", ""),
        "地图内部标识": metadata.get("地图内部标识", ""),
        "地图名称来源": metadata.get("地图名称来源", ""),
        "地图名称说明": metadata.get("地图名称说明", ""),
    }
    # The serialized vehicle-object count can represent only active/runtime
    # objects (for the reference quicksave it is 167), while the company
    # reports expose the complete fleet (322 + 283 = 605).  Public counts
    # must use the complete fleet so the manifest, status bar and overview
    # all share one consistent meaning.
    fleet_total = sum(integer(company.get("车辆总数")) for company in companies)
    return {
        "tag": tag, "save_type": "multiplayer" if len(companies) > 1 else "single",
        "metadata": metadata_display,
        "companies": companies, "lines": lines, "timetables": timetable_rows,
        "departures": departure_rows, "trends": trends, "history": history_rows,
        "simulation_time": current.strftime("%Y-%m-%d %H:%M:%S"),
        "vehicle_catalog": catalog,
        "counts": {"companies": len(companies), "lines": len(lines), "vehicles": fleet_total, "timetables": len(timetable_rows), "departures": len(departure_rows)},
    }
