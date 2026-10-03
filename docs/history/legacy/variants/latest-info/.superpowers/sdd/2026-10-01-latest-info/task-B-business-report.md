# B 四业务模块与最新极值卡修订交付

日期：2026-10-02。父已正式开放B独占串行离屏Qt槽。本轮仅写B四个自有产品/测试文件和本目录证据；没有修改A/C/D、统计页共享绘制或色板、主树、Git index、存档、缓存或探针。最后确认无Python/pythonw/parser_backend进程，B槽已完成，可由父移交E。

## 逐项落实

|区域|实际改变|证据与限制|
|---|---|---|
|指标分组|13项各出现一次，组成网络规模（线路/车辆）、经营收支（收入/支出/净利润）、运行效率（时间/周转/间隔/速度）、乘客出行（单班/车公里/分担率/换乘）。已删除CORE/aux数组式容器，经营三项相邻，利润前仅一条淡分隔。|三真实缓存及多人单公司范围，13项逐个与A快照显示值对应。保持原metrics/导出/snapshot合同。|
|层级与图标|各业务组只有一层白色卡面和一个共享Fluent图标：BUS/MARKET/HISTORY/PEOPLE，16px。首页复用统计标题的40px淡蓝底、22px HOME。业务组内边距统一12，组间12，字段之间4；标签12次色，网络数字28半粗，收入/利润24半粗，辅助20常规，单位12次色。|数值和单位组成紧凑整体，真实字形测距4–5px；没有用stretch把单位推到卡边。实际字体检查内容宽高及容器边界通过，不以审美镜像像素测试作为验收。|
|Hero|删除重复的“城市/模拟日期与时间/存档”字段标题；保留大城市、完整日期星期、时刻、人口与人单位、次级真实存档名。城市继续来自A可靠原始.save头：Eixeia/Ljubljana/Szczecin。|三份真实保存头只读，来源save-header:m_originalMapName；日期/时刻/人口真实字体完整测量。存档身份允许中间省略并保留完整tooltip。|
|四极值|按本实施聊天最新直接用户要求，四框拆成独立白色卡面；最大客流/最多班次使用DATA_COMPANY_COLORS蓝色细条，最小客流/最少班次使用同色板紫色细条。父已撤回与此冲突的共享字段面板要求。色条只区分极值角色。四个真实身份及类型、全部16值和单位均保留；对应极值20半粗，其余13常规，数字列右对齐。|三份真实缓存以及多人单公司测量全16数值/字段/单位；没有把同线路获得两极值去重。原LineSummary.key、鼠标/Enter/Space跳转及tooltip保持。四列间距12；普通只读模块不挂强hover浮起，真实线路卡保留hover/focus反馈。|
|三态图及颜色|制式分布/线路排行/线路占比、固定返回图标、图内mode互切保留及返回清mode、双卡独立、真实key跳线与全量分母全部保持。制式颜色仍调用共享ChartPanel规则并注入统计专用DATA_CATEGORY_COLORS，未知制式继续稳定映射。|真实四范围都生成结构、完整10行排名及11项占比PNG；其余缺测/零值/微小扇区/同名key/键盘/门禁由定向组件测试覆盖。没有改共享统计页来迁就首页。|
|环心总数|真实多人1,376,429及望春1,045,770在结构与线路占比环心完整可见。占比环径176；百分比按真实文本预留宽度，其他线路真实N仍完整。更长有限总量若不能放入环心，卡内额外居中完整总数行兜底，卡片按需增高。|测试12位及27位有限总量跨结构/占比/排行/返回的完整可见字形边界，未自动缩字、改单位或只筛可见label避开隐藏。异常超长数的增高是响应式备用，不声称也满足正常数据一屏预算。|
|趋势|TodayTrendPanel直接继承ChartPanel._append_time_segments与FluentChartView微渐变，未重写绘图效果；同一公司色、线宽、坐标轴与悬浮信息。真实多人双线、单公司一线；仅line选项，没有QAreaSeries。|测试检查共享方法对象身份、实际QLineSeries数量和原缺口。真实PNG可见共享微渐变。重名公司图例取真实ID唯一短后缀，完整ID留在图例tooltip/无障碍及共享悬浮信息；真实公司ID路由未变。|
|提醒|挂载C实际LatestInfoAlertsPanel及C/A真实快照，不再用占位渲染。按传入原顺序显示实际提醒，正文/数字完整，提醒止于上半部。|本次真实源实测秋山4条、望春3条、多人19条、多人选中公司11条，摘要为4/3/5/5；数据来自本次实际模型，不冒充旧报告其他缓存/窗口的计数。C规则/读取身份/阈值/全部/详情不在B重写，C功能已由父另验。|
|异步/响应式|set_snapshot及clear/session范围清理均立即重算内容布局，已显示窗口接新数据不需resize。超长金额通过内容测量从四列变单列，恢复小值回四列。800宽两列，420宽单列，不缩字、不删指标。|新增实际字体异步长值→范围清空→小值无resize事件检查；两张真实多人响应式PNG。小窗口允许合理纵向滚动，不称一屏。|
|1440/缩放|真实组件1204×852、DPR1、横纵整页滚动均0；上部主列932，提醒260，下图288/448/448×282，完整三态。|这些是内容组件证据，不是MainWindow，不是原生1440×960或Windows系统125%验收；整窗、系统缩放、真实前台全屏/tooltip仍交E。|

