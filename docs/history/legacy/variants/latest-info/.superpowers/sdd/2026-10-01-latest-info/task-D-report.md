# 包 D 交付报告：共享接线与限定离屏验证完成

2026-10-02 第二轮 controller 图态接线最新结果见 `task-D-revision-report.md`：24项 RED→GREEN、最终受影响72项与纯导出15项通过。本报告以下为首轮历史交付，不代表第二轮视觉验收。

## 最新交付状态（以本节为准）

父后续明确放行了组件、B 的微小可用性 API、共享限定 hunks，以及原 14 项 MainWindow 离屏测试和必要旧断言迁移。D 在 `D:/test/CIM2_SaveStats/.worktrees/latest-info` 完成这些工作。此前等待放行的叙述保留为过程记录，已被本节取代。

最终 **132 passed, 3 deselected in 75.35s**，exit 0，日志 `task-D-final-bootstrap-gui.log`；纯导出/统计模型回归 **82 passed in 11.54s**，exit 0，日志 `task-D-final-pure.log`。全部 Qt 运行在启动前明确设置并断言 `QT_QPA_PLATFORM=offscreen`，禁用插件自动加载；新主页及整窗测试使用临时 INI。D 的所有测试进程均已退出，离屏 slot 可移交 E。没有原生窗口操作、全局鼠标键盘、QCursor、QtTest.mouseMove、系统 DPI、更换 DPI、整库 pytest 或真实 ParseWorker/backend 运行；仅使用既有缓存。没有 subagent、其他聊天消息、stage、commit、主树或主索引写入。

父最终入口澄清后补充正式 `CIM2_SaveStats.py` launcher 用例，最新本包集成文件 **43 passed in 21.41s**，exit 0，日志 `task-D-final-all-integration.log`。该补充测试在 E 交接指令到达前已经启动，收到指令后确认进程退出；D 不再运行 Qt 或修改产品。132 是此前限定集合的实际结果，43 是补充正式入口后的独立整文件结果，不伪称跑过 133 项单次集合。正式入口用例保留真实 Python 脚本目录 root 语义，cwd=tmp、清除 PYTHONPATH、导入实际 launcher，再用真实 MainWindow 构造/关闭/DeferredDelete 退出。

最终限定 GUI 集合：B 页面 48、本包集成 42（原 14 个 MainWindow + 26 个独立组件 + 1 个独立导入路径回归 + 1 个异 cwd 真实整窗启动回归）、原统计导出集成 5、生命周期 10、公司布局预算 7、受影响 StatsFluent 4、受影响 StatsShell 5、旧页面回归 11。旧页面文件中的两项实际鼠标点击和一项真实 parser/backend 测试按授权排除，共 3 deselected；没有隐藏失败或删除测试。精确 Python 路径、工作区、环境及 pytest args 见 `task-D-final-gui-args.json`。

## 产品与测试交付边界

- 本包新文件：`frontend/latest_info_controller.py`、`frontend/latest_info_exports.py`、`src/test_latest_info_integration.py`（最新 43 项）、`src/test_latest_info_exports.py`（15 项）。控制器只消费 A 快照、C 既有提醒算法和 B 公共接口。
- 限定共享产品 hunks：`frontend/desktop_app.py`、`frontend/statistics_page.py`、`frontend/stats_integration.py`、`frontend/stats_text.py`。首标签改“最新信息”，移除旧首页计算/图表刷新链，首页隐藏旧 header，保留线路和统计路由。统计页移除第二套提醒列表、开关和阈值入口，筛选控件 9→7，响应式索引同步，无空洞；统计查询和阈值存储继续沿用。
- 限定旧测试迁移：`src/test_stats_integration.py`、`src/test_stats_fluent_page.py`、`src/test_stats_shell.py`、`src/test_company_layout_budget.py`、`src/test_other_pages.py`。保留稳定公司 ID、制式筛选、导航、重导入、原 XLSX 字节复制、字段/时刻表清理、窄窗可达性及动画布局检查。非运行日均无有效间隔时的新首页预期为 `—`（None），符合已冻结缺测口径，不能继续伪造 0；原未知/未启用班次行仍保留。
- 父单独交给 D 的 B 微小改动：`frontend/latest_info_page.py` 的公开 `set_workbook_availability(line_available, company_available)`、默认 False、clear/set_session 清可用性、`_set_actions` 同步按钮和窄窗 menu；`src/test_latest_info_page.py` 两项既有动作测试明确设置真实可用性前提。未改 B 布局、趋势时间、图表或排行实现，B 48 项均通过。父合并时只认这几个 D hunks，B 全文件仍归 B 交付。

