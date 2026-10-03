# 网络数据增量重构：已批准执行计划

## 最新布局与覆盖率显示修订

用户确认目前无法展示多公司联合覆盖率：多公司总体模式保留覆盖率数据接口、图卡与摘要组件代码供未来扩展，但当前不显示对应摘要或图卡，不留下空白槽/占位解释；单公司和公司对比/同期已有覆盖率能力保留。此条覆盖旧总体六位置与固定八张可见图要求：保留基础指标定义，显示数量按当前可用策略过滤，不改变其他图序。

总体模式优先顶部一行紧凑摘要、下方集中图表。多公司总体隐藏覆盖率后五项摘要一行；整体压缩无意义空隙，不新增左侧独立滚动栏。窄窗自适应换行。尽量减少纵向滚动，但不能裁轴、缩小文字或牺牲图形可读性；网络绘图区最小高度约180仍需合理验证。其他比较模式维持已批准的按公司分组结构。

所有数据卡片数值与单位同排并按文字基线对齐，单位不能沉到下一行或卡片底部。KPI字体大小差异不应导致单位视觉下坠，长数值/百分比/倍/辆等均须实看；必要宽度重排但不强制截断数据。共享KPI样式同样检查公司页，布局与截图验收以此为准。

## 最新数据卡片口径（覆盖此前区间平均约定）

用户明确：平均运行车辆数、覆盖率、换乘系数的数据卡片取统计范围最后一天的日内平均，不取整个选定区间的平均；线路数、站点数、车库数的数据卡片取截止时间前最新有效值。趋势图必须保留各时间桶的变化，不能复用卡片汇总值画平线，也不能仅留下最后一天。卡片查询窗口与趋势完整窗口分别处理，共用原始数据，不额外解析存档。

最后一天按所选统计范围确定：结束时间为午夜且采用[start,end)时，取其前一个自然日；结束时间位于日内时，仅使用当天截至结束时间的有效数据，不读取未来数据。该日无数据应如实空缺，不暗中换成整个区间均值。日内缺测不补零。换乘系数的日内统计仍需使用同一天总客流/总分区出行量这一已指定分子分母口径，不能混用全区间总量；覆盖率日内观测的真实总体语义继续核查。最终结果测试应覆盖前几天与最后一天明显不同，证明卡片只取最后一天而趋势保留完整区间。

## 最新图形与时点口径修订

用户要求：多公司对比模式下，线路数、站点数等数量指标的趋势按公司合计，每家公司一条总数曲线，不按制式拆线；分制式信息只在切换到分类条形图后显示。站点按游戏现有分类数量口径合计，不能宣称物理去重，但界面标题只写“站点数”，不添加技术括注。此条覆盖下文旧“站点趋势保留制式分类、不制造总量”要求。

不反映时间变化的数量型分类条形图，一律取对应统计截止时间之前的最新有效观测，不取区间均值；不能读取截止之后的记录。若有效期末缺失、类别/公司时点不齐，保持真实缺测/完整性，不补零，不拿不同日期末值伪称同刻。同期分别按本期和对比期各自截止时间取数。用户允许客流、出行量等平均有意义的非控制型指标使用平均口径，须按既有桶粒度与有效观测明确分母，不混同存量。换乘系数继续遵守用户已指定的总客流/总分区出行量，不平均各公司或各时间桶系数。本条针对趋势系列组织与不带时间轴的条形图，不擅改时间柱状图各桶流量或公司份额饼分母。

绘制偏好仅改变视图，不触发重新解析存档。数据适配须提供足够的公司合计趋势与制式期末数据，避免渲染器随意summarize导致误用平均值。具体指标映射和测试证据写入开发文档，不向界面追加解释性文字。

## 用户最新数据纠正（优先于下文旧能力限制）

数据整理、源字段挖掘、计算修复与独立核查统一使用GPT-6 Sol/high；原Luna验收会话已改为Sol/high。UI文案须严格去除擅自添加的口径括注与实现解释，如“站点数（游戏历史口径）”改为“站点数”。只保留业务名称、单位、日期、公司/周期图例、操作所需标签及简短真实状态，技术说明留文档，不把长篇说明转移到tooltip敷衍。所有用户可达页面和图卡都需排查。清理文案不得掩盖真实缺失或伪造数据；演示截图仍需标明合成数据。

用户已指出：公司数据中存在可取得的总体数据，总体模式下所有要求字段都应展示总体数据；换乘系数明确为总客流除以总分区出行量。必须先核对原始总体记录、公司标识、字段与时间范围，优先使用真实总体记录，不能因旧设计预设而主动丢弃数据或恒显示“总体不可计算”。总体摘要、各图卡及导出共用同一口径；换乘系数由总量分子/总量分母直接相除，不能平均公司或时间桶的系数，分群体客流不重复相加。总体记录的全公司/选定子集范围必须查明并与筛选一致，不能暗中扩大范围。最大值等字段同样先查真实来源，不能用未经证实的代理值填充。真实缺失和零分母仍如实标记。本轮由B统一修改网络模型与接入，Luna独立验收，不让旧限制阻止正确取数。

