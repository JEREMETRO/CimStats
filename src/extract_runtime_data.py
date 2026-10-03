from __future__ import annotations

import csv
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from parse_events import ProgressReporter

import clr
import System
from System import AppDomain
from history_contract import coverage_live_total, owner_identity, slot_time, valid_slot_indices

PROJECT = Path(__file__).resolve().parents[1]
# Runtime dependencies stay in the project data directory, while each parse
# job may place its generated payload in an isolated working directory.
DATA = Path(os.environ.get("CIM2_RUNTIME_DATA_DIR", str(PROJECT / "data")))
PAYLOAD_DIR = Path(os.environ.get("CIM2_PAYLOAD_DIR", str(DATA)))
EXPORT = Path(os.environ.get("CIM2_EXPORT_DIR", str(PROJECT / "exports")))
DEFAULT_SAVE = DATA / "望春市6.save"
SAVE = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_SAVE
if not SAVE.is_absolute():
    SAVE = (PROJECT / SAVE).resolve()
if not SAVE.exists():
    raise FileNotFoundError(f"存档不存在: {SAVE}")
TAG = "运行时" if SAVE.stem == "望春市6" else f"{SAVE.stem}_运行时"
OUT = lambda stem: EXPORT / f"{stem}_{TAG}.csv"
_configured_managed = os.environ.get("CIM2_MANAGED_ROOT", "")
# Source checkouts without a bundled runtime set CIM2_MANAGED_ROOT; the desktop
# app always supplies it explicitly.  (An empty variable must not become
# Path("") == Path("."), which silently searched the working directory.)
MANAGED = Path(_configured_managed) if _configured_managed else PROJECT / "game_runtime" / "Managed"
PROBE = DATA / "Assembly-CSharp.probe.dll"
PAYLOAD = PAYLOAD_DIR / f"{SAVE.stem}.payload.bin"
SOURCE_ASSEMBLY = MANAGED / "Assembly-CSharp.dll"

if not SOURCE_ASSEMBLY.exists():
    if getattr(sys, "frozen", False):
        raise FileNotFoundError(f"安装包缺少内置 Assembly-CSharp.dll：{SOURCE_ASSEMBLY}")
    raise FileNotFoundError(f"未找到 Assembly-CSharp.dll：{SOURCE_ASSEMBLY}")
if not PROBE.exists():
    if getattr(sys, "frozen", False):
        raise FileNotFoundError(f"便携包缺少内置探针：{PROBE}")
    os.environ["CIM2_ASSEMBLY_SOURCE"] = str(SOURCE_ASSEMBLY)
    os.environ["CIM2_PROBE_OUTPUT"] = str(PROBE)
    subprocess.run([sys.executable, str(Path(__file__).with_name("patch_singleton_probe.py"))], check=True)
elif not getattr(sys, "frozen", False) and PROBE.stat().st_mtime < SOURCE_ASSEMBLY.stat().st_mtime:
    os.environ["CIM2_ASSEMBLY_SOURCE"] = str(SOURCE_ASSEMBLY)
    os.environ["CIM2_PROBE_OUTPUT"] = str(PROBE)
    subprocess.run([sys.executable, str(Path(__file__).with_name("patch_singleton_probe.py"))], check=True)


def prepare_payload():
    """Use the same validated container reader as the editing utilities."""
    from save_container import locate_payload
    location, payload = locate_payload(SAVE)
    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PAYLOAD.write_bytes(payload)
    return location.offset, location.payload_size


def resolve_assembly(_sender, args):
    name = args.Name.split(",")[0] + ".dll"
    path = MANAGED / name
    return System.Reflection.Assembly.LoadFile(str(path)) if path.exists() else None


AppDomain.CurrentDomain.AssemblyResolve += resolve_assembly
clr.AddReference(str(DATA / "UnityEngine.dll"))
clr.AddReference(str(PROBE))
ASM = System.Reflection.Assembly.LoadFile(str(PROBE))
FLAGS = (System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public |
         System.Reflection.BindingFlags.NonPublic)


def field(obj, name):
    if obj is None:
        return None
    f = obj.GetType().GetField(name, FLAGS)
    return f.GetValue(obj) if f is not None else None


def duration_text(ticks):
    if ticks is None:
        return ""
    # Game clock values are .NET ticks from midnight for timetable fields.
    seconds = int(ticks) // 10_000_000
    days, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    return f"{days}d {h:02d}:{m:02d}:{s:02d}" if days else f"{h:02d}:{m:02d}:{s:02d}"


def datetime_text(ticks):
    if ticks is None or int(ticks) <= 0:
        return ""
    try:
        value = dt.datetime(1, 1, 1) + dt.timedelta(microseconds=int(ticks) / 10)
        return value.strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, ValueError):
        return str(int(ticks))


def array_values(arr):
    return [] if arr is None else [arr[i] for i in range(arr.Length)]


def line_mode(line):
    # The probe returns a minimal VehicleTypeObject whose m_id is the exact
    # serialized type identifier requested by DataStoreManager.  In v1.6.3
    # these identifiers are strings (for example, "tram" and "bus"), not
    # energy/fuel categories.
    type_object = field(line, "m_type")
    type_id = str(field(type_object, "m_id") or "").strip().lower()
    from display_rules import MODE_NAMES
    return MODE_NAMES.get(type_id, f"未知类型({type_id})" if type_id else "未知类型")



# VehicleTypeDataStore values from the installed v1.6.3 GameShared bundle.
# These are the same values consumed by VehicleTypeObject.CalculateDuration.
VEHICLE_TYPE_PARAMS = {
    # Values read from GameShared.bundle VehicleTypeObject assets used by
    # VehicleTypeObject.CalculateDuration in v1.6.3.
    "公交": (3300, 12),
    "无轨电车": (3400, 8),
    "有轨电车": (3500, 8),
    "地铁": (8000, 15),
    "单轨列车": (8000, 15),
    "水上巴士": (5000, 30),
}


