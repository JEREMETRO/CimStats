"""Stable semantic identities shared by charts, maps, legends and exports."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from colorsys import hls_to_rgb
from math import isfinite
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


@dataclass(frozen=True)
class MetricScale:
    title: str
    unit: str
    anchors: tuple
    ranges: tuple
    labels: tuple


METRIC_SCALES = {
    'interval': MetricScale('平均间隔','min',
        ((5,'#5A1020'),(7.5,'#E52222'),(12.5,'#FF8A00'),
         (17.5,'#F3CF32'),(25,'#A6CE39'),(37.5,'#2E8B57'),(45,'#173D6E')),
        ((5,5),(5,10),(10,15),(15,20),(20,30),(30,45),(45,45)),
        ('≤5','5–10','10–15','15–20','20–30','30–45','≥45')),
    'interval_peak': MetricScale('平均间隔','min',
        ((3,'#350916'),(4,'#E52222'),(6.5,'#FF8A00'),(10,'#F3CF32'),
         (15,'#A6CE39'),(21.5,'#2E8B57'),(25,'#173D6E')),
        ((3,3),(3,5),(5,8),(8,12),(12,18),(18,25),(25,25)),
        ('≤3','3–5','5–8','8–12','12–18','18–25','≥25')),
    'passengers': MetricScale('客流','千人次',
        ((1000,'#173D6E'),(3000,'#2E8B57'),(7500,'#F3CF32'),(15000,'#F2AA24'),
         (25000,'#E45F2B'),(40000,'#D32F2F'),(50000,'#5A1020')),
        ((1000,1000),(1000,5000),(5000,10000),(10000,20000),
         (20000,30000),(30000,50000),(50000,50000)),
        ('<1','1–5','5–10','10–20','20–30','30–50','≥50')),
}


def metric_color(metric,value):
    """Continuous RGB colour; categorical labels describe representative ranges."""
    scale=METRIC_SCALES[metric]
    try:number=float(value) if not isinstance(value,bool) else float('nan')
    except (ValueError,TypeError):number=float('nan')
    if not isfinite(number) or number<0:return PROFIT[-1].color
    if number<=scale.anchors[0][0]:return scale.anchors[0][1]
    for (low,first),(high,second) in zip(scale.anchors,scale.anchors[1:]):
        if number<=high:
            factor=(number-low)/(high-low)
            return '#'+''.join(f'{round(int(first[i:i+2],16)*(1-factor)+int(second[i:i+2],16)*factor):02X}'
                               for i in (1,3,5))
    return scale.anchors[-1][1]


@dataclass(frozen=True)
class MetricLegend:
    metric: str
    date: str | None
    source: str | None = None

    @property
    def title(self):
        if self.metric=='passengers':
            return {'today':'今日客流','average':'平均客流'}.get(self.source,'客流')
        return METRIC_SCALES[self.metric].title
    @property
    def unit(self):return METRIC_SCALES[self.metric].unit
    @property
    def labels(self):return METRIC_SCALES[self.metric].labels
    @property
    def missing_colour(self):return PROFIT[-1].color
    @property
    def heading(self):return f'{self.title}/{self.unit} · {self.date or "日期未知"}'

    @property
    def gradient_stops(self):
        """Equal range bands, with exact stops from the map's same RGB resolver."""
        scale=METRIC_SCALES[self.metric];count=len(scale.ranges);stops={}
        for index,(low,high) in enumerate(scale.ranges):
            if low==high:
                stops[index/count]=stops[(index+1)/count]=metric_color(self.metric,low)
                continue
            values={low,high}|{value for value,_ in scale.anchors if low<value<high}
            for value in sorted(values):
                stops[(index+(value-low)/(high-low))/count]=metric_color(self.metric,value)
        return tuple(sorted(stops.items()))

    def __iter__(self):
        # Existing pair-based legend consumers remain compatible until drawn as a ramp.
        scale=METRIC_SCALES[self.metric]
        items=[(label,metric_color(self.metric,(low+high)/2))
               for label,(low,high) in zip(scale.labels,scale.ranges)]
        items[0]=(self.heading+' '+items[0][0],items[0][1])
        return iter((*items,('数据缺失',self.missing_colour)))


def metric_legend(metric,date=None,source=None):
    return MetricLegend(metric,date or None,source)
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