实施同时遵守[VISUAL-ACCEPTANCE.md](VISUAL-ACCEPTANCE.md)：图形模式与摘要口径使用明确分段按钮；每次阶段返回前实际打开原图与运行截图逐项自查。

日期2026-09-29。用户已明确要求实施。沿用DESIGN.md、VISUAL-CONTRACT.md和stats_tokens.py的Fluent视觉系统；本文件的网络业务规则优先于效果图。

## 原图（UI及图表会话必须实际打开）

![总体数据参考](references/03-网络数据1.png)
![多公司对比参考](references/04-网络数据2.png)
![按公司同期对比参考](references/05-网络数据3.png)

删除图中的企业插画、宣传语、装饰状态、重复说明、无依据增长箭头。不得写死公司名/数值/日期；不得遗漏文字要求的图卡。全局时间沿用上一完整周/上一完整日/日历自定义，不恢复常驻手输日期。第三模式为单公司同期对比，默认上一等长周期，显示环比/上周同期/上月同期/自定义的真实关系，不统一写同比。

## 布局与模式

固定筛选，统一正文滚动；网络不追求一屏全部展示。公司/城市业务不变。

- overall（总体数据模式）：六位置摘要一套，八图一套；统计范围仅已选公司，不能扩大为全市。
- companies（多公司对比模式）：按公司分组完整摘要，下方按指标共享比较图。少于两家禁用；选择降为一家时回到overall并提示；三家以上摘要换行。九图，增加分公司客流。
- period（单公司同期对比）：按公司等宽双栏，各栏摘要后为单列八图；本公司只比较自己的两个周期。窄屏上下排列，同类图对齐，无独立滚动。
- 摘要固定六位置：线路数；车库数/站点数（默认车库）；平均/最大运行车辆（默认平均）；覆盖率；客流/出行量（默认客流）；换乘系数。
- 摘要优先3×2，切换在标题内，跨公司同步。车辆口径同步摘要和车辆图，但不改变图形类型；设施/客流切换不移除任何独立图卡。
- overall/companies主图区3/2/1列，图卡最低约360逻辑像素宽，绘图区高>=180。period每公司列内一列图卡。

## 图表清单与能力

固定顺序：linecount、stopcount、coverage、vehicles-running、transfer-coefficient、transport-by-type、transport-by-group、trip-types；companies追加company-passengers。

- 线路/站点：line或bar（制式横条）；小时仅bar，切回其他粒度恢复此前line偏好。站点趋势保留制式分类，不制造总量。
- 覆盖率仅line，小时保留图卡与不可用提示，不画小时趋势。
- 运行车辆line/bar，平均/最大独立状态；真实峰值无来源时占位不可用。
- 换乘系数仅line，不做好坏评价。
- 三类客流/出行：trend-bar（横轴时间）或pie；company-passengers同样两种图形但仅companies模式显示。
- 每卡独立保存图形偏好，只显示一种图形，不同时塞柱图和微饼。
- 总体分类时间柱可按类别堆叠；跨公司为公司并列、公司内分类堆叠；同期为周期并列、周期内分类堆叠。类别用稳定色，公司/周期用组标签或其他独立编码，不让颜色承担两种含义。
- 跨公司分类饼在同卡内各公司一饼；同期同卡本期/对比期双饼。company-passengers例外为一张公司份额饼，分母仅已选公司。
- 同指标共量程/单位/时间。图例隐藏不改数值或分母，全屏保留图形、口径、图例；tooltip含真实日期、公司、类别、数值、完整性。

## 数据约束

复用DashboardResult中的真实Result/Bucket/raw，不修改统计核心或重解析存档。

- 存量仅同一有效期末时点合成，不跨小时相加，不拼不同日期各自末值。
- 车辆总体平均先在可比观测时刻合成，再时间加权；各公司缺测不能默认为零，部分覆盖保留不完整标记。
- 现有小时均值不支持瞬时最大值；最大车辆显示不可用原因，不用max(小时均值)、拥有量或班表推断冒充。
- 多公司总体覆盖率没有去重空间依据，显示总体不可计算并保留分公司值；单公司保留真实查询值。
- 站点只保留游戏历史分类，不制造跨公司或跨制式物理去重总量；摘要同一位置可用分类明细。
- 换乘系数由已选范围有效客流分子和出行量分母聚合后相除，不平均公司比值。缺失保留，零分母不可用。
- 客流用transport-by-type，分群体是另一种分解，不能重复相加。
- 数值与图来自同快照，历史不存在显示无对应历史数据，不补0/插值/伪线。变化只有有效可比周期才显示，百分比差为百分点。

## N 数据接口与所有权（复用data工作树，Sol high）

新增src/network_model.py、src/test_network_model.py；只改这些及自己的数据能力说明，不改dashboard_model/statistics_model/统计页/图表。先完成可消费接口与人工可复算测试，再提交。以下为约定接口，若实际需要改动先协调，禁止UI猜私有结构。

