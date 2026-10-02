"""Read the bounded CIM2 metadata prefix; preserve original map-name provenance.

This is not a save deserializer. It supports the audited 2013120900 metadata
schema and refuses other schemas, malformed declarations and oversized fields.
No payload decompression, CLR, Qt, filename inference or write operation occurs.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
import unicodedata

MAX_HEADER_BYTES = 16384
MAX_STRING_UNITS = 2048
MAX_PLAYERS = 32
FORMAT_VERSION = 2013120900
MISSING_CITY = '未提供城市名称'
HEADER_SOURCE = 'save-header:m_originalMapName'
RELIABLE_SOURCES = frozenset((HEADER_SOURCE, 'runtime:m_originalMapName',
                             'runtime:m_mapName', 'runtime:m_scenarioName', 'runtime:m_cityName'))


@dataclass(frozen=True)
class MapNameInfo:
    display_name: str = MISSING_CITY
    raw_reference: str = ''
    raw_map_name: str = ''
    internal_id: str = ''
    source: str = ''
    status: str = 'unknown'
    reason: str = ''
    format_version: int | None = None
    read_bytes: int = 0


def normalize_map_reference(reference: str, *, source: str = 'original-map-reference') -> MapNameInfo:
    """Normalize explicit original-map text, never a filename or arbitrary header scan.

    Unmarked numeric suffixes are preserved. The four exceptional suffix/region
    removals are limited to verified Workshop-ID + exact-name pairs.
    """
    if not isinstance(reference, str) or not reference.strip():
        return MapNameInfo(source=source, status='missing', reason='原始地图名称未提供')
    if len(reference.encode('utf-16-be', errors='surrogatepass')) // 2 > MAX_STRING_UNITS or any(
            unicodedata.category(char) in ('Cc', 'Cs') for char in reference):
        return MapNameInfo(source=source, reason='原始地图名称含无效编码、控制字符或超限长度')
    raw_name = reference.strip()
    internal_id = ''
    if raw_name.startswith(':'):
        match = re.fullmatch(r':([0-9]{1,20}):(.+)', raw_name)
        if not match:
            return MapNameInfo(source=source, reason='地图引用内部标识格式不支持')
        internal_id, raw_name = match.groups()
    aliases = {
        ('273831404', 'Eixeia1.1'): 'Eixeia',
        ('152482145', 'Reeve Delta Map'): 'Reeve Delta',
        ('185668233', 'Budapest, HU 2.0'): 'Budapest',
        ('517000010', 'Szczecin (Stettin), Poland'): 'Szczecin',
    }
    display = aliases.get((internal_id, raw_name), raw_name)
    # Only an explicit ASCII identifier with underscore/hyphen separators is
    # prettified. This acts on the original map field, never SAVE.stem/tag.
    if re.fullmatch(r'[A-Za-z][A-Za-z0-9]*(?:[_-][A-Za-z0-9]+)+', raw_name):
        if not internal_id:
            internal_id = raw_name
        display = ' '.join(token.capitalize() for token in re.split(r'[_-]', raw_name))
    # Explicit version words distinguish versions from intrinsic city digits.
    display = re.sub(r'\s+(?:v(?:ersion)?\.?\s*)\d+(?:\.\d+)*(?:[a-z])?$', '', display,
                     flags=re.IGNORECASE).strip()
    if not display:
        return MapNameInfo(source=source, reason='标准化后没有有效城市名称')
    return MapNameInfo(display, reference, raw_name, internal_id, source, 'known',
                       '原始地图引用；已核验别名或明确版本标记标准化，保留原始值')


class _Unsupported(ValueError):
    pass


class _PrefixReader:
    def __init__(self, data):
        self.data = memoryview(data)[:MAX_HEADER_BYTES]
        self.position = 0
        self.types = []
        self.objects = []

    def take(self, count):
        if count < 0 or self.position + count > len(self.data):
            raise _Unsupported('文件头截断或字段越界')
        result = self.data[self.position:self.position + count].tobytes()
        self.position += count
        return result

    def integer(self, count):
        return int.from_bytes(self.take(count), 'big')

    def string(self):
        first = self.integer(1)
        if first == 255:
            return None
        units = (first << 16) | self.integer(2)
        if units > MAX_STRING_UNITS:
            raise _Unsupported('UTF-16 字符数超出有界读取限制')
        try:
            return self.take(units * 2).decode('utf-16-be', errors='strict')
        except UnicodeDecodeError as error:
            raise _Unsupported('UTF-16BE 编码无效') from error

    def shared_type(self):
        marker = self.integer(1)
        if marker == 254:
            name = self.string()
            if not name:
                raise _Unsupported('类型声明缺失')
            self.types.append(name)
            return name
        if marker == 255:
            raise _Unsupported('不支持空类型声明')
        index = (marker << 8) | self.integer(1)
        if index >= len(self.types):
            raise _Unsupported('共享类型引用越界')
        return self.types[index]

    def object_type(self):
        marker = self.integer(1)
        if marker == 255:
            return None
        if marker == 254:
            name = self.shared_type()
            self.objects.append(name)
            return name
        index = (marker << 16) | self.integer(2)
        if index >= len(self.objects):
            raise _Unsupported('对象引用越界')
        return self.objects[index]


def parse_save_map_header(header: bytes) -> MapNameInfo:
    """Walk the verified type/field schema, rather than reading a fixed offset."""
    reader = _PrefixReader(header)
    version = None
    try:
        if reader.integer(1) != 253:
            raise _Unsupported('不支持的存档流标记')
        version = reader.integer(4)
        if version != FORMAT_VERSION:
            raise _Unsupported('不支持的元数据序列化版本')
        if reader.object_type() != 'GameState+SerializableMetaData':
            raise _Unsupported('根对象不是已核验的 SerializableMetaData')
        reader.take(4)  # m_simulationFrame: UInt32
        reader.take(8 * 6)  # four DateTime ticks and two TimeSpan ticks
        first = reader.integer(1)
        players = 0 if first == 255 else (first << 16) | reader.integer(2)
        if players > MAX_PLAYERS:
            raise _Unsupported('玩家声明数量超出有界限制')
        for _ in range(players):
            if reader.object_type() not in ('PlayerData', None):
                raise _Unsupported('玩家数组含不支持的对象类型')
        reference = reader.string()  # m_originalMapName: unique string
        reader.string()  # m_environment follows it; also validate its bounds/encoding.
        info = normalize_map_reference(reference, source=HEADER_SOURCE)
        return replace(info, format_version=version, read_bytes=reader.position)
    except _Unsupported as error:
        return MapNameInfo(source=HEADER_SOURCE, reason=str(error), format_version=version,
                           read_bytes=reader.position)


def read_save_map_name(save_path: str | Path) -> MapNameInfo:
    """Read at most 16 KiB from an existing save in binary read-only mode."""
    try:
        with Path(save_path).open('rb') as stream:
            header = stream.read(MAX_HEADER_BYTES)
    except (OSError, ValueError, TypeError) as error:
        return MapNameInfo(source=HEADER_SOURCE, reason=f'存档文件头不可读取：{type(error).__name__}')
    return parse_save_map_header(header)


def resolve_session_map_name(data: dict) -> MapNameInfo:
    """Shared synchronous metadata display for set_session and the worker snapshot.

    Legacy unmarked ``地图名称`` is not trusted: the old extractor populated it
    from SAVE.stem when the original map field was unavailable. No filename-shape
    heuristic can reliably distinguish that fallback from an actual city label.
    """
    header_info = None
    if data.get('save_path'):
        header_info = read_save_map_name(data['save_path'])
        if header_info.status == 'known':
            return header_info
    metadata = data.get('metadata') or {}
    source = str(metadata.get('地图名称来源') or '')
    if source in RELIABLE_SOURCES:
        reference = metadata.get('地图原始引用') or metadata.get('地图原始名称') or metadata.get('地图名称')
        info = normalize_map_reference(reference, source='metadata:' + source)
        if info.status == 'known':
            return info
    reason = '旧缓存地图文本缺少可靠原始名称来源；不把存档文件名或导出 tag 当城市'
    if header_info:
        reason = header_info.reason + '；' + reason
    return MapNameInfo(reason=reason)


def display_session_city_name(data: dict) -> str:
    """Public pure-Python display entry point; identical to the snapshot resolver."""
    return resolve_session_map_name(data).display_name


def map_metadata_fields(save_path: str | Path, *, runtime_name: str = '', runtime_source: str = '') -> dict[str, str]:
    """Metadata block adapter for extraction; never falls back to SAVE.stem."""
    info = read_save_map_name(save_path)
    if info.status != 'known' and runtime_name and runtime_source in RELIABLE_SOURCES - {HEADER_SOURCE}:
        info = normalize_map_reference(runtime_name, source=runtime_source)
    return {'地图名称': info.display_name if info.status == 'known' else '',
            '地图原始引用': info.raw_reference, '地图原始名称': info.raw_map_name,
            '地图内部标识': info.internal_id, '地图名称来源': info.source,
            '地图名称说明': info.reason}
