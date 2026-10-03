# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
import re
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from importlib.metadata import distribution
from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct

root = Path(SPECPATH)
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
from app_metadata import application_metadata, icon_directory
from candidate_package import bundle_data, managed_data
metadata = application_metadata(root)
if metadata.name != 'CimStats' or metadata.version != (root / 'VERSION').read_text(encoding='utf-8-sig').strip():
    raise RuntimeError('Integrate and freeze the approved CimStats VERSION before building')
if os.environ.get('CIMSTATS_LOCAL_REVIEW_BUILD') != '1':
    raise RuntimeError('This spec is a local review candidate; invoke the guarded build script')
if not re.fullmatch(r'\d+\.\d+\.\d+', metadata.version):
    raise ValueError('VERSION must contain major.minor.patch')
version_parts = tuple(map(int, metadata.version.split('.'))) + (0,)
if any(part > 65535 for part in version_parts): raise ValueError('Windows version components exceed 16 bits')
version_resource = VSVersionInfo(
    ffi=FixedFileInfo(filevers=version_parts, prodvers=version_parts),
    kids=[StringFileInfo([StringTable('080404B0', [
        StringStruct('FileDescription', metadata.name), StringStruct('ProductName', metadata.name),
        StringStruct('CompanyName', metadata.author), StringStruct('FileVersion', metadata.version),
        StringStruct('ProductVersion', metadata.version), StringStruct('OriginalFilename', 'CimStats.exe'),
        StringStruct('InternalName', 'CimStats'), StringStruct('LegalCopyright', metadata.copyright_notice),
        StringStruct('Comments', metadata.license_spdx),
    ])]), VarFileInfo([VarStruct('Translation', [2052, 1200])])],
)
hiddenimports = collect_submodules("PySide6.QtCharts") + collect_submodules("clr") + [
    "clr", "pythonnet", "clr_loader",
]
managed_root_arg = os.environ.get("CIM2_BUILD_MANAGED_ROOT")
probe_arg = os.environ.get("CIM2_BUILD_PROBE_PATH")
if not managed_root_arg or not probe_arg:
    raise RuntimeError("Build must provide a fresh staged Managed root and probe")
managed_root = Path(managed_root_arg)
probe_path = Path(probe_arg)
if not managed_root.exists() or not probe_path.exists():
    raise RuntimeError("Fresh staged runtime or probe is missing")
runtime_datas = managed_data(managed_root)
fluent_datas = collect_data_files("qfluentwidgets")
for package in ("PySide6-Fluent-Widgets", "PySideSix-Frameless-Window", "darkdetect", "PySide6", "PySide6_Addons", "PySide6_Essentials", "shiboken6", "pythonnet", "clr_loader", "openpyxl", "psutil", "cffi", "pycparser", "et_xmlfile", "packaging", "PyInstaller"):
    dist = distribution(package)
    for entry in dist.files or ():
        if any(token in str(entry).lower() for token in ('license', 'copying')) and Path(dist.locate_file(entry)).is_file() and not str(entry).lower().endswith(('.dll','.pyd','.exe')):
            fluent_datas.append((str(dist.locate_file(entry)), "licenses/" + package + '-' + dist.version + '/' + str(Path(entry).parent)))
cpython_license = Path(sys.base_prefix) / 'LICENSE.txt'
if not cpython_license.is_file(): raise RuntimeError('Build interpreter is missing its original CPython LICENSE.txt')
fluent_datas.append((str(cpython_license), 'licenses/CPython-' + '.'.join(map(str, sys.version_info[:3]))))
# Explicit project data: no docs/static/src directory recursion or evidence caches.
project_datas = bundle_data(root)
pyside_dir = Path(distribution('PySide6').locate_file('PySide6'))
shiboken_dir = Path(distribution('shiboken6').locate_file('shiboken6'))
system32 = Path(os.environ.get("WINDIR", r"C:\\Windows")) / "System32"

a = Analysis(
    [str(root / "CIM2_SaveStats.py")],
    pathex=[str(root), str(root / "frontend"), str(root / "src")],
    datas=[
        *project_datas,
        (str(probe_path), "data"),
        (str(root / "data" / "UnityEngine.dll"), "data"),
        *runtime_datas,
        *fluent_datas,
    ],
    binaries=[
        # Keep a flat copy of Qt's loader dependencies.  Some Windows loader
        # configurations do not resolve a DLL imported by PySide6/*.pyd from
        # a sibling package directory in a one-file extraction.
        (str(pyside_dir / name), ".")
        for name in ("Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll", "Qt6Charts.dll", "Qt6Network.dll", "Qt6OpenGL.dll", "Qt6OpenGLWidgets.dll", "pyside6.abi3.dll", "MSVCP140.dll", "MSVCP140_1.dll", "MSVCP140_2.dll", "VCRUNTIME140.dll", "VCRUNTIME140_1.dll")
        if (pyside_dir / name).exists()
    ] + [
        (str(shiboken_dir / name), ".")
        for name in ("shiboken6.abi3.dll",)
        if (shiboken_dir / name).exists()
    ] + [
        # Qt6Core imports the generic ICU DLL name.  On machines with
        # Anaconda/other ICU builds earlier on PATH, Qt can otherwise bind to
        # a versioned ICU ABI that lacks the unversioned symbols it imports.
        (str(system32 / name), ".")
        for name in ("icu.dll", "icuin.dll", "icuuc.dll")
        if (system32 / name).exists()
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "_pytest", "Cython", "IPython", "UnityPy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="CimStats",
    version=version_resource,
    icon=str(icon_directory(root) / 'cimstats.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