```python
@dataclass(frozen=True)
class NetworkOptions:
    mode: str = 'overall'  # overall|companies|period
    facility: str = 'depotcount'  # depotcount|stopcount
    vehicle: str = 'average'  # average|maximum
    passenger: str = 'transport-by-type'  # transport-by-type|trip-types
    comparison_label: str = '环比'

@dataclass(frozen=True)
class NetworkValue:
    metric_id: str
    title: str
    unit: str
    value: Decimal | None
    details: tuple[tuple[str, Decimal | None], ...] = ()
    complete: bool = False
    reason: str = ''

@dataclass(frozen=True)
class NetworkSummary:
    company_id: str | None  # None为已选公司总体，不是假公司ID
    title: str
    values: tuple[NetworkValue, ...]  # 固定六位置

@dataclass(frozen=True)
class NetworkChart:
    key: str  # 固定八/九指标键
    title: str
    company_id: str | None  # period为所属公司，其余None
    result: Result | None
    allowed_modes: tuple[str, ...]
    reason: str = ''

@dataclass(frozen=True)
class NetworkSnapshot:
    filters: FilterState
    options: NetworkOptions
    companies: dict[str, str]
    summaries: tuple[NetworkSummary, ...]
    charts: tuple[NetworkChart, ...]

def build_network_snapshot(snapshot: DashboardResult, options: NetworkOptions,
                           companies: dict[str, str], cancelled=None) -> NetworkSnapshot: ...
```

总体Result若需要内部总体series键，使用明确的'__selected__'仅用于结果展示，不进入实际公司查询；companies映射保留真实公司，不污染公司身份。处理期间支持cancelled抛QueryCancelled。过滤无公司不等于所有公司。数据层不管理图例或UI偏好。

## C 图表扩展（原charts会话，Sol high）

先完成并提交当前公司图表，再实现网络图表，所有共享stats_charts.py仍由C单独拥有。优先新增frontend/network_charts.py及src/test_network_charts.py以隔离网络分类逻辑；底层继续QtCharts，统一消费tokens。

公开组件NetworkChartPanel(parent=None)，set_descriptor(descriptor: NetworkChart, snapshot: NetworkSnapshot)、set_mode(mode: str)、set_company_palette(palette: dict[str,str])、clear()，以及现有风格的真实全屏按钮。由N的descriptor和NetworkSnapshot.options区分总体/公司/周期组织，不靠公司数量猜模式。

默认使用descriptor.allowed_modes第一项（line优先；客流trend-bar优先）。图卡头部图形选择归网络UI外层所有，Panel只负责绘图/图例/tooltip/全屏。不读取UI的私有属性。不等长同期保留完整比较期，tooltip显示原日期。

## B 网络内容及页面接入（原UI会话，Sol high）

先完成并提交当前总体框架，不在未完成公司功能上混写网络功能。之后新增frontend/network_dashboard.py及src/test_network_dashboard.py；由原B唯一修改statistics_page.py和stats_integration.py。网络内容先作为独立组件开发，接入最后做，无需新增工作树。

NetworkDashboard(settings=None,parent=None)：set_snapshot(snapshot:NetworkSnapshot)、set_company_palette(palette)、clear()、export_target()->QWidget；options_changed=Signal(object)发送NetworkOptions。摘要口径影响数据描述，图形/图例仅本地重绘。图形偏好使用network/<metric>/chart_mode键，同指标所有公司共享图形偏好，与公司页设置隔离。

公司/范围/粒度为全局筛选；mode及comparison选择按子选项卡保存。network overall与公司default不同，不共用含义。页面现有worker中构建network snapshot，与同一token绑定后同时发布，不另开解析线程。网络模式/口径变化复用已有原始快照可在worker重新构建展示模型，不重新解析；纯图形不查询。

网络导出PNG为完整网络内容。XLSX保留已有明细，新增网络摘要页：模式、范围、公司、指标口径、值/单位、完整性、不可用原因及分类详情；从当前有效NetworkSnapshot导出，取消/过期快照不得导出。stats_exports.py和相应导出测试由B所有（公司明细不改动）。

## 验收与协调

- 人工复算测试：存量不同末时点、车辆错开缺测、系数零分母/缺失、站点分类、覆盖率不可合并、缺峰值、选择子集、空选择、分类不重复累计。
- 组件测试：三模式8/9图、六位置三开关、图形独立与小时恢复、少于两公司回退、周期身份正确、图例分母不变、异步旧结果拒收、导出一致。
- 真实存档截图：单/双总体、跨公司、按公司同期、全部图卡滚动、日期弹窗、窄窗和DPI。允许数据限制占位，不用示例数值伪装真实结果。
- 整合后Luna high独立验收；复用空闲data工作树，不新增平级目录；不发布/覆盖正式dist。
- 子会话不自行合并其他分支、不创建子代理/额外工作树；阶段完成后提交并报告，主会话在稳定提交点同步。所有删除使用Windows回收站。