def path_length_from_vehicle_route(line):
    """Return the unconverted map-road length used by vehicles on a line.

    ``RoadPathSegment.m_length`` is a pathfinding segment value and includes
    the terminal stop connector.  The line panel excludes that final entry
    and reads the referenced ``RoadData.m_length`` for actual map distance.
    Keep the road length unconverted here; expressway and junction rules are
    applied separately by ``CalculateSegmentLength`` for displayed mileage.
    """
    total = 0
    for line_stop in array_values(field(line, "m_stops")):
        path = array_values(field(line_stop, "m_path"))
        for path_segment in path[:-1]:
            road = field(path_segment, "m_road")
            if road is not None:
                total += int(field(road, "m_length") or 0)
    return total


def map_length_from_vehicle_route(line):
    """Return the pre-conversion effective road length.

    This mirrors the first value used by ``LineData.GetRoadLength``: for each
    valid path element (all entries except the final station connector), read
    ``RoadPathSegment.m_road.m_length``.  Expressway halving, junction
    penalties, and endpoint offsets are applied only afterwards by
    ``CalculateSegmentLength`` and are therefore excluded here.
    """
    total = 0
    for line_stop in array_values(field(line, "m_stops")):
        path = array_values(field(line_stop, "m_path"))
        for segment in path[:-1]:
            road = field(segment, "m_road")
            if road is not None:
                total += int(field(road, "m_length") or 0)
    return total if total > 0 else path_length_from_vehicle_route(line)


def calculate_segment_length_sum(line):
    """Reproduce LineData.CalculateSegmentLength for every serialized stop."""
    stops = array_values(field(line, "m_stops"))
    calculator = next((m for m in line.GetType().GetMethods(FLAGS)
                       if m.Name == "CalculateSegmentLength"), None)
    if calculator is None:
        return 0
    try:
        return sum(int(calculator.Invoke(line, [System.Int32(index)]))
                   for index in range(len(stops)))
    except Exception:
        return 0


