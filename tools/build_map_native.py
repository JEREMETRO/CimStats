"""Build the small, CRT-free Windows GL submission helper from reviewed C.

Zig is a build dependency only; the shipped application needs no compiler.
Set CIMSTATS_ZIG to the zig executable, or install ziglang in the build env.
"""
from pathlib import Path
import argparse
import importlib.util
import os
import shutil
import subprocess


def build(root,output=None):
    root=Path(root).resolve()
    source=root/'frontend/native/map_gpu_submit.c'
    output=Path(output or root/'build/native/map_gpu_submit.dll').resolve()
    zig=os.environ.get('CIMSTATS_ZIG') or shutil.which('zig')
    if not zig:
        spec=importlib.util.find_spec('ziglang')
        if spec and spec.submodule_search_locations:
            zig=str(Path(next(iter(spec.submodule_search_locations)))/'zig.exe')
    if not zig or not Path(zig).is_file():
        raise RuntimeError('Install ziglang==0.15.2 in the build environment or set CIMSTATS_ZIG')
    output.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([zig,'cc','-target','x86_64-windows-msvc','-shared','-O2',
        '-ffreestanding','-fno-math-errno','-fno-stack-protector','-nostdlib',str(source),'-o',str(output)],
        check=True,cwd=root)
    if not output.is_file():raise RuntimeError('Native map helper was not produced')
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path)
    args=p.parse_args();print(build(Path(__file__).resolve().parents[1],args.output))
