"""Optional Unity Player bridge for guarded CIM2 save editing.

This module is intentionally inert by default.  It never patches the game
installation and never writes a save unless an external, explicitly supplied
bridge executable reports a successful in-process round-trip.  The desktop
application can import this module without requiring Unity or pythonnet.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid


@dataclass(frozen=True)
class UnityRuntime:
    player: Path
    managed: Path
    version: str = "v1.6.3"


@dataclass(frozen=True)
class RuntimeResult:
    status: str
    job_id: str
    output: Path | None
    log: Path
    message: str


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def discover(search_roots: list[Path] | None = None) -> list[UnityRuntime]:
    """Find installed CIM2 players without modifying any installation."""
    roots = search_roots or [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)")),
        Path(os.environ.get("PROGRAMFILES", r"C:\\Program Files")),
        Path("D:/Program Files (x86)"), Path("D:/SteamLibrary"),
    ]
    found: list[UnityRuntime] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        try:
            candidates = root.glob("**/Cities in Motion 2/CIM2.exe")
        except OSError:
            continue
        for player in candidates:
            managed = player.parent / "CIM2_Data" / "Managed"
            if player.resolve() in seen or not (managed / "Assembly-CSharp.dll").exists():
                continue
            seen.add(player.resolve())
            found.append(UnityRuntime(player.resolve(), managed.resolve()))
    return found


class UnityBridge:
    """Launch-only bridge; actual mutation requires a trusted helper."""

    def __init__(self, jobs_root: Path, runtime: UnityRuntime | None = None):
        self.jobs_root = Path(jobs_root)
        self.runtime = runtime

    def edit(self, save_path: Path, changes: dict, helper: Path | None = None) -> RuntimeResult:
        save_path = Path(save_path)
        if save_path.suffix.lower() != ".save":
            raise ValueError("输入文件必须是 .save")
        if not save_path.exists():
            raise FileNotFoundError(save_path)
        job = self.jobs_root / ("unity_" + uuid.uuid4().hex)
        job.mkdir(parents=True, exist_ok=False)
        original = job / "original.save.copy"
        shutil.copy2(save_path, original)
        (job / "changes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=2), encoding="utf-8")
        log = job / "unity.log"
        if self.runtime is None:
            log.write_text("Unity runtime not configured; no process started.\n", encoding="utf-8")
            return RuntimeResult("rejected", job.name, None, log, "未配置 Unity 运行时")
        if helper is None or not Path(helper).exists():
            log.write_text("No in-process bridge helper supplied; refusing mutation.\n", encoding="utf-8")
            return RuntimeResult("rejected", job.name, None, log, "缺少进程内桥接插件，已拒绝写回")
        output = job / "modified.save"
        manifest = job / "request.json"
        manifest.write_text(json.dumps({"input": str(original), "output": str(output), "changes": changes}, ensure_ascii=False, indent=2), encoding="utf-8")
        with log.open("w", encoding="utf-8") as stream:
            proc = subprocess.run([str(helper), str(manifest)], cwd=str(job), stdout=stream, stderr=subprocess.STDOUT, check=False)
        if proc.returncode != 0 or not output.exists():
            return RuntimeResult("rejected", job.name, None, log, "Unity 桥接进程失败，未生成存档")
        return RuntimeResult("pending_validation", job.name, output, log, "已生成候选文件，必须通过重新解析校验")

    def probe(self, seconds: int = 12) -> RuntimeResult:
        """Start the player in an isolated process and collect initialization logs."""
        if self.runtime is None:
            raise ValueError("未配置 Unity 运行时")
        job = self.jobs_root / ("probe_" + uuid.uuid4().hex)
        job.mkdir(parents=True, exist_ok=False)
        log = job / "unity.log"
        with log.open("w", encoding="utf-8") as stream:
            proc = subprocess.Popen([str(self.runtime.player), "-batchmode", "-nographics", "-no-dialogs", "-logFile", str(log)], cwd=str(self.runtime.player.parent), stdout=stream, stderr=subprocess.STDOUT)
            try:
                proc.wait(timeout=max(1, int(seconds)))
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            code = proc.returncode
        if code not in (0, None):
            return RuntimeResult("rejected", job.name, None, log, f"Unity Player 退出码 {code}")
        return RuntimeResult("probe_only", job.name, None, log, "Unity 已启动；未执行存档写回")
