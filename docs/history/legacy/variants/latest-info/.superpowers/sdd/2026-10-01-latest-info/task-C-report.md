# 包 C 报告 — 2026-10-01

> 当前状态（2026-10-02）：第二轮 C 定向 offscreen 回归 **50 passed、3 条依赖弃用警告、exit 0**。三份真实缓存挂载均为 260×494，整体滚动量 0。全部测试进程退出，C 槽已释放给父，由父交 D。第一版 103 passed 和本轮先前静态阶段为历史记录；最新证据与限制见文末“第二轮 C 串行 Qt 验证完成”。最终整窗/上区新重排与独立 Astra 视觉验收仍归父/E。

第一版状态：纯模型与 GUI 的限定回归为 103 passed，exit 0。该轮 GUI 检查使用严格 offscreen 与临时 INI，测试子进程正常退出。以下第一版记录不代表第二轮修订已通过，也不代表应用外壳集成或原生验收。

## 修改范围

- src/latest_info_alerts.py：纯模型默认日窗口与 shared dashboard 入口。
- frontend/latest_info_alerts.py：Fluent 提醒面板、全量列表、详情、阈值与开关。
- src/test_latest_info_alerts.py：23 项纯模型、12 项 GUI（包含 3 份真实缓存挂载检查）。
- 本报告。

原 statistics_page.py、stats_integration.py、stats_alerts.py 与主目录源未修改；未 stage/commit，未派任务，未向其他聊天发消息。

## 模型接口与规则复用

`default_alert_filters(simulation_time, company_ids: tuple[str, ...]) -> FilterState` 将模拟时钟归到今日 00:00；当前窗口为昨日 00:00 至今日 00:00，对比窗口为前日 00:00 至昨日 00:00，半开区间，粒度 hour。使用现有 parse_time，不读取现实时间。稳定公司 ID 筛选，与显示名无关。

全部公司时 D 传入所有稳定公司 ID；空 tuple 沿用 shared dashboard 的“无公司选择”语义，城市观测仍查询，不能把空 tuple 暗中解释为全部公司。docstring 与测试均明确这一点。

`build_latest_alerts(store, filters, thresholds=(5,20,100), cancelled=None) -> DashboardResult` 直接调用原 dashboard_model.build_dashboard，因此 statistics_model.alerts_for_result、DashboardResult 结果/分解/基期、dedup 与 QueryCancelled 均复用。没有添加任何提醒规则或门槛。

沿用 confirmed、完整且非缺测、等长对比、现金流转正/转负、规模缩减、百分点变化、相对变化、客流绝对量门槛；换乘系数保留原排除规则，能源价格等未确认指标不生成。无比较窗口、缺小时、零分母或无真实历史返回空 alerts；城市三方式合成不制造第二份同源提醒。

## GUI 与 D 接线

明确导入：`from frontend.latest_info_alerts import LatestInfoAlertsPanel`。模型仍 top-level `from latest_info_alerts import ...`（src 路径优先）。两个同名模块必须区分命名空间。

已实现冻结接口：LatestInfoAlertsPanel(settings=None, parent=None)、set_snapshot(snapshot, session_key, companies)、clear_session()、mark_read(alert)、mark_all_read()；thresholds / alerts_enabled 属性；thresholds_changed(object) / enabled_changed(bool) 信号。另外提供 set_thresholds(tuple) 与 set_alerts_enabled(bool)，供对话框、开关与行为检查复用。

UI 使用 QFluentWidgets CardWidget / PushButton / PrimaryPushButton / SwitchButton / DoubleSpinBox，共享 tokens、font / FullLabel、card elevation、surface reveal。摘要至多 5 条，显示真实指标、公司/分组及两期值，完整身份/值保留 tooltip 与 accessibleName；未读数计算全量 alerts。所有提醒都保留在“全部”可滚动对话框；每条详情与单项已读、全部已读可达。

详情提供指标、显示名、稳定公司 ID、分组、两期完整 Decimal 原值与单位、精确两期模拟窗口（半开）、原 reason。没有严重性、墙上时钟时间、运营评价或虚构线路警报。重名公司显示稳定 ID。列表已读操作即时刷新列表与摘要/未读计数。

无快照/不能完整比较显示“当前窗口无可比数据”；有完整可比指标但没有达标提醒显示“当前窗口无达标提醒”；开关关闭显示“提醒已关闭”。_comparable 仅用于空态描述，不参与警报判定。

原设置键与默认值：

