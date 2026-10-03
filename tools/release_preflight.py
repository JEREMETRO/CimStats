"""Read-only release inventory. No copy/build/upload/delete/app execution path.

Default: source candidates in this repository. --mode package audits a supplied
existing directory. An explicit --output writes only a JSON review report.
Classification is a review aid, not publication approval or legal clearance.
"""
from __future__ import annotations
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile
from candidate_package import selected_documents

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
BRIDGE_NAME = 'cim2runtimeschedulebridge.dll'
WINDOWS_FONTS = ('segoe', 'segui', 'msyh', 'microsoft yahei')
LOCAL_PATH = re.compile(r"(?i)\b[A-Z]:[\\/](?:Users[\\/][^\\/\s\"'<>]+|Program Files(?: \(x86\))?[\\/]|SteamLibrary[\\/]|test[\\/])")
SOURCE_SUFFIXES = {'.py', '.cs', '.js', '.css', '.html', '.ps1', '.spec', '.toml', '.ini', '.yml', '.yaml'}
ROOT_DOCUMENTS = {'readme.md', 'changelog.md', 'contributing.md', 'security.md', 'license', 'third_party_notices.md', 'agents.md',
                  'version', 'requirements-desktop.txt', 'requirements-dev.txt', '.gitignore', '.savestats-workspace'}
RELEASE_DOCS = {name.lower() for name in selected_documents()}
DOC_FILES = ['README.md', 'AGENTS.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'SECURITY.md', 'THIRD_PARTY_NOTICES.md',
             *selected_documents()]


def local_path_findings(text: str) -> list[dict]:
    """Record locations/types, without copying a person's full local path."""
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        matches = list(LOCAL_PATH.finditer(line))
        if matches:
            personal = any(re.search(r'(?i)^[A-Z]:[\\/]Users[\\/]', match.group()) for match in matches)
            findings.append({'line': number, 'kind': 'personal_path' if personal else 'machine_path'})
    return findings


