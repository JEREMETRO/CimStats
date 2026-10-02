"""Shared presentation rules for parser, desktop, and workbook output."""
import re

MODE_NAMES = {
    "bus": "公交", "trolley": "无轨电车", "trolleybus": "无轨电车",
    "tram": "有轨电车", "metro": "地铁", "subway": "地铁",
    "monorail": "单轨列车", "waterbus": "水上巴士", "ferry": "水上巴士",
    "ship": "水上巴士", "anyvehicletype": "综合",
}


def display_mode(value):
    raw = str(value or "").strip()
    return MODE_NAMES.get(raw.lower(), raw)


def format_line_name(number_value, raw_name):
    number_text = str(int(float(number_value or 0)))
    name = str(raw_name or "").strip()
    if not name:
        return f"{number_text}路"
    if re.fullmatch(r"[A-Za-z]", name):
        return f'{number_text}{name}'
    suffix = re.fullmatch(r"(\d+)(?:路-?|-)?([A-Za-z])", name)
    if suffix:
        return ''.join(suffix.groups())
    if name.isdigit():
        return f'{name}路'
    if re.match(r"\d", name):
        return name
    if len(name) < 3:
        return f"{number_text}路{name}"
    return f"{number_text}路·{name}"


def format_garage(company, mode, value):
    """Keep serialized depot names; only bare positive indices need a label."""
    raw = str(value or '').strip()
    if not raw or raw.lower() in ('unknown', 'none', 'null', '未知', '—'):
        return ''
    if re.fullmatch(r'[-+]?\d+(?:\.0+)?', raw):
        index = int(float(raw))
        if index <= 0:
            return ''
        if not company or not mode:
            return ''
        return f'{company}{mode}车库{index}'
    return raw if not company or raw.startswith(company) else f'{company}{raw}'