## 验证与已修复缺口

全部使用应用实际Microsoft YaHei UI字体、Fluent主题且禁止主题持久化，临时INI和减少动效。只执行B两测试文件，未跑全库或启动MainWindow。

新增需求先确认失败：四业务模块缺失、重名公司图例同名，单位实际文字距170px；父审查的清理后仍保留长值900px模块高度；真实百万占比环心缺数；长有限总量虽label可见但实际字形超宽；用户新要求的业务组图标及四色框角色条。均按实际失败修正。旧的4+5+4/核心先整行等布局断言已按最新语义分组替换，原数据/状态/导出门禁/真实事件测试保持。

最终命令：Python312 `-X utf8 -m pytest -p no:cacheprovider -q src/test_latest_info_page.py src/test_latest_info_charts.py --tb=short`，**103 passed in 16.60s，actualexit=0**。

真实缓存渲染器`task-B-business-real-render.py`最终退出0：三份真实缓存＋多人单公司，共四范围；每范围先show再交付实际snapshot，不用最后resize掩盖异步布局。指标/单位/全部极值/日期人口/实际提醒数值/结构与占比环心/完整图例逐个进行字形与容器边界检查。缓存CSV/manifest SHA256及.save头SHA256、size、mtime前后不变。元数据`task-B-business-real-metadata.json`记录来源、全部测量和源码哈希。

最后只读进程检查：**No Python/pythonw/parser_backend processes remain**。产品源码及测试现冻结，不stage/commit；等待父/E/Astra独立验收，不称“Astra视觉全部通过”。

## 新版真实组件截图

- `task-B-business-multi-all-structure.png`：多人、两公司、全部指标/四独立蓝紫极值卡/实际19提醒/双线/完整结构。
- `task-B-business-multi-all-ranking.png`：同真实源，两图完整十行。
- `task-B-business-multi-all-line_share.png`：同真实源，1,376,429环心完整，其他线路63条及绝对值/百分比。
- `task-B-business-autumn-all-structure.png`：真实单人Eixeia与实际4提醒。
- `task-B-business-spring-all-structure.png`：真实单人Ljubljana与实际3提醒。
- `task-B-business-multi-company-structure.png`：真实多人存档的单公司综合，35条、322辆、620,296客流及11提醒，实际一条曲线。
- 其余同名`ranking/line_share`为另三范围的全三态；`task-B-business-multi-responsive-800.png`和`...-420.png`为真实多人两列/单列响应式。

已逐张看四范围structure、多人ranking/line_share及两张窄窗PNG。容量fixture旧`task-B-revision-*.png`为历史证据，不再作为新版视觉结论。

## 最终源码SHA256

- frontend/latest_info_page.py：7A744950B475ACDC9135AE158D3F329FEAFF7E7DEBE4425262A49AB3FFBE1599
- frontend/latest_info_charts.py：6638F7EF5CC49EC389E95B45BCDA1D95B3931FC550CA6CE37FB0157B29C9CF82
- src/test_latest_info_page.py：A2E0CBC1F0AAD0BBC427B88B3581738879910FEF41F0E3BA6A487B1AF39E85BD
- src/test_latest_info_charts.py：49F7DB6A923A24D12098E51D10FBFCBB865E797B9FF7260C6AF674295764208D

公开capture_chart_state/restore_chart_state、set_snapshot、set_session、scope与set_workbook_availability保持第二轮合同。截图来源和这些哈希由元数据对应；父可在此基础上移交E整窗和Astra复审。
