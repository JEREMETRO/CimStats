"""Meaningful classification regression checks; all fixtures stay in memory."""
import sys
sys.dont_write_bytecode = True
import unittest

from release_preflight import classify_file, classify_embedded_file, local_path_findings


class PreflightRules(unittest.TestCase):
    def check(self, path, expected, **kwargs):
        self.assertEqual(classify_file(path, **kwargs)['decision'], expected)

    def test_project_source_is_candidate(self):
        self.check('src/statistics_model.py', 'include')

    def test_source_bridge_is_separate_from_game_assembly(self):
        self.check('optional/save_editing/CIM2RuntimeScheduleBridge.cs', 'include')

    def test_game_dll_is_excluded(self):
        self.check('data/Assembly-CSharp.probe.dll', 'exclude')
        self.check('runtime/UnityEngine.dll', 'exclude', mode='package')

    def test_ordinary_native_dll_is_pending_not_automatically_forbidden(self):
        self.check('Qt6Core.dll', 'confirm', mode='package')
        self.check('my_owned_module.dll', 'confirm', mode='package')

    def test_embedded_game_runtime_inherits_manifest_exclusion(self):
        policy = {'exclude': ['game_runtime/**']}
        row = classify_embedded_file('game_runtime/System.dll', policy)
        self.assertEqual(row['decision'], 'exclude')

    def test_embedded_ordinary_dependency_remains_pending(self):
        policy = {'exclude': ['game_runtime/**']}
        row = classify_embedded_file('PySide6/Qt6Core.dll', policy)
        self.assertEqual(row['decision'], 'confirm')

    def test_bridge_binary_is_project_candidate_in_binary_mode(self):
        row = classify_file('CIM2RuntimeScheduleBridge.dll', mode='package')
        self.assertEqual(row['decision'], 'confirm')
        self.assertIn('project_bridge', row['tags'])
        self.assertNotIn('game_assembly', row['tags'])

    def test_source_bridge_binary_is_default_excluded(self):
        self.check('optional/save_editing/bin/CIM2RuntimeScheduleBridge.dll', 'exclude')

    def test_archives_and_nested_packages_are_reported(self):
        self.check('archive/versions/v1.0.0/source.zip', 'exclude')
        row = classify_file('nested-old-release.zip', mode='package')
        self.assertEqual(row['decision'], 'exclude')
        self.assertIn('nested_archive', row['tags'])

    def test_save_is_always_excluded(self):
        self.check('sample.save', 'exclude', mode='package')
        self.check('data/sample.sav', 'exclude')

    def test_windows_fonts_are_excluded_but_other_fonts_need_license(self):
        self.check('fonts/segoeui.ttf', 'exclude', mode='package')
        self.check('fonts/DejaVuSans.ttf', 'confirm', mode='package')

    def test_wordmark_outline_needs_clearance(self):
        self.check('frontend/static/branding/cimstats/wordmark-outline.json', 'exclude')

    def test_review_and_worktree_materials_are_excluded(self):
        self.check('docs/branding/cimstats/review/image.png', 'exclude')
        self.check('.worktrees/fix/src/main.py', 'exclude')

    def test_notice_and_report_are_separate(self):
        self.check('docs/PROJECT_NOTICE.md', 'include')
        self.check('docs/preflight/source.json', 'exclude')

    def test_license_hash_must_match_provenance(self):
        name = 'third_party_licenses/example/LICENSE'
        self.check(name, 'include', digest='a'*64, license_hashes={name: 'a'*64})
        self.check(name, 'confirm', digest='b'*64, license_hashes={name: 'a'*64})

    def test_personal_paths_downgrade_source_to_pending(self):
        row = classify_file('docs/USER_GUIDE.md', text='Log at C:/Users/Alice/AppData/Local/example.txt')
        self.assertEqual(row['decision'], 'confirm')
        self.assertIn('personal_path', row['tags'])

    def test_system_path_variable_is_not_personal_path(self):
        self.assertEqual(local_path_findings('%LOCALAPPDATA%/CIM2_SaveStats/jobs'), [])

    def test_symlinks_and_escape_paths_are_not_followed(self):
        self.check('src/link.py', 'exclude', is_link=True)
        self.check('../external/source.py', 'exclude')


if __name__ == '__main__':
    unittest.main()