受父刷新而已在工作树显示 diff 的以下 7 项是**依赖基线，不是 D 交付**：`frontend/line_query_page.py`、`frontend/line_schedule_view.py`、`frontend/stats_style.py`、`src/test_line_visual_capacity.py`、`src/test_line_schedule_view.py`、`src/test_line_query_layout.py`、`data/Assembly-CSharp.probe.dll`。逐项 SHA256 与父刷新记录一致，详情 `task-D-peer-integrity.json`。不合入 D patch；父后续 tooltip 变更仍按父最新源同步后交 E。

交接时父已再次同步 7 项，最终以 `refreshed-peer-baseline-final.json` 为准：更新 `frontend/line_query_page.py` 与 `src/test_line_query_layout.py`；stats_style 和另外 4 项不变。此刷新属于父，不是 D；132 项记录针对此前核查基线，E 负责最新依赖的独立验收。D 的限定 patch 未包含任何这些依赖路径。

## 最终行为与生命周期

单个 LatestInfoTask 捕获 data、token、稳定公司/制式范围、阈值和开关，先构建 A 首页快照，再用 **A 已解析的 simulation_time** 构造 C 上一完整模拟日/前一日窗口，独立于访问统计页。A 时钟缺失时仍发布可计算的线路/班次首页值，跳过 C 查询；元数据时钟兜底由 A 处理。提醒关闭时不主动查询，重新打开再查询。阈值继续写原 statistics 三个键，并同步到 statistics_page.set_thresholds。

scope/threshold/enable/session 变化即时清快照、提醒和动作，递增 token、取消旧 worker；回调再核对 token、当前 data/session、范围和 closing 状态。旧失败不会破坏新会话。close 先取消并等待首页 worker，保留 ParseWorker/统计页原关闭保护；未停 worker 的父对象保持存活，延迟关闭。导出/分享均消费同一个确认快照；保存对话框返回后重验 token、snapshot/alerts/data 身份及实际 save_key。原 line/company XLSX 动作仅真实 `Path.is_file()` 源文件可用；原工作簿继续按字节复制，并在对话框后重验 session/source。

首页 line_requested 使用真实 key 找当前线路并调用原查询/详情方法；本包没有改 `build_lines`、`show_line`、`refresh_lines`。分享菜单为复制当前摘要/实际页面 PNG；报告菜单为当前范围六 sheet XLSX/实际页面 PNG。离屏实际 PNG 写出并回读尺寸，当前范围 XLSX 回读数值，剪贴板摘要与选定公司一致；取消、对话框期间切存档/原对象 save_key 变化均不写旧文件。

## 本轮 RED → GREEN 的真实证据

