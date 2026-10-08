"""Approved dashboard labels. Explanatory UI copy requires user approval."""

TEXT = {
    'company': '公司数据看板', 'service': '服务规模看板',
    'passenger': '客流数据看板', 'city': '城市数据看板',
    'summary': '总统计数据', 'bar': '条形图', 'line': '折线图', 'pie': '饼图',
    'transfer-coefficient': '平均换乘系数', 'trip-types': '公司参与行程次数',
    'transport-by-group': '分群体客流', 'transport-by-type': '分制式客流',
    'alerts': '关键变化提醒', 'read-all': '全部标为已读', 'read': '标为已读',
    'export': '导出报表', 'export-png': '导出 PNG', 'export-xlsx': '导出 Excel',
    'missing': '—', 'companies': '公司', 'grain': '时间粒度',
    'time': '时间范围', 'comparison': '跨期对比', 'thresholds': '提醒阈值',
    'cashflow': '现金流', 'company-value': '公司价值', 'monthly-ticket': '月票使用率',
    'satisfaction': '满意度', 'satisfaction-speed': '速度满意度',
    'satisfaction-cost': '费用满意度', 'satisfaction-quality': '质量满意度',
    'reputation': '声誉', 'popularity': '受欢迎程度', 'linecount': '线路数',
    'stopcount': '站点数', 'depotcount': '车库数',
    'vehicles-running': '平均运行车辆数', 'coverage': '覆盖率', 'population': '人口',
    'economy': '经济增长／利率', 'energy-prices': '能源价格',
    'city-mode-share': '出行方式占比', 'trip-number': '出行量', 'traffic-density': '交通密度',
    'public-transport': '公共交通方式占比', 'private-motoring': '私人机动车方式占比',
    'walking': '步行方式占比',
    'hour': '小时', 'day': '日', 'week': '周', 'month': '月',
    'off': '关闭', 'previous': '上一等长区间', 'previous_week': '上周同期',
    'previous_month': '上月同期', 'custom': '自定义', 'apply': '应用',
    'reset': '重置', 'metrics': '多指标对比', 'open': '打开存档',
    'overview': '最新信息', 'lines': '线路查询', 'statistics': '统计数据',
    'current': '本期', 'comparison-value': '对比',
    'filters': '筛选条件', 'company-id': '公司标识', 'group': '分组', 'layer': '数据层', 'unit': '单位',
    'start': '开始时间', 'end': '结束时间', 'complete': '完整',
    'comparison-start': '对比开始', 'comparison-end': '对比结束',
    'comparison-complete': '对比完整',
    'threshold-points': '比例变化（百分点）', 'threshold-percent': '一般变化（%）',
    'threshold-passengers': '客流最小变化（人次）',
}

GROUPS = {
    '总计': '总计', 'BlueCollar': '蓝领', 'WhiteCollar': '白领',
    'BusinessPeople': '商务人士', 'Pensioner': '退休人士', 'Student': '学生',
    'Tourist': '游客', 'bus': '公交', 'tram': '有轨电车', 'trolley': '无轨电车',
    'metro': '地铁', 'monorail': '单轨', '单轨列车': '单轨', 'waterbus': '水上巴士', 'misc': '其他',
    'single-line': '单线', 'one-zone': '一区', 'two-zones': '二区',
    'three-zones': '三区', 'four-zones': '四区', 'growth': '经济增长',
    'interests': '利率', 'electricity': '电价', 'fuel': '燃油价格',
    'Road': '道路', 'Rail': '轨道', 'Track': '轨道', 'net-cash': '净现金',
    'infra-value': '基础设施价值', 'vehicles-value': '车辆价值', 'business-value': '业务价值',
}

def label(key):
    return TEXT.get(key, key)

def group_label(group):
    return ' · '.join(GROUPS.get(part, part) for part in group.split(' · '))
