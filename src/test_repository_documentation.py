"""Validate maintained documentation, community entry points and package coverage."""
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOPICS = {
    'requirements': ('product.md', 'charts.md', 'latest-info.md'),
    'design': ('architecture.md', 'controls.md', 'visual-design.md'),
    'reference': ('history-metrics.md', 'line-metrics.md', 'runtime-decoding.md',
                  'field-inventory.md', 'geometry-and-vehicles.md',
                  'passenger-routing.md', 'multiplayer.md', 'tools.md'),
    'testing': ('acceptance.md',),
}


def maintained_documents():
    files = list((ROOT / 'docs').rglob('*.md'))
    files.extend(ROOT / name for name in (
        'README.md', 'AGENTS.md', 'CONTRIBUTING.md', 'SECURITY.md',
        'CHANGELOG.md', 'THIRD_PARTY_NOTICES.md'))
    files.extend((ROOT / '.github').rglob('*.md'))
    return files


@pytest.mark.parametrize('folder,names', TOPICS.items())
def test_documentation_is_grouped_by_use(folder, names):
    for name in names:
        assert (ROOT / 'docs' / folder / name).is_file()
    assert not (ROOT / 'docs/history').exists()


def test_documentation_has_no_embedded_workspaces_or_private_machine_paths():
    for source in maintained_documents():
        content = source.read_text(encoding='utf-8-sig')
        assert not {'archive', 'variants', 'recycle_bin', 'superpowers'} & set(source.relative_to(ROOT).parts)
        assert not re.search(r'(?i)\b[A-Z]:[\\/](?:Users|test|Program Files)', content), source
        assert 'history/legacy' not in content, source


def test_maintained_documentation_resolves_local_links():
    for source in maintained_documents():
        content = source.read_text(encoding='utf-8-sig')
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', content):
            url = urlsplit(link.strip('<>'))
            if url.scheme or not url.path:
                continue
            target = (source.parent / unquote(url.path)).resolve()
            assert target.is_relative_to(ROOT), (source, link)
            assert target.exists(), (source, link)


def test_index_covers_every_maintained_topic():
    content = (ROOT / 'docs/README.md').read_text(encoding='utf-8')
    for folder, names in TOPICS.items():
        for name in names:
            assert f'{folder}/{name}' in content


def test_github_community_entry_points_are_recognized():
    for name in ('README.md', 'LICENSE', 'CONTRIBUTING.md', 'SECURITY.md',
                 '.github/pull_request_template.md'):
        assert (ROOT / name).is_file()
    for source in (ROOT / '.github/ISSUE_TEMPLATE').glob('*.md'):
        content = source.read_text(encoding='utf-8-sig')
        assert content.startswith('---\n')
        header = content.split('---', 2)[1]
        assert re.search(r'^name:\s*\S', header, re.MULTILINE)
        assert re.search(r'^about:\s*\S', header, re.MULTILINE)


def test_chart_and_agent_rules_share_the_identity_legend_contract():
    for source in (ROOT / 'AGENTS.md', ROOT / 'docs/requirements/charts.md'):
        content = source.read_text(encoding='utf-8')
        assert all(term in content for term in ('公司', '同期', '色柱', 'SeriesLegend'))
        assert '左／右、上／下' in content


def test_ratio_rollup_retains_observed_zero_divider_numerators():
    content = (ROOT / 'docs/reference/history-metrics.md').read_text(encoding='utf-8')
    assert '10/0 + 20/10' in content and '300%' in content
    assert '零分母' in content and '仍参与' in content


def test_latest_info_documents_transfer_mode_filter_exception():
    content = (ROOT / 'docs/requirements/latest-info.md').read_text(encoding='utf-8')
    assert '全部制式' in content and '缺少制式分母' in content
    assert 'scope' in content and 'reason' in content


def test_company_docs_describe_fixed_metrics_and_existing_chart_interfaces():
    product = (ROOT / 'docs/requirements/product.md').read_text(encoding='utf-8')
    controls = (ROOT / 'docs/design/controls.md').read_text(encoding='utf-8')
    assert '固定四图' in product and '单系列' in product and '`line`' in product
    assert 'set_metric_menu' not in controls
    assert '指标选择器' in controls and '不提供' in controls


def test_release_notes_match_restored_chart_presentation():
    notes = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8').split('## CimStats 0.1.0', 1)[0]
    assert '两端圆角' in notes and '摘要卡片' in notes
    assert '完整数值表' not in notes


def test_formal_010_release_records_known_issues_and_download_name():
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    notes = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    release = (ROOT / 'docs/RELEASE.md').read_text(encoding='utf-8')
    spec = (ROOT / 'CIM2_SaveStats.spec').read_text(encoding='utf-8')
    assert 'CimStats_x64_v0.1.0.exe' in readme
    assert '## 0.1.0 - 2026-10-03' in notes
    assert '悬停标签' in notes and '背景颜色' in notes and '控件显示被截断' in notes
    assert '正式版' in release and '/releases/tag/v0.1.0' in release
    assert "StringStruct('Comments', metadata.license_spdx)" in spec


def test_formal_010_release_leads_with_contributor_credit():
    notes = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8').split('## CimStats 0.1.0', 1)[0]
    policy = (ROOT / 'docs/RELEASE.md').read_text(encoding='utf-8')
    assert 'https://github.com/Trilleo' in notes
    assert 'https://github.com/JEREMETRO/CimStats/pull/1' in notes
    assert notes.index('Trilleo') < notes.index('###')
    assert '### 验证' not in notes
    assert '贡献者' in policy and '测试数量' in policy and '合并过程' in policy


def test_curated_docs_are_in_source_and_bundle_manifests(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'tools'))
    import candidate_package
    import release_preflight

    docs = {source.relative_to(ROOT).as_posix() for source in (ROOT / 'docs').rglob('*.md')}
    assert set(candidate_package.selected_documents()) == docs
    assert candidate_package.source_path_allowed('AGENTS.md')
    assert 'AGENTS.md' in release_preflight.DOC_FILES
    for name in docs:
        assert candidate_package.source_path_allowed(name), name
        assert release_preflight.classify_file(name)['decision'] == 'include', name
        assert name in release_preflight.DOC_FILES, name
    for name in ('docs/history/legacy/INDEX.md', 'docs/preflight/report.md',
                 'docs/reference/private.save', 'docs/testing/runtime.dll'):
        assert not candidate_package.source_path_allowed(name)
