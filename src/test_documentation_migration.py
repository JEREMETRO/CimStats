"""Keep imported source documents traceable and current entry points reachable."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / 'docs/history/legacy'


def test_migration_manifest_preserves_every_source_document_content():
    manifest = json.loads((LEGACY / 'MANIFEST.json').read_text(encoding='utf-8'))
    assert set(manifest['sources']) == {'main', 'ui', 'data', 'charts', 'latest-info'}
    assert manifest['records']
    for record in manifest['records']:
        target = (ROOT / record['destination']).resolve()
        assert target.is_relative_to(ROOT)
        assert target.is_file(), record
        text = target.read_text(encoding='utf-8-sig')
        assert hashlib.sha256(text.encode('utf-8')).hexdigest() == record['text_sha256'], record
        if record['destination'].startswith('docs/history/legacy/'):
            assert hashlib.sha256(target.read_bytes()).hexdigest() == record['sha256'], record
    required = {'DESIGN.md', 'CONTROL-SPEC.md', 'NETWORK-DATA.md', 'VISUAL-CONTRACT.md',
                'LATEST-INFO-CONTRACT.md', 'CIM2_统计中心指标口径.md', 'CHART-SETTINGS-REFERENCE.md'}
    assert required <= {Path(record['path']).name for record in manifest['records']}


def test_current_documentation_and_migration_index_resolve_local_links():
    files = [ROOT / 'README.md', ROOT / 'AGENTS.md', LEGACY / 'INDEX.md']
    files.extend((ROOT / 'docs').glob('*.md'))
    for source in files:
        content = source.read_text(encoding='utf-8')
        for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)', content):
            path = urlsplit(link).path
            if urlsplit(link).scheme or not path:
                continue
            target = (source.parent / unquote(path)).resolve()
            assert target.is_relative_to(ROOT), (source, link)
            assert target.exists(), (source, link)


def test_current_chart_requirements_and_agent_rules_share_the_legend_contract():
    for source in (ROOT / 'AGENTS.md', ROOT / 'docs/UI_REQUIREMENTS.md'):
        content = source.read_text(encoding='utf-8')
        assert '公司' in content and '同期' in content and '色柱' in content
        assert '左／右、上／下' in content
    assert 'SeriesLegend' in (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
