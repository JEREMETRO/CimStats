"""Safe orchestration for timetable edits.

Assembly-specific mutation is injected through a backend adapter. The service
owns backups, snapshots, validation and output policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import shutil
import uuid

from save_container import locate_payload
from unity_runtime_bridge import UnityBridge


@dataclass
class EditResult:
    job_id: str
    output: Path | None
    status: str
    warnings: list[str]
    validation: dict


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_snapshot(before: dict, after: dict, changed_lines: set[str]) -> list[str]:
    errors = []
    for key in ("company_count", "line_count", "vehicle_count"):
        if before.get(key) != after.get(key):
            errors.append(f"{key} changed: {before.get(key)} -> {after.get(key)}")
    before_lines = before.get("lines", {})
    after_lines = after.get("lines", {})
    if set(before_lines) != set(after_lines):
        errors.append("线路对象集合发生变化")
    for key in set(before_lines) & set(after_lines):
        if key in changed_lines:
            continue
        if before_lines[key] != after_lines[key]:
            errors.append(f"非目标线路发生变化: {key}")
    return errors


class SaveEditorService:
    def __init__(self, jobs_root: Path):
        self.jobs_root = jobs_root

    def prepare_job(self, save_path: Path) -> tuple[Path, Path]:
        if save_path.suffix.lower() != ".save":
            raise ValueError("输入文件必须是 .save")
        if not save_path.exists():
            raise FileNotFoundError(save_path)
        job = self.jobs_root / uuid.uuid4().hex
        job.mkdir(parents=True, exist_ok=False)
        original = job / "original.save.copy"
        shutil.copy2(save_path, original)
        return job, original

    def inspect_container(self, save_path: Path) -> dict:
        location, payload = locate_payload(save_path)
        return {"offset": location.offset, "compressed_size": location.compressed_size, "payload_size": len(payload), "sha256": file_hash(save_path)}

    def write_report(self, job: Path, name: str, data: dict) -> None:
        (job / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def apply_with_adapter(self, save_path: Path, output_path: Path, adapter, changes: dict) -> EditResult:
        """Run a guarded edit using an assembly-specific adapter.

        The adapter must implement ``load_snapshot(path)``, ``apply_changes``
        and ``serialize(path, root, payload_location)``. Keeping these hooks
        explicit prevents the UI from silently writing incomplete object graphs.
        """
        job, original = self.prepare_job(save_path)
        warnings = []
        try:
            before = adapter.load_snapshot(original)
            self.write_report(job, "before.json", before)
            # Mandatory no-op round-trip gate.
            baseline = adapter.round_trip(original, job / "baseline.save")
            baseline_errors = validate_snapshot(before, baseline, set())
            if baseline_errors:
                self.write_report(job, "validation.json", {"status": "rejected", "errors": baseline_errors})
                return EditResult(job.name, None, "rejected", ["无修改 round-trip 校验失败"], {"errors": baseline_errors})
            adapter.apply_changes(changes)
            modified = adapter.serialize(job / "modified.save")
            after = adapter.load_snapshot(modified)
            changed = set(changes.get("line_keys", []))
            errors = validate_snapshot(before, after, changed)
            self.write_report(job, "after.json", after)
            self.write_report(job, "changes.json", changes)
            self.write_report(job, "validation.json", {"status": "ok" if not errors else "rejected", "errors": errors})
            if errors:
                return EditResult(job.name, None, "rejected", ["修改后对象图校验失败"], {"errors": errors})
            output_path = Path(output_path)
            if output_path.resolve() == Path(save_path).resolve():
                raise ValueError("输出文件不能覆盖原始存档")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(modified, output_path)
            return EditResult(job.name, output_path, "ok", warnings, {"errors": []})
        except Exception as exc:
            self.write_report(job, "validation.json", {"status": "error", "error": str(exc)})
            return EditResult(job.name, None, "error", [str(exc)], {"error": str(exc)})

    def apply_with_unity_bridge(self, save_path: Path, output_path: Path, runtime, helper: Path | None, changes: dict, adapter=None) -> EditResult:
        """Run an explicitly supplied in-process Unity helper.

        The helper receives only a copied input and a manifest.  If an adapter
        is supplied, its snapshot validator is run against the helper output;
        otherwise the result remains ``pending_validation`` and is never
        copied to the requested destination.
        """
        bridge = UnityBridge(self.jobs_root, runtime)
        result = bridge.edit(Path(save_path), changes, helper)
        if result.status != "pending_validation" or result.output is None:
            return EditResult(result.job_id, None, result.status, [result.message], {"log": str(result.log)})
        if adapter is None:
            return EditResult(result.job_id, None, "rejected", ["缺少重新解析适配器，候选存档未交付"], {"log": str(result.log)})
        try:
            before = adapter.load_snapshot(Path(save_path))
            after = adapter.load_snapshot(result.output)
            errors = validate_snapshot(before, after, set(changes.get("line_keys", [])))
            job = self.jobs_root / result.job_id
            self.write_report(job, "validation.json", {"status": "ok" if not errors else "rejected", "errors": errors})
            if errors:
                return EditResult(result.job_id, None, "rejected", ["修改后重新解析校验失败"], {"errors": errors})
            destination = Path(output_path)
            if destination.resolve() == Path(save_path).resolve():
                raise ValueError("输出文件不能覆盖原始存档")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(result.output, destination)
            return EditResult(result.job_id, destination, "ok", [], {"errors": []})
        except Exception as exc:
            return EditResult(result.job_id, None, "error", [str(exc)], {"error": str(exc)})