|阶段|实际结果与日志|
|---|---|
|缺失 controller 的正常需求 RED|9 failed, 14 deselected，`task-D-component-red.log`；初次 fixture 9 errors 不作为需求 RED|
|首批组件 GREEN|9 passed, 14 deselected，`task-D-component-green.log`|
|session guard/统计页唯一提醒边界 RED|3 failed, 15 passed, 14 deselected，`task-D-component-boundary-red.log`；后续对应组件 GREEN|
|B 工作簿公开可用性 RED|5 failed, 32 deselected，`task-D-workbook-red.log`；新 API 后 4 组合与目录非文件全部通过|
|共享外壳方法 RED|3 failed, 37 deselected，`task-D-shell-method-red.log`；接线后通过|
|统计页移除第二提醒 RED|1 failed, 4 deselected，`task-D-stats-reminder-red.log`；移除创建/更新后 5 通过|
|组件全部 GREEN|26 passed, 14 deselected，`task-D-component-all-green.log`|
|放行后限定首轮回归|99 passed, 14 deselected，`task-D-limited-gui-regression.log`|
|原 14 整窗首次实际运行|14 passed, 26 deselected，`task-D-mainwindow-first.log`；未伪称其此前运行过 RED|
|旧首页断言需迁移|8 failed, 3 passed, 3 deselected，`task-D-old-home-contract.log`；迁移后 15 通过、2 个边界失败，`task-D-old-home-migrated.log`|
|导入命名冲突正常 RED|1 failed，`task-D-alert-import-red.log`；独立新进程将 frontend 放在 src 前复现同名模块误读|
|导入修复与两边界 GREEN|3 passed，`task-D-alert-import-green.log`|
|最终全部限定 GUI|131 passed, 3 deselected，`task-D-final-bounded-gui.log`，exit 0|
|父补充异 cwd 启动 RED|1 failed，`task-D-foreign-cwd-red.log`；清空 PYTHONPATH、从 tmp 导入 frontend 入口并真实构造 MainWindow，ModuleNotFoundError: frontend|
|最小 bootstrap GREEN|2 passed，`task-D-foreign-cwd-green.log`；含异 cwd 整窗构造/关闭/退出及独立模型/UI 导入|
|启动修正后最终全部限定 GUI|132 passed, 3 deselected，`task-D-final-bootstrap-gui.log`，exit 0|
|补充正式 launcher 后全部 D 集成|43 passed，`task-D-final-all-integration.log`，exit 0；当前 source 共 43 项|
|最终纯回归|82 passed，`task-D-final-pure.log`，exit 0|

单独执行旧两项时暴露实际 namespace bug：裸 `latest_info_alerts` 被 Python 路径顺序解析成 frontend 控件模块，导致构造失败及随后 teardown 错误（`task-D-old-home-two-boundaries.log`）。D 先新增独立进程正常失败测试，再最小修正为 `from src.latest_info_alerts import ...`；UI 保持 `from frontend.latest_info_alerts import LatestInfoAlertsPanel`。没有修改 C 模型/UI。其余两处只调整测试边界：金额用显式精度近似断言避免 Decimal/float 二进制表示比较；窄窗线路回归先选真实线路再检查详情滚动，保留原左栏宽度断言。

父随后指出仅 pytest 根目录启动会掩盖 namespace 的项目根依赖。核对 `CIM2_SaveStats.py`（正式源 launcher）、`CIM2_SaveStats.spec`（Analysis 入口及 pathex root/frontend/src）、`docs/桌面前端使用说明.md`（py CIM2_SaveStats.py）后，确认正式源 launcher 由 Python 脚本目录带入 root，但直接 frontend/desktop_app.py 从其他 cwd 启动没有该保障。先新增独立 subprocess 用例：cwd=tmp、删除 PYTHONPATH、只将 frontend 放入口 path，patch 临时 QSettings/禁 check_install，真实构造 MainWindow 后 close/DeferredDelete/退出。正常 RED 精确缺少 frontend 包；产品最小修复仅 desktop_app.py bootstrap 在 SRC 后加入 PROJECT 根路径，保持 SRC 在 PROJECT 之前。GREEN 和最终 132 回归验证通过；没有产品测试开关、业务变更或打包构建。包装好的 exe 本轮未运行。

## 合并候选与保护核对

`task-D-shared-candidate.patch` 仅含上述 9 个 tracked 共享源/受影响测试路径，**不含 7 项父依赖基线，也不含 B 全文件**。本包新源由父按文件审查；B 公开 API 独立按上述微小 hunks 审查。不要整棵 worktree copy 或 git add 全目录。

