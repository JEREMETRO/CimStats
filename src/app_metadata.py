"""Lightweight CimStats identity shared by the launcher, desktop and about page.

Importing this module loads only the Python standard library. Version text is
read from the single bundled VERSION file when requested, never duplicated here.
Third-party and proprietary materials retain their own license terms.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

APP_NAME = 'CimStats'
APP_AUTHOR = 'JEREMETRO'
PROJECT_LICENSE_SPDX = 'GPL-3.0-only'
PROJECT_LICENSE_NAME = 'GNU General Public License v3.0'
PROJECT_LICENSE_SCOPE = '项目自有源代码；第三方组件与游戏运行库分别适用其原有许可'
COPYRIGHT_NOTICE = f'Copyright © 2026 {APP_AUTHOR}'
NO_WARRANTY_NOTICE = '本软件按现状提供，不附带任何担保。'
REDISTRIBUTION_NOTICE = '项目自有源代码可按 GNU GPL v3 条款修改和再分发。'
TECHNICAL_APPLICATION_NAME = 'CIM2 SaveStats'
WINDOWS_APP_ID = 'CimStats.Desktop'
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256, 512)


@dataclass(frozen=True)
class ApplicationMetadata:
    name: str
    version: str
    author: str
    license_spdx: str
    license_name: str
    license_scope: str
    copyright_notice: str = COPYRIGHT_NOTICE
    no_warranty_notice: str = NO_WARRANTY_NOTICE
    redistribution_notice: str = REDISTRIBUTION_NOTICE


def bundle_root() -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


def application_version(root: Path | None = None) -> str:
    return ((root or bundle_root()) / 'VERSION').read_text(encoding='utf-8-sig').strip()


def application_metadata(root: Path | None = None) -> ApplicationMetadata:
    return ApplicationMetadata(APP_NAME, application_version(root), APP_AUTHOR,
                               PROJECT_LICENSE_SPDX, PROJECT_LICENSE_NAME, PROJECT_LICENSE_SCOPE)


def icon_directory(root: Path | None = None) -> Path:
    return (root or bundle_root()) / 'frontend' / 'static' / 'branding' / 'cimstats'


def icon_png_paths(root: Path | None = None) -> tuple[tuple[int, Path], ...]:
    directory = icon_directory(root)
    return tuple((size, directory / f'cimstats-{size}.png') for size in ICON_SIZES)


def icon_svg_path(root: Path | None = None) -> Path:
    return icon_directory(root) / 'cimstats-symbol.svg'


def project_license_path(root: Path | None = None) -> Path:
    return (root or bundle_root()) / 'LICENSE'


def third_party_notices_path(root: Path | None = None) -> Path:
    return (root or bundle_root()) / 'THIRD_PARTY_NOTICES.md'


if __name__ == '__main__':
    from dataclasses import asdict
    import json
    print(json.dumps(asdict(application_metadata()), ensure_ascii=False))
