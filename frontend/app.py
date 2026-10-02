from __future__ import annotations

import csv
import os
import subprocess
import sys
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

PROJECT = Path(__file__).resolve().parents[1]
SRC = PROJECT / "src"
sys.path.insert(0, str(SRC))
from display_rules import format_line_name
EXPORT = PROJECT / "exports"
UPLOADS = PROJECT / "frontend" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024
latest = {"tag": None, "files": {}}


def tag_for(path: Path) -> str:
    return "运行时" if path.stem == "望春市6" else f"{path.stem}_运行时"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def run_parser(save_path: Path) -> tuple[str, dict[str, Path]]:
    tag = tag_for(save_path)
    env = os.environ.copy()
    env["CIM2_EXPORT_DIR"] = str(EXPORT)
    env["PYTHONIOENCODING"] = "utf-8"
    commands = [
        [sys.executable, str(SRC / "extract_runtime_data.py"), str(save_path)],
        [sys.executable, str(SRC / "build_line_workbook.py"), tag],
        [sys.executable, str(SRC / "build_company_workbook.py"), tag],
    ]
    logs = []
    for command in commands:
        completed = subprocess.run(command, cwd=PROJECT, env=env, text=True,
                                   capture_output=True, encoding="utf-8", timeout=300)
        logs.append(completed.stdout + completed.stderr)
        if completed.returncode:
            raise RuntimeError(logs[-1][-4000:])
    files = {
        "line_workbook": EXPORT / f"CIM2_线路发班整理_{tag}.xlsx",
        "company_workbook": EXPORT / f"CIM2_公司信息整理_{tag}.xlsx",
        "lines": EXPORT / f"CIM2_线路客流_完整导出_{tag}.csv",
        "timetables": EXPORT / f"CIM2_发班信息_完整导出_{tag}.csv",
        "departures": EXPORT / f"CIM2_发班记录_完整导出_{tag}.csv",
        "metadata": EXPORT / f"CIM2_城市历史元数据_{tag}.csv",
    }
    latest.update({"tag": tag, "files": files, "logs": logs})
    return tag, files


def line_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("公司名称", ""), row.get("线路类型", ""), row.get("线路号", "")


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/parse")
def parse_upload():
    upload = request.files.get("save")
    if upload is None or not upload.filename.lower().endswith(".save"):
        return jsonify({"error": "请选择 .save 存档文件"}), 400
    target = UPLOADS / f"{uuid.uuid4().hex}_{Path(upload.filename).name}"
    upload.save(target)
    try:
        tag, files = run_parser(target)
        lines = read_csv(files["lines"])
        timetables = read_csv(files["timetables"])
        departures = read_csv(files["departures"])
        grouped = {}
        for row in lines:
            row["线路名称"] = format_line_name(row.get("线路号"), row.get("线路名称"))
            grouped.setdefault(line_key(row), row)
        return jsonify({
            "tag": tag,
            "count": len(grouped),
            "lines": list(grouped.values()),
            "timetables": timetables,
            "departures": departures,
            "downloads": {key: f"/api/download/{key}" for key in ("line_workbook", "company_workbook")},
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/api/download/<kind>")
def download(kind: str):
    path = latest.get("files", {}).get(kind)
    if path is None or not path.exists():
        return jsonify({"error": "尚未生成该文件"}), 404
    return send_file(path, as_attachment=True, download_name=path.name)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("CIM2_PORT", "8765")), debug=False)