`task-D-final-integrity.json` 记录 15 个 D 相关文件最终 SHA256 与静态 compile 通过；`task-D-final-integrity.log` 记录 **24 个受保护方法 AST 与工作树 HEAD 完全一致**，包括原线路 build/show/refresh、cancel_parse、DashboardTask、StatisticsPage 查询/取消/过期保护/阈值、筛选 transition、resize/reflow/lifecycle guards。`git diff --check` exit 0，仅既有 LF/CRLF 提示；本树 cached diff 为空。主目录四个共享源 SHA256 前后相同，`task-D-primary-four-unchanged.json`；只读核对，未写主树。

关键新源 SHA256：controller `A27528E0C488776540E454AE79B399E45B8EE973DADC0A17AD4A9C8A2E8FD336`；exports `FBB113069285B5889BE16C620641CC2B9E827CD3B05204626D182EF63E807A15`；integration tests `9BB0EE450404D561B3AB766B3F982876FD75309F7D70981F8752D114C4532ABA`。真实缓存两份 XLSX 与 E-D-01 证据仍见下方历史记录，未重新解析。D 本包在授权范围内交付完成，父合并与 E 独立验收由父继续协调。

## 早期阶段记录（历史）

工作区：`D:/test/CIM2_SaveStats/.worktrees/latest-info`。需求依据为本目录 `task-D-brief.md`、`docs/ui-redesign/LATEST-INFO-CONTRACT.md` 和计划任务 5 / Global Constraints。当前阶段只修改本包新文件；未修改共享源、A/B/C 文件；未 stage / commit；未启动 QApplication、GUI 或原生解析；未另派代理或向其他聊天发送消息。

## 已完成文件与接口

- `frontend/latest_info_exports.py`：`build_share_summary(snapshot) -> str`、`export_latest_info_xlsx(snapshot, alerts, path) -> None`、`export_latest_info_png(target, path)`。
- `src/test_latest_info_exports.py`：初始 12 个纯导出用例；E-D-01 修复后现有 15 个，最新结果见报告末尾。
- `src/test_latest_info_integration.py`：初始 14 个 MainWindow 集成用例，后增 9 个独立组件用例，共 23 个；函数内延迟导入 Qt，仅完成 collect-only 检查，尚未执行 RED。
- 本目录 `task-D-verify-cache.py`、RED/GREEN/回归日志、真实导出日志及两份 XLSX：本包证据文件，不属于产品源修改。

分享摘要保留城市、存档、模拟时刻、人口、稳定公司 ID、制式、总范围、每项指标的独立范围与原始缺测/口径原因；列出 13 指标和 4 极值。人口/指标缺测显示 `—`；真实零值显示 0；部分观测注明。导出不重新查询或重新计算首页指标。

XLSX 六个中文 sheet：范围与说明、首页指标、线路极值、客流前十、班次分类、关键提醒。数值保持 int / float；Decimal 只在写入边界转成 Excel 数值。缺测与 NaN/Infinity 写空值，不能写 0 或 Excel 错误。保留全部班次分类、真实总数、占比；总数缺测或非正时占比为空。保存每个提醒的指标、稳定公司 ID/显示名、分组、本期/对比原值、单位、两个完整窗口以及原提醒原因。无可比数据/无达标提醒无占位提醒行；未计算与空结果有不同说明。存档/线路名以文本写入，前导 `=` 不会成为 Excel 公式。

沿用项目明确指定的 Python/openpyxl 技术栈，不新增依赖。所有导出只记录确认快照；比例使用快照分类计数/总数，未制作重新建模用的计算工作簿。没有 Excel 公式，因而无公式重算依赖。字体为 Microsoft YaHei UI，冻结表头、筛选、时间格式、占比格式及换行宽度齐全。PNG 包装仅调用现有 `stats_exports.export_png`，Qt 导入延迟到显式调用。

## RED → GREEN 与验证证据

