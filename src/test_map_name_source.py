"""Bounded serialization-prefix parsing and conservative city-name display."""
import importlib
import importlib.util
from pathlib import Path

import pytest


def api():
    assert importlib.util.find_spec('map_name_source') is not None, 'bounded map-name reader is missing'
    return importlib.import_module('map_name_source')


def string(value):
    if value is None:
        return b'\xff'
    encoded = value.encode('utf-16-be')
    return (len(encoded) // 2).to_bytes(3, 'big') + encoded


def header(reference, *, players=1, version=2013120900, root_type='GameState+SerializableMetaData'):
    # Literal game Serialize field order; object array declares queued players.
    result = b'\xfd' + version.to_bytes(4, 'big') + b'\xfe\xfe' + string(root_type)
    result += (123).to_bytes(4, 'big') + (1000).to_bytes(8, 'big') * 6
    result += players.to_bytes(3, 'big')
    for index in range(players):
        result += b'\xfe\xfe' + string('PlayerData') if index == 0 else b'\xfe\x00\x01'
    return result + string(reference) + string('Default')


@pytest.mark.parametrize('reference,display,raw_name,internal_id', [
    (':273831404:Eixeia1.1', 'Eixeia', 'Eixeia1.1', '273831404'),
    (':180250842:Ljubljana', 'Ljubljana', 'Ljubljana', '180250842'),
    (':152482145:Reeve Delta Map', 'Reeve Delta', 'Reeve Delta Map', '152482145'),
    (':185668233:Budapest, HU 2.0', 'Budapest', 'Budapest, HU 2.0', '185668233'),
    (':152079482:San Andreas', 'San Andreas', 'San Andreas', '152079482'),
    (':517000010:Szczecin (Stettin), Poland', 'Szczecin', 'Szczecin (Stettin), Poland', '517000010'),
    ('north_city', 'North City', 'north_city', 'north_city'),
])
def test_verified_header_reference_and_display_are_separate(reference, display, raw_name, internal_id):
    result = api().parse_save_map_header(header(reference))
    assert result.display_name == display
    assert result.raw_reference == reference
    assert result.raw_map_name == raw_name
    assert result.internal_id == internal_id
    assert result.source == 'save-header:m_originalMapName'
    assert result.status == 'known'
    assert result.format_version == 2013120900


def test_player_array_is_walked_instead_of_using_sample_offset():
    module = api()
    for players in (0, 1, 2, 4):
        result = module.parse_save_map_header(header(':180250842:Ljubljana', players=players))
        assert result.display_name == 'Ljubljana'
    # Valid reference to an already declared PlayerData rather than a new object.
    blob = header('North City', players=2)
    blob = blob.replace(b'\xfe\x00\x01', b'\x00\x00\x01', 1)
    assert module.parse_save_map_header(blob).display_name == 'North City'


@pytest.mark.parametrize('bad', [
    b'not-a-save' + header(':180250842:Ljubljana'),
    header(':180250842:Ljubljana', root_type='GameState+SerializableData'),
    header(':180250842:Ljubljana', version=2013021400),
    header(':180250842:Ljubljana')[:120],
    header(':180250842:Ljubljana').replace(string('PlayerData'), string('CompanyData'), 1),
    header(':180250842:Ljubljana').replace(b'\x00\x00\x01\xfe\xfe', b'\x00\x01\x00\xfe\xfe', 1),
    header(':180250842:Ljubljana').replace(string(':180250842:Ljubljana'), b'\x00\x00\x01\xd8\x00'),
    header(':180250842:Ljubljana').replace(string(':180250842:Ljubljana'), b'\x00\xff\xff'),
    header(':180250842:Ljubljana')[:-5],
])
def test_unverified_structure_length_or_encoding_never_scans_for_city_text(bad):
    result = api().parse_save_map_header(bad)
    assert result.status == 'unknown'
    assert result.display_name == '未提供城市名称'
    assert result.raw_reference == ''
    assert result.reason


def test_oversized_length_and_invalid_player_reference_are_bounded():
    module = api()
    for blob in (header('Ljubljana').replace(string('Ljubljana'), b'\xfe\xff\xff', 1),
                 header('Ljubljana', players=2).replace(b'\xfe\x00\x01', b'\xfe\x00\x20', 1)):
        assert module.parse_save_map_header(blob).status == 'unknown'


def test_reader_reads_only_bounded_prefix_and_never_writes(tmp_path, monkeypatch):
    module = api()
    blob = header(':273831404:Eixeia1.1') + b'payload-not-to-be-read' * 100000
    save = tmp_path / '任意文件名.save'
    save.write_bytes(blob)
    reads = []
    original = Path.open
    class Observed:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): return self
        def __exit__(self, *args): self.stream.close()
        def read(self, size):
            reads.append(size)
            assert 0 < size <= 16384
            return self.stream.read(size)
    def open_read_only(path, mode='r', *args, **kwargs):
        assert mode == 'rb'
        return Observed(original(path, mode, *args, **kwargs))
    with monkeypatch.context() as context:
        context.setattr(Path, 'open', open_read_only)
        result = module.read_save_map_name(save)
    assert reads == [16384]
    assert result.display_name == 'Eixeia'
    assert save.read_bytes() == blob


