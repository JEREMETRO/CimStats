"""Stable semantic identities shared by charts, maps, legends and exports."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from colorsys import hls_to_rgb
import stats_tokens as tokens


@dataclass(frozen=True)
class Category:
    key: str
    name: str
    color: str
    missing: bool = False


SOCIAL = tuple(Category(key, name, tokens.DATA_CATEGORY_COLORS[tokens.DATA_CATEGORY_GROUPS.index(key)])
               for key,name in (('BlueCollar','蓝领'),('WhiteCollar','白领'),
                                ('BusinessPeople','商务人士'),('Pensioner','退休人员'),
                                ('Student','学生'),('Tourist','游客')))
MODES = tuple(Category(key, name, tokens.transport_color(key)) for key, name in (
    ('bus', '公交'), ('tram', '有轨电车'), ('trolley', '无轨电车'),
    ('metro', '地铁'), ('waterbus', '水上巴士'), ('monorail', '单轨'),
)) + (Category('misc', '其他', '#72C7D9'),)
USAGES = tuple(Category(key, name, color) for key, name, color in (
    ('residential', '住宅', '#159A79'), ('commercial', '商业', '#1677FF'),
    ('work', '工作', '#D56464'), ('mixed', '商业／工作混合', '#A477E6'),
    ('transport', '交通建筑', '#D8AF43'), ('special', '特殊建筑', '#B9627F'),
))
PROFIT = (Category('profit', '盈利', '#159A79'), Category('loss', '亏损', '#C63864'),
          Category('zero', '持平', '#C49A37'), Category('missing', '数据缺失', '#98A8B9', True))
UNKNOWN = Category('unknown', '未分类', '#B7BCC2', True)
REGISTRY = {'social': SOCIAL, 'mode': MODES, 'usage': USAGES, 'profit': PROFIT}
MODE_ALIASES = {'公交': 'bus', '有轨电车': 'tram', '无轨电车': 'trolley',
                '地铁': 'metro', '水上巴士': 'waterbus', '单轨': 'monorail', '单轨列车': 'monorail',
                'trolleybus': 'trolley', 'ferry': 'waterbus'}


def stable_color(key, palette):
    return palette[int.from_bytes(sha256(str(key).encode('utf-8')).digest()[:4], 'big') % len(palette)]


def canonical_key(domain, key):
    return MODE_ALIASES.get(str(key), str(key)) if domain == 'mode' else str(key)


def category(domain, key):
    key = canonical_key(domain, key)
    for item in REGISTRY.get(domain, ()):
        if item.key == key:
            return item
    if key in ('unknown', 'AnySocialGroup', '', 'None'):
        return UNKNOWN
    # Retain the previous statistics fallback for unlisted serialized modes.
    color = stable_color('category:' + key, tokens.DATA_CATEGORY_COLORS)
    return Category(key, {'monorail': '单轨'}.get(key, key), color)


def company_palette(identities):
    """Use the complete save identity set, never a current selection."""
    return {key: tokens.DATA_COMPANY_COLORS[i % len(tokens.DATA_COMPANY_COLORS)]
            for i, key in enumerate(sorted(set(map(str, identities))))}


def color_for(domain, key):
    if domain == 'company':
        return stable_color('company:' + str(key), tokens.COMPANY_COLORS)
    if domain == 'line':
        digest = sha256(('line:' + str(key)).encode('utf-8')).digest()
        hue = int.from_bytes(digest[:4], 'big') / 2**32
        light = .39 + digest[4] / 255 * .15
        saturation = .58 + digest[5] / 255 * .20
        return '#' + ''.join(f'{round(channel*255):02X}' for channel in hls_to_rgb(hue,light,saturation))
    return category(domain, key).color


def mix_color(color, strength, background='#F4F2ED'):
    strength = max(0., min(1., float(strength)))
    parts = [round(int(background[i:i+2], 16) * (1-strength) + int(color[i:i+2], 16) * strength)
             for i in (1, 3, 5)]
    return '#' + ''.join(f'{part:02X}' for part in parts)


def map_fill(domain, key, strength=.20):
    return mix_color(color_for(domain, key), strength)


def building_function_fill(values, emphasis=False):
    """Shared functional hues, with native capacity ratios driving intensity."""
    amounts=(values.home,values.work,values.leisure)
    if values.denominator is None or any(v is None for v in amounts):
        return map_fill('usage','unknown',.42 if emphasis else .16)
    if values.denominator == 0 or max(amounts) == 0:
        return map_fill('usage','unknown',.18 if emphasis else .08)
    home,work,leisure=amounts
    mixed=min(work,leisure)
    weights=(('residential',home),('work',work-mixed),
             ('commercial',leisure-mixed),('mixed',mixed*2))
    total=sum(weight for _,weight in weights)
    base='#'+''.join(f'{round(sum(int(color_for("usage",key)[i:i+2],16)*weight for key,weight in weights)/total):02X}'
                     for i in (1,3,5))
    density=min(1.,max(amounts)/values.denominator)
    return mix_color(base,(.08+.77*density) if emphasis else (.12+.12*density))


def category_color_hex(group, palette=None):
    transport = tokens.transport_color(group)
    if transport is not None:
        return transport
    # Explicit custom palettes remain an existing supported chart API.
    if palette is not None and tuple(palette) != tokens.DATA_CATEGORY_COLORS:
        if group in tokens.DATA_CATEGORY_GROUPS:
            return palette[tokens.DATA_CATEGORY_GROUPS.index(group) % 6]
        return stable_color('category:' + group, palette)
    if group in {entry.key for entry in SOCIAL}:
        return color_for('social', group)
    return color_for('mode', group)


def line_palette(identities):
    colors = {}
    used = set()
    for identity in sorted(set(identities),key=str):
        color = color_for('line',identity)
        salt = 0
        while color in used:
            salt += 1
            color = color_for('line',f'{identity}:{salt}')
        colors[identity] = color
        used.add(color)
    return colors
