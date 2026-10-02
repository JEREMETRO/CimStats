"""Exercise the exact frozen candidate before it can be published."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from openpyxl import load_workbook
from app_paths import jobs_directory
from release_checks import verify_package, sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate', type=Path)
    parser.add_argument('saves', type=Path, nargs='+')
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    record = verify_package(candidate / 'package')
    exe = candidate / 'package/CIM2_SaveStats.exe'
    proof = {'source_commit': record['source_commit'], 'exe_sha256': sha256(exe), 'passed': False, 'saves': []}
    # A failed rerun must revoke earlier evidence for the same executable.
    (candidate / 'validation.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf-8')
    for save in args.saves:
        save = save.resolve(strict=True)
        job = jobs_directory(exe.parent) / f'release-{record["version"]}-{uuid.uuid4().hex}'
        job.mkdir(parents=True)
        original_hash = sha256(save)
        env = os.environ.copy()
        env.update(CIM2_EXPORT_DIR=str(job), CIM2_PAYLOAD_DIR=str(job), PYTHONIOENCODING='utf-8')
        proc = subprocess.run([str(exe), '--backend', str(save), 'auto'], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
        output = proc.stdout.decode('utf-8', errors='strict')
        (job / 'backend.log').write_text(output, encoding='utf-8')
        if proc.returncode or sha256(save) != original_hash:
            raise RuntimeError(f'Backend failed or input changed: {save}\n{output}')
        workbooks = list(job.glob('*.xlsx'))
        if len(workbooks) != 2:
            raise RuntimeError(f'Expected two workbooks: {job}')
        for path in workbooks:
            wb = load_workbook(path, read_only=True, data_only=True)
            try:
                if any(cell.data_type == 'e' for sheet in wb for row in sheet for cell in row):
                    raise RuntimeError(f'Workbook contains error cells: {path}')
            finally:
                wb.close()
        proof['saves'].append({'name': save.name, 'input_sha256': original_hash, 'job': str(job), 'passed': True})
        print(f'Passed: {save.name}', flush=True)
    proof['passed'] = True
    (candidate / 'validation.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