- statistics/percentage_points：5
- statistics/relative_percent：20
- statistics/passenger_absolute：100
- stats_alerts/read_ids：直接调用只读共享 stats_alerts._alert_id，不拷贝算法、不重置已有 ID。

新增首页专用开关键：latest_info/alerts_enabled，默认 true，已验证重启持久化。关闭只改变展示/主动查询，保留传入 alerts 和 read 身份；D 监听 enabled_changed 后停止/恢复主动查询，监听 thresholds_changed 后重算同一日比较。阈值使用原三个键，实际对话框取消不写入、不 emit，应用写入并 emit。

set_snapshot / clear_session 会拒绝并关闭面板打开的旧列表/详情/阈值对话框，立即清旧行；mark_read 拒绝不在当前真实 alerts 中的对象。旧 read IDs 从设置恢复并在写入时合并，避免重置历史已读状态。

异步边界仍由 D 负责：set_snapshot 没有 request token，无法辨认已清空后送入的过期 worker 结果。D 在送入面板前必须核验 session/scope/generation，复用既有取消机制；不能用 company 显示名判断会话身份。

## 实际 B+A+C 真实缓存挂载容量

所有三份输入只读 load_session 缓存，未解析存档、未改缓存。A build_latest_info 生成真实快照，B LatestInfoPage 挂载真实 C panel；提醒根据缓存模拟时钟独立比较上一完整日与前日，全部公司用实际稳定 ID。缓存没有实际 save_path，不借 tag 假造存档文件名。

| 缓存 | 真实提醒 | 摘要项 | 全量未读 | panel | B board | 整体纵向滚动 |
|---|---:|---:|---:|---|---|---:|
| 秋山市n6 (2)_运行时 | 4 | 4 | 4 | 260×788 | 1200×852 | 0 |
| 望春市_test_运行时 | 9 | 5 | 9 | 260×788 | 1200×852 | 0 |
| quicksave.76561198362520556-76561198845688243_运行时 | 19 | 5 | 19 | 260×788 | 1200×852 | 0 |

输入目录分别为 D:/test/CIM2_SaveStats/jobs/56dd6b5276cd4c5ba083815f8a30b515、D:/test/CIM2_SaveStats/exports（后两份）。挂载检查逐一断言真实 count、260px 宽、scroll maximum=0、5 条上限、所有摘要行/按钮位于 panel 内、文本字高足够，并打开真实全部对话框验证保留 4/9/19 个详情入口。对话框滚动只发生在其内部，不撑长整个 page。

此为实际 offscreen 组件几何证据，不是 native 1440×960 / 125% DPI / 实际整窗验收，也没有称它是原生截图。

## RED→GREEN 与实际命令

解释器：C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe，pytest 9.1.1；普通 sandbox 直接 exe 启动拒绝访问，授权 require_escalated 后正常。没有安装依赖；py launcher 注册问题不作为产品失败。

纯模型初始：

`...python.exe -X utf8 -m pytest --noconftest src/test_latest_info_alerts.py -k 'not gui' -q`

新入口未建时 `22 failed, 5 deselected in 0.52s`，exit 1，全部 ModuleNotFoundError。模型实现后同命令 `22 passed, 5 deselected in 0.09s`，exit 0。补充空公司边界后相关纯模型回归 `86 passed, 7 skipped in 7.57s`，exit 0（此为放行前历史证据，GUI 当时被显式 hold）。

历史纯回归曾有 `1 failed, 85 passed, 7 skipped`，唯一失败 test_all_company_ids_are_separate_even_with_duplicate_display_names：测试错误要求 shared HistoryStore 未约定的集合遍历顺序。只将测试比较按稳定 ID 排序，不改产品或 shared rules；复验通过。

父正式放行后移除了所有 GUI release skipif/opt-in 门槛，默认全套运行 GUI；纯模型仍可用 -k 'not gui' 避免 QApplication。实际 GUI 执行序列：

