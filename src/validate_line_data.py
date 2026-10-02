from __future__ import annotations

import csv
import sys
from pathlib import Path

import extract_runtime_data as e

PROJECT = Path(__file__).resolve().parents[1]
EXPORT = PROJECT / "exports"
SAVE = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT / "data" / "quicksave.76561198362520556-76561198845688243.save"
if not SAVE.is_absolute():
    SAVE = (PROJECT / SAVE).resolve()
TAG = "运行时" if SAVE.stem == "望春市6" else f"{SAVE.stem}_运行时"


def array_values(arr):
    return e.array_values(arr)


def owner_name(line, players, companies):
    depot = e.field(line, "m_depot")
    owner = e.field(depot, "m_owner") if depot is not None else None
    for i, player in enumerate(players):
        if owner is not None and e.System.Object.ReferenceEquals(owner, e.field(player, "m_companyData")):
            return companies.get(i, "")
    return ""


def main():
    root, _ = e.load_root()
    players, company_rows, _ = e.company_rows(root)
    companies = {r["公司序号"]: r["公司名称"] for r in company_rows}
    current_path = EXPORT / f"CIM2_线路客流_完整导出_{TAG}.csv"
    with current_path.open(encoding="utf-8-sig", newline="") as f:
        exported = list(csv.DictReader(f))
    exported_by_key = {(r["公司名称"], r["线路类型"], r["线路号"]): r for r in exported}

    transport = e.field(root, "m_transportManagerData")
    line = e.field(transport, "m_firstLine")
    rows = []
    direct_fields = [
        ("线路类型", "线路类型", lambda l: e.line_mode(l)),
        ("线路号", "线路号", lambda l: int(e.field(l, "m_number") or 0)),
        ("线路名称", "线路名称", lambda l: str(e.field(l, "m_name") or "")),
        ("客流_今日", "客流_今日", lambda l: int(e.field(l, "m_transportedToday") or 0)),
        ("客流_累计", "客流_累计", lambda l: int(e.field(l, "m_totalTransported") or 0)),
        ("配车数", "配车数", lambda l: len(array_values(e.field(l, "m_vehicles")))),
        ("时刻表数", "时刻表数", lambda l: len(array_values(e.field(l, "m_timeTables")))),
        ("站点数", "站点数", lambda l: len(array_values(e.field(l, "m_stops")))),
        ("收入_累计", "收入_累计", lambda l: int(e.field(l, "m_income") or 0)),
        ("支出_累计", "支出_累计", lambda l: int(e.field(l, "m_expenses") or 0)),
        ("线路长度", "原始线路长度", lambda l: int(e.field(l, "m_lineLength") or 0)),
        ("单程时间_tick", "原始单程时间_tick", lambda l: int(e.field(l, "m_estimatedDuration") or 0)),
        ("最大配车数", "原始最大配车数", lambda l: int(e.field(l, "m_vehiclesNeededTop") or 0)),
    ]
    seen = set()
    while line is not None:
        number = str(int(e.field(line, "m_number") or 0))
        mode = e.line_mode(line)
        company = owner_name(line, players, companies)
        key = (company, mode, number)
        current = exported_by_key.get(key, {})
        mismatches = []
        checked = 0
        for raw_key, out_key, getter in direct_fields:
            direct = getter(line)
            if raw_key == "线路类型":
                actual = current.get("线路类型", "")
            elif raw_key in {"线路长度", "单程时间_tick", "最大配车数"}:
                # These three fields may intentionally be replaced when the
                # serialized cache is invalid; compare them separately below.
                continue
            else:
                try: actual = int(float(current.get(raw_key, "0") or 0)) if isinstance(direct, int) else current.get(raw_key, "")
                except ValueError: actual = current.get(raw_key, "")
            checked += 1
            if str(direct) != str(actual):
                mismatches.append(f"{raw_key}:{direct}!={actual}")
        raw_length = int(e.field(line, "m_lineLength") or 0)
        raw_duration = int(e.field(line, "m_estimatedDuration") or 0)
        raw_top = int(e.field(line, "m_vehiclesNeededTop") or 0)
        # The exporter intentionally uses a cache-independent reconstruction.
        # A nonzero cache can still be stale after a line edit in a multiplayer
        # save, so validation must compare against the current serialized route,
        # not blindly trust the three cached fields.
        rebuilt_length, rebuilt_duration, rebuilt_top = e.recompute_runtime_line_values(line, mode, 350000)
        cache_valid = raw_length > 0 and raw_duration > 0 and raw_top > 0
        expected_length = rebuilt_length
        expected_duration = rebuilt_duration
        expected_top = rebuilt_top
        actual_length = int(float(current.get("线路长度", "0") or 0))
        actual_duration = int(float(current.get("单程时间_tick", "0") or 0))
        actual_top = int(float(current.get("最大配车数", "0") or 0))
        metric_mismatches = []
        if actual_length != expected_length: metric_mismatches.append("线路长度")
        if actual_duration != expected_duration: metric_mismatches.append("预计时间")
        if actual_top != expected_top: metric_mismatches.append("最大车辆需求数")
        rows.append({
            "公司名称": company, "运输制式": mode, "线路号": number,
            "直接字段检查数": checked, "直接字段不一致数": len(mismatches),
            "直接字段不一致": "; ".join(mismatches),
            "LineData原始线路长度": raw_length, "导出线路长度": current.get("线路长度", ""),
            "LineData原始单程时间_tick": raw_duration, "导出单程时间_tick": current.get("单程时间_tick", ""),
            "LineData原始最大配车数": raw_top, "导出最大配车数": current.get("最大配车数", ""),
            "重建后线路长度": rebuilt_length, "重建后单程时间_tick": rebuilt_duration, "重建后最大配车数": rebuilt_top,
            "线路三项校验": "通过" if not metric_mismatches else "失败:" + ",".join(metric_mismatches),
            "缓存状态": "有效且一致" if cache_valid and (raw_length, raw_duration, raw_top) == (rebuilt_length, rebuilt_duration, rebuilt_top) else ("有效但过期" if cache_valid else "失效/重建"),
        })
        seen.add(key)
        line = e.field(line, "m_nextLine")
    out = EXPORT / f"CIM2_LineData全字段校验_{TAG}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(f"线路={len(rows)} 直接字段不一致线路={sum(r['直接字段不一致数']>0 for r in rows)} 三项校验失败线路={sum(r['线路三项校验']!='通过' for r in rows)} 输出={out}")
    for r in rows:
        if r["直接字段不一致数"]:
            print(r["公司名称"], r["运输制式"], r["线路号"], r["直接字段不一致"])


if __name__ == "__main__":
    main()