def test_utf16_character_count_handles_non_ascii_and_surrogate_pairs():
    result = api().parse_save_map_header(header('数字城 2 😀'))
    assert result.raw_reference == '数字城 2 😀'
    assert result.display_name == '数字城 2 😀'


@pytest.mark.parametrize('raw,expected', [
    ('District 9', 'District 9'), ('Route 66', 'Route 66'), ('City 2', 'City 2'),
    ('2012 City', '2012 City'), ('New York', 'New York'), ('Sector 1.1', 'Sector 1.1'),
    ('City v2.0', 'City'), ('City version 2.1', 'City'),
])
def test_normalization_preserves_intrinsic_numbers_and_only_removes_explicit_versions(raw, expected):
    assert api().normalize_map_reference(raw).display_name == expected


@pytest.mark.parametrize('raw,expected', [
    ('south_city', 'South City'), ('river_delta_2', 'River Delta 2'),
    ('route_66', 'Route 66'), ('new-york', 'New York'), ('CITY_2', 'City 2'),
    ('area_51', 'Area 51'), ('north_city_v2', 'North City'),
])
def test_explicit_internal_identifiers_are_readable_without_losing_original_digits(raw, expected):
    result = api().normalize_map_reference(raw)
    assert result.display_name == expected
    assert result.raw_reference == result.raw_map_name == result.internal_id == raw


def test_header_precedes_conflicting_legacy_metadata_and_filename(tmp_path):
    save = tmp_path / '秋山市n6 (2).save'
    save.write_bytes(header(':273831404:Eixeia1.1'))
    data = {'save_path': str(save), 'tag': '秋山市n6 (2)_运行时', 'metadata': {'地图名称': '秋山市n6 (2)'}}
    assert api().resolve_session_map_name(data).display_name == 'Eixeia'
    assert api().display_session_city_name(data) == 'Eixeia'


def test_reliable_metadata_can_back_up_missing_or_unsupported_header(tmp_path):
    data = {'save_path': str(tmp_path / '不存在.save'), 'metadata': {
        '地图原始引用': ':185668233:Budapest, HU 2.0', '地图名称来源': 'save-header:m_originalMapName'}}
    result = api().resolve_session_map_name(data)
    assert result.display_name == 'Budapest'
    assert result.source == 'metadata:save-header:m_originalMapName'
    save = tmp_path / '不支持.save'
    save.write_bytes(b'unsupported')
    data['save_path'] = str(save)
    assert api().resolve_session_map_name(data).display_name == 'Budapest'


def test_legacy_filename_fallback_and_unmarked_text_are_not_reliable_city_sources(tmp_path):
    for name in ('quicksave', 'quicksave.76561198362520556-76561198845688243', '秋山市n6 (2)', 'Ljubljana'):
        data = {'save_path': str(tmp_path / (name + '.save')), 'tag': name + '_运行时',
                'metadata': {'地图名称': name}}
        assert api().resolve_session_map_name(data).display_name == '未提供城市名称'
    data = {'metadata': {'地图原始引用': 'North City', '地图名称来源': 'filename-fallback'}}
    assert api().resolve_session_map_name(data).status == 'unknown'


