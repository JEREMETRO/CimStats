from __future__ import annotations
import csv, os, sys
from datetime import datetime, timedelta
from pathlib import Path
from parse_events import ProgressReporter
# Keep workbook serialization on the standard et_xmlfile path.  This avoids
# lxml IO_WRITE failures observed in one-file frozen processes.
import openpyxl
openpyxl.LXML = False
import openpyxl.xml.functions as _oxml
from et_xmlfile import xmlfile as _stdlib_xmlfile
_oxml.LXML = False
_oxml.xmlfile = _stdlib_xmlfile
from openpyxl import Workbook

PROJECT = Path(__file__).resolve().parents[1]
EXPORT = Path(os.environ.get("CIM2_EXPORT_DIR", str(PROJECT / "exports")))
TAG = sys.argv[1] if len(sys.argv) > 1 else "\u8fd0\u884c\u65f6"
NAMES = {"826272703's Company": "\u516d\u8fdb\u516c\u4ea4", "jeremylin2005's Company": "\u516b\u8fde\u4ea4\u901a\u96c6\u56e2"}
MODE = {"bus":"\u516c\u4ea4", "trolley":"\u65e0\u8f68\u7535\u8f66", "tram":"\u6709\u8f68\u7535\u8f66", "metro":"\u5730\u94c1", "waterbus":"\u6c34\u4e0a\u5df4\u58eb", "monorail":"\u5355\u8f68\u5217\u8f66", "anyvehicletype":"\u7efc\u5408"}
MODE_ORDER = ["\u516c\u4ea4", "\u5355\u8f68\u5217\u8f66", "\u5730\u94c1", "\u65e0\u8f68\u7535\u8f66", "\u6709\u8f68\u7535\u8f66", "\u6c34\u4e0a\u5df4\u58eb", "\u7efc\u5408"]
READ_INDEX = 0
def read_csv(stem):
    global READ_INDEX
    expected = ["\u516c\u53f8\u5e8f\u53f7", "\u8f66\u578b\u5e8f\u53f7", "\u6a21\u62df\u5f00\u59cb", "\u5f53\u524d\u503c"][min(READ_INDEX, 3)]
    READ_INDEX += 1
    for path in sorted(EXPORT.glob(f"CIM2_*_{TAG}.csv")):
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        if rows and expected in rows[0]: return rows
    raise FileNotFoundError(f"CSV for {expected} not found")
def integer(v):
    try: return int(float(v or 0))
    except (TypeError, ValueError): return 0
def money(v): return round(integer(v) / 100, 2)
def mode(v): return MODE.get(v, v)
def company(v): return NAMES.get(v, v)
def parse_dt(v):
    for f in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try: return datetime.strptime(v, f)
        except ValueError: pass
    return None
def running_by_company_type(types):
    """Return company-scoped running values from CompanyVehicleTypeData.

    The city history series ``vehicles-running`` is grouped only by transport
    mode, so it cannot populate per-company rows.  The serialized
    ``m_vehiclesRunning`` field is company-scoped and uses fixed-point units;
    the game display divides it by 1024.
    """
    return {
        (r.get("\u516c\u53f8\u540d\u79f0", ""), mode(r.get("\u8f66\u578b\u7c7b\u578b", ""))):
        round(integer(r.get("\u8fd0\u884c\u8f66\u8f86\u6570", "0")) / 1024, 2)
        for r in types
    }
def running_from_history(history_rows):
    """Use the last completed-hour company history value when available."""
    result = {}
    for r in history_rows:
        if r.get("指标") != "vehicles-running" or r.get("当前槽位") != "True":
            continue
        owner = r.get("公司名称", "")
        if owner:
            result[(owner, mode(r.get("分组", "")))] = round(integer(r.get("值", "0")) / 1024, 2)
    return result