def classify_file(relative: str, *, mode='source', text='', digest=None, license_hashes=None, is_link=False, excludes=()) -> dict:
    path = relative.replace('\\', '/')
    lower = path.lower(); parts = PurePosixPath(lower).parts; name = PurePosixPath(lower).name
    tags, reasons = [], []
    decision = 'confirm'
    def result(value, reason):
        return {'decision': value, 'reasons': [reason, *reasons], 'tags': sorted(set(tags))}
    if is_link or path.startswith('/') or '..' in parts or re.match(r'^[A-Za-z]:', path):
        tags.append('redirected_or_outside_path')
        return result('exclude', '符号链接、重定向或越界路径：不跟随读取，不纳入发布')
    if name.endswith('.dll') and (name.startswith('assembly-csharp') or name in ('unityengine.dll', 'steamworksmanaged.dll') or name.startswith('assembly-unityscript')):
        tags.append('game_assembly')
        return result('exclude', '游戏/Unity/探针或未核实 Steamworks 材料；项目声明不授予再分发权')
    if name.endswith(('.save', '.sav')):
        tags.append('save_data')
        return result('exclude', '实际存档/用户数据：不纳入公开发行')
    if name == BRIDGE_NAME:
        tags.append('project_bridge')
        return result('exclude' if mode == 'source' else 'confirm', '项目 Bridge 编译产物；源码包默认只带源码，独立二进制需对应源码/许可及使用边界核验')
    if name.endswith(('.ttf', '.otf', '.woff', '.woff2')):
        if any(token in name for token in WINDOWS_FONTS):
            tags.append('windows_font')
            return result('exclude', 'Windows 字体文件未获独立应用/字体再分发授权')
        tags.append('third_party_font')
        return result('confirm', '第三方字体，按具体来源、版本和许可判断；不能按字体后缀一概禁止或批准')
    if 'wordmark-outline' in name or (name.startswith('cimstats-lockup') and name.endswith('.svg')):
        tags.append('font_outline')
        return result('exclude', 'Segoe 可编辑字形轮廓源的具体图形输出授权待确认，当前公开清单排除')
    if parts and parts[0] in ('.git', '.worktrees', 'archive', 'build', 'dist', 'jobs', 'analysis', 'recycle_bin', 'recycle-bin', '_build_runtime'):
        tags.append('workspace_or_history')
        return result('exclude', '源码候选排除工作树、历史包、构建或任务资料；本地保留，不删除')
    if '__pycache__' in parts or name.endswith(('.pyc', '.pyo')):
        tags.append('generated_cache')
        return result('exclude', '生成缓存，不作为公开源文件')
    if lower.startswith(('docs/branding/', 'docs/performance/', 'docs/ui-redesign/', 'docs/preflight/')):
        tags.append('review_or_evidence')
        return result('exclude', '审稿/测试证据或本地预检记录；不递归带入发布')
    if name.endswith(('.zip', '.7z', '.rar', '.tar', '.gz')):
        tags.append('nested_archive')
        return result('exclude', '嵌套归档/旧包：保持独立，不打进本轮发行内容')
    for pattern in excludes:
        if not any(character.isspace() for character in pattern) and fnmatch.fnmatch(lower, pattern.lower()):
            tags.append('public_manifest_exclusion')
            return result('exclude', '现有公开建议清单的排除规则命中：'+pattern)
    if name.endswith(('.dll', '.pyd', '.so', '.dylib', '.exe')):
        tags.append('native_or_compiled')
        return result('confirm', '原生依赖或项目编译产物：需要来源/版本、原许可、对应源码/运行库及内容核验；并非所有 DLL 都不可分发')
    if lower.startswith('third_party_licenses/'):
        if digest and license_hashes and license_hashes.get(path) == digest:
            tags.append('verified_license_text')
            decision = 'include'; reasons.append('原许可文本与选择来源清单哈希相符；不表示整个组件包已获准发行')
        else:
            tags.append('license_needs_provenance'); reasons.append('许可文件来源/哈希缺失或变化，需复核')
    elif (len(parts) == 1 and name in ROOT_DOCUMENTS) or lower in RELEASE_DOCS:
        decision = 'include'; tags.append('release_document'); reasons.append('项目发布文档/声明候选，保留作者与第三方范围')
    elif lower.startswith(('.github/', 'tools/')) or (parts and parts[0] in ('src', 'frontend', 'optional') and PurePosixPath(name).suffix in SOURCE_SUFFIXES) or (len(parts) == 1 and PurePosixPath(name).suffix in SOURCE_SUFFIXES):
        decision = 'include'; tags.append('project_source_candidate'); reasons.append('项目自有代码候选，仍需核对作者来源与 GPL 告知；不是运行或发布批准')
    elif lower.startswith('frontend/static/branding/'):
        tags.append('brand_asset'); reasons.append('品牌资产：设计批准与资产授权/参考来源分别核验')
    else:
        tags.append('unclassified'); reasons.append('不在明确源文件/文档允许类别，需确定用途和权利来源')
    privacy = local_path_findings(text)
    if privacy:
        tags.extend(finding['kind'] for finding in privacy)
        reasons.append('发现本地路径，复核必要脱敏/机器绑定；仅记录行号，不输出完整个人路径')
        if decision == 'include': decision = 'confirm'
    return {'decision': decision, 'reasons': reasons, 'tags': sorted(set(tags)), 'local_path_findings': privacy}


def classify_embedded_file(relative, public_manifest):
    """Apply the same public policy to ZIP and hash-bound EXE members."""
    return classify_file(relative, mode='package', excludes=public_manifest.get('exclude', []))


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git_read(root, *args):
    environment = os.environ.copy(); environment['GIT_OPTIONAL_LOCKS'] = '0'
    completed = subprocess.run(['git', '-c', 'safe.directory='+str(root), '-C', str(root), *args],
                               capture_output=True, env=environment)
    if completed.returncode:
        return None, completed.stderr.decode('utf-8', 'replace').strip()
    return completed.stdout.decode('utf-8', 'surrogateescape'), None


def read_json(path):
    try: return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError): return {}


def local_link_check(root):
    """Check only current release docs, skip external URLs, never request network."""
    rows = []
    for filename in DOC_FILES:
        path = root/filename
        if not path.is_file():
            rows.append({'document': filename, 'target': filename, 'exists': False, 'reason': 'required document missing'})
            continue
        text = path.read_text(encoding='utf-8-sig')
        for raw in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
            target = raw.strip().split(' "', 1)[0].strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'): continue
            from urllib.parse import unquote
            target = unquote(target.split('#', 1)[0].split('?', 1)[0])
            resolved = (path.parent/target).resolve()
            inside = resolved.is_relative_to(root)
            rows.append({'document': filename, 'target': target, 'exists': inside and resolved.exists(), 'inside_root': inside})
    return {'checked_documents': DOC_FILES, 'local_links': rows, 'broken_count': sum(not row['exists'] for row in rows)}


