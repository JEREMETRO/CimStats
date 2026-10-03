"""Release guard tests with in-memory inventories; no build or cleanup."""
import sys
sys.dont_write_bytecode = True
import unittest
from unittest.mock import patch
from types import ModuleType, SimpleNamespace
from pathlib import Path
import os
import importlib.metadata
import candidate_package
from candidate_package import source_path_allowed, compare_inventory, package_blockers, validate_name, selected_documents


class CandidateRules(unittest.TestCase):
    def test_source_includes_own_code_and_bridge_source(self):
        for path in ('src/app_metadata.py', 'frontend/app_startup.py', 'tools/test_publish_pipeline.ps1', 'optional/save_editing/CIM2RuntimeScheduleBridge.cs'):
            self.assertTrue(source_path_allowed(path))

    def test_source_excludes_game_dll_even_outside_data(self):
        for path in ('data/UnityEngine.dll', 'src/Assembly-CSharp.dll', 'frontend/cache/probe.dll'):
            self.assertFalse(source_path_allowed(path))

    def test_source_excludes_history_private_and_generated_files(self):
        for path in ('archive/source.zip', 'jobs/result.py', '.worktrees/a/src/main.py', 'src/__pycache__/main.py', 'docs/ui-redesign/city-evidence/cache.py', 'data/sample.save'):
            self.assertFalse(source_path_allowed(path))

    def test_source_excludes_unapproved_font_outlines(self):
        self.assertFalse(source_path_allowed('frontend/static/branding/cimstats/wordmark-outline.json'))
        self.assertFalse(source_path_allowed('frontend/static/branding/cimstats/cimstats-lockup.svg'))

    def test_source_includes_selected_legal_text_only(self):
        self.assertTrue(source_path_allowed('LICENSE'))
        self.assertTrue(source_path_allowed('third_party_licenses/example/LICENSE', license_names={'third_party_licenses/example/LICENSE'}))
        self.assertFalse(source_path_allowed('third_party_licenses/example/rogue.dll'))

    def test_docs_are_explicit_not_evidence_recursion(self):
        self.assertIn('docs/PROJECT_NOTICE.md', selected_documents())
        self.assertIn('docs/DATA_DEFINITIONS.md', selected_documents())
        self.assertFalse(source_path_allowed('docs/ui-redesign/card-comparisons-evidence/UnityEngine.dll'))

    def test_selected_documents_are_available_in_a_source_checkout(self):
        for relative in selected_documents():
            self.assertTrue((candidate_package.ROOT / relative).is_file(), relative)

    def test_snapshot_changes_are_rejected(self):
        with self.assertRaises(ValueError): compare_inventory({'src/main.py':'a'}, {'src/main.py':'b'})

    def test_added_source_is_rejected(self):
        with self.assertRaises(ValueError): compare_inventory({'src/main.py':'a'}, {'src/main.py':'a','src/new.py':'b'})

    def test_missing_source_is_rejected(self):
        with self.assertRaises(ValueError): compare_inventory({'src/main.py':'a'}, {})

    def test_unchanged_snapshot_is_accepted(self):
        compare_inventory({'src/main.py':'a'}, {'src/main.py':'a'})

    def test_managed_and_probe_are_exactly_reported_as_blockers(self):
        rows = [{'path':'_internal/game_runtime/Managed/System.dll','sha256':'a'*64}, {'path':'_internal/data/Assembly-CSharp.probe.dll','sha256':'b'*64}]
        result = package_blockers(rows)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['sha256'], 'a'*64)

    def test_ordinary_qt_dependency_is_not_game_assembly(self):
        self.assertEqual(package_blockers([{'path':'_internal/PySide6/Qt6Core.dll','sha256':'a'*64}]), [])

    def test_bridge_binary_is_separate_from_game_assembly(self):
        self.assertEqual(package_blockers([{'path':'_internal/CIM2RuntimeScheduleBridge.dll','sha256':'a'*64}]), [])

    def test_font_files_require_specific_clearance(self):
        result = package_blockers([{'path':'_internal/fonts/segoeui.ttf','sha256':'a'*64}])
        self.assertEqual(result[0]['kind'], 'font_clearance')

    def test_save_nested_archive_and_docs_dll_are_rejected(self):
        for path in ('sample.save', 'nested.zip', '_internal/docs/evidence/runtime.dll'):
            self.assertEqual(package_blockers([{'path':path,'sha256':'a'*64}])[0]['kind'], 'unexpected_payload')

    def test_candidate_name_cannot_escape_or_claim_publication(self):
        for value in ('../outside', 'C:/outside', 'release.zip', 'dist', 'CON'):
            with self.assertRaises(ValueError): validate_name(value)

    def test_unique_local_candidate_name(self):
        self.assertEqual(validate_name('CimStats-0.1.0-review-abc123'), 'CimStats-0.1.0-review-abc123')


