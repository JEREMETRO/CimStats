# 最新信息首页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 用户明确指定的独立子会话形式优先于技能默认子代理形式。

**Goal:** 增量重构现有首页为“最新信息”，统一另外两页的 Fluent 样式和真实数据，并集中展示既有关键提醒。

**Architecture:** 从现有会话数据和历史模型生成一个首页快照；新首页组件消费快照，提醒模块复用原规则和已读身份。共享应用外壳只做小范围接线，保持解析、线路查询和统计数据业务及已有有效导出。

**Tech Stack:** Python 3.12、PySide6、QFluentWidgets、既有 HistoryStore/Result/图表组件、openpyxl。

**Spec:** `docs/ui-redesign/LATEST-INFO-HANDOFF-2026-10-01.md`。用户当前请求优先；附件作为待确认增量功能清单。

**Execution status:** 用户已确认完整方案、自动日对日提醒（无法计算不生成）及独立可见 GPT-6.1 子会话。正在项目内 `.worktrees/latest-info` 准备隔离基线与分包；主目录共享源、索引和 Qt 仍等待释放。

## Global Constraints

- 工作项目固定 `D:/test/CIM2_SaveStats`；不创建平级项目目录，不换框架。
- 现有 11 项首页指标、四项线路极值和有效图表交互全部保留；数据采用真实存档及已核定模型。
- 公共交通分担率保持全市范围；换乘系数为所选公司总客流 / 总分区出行量，不平均系数。
- 当前模拟时间之前的有效数据才可显示；不补零、不跨缺测插值，不编造基期、运营评级或警报。
- 存档、既有 probe.dll 变更和其他任务的未提交文件不得覆盖、回滚或清理。
- 共享文件按函数/代码块交接，只有一个集成者写应用外壳及 Git 索引；禁止并行提交和全量暂存。
- 1440×960 整窗主要信息无整体纵向滚动；小窗响应式重排，不删指标、不截断 Top10/制式列表。
- 卡片/图表/字体/控件/配色/阴影/动效复用另外两页共享实现；单位和辅助字号保持 12px 主值采用 21px。
- 三个主页面保持无底部状态栏；进度/错误使用既有加载overlay和顶部文件区，不新增页脚。
- 提醒阈值、可比性、已读身份沿用原实现；无真实提醒不添加占位警报。
- Qt 与原生验收串行排队；不占用另两个会话在途测试窗口，不将模拟截图称为原生验收。
- GPT-6.1 用于所有分包，工程与独立验收使用 high；用户不需另行选择思考深度。
- 本次交付源码和真实运行证据；发布/替换正式 EXE不属于当前确认的范围。

## Review Focus

- 多公司重名：使用稳定公司 ID 筛选、提醒去重及跳转，不能只按名称关联。
- 缺测/真实零值/零分母：区分“—”和 0，缺小时断线，换乘不输出无穷大。
- 快速过滤与重新导入：旧异步快照、提醒、导出不可覆盖新存档或新范围。
- 公司范围与城市范围混用：全市分担率和公司子集换乘的标签、分子/分母及时间一致。
- 长线路名、10条排行、全部制式与125%缩放：文本完整、操作可达，视觉一致不以裁切换取容量。

## 分包与顺序

| 包 | 模型/深度 | 文件归属 | 依赖 |
|---|---|---|---|
| A 数据与快照 | GPT-6.1 / high | 新 `src/latest_info_model.py` 与纯模型测试 | 用户确认范围；共享模型只读 |
| B 首页界面 | GPT-6.1 / high | 新 `frontend/latest_info_page.py`、`latest_info_charts.py` | A接口固定后可先用明确测试fixture；Qt需排队 |
| C 真实提醒迁移 | GPT-6.1 / high | 新 `latest_info_alerts.py` 模型/界面文件及提醒测试 | 用户确认提醒窗口；原规则只读 |
| D 集成与导出 | GPT-6.1 / high | 应用外壳首页函数、统计提醒接线、新首页导出模块 | A/B/C交付；共享源释放；单一写入者 |
| E 独立验收 | GPT-6.1 / high | 测试/验收脚本和证据；产品源只读 | D集成完成、取得Qt窗口 |

最多同时推进 A/B/C 三个互不重叠的工程包；D/E顺序执行。若使用内部代理，遵守实际可用并发槽。若用户指定独立可见子会话，以对应会话工具创建并跟踪，所有说明包含绝对项目路径、任务边界、模型和验证要求。

## 任务 1：基线与接口冻结

**Files:** 交接文件、本计划，以及实施工作区的基线记录。

**Interfaces:** 输入是主项目已释放的源码状态；输出是可复读的提交、未提交差异哈希、各包文件归属和下列接口。

- [x] 用户回答三个规格问题：完整实施；自动真实日对日提醒，无法计算不生成；独立可见 GPT-6.1 子会话。
- [ ] 与已获授权的两个交接会话确认共享源/索引/Qt释放；不自动联系其提及的第三方会话。
- [ ] 读取最新 HEAD/status；采用隔离工作区时保留并记录必要未提交覆盖层，不能从旧HEAD丢弃线路新版。
- [ ] 冻结 A/B/C 的返回类型及调用接口。没有接口实现假定，不直接引用另包私有属性。

