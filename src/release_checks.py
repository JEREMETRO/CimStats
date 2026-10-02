"""Read-only release verification shared by build, publish and tests."""
import hashlib
import json
import re
from pathlib import Path

PACKAGE_FILES = {'CIM2_SaveStats.exe', 'README.md', 'VERSION.json'}


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_package(root: Path) -> dict:
    entries = list(root.iterdir())
    if {p.name for p in entries} != PACKAGE_FILES or not all(p.is_file() and not p.is_symlink() for p in entries):
        raise ValueError(f'Package must contain exactly {sorted(PACKAGE_FILES)}: {root}')
    record = json.loads((root / 'VERSION.json').read_text(encoding='utf-8-sig'))
    if not re.fullmatch(r'\d+\.\d+\.\d+', record.get('version', '')):
        raise ValueError('Invalid release version')
    if not re.fullmatch(r'[0-9a-f]{40}', record.get('source_commit', '')):
        raise ValueError('Missing source commit')
    if set(record.get('files', {})) != PACKAGE_FILES - {'VERSION.json'}:
        raise ValueError('Incomplete package checksums')
    for name, expected in record['files'].items():
        if sha256(root / name) != expected:
            raise ValueError(f'Checksum mismatch: {name}')
    return record


def verify_candidate(root: Path) -> dict:
    record = verify_package(root / 'package')
    proof = json.loads((root / 'validation.json').read_text(encoding='utf-8-sig'))
    if (proof.get('passed') is not True
            or proof.get('source_commit') != record['source_commit']
            or proof.get('exe_sha256') != record['files']['CIM2_SaveStats.exe']
            or not proof.get('saves')
            or not all(row.get('passed') is True for row in proof['saves'])):
        raise ValueError('Missing validation for this exact executable/source')
    return record


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=['package', 'candidate'])
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    result = (verify_candidate if args.kind == 'candidate' else verify_package)(args.path)
    print(f"Verified {result['version']} at {args.path}")
