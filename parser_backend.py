"""Run the three existing report stages inside the packaged backend process."""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def root_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def run_script(path: Path, args: list[str]) -> None:
    old_argv = sys.argv
    try:
        sys.argv = [str(path), *args]
        runpy.run_path(str(path), run_name="__main__")
    finally:
        sys.argv = old_argv


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: parser_backend <save> <tag>", file=sys.stderr)
        return 2
    root = root_dir()
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    save = sys.argv[1]
    # extract_runtime_data.py derives its output suffix from the save stem.
    # Normalize the backend tag to the same rule so a manual/legacy caller
    # cannot request a suffix for which no CSVs were produced.
    save_stem = Path(save).stem
    tag = "运行时" if save_stem == "望春市6" else f"{save_stem}_运行时"
    # A frozen backend owns its extracted probe/runtime dependencies.  Do not
    # inherit the GUI process's _MEIPASS path, which belongs to another
    # one-file executable.
    os.environ["CIM2_RUNTIME_DATA_DIR"] = str(root / "data")
    # The frozen parser and its probe must use the same embedded assembly.
    # The GUI may locate an installed game for discovery, but that install
    # can change independently (for example, when a mod updates it).
    if getattr(sys, "frozen", False):
        os.environ["CIM2_MANAGED_ROOT"] = str(root / "game_runtime" / "Managed")
    else:
        os.environ.setdefault("CIM2_MANAGED_ROOT", str(root / "game_runtime" / "Managed"))
    run_script(src / "extract_runtime_data.py", [save])
    run_script(src / "build_line_workbook.py", [tag])
    run_script(src / "build_company_workbook.py", [tag])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
