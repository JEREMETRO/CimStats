# 执行台账 — docs/stats-ui/REVISION.md

- 2026-09-26: native worktree工具因当前项目D:/test不是git根返回Not a git repository，使用git worktree fallback建立D:/test/CIM2_SaveStats-ui，feature/stats-ui-integration，从ff7618c起。
- 基线测试：py -3.12 -m pytest -q，73 passed (4.84s)。原目录未修改。
- 用户明确要求子会话，禁用collaboration agents，全部create_thread。项目test非git，创建local子会话后prompt指定已准备worktree绝对路径。
- P1/P2保留原计划；REVISION覆盖仅medium、文案和其他明确后续要求。共享文件冲突检查见CONTRACTS。

|需求|来源|负责人|实现位置|证据|状态|
|Qt侧栏/旧页面不退化|P1/P2|B|desktop_app/stats_style|待最终集成验收|已实现，验收中|
|四看板/自适应|P1/P2|B|statistics_page|待最终集成验收|已实现，验收中|
|默认7完整日/公司多选/全部比较模式|P1/P2|A/B|dashboard_model/statistics_page|待最终集成验收|已实现，验收中|
|系数/缺失/聚合/取消|P1/P2|A|statistics_model/dashboard_model|待最终集成验收|已实现，验收中|
|三客流四视图/公司分离|P1/P2|C/B|stats_charts/statistics_page|待最终集成验收|已实现，验收中|
|整数轴/负值/统一量程|P2|C|stats_charts|待最终集成验收|已实现，验收中|
|文案清单/无备注|P2|Root|stats_text及全UI|待最终集成验收|已实现，验收中|
|全看板提醒/已读|P1/P2|D|stats_alerts|待最终集成验收|已实现，验收中|
|PNG/XLSX同源|P1/P2|D|stats_exports|待最终集成验收|已实现，验收中|
|全部公司指标及三满意度/多指标|P1|B|statistics_page|待最终集成验收|已实现，验收中|
|服务站点分制式/运行均值|P1|A/B|statistics_page|待最终集成验收|已实现，验收中|
|城市全指标/比例不归一|P1|A/B/C|statistics_page|待最终集成验收|已实现，验收中|
|图例显隐不改总量/保存偏好|P1|B/C|stats_charts|待最终集成验收|已实现，验收中|
|去除明细入口/保存原导出|P1|B|desktop_app/statistics_page|待最终集成验收|已实现，验收中|
|数据样本/全回归|P1/P2|Root/F|tests|待最终集成验收|已实现，验收中|
|5尺寸×4DPI/边界/无碰撞|P2|Root/E|QA截图|待最终集成验收|未完成，UI返工后执行|
|候选包/真实存档/绑定SHA|P1/P2|Root|build/staging|待最终集成验收|未开始，等待审核|

## 2026-09-26 集成审核记录

- A 数据提交 b49e9f1 已审入；C 图表初版及 7dcdf40 已审入；B 外框5457a46已审入后被用户否决视觉效果，当前以QFluentWidgets重做，不能认定UI完成。
- D 提醒/导出 ac693f7 和 Fluent 接线 b94887b 已审入；页面连接等待B同轮集成。
- 用户确认个人本地 portable 使用；依赖 PySide6-Fluent-Widgets 1.11.3 已安装固定版本、许可证收集加入spec；暂不更新版本和构建。
- Root数据证据：jobs/ui-qa/real-data.json，单人/多人全历史四粒度复算预期系数。截图 first 为被否决初稿，不是验收证据。
- Root回归：src/test_other_pages.py，真实导出fixture覆盖概览筛选/排序图切换、线路搜索排序详情班次、列及字段开关、原XLSX复制、换存档清理取消。5项通过。
- Root集成全量：118 passed（D接线合入、Fluent外框尚在子分支）。QtCharts测试生命周期使用DeferredDelete刷新修复，未以隐藏生产问题方式跳过测试。
- 后续门槛：B/C Fluent视觉及交互 -> E尺寸/缩放 -> F固定提交独立审核 -> Root真实UI/数据/导出/旧页复查 -> 审核通过后1.0.0候选构建及实际EXE验证。所有未满足门槛仍未完成。

## 2026-09-27 恢复后的审核

- 使用原 B/C/E/F 任务继续，未创建重复任务；数据 A 和导出 D 的已完成提交保留。
- 集成 `c663e07`：合入 B 的偏好持久化、缺失公司行、同单位量程、完整时分和蓝白徽章；Root 修正旧页长存档名最小宽、饼图灰底及缺字切换图标。
- Root 复跑全量测试：150 passed，3 个 QFluentWidgets 弃用警告；旧页针对性 8 passed。
- 旧页实际 920/1920 渲染：内容宽等于 viewport，整页横向滚动范围 0。证据 `jobs/ui-qa/root-legacy`。线路班次表有独立纵向滚动，底部操作可达。
- 仍未通过：统计图例最小宽反馈导致窄窗横裁（C）、柱/折线周期位置偏移（C）、宽屏看板比例与下方内容留白（B/Root）。新版尺寸矩阵等待这些修复后重新采集。
- 未更新 1.0.0，未构建候选包；不得以单元测试通过替代 UI 验收。

## 收尾复核（代码 12b9f95）

- 完整逐项需求对照与证据入口见 ACCEPTANCE.md；原始计划保留不变。
- Root 亲自检查真实双公司完整看板、920 窄窗、原页面上下滚动，以及实际侧栏导航和勾选菜单。
- 已修复：clicked(bool) 误作页索引；城市方式绑定群体明细造成18项展示；长同名公司换行与短编号；空态横溢；PNG背景；分类柱图标签空间；日期轴根据绘图区宽度稀疏显示；替换数据时旧卡片/图表/提醒/原页行立即隐藏。
- 全量测试 163 passed（23秒），证据 jobs/ui-qa/final-tests.xml；三个警告来自 QFluentWidgets 的弃用构造函数。原两个页面专项10项通过。
- F 数据/身份/时序/异步审核见 jobs/review-f；E 旧20项矩阵和逐轮修复证据见独立review-e工作树。新时间标签与删除时序增量仍在最终复核，候选构建尚未开始。

## 首次候选撤回后的修复

- 首次1.0.0候选 de9b624 后端验证通过，但用户实际查看首页后指出字体、空白与旧控件问题。整体交付资格撤回，包体转存 build/rejected/v1.0.0-de9b624，正式 dist 未动。
- 应用字体锁定 Microsoft YaHei UI，排除 Microsoft YaHei、Noto Sans SC 和 SimHei。C 图表字体修复2a0b35c已合入；B继续统一正式入口与原两页面 Fluent 控件。
- Root真实布局复查新增阻塞：1200宽度同窗侧栏展开后卡片与图表间隙变为-91；线路详情9卡仅3卡可见、后6卡没有滚动到达路径；切换线路后的班次标签有延迟删除残影。已退回B，修复后须独立复验。
- tools/legacy_ui_qa.py记录实际QFontInfo、控件类、16px间距、侧栏变化、每张详情卡片完整可达性；最终证据必须重采，旧统计页20项矩阵不能代替整个应用验收。
