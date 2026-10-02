from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
EXPORT = PROJECT / "exports"
TAG = sys.argv[1] if len(sys.argv) > 1 else "quicksave.76561198362520556-76561198845688243_运行时"


def read(stem):
    path = EXPORT / f"CIM2_{stem}_{TAG}.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def running_history(rows):
    """Last completed-hour values written by CompanyData.SimulationTick."""
    result = {}
    for row in rows:
        if row.get("指标") == "vehicles-running" and row.get("当前槽位") == "True" and row.get("公司名称"):
            result[(row.get("公司名称", ""), MODE.get(row.get("分组", ""), row.get("分组", "")))] = integer(row.get("值")) / 1024
    return result


def integer(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def parse_datetime(value):
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except (TypeError, ValueError):
            pass
    return None


MODE = {
    "bus": "公交", "trolley": "无轨电车", "tram": "有轨电车",
    "metro": "地铁", "waterbus": "水上巴士", "monorail": "单轨列车",
    "anyvehicletype": "综合",
}


def company_costs(type_row, company_row):
    prices_e = integer(company_row.get("电力价格"))
    prices_f = integer(company_row.get("燃料价格"))
    wages_m = integer(company_row.get("维护工资"))
    wages_d = integer(company_row.get("司机工资"))
    energy = integer(type_row.get("电力估算")) * prices_e / 102400
    fuel = integer(type_row.get("燃料估算")) * prices_f / 102400
    maintenance = integer(type_row.get("维护估算")) * 3 * wages_m / (1440 * 102400)
    driver = integer(type_row.get("司机估算")) * wages_d / (1440 * 102400)
    return energy, fuel, maintenance, driver


def main():
    companies = read(f"公司信息")
    types = read(f"公司车型数据")
    lines = read(f"线路客流_完整导出")
    metadata = read(f"城市历史元数据")[0]
    history = running_history(read(f"城市历史指标_完整"))
    by_company = {r.get("公司名称", ""): r for r in companies}
    line_sums = defaultdict(lambda: [0, 0])
    for row in lines:
        key = (row.get("公司名称", ""), row.get("线路类型", ""))
        line_sums[key][0] += integer(row.get("收入_累计"))
        line_sums[key][1] += integer(row.get("支出_累计"))

    end = parse_datetime(metadata.get("模拟当前时间", ""))
    week_start = end - timedelta(days=end.weekday()) if end else None
    rows = []
    for item in types:
        company_key = item.get("公司名称", "")
        mode = MODE.get(item.get("车型类型", ""), item.get("车型类型", ""))
        company_row = by_company.get(company_key, {})
        energy, fuel, maintenance, driver = company_costs(item, company_row)
        weekly_expense = energy + fuel + maintenance + driver
        raw_expense = integer(item.get("支出累计")) / 100
        running = history.get((company_key, mode), integer(item.get("运行车辆数")) / 1024)
        line_income, line_expense = line_sums[(company_key, mode)]
        rows.append({
            "公司名称": company_key,
            "运输制式": mode,
            "起始日期_周一": week_start.strftime("%Y-%m-%d") if week_start else "",
            "结束日期": (week_start + timedelta(days=6)).strftime("%Y-%m-%d") if week_start else "",
            "车型收入_除100": round(integer(item.get("收入累计")) / 100, 2),
            "线路收入合计_除1024再除100": round(line_income / 102400, 2),
            "收入差": round(integer(item.get("收入累计")) / 100 - line_income / 102400, 2),
            "分项支出合计": round(weekly_expense, 2),
            "车型支出字段_除100": round(raw_expense, 2),
            "支出字段与分项差": round(raw_expense - weekly_expense, 2),
            "能源支出": round(energy, 2),
            "燃料支出": round(fuel, 2),
            "维护支出": round(maintenance, 2),
            "驾驶员支出": round(driver, 2),
            "分项合计一致": "是" if abs((energy + fuel + maintenance + driver) - weekly_expense) < 0.005 else "否",
        })
    out = EXPORT / f"CIM2_公司周收支口径审计_{TAG}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("记录", len(rows), "分项合计一致", sum(r["分项合计一致"] == "是" for r in rows))
    print("周一起始", rows[0]["起始日期_周一"] if rows else "")
    print("输出", out)


if __name__ == "__main__":
    main()