class SpecContract(unittest.TestCase):
    """Evaluate spec flow using fake builders: no Qt/CLR or build execution."""
    def evaluate(self, *, local_review=True, version='0.1.0'):
        observed = {}
        hooks = ModuleType('PyInstaller.utils.hooks')
        hooks.collect_submodules = lambda name: []
        hooks.collect_data_files = lambda name: []
        resource = ModuleType('PyInstaller.utils.win32.versioninfo')
        for name in ('VSVersionInfo','FixedFileInfo','StringFileInfo','StringTable','StringStruct','VarFileInfo','VarStruct'):
            setattr(resource, name, lambda *args, **kwargs: (args,kwargs))
        metadata = ModuleType('app_metadata')
        metadata.application_metadata = lambda root: SimpleNamespace(name='CimStats',version=version,author='JEREMETRO',copyright_notice='Copyright 2026 JEREMETRO',license_spdx='GPL-3.0-only')
        metadata.icon_directory = lambda root: root/'frontend/static/branding/cimstats'
        root = candidate_package.ROOT
        def analysis(*args, **kwargs):
            observed['analysis'] = kwargs
            return SimpleNamespace(pure=[],scripts=['launcher'],binaries=['native-dependencies'],datas=kwargs['datas'])
        def exe(*args, **kwargs): observed['exe']=(args,kwargs); return 'executable'
        def collect(*args, **kwargs): observed['collect']=(args,kwargs)
        namespace = {'SPECPATH':str(root),'Analysis':analysis,'PYZ':lambda pure:'pyz','EXE':exe,'COLLECT':collect}
        environment = {'CIMSTATS_LOCAL_REVIEW_BUILD':'1' if local_review else '',
                       'CIM2_BUILD_MANAGED_ROOT':str(root/'game_runtime/Managed'),
                       'CIM2_BUILD_PROBE_PATH':str(root/'data/Assembly-CSharp.probe.dll')}
        distribution = lambda name: SimpleNamespace(files=[],version='test',locate_file=lambda entry:root/'not-installed'/entry)
        with patch.dict(sys.modules,{'PyInstaller.utils.hooks':hooks,'PyInstaller.utils.win32.versioninfo':resource,'app_metadata':metadata}), patch.dict(os.environ,environment), patch.object(importlib.metadata,'distribution',distribution):
            exec(compile((root/'CIM2_SaveStats.spec').read_text(encoding='utf-8-sig'),'CIM2_SaveStats.spec','exec'),namespace)
        return observed

    def test_onefile_spec_keeps_native_and_data_files_in_executable(self):
        observed = self.evaluate()
        args, options = observed['exe']
        self.assertFalse(options.get('exclude_binaries', False))
        self.assertEqual(args[2], ['native-dependencies'])
        self.assertEqual(args[3], observed['analysis']['datas'])
        self.assertEqual(options['name'], 'CimStats')
        self.assertNotIn('collect', observed)

    def test_spec_includes_legal_metadata_and_all_approved_icons(self):
        observed = self.evaluate()
        sources = {Path(row[0]).relative_to(candidate_package.ROOT).as_posix() for row in observed['analysis']['datas'] if Path(row[0]).is_relative_to(candidate_package.ROOT)}
        for name in ('LICENSE','THIRD_PARTY_NOTICES.md','src/app_metadata.py','docs/PROJECT_NOTICE.md',*[candidate_package.ICON_DIR+n for n in candidate_package.ICON_NAMES]):
            self.assertIn(name,sources)
        self.assertFalse(any(name.startswith(('docs/ui-redesign/','docs/branding/','docs/performance/')) for name in sources))

    def test_direct_spec_build_is_rejected_without_review_gate(self):
        with self.assertRaises(RuntimeError): self.evaluate(local_review=False)

    def test_old_version_is_rejected(self):
        with self.assertRaises(RuntimeError): self.evaluate(version='1.0.0')


if __name__ == '__main__': unittest.main()
