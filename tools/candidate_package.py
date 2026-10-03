"""Local directory-candidate preparation and read-only verification.

No upload, deletion or dist promotion. 'freeze' writes a reviewed source
inventory; 'finalize' records only an already built unique local candidate.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {'CIM2_SaveStats.py', 'parser_backend.py', 'CIM2_SaveStats.spec', 'parser_backend.spec',
              'build_portable.ps1', 'publish_release.ps1', 'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md',
              'SECURITY.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'AGENTS.md', 'VERSION', 'requirements-desktop.txt',
              'requirements-dev.txt', 'pytest.ini', '.gitignore', '.gitattributes', '.savestats-workspace'}
DOCS = ('docs/USER_GUIDE.md', 'docs/DATA_DEFINITIONS.md', 'docs/DEVELOPMENT.md', 'docs/RELEASE.md',
        'docs/PROJECT_NOTICE.md', 'docs/README.md',
        'docs/requirements/product.md', 'docs/requirements/charts.md', 'docs/requirements/latest-info.md',
        'docs/design/architecture.md', 'docs/design/controls.md', 'docs/design/visual-design.md',
        'docs/reference/history-metrics.md', 'docs/reference/line-metrics.md',
        'docs/reference/runtime-decoding.md', 'docs/reference/field-inventory.md',
        'docs/reference/geometry-and-vehicles.md', 'docs/reference/passenger-routing.md',
        'docs/reference/multiplayer.md', 'docs/reference/tools.md', 'docs/testing/acceptance.md')
SCRIPT_DATA = ('extract_runtime_data.py', 'build_line_workbook.py', 'build_company_workbook.py',
               'display_rules.py', 'save_container.py', 'app_paths.py', 'app_metadata.py', 'history_contract.py', 'parse_events.py')
STATIC = ('frontend/static/app.css', 'frontend/static/app.js', 'frontend/static/cimstats/home-decoration.svg',
          'frontend/templates/index.html')
ICON_DIR = 'frontend/static/branding/cimstats/'
ICON_NAMES = ('cimstats.ico', 'cimstats-symbol.svg', 'cimstats-symbol-16.svg', 'cimstats-symbol-20.svg', 'cimstats-symbol-24.svg',
              *[f'cimstats-{n}.png' for n in (16,20,24,32,40,48,64,96,128,256,512)])
CATALOGS = ('exports/CIM2_车型尺寸速度目录.csv', 'exports/CIM2_道路类型宽度目录.csv')
MANAGED_NAMES = ('Assembly-CSharp-firstpass.dll', 'Assembly-CSharp.dll', 'Assembly-UnityScript-firstpass.dll',
                 'Boo.Lang.dll', 'Ionic.Zlib.dll', 'Mono.Posix.dll', 'Mono.Security.dll', 'SteamworksManaged.dll',
                 'System.Configuration.dll', 'System.Core.dll', 'System.Security.dll', 'System.Xml.dll', 'System.dll', 'UnityEngine.dll')
EXPECTED_BASE = '2bd1ca1353c228fbbcc04df2355d9cbc545f29ddd06ec1c10a6dd62d7bfda4d2'


def selected_documents(): return DOCS


def source_path_allowed(relative, *, license_names=()):
    path = relative.replace('\\', '/')
    parts = PurePosixPath(path).parts
    if not parts or path.startswith('/') or '..' in parts or ':' in path or '__pycache__' in parts: return False
    if path in ROOT_FILES or path in DOCS or path in STATIC or path in CATALOGS: return True
    if path == 'third_party_licenses/PROVENANCE.json' or path in license_names: return True
    if path.startswith(ICON_DIR): return path[len(ICON_DIR):] in ICON_NAMES
    if parts[0] in ('src', 'frontend', 'tools') and path.endswith('.py'): return True
    if parts[0] == 'tools' and path.endswith('.ps1'): return True
    if path in ('optional/save_editing/CIM2RuntimeScheduleBridge.cs', 'optional/save_editing/bridge.rsp', 'optional/save_editing/README.md'): return True
    if path.startswith('.github/') and path.endswith(('.yml', '.yaml', '.md')): return True
    return False


def validate_name(name):
    if not re.fullmatch(r'CimStats-\d+\.\d+\.\d+-review-[A-Za-z0-9-]+', name):
        raise ValueError('Use a unique CimStats-major.minor.patch-review-id directory name')
    return name


def compare_inventory(expected, actual):
    changed = sorted(name for name in expected.keys() | actual.keys() if expected.get(name) != actual.get(name))
    if changed: raise ValueError('Inventory changed: '+', '.join(changed[:20]))


def package_blockers(rows):
    result = []
    for row in rows:
        name = row['path'].replace('\\','/').lower()
        inner = name.removeprefix('_internal/')
        leaf = PurePosixPath(inner).name
        kind = None
        if inner.startswith('game_runtime/') or leaf.startswith(('assembly-csharp', 'assembly-unityscript')) or leaf in ('unityengine.dll','steamworksmanaged.dll'):
            kind = 'game_runtime_redistribution'
        elif (leaf.endswith(('.save','.sav','.zip','.7z','.rar')) and inner != 'base_library.zip') or (inner.startswith('docs/') and leaf.endswith(('.dll','.exe','.pyd'))):
            kind = 'unexpected_payload'
        elif leaf.endswith(('.ttf','.otf','.woff','.woff2')): kind = 'font_clearance'
        if kind: result.append({'path':row['path'], 'sha256':row['sha256'], 'kind':kind})
    return result


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def redirected(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def inside(path, parent):
    path = Path(path).absolute(); parent = Path(parent).resolve()
    if not path.is_relative_to(parent) or path == parent: raise ValueError('Output must stay inside '+str(parent))
    for item in (path, *path.parents):
        if item == parent: break
        if redirected(item): raise ValueError('Redirected path: '+str(item))
    if not path.resolve().is_relative_to(parent): raise ValueError('Resolved path outside allowed root')
    return path


def tree_files(root):
    for current, directories, files in os.walk(root, followlinks=False):
        parent = Path(current)
        for name in directories:
            if redirected(parent/name): raise ValueError('Redirected directory: '+str(parent/name))
        for name in files:
            path = parent/name
            if redirected(path): raise ValueError('Redirected file: '+str(path))
            yield path


def license_records(root):
    data = read_json(root/'third_party_licenses/PROVENANCE.json')
    records = {row['destination']: row['sha256'] for row in data['files']}
    for name, digest in records.items():
        path = inside(root/name, root/'third_party_licenses')
        if sha(path) != digest: raise ValueError('Selected license text changed: '+name)
    return records


def source_inventory(root):
    licenses = license_records(root)
    names = set(ROOT_FILES) | set(DOCS) | set(STATIC) | set(CATALOGS) | set(licenses) | {'third_party_licenses/PROVENANCE.json'}
    names |= {ICON_DIR+name for name in ICON_NAMES}
    for directory in ('src','frontend','tools','optional','.github'):
        if not (root/directory).is_dir(): continue
        for path in tree_files(root/directory):
            name = path.relative_to(root).as_posix()
            if source_path_allowed(name, license_names=licenses): names.add(name)
    result = {}
    for name in sorted(names): result[name] = sha(inside(root/name,root))
    return result


def identity(root):
    version = (root/'VERSION').read_text(encoding='utf-8-sig').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+',version): raise ValueError('Invalid VERSION')
    tree = ast.parse((root/'src/app_metadata.py').read_text(encoding='utf-8-sig'))
    values = {}
    for node in tree.body:
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant):
            values.update({target.id:node.value.value for target in node.targets if isinstance(target,ast.Name)})
    if values.get('APP_NAME') != 'CimStats' or values.get('APP_AUTHOR') != 'JEREMETRO': raise ValueError('Production identity has not been integrated')
    if values.get('PROJECT_LICENSE_NAME') != 'GNU General Public License v3.0': raise ValueError('Unexpected license display name')
    return {'name':'CimStats','version':version,'author':'JEREMETRO','executable':'CimStats.exe'}


def bundle_data(root):
    licenses = license_records(root)
    names = ['VERSION','LICENSE','THIRD_PARTY_NOTICES.md',*DOCS,*STATIC,*CATALOGS,
             *['src/'+name for name in SCRIPT_DATA],*[ICON_DIR+name for name in ICON_NAMES],
             *licenses,'third_party_licenses/PROVENANCE.json']
    for name in names:
        path = inside(root/name, root)
        if not path.is_file(): raise FileNotFoundError('Required bundle data: '+name)
    return [(str(root/name), str(PurePosixPath(name).parent)) for name in names]


def managed_data(directory):
    if sha(directory/'Assembly-CSharp.dll') != EXPECTED_BASE: raise ValueError('Staged base differs from audited assembly')
    for name in MANAGED_NAMES:
        if not (directory/name).is_file() or redirected(directory/name): raise ValueError('Missing or redirected staged dependency: '+name)
    return [(str(directory/name),'game_runtime/Managed') for name in MANAGED_NAMES]


def freeze(root):
    metadata = identity(root)
    files = source_inventory(root)
    environment = os.environ.copy(); environment['GIT_OPTIONAL_LOCKS']='0'
    commit = subprocess.check_output(['git','-c','safe.directory='+str(root),'-C',str(root),'rev-parse','HEAD'], env=environment,text=True).strip()
    return {'identity':metadata,'source_commit':commit,'files':files,
            'runtime_inputs':{'data/UnityEngine.dll':sha(root/'data/UnityEngine.dll')},
            'source_frozen':True,'publication_authorized':False,
            'meaning':'Exact local candidate source snapshot; not proof of UI approval or public source clearance'}


def check_freeze(root, path):
    record = read_json(path)
    if record.get('source_frozen') is not True: raise ValueError('Missing source freeze marker')
    if record['identity'] != identity(root): raise ValueError('Identity changed after freeze')
    compare_inventory(record['files'],source_inventory(root))
    compare_inventory(record['runtime_inputs'],{'data/UnityEngine.dll':sha(root/'data/UnityEngine.dll')})
    return record


def package_inventory(package):
    return [{'path':path.relative_to(package).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)}
            for path in sorted(tree_files(package)) if path.relative_to(package).as_posix() != 'VERSION.json']


def write_new(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream: json.dump(data,stream,ensure_ascii=False,indent=2); stream.write('\n')


def inspect_onefile(executable, snapshot):
    """Inspect embedded bytes, including dependencies hidden inside the EXE."""
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(executable))
    names = {name.replace('\\', '/'): name for name in archive.toc}
    required = ('VERSION', 'LICENSE', 'THIRD_PARTY_NOTICES.md',
                'third_party_licenses/PROVENANCE.json', *[ICON_DIR+n for n in ICON_NAMES])
    for name in required:
        if name not in names:
            raise ValueError('Missing embedded data: '+name)
        payload = archive.extract(names[name])
        if hashlib.sha256(payload).hexdigest() != snapshot['files'][name]:
            raise ValueError('Bundled legal/version/brand data differs: '+name)
    rows = []
    for name, original in names.items():
        # Only material requiring payload review needs decompression here.
        probe = {'path':name, 'sha256':''}
        if package_blockers([probe]):
            payload = archive.extract(original)
            rows.append({'path':name, 'bytes':len(payload),
                         'sha256':hashlib.sha256(payload).hexdigest()})
    return rows


def finalize(candidate, source_manifest):
    candidate = inside(candidate, ROOT/'build/candidates')
    validate_name(candidate.name)
    snapshot = check_freeze(ROOT, source_manifest)
    package = candidate/'package/CimStats'
    if not (package/'CimStats.exe').is_file(): raise ValueError('Missing single-file candidate executable')
    embedded = inspect_onefile(package/'CimStats.exe', snapshot)
    # Readable legal/user documents beside the EXE, using the same explicit
    # source list. UI About still reads its one-file extracted copies.
    readable = ['README.md','LICENSE','THIRD_PARTY_NOTICES.md','CHANGELOG.md','CONTRIBUTING.md','SECURITY.md','AGENTS.md',
                *DOCS,*license_records(ROOT),'third_party_licenses/PROVENANCE.json']
    for name in readable:
        destination = inside(package/name,package)
        if destination.exists():
            if sha(destination) != snapshot['files'][name]: raise ValueError('Conflicting candidate document: '+name)
            continue
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as stream: stream.write((ROOT/name).read_bytes())
    rows = package_inventory(package)
    blockers = package_blockers([*rows, *embedded])
    if any(row['kind']=='unexpected_payload' for row in blockers): raise ValueError('Unexpected save/archive/docs binary in candidate')
    record = {**snapshot['identity'],'source_commit':snapshot['source_commit'],'source_snapshot_sha256':sha(source_manifest),
              'layout':'onefile','local_review_only':True,'public_release_allowed':False,'files':{row['path']:row['sha256'] for row in rows}}
    write_new(package/'VERSION.json',record)
    source_zip = candidate/'CorrespondingProjectSource.zip'
    with zipfile.ZipFile(source_zip,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(snapshot['files']): archive.write(ROOT/name,name)
    report = {'identity':snapshot['identity'],'files':rows,'embedded_review_files':embedded,'package_version_record_sha256':sha(package/'VERSION.json'),
              'source_manifest_sha256':sha(source_manifest),'source_zip_sha256':sha(source_zip),
              'source_zip_scope':'Project-selected source only; not a substitute for third-party corresponding-source obligations or public-source privacy review',
              'public_release_allowed':False,'public_blocking_files':blockers,
              'remaining_gates':['exact frozen dependencies/license and corresponding source review','private paths and asset/font clearance','clean environment GUI/backend/export smoke tests','user package review before publication'],
              'environment':{'python':sys.version,'distributions':{d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata.get('Name')}},
              'built_locally':True,'published':False,'source_checked_after_build':True}
    write_new(candidate/'review-inventory.json',report)
    with (candidate/'source-snapshot.json').open('xb') as stream:
        stream.write(Path(source_manifest).read_bytes())
    compare_inventory(snapshot['files'],source_inventory(ROOT))
    return {'candidate':str(candidate),'files':len(rows),'blocking_files':len(blockers),'public_release_allowed':False}


def verify_candidate(candidate, public=False):
    candidate = inside(candidate,ROOT/'build/candidates')
    validate_name(candidate.name)
    package = candidate/'package/CimStats'
    record = read_json(package/'VERSION.json'); proof = read_json(candidate/'review-inventory.json')
    compare_inventory(record['files'],{row['path']:row['sha256'] for row in package_inventory(package)})
    if sha(package/'VERSION.json') != proof['package_version_record_sha256']: raise ValueError('VERSION record changed')
    if sha(candidate/'source-snapshot.json') != record['source_snapshot_sha256']: raise ValueError('Source snapshot changed')
    if sha(candidate/'CorrespondingProjectSource.zip') != proof['source_zip_sha256']: raise ValueError('Source archive changed')
    if public:
        raise ValueError('Public release remains blocked: local game dependencies and outstanding review gates. This command does not publish.')
    return {'identity':record['name']+' '+record['version'],'layout':record['layout'],'files_verified':len(record['files']),
            'local_review_only':True,'public_release_allowed':False,'public_blocking_files':proof['public_blocking_files']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','check-freeze','finalize','verify'))
    parser.add_argument('--source-manifest',type=Path)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--public',action='store_true')
    args = parser.parse_args()
    if args.action == 'freeze':
        if not args.output: parser.error('freeze requires a new --output report under docs/preflight')
        output = inside(args.output,ROOT/'docs/preflight')
        if output.suffix != '.json': parser.error('JSON snapshot required')
        result = freeze(ROOT); write_new(output,result)
        result = {'source_manifest':str(output),'version':result['identity']['version'],'source_files':len(result['files'])}
    elif args.action == 'check-freeze':
        if not args.source_manifest: parser.error('--source-manifest required')
        snapshot = check_freeze(ROOT,args.source_manifest); result={'source_unchanged':True,'version':snapshot['identity']['version']}
    elif args.action == 'finalize':
        if not args.candidate or not args.source_manifest: parser.error('--candidate and --source-manifest required')
        result = finalize(args.candidate,args.source_manifest)
    else:
        if not args.candidate: parser.error('--candidate required')
        result = verify_candidate(args.candidate,args.public)
    print(json.dumps(result,ensure_ascii=True))


if __name__ == '__main__': main()