使用现有解释器 `C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe`。沙箱内启动返回 Access denied，未执行测试，不记作 RED；后续纯测试走工具自动审批成功启动。所有纯测试带 `--noconftest`。

1. `pytest --noconftest -q src/test_latest_info_exports.py`：RED **12 failed**，失败均为断言“首页导出模块尚未实现”，不是收集错误。日志 `task-D-export-red.log`。
2. 同命令：GREEN **12 passed in 2.14s**，exit 0。日志 `task-D-export-green.log`。
3. `pytest --noconftest -q src/test_latest_info_exports.py src/test_statistics_model.py src/test_network_model.py src/test_dashboard_model.py`：**79 passed in 9.92s**，exit 0。日志 `task-D-pure-regression.log`。
4. `pytest --noconftest --collect-only -q src/test_latest_info_integration.py`：**14 tests collected**，exit 0。仅收集，未运行 GUI；不能称为 GUI RED/GREEN。
5. 独立子进程禁止导入 `PySide6`、`qfluentwidgets`、`stats_exports`，仍能生成摘要并写 XLSX，证明纯导出没有加载 Qt。

定向测试覆盖 13 项数值/范围/完整性、4 极值、Top10 完整行、6 类制式 fixture、真实 0 与缺测占比、无提醒与未计算提醒、空线路范围、非有限值、名称公式误识别。全库 pytest 包含 Qt，因明确 hold 未运行；完整 GUI 与整库验证留待放行，不以纯测试代替。

## 真实缓存导出回读

输入为只读既有缓存 `D:/test/CIM2_SaveStats/jobs/56dd6b5276cd4c5ba083815f8a30b515` / `秋山市n6 (2)_运行时`，不是本次重新解析。使用真实 `report_model.load_session`、A 的 `build_latest_info`、C 的 `default_alert_filters/build_latest_alerts`；没有 Qt 导入。摘要/导出由 D 消费实际 A dataclass。来源缓存不含完整原存档路径，本次验证补充显示文件名 `秋山市n6 (2).save` 和带缓存来源的 session key，未修改缓存文件。

生成 `task-D-real-all.xlsx` 与 `task-D-real-company.xlsx`，分别为全部公司和稳定 ID `76561198845688243` 的综合范围。此缓存为单公司，两者真实数值相同，不把这次核查称为多人筛选验证。

回读结果：模拟时刻 **2013-05-21 23:59:13**；13 指标、4 极值、75 条真实线路来源、Top10 十条；公交 3861、无轨电车 359、水上巴士 74、有轨电车 163，总班次 **4457**；**4 条真实提醒**。提醒本期为 `[2013-05-20 00:00, 2013-05-21 00:00)`，对比为 `[2013-05-19 00:00, 2013-05-20 00:00)`，与首页当天范围独立标注。逐项数值、范围、分类行及提醒数量与快照一致；无公式单元格或 Excel 错误。详情 `task-D-real-export.log`，执行 exit 0。

## 放行后的精确接线方案（尚未实施）

需要新增本包控制器 `frontend/latest_info_controller.py`，不会改 A/B/C 模块。应用外壳只连接公开接口；GUI 测试预留 `window.latest_info_page` 和 `window.latest_info_controller` 作为集成边界。

控制器约定：`LatestInfoController(page, settings, parent)` 持有 `snapshot`、`alerts_snapshot`、`alerts_panel`、单调 `token`、存活 `workers` 列表；方法 `set_session(data)`、`clear_session()`、`stop_workers()`、`copy_summary()`、`_export(kind)`；完成槽 `_receive(token, (snapshot, alerts_snapshot))`。本包可在实际 GUI RED 后调整内部实现，但不改变冻结 A/B/C 接口。