1. 入口未建：`23 deselected, 7 errors in 0.54s`，exit 1，明确记录为模块缺失，不当作行为 RED。
2. 建最小可实例化 CardWidget 后，执行下面命令：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:CIM2_REDUCED_MOTION='1'
& 'C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe' -X utf8 -B -m pytest --noconftest -p no:cacheprovider src/test_latest_info_alerts.py -k gui -q --tb=short
```

实际 `7 failed, 23 deselected in 1.10s`，exit 1；所有失败为缺 set_snapshot / thresholds_changed 等实际行为。完成最小 GUI 后同命令 `7 passed, 23 deselected in 1.06s`，exit 0。

3. 增加阈值真实模态取消/应用、开关重启/损坏 read 设置、三真实缓存挂载检查后，GUI 子集 `12 passed, 23 deselected in 10.22s`，exit 0。新增 5 项边界/真实容量检查首次即通过，没有宣称它们经历新修复 RED。

最终限定回归命令：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:CIM2_REDUCED_MOTION='1'
& 'C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe' -X utf8 -B -m pytest --noconftest -p no:cacheprovider src/test_latest_info_alerts.py src/test_stats_alerts.py src/test_statistics_model.py src/test_dashboard_model.py src/test_history_contract.py src/test_stats_identity.py src/test_stats_view_model.py -q --tb=short
```

实际完整输出：

```text
........................................................................ [ 69%]
...............................                                          [100%]
103 passed in 19.27s
```

实际 exit 0；无失败、无 skip。包含 C 23 pure + 12 GUI、原 AlertsPanel 的 5 read-state/清空/损坏设置等回归、相关原纯模型 63 项。Qt fixture 保持 session 级 QApplication 强引用供原提醒回归复用，且仅在 GUI 用例请求时创建；全部 QSettings 使用 tmp_path 临时 INI。创建 QApplication 前设置 QT_QPA_PLATFORM=offscreen 并 assert platformName，共享 initialize_theme 使用不保存真实配置的主题机制。

普通受限进程 git diff --check 返回 exit 0；git status 仅列出本包三个新源码为未暂存文件，没有改共享原文件。

## 限制与槽释放

没有创建 MainWindow、操作 native HWND、全局鼠标/键盘/焦点/QCursor/QtTest.mouseMove/系统 DPI；没有读取真实用户 QSettings；没有运行全库 pytest、parser 或真实桌面验收。测试使用临时设置和独立 offscreen 子进程，所有已启动命令均已收到 exit 0/1，不存在仍运行的测试 session。最终103项子进程正常 exit 0后 C 槽已释放。

D 接线/原统计页提醒入口与开关/阈值移除、异步token、安全保存身份、导出及真实外壳宽度验收仍归 D；原生1440×960/125%缩放、焦点与全库检查由父/E排期。作者完成本包自审，E的独立GUI审查尚未运行；此前E已独立审查C纯模型无发现，不以作者测试替代该GUI审查。

## 第二轮视觉修订（源码实现阶段历史，曾等待 Qt 排期）

已完整读取 Astra 独立审查及 LATEST-INFO-REVISION-2026-10-01.md，并通过 view_image 亲看 current-multi-1440x960.png。确认原提醒从顶部延伸到底部、每行两个常驻按钮与开关/阈值表单造成视觉噪声。本轮仅修改 frontend/latest_info_alerts.py、src/test_latest_info_alerts.py 的 GUI 用例及本报告；没有修改 page/charts/controller/模型/规则、主工程或缓存。

摘要改为 80px 可操作行，最多 5 条，面板 maximumHeight=494。标题、真实全量未读与“全部”在卡头；上下文为“公司及全市 · 前一完整日”，完整模拟窗口保留 tooltip 和详情。每行中性蓝点表示未读、灰点表示已读，仅反映 read state，不表示严重等级；指标 14px，主体/分组 12px 次级色，前后值 12px 并使用千分位，完整原值仍在详情。标题/对象身份使用完整 tooltip/accessibility，数值使用真实 QLabel，不用 elide 隐藏数字。行点击、Enter/Space 打开详情，默认摘要没有重复“详情/标为已读”按钮。

按照父允许的最小改动，不新增排序算法：严格保留每次 DashboardResult.alerts 的传入顺序，最多取前 5 条，未宣称“最重要”。新增用例反转传入顺序，要求行与前五个 Alert 对应，防止视图擅自重排。既有 shared 模型顺序未改写，跨进程公司集合遍历顺序仍属于该模型原行为。

“更多”使用明确的 Fluent DropDownPushButton / RoundMenu，含可勾选“开启提醒”、“提醒阈值”、“全部标为已读”。管理动作退出摘要常驻区，详情/全部列表继续保留单条已读及全部已读。会话变化或关闭会关闭旧菜单与旧对话框，read ID 与对话框原值/精确模拟窗口/原 reason 沿用第一版。

### API 与功能保留矩阵