## 任务 2（A）：真实数据与首页快照

**Files:** Create `src/latest_info_model.py`; Test `src/test_latest_info_model.py`。

**Interfaces:** `build_latest_info(data: dict, company_id: str = '', mode: str = '综合', *, cancelled=None) -> LatestInfoSnapshot`。快照含元数据、以稳定指标ID索引的指标、四个极值记录、真实Top10、完整制式班次分类、当日趋势 `Result | None`、各指标范围与缺测原因。`LatestInfoSnapshot` 的字段在任务1冻结后发给 B/C/D。

- [ ] 写失败用例 `test_selected_company_and_mode_share_one_line_scope`：两个公司同名，分别筛选后核心指标、四极值、Top10、班次分类只来自相同真实集合。
- [ ] 写失败用例 `test_overall_transfer_uses_combined_counts`：两公司分子/分母100/20、10/10，总体为110/30；子集为100/20，不能得到公司系数平均3。
- [ ] 写失败用例 `test_city_share_ignores_company_and_mode_filters` 与 `test_missing_hour_and_zero_denominator_stay_missing`：全市指标不随公司变化；缺小时/零分母保持缺测，真实0保留。
- [ ] 写失败用例 `test_today_history_stops_at_simulation_clock`：不读未来小时，不以现实日期构造窗口；没有地图名称时不替换成存档文件名。
- [ ] 运行 `py -3.12 -X utf8 -m pytest -q src/test_latest_info_model.py`，确认失败原因针对实际需求。
- [ ] 最小实现 `build_latest_info`：重用现有字段/历史聚合/日期/换乘逻辑；列出旧首页同名口径差异，不擅改时间窗口。
- [ ] 运行新增纯模型测试与 `src/test_statistics_model.py`、`src/test_network_model.py`、`src/test_dashboard_model.py` 的适用纯模型检查；记录实际输出。
- [ ] 用已存在的秋山市/望春市/多人缓存只读复算；提交本包文件或交付限定补丁，提交前申请内部索引窗口，不触碰他人文件。

## 任务 3（B）：首页布局与分类图

**Files:** Create `frontend/latest_info_page.py`, `frontend/latest_info_charts.py`; Test `src/test_latest_info_page.py`。

**Interfaces:** `LatestInfoPage(settings=None, parent=None)`，公开 `set_session(data)`, `set_snapshot(snapshot)`, `clear_session()`；信号 `scope_changed(str, str)`, `open_save_requested`, `line_requested(str)`, `share_requested`, `report_requested`。提醒区域以公开容器/设置方法接入C；不得依赖应用外壳私有数据。

- [ ] 写失败用例 `test_home_keeps_all_metrics_highlights_and_chart_sections`：13指标（完整方案时）、4极值、3图卡及提醒区始终存在；无数据保留结构且显示缺测。
- [ ] 写失败用例 `test_top10_and_all_modes_are_visible`：明确fixture含10条长线路名与6制式，排行值/完整图例/总数/占比保持一致；不足10条不填充。
- [ ] 写失败用例 `test_home_scope_change_keeps_city_context_and_clears_stale_rows`：切换范围/新存档后没有旧卡片、旧图和旧提醒残留。
- [ ] 等Qt窗口释放后运行上述检查，确认真实失败；等待期只写独立模块，不启动QApplication。
- [ ] 以共享token、Fluent控件、现有elevation/motion实现布局。城市卡约28–32px名称；核心指标突出；辅助指标响应式；极值四卡统一字段。
- [ ] 今日趋势调用共享 `ChartPanel`；Top10和班次图用真实分类适配器，完整保留有效钻取与返回动作，不给分类数据伪造观测时刻。
- [ ] 首页右栏约260px；提供真实提醒3–5条容量与无提醒空态。1440×960主内容一屏，小窗顺序重排并可滚动。
- [ ] 在取得Qt窗口后定向检查和截图；独立验收由E最终确认。交付仅本包文件与报告。

## 任务 4（C）：关键提醒集中展示

**Files:** Create `src/latest_info_alerts.py`, `frontend/latest_info_alerts.py`; Test `src/test_latest_info_alerts.py`。

**Interfaces:** 模型接口 `build_latest_alerts(store, filters, thresholds=(5, 20, 100), cancelled=None) -> DashboardResult`；直接复用 `build_dashboard`，不新造警报规则。界面公开 `set_snapshot(snapshot, session_key, companies)`, `clear_session()`, `mark_read(alert)`, `mark_all_read()`；设置变化使用信号回传同一阈值配置。若选择镜像模式，由D传入统计页 `snapshot_changed`，不另查窗口。