|共享文件与函数/代码块|限定修改及不变约束|
|---|---|
|`desktop_app.py` imports|导入 B 的 `LatestInfoPage` 和本包 controller；不移动线路/统计业务|
|`build_ui` 导航/首页构造|仅首个显示名改“最新信息”；保留 overview 路由及三个页面顺序；在 StatisticsPage 构造后把 C 阈值变化连接 `statistics_page.set_thresholds`，初始化值读取原 settings 键|
|`build_overview`|委派 `LatestInfoPage(self.settings)` 并 addWidget；公开 company_combo/mode_combo 保持兼容引用；controller 接入 C 的 panel 与各动作；不保留第二套旧首页数据刷新链|
|`navigate` 首页 header / `resizeEvent` 首页分支|首页隐藏 legacy_header 与 stats_header，使用 B 自有 header；线路原 header 与统计 header 的布局保持；line_footer 持续隐藏；仅删改旧首页专属 resize/reflow 访问|
|`start_parse` 首页复位片段|在启动新 parser 之前 controller.clear_session + page.clear_session；移除旧首页图表/卡片逐个归零代码；线路选中清理、表格/详情/时刻表复位保持原代码|
|`on_completed` 首页元数据/筛选初始化片段|保存 self.data 后交给 controller.set_session；页面 set_session 只读元数据，不在 UI 线程重新计算；保留线路公司/制式选择填充与 refresh_lines；原工作簿有效性决定首页原 XLSX 动作可用|
|`refresh_company` / `company_changed`|只委派 controller 发起/调度同一查询；不保留旧公式计算、旧排行与旧班次聚合实现；旧首页图表钻取回调由 B 自身管理，不触碰新版线路图|
|`_check_dashboard_ready` / `_dashboard_failed`|当前 data 身份一致时，最新信息 snapshot 及所需提醒结果也必须已就绪；首页失败经既有 overlay/文件区反馈；不错误提前关闭载入 overlay|
|`on_failed` / `cancel_parse`|失败、取消立即清 controller/page，token 失效；禁止旧结果回填。复用既有错误/取消文案和 overlay，不加页脚|
|`closeEvent`|先停止首页 debounce、打断并等待首页 worker，保留 5f19eef 的 ParseWorker/统计页关闭保护；若线程尚未停则保持父对象存活并延迟关闭|
|`statistics_page.py` 提醒控件构造/_controls/_fields、alerts_host、`_toggle_alerts`、`_settings_dialog`|移除提醒列表、开关和阈值入口的第二份可见 UI；相应响应式布局索引同步更新；保留 `thresholds`、`set_thresholds` 与原查询参数；不改统计聚合/三看板内容|
|`stats_integration.py` constructor / `_snapshot_changed`|停止在统计页创建或渲染 AlertsPanel；保留 export_requested、PNG/XLSX/城市/网络导出及原过期保护；已有受影响测试只更新提醒迁移相关断言|
|`stats_text.py` TEXT 首页 label|overview 显示名改“最新信息”；仅新增必要首页动作标签；其他 label 不改|

**异步数据与生命周期：** 一个 QThread worker 一次计算 A 快照和 C 提醒，捕获 data、公司/制式 scope、三阈值和提醒开关值。A/C 均接受 worker interruption 的取消回调。提醒窗口由模拟时钟构造上一完整日/前一日，不能依赖访问统计标签。全公司使用 data 内稳定 IDs，单公司使用 scope ID；制式不会伪装成提醒公司窗口。每次 scope/threshold/enable/session 变化立即清已确认 snapshot/alerts 并递增 token，打断旧 worker；在当前 token、当前 data 身份且未关闭时才接收结果。ready/failed/finished 均绑定所属 worker，finished 从列表移除并 deleteLater；不能让旧 failed 触发新存档错误。关提醒时不做主动提醒查询；重新打开再查询；不改变原报警判定。

**动作接线：** open_save_requested→现有 open_dialog；line_requested(key)→按真实 key 找 self.data 线路并 navigate(1)/show_line(row)，保持原 build_lines/show_line/refresh_lines 业务；原 line_export/company_export→现有 export_file 对应源工作簿。share_requested 提供复制当前摘要与导出页面 PNG；report_requested 提供当前范围 XLSX 和实际页面 PNG。导出时先捕获 snapshot、alerts_snapshot、token/session；保存对话框返回后重新核对全部身份及当前有效快照，无路径或失效立即返回；追加后缀和错误反馈复用现有机制。PNG 使用 page.export_target，不截取不可用旧首页。复制与导出仅使用同一已确认快照。

