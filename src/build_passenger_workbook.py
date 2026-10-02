from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

from openpyxl import Workbook

PROJECT = Path(__file__).resolve().parents[1]
EXPORT = Path(os.environ.get("CIM2_EXPORT_DIR", str(PROJECT / "exports")))
TAG = sys.argv[1] if len(sys.argv) > 1 else "运行时"

LINE_MONEY_SCALE = 102400
LINE_LENGTH_SCALE = 1024000
MAP_LENGTH_MULTIPLIER = 2.0


def read_lines() -> list[dict[str, str]]:
    path = EXPORT / f"CIM2_线路客流_完整导出_{TAG}.csv"
    if not path.exists():
        path = EXPORT / "reanalysis" / f"CIM2_线路客流_完整导出_{TAG}.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def integer(value: str) -> int:
    try:
        return int(float(value or 0))
    except ValueError:
        return 0


def main() -> None:
    rows = read_lines()
    headers = [
        "公司名称", "运输制式", "线路号", "线路名称", "累计客流", "今日客流",
        "当前配车数", "站点数", "线路长度", "每周收入", "每周支出",
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "线路客流"
    ws.append(headers)
    for row in rows:
        ws.append([
            row.get("公司名称", ""), row.get("线路类型", ""), integer(row.get("线路号", "0")), row.get("线路名称", ""),
            integer(row.get("客流_累计", "0")), integer(row.get("客流_今日", "0")), integer(row.get("配车数", "0")),
            integer(row.get("站点数", "0")), round(integer(row.get("地图里程", row.get("线路长度", "0"))) / LINE_LENGTH_SCALE * MAP_LENGTH_MULTIPLIER, 6),
            round(integer(row.get("收入_累计", "0")) / LINE_MONEY_SCALE, 2), round(integer(row.get("支出_累计", "0")) / LINE_MONEY_SCALE, 2),
        ])
    for sheet in wb.worksheets:
        widths = {}
        for row in sheet.iter_rows():
            for cell in row:
                value = "" if cell.value is None else str(cell.value)
                widths[cell.column] = max(widths.get(cell.column, 0), len(value))
        for column, width in widths.items():
            sheet.column_dimensions[sheet.cell(1, column).column_letter].width = min(max(width + 2, 10), 32)
    out = EXPORT / f"CIM2_线路客流_{TAG}.xlsx"
    wb.save(out)
    print(out)


if __name__ == "__main__":
    main()
