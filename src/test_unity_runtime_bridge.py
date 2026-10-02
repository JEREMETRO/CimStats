from pathlib import Path
from unity_runtime_bridge import UnityBridge, UnityRuntime


def test_bridge_refuses_without_helper(tmp_path: Path):
    save = tmp_path / "中文.save"
    save.write_bytes(b"safe")
    result = UnityBridge(tmp_path / "jobs", UnityRuntime(Path("C:/missing/CIM2.exe"), Path("C:/missing"))).edit(save, {})
    assert result.status == "rejected"
    assert result.output is None
    assert (tmp_path / "jobs" / result.job_id / "original.save.copy").read_bytes() == b"safe"


def test_bridge_rejects_bad_extension(tmp_path: Path):
    bad = tmp_path / "x.bin"
    bad.write_bytes(b"x")
    try:
        UnityBridge(tmp_path).edit(bad, {})
    except ValueError:
        return
    raise AssertionError("expected extension validation")
