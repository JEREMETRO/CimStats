"""Portable desktop launcher and embedded parser backend entry point."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# The lxml incremental writer can fail inside a PyInstaller one-file process
# while openpyxl's standard-library XML writer is stable for these workbooks.
if getattr(sys, "frozen", False):
    os.environ["OPENPYXL_LXML"] = "False"

# The one-file build reuses this executable for the isolated parser process.
# Keep the dispatch before importing Qt so the backend child has no GUI setup.
if len(sys.argv) > 1 and sys.argv[1] == "--backend":
    from parser_backend import main as backend_main
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    raise SystemExit(backend_main())

if len(sys.argv) == 3 and sys.argv[1] == '--map-geometry-worker':
    from map_geometry import worker_main
    worker_main(sys.argv[2])
    raise SystemExit(0)

if len(sys.argv) == 3 and sys.argv[1] == '--map-direction-worker':
    from map_geometry import direction_worker_main
    direction_worker_main(sys.argv[2])
    raise SystemExit(0)

FRONTEND = ROOT / "frontend"
if str(FRONTEND) not in sys.path:
    sys.path.insert(0, str(FRONTEND))


def prepare_embedded_qt():
    """Make bundled Qt/Shiboken native dependencies discoverable on Windows."""
    if not getattr(sys, "frozen", False):
        return
    bundle = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    dll_dirs = [bundle, bundle / "PySide6", bundle / "shiboken6"]
    existing_path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join([*(str(path) for path in dll_dirs), existing_path])
    handles = []
    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory:
        for path in dll_dirs:
            if path.exists():
                handles.append(add_dll_directory(str(path)))
    # Keep AddDllDirectory handles alive for the lifetime of the GUI process.
    sys._cim2_qt_dll_handles = handles
    # Do not preload PySide6/Shiboken extension modules with ctypes.  They
    # depend on the embedded Python runtime and Qt module initialization; a
    # direct WinDLL load can fail with WinError 127 before Python imports them.
    # PATH/AddDllDirectory above is sufficient once the complete native DLL
    # closure (including ICU) is present in the one-file extraction.


prepare_embedded_qt()

# Worker dispatch precedes any bootstrap or desktop import.
if len(sys.argv) == 5 and sys.argv[1] == '--startup-splash':
    from startup_splash import run_splash
    raise SystemExit(run_splash(int(sys.argv[2]), sys.argv[3], Path(sys.argv[4])))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--ui-smoke':
        from package_smoke import main as smoke_main
        return smoke_main(ROOT / 'CIM2_SaveStats.py', sys.argv[2:])
    from startup_bootstrap import main as bootstrap_main
    return bootstrap_main(ROOT / 'CIM2_SaveStats.py')


if __name__ == "__main__":
    raise SystemExit(main())
