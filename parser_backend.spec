# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH)
datas = [
    (str(root / "src"), "src"),
    (str(root / "data" / "Assembly-CSharp.probe.dll"), "data"),
    (str(root / "data" / "UnityEngine.dll"), "data"),
]
a = Analysis(
    [str(root / "parser_backend.py")],
    pathex=[str(root), str(root / "src")],
    binaries=[], datas=datas,
    hiddenimports=collect_submodules("clr") + [
        "clr", "pythonnet", "openpyxl", "openpyxl.cell", "openpyxl.chart",
        "openpyxl.descriptors", "openpyxl.formatting", "openpyxl.packaging",
        "openpyxl.styles", "openpyxl.utils", "openpyxl.worksheet", "openpyxl.xml",
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=["tkinter"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="parser_backend", debug=False,
         bootloader_ignore_signals=False, strip=False, upx=False, console=True)
