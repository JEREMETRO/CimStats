"""Two compact map information sections using the existing line-page values."""
from collections.abc import Mapping
from display_rules import display_mode
from line_query_page import line_display_value, line_query_name, shown
from map_service_time import session_line
from report_model import display_company


# Preserve the detail page's field order within the two requested categories.
_LINE_FIELDS = (
    ('线路车库', '线路车库', ''),
    ('开线日期', '开线日期', ''),
    ('最近改线日期', '最近改线日期', ''),
    ('地图里程', '地图里程（全线）', 'km'),
    ('单程时间', '核定时间（全线）', 'min'),
    ('核定速度', '核定速度', 'km/h'),
    ('站点数', '站点数', '站'),
    ('当日发班数', '当日发班', '班'),
    ('平均间隔', '平均间隔', ''),
    ('理论最大车辆需求数', '最大车辆需求', '辆'),
    ('平均车辆需求数', '平均车辆需求', '辆'),
    ('每周收入', '每周收入', ''),
    ('每周支出', '每周支出', ''),
)
_PASSENGER_FIELDS = (
    ('今日客流', '今日客流', '人次'),
    ('平均客流', '平均客流', '人次'),
    ('今日平均单班人次', '今日平均单班人次', ''),
    ('今日平均车公里人次', '今日平均车公里人次', ''),
)


def line_information(session, route_id, *, direction_metrics=None):
    """Resolve a unique stable object ID, preserving the line page's missing rules."""
    line = session_line(session, route_id)
    if line is None:
        return None
    lines = (session or {}).get('lines', ())
    def metric(key):
        return (direction_metrics.get(key) if isinstance(direction_metrics, Mapping)
                else getattr(direction_metrics, key, None))
    direction = metric('effective_direction') if direction_metrics is not None else 'whole'
    if direction not in ('up', 'down', 'whole'):
        raise ValueError('Unknown information direction')
    suffix = {'up':'上行','down':'下行','whole':'全线'}[direction]

    def rows(fields):
        result=[]
        for key,title,unit in fields:
            if key == '地图里程' and direction != 'whole':
                continue
            value = line_display_value(line, key, lines)
            if key in ('单程时间', '核定速度'):
                title = f'{"核定时间" if key == "单程时间" else "核定速度"}（{suffix}）'
                if direction_metrics is not None and direction != 'whole':
                    value = metric('duration_minutes' if key == '单程时间' else 'speed_kmh')
            result.append((key,title,shown(value,unit)))
        return tuple(result)

    return {
        'direction': direction,
        'identity': dict(id=route_id, name=line_query_name(line, lines),
                         mode=display_mode(line.get('运输制式', '')),
                         company_name=display_company(line.get('公司名称', '')),
                         company_id=line.get('公司标识')),
        'sections': (
            ('line_information', '线路信息', rows(_LINE_FIELDS)),
            ('passenger_data', '客流数据', rows(_PASSENGER_FIELDS)),
        ),
    }
