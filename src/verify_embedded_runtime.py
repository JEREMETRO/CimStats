"""Verify the frozen EXE contains the exact staged, audited game dependencies."""
import hashlib
import json
import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

EXPECTED_BASE = '2bd1ca1353c228fbbcc04df2355d9cbc545f29ddd06ec1c10a6dd62d7bfda4d2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    exe, base, probe, dependencies, staged, output = map(Path, sys.argv[1:7])
    if sha(base.read_bytes()) != EXPECTED_BASE:
        raise RuntimeError('Base assembly hash differs from the audited original')
    archive = CArchiveReader(str(exe))
    expected = {'data\\Assembly-CSharp.probe.dll': probe}
    for path in staged.glob('*.dll'):
        if path.name.lower() != 'mscorlib.dll':
            expected['game_runtime\\Managed\\' + path.name] = path
    if not expected:
        raise RuntimeError('No staged runtime DLLs')
    entries = {}
    for name, path in expected.items():
        source_hash = sha(path.read_bytes())
        embedded_hash = sha(archive.extract(name))
        if source_hash != embedded_hash:
            raise RuntimeError(f'Embedded content differs from staged file: {name}')
        entries[name] = embedded_hash
    if entries['game_runtime\\Managed\\Assembly-CSharp.dll'] != EXPECTED_BASE:
        raise RuntimeError('EXE embeds a different game assembly')
    proof = {
        'audited_base_path': str(base.resolve()),
        'audited_base_sha256': EXPECTED_BASE,
        'fresh_probe_path': str(probe.resolve()),
        'fresh_probe_sha256': sha(probe.read_bytes()),
        'dependency_directory': str(dependencies.resolve()),
        'staged_managed_directory': str(staged.resolve()),
        'exe_path': str(exe.resolve()),
        'exe_sha256': sha(exe.read_bytes()),
        'embedded_entry_sha256': entries,
        'passed': True,
    }
    output.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Verified {len(entries)} exact embedded runtime/probe entries; base {EXPECTED_BASE}')


if __name__ == '__main__':
    main()
