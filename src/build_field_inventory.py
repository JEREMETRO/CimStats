from __future__ import annotations

import csv
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
EXPORT = PROJECT / "exports"
TAG = sys.argv[1] if len(sys.argv) > 1 else "quicksave.76561198362520556-76561198845688243_运行时"


def main() -> None:
    rows = []
    for path in sorted(EXPORT.glob(f"CIM2_*_{TAG}.csv")):
        if path.name == f"CIM2_可统计字段清单_{TAG}.csv":
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            fields = next(reader, [])
            count = sum(1 for _ in reader)
        rows.append({
            "数据集": path.stem.removesuffix(f"_{TAG}"),
            "文件": path.name,
            "记录数": count,
            "字段数": len(fields),
            "字段": "|".join(fields),
        })
    out = EXPORT / f"CIM2_可统计字段清单_{TAG}.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("数据集", len(rows), "输出", out)


if __name__ == "__main__":
    main()