def run_preflight(root, mode='source', expected_version=None):
    root = root.resolve()
    policy_root = PROJECT
    public = read_json(policy_root/'docs/REDISTRIBUTION_PUBLIC_MANIFEST.json')
    provenance = read_json(policy_root/'third_party_licenses/PROVENANCE.json')
    license_hashes = {row['destination']: row['sha256'] for row in provenance.get('files', [])}
    if (policy_root/'third_party_licenses/PROVENANCE.json').is_file():
        license_hashes['third_party_licenses/PROVENANCE.json'] = file_hash(policy_root/'third_party_licenses/PROVENANCE.json')
    evidence = read_json(policy_root/'docs/REDISTRIBUTION_EVIDENCE.json')
    findings, rows = [], []
    index = root/'.git/index'
    index_before = file_hash(index) if index.is_file() else None
    status_before = None
    if mode == 'source':
        names, error = git_read(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard')
        if error:
            findings.append({'kind': 'git_inventory_unavailable', 'detail': error})
            names = ''; paths = [path.relative_to(root).as_posix() for path in root.iterdir() if path.is_file()]
        else: paths = names.split('\0')[:-1]
        status_before, error = git_read(root, 'status', '--porcelain=v1', '-z', '--untracked-files=normal')
        if status_before:
            findings.append({'kind': 'worktree_not_frozen', 'detail': '存在未提交/未跟踪修改；清单快照不能当作已提交发行源码', 'entries': status_before.split('\0')[:-1]})
        worktrees, error = git_read(root, 'worktree', 'list', '--porcelain')
        if worktrees: findings.append({'kind': 'worktree_inventory', 'detail': worktrees.splitlines()})
        if (root/'.worktrees').exists(): findings.append({'kind': 'nested_worktree_directory', 'path': '.worktrees', 'decision': 'exclude'})
        # The spec reads ignored filesystem docs too. Audit these separately from
        # the Git source list; never recurse into build/jobs/worktrees here.
        try:
            for path in (root/'docs').rglob('*'):
                if path.suffix.lower() in ('.dll', '.exe', '.ttf', '.otf', '.woff', '.woff2', '.zip', '.save', '.sav') and path.is_file():
                    paths.append(path.relative_to(root).as_posix())
        except OSError as error:
            findings.append({'kind': 'filesystem_inventory_incomplete', 'detail': str(error)})
    else:
        paths = []
        for parent, folders, files in os.walk(root, followlinks=False):
            safe = []
            for name in folders:
                path = Path(parent)/name
                if path.is_symlink() or path.is_junction():
                    paths.append(path.relative_to(root).as_posix())
                elif name == '.git':
                    findings.append({'kind': 'nested_repository', 'path': path.relative_to(root).as_posix(), 'decision': 'exclude'})
                elif name == '.worktrees':
                    findings.append({'kind': 'nested_worktree_directory', 'path': path.relative_to(root).as_posix(), 'decision': 'exclude', 'detail':'不递归读取其他工作树'})
                else: safe.append(name)
            folders[:] = safe
            paths.extend((Path(parent)/name).relative_to(root).as_posix() for name in files)
    for name in sorted(set(paths)):
        path = root/name
        link = path.is_symlink() or path.is_junction()
        item = {'path': name, 'bytes': None, 'sha256': None}
        if link:
            item.update(classify_file(name, mode=mode, is_link=True)); rows.append(item); continue
        if not path.is_file():
            item.update(decision='confirm', reasons=['Git 清单文件缺失或不是普通文件'], tags=['missing_or_nonfile'])
            rows.append(item); continue
        try:
            before = path.stat()
            digest = file_hash(path)
            text = ''
            if before.st_size <= 2*1024*1024 and path.suffix.lower() not in ('.dll', '.exe', '.zip', '.pyd', '.ttf', '.png', '.jpg', '.jpeg', '.save', '.sav'):
                try: text = path.read_text(encoding='utf-8-sig')
                except UnicodeError: pass
            item.update(bytes=before.st_size, sha256=digest)
            item.update(classify_file(name, mode=mode, text=text, digest=digest, license_hashes=license_hashes, excludes=public.get('exclude', [])))
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                item['decision']='confirm'; item['reasons'].append('读取期间文件变化，请冻结后重跑'); item['tags'].append('changed_during_read')
            rows.append(item)
            if path.suffix.lower() == '.zip':
                try:
                    with zipfile.ZipFile(path) as archive:
                        for member in archive.infolist():
                            if member.is_dir() or not member.filename.lower().endswith(('.dll', '.exe', '.zip', '.ttf', '.otf', '.woff', '.woff2', '.save', '.sav')): continue
                            child={'path': name+'!'+member.filename, 'container_path': name, 'container_decision': item['decision'], 'bytes': member.file_size, 'sha256': None}
                            child.update(classify_embedded_file(member.filename, public))
                            if member.file_size <= 512*1024*1024:
                                with archive.open(member) as stream: child['sha256']=hashlib.file_digest(stream,'sha256').hexdigest()
                            else: child['reasons'].append('大型归档成员未解压读哈希，需独立检查')
                            rows.append(child)
                except (OSError, ValueError, zipfile.BadZipFile) as error:
                    findings.append({'kind':'archive_not_inspected','path':name,'detail':str(error)})
            if path.suffix.lower() == '.exe':
                old = evidence.get('old_exe', {})
                if digest == old.get('sha256'):
                    item['reasons'].append('SHA-256 与只读归档审计证据一致；嵌入内容逐项列于以下记录')
                    for key in ('game_runtime_files','native_dll_files','font_files'):
                        for embedded in old.get(key, []):
                            child={'path': name+'!'+embedded['archive_name'], 'container_path': name, 'bytes': embedded['bytes'], 'sha256': embedded['sha256'], 'evidence':'exact-EXE-hash-matched audit'}
                            child.update(classify_embedded_file(embedded['archive_name'], public))
                            rows.append(child)
                else:
                    item['reasons'].append('尚无绑定此精确 EXE 哈希的归档内容证据；需重新只读核对冻结内容')
        except OSError as error:
            item.update(decision='confirm', reasons=['文件读取失败：'+str(error)], tags=['unreadable'])
            rows.append(item)
    version = None
    if (root/'VERSION').is_file(): version=(root/'VERSION').read_text(encoding='utf-8-sig').strip()
    elif (root/'VERSION.json').is_file(): version=read_json(root/'VERSION.json').get('version')
    if expected_version and version != expected_version:
        findings.append({'kind':'version_mismatch','actual':version,'expected':expected_version})
    if mode == 'source':
        status_after, error=git_read(root,'status','--porcelain=v1','-z','--untracked-files=normal')
        if status_after != status_before: findings.append({'kind':'worktree_changed_during_check','detail':'读取期间工作树状态发生变化'})
    index_after = file_hash(index) if index.is_file() else None
    counts = {name: sum(row['decision']==name for row in rows) for name in ('include','exclude','confirm')}
    links = local_link_check(policy_root)
    return {'mode':mode,'target':str(root),'dry_run':True,'publication_authorized':False,'build_run':False,'copy_run':False,'upload_run':False,'delete_run':False,
            'version_read':version,'public_manifest_scope':public.get('scope'),'manifest_publication_approved':public.get('approved_for_publication',False),
            'screenshot_approval':'not verified here; user screenshot approval remains required before building',
            'summary':counts,'files':rows,'findings':findings,'document_links':links,'git_index_unchanged':index_before==index_after,
            'interpretation':'include=可复核的候选材料；exclude=排除本次发布但保留本地；confirm=需要来源/许可/内容/脱敏确认。不能据此宣称整个项目不可发布或整包已通过。'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',type=Path,default=PROJECT)
    parser.add_argument('--mode',choices=('source','package'),default='source')
    parser.add_argument('--expected-version')
    parser.add_argument('--output',type=Path,help='Write a JSON report under docs/preflight only; existing report is not overwritten')
    args=parser.parse_args()
    report=run_preflight(args.target,args.mode,args.expected_version)
    payload=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        destination=args.output.resolve()
        if not destination.is_relative_to(PROJECT/'docs/preflight') or destination.suffix.lower() != '.json':
            parser.error('Only .json review reports under docs/preflight may be written')
        if destination.exists(): parser.error('Report already exists; choose another filename')
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('x',encoding='utf-8',newline='\n') as stream: stream.write(payload)
        print(json.dumps({'report':str(destination),'summary':report['summary'],'broken_local_links':report['document_links']['broken_count'],
                          'git_index_unchanged':report['git_index_unchanged'],'dry_run':True},ensure_ascii=True))
    else:
        sys.stdout.reconfigure(encoding='utf-8')
        print(payload,end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