**保护既有工作：** 不改 build_lines、show_line、refresh_lines 的数据/查询逻辑；只在首页信号的适配层调用。保留主目录 e4cf2fb 筛选动画、5f19eef 生命周期、平均间隔过滤、重载选择清理和隐藏 line_footer。父最终按最新主 HEAD 合并限定 hunks，不能整文件覆盖主源。

## 当前共享源留存指纹

阶段检查 `git diff --name-only` 为空；本包三个产品/测试文件为未跟踪新文件。共享源 SHA256：

- desktop_app.py：`FD34378E0FF3B69C6566DC9A8733AE9FF5E47AA8A50EC8AAF808C5942FD8DD51`
- statistics_page.py：`EE64C18D1EB026504ED97ECB4BA7D08E8FF54325A9E356189A37DCD956157471`
- stats_integration.py：`7492038E3409AC244F79F9CF9FD015973F67C74084B306D6244E2B52C7A97039`
- stats_text.py：`F848D4D5F249C6213CA0F8CA5EF9899187AB8B0B3E778FA6546ECC8E6B16ED83`

## 尚未完成的条件

共享源/Qt 当前 hold：未实施上述接线，未运行 GUI RED、PNG 真实渲染、保存对话框/剪贴板/快速筛选/取消重导入 GUI 核查、整库 Qt 回归；A/B/C 的 GUI 交付与父明确放行后，在本会话继续执行。无需重复询问用户已确认的规格。本报告是导出准备阶段交付，不是整项集成完成声明。

## E-D-01 定向修复（本轮最新状态）

父转交 E 审查后，核对 C 模型文档与原 dashboard：`DashboardResult.filters.companies=()` 是无公司选择，仍可查询全市指标；不是首页 company_id='' 的全部公司。原 exporter 的“提醒公司”空 tuple 回退确实误写为“全部公司”。

先在 `src/test_latest_info_exports.py` 新增参数化真实工作簿回读测试 `test_alert_company_scope_preserves_empty_selection_and_stable_ids`。三个独立预期分别为：空 tuple → `无公司选择（仅全市指标）`；单 ID p2 → `同名公司 [p2]`；多 ID p2/p1 → `同名公司 [p2]、同名公司 [p1]`。还验证首页自身公司范围仍为 p2，提醒表没有补造公司提醒。

- RED：`pytest --noconftest -q src/test_latest_info_exports.py -k alert_company_scope` 实际 **1 failed, 2 passed, 12 deselected in 1.08s**，exit 1；失败精确是 `全部公司 != 无公司选择（仅全市指标）`。日志 `task-D-E-D-01-red.log`。
- 最小产品修复仅 `frontend/latest_info_exports.py` 的“提醒公司”空选择标签；真实单/多公司逐稳定 ID 展示逻辑保留。
- GREEN：`pytest --noconftest -q src/test_latest_info_exports.py` 实际 **15 passed in 2.37s**，exit 0。日志 `task-D-E-D-01-green.log`。
- 回归：`pytest --noconftest -q src/test_latest_info_exports.py src/test_statistics_model.py src/test_network_model.py src/test_dashboard_model.py` 实际 **82 passed in 8.42s**，exit 0。日志 `task-D-E-D-01-regression.log`。

修复后 SHA256：exports `FBB113069285B5889BE16C620641CC2B9E827CD3B05204626D182EF63E807A15`；exports tests `ACAB2A5B76B6EA0BA9EC79C50CB1159F3740F4CAECF4AC634B620C82D57A24C3`。未修改 E 证据/探针或 C 模型；E 独立复验尚未执行，由父协调。未 stage/commit、未启动 Qt。

