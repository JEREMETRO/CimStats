"""Writable job storage is separate from immutable release packages."""
import os
from pathlib import Path


def jobs_directory(app_dir: Path) -> Path:
    app_dir = app_dir.resolve()
    for parent in (app_dir, *app_dir.parents):
        marker = parent / '.savestats-workspace'
        if marker.is_file() and marker.read_text(encoding='utf-8').strip() == 'CIM2_SaveStats':
            return parent / 'jobs'
    local = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local')))
    return local / 'CIM2_SaveStats' / 'jobs'


def application_version(bundle: Path) -> str:
    return (bundle / 'VERSION').read_text(encoding='utf-8').strip()
