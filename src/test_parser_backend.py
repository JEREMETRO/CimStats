import os
import sys

import parser_backend


def test_frozen_backend_uses_embedded_runtime_even_when_gui_selected_installed_game(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'argv', ['CIM2_SaveStats.exe', 'example.save', 'auto'])
    monkeypatch.setenv('CIM2_MANAGED_ROOT', r'D:\modified-game\Managed')
    monkeypatch.setattr(parser_backend, 'root_dir', lambda: tmp_path)
    seen = []
    monkeypatch.setattr(parser_backend, 'run_script', lambda _path, _args: seen.append(os.environ['CIM2_MANAGED_ROOT']))
    assert parser_backend.main() == 0
    assert seen == [str(tmp_path / 'game_runtime' / 'Managed')] * 3