def test_extractor_fields_preserve_reference_and_source_without_filename_fallback(tmp_path):
    fields = api().map_metadata_fields(tmp_path / '不存在.save', runtime_name='North City', runtime_source='runtime:m_cityName')
    assert fields['地图名称'] == 'North City'
    assert fields['地图原始引用'] == 'North City'
    assert fields['地图原始名称'] == 'North City'
    assert fields['地图名称来源'] == 'runtime:m_cityName'
    assert api().map_metadata_fields(tmp_path / '只有文件名.save')['地图名称'] == ''


def run_extractor_metadata_block(save):
    """Exercise only the authorized metadata block, without importing CLR/backend."""
    import ast
    source = Path(__file__).with_name('extract_runtime_data.py').read_text(encoding='utf-8')
    main = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    first = next(i for i, node in enumerate(main.body) if isinstance(node, ast.FunctionDef) and node.name == 'optional_text')
    last = next(i for i, node in enumerate(main.body) if isinstance(node, ast.Expr) and
                isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and
                node.value.func.id == 'write_csv' and isinstance(node.value.args[0], ast.Call) and
                isinstance(node.value.args[0].args[0], ast.Constant) and node.value.args[0].args[0].value == 'CIM2_城市历史元数据')
    output = []
    namespace = {'SAVE': save, 'root': {}, 'field': lambda obj, name: (obj or {}).get(name),
                 'OUT': lambda stem: stem, 'write_csv': lambda path, rows: output.extend(rows)}
    namespace.update({key: [] for key in ('company_info_rows', 'history_summary', 'lines', 'vehicle_rows',
                                         'timetable_rows', 'row_rows', 'stop_rows')})
    exec(compile(ast.Module(body=main.body[first:last + 1], type_ignores=[]), '<isolated-map-metadata>', 'exec'), namespace)
    return output[0]


def test_actual_extractor_metadata_block_emits_verified_original_map_fields(tmp_path):
    save = tmp_path / '秋山市n6 (2).save'
    save.write_bytes(header(':273831404:Eixeia1.1'))
    result = run_extractor_metadata_block(save)
    assert result['地图名称'] == 'Eixeia'
    assert result['地图原始引用'] == ':273831404:Eixeia1.1'
    assert result['地图原始名称'] == 'Eixeia1.1'
    assert result['地图内部标识'] == '273831404'
    assert result['地图名称来源'] == 'save-header:m_originalMapName'


def test_actual_extractor_metadata_block_does_not_write_save_stem_as_map(tmp_path):
    save = tmp_path / '只能知道存档名.save'
    save.write_bytes(b'unsupported')
    assert run_extractor_metadata_block(save)['地图名称'] == ''


def test_load_session_preserves_map_provenance_for_header_unavailable_fallback(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'frontend'))
    import report_model
    metadata = {'模拟当前时间': '2013-05-21 23:59:13',
                '地图名称': 'Eixeia', '地图原始引用': ':273831404:Eixeia1.1',
                '地图原始名称': 'Eixeia1.1', '地图内部标识': '273831404',
                '地图名称来源': 'save-header:m_originalMapName', '地图名称说明': '原始引用'}
    monkeypatch.setattr(report_model, 'read_csv', lambda directory, stem, tag:
                        [metadata] if stem == 'CIM2_城市历史元数据' else [])
    data = report_model.load_session(tmp_path, '任意缓存tag', catalog_dir=tmp_path)
    for key, expected in metadata.items():
        if key.startswith('地图'):
            assert data['metadata'][key] == expected
    assert api().display_session_city_name(data) == 'Eixeia'
    metadata.pop('地图名称来源')
    legacy = report_model.load_session(tmp_path, '任意缓存tag', catalog_dir=tmp_path)
    assert legacy['metadata']['地图名称'] == 'Eixeia'
    assert api().display_session_city_name(legacy) == '未提供城市名称'