## 父补充放行与静态准备边界

父已有限放行 `.worktrees/latest-info` 既定共享 hunks 与静态检查；主树、主索引、native/MainWindow 仍禁。B→C→D 的离屏窗口串行，D 必须等 C 交付和父明确放行后才运行 B+C+controller 组件 RED/GREEN，不实例化 MainWindow。当前仅准备组件用例/接线细节，未在 GUI RED 前实现未验证的共享接线。

接线必须显式使用 `from frontend.latest_info_alerts import LatestInfoAlertsPanel`；纯模型另用 `from latest_info_alerts import default_alert_filters, build_latest_alerts`，避免 src/frontend 同名模块冲突。父核对本轮 desktop_app/statistics_page/stats_integration/stats_charts 的主树与工作树哈希一致；line_query_page、line_schedule_view、stats_style 已有主树增量，最终只合入限定 hunks，不整文件 copy。

提醒控件移出统计页时同步处理 `_controls`、`_control_keys`、`_fields`、grid 索引及折叠 visibility，不能只 hide 而保留布局空洞；保留 e4cf2fb 的筛选 transition/布局预算和 5f19eef 的生命周期/reflow guards；DashboardTask 的统计查询、取消、过期保护与导出全部保留。原 14 个 MainWindow 集成用例继续留待后续窗口，不以离屏组件通过冒称整窗已验。

已在本包现有集成测试文件追加 9 个独立组件用例：实际 A 快照/C 提醒与范围、稳定公司 ID 切换前即时失效、clear/reimport 旧 token 丢弃、XLSX/PNG 保存取消、对话框期间换存档不写旧快照、分享与报告消费同一当前公司快照。组件 fixture 只实例化普通 QWidget、B LatestInfoPage 和本包 controller；不导入 desktop_app 或构造 MainWindow。父放行后可用 `pytest -q src/test_latest_info_integration.py -k component` 运行该子集；此时不带 --noconftest，以使用现有 qt_application fixture，运行环境由父限定 offscreen。

静态准备验证：`pytest --noconftest --collect-only -q src/test_latest_info_integration.py` 最新 **23 tests collected in 0.57s**，exit 0；日志 `task-D-component-collection.log`。未执行这 23 项，没有组件 RED/GREEN 声明；控制器产品源仍未实现，共享接线尚未修改。E-D-01 等待 E 独立复验，D 离屏组件等待父后续明确放行。

## D 实施放行后的公开能力请求（请父协调 B）

9 个独立组件 RED 已在明确释放的 offscreen slot 执行，正常 **9 failed, 14 deselected in 2.39s**，exit 1，均为“首页控制器尚未实现”；`task-D-component-red.log`。首次把缺失断言放 fixture 得到 setup errors，已在实现前改为测试体断言并重跑为上述正常需求失败；不把首次9 errors当正确RED。

发现 B 公共接口尚不足以落实父要求“原工作簿动作按真实输出有效性处理”：`LatestInfoPage.set_snapshot` 会统一启用所有 buttons/menu actions，而冻结接口无单独调整原工作簿可用性方法。D 不通过 B 的 actions/menu_actions 私有结构接线，也不修改 B 产品文件。

请求父协调 B 增加公开 `set_workbook_availability(line_available: bool, company_available: bool)`：记录当前会话两个源 XLSX 的真实存在状态，set_snapshot 后仅原 line/company 导出动作使用该状态；share/report 继续取快照有效性；clear_session 必须清可用性；按钮与窄窗菜单同步。默认应为 False，不因首页模型算出快照而把不存在源文件的原 XLSX动作启用。D 将在 session 建立时按 outputs 和 Path.is_file 检查并调用该能力，原 export_file 返回前仍重验 session/token/source。

此请求只扩展 B 的公开可用性能力，不改变 A/C 算法或冻结数据类型；未批准前 D 先完成其他 controller/lifecycle/导出和限定共享接线。MainWindow继续禁止；后续本轮结果追加报告。