def fixed_vector_length3d(a, b):
    """Mirror FixedMath.VectorLength3D, including its fixed-point sqrt."""
    if a is None or b is None:
        return 0
    try:
        square = sum((int(field(b, axis)) - int(field(a, axis))) ** 2
                     for axis in ("x", "y", "z"))
    except Exception:
        return 0
    root = square >> 11
    if root <= 0:
        return 0
    # FixedMath.Sqrt performs twelve Newton iterations with integer division.
    for _ in range(12):
        root = (root + square // root + 1) >> 1
    return int(root)


def stop_position(stop_data):
    """Return PlacementData.m_position used by LinePanel.CalculateDuration."""
    return field(stop_data, "m_position") if stop_data is not None else None


def duration_segment_distance(line, stop_index):
    """Reproduce the distance argument passed to VehicleTypeObject.CalculateDuration.

    The serialized path branch is evaluated by the same LineData road-length
    conversion used by the game panel: each segment except the terminal one
    is passed through GetRoadLength, then the scalar
    IStopData.GetQuickPosition() difference is added.  This is important for
    expressways and junction corrections, which are not represented by a raw
    RoadData.m_length sum.  The no-path branch instead uses the
    PlacementData.m_position three-dimensional distance.
    """
    stops = array_values(field(line, "m_stops"))
    if not stops:
        return 0
    current = stops[stop_index]
    following = stops[(stop_index + 1) % len(stops)]
    path = field(current, "m_path")
    if path is not None:
        segments = array_values(path)
        # The terminal path segment is a station-to-road endpoint and is
        # excluded by the panel IL.  GetRoadLength includes the game's road
        # type and junction corrections; using raw m_length here understates
        # lines such as 201/901.
        get_road = next((m for m in line.GetType().GetMethods(FLAGS)
                         if m.Name == "GetRoadLength"), None)
        road_total = 0
        if get_road is not None and segments:
            try:
                road_total = sum(
                    int(get_road.Invoke(line, [path, System.Int32(i)]))
                    for i in range(max(0, len(segments) - 1))
                )
            except Exception:
                road_total = 0
        current_stop = field(current, "m_stop")
        following_stop = field(following, "m_stop")
        try:
            quick_delta = int(following_stop.GetQuickPosition()) - int(current_stop.GetQuickPosition())
        except Exception:
            quick_delta = 0
        return max(0, int(road_total + quick_delta))
    current_stop = field(current, "m_stop")
    following_stop = field(following, "m_stop")
    vector_distance = fixed_vector_length3d(
        stop_position(current_stop), stop_position(following_stop)
    )
    return max(0, int(vector_distance))


def timetable_needed_vehicles(line, duration):
    """Mirror LinePanel.CalculateNeededVehicles' 7-day, 5-minute buffer."""
    if duration <= 0:
        return 0
    slot_ticks = 3_000_000_000  # five in-game minutes
    buffer = [0] * 2016
    for day in range(7):
        for timetable in array_values(field(line, "m_timeTables")):
            active_days = int(field(timetable, "m_activeDays") or 0)
            if not (active_days & (1 << day)):
                continue
            for row in array_values(field(timetable, "m_rows")):
                departure = int(field(row, "m_departure") or 0)
                # SelectionPanel.CalculateNeededVehicles wraps both endpoints
                # into the seven-day buffer before walking start < end.
                start = (day * 288 + departure // slot_ticks) % 2016
                end = (day * 288 + (departure + duration) // slot_ticks) % 2016
                for slot in range(start, end):
                    buffer[slot] += 1
    return max(buffer) if buffer else 0


def can_stop_here_serialized(stop_data):
    """Reproduce StopData.CanStopHere when Unity prefab references are absent.

    v1.6.3 returns ``m_prefabObject.m_waypoint == null``.  A deserialized
    multiplayer save does not bind the prefab object, but every real stop on a
    LineData route has a positive m_lineCount; waypoint-only entries do not.
    """
    prefab = field(stop_data, "m_prefabObject")
    if prefab is not None:
        waypoint = field(prefab, "m_waypoint")
        return waypoint is None
    return int(field(stop_data, "m_lineCount") or 0) > 0


def derive_runtime_line_values(line, mode, frame_time_span):
    """Recover invalid line caches from the vehicle route and timetable data.

    Multiplayer saves can contain a zero/stale LineData cache for a line owned
    by another player.  The vehicle path remains serialized and is the source
    the in-game vehicle/line panel uses after recalculation.
    """
    cached_length = int(field(line, "m_lineLength") or 0)
    cached_duration = int(field(line, "m_estimatedDuration") or 0)
    cached_top = int(field(line, "m_vehiclesNeededTop") or 0)
    length = cached_length
    if length <= 0:
        length = calculate_segment_length_sum(line)
        if length <= 0:
            length = path_length_from_vehicle_route(line)

    duration = cached_duration
    speed, stop_time = VEHICLE_TYPE_PARAMS.get(mode, (3300, 12))
    if duration <= 0 or (cached_duration == 6_000_000_000 and cached_length <= 0):
        # LinePanel.CalculateDuration skips index 0 (the depot) when adding
        # stop dwell time; only subsequent stops are tested with CanStopHere.
        # The serialized prefab references needed to call CanStopHere are not
        # present outside Unity, so use the conservative depot-excluded count.
        stop_count = max(0, len(array_values(field(line, "m_stops"))) - 1)
        # VehicleTypeObject.CalculateDuration: (distance * 16 / speed
        # + stopTime * 60 * stopCount) * frameTimeSpan.
        base = (length * 16) // speed + stop_time * 60 * stop_count
        duration = int(base * frame_time_span)
        # The line panel displays whole minutes; retain that same granularity
        # for reconstructed values (ceiling avoids understating a full loop).
        slot_ticks = 3_000_000_000  # five in-game minutes
        duration = max(slot_ticks * 2, ((duration + slot_ticks - 1) // slot_ticks) * slot_ticks)

    top = cached_top
    if top <= 0 or (cached_top == 1 and cached_length <= 0):
        top = timetable_needed_vehicles(line, duration)
    return length, duration, top


def recompute_runtime_line_values(line, mode, frame_time_span):
    """Recompute all three panel metrics from serialized route/timetable data.

    Unlike :func:`derive_runtime_line_values`, this intentionally ignores the
    LineData cache. It is used to validate the fitted algorithm independently
    of values that happened to be serialized in the save.
    """
    # CalculateSegmentLength is the game's road-type-aware conversion routine.
    # Calling it for every stop reproduces the panel mileage without reading
    # the serialized m_lineLength cache.
    length = 0
    stops = array_values(field(line, "m_stops"))
    calculator = next((m for m in line.GetType().GetMethods(FLAGS)
                       if m.Name == "CalculateSegmentLength"), None)
    if calculator is not None:
        try:
            length = calculate_segment_length_sum(line)
        except Exception:
            length = 0
    if length <= 0:
        # Fallback remains route-derived and never uses LineData cache.
        length = path_length_from_vehicle_route(line)
    speed, stop_time = VEHICLE_TYPE_PARAMS.get(mode, (3300, 12))
    # LinePanel.CalculateDuration calls CalculateDuration once per segment,
    # preserving integer division before multiplying by frameTimeSpan.  Dwell
    # time is added for stoppable entries after the depot.
    duration = 0
    for index in range(len(stops)):
        distance = duration_segment_distance(line, index)
        duration += ((distance * 16) // speed) * frame_time_span
        if index > 0 and can_stop_here_serialized(field(stops[index], "m_stop")):
            duration += (stop_time * 60) * frame_time_span
    slot_ticks = 3_000_000_000  # five in-game minutes
    if duration > 0:
        duration = max(slot_ticks * 2, ((duration + slot_ticks - 1) // slot_ticks) * slot_ticks)
    top = timetable_needed_vehicles(line, duration)
    if top <= 0:
        top = int(field(line, "m_vehiclesNeededTop") or 0)
    return length, duration, top


def load_root(refresh_payload: bool = False):
    """Deserialize the selected save, refreshing a stale payload when needed.

    Most probe scripts import this module and call ``load_root`` directly,
    outside ``main``.  A replaced quicksave could otherwise leave them reading
    an older ``*.payload.bin``.  The explicit refresh flag is useful for
    validation; the normal path refreshes automatically when the save is
    newer than its payload.
    """
    if refresh_payload or not PAYLOAD.exists() or PAYLOAD.stat().st_mtime < SAVE.stat().st_mtime:
        prepare_payload()
    serializer = ASM.GetType("DataSerializer")
    # Keep the payload in a managed memory stream.  Opening the shared
    # payload file directly leaves a Windows file handle locked for the
    # lifetime of the deserialized object graph and makes concurrent audit
    # processes race with payload refreshes.
    # Read into a managed byte[] directly. Python bytes passed to this
    # constructor are marshalled element by element by pythonnet, which
    # dominates load time for the 50-75 MB payloads. ReadAllBytes closes the
    # payload file before deserialization, retaining memory-stream isolation.
    stream = System.IO.MemoryStream(System.IO.File.ReadAllBytes(str(PAYLOAD)))
    method = [m for m in serializer.GetMethods() if m.Name == "Deserialize" and m.IsStatic][0]
    root = method.Invoke(None, [stream, System.Boolean(False), System.Int32(4), None])
    return root, int(stream.Position)


def history_rows(root, reporter=None, total=None):
    """Flatten DataManager HistoryData ring buffers into auditable rows."""
    data_manager = field(root, "m_dataManagerData")
    histories = array_values(field(data_manager, "m_historyData"))
    start = field(root, "m_simulationStart")
    start_time = dt.datetime(start.Year, start.Month, start.Day, start.Hour,
                             start.Minute, start.Second) if start is not None else dt.datetime.min
    current = field(root, "m_simulationTime")
    current_time = dt.datetime(current.Year, current.Month, current.Day, current.Hour,
                               current.Minute, current.Second) if current is not None else start_time
    owners = []
    for index, player in enumerate(array_values(field(root, "m_players"))):
        company = field(player, "m_companyData")
        if company is not None:
            owners.append((company, str(field(player, "m_id") or ""), index))
    rows = []
    summaries = []
    core_names = {
        "public-transport", "trip-number", "trip-time", "vehicles-running",
        "linecount", "depotcount", "stopcount", "transport-by-group",
        "transport-by-type", "trip-types", "coverage", "popularity",
    }
    for history in histories:
        metric = str(field(history, "m_name") or "")
        # Company histories are keyed by HistoryData.m_company.  Preserve
        # that owner in the flat export; without it, two companies' rows for
        # vehicles-running/cashflow are indistinguishable.
        history_company = field(history, "m_company")
        history_company_name = str(field(history_company, "m_name") or "") if history_company is not None else ""
        company_id, company_index = owner_identity(history_company, owners)
        position = int(field(history, "m_position") or 0)
        percent = bool(field(history, "m_percent"))
        incremental = bool(field(history, "m_incremental"))
        # The unnamed base group is the game's per-company "Any" total.
        # Export it only for coverage, where the total has a verified meaning;
        # downstream queries keep it separate from its category components.
        category_groups = array_values(field(history, "m_tempGroups"))
        groups = [(group, str(field(group, "m_name") or ""), "分类")
                  for group in category_groups]
        base_group = field(history, "m_baseGroup")
        if metric == "coverage" and base_group is not None:
            groups.insert(0, (base_group, "任意", "总计"))
        for group, group_name, group_level in groups:
            values = field(group, "m_historyValues")
            dividers = field(group, "m_historyDividers")
            if values is None:
                continue
            # Position is the next slot; m_value/m_divider are the current slot.
            for index in valid_slot_indices(start_time, current_time, position, values.Length):
                if index == position:
                    continue
                value = int(values[index])
                divider = int(dividers[index]) if dividers is not None else 0
                ratio = (value / divider) if divider else None
                timestamp = slot_time(current_time, position, index, values.Length)
                rows.append({
                    "公司名称": history_company_name,
                    "指标": metric, "分组": group_name, "历史序号": index,
                    "模拟时间": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "值": value, "分母": divider, "值/分母": ratio,
                    "百分比指标": percent, "增量指标": incremental, "当前槽位": False,
                    "公司标识": company_id, "公司序号": company_index,
                    "分组层级": group_level,
                    "分组来源": "原始总组" if group_level == "总计" else "原始分类",
                })
            value = int(field(group, "m_value") or 0)
            divider = int(field(group, "m_divider") or 0)
            group_source = "原始总组" if group_level == "总计" else "原始分类"
            if group_level == "总计":
                # The live slot is held in the category groups in inspected
                # saves; the base group's live fields are left at zero.
                category_values = [(field(item, "m_value"), field(item, "m_divider"))
                                   for item in category_groups]
                value, divider, group_source = coverage_live_total(
                    value, divider, category_values)
            ratio = (value / divider) if divider else None
            timestamp = slot_time(current_time, position, position, values.Length)
            rows.append({
                "公司名称": history_company_name,
                "指标": metric, "分组": group_name, "历史序号": position,
                "模拟时间": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "值": value, "分母": divider, "值/分母": ratio,
                "百分比指标": percent, "增量指标": incremental, "当前槽位": True,
                "公司标识": company_id, "公司序号": company_index,
                "分组层级": group_level,
                "分组来源": group_source,
            })
            summaries.append({
                "公司名称": history_company_name,
                "指标": metric, "分组": group_name, "历史位置": position,
                "当前值": value, "当前分母": divider, "当前值/分母": ratio,
                "百分比指标": percent, "增量指标": incremental,
                "历史数组长度": int(values.Length), "是否核心指标": metric in core_names,
                "公司标识": company_id, "公司序号": company_index,
                "分组层级": group_level,
                "分组来源": group_source,
            })
            if reporter is not None:
                reporter.progress('history', len(rows), total)
    return rows, summaries, core_names


def workload_counts(root, lines):
    """Count rows from array lengths/ring positions, without extracting values."""
    start, current = field(root, 'm_simulationStart'), field(root, 'm_simulationTime')
    def as_hour(value):
        return dt.datetime(value.Year, value.Month, value.Day, value.Hour) if value is not None else dt.datetime.min
    elapsed = int((as_hour(current) - as_hour(start)).total_seconds() // 3600)
    histories = array_values(field(field(root, 'm_dataManagerData'), 'm_historyData'))
    history_count = 0
    for history in histories:
        position = int(field(history, 'm_position') or 0)
        groups = array_values(field(history, 'm_tempGroups'))
        base = field(history, 'm_baseGroup')
        if str(field(history, 'm_name') or '') == 'coverage' and base is not None:
            groups = [base, *groups]
        for group in groups:
            values = field(group, 'm_historyValues')
            if values is None or values.Length == 0:
                continue
            length = int(values.Length)
            valid = length if elapsed >= length else min(position + 1, length)
            history_count += valid - int(0 <= position < valid) + 1
    departures = 0
    for line in lines:
        for timetable in array_values(field(line, 'm_timeTables')):
            rows = field(timetable, 'm_rows')
            departures += int(rows.Length) if rows is not None else 0
    return dict(event='workload', line_count=len(lines), history_rows=history_count,
                departure_count=departures)


def company_rows(root):
    """Flatten all multiplayer PlayerData/CompanyData records."""
    players = array_values(field(root, "m_players"))
    city_manager = field(root, "m_cityManagerData")
    economy = field(city_manager, "m_economyData")
    electricity_price = int(field(economy, "m_electricityPrice") or 0)
    fuel_price = int(field(economy, "m_fuelPrice") or 0)
    companies = []
    vehicle_types = []
    for player_index, player in enumerate(players):
        company = field(player, "m_companyData")
        if company is None:
            continue
        company_id = str(field(player, "m_id") or "")
        company_name = field(company, "m_name") or field(player, "m_companyName") or ""
        companies.append({
            "公司序号": player_index, "玩家ID": company_id,
            "玩家名": field(player, "m_name") or "",
            "公司名称": company_name, "公司标志": field(company, "m_logo") or field(player, "m_companyLogo") or "",
            "颜色1": int(field(company, "m_color1") or 0), "颜色2": int(field(company, "m_color2") or 0),
            "资金": int(field(company, "m_money") or 0), "基础设施价值": int(field(company, "m_infraValue") or 0),
            "车辆价值": int(field(company, "m_vehicleValue") or 0), "业务价值": int(field(company, "m_businessValue") or 0),
            "公司价值": int(field(company, "m_companyValue") or 0),
            "待付运营支出": int(field(company, "m_pendingExpenses") or 0),
            "待付杂项支出": int(field(company, "m_pendingMiscExpenses") or 0),
            "司机工资": int(field(company, "m_driverWage") or 0),
            "维护工资": int(field(company, "m_maintenanceWage") or 0),
            "检查员工资": int(field(company, "m_inspectorWage") or 0),
            "检查员数量": int(field(company, "m_inspectorCount") or 0),
            "拥挤度": int(field(company, "m_overcrowding") or 0),
            "声誉": int(field(company, "m_reputation") or 0),
            "逃票累计": int(field(company, "m_cheaters") or 0),
            "双车行程客流": int(field(company, "m_transportedWithTwoVehicles") or 0),
            "玩家槽位": int(field(player, "m_index") or player_index),
            "电力价格": electricity_price, "燃料价格": fuel_price,
        })
        type_data = []
        general = field(company, "m_generalVehicleTypeData")
        if general is not None:
            type_data.append((0, general))
        for type_index, item in enumerate(array_values(field(company, "m_vehicleTypeData")), 1):
            type_data.append((type_index, item))
        for type_index, item in type_data:
            vehicle_types.append({
                "公司序号": player_index, "玩家ID": company_id, "公司名称": company_name,
                "车型序号": type_index, "车型类型": field(item, "m_type") or "",
                "已拥有": bool(field(item, "m_owned")), "单线票价": int(field(item, "m_singleLine") or 0),
                "一区票价": int(field(item, "m_oneZone") or 0), "二区票价": int(field(item, "m_twoZones") or 0),
                "全区票价": int(field(item, "m_allZones") or 0),
                "收入累计": int(field(item, "m_income") or 0), "支出累计": int(field(item, "m_expenses") or 0),
                "待付支出": int(field(item, "m_pendingExpenses") or 0),
                "电力估算": int(field(item, "m_electricityEstimate") or 0),
                "燃料估算": int(field(item, "m_fuelEstimate") or 0),
                "维护估算": int(field(item, "m_maintenanceEstimate") or 0),
                "司机估算": int(field(item, "m_driverEstimate") or 0),
                "维护需求": int(field(item, "m_maintenanceRequirement") or 0),
                "电力消耗": int(field(item, "m_electricityConsumption") or 0),
                "燃料消耗": int(field(item, "m_fuelConsumption") or 0),
                "司机需求": int(field(item, "m_driverRequirement") or 0),
                "运行车辆数": int(field(item, "m_vehiclesRunning") or 0),
            })
    return players, companies, vehicle_types


def main():
    EXPORT.mkdir(parents=True, exist_ok=True)
    reporter = ProgressReporter()
    reporter.start('payload')
    compressed_offset, payload_length = prepare_payload()
    reporter.emit(dict(event='payload', save_bytes_done=SAVE.stat().st_size,
                       save_bytes_total=SAVE.stat().st_size, payload_bytes=payload_length))
    reporter.finish('payload')
    reporter.start('deserialize')
    root, stream_position = load_root()
    reporter.finish('deserialize')
    players, company_info_rows, company_type_rows = company_rows(root)
    simulation_start = field(root, "m_simulationStart")
    simulation_time = field(root, "m_simulationTime")
    simulation_frame = int(field(root, "m_simulationFrame") or 0)
    frame_time_span = 350000
    if simulation_start is not None and simulation_time is not None and simulation_frame:
        try:
            frame_time_span = max(1, int(round((simulation_time - simulation_start).Ticks / simulation_frame)))
        except Exception:
            pass
    company_by_player = {row["公司序号"]: row for row in company_info_rows}
    transport = field(root, "m_transportManagerData")
    # Count every owned vehicle in every depot, including vehicles currently
    # parked or not assigned to a line.  LineData.m_vehicles only contains
    # vehicles attached to that line and therefore undercounts company fleets.
    depot_vehicle_counts = {i: 0 for i in range(len(players))}
    depot = field(transport, "m_firstDepot")
    depot_limit = int(field(transport, "m_depotCount") or 1000)
    depot_index = 0
    depot_objects = []
    while depot is not None and depot_index < depot_limit:
        depot_objects.append(depot)
        owner = field(depot, "m_owner")
        owner_index = next(
            (i for i, player in enumerate(players)
             if System.Object.ReferenceEquals(owner, field(player, "m_companyData"))),
            None,
        )
        if owner_index is not None:
            depot_vehicle_counts[owner_index] += len(array_values(field(depot, "m_vehicles")))
        depot = field(depot, "m_nextDepot")
        depot_index += 1
    for row in company_info_rows:
        row["车辆总数"] = depot_vehicle_counts.get(int(row["公司序号"]), 0)
    line = field(transport, "m_firstLine")
    lines = []
    seen = set()
    while line is not None and len(lines) < 1000:
        identity = int(field(line, "m_objectID") or 0)
        if identity in seen:
            break
        seen.add(identity)
        mode = line_mode(line)
        number = int(field(line, "m_number") or 0)
        lines.append((line, mode, number))
        line = field(line, "m_nextLine")
    workload = workload_counts(root, [line for line, _, _ in lines])
    reporter.emit(workload)
    reporter.start('lines')

    # Attribute complete depot fleets by transport mode.  A depot's prefab
    # type is a Unity runtime reference and may be absent in a standalone
    # deserialization.  Assigned line vehicles provide an unambiguous mode;
    # an unassigned depot is assigned to the company's dominant known mode so
    # per-mode totals still add exactly to the complete fleet total.
    depot_modes = {}
    for line, mode, _ in lines:
        depot = field(line, "m_depot")
        if depot is None:
            continue
        key = next((i for i, item in enumerate(depot_objects) if System.Object.ReferenceEquals(item, depot)), None)
        if key is not None:
            depot_modes.setdefault(key, set()).add(mode)
    mode_totals = {i: {} for i in range(len(players))}
    unknown_depots = {i: 0 for i in range(len(players))}
    depot = field(transport, "m_firstDepot")
    depot_index = 0
    depot_index = 0
    while depot is not None and depot_index < depot_limit:
        owner = field(depot, "m_owner")
        owner_index = next(
            (i for i, player in enumerate(players)
             if System.Object.ReferenceEquals(owner, field(player, "m_companyData"))),
            None,
        )
        if owner_index is not None:
            depot_key = depot_index
            modes = depot_modes.get(depot_key, set())
            count = int(field(depot, "m_totalVehicles") or len(array_values(field(depot, "m_vehicles"))))
            if len(modes) == 1:
                mode = next(iter(modes)); mode_totals[owner_index][mode] = mode_totals[owner_index].get(mode, 0) + count
            else:
                unknown_depots[owner_index] += count
        depot = field(depot, "m_nextDepot")
        depot_index += 1
    for row in company_info_rows:
        # Totals are keyed by player index; players without a company have no
        # row, so the row position is not a player index.
        player_index = int(row["公司序号"])
        known = mode_totals[player_index]
        fallback_mode = max(known, key=known.get) if known else "公交"
        if unknown_depots[player_index]:
            known[fallback_mode] = known.get(fallback_mode, 0) + unknown_depots[player_index]
        for mode in ("公交", "单轨列车", "地铁", "无轨电车", "有轨电车", "水上巴士"):
            row[f"车辆总数_{mode}"] = known.get(mode, 0)

    line_rows = []
    vehicle_rows = []
    timetable_rows = []
    row_rows = []
    stop_rows = []
    line_schedule_summary = []
    for line_index, (line, mode, number) in enumerate(lines):
        depot = field(line, "m_depot")
        owner = field(depot, "m_owner") if depot is not None else None
        owner_index = next(
            (i for i, player in enumerate(players)
             if System.Object.ReferenceEquals(owner, field(player, "m_companyData"))),
            None,
        )
        owner_info = company_by_player.get(owner_index)
        owner_name = owner_info["公司名称"] if owner_info else ""
        owner_id = owner_info["玩家ID"] if owner_info else ""
        identity = int(field(line, "m_objectID") or 0)
        vehicles = array_values(field(line, "m_vehicles"))
        timetables = array_values(field(line, "m_timeTables"))
        stops = array_values(field(line, "m_stops"))
        # Raw map mileage is the sum of referenced RoadData lengths, excluding
        # each station path's terminal connector.
        # ``runtime_length`` is the game's converted/fixed-point mileage from
        # CalculateSegmentLength (junction and expressway rules included).
        # The game's displayed map mileage is the road-type-aware converted
        # value, not a raw sum of RoadData lengths.  The latter omits endpoint
        # offsets and makes many multiplayer lines appear far too short.
        map_length = map_length_from_vehicle_route(line)
        # The serialized LineData cache can be stale in multiplayer saves.
        # Always follow the same route/timetable calculation used by the line
        # panel; the cache remains available to the comparison/audit tools.
        # Compute the raw map value first because rebuilding the converted
        # metric may lazily refresh path objects through GetQuickPosition.
        runtime_length, runtime_duration, runtime_top = recompute_runtime_line_values(line, mode, frame_time_span)
        line_rows.append({
            "公司序号": owner_index if owner_index is not None else "", "玩家ID": owner_id,
            "公司名称": owner_name, "线路类型": mode, "线路号": number,
            "线路名称": field(line, "m_name") or "",
            # LineData inherits ObjectData.m_buildTime.  StopData.m_buildTime
            # is the construction time of a shared stop and can predate the
            # line, so it must not be used as the line opening date.
            "开线日期": datetime_text(field(line, "m_buildTime")),
            "开线日期_tick": int(field(line, "m_buildTime") or 0),
            "最近改线日期": datetime_text(field(line, "m_lineEditTime")),
            "最近改线日期_tick": int(field(line, "m_lineEditTime") or 0),
            "线路车库": int(field(depot, "m_number") or 0) if depot is not None else "",
            "客流_今日": int(field(line, "m_transportedToday") or 0),
            "客流_累计": int(field(line, "m_totalTransported") or 0),
            "配车数": len(vehicles), "最大配车数": runtime_top,
            "时刻表数": len(timetables), "站点数": len(stops),
            "发车间隔_tick": int(field(timetables[0], "m_interval") or 0) if timetables else 0,
            "发车间隔": duration_text(field(timetables[0], "m_interval")) if timetables else "",
            "首班_tick": int(field(timetables[0], "m_startTime") or 0) if timetables else 0,
            "末班_tick": int(field(timetables[0], "m_endTime") or 0) if timetables else 0,
            "地图里程": map_length,
            "折算里程": runtime_length,
            # Keep the legacy key in the CSV for older audit scripts; the
            # workbook presents the explicit “地图里程/折算里程” names.
            "线路长度": runtime_length,
            "单程时间_tick": runtime_duration,
            "单程时间": duration_text(runtime_duration),
            "收入_累计": int(field(line, "m_income") or 0),
            "支出_累计": int(field(line, "m_expenses") or 0),
            "对象ID": identity,
            "平均车辆需求数_缓存_fixed": int(field(line, "m_vehiclesNeededAvg")) if field(line, "m_vehiclesNeededAvg") is not None else "",
            "线路车库名称": (field(depot, "m_name") or "") if depot is not None else "",
        })
        for slot, lv in enumerate(vehicles, 1):
            dv = field(lv, "m_depotVehicle")
            vehicle_rows.append({
                "公司序号": owner_index if owner_index is not None else "", "玩家ID": owner_id,
                "公司名称": owner_name, "线路类型": mode, "线路号": number, "车辆槽位": slot,
                "车辆对象ID": int(field(dv, "m_id") or 0),
                "车辆编号": int(field(dv, "m_number") or 0),
                "车辆名称": field(dv, "m_name") or "",
                "车辆客流_今日": int(field(dv, "m_transportedToday") or 0),
                "车辆客流_累计": int(field(dv, "m_totalTransported") or 0),
                "本次发车_tick": int(field(lv, "m_departure") or 0),
                "本次发车": datetime_text(field(lv, "m_departure")),
                "下次发车_tick": int(field(lv, "m_nextDeparture") or 0),
                "下次发车": datetime_text(field(lv, "m_nextDeparture")),
                "下一站序号": int(field(lv, "m_nextStopIndex") or 0),
                "末段距离": int(field(lv, "m_lastDistance") or 0),
            })
        for ti, tt in enumerate(timetables, 1):
            rows = array_values(field(tt, "m_rows"))
            timetable_rows.append({
                "公司序号": owner_index if owner_index is not None else "", "玩家ID": owner_id,
                "公司名称": owner_name, "线路类型": mode, "线路号": number, "时刻表序号": ti,
                "运行日掩码": int(field(tt, "m_activeDays") or 0),
                "开始_tick": int(field(tt, "m_startTime") or 0), "开始": duration_text(field(tt, "m_startTime")),
                "结束_tick": int(field(tt, "m_endTime") or 0), "结束": duration_text(field(tt, "m_endTime")),
                "间隔_tick": int(field(tt, "m_interval") or 0), "间隔": duration_text(field(tt, "m_interval")),
                "首选车型": int(field(tt, "m_preferSize") or 0),
                "列车配置": int(field(tt, "m_trainConfiguration") or 0),
                "发班记录数": len(rows),
            })
            for ri, rr in enumerate(rows, 1):
                departure = field(rr, "m_departure")
                row_rows.append({
                    "公司序号": owner_index if owner_index is not None else "", "玩家ID": owner_id,
                    "公司名称": owner_name, "线路类型": mode, "线路号": number, "时刻表序号": ti,
                    "时刻表_运行日掩码": int(field(tt, "m_activeDays") or 0),
                    "时刻表_首选车型": int(field(tt, "m_preferSize") or 0),
                    "发班序号": ri, "发班_tick": int(departure or 0),
                    "发班时间": duration_text(departure),
                })
        line_schedule_summary.append({
            "公司序号": owner_index if owner_index is not None else "", "玩家ID": owner_id,
            "公司名称": owner_name, "线路类型": mode, "线路号": number, "配车数": len(vehicles),
            "时刻表数": len(timetables), "发班记录总数": sum(
                len(array_values(field(tt, "m_rows"))) for tt in timetables
            ),
            "对象ID": identity,
        })
        for si, ls in enumerate(stops, 1):
            stop_obj = field(ls, "m_stop")
            stop_rows.append({
                "公司序号": owner_index if owner_index is not None else "", "玩家ID": owner_id,
                "公司名称": owner_name, "线路类型": mode, "线路号": number, "站点序号": si,
                "站点对象类型": stop_obj.GetType().FullName if stop_obj is not None else "",
                "站点编号": int(field(stop_obj, "m_number") or 0),
                "站点名称": field(stop_obj, "m_name") or "",
                "线路当前候车人数": int(field(ls, "m_passengerCount") or 0),
                "站点客流_今日": int(field(stop_obj, "m_transportedToday") or 0),
                "站点客流_累计": int(field(stop_obj, "m_totalTransported") or 0),
                "分区": int(field(ls, "m_division") or 0),
                "时间偏移_tick": int(field(ls, "m_timeOffset") or 0),
            })
        reporter.progress('lines', line_index + 1, len(lines))
    reporter.finish('lines')

    csv_done = 0
    history_complete = False
    def write_csv(path, rows):
        nonlocal csv_done
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
        csv_done += 1
        if history_complete:
            reporter.progress('csv', csv_done, 15)

    write_csv(OUT("CIM2_公司信息"), company_info_rows)
    write_csv(OUT("CIM2_公司车型数据"), company_type_rows)
    write_csv(OUT("CIM2_线路客流_完整导出"), line_rows)
    write_csv(OUT("CIM2_配车信息_完整导出"), vehicle_rows)
    write_csv(OUT("CIM2_发班信息_完整导出"), timetable_rows)
    write_csv(OUT("CIM2_发班记录_完整导出"), row_rows)
    write_csv(OUT("CIM2_线路发班配车汇总"), line_schedule_summary)
    write_csv(OUT("CIM2_线路站点客流分布_当前"), stop_rows)

    reporter.start('history')
    all_history, history_summary, core_names = history_rows(root, reporter, workload['history_rows'])
    assert len(all_history) == workload['history_rows'], 'History count differs from actual rows'
    reporter.finish('history')
    history_complete = True
    write_csv(OUT("CIM2_城市历史指标_完整"), all_history)
    write_csv(OUT("CIM2_城市历史指标汇总"), history_summary)
    write_csv(OUT("CIM2_城市历史核心指标"), [
        row for row in all_history if row["指标"] in core_names
    ])
    distribution_names = {"public-transport", "transport-by-group", "transport-by-type", "trip-types"}
    write_csv(OUT("CIM2_城市客流分布_完整"), [
        row for row in all_history if row["指标"] in distribution_names
    ])
    # Prefer bounded, typed save-header m_originalMapName. Preserve the raw
    # reference and provenance; a save filename is not a map/city name.
    def optional_text(obj, *names):
        for name in names:
            value = field(obj, name)
            if value is not None and str(value):
                return str(value)
        return ""

    city_data = field(field(root, "m_cityManagerData"), "m_cityData")
    from map_name_source import map_metadata_fields
    runtime_map_name, runtime_map_source = "", ""
    for map_field in ("m_originalMapName", "m_mapName", "m_scenarioName", "m_cityName"):
        runtime_map_name = optional_text(root, map_field)
        if runtime_map_name:
            runtime_map_source = "runtime:" + map_field
            break
    map_fields = map_metadata_fields(SAVE, runtime_name=runtime_map_name, runtime_source=runtime_map_source)

    write_csv(OUT("CIM2_城市历史元数据"), [{
        "数据格式版本": int(field(root, "m_dataFormatVersion") or 0),
        "模拟帧": int(field(root, "m_simulationFrame") or 0),
        "模拟开始": str(field(root, "m_simulationStart") or ""),
        "模拟开始_tick": int(field(root, "m_simulationStart").Ticks) if field(root, "m_simulationStart") is not None else 0,
        "模拟当前时间": str(field(root, "m_simulationTime") or ""),
        "模拟当前时间_tick": int(field(root, "m_simulationTime").Ticks) if field(root, "m_simulationTime") is not None else 0,
        "DataManager最后历史时间": str(field(field(root, "m_dataManagerData"), "m_lastTime") or ""),
        "公司数": len(company_info_rows), "历史指标数": len(history_summary), "线路数": len(lines),
        "配车对象数": len(vehicle_rows), "时刻表数": len(timetable_rows),
        "发班记录数": len(row_rows), "站点记录数": len(stop_rows),
        **map_fields,
        "当前人口数": int(field(city_data, "m_totalCitizenCount") or field(city_data, "m_citizenCount") or 0),
    }])
    metric_meanings = {
        "unemployment": "失业率", "population": "人口",
        "traffic-density": "道路/轨道交通密度", "public-transport": "公共交通客流",
        "private-motoring": "私家车出行", "walking": "步行出行",
        "trip-number": "行程数量（城市历史统计）", "trip-time": "行程时间（原始值及分母）",
        "economy": "经济指标", "energy-prices": "能源价格", "cashflow": "现金流",
        "vehicles-running": "运行中的车辆数", "reputation": "声誉",
        "company-value": "公司价值", "coverage": "公共交通覆盖率",
        "depotcount": "车库数", "stopcount": "站点数", "linecount": "线路数",
        "popularity": "公共交通吸引力", "satisfaction-speed": "速度满意度",
        "satisfaction-cost": "成本满意度", "satisfaction-quality": "质量满意度",
        "monthly-ticket": "月票客流", "generic-ticket": "普通票客流",
        "fare-dodging": "逃票", "trip-types": "行程类型分布",
        "transport-by-group": "按社会群体的客流分布",
        "transport-by-type": "按交通工具类型的客流分布",
    }
    metric_dict = []
    for row in history_summary:
        if not any(x["指标"] == row["指标"] for x in metric_dict):
            metric_dict.append({
                "指标": row["指标"], "中文含义": metric_meanings.get(row["指标"], "未命名历史指标"),
                "百分比指标": row["百分比指标"], "增量指标": row["增量指标"],
                "历史数组长度": row["历史数组长度"],
                "历史序列说明": "数组索引0至历史位置-1，历史位置槽为当前值",
            })
    write_csv(OUT("CIM2_城市历史指标字典"), metric_dict)

    payload_size = PAYLOAD.stat().st_size
    diagnostic = {
        "save": str(SAVE),
        "payload": str(PAYLOAD),
        "compressed_stream_offset": compressed_offset,
        "payload_size": payload_size,
        "deserializer_stream_position": stream_position,
        "trailing_padding_bytes": payload_size - stream_position,
        "root_type": root.GetType().FullName,
        "data_format_version": int(field(root, "m_dataFormatVersion") or 0),
        "company_count": len(company_info_rows), "line_count": len(lines), "vehicle_count": len(vehicle_rows),
        "timetable_count": len(timetable_rows), "timetable_row_count": len(row_rows),
        "stop_row_count": len(stop_rows), "history_metric_count": len(metric_dict),
        "history_group_count": len(history_summary),
        "history_rows": len(all_history), "history_valid_last_index": max(
            (int(r["历史序号"]) for r in all_history), default=None
        ),
        "complete_object_graph": True,
    }
    (EXPORT / f"CIM2_运行时模拟解析诊断_{TAG}.json").write_text(
        json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manual = [
        ("有轨电车", 2, 90057), ("有轨电车", 5, 70881), ("公交", 8, 50738),
        ("公交", 2, 37439), ("公交", 11, 36250), ("公交", 6, 32289),
        ("有轨电车", 1, 29116), ("公交", 5, 29089), ("有轨电车", 4, 29041),
        ("公交", 4, 28988), ("公交", 7, 26914), ("有轨电车", 3, 26029),
        ("公交", 10, 24821), ("公交", 38, 24166), ("公交", 3, 24037),
        ("公交", 22, 23491), ("公交", 43, 23146), ("公交", 9, 23127),
        ("公交", 27, 23098), ("公交", 19, 22531), ("公交", 231, 20837),
        ("公交", 18, 20128), ("公交", 1, 18043), ("公交", 16, 17829),
        ("公交", 13, 17299),
    ]
    by_passenger = {r["客流_今日"]: r for r in line_rows}
    compare = []
    for rank, (mode, number, expected) in enumerate(manual, 1):
        # Passenger totals are unique in the reference rows and avoid
        # conflating the game's energy signature with the screenshot label.
        actual = by_passenger.get(expected)
        value = actual["客流_今日"] if actual else None
        compare.append({"人工排名": rank, "线路类型": mode, "线路号": number,
                        "人工客流_今日": expected, "存档客流_今日": value,
                        "差值": (value - expected) if value is not None else None,
                        "存档线路号": actual["线路号"] if actual else None,
                        "存档线路类型": actual["线路类型"] if actual else None,
                        "结果": "一致" if value == expected and actual["线路号"] == number else "缺失/不一致"})
    write_csv(OUT("CIM2_人工数据比对_完整"), compare)

    print(f"lines={len(lines)} vehicles={len(vehicle_rows)} timetables={len(timetable_rows)} timetable_rows={len(row_rows)}")
    print(f"manual_exact={sum(r['结果']=='一致' for r in compare)}/{len(compare)}")


if __name__ == "__main__":
    main()
