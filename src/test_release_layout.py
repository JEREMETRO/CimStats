import hashlib
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize('relative', ['dist', 'archive/versions/v0.5.1/package', 'build/staging/v0.5.1/package'])
def test_jobs_stay_at_workspace_root(tmp_path, relative):
    from app_paths import jobs_directory
    (tmp_path / '.savestats-workspace').write_text('CIM2_SaveStats', encoding='utf-8')
    app_dir = tmp_path / relative
    app_dir.mkdir(parents=True)
    assert jobs_directory(app_dir) == tmp_path / 'jobs'


def test_standalone_uses_local_app_data(tmp_path, monkeypatch):
    from app_paths import jobs_directory
    original_is_file = Path.is_file
    # This fixture may live below the actual workspace. Simulate a standalone
    # location with no workspace marker rather than inheriting the real one.
    monkeypatch.setattr(Path, 'is_file', lambda path: False if path.name == '.savestats-workspace' else original_is_file(path))
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'local'))
    assert jobs_directory(tmp_path / 'portable') == tmp_path / 'local/CIM2_SaveStats/jobs'


def package(tmp_path):
    root = tmp_path / 'package'
    root.mkdir()
    (root / 'CIM2_SaveStats.exe').write_bytes(b'candidate exe')
    (root / 'README.md').write_text('readme', encoding='utf-8')
    record = {'version': '0.5.1', 'source_commit': 'a' * 40, 'files': {}}
    for name in ['CIM2_SaveStats.exe', 'README.md']:
        record['files'][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    (root / 'VERSION.json').write_text(json.dumps(record), encoding='utf-8')
    return root


def test_verify_valid_package(tmp_path):
    from release_checks import verify_package
    assert verify_package(package(tmp_path))['version'] == '0.5.1'


@pytest.mark.parametrize('extra', ['jobs', 'repaired', 'old.exe'])
def test_package_rejects_extra_content(tmp_path, extra):
    from release_checks import verify_package
    root = package(tmp_path)
    (root / extra).mkdir()
    with pytest.raises(ValueError):
        verify_package(root)


def test_package_rejects_modified_executable(tmp_path):
    from release_checks import verify_package
    root = package(tmp_path)
    (root / 'CIM2_SaveStats.exe').write_bytes(b'other version')
    with pytest.raises(ValueError):
        verify_package(root)


def test_validation_cannot_be_reused_for_another_binary(tmp_path):
    from release_checks import verify_candidate
    root = package(tmp_path)
    (tmp_path / 'validation.json').write_text(json.dumps({'exe_sha256': '0' * 64, 'passed': True}), encoding='utf-8')
    with pytest.raises(ValueError):
        verify_candidate(tmp_path)


def test_failed_rerun_invalidates_old_validation(tmp_path, monkeypatch):
    from verify_candidate import main
    root = package(tmp_path)
    metadata = json.loads((root / 'VERSION.json').read_text(encoding='utf-8'))
    proof = {'exe_sha256': metadata['files']['CIM2_SaveStats.exe'],
             'source_commit': metadata['source_commit'], 'passed': True, 'saves': [{'passed': True}]}
    (tmp_path / 'validation.json').write_text(json.dumps(proof), encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['verify_candidate', str(tmp_path), str(tmp_path / 'missing.save')])
    with pytest.raises(FileNotFoundError):
        main()
    assert json.loads((tmp_path / 'validation.json').read_text(encoding='utf-8'))['passed'] is False


def test_candidate_accepts_matching_validation(tmp_path):
    from release_checks import verify_candidate
    root = package(tmp_path)
    metadata = json.loads((root / 'VERSION.json').read_text(encoding='utf-8'))
    proof = {'exe_sha256': metadata['files']['CIM2_SaveStats.exe'],
             'source_commit': metadata['source_commit'], 'passed': True, 'saves': [{'passed': True}]}
    (tmp_path / 'validation.json').write_text(json.dumps(proof), encoding='utf-8')
    assert verify_candidate(tmp_path)['version'] == '0.5.1'