| 能力 | 第二轮入口/兼容性 | 验证状态 |
|---|---|---|
| frozen constructor/set_snapshot/clear_session/mark_read/mark_all_read | 签名保持；D 不需改这些调用 | 静态检查，运行待测 |
| thresholds / alerts_enabled 属性与两个 changed 信号 | 保持；便利 set_thresholds/set_alerts_enabled 也保持 | 既有用例保留，待运行 |
| 最多5条真实摘要，全量未读 | 80px行，260×494上半部容量；全部按钮 tooltip 写全量数 | GUI容量用例更新，待运行 |
| 原顺序与真实对象 | 严格按传入 alerts 前5条，不评估重要性 | 新反序输入用例待运行 |
| 详情与键盘 | 点击行、Enter/Space；详情原字段与单项已读不变 | 新真实局部事件用例待运行 |
| 全部列表/单项和全部已读 | 全部入口在标题；列表仍可滚动且保留全量行 | 既有模态用例保留，待运行 |
| 开关 | 更多的 checkable Action；关闭展示准确空态 | signal/persistence用例保留；新菜单动作待运行 |
| 阈值与取消/应用 | 更多的提醒阈值 Action；原三个 statistics/* 键 | 原模态测试改为真实 Action.trigger，待运行 |
| 全部已读 | 更多入口，全部列表也保留 | 新菜单动作与原列表用例待运行 |
| read IDs 与 session guard | stats_alerts._alert_id 与原 stats_alerts/read_ids 不变 | 迁移/重启/换会话用例保留，待运行 |
|  unknown/关闭/无可比/无达标空态 | 原准确空态保持；不补假提醒 | 既有用例保留，待运行 |
| 数据窗口、阈值、dedup | src/latest_info_alerts.py 与 shared rules 未改 | 本轮未改纯模型测试 |

内部控制件 threshold_button、enable_switch、read_all_button 已被菜单 Action 替代，不属于冻结公开 API。对应测试使用 threshold_action、enable_action、read_all_action；D 的 controller 静态检索没有依赖这些旧内部控件。GUI 仍需显式 frontend.latest_info_alerts 命名空间导入。

### 静态检查与当前限制

执行已有 Python312 的纯 ast.parse，仅读取上述两个源文件，不 import 产品模块、不 import PySide、不构造 QApplication。实际输出：AST OK frontend/latest_info_alerts.py；AST OK src/test_latest_info_alerts.py；GUI functions 12（含三案例真实缓存参数化，实际 GUI case 14）；exit 0。

本轮测试文件共预计37个case：原23 pure未改、GUI14（原12 case更新，加两项摘要视觉/真实局部事件与菜单保留检查）。没有运行测试，没有宣称 RED/GREEN或新容量通过；父本轮明确允许源码实现+静态而暂禁Qt，遵从此排期而不把上一轮绿色结果套到新源码。

git diff --check 子进程 exit 0，但这两个源文件仍为 untracked，Git diff不会验证它们；全树另有父/其他包文件的CRLF提示。本包额外逐行尾空白及AST检查针对实际两个文件，见最终静态输出；不以git diff结果代替新文件验证。

待父在B明确退出后安排C串行offscreen：运行完整 src/test_latest_info_alerts.py 与原 test_stats_alerts.py 定向回归；核对3真实缓存4/9/19条、5条摘要、260×494、文字/数值不裁切，更新B+A+C真实挂载几何；实际点击/Enter、更多开关/阈值/全部已读、modal详情与全列表、session清空/read ID均重验。原生整窗/缩放、截图与最终独立Astra审查归父/E。

本轮未启动任何Qt/原生进程，也未占用C测试槽；没有stage/commit、主树写入、另派代理、跨聊天消息。B当前独占Qt，C保持等待。

## 第二轮 C 串行 Qt 验证完成 — 2026-10-02

父正式移交 C 槽，B 已退出并冻结源码；仅运行 C 新提醒文件与原提醒回归，没有全库、MainWindow、解析或原生程序。QApplication 在 offscreen 环境下创建且断言平台，设置均为 tmp_path 临时 INI，鼠标和键盘只通过局部 QCoreApplication.sendEvent 投递，没有 global cursor、前台输入或 OS DPI 操作。

首次执行第二轮已有用例及原提醒回归：42 passed in 10.88s，实际 exit 0。其后三份缓存的数值行增加真实字体宽度检查；细化 Enter/键盘Enter/Space 三种详情入口、详情/全部/阈值三种旧会话对话框拒绝、新会话不写入旧read ID、取消旧阈值不应用、真实更多菜单展开。

一轮扩展测试出现 1 failed、47 passed、exit 1，仅 test_more_menu_opens_locally_and_exposes_checked_state_gui：使用了 QPushButton.click()，它仅 emit clicked，不触发 Fluent DropDownPushButton 的 mouseReleaseEvent；只读检查已安装依赖源码确认菜单从 mouseReleaseEvent 打开。测试改为真实局部鼠标释放事件后，定向 1 passed、42 deselected、1 dependency warning、exit 0；此为测试事件修正，没有声称产品修复。

随后检查键盘更多入口，实际发现产品控件可用性缺口：原 Fluent DropDownPushButton 的 Enter/Space 不打开更多菜单。新增两项真实局部按键用例，RED 为 2 failed、43 deselected in 1.12s，exit 1；两者实际 observed=[False]，而期望菜单可见。只在 frontend/latest_info_alerts.py 新增 AlertMoreButton 子类，沿用原鼠标下拉路径，并在 keyReleaseEvent 对 Return/Enter/Space 打开同一管理菜单，没有改 shared 控件。完整定向回归 GREEN 如下。

### 最终命令与输出

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:CIM2_REDUCED_MOTION='1'
& 'C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe' -X utf8 -B -m pytest --noconftest -p no:cacheprovider src/test_latest_info_alerts.py src/test_stats_alerts.py -q --tb=short -s
```

实际结果：**50 passed, 3 warnings in 10.33s，actual exit 0**；C 23 pure + 22 GUI cases + 原提醒5项回归，无失败、无skip。第一轮移交时源码测试已由父明确允许先实现后静态，未把第二轮全部用例虚称RED；本次新增更多键盘缺口明确经历了实际RED→GREEN。

三条 warning 均来自 QFluentWidgets menu.py:843，调用已弃用 QHoverEvent 构造器；分别发生于实际菜单鼠标、Return、Space 展开测试。没有过滤/隐藏这些警告，也没有修改第三方依赖；不影响当前行为通过，但需在依赖升级阶段跟踪。

### 真实缓存与面板容量结果

| 缓存 | 实际提醒 | 摘要数 | 未读全量 | 面板 | B board | 整体纵向滚动 |
|---|---:|---:|---:|---|---|---:|
| 秋山市n6 (2)_运行时 | 4 | 4 | 4 | 260×494 | 1200×852 | 0 |
| 望春市_test_运行时 | 9 | 5 | 9 | 260×494 | 1200×852 | 0 |
| quicksave.76561198362520556-76561198845688243_运行时 | 19 | 5 | 19 | 260×494 | 1200×852 | 0 |

此为实际 A 快照 + 冻结 B page + C panel 三份只读真实缓存检查，没有编造第5条秋山提醒。每条摘要80px，传入原顺序未重排；菜单动作与所有摘要行位于 panel 内。增加数值行 horizontalAdvance <= contentsRect.width，三份真实缓存全部通过，数字无 elide、未缩字号、未删数值。所有文字字高检查通过。实际全部对话框保持4/9/19条全量、未读保持真实总数。

功能矩阵本轮已执行：原read ID/原阈值键迁移与重启，开关持久化/信号，阈值真实模态取消/应用，单项详情已读、全列表全部已读，点击/Return/Enter/Space详情，更多真实鼠标与键盘展开及更多全部已读/开关动作，旧会话三类对话框拒绝并不写旧read IDs、不应用旧阈值，清空/新会话、损坏read设置、准确无可比/无达标/关闭空态。GUI frozen公开API保持，controller门禁仍不在本包改写。

本阶段只增加本包GUI用例和AlertMoreButton键盘补丁，未改B/纯模型/共享规则、缓存/save/probe、主树或Git索引。

### 退出与剩余限制

所有已启动 pytest 及检查子进程均已收到明确退出码；最终 pytest 正常 exit 0。随后只读 Get-Process 对 python/pythonw/parser_backend 的实际输出为：No Python/pythonw/parser_backend processes remain，检查进程 exit 0。**C 串行Qt槽现已释放给父，由父交D。**

没有跑全库或原生1440×960/系统125%，也未将offscreen组件几何称为原生整窗视觉验收。父通知B后续仍将重排上区，本阶段证据仅覆盖功能与当前260×494面板容量；最终整窗几何、截图和独立Astra签收仍需E/父执行。已知剩余事项为3条第三方菜单弃用警告，未发现本阶段字段容量失败。
