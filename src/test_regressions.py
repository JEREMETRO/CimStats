import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'frontend'))
from report_model import format_line_name, display_mode, _line_metrics
from save_container import locate_payload


@pytest.mark.parametrize('offset,padding', [(0x26000, 5), (0x27000, 0), (0x26000, 36), (0x2A000, 200)])
def test_payload_without_long_zero_padding(tmp_path, offset, padding):
    payload = b'\xfd\x77\xfd\xc9' + b'valid serialized content' * 100
    compressed = zlib.compress(payload, wbits=-15)
    path = tmp_path / '中文路径.save'
    path.write_bytes(b'x' * (offset - padding) + b'\0' * padding + compressed + b'trailer')
    location, actual = locate_payload(path)
    assert location.offset == offset
    assert location.compressed_size == len(compressed)
    assert actual == payload


@pytest.mark.parametrize('name,expected', [('', '12路'), ('A', '12A'), ('5-C', '5C'), ('101快线', '101快线'), ('机场', '12路机场'), ('旅游专线', '12路·旅游专线')])
def test_route_display(name, expected):
    assert format_line_name(12, name) == expected


@pytest.mark.parametrize('mode,expected', [('bus','公交'), ('trolley','无轨电车'), ('tram','有轨电车'), ('waterbus','水上巴士'), ('metro','地铁'), ('monorail','单轨列车'), ('ship','水上巴士')])
def test_modes(mode, expected):
    assert display_mode(mode) == expected


def test_reject_invalid_container(tmp_path):
    path = tmp_path / 'bad.save'
    path.write_bytes(b'not a save' * 20000)
    with pytest.raises(ValueError):
        locate_payload(path)


def test_metrics_zero_denominator():
    result = _line_metrics({'客流_今日': '100'}, [], 2, 0)
    assert result['今日平均单班人次'] == 0
    assert result['今日平均车公里人次'] == 0


def test_metrics_use_active_day_and_vehicle_km():
    result = _line_metrics({'客流_今日': '120'}, [
        {'时刻表_运行日掩码': '2'}, {'时刻表_运行日掩码': '2'},
        {'时刻表_运行日掩码': '4'},
    ], 2, 3)
    assert result['今日平均单班人次'] == 60
    assert result['今日平均车公里人次'] == 20