- [ ] 写失败用例 `test_same_thresholds_and_read_identity_survive_migration`：迁移前已读提醒仍已读，不因换位置或公司显示名变化重置。
- [ ] 写失败用例 `test_uncomparable_period_and_transfer_never_create_fake_alerts`：不等长/不完整/未确认指标及换乘系数均不制造提醒。
- [ ] 写失败用例 `test_clear_or_new_session_removes_previous_alerts`：重新载入立即清旧值，过期异步结果不能回填。
- [ ] 自动模式用例 `test_home_alerts_need_no_statistics_tab_visit`；镜像模式改用 `test_home_tracks_only_current_confirmed_stats_snapshot`，两模式不得同时混合。
- [ ] 取得Qt窗口后运行涉及界面的失败测试；纯模型可在此前执行。
- [ ] 实现真实摘要、全部查看、单条/全部已读、阈值入口；展示来源公司/指标、比较窗口及原值，不给提醒随意添加“14:20”或严重性。
- [ ] 保留原阈值settings键与read ID算法；阈值改变刷新同一提醒数据。无真实提醒/无可比数据时给出对应说明。
- [ ] 通过新增检查及既有 `test_stats_alerts.py` 的相关回归后交付。统计页控件移除由D单独完成。

## 任务 5（D）：应用接线、分享与报告

**Files:** Modify `frontend/desktop_app.py` 的导航名称、首页创建/刷新/重置/resize及顶部操作接线；Modify `frontend/statistics_page.py`、`stats_integration.py` 的提醒容器/开关/阈值接线；Modify `stats_text.py` 首页label；Create `frontend/latest_info_exports.py`; Test `src/test_latest_info_integration.py`, `src/test_latest_info_exports.py`。已有受影响测试只更新变更要求相关断言。

**Interfaces:** 消费A/B/C的公开接口；`build_share_summary(snapshot) -> str`, `export_latest_info_xlsx(snapshot, alerts, path) -> None`，PNG沿用 `export_png`。若用户选择最小范围，则不新增分享/报告菜单。

- [ ] 确认共享源已释放；逐函数合并首页，不整文件替换、不移动线路查询逻辑，不覆盖城市/全屏图在途改造。
- [ ] 写失败用例 `test_navigation_renames_only_home_and_keeps_other_pages` 与 `test_reminders_have_one_home_entry`：首页“最新信息”；另两页保持现有操作；迁移后无重复提醒展示。
- [ ] 写失败用例 `test_import_cancel_failure_and_reimport_clear_home`：加载/取消/失败/再次打开正确复位；打开存档与原XLSX导出行为继续可用。
- [ ] 写失败用例 `test_share_and_report_use_current_scope_and_handle_cancel`：复制摘要取当前真实快照；取消保存无文件；换存档期间禁用旧报告；不写无效数值单元格。
- [ ] 取得Qt窗口运行失败用例，然后最小接线；旧首页回调适配新组件，不保留两套不同数据刷新链。
- [ ] 完整方案下“分享”提供复制当前摘要/导出PNG；“导出报告”提供首页指标、四极值、Top10、全部班次分类、提醒/范围的XLSX与实际界面PNG，复用现有保存对话框和错误反馈。
- [ ] 运行本包定向回归；与原两会话确认需要合并的共享测试hunk，不删失败测试换取通过。
- [ ] 单一索引窗口提交限定文件；保留其他任务的未提交变化。

## 任务 6（E）：独立数据与原生验收

**Files:** Create `docs/ui-redesign/qa_latest_info.py`, `docs/ui-redesign/LATEST-INFO-ACCEPTANCE-2026-10-01.md` 与 `latest-info-evidence/`；必要测试归属独立验收文件，产品源只读。

**Interfaces:** 真实应用的 `MainWindow` + 既有 `load_session`；测试/证据记录提交及代码哈希、缓存路径、模拟时间、frame/client尺寸、DPR与系统缩放。

- [ ] 用真实缓存 `jobs/56dd6b5276cd4c5ba083815f8a30b515` / `秋山市n6 (2)_运行时`，另用望春市和多人存档；分别说明既有缓存与重新解析来源。
- [ ] 独立复算总体/子集换乘、全市分担率、原指标、四极值、Top10、班次分类和总数；缺测与真实0分开核对。
- [ ] 原生1440×960检查无整体滚动、10条Top10（实际线路足够时）、所有制式、四亮点/全部指标/提醒容量；查看截图排除遮挡、裁切与覆盖。
- [ ] 125%实际缩放复验，补充窄窗920×680、导航展开/收起、长名称、无数据、加载和反复导入；完整记录真实显示条件，不伪装DPI。
- [ ] 验证键盘焦点、hover/tooltips、减少动画、提醒全部查看/已读/阈值、分享、导出及保存取消；检查分类钻取/返回继续可用。
- [ ] 执行 `py -3.12 -X utf8 -m pytest -q`；确认实际退出码、失败及警告，不以先前版本通过代替本版结果。
- [ ] 发现问题反馈对应包，修复后仅复测受影响路径与必要整库检查；不频繁重复无变化的全套检查。
- [ ] 最终交付修改文件、布局说明、新字段来源、真实运行截图、Top10/全制式证据、分享/报告行为及真实限制。发布正式EXE另按用户后续要求执行。