def costs(r, meta):
    # Exact CompanyData.SimulationTick formulas. Estimates are fixed-point;
    # 102400 is 1024 fixed-point units times 100 currency subunits.
    e = round(integer(r.get("\u7535\u529b\u4f30\u7b97")) * integer(meta.get("\u7535\u529b\u4ef7\u683c")) / 102400, 2)
    f = round(integer(r.get("\u71c3\u6599\u4f30\u7b97")) * integer(meta.get("\u71c3\u6599\u4ef7\u683c")) / 102400, 2)
    m = round(integer(r.get("\u7ef4\u62a4\u4f30\u7b97")) * 3 * integer(meta.get("\u7ef4\u62a4\u5de5\u8d44")) / (1440 * 102400), 2)
    d = round(integer(r.get("\u53f8\u673a\u4f30\u7b97")) * integer(meta.get("\u53f8\u673a\u5de5\u8d44")) / (1440 * 102400), 2)
    return round(e + f + m + d, 2), e, f, m, d
def main():
    reporter = ProgressReporter()
    reporter.start('company_workbook')
    companies, types, meta = read_csv("company"), read_csv("types"), read_csv("metadata")[0]
    history_path = EXPORT / f"CIM2_城市历史指标_完整_{TAG}.csv"
    history_rows = []
    if history_path.exists():
        with history_path.open(encoding="utf-8-sig", newline="") as handle:
            history_rows = list(csv.DictReader(handle))
    keys = [r.get("\u516c\u53f8\u540d\u79f0", "") for r in companies]
    running = running_from_history(history_rows) or running_by_company_type(types)
    start, end = parse_dt(meta.get("\u6a21\u62df\u5f00\u59cb", "")), parse_dt(meta.get("\u6a21\u62df\u5f53\u524d\u65f6\u95f4", "")); week = end - timedelta(days=end.weekday()) if end else None
    # 周收支是 7 天平滑周化值，报告区间固定为当前周的完整平滑窗口。
    period_end = week + timedelta(days=6) if week else None
    wb = Workbook(); ws = wb.active; ws.title = "\u88681_\u516c\u53f8\u4fe1\u606f"; ws.append(["\u516c\u53f8\u540d\u79f0","\u8d44\u91d1","\u516c\u53f8\u4ef7\u503c","\u57fa\u7840\u8bbe\u65bd\u4ef7\u503c","\u8f66\u8f86\u4ef7\u503c","\u4e1a\u52a1\u4ef7\u503c","\u58f0\u8a89"])
    for r in companies: ws.append([company(r.get("\u516c\u53f8\u540d\u79f0")), money(r.get("\u8d44\u91d1")), money(r.get("\u516c\u53f8\u4ef7\u503c")), money(r.get("\u57fa\u7840\u8bbe\u65bd\u4ef7\u503c")), money(r.get("\u8f66\u8f86\u4ef7\u503c")), money(r.get("\u4e1a\u52a1\u4ef7\u503c")), integer(r.get("\u58f0\u8a89"))/10000])
    reporter.progress('company_workbook', 1, 5)
    ws = wb.create_sheet("\u88682_\u4eba\u5458\u8868"); ws.append(["\u516c\u53f8\u540d\u79f0","\u5f85\u4ed8\u4eba\u5458\u652f\u51fa","\u5f85\u4ed8\u6742\u9879\u652f\u51fa","\u53f8\u673a\u5de5\u8d44","\u7ef4\u62a4\u5de5\u8d44","\u68c0\u67e5\u5458\u5de5\u8d44","\u68c0\u67e5\u5458\u6570\u91cf"])
    for r in companies: ws.append([company(r.get("\u516c\u53f8\u540d\u79f0")), money(r.get("\u5f85\u4ed8\u8fd0\u8425\u652f\u51fa")), money(r.get("\u5f85\u4ed8\u6742\u9879\u652f\u51fa")), money(r.get("\u53f8\u673a\u5de5\u8d44")), money(r.get("\u7ef4\u62a4\u5de5\u8d44")), money(r.get("\u68c0\u67e5\u5458\u5de5\u8d44")), integer(r.get("\u68c0\u67e5\u5458\u6570\u91cf"))])
    modes = MODE_ORDER; by = {(mode(r.get("\u8f66\u578b\u7c7b\u578b", "")), r.get("\u516c\u53f8\u540d\u79f0", "")): r for r in types}
    reporter.progress('company_workbook', 2, 5)
    ws = wb.create_sheet("\u88683_\u7968\u4ef7\u8868")
    for ci, key in enumerate(keys):
        ws.append([company(key)]); ws.append(["\u8fd0\u8f93\u5236\u5f0f","\u5355\u7ebf\u7968\u4ef7","\u4e00\u533a\u7968\u4ef7","\u4e8c\u533a\u7968\u4ef7","\u5168\u533a\u7968\u4ef7"])
        for md in modes:
            r = by.get((md, key), {}); ws.append([md, money(r.get("\u5355\u7ebf\u7968\u4ef7")), money(r.get("\u4e00\u533a\u7968\u4ef7")), money(r.get("\u4e8c\u533a\u7968\u4ef7")), money(r.get("\u5168\u533a\u7968\u4ef7"))])
        if ci < len(keys)-1: ws.append([])
    reporter.progress('company_workbook', 3, 5)
    ws = wb.create_sheet("\u88684_\u5468\u6536\u652f\u8868"); ws.append(["\u8d77\u59cb\u65e5\u671f", week.strftime("%Y-%m-%d") if week else "", "\u7ed3\u675f\u65e5\u671f", period_end.strftime("%Y-%m-%d") if period_end else ""]); ws.append([])
    labels = ["\u6bcf\u5468\u6536\u5165","\u6bcf\u5468\u652f\u51fa","\u80fd\u6e90\u652f\u51fa","\u71c3\u6599\u652f\u51fa","\u7ef4\u62a4\u652f\u51fa","\u9a7e\u9a76\u5458\u652f\u51fa","\u5f85\u4ed8\u652f\u51fa","\u7ef4\u62a4\u9700\u6c42","\u7535\u529b\u6d88\u8017","\u71c3\u6599\u6d88\u8017","\u53f8\u673a\u9700\u6c42"]
    for ci, key in enumerate(keys):
        ws.append([company(key)]); ws.append(["\u8fd0\u8f93\u5236\u5f0f"] + labels)
        for md in modes:
            r = by.get((md, key), {}); meta_row = next((x for x in companies if x.get("\u516c\u53f8\u540d\u79f0") == key), {}); total,e,f,m,d = costs(r, meta_row); ws.append([md, money(r.get("\u6536\u5165\u7d2f\u8ba1")), total,e,f,m,d,money(r.get("\u5f85\u4ed8\u652f\u51fa")),integer(r.get("\u7ef4\u62a4\u9700\u6c42")),integer(r.get("\u7535\u529b\u6d88\u8017")),integer(r.get("\u71c3\u6599\u6d88\u8017")),integer(r.get("\u53f8\u673a\u9700\u6c42"))])
        if ci < len(keys)-1: ws.append([])
    reporter.progress('company_workbook', 4, 5)
    # Keep the workbook unstyled while sizing every column to its contents.
    for sheet in wb.worksheets:
        widths = {}
        for row in sheet.iter_rows():
            for cell in row:
                value = "" if cell.value is None else str(cell.value)
                widths[cell.column] = max(widths.get(cell.column, 0), len(value))
        for column, width in widths.items():
            sheet.column_dimensions[sheet.cell(1, column).column_letter].width = min(max(width + 2, 10), 32)
    out = EXPORT / f"CIM2_\u516c\u53f8\u4fe1\u606f\u6574\u7406_{TAG}.xlsx"; wb.save(out)
    reporter.progress('company_workbook', 5, 5)
    reporter.finish('company_workbook')
    print(out)
if __name__ == "__main__": main()
