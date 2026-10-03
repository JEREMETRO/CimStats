# 最新信息独立验收 — 2026-10-01

状态：**旧版功能与数据限定验收完成；用户已否决当前视觉效果，视觉未通过，父已暂缓主源应用。** 782项功能/几何结果不代表美观合格。既有四项P2已关闭。产品源只读，未stage/commit；Qt/native独占已结束，详见 `task-E-slot-release.json`。Astra审计及效果图由父安排。另获明确放行后，已采集[重构前主工程真实首页](astra-visual-audit-2026-10-01/before-main-multi-1440x960.png)和[原Top10状态](astra-visual-audit-2026-10-01/before-main-multi-top10-1440x960.png)，同真实多人缓存、进程DPR1、DWM可见1440×960；原主源及保护文件hash前后不变，actualexit0，窗口立即退出。

用户最新约束：**未明确要求的说明禁止添加。** E已检查首页、图表、提醒和分享/导出文案，长范围说明、排行重复注释、分享固定缺测尾注列为删减对象，见`task-E-copy-audit.md`；此只读QA不改产品。

实际结果：整套首轮 **773 passed / 1 failed / 13 deselected，exit1**；唯一失败是 E 的临时目录位于带 `.savestats-workspace` 标记的仓库内，触发正确的 workspace 分支。外部临时目录补跑该项及后续放行的8项，共 **9 passed，exit0**。最终 **782 个不同用例通过，5项受限检查未执行**，不是单次“782 passed / exit0”。原失败日志及根因证据保留，无产品改动。

真实缓存 MainWindow 背景 HWND PrintWindow 已实测：秋山市及多人 **DWM 可见整窗/PNG 1440×960**，进程 DPR=1；三缓存 **1800×1200**，进程 DPR=1.25（1440×960布局目标）。宽窗13指标、4亮点、3图、Top10十条、全部真实制式和提醒完整可见；首页纵向/横向滚动均0，指标数值无裁切。多人客户端920×680、导航收起、范围/已读/阈值/取消清理及真实全量19条/详情模态已实测。

**系统实测 DPI=192（200%），未修改系统 DPI。** 仅 QA 进程用 QT_SCALE_FACTOR=0.5 / 0.625 得到实测 DPR=1 / 1.25。125%属于进程模拟；**实际系统125%、前台鼠标键盘/hover、桌面像素、真实解析backend及打包EXE未测**。离屏局部 click/key/focus 用例不外推为前台验收。

执行工作区：`D:/test/CIM2_SaveStats/.worktrees/latest-info`。依据冻结契约、父授权及独占窗口；不发送跨聊天消息。最终证据汇总 `task-E-final-evidence.json` 核对所有当前源/受保护文件与 PNG/XLSX 字节 SHA256，actualexit0。父负责交付说明及精确主源应用，E 不改其 DELIVERY 文件；本树基线7057b9及七项peer依赖刷新不能整树覆盖主源。

## 实测范围与证据

| 项目 | 结论 | 证据 |
|---|---|---|
| A模型/历史比例 | 31指定纯项、10风险、25范围/600点；已关闭E-A-01 | E report、A-retest JSON/log |
| B最终组件 | 源逻辑修复复验及本轮整套GUI运行通过 | B-retest-source、suite日志；旧fixture图仅历史证据 |
| C提醒 | 源16项、整套GUI、真实摘要5/全量19/两期详情通过 | C-source-review、native-multi-scale1-25-detail.json |
| D最终接线/旧测试 | 14源hash、8保护方法AST、7peer依赖核对，无阻断；本轮集成通过 | D-integration-source、suite日志 |
| 全量与受限项 | 782不同用例通过，5项明确未执行 | suite-combined.json / suite-targeted-result.json |
| 真缓存原生背景窗口 | 精确1440×960及进程125%均通过；均非桌面/前台捕获 | 下方PNG及native JSON |
| 导出 | 实际产品PNG与六表XLSX、13指标/Top10/完整提醒/总班次读回通过 | 各board PNG、report XLSX；字节hash/ZIP复核 |
| 保护与收尾 | 源/CSV/manifest/原save/probe前后hash一致；worker关闭、Python/Qt退出 | native JSON、final-evidence、slot-release |

详细顺序记录及历史失败保留于 `.superpowers/sdd/2026-10-01-latest-info/task-E-report.md`。全部路径相对此工作区。

## 当前截图与导出

| 输入/范围 | native可见像素 / DPR | 主证据 |
|---|---|---|
| 秋山真实缓存、全部公司/综合 | 1440×960 / 1 | [背景整窗](latest-info-evidence/autumn-frame1440-scale1.png)、[产品PNG](latest-info-evidence/autumn-board-scale1.png)、[报告](latest-info-evidence/autumn-report-scale1.xlsx) |
| 多人真实缓存、全部公司/综合 | 1440×960 / 1 | [背景整窗](latest-info-evidence/multi-frame1440-scale1.png)、[导航收起](latest-info-evidence/multi-collapsed-scale1.png)、[报告](latest-info-evidence/multi-report-scale1.xlsx) |
| 三缓存进程125% | 1800×1200 / 1.25 | [秋山](latest-info-evidence/autumn-frame1440-scale1-25.png)、[望春](latest-info-evidence/spring-frame1440-scale1-25.png)、[多人](latest-info-evidence/multi-frame1440-scale1-25.png) |
| 多人窄窗（客户端逻辑920×680） | 924×740 / 1；1154×910 / 1.25 | [DPR1](latest-info-evidence/multi-client920x680-scale1.png)、[DPR1.25](latest-info-evidence/multi-client920x680-scale1-25.png)；重排/纵向滚动为预期 |
| 真实全量/详情模态 | 自有HWND、进程DPR1.25 | [19条全量列表](latest-info-evidence/multi-0-dialog-scale1-25-detail.png)、[原值详情](latest-info-evidence/multi-1-dialog-scale1-25-detail.png) |

主 metadata：`native-autumn-scale1.json`、`native-multi-scale1.json`、`native-all-scale1-25.json`；后续真实模态补充 `native-multi-scale1-25-detail.json`。均记录源hash、真实缓存/tag、manifest精确save_path、模拟时间、OS DPI、DPR、Qt/native frame/client/DWM可见frame、像素与导出hash。可见窗口用DWM扩展frame裁去不可见边框；GetWindowRect可大于PNG，不能混称。

首张系统200%原样记录的1866×1431最小窗不算1440×960通过，备份为`autumn-frame1440-first-system200.png`及`native-first-system200.json`。原native-scale1.json仅历史元数据；其初始同名输出已用first-system200备份保留，不能沿用原路径冒充当前证据。

## 真实缓存基线

以下均是**既有解析缓存**，本轮没有重新解析；数字已独立 CSV 复算，并与最终模型及真实首页核对。

| 缓存 | 模拟时间 | 公司 / 线路 | 车队总量 | 确认当日班次 | 实际线路制式 |
|---|---|---:|---:|---:|---|
| `jobs/56dd6b5276cd4c5ba083815f8a30b515`，秋山市n6 (2)_运行时 | 2013-05-21 23:59:13 | 1 / 75 | 482 | 4457 | 公交、无轨电车、有轨电车、水上巴士 |
| `jobs/68efa444f87541d8b15a8f26042be642`，运行时 | 2013-04-18 23:59:11 | 1 / 59 | 376 | 5936 | 公交、有轨电车 |
| `jobs/a15a66a7b97e4497a699cc0e729e2358`，多人 quicksave | 2013-04-10 23:59:22 | 2 / 73 | 605 | 6745 | 公交、有轨电车 |

绝对缓存根均为 `D:/test/CIM2_SaveStats/jobs`。多人稳定 ID：`76561198362520556`、`76561198845688243`；真实缓存没有同名公司，须另用明确标注的风险 fixture 核验同名 ID 行为。

| 当日原始历史复算 | 秋山市 | 望春市 | 多人总体 |
|---|---:|---:|---:|
| 全市公共交通分担率分子 / 分母 | 178097 / 329309 | 273631 / 649078 | 284091 / 911849 |
| 全市公共交通分担率（%） | 54.082032376886 | 42.156874828603 | 31.155487366878 |
| 换乘系数分子 / 分母 | 509691 / 178097 | 1045770 / 273631 | 1376429 / 493442 |
| 换乘系数（倍） | 2.861873024251 | 3.821825743428 | 2.789444352122 |

多人两公司子集分别为 `620296/228850 = 2.710491588377`、`756133/264592 = 2.857731904215`；总体系数不能平均这两个值。完整精度和每小时/分组覆盖见 JSON。

三缓存当日都有 24 个实际小时，23 时为当前部分观测，不能标为完整日。上一完整模拟日及前一日，上述四类审查指标均有 24 小时/实际分组覆盖；这不代替其他提醒指标的完整性检查。望春与多人缓存在审查的四类指标中各有 6 条未来观测，必须排除。

C 纯模型真实缓存对照：默认阈值秋山市4条、望春3条、多人19条提醒；全部与直接原 dashboard 相等且来源 complete+confirmed。最终真实首页、全量对话框及报告已验证多人摘要5条、全部19条、初始未读19。

未启用班次记录秋山市 1047、望春 256、多人 307；运行日未知班次均 0。manifest 的 departure_count 是全部记录数，不等于首页模拟当日班次。人口取元数据 147938 / 238144 / 292330，不能用配车对象数代替完整车队。


## 13 指标来源、单位和范围核验表

已按最终 A 实现、独立风险输入及三缓存25范围/600小时点核验。财务和运营沿原字段；历史比例从原始整数总量独立复算。

| ID | 核验来源与算式 | 单位 / 范围 |
|---|---|---|
| line-count | 所选公司 ID + 制式的真实线路数 | 条；当前线路集合 |
| fleet | 公司车辆总数；制式筛选时车队对应制式 | 辆；完整拥有车队，非运行配车对象 |
| drive-minutes | 当日确认发班数 × 单程时间_tick / 10^7 / 60 | 分钟；模拟当日 |
| turnover | 当日确认班次总量 / 所选车队总量 | 班/辆/天；零分母缺测 |
| weekly-income | 原线路收入_累计 / 102400，沿 load_session 的原周收入口径 | 货币；原周口径，不换成历史现金流 |
| weekly-expense | 原线路支出_累计 / 102400，沿原周支出口径 | 货币；原周口径 |
| profit | 上述同范围收入 − 支出 | 货币；原周口径 |
| interval | 原首页有效运行日组相邻正间隔；排除未启用/运行日未知 | 分钟；沿冻结模型定义，范围及原因由 InfoValue 明确说明 |
| speed | 有效线路核定速度均值，地图里程 / 1024000 × 2 / 单程分钟 × 60 | km/h；所选线路，保留原定义 |
| passengers-per-run | 所选线路当日总客流 / 确认当日总班次 | 人次/班；总量比，零分母缺测 |
| passengers-per-km | 总客流 / Σ(确认当日班次 × 地图公里) | 人次/车公里；总量比 |
| public-transport-share | 全市当天有效 public-transport 的 Σ值 / Σ分母 × 100 | %；不随公司或制式筛选 |
| transfer-coefficient | 所选公司当天 transport-by-type 的 Σ值 / trip-types 的 Σ值 | 倍；制式无配套分母，明确保留公司范围 |

对 InfoValue 同时检查 value、unit、scope、reason、complete，不从格式化字符串推断数值语义。None、真实 0、负现金流、零分母、非有限值需区分。


## 行为及字段核验

- 模拟时钟只用缓存/元数据，不用现实时间；存档名来自manifest明确save_path。缺失/坏时间安全未知，缺城市名按实际数据回退，缺人口None。
- 公司用稳定ID，综合/制式同步13指标、四亮点、排行与班次。全市分担率不随筛选；换乘系数按公司配对小时、原始分子/分母加总，不平均公司系数或混用全分母。
- 缺小时断线、未来观测排除、当前部分小时说明；None/0/负值/零分母/非有限值区分。排行缺测不占位，真实0可排序；不凑Top10。
- Hero全宽紧凑，4核心+9辅助，数值21px/单位12px；原生人工核对文字/图例及PNG，进程125%多人补查16个亮点数值宽度均足够。长名/来源说明明确省略并保留完整信息，未缩字体删项。
- 提醒按原小时dashboard判定/去重/取消及旧readID、阈值键；统计页不再另建提醒。真实多人全量保留19个行对象，详情保留两期原值、公司ID、窗口及原因；关闭后dialog登记清空。
- 真实公司/制式切换、旧token回填拒绝、单条/全部已读、7/30/250阈值与统计页同步、关闭/恢复、真实线路key跳转、取消/失败清理通过。加载/取消后报告禁用，打开存档保持可用；旧parser/统计关闭保护源方法保持。
- 宽窗的打开存档、分享、导出报告及原线路/公司XLSX入口；窄窗“更多”保留动作。原XLSX缺文件时禁用，当前真实缓存正是该情况；正向字节复制、保存取消、对话框返回后旧快照拒绝由整套集成用例覆盖。实际PNG含完整首页，XLSX六表及完整19提醒读回。

## 明确未执行的5项

- `src/test_line_visual_capacity.py::test_hover_elevation_keeps_whole_shell_geometry_and_opacity`：QTest.mouseMove可能移动系统光标，当前禁止。
- `src/test_other_pages.py::test_close_cancels_real_parser_thread_and_backend`：真实解析线程/backend超出仅缓存授权范围。
- `src/test_stats_charts.py::test_fluent_time_marks_skip_zero_and_missing_and_keep_original_hover_value`：QTest.mouseMove可能移动系统光标，当前禁止。
- `src/test_stats_charts.py::test_fluent_horizontal_comparison_and_pie_hover_use_visible_marks`：QTest.mouseMove可能移动系统光标，当前禁止。
- `src/test_stats_charts.py::test_line_mode_has_light_area_and_negative_hover_without_joining_missing`：QTest.mouseMove可能移动系统光标，当前禁止。

另不外推：真实前台Tab/焦点返回/hover、真实OS125%、真实解析取消或打包EXE启动。此次授权要求的背景窗口、进程模拟及仅缓存行为已完成，不因这些限制声称全面原生交互通过。

## 历史缺陷 — 均已独立复验关闭

| ID | 严重性 / 状态 | 位置 | 实际 / 预期 | 证据 |
|---|---|---|---|---|
| E-D-01 | P2 / 已定向复验关闭 | frontend/latest_info_exports.py:102 | 修复后空选择为“无公司选择（仅全市指标）”，单/多ID范围准确，首页范围保持独立 | 原失败证据保留；task-E-D-retest.json / .log / 3份XLSX |
| E-A-01 | P2 / 已定向复验关闭 | 原src/latest_info_model.py:278；修复 `_transfer_value` | 修复后原例返回4；完整类别且配对小时逐公司累计，明确有效/排除小时，不接受旧220/60 | 原failure保留；task-E-A-retest-risk.json / .log；task-E-A-retest-cache.json |
| E-B-01 | P2 / 已定向复验关闭 | 原frontend/latest_info_charts.py:225、455 | 修复后known+0+None仅2条、全缺测0条；NaN/inf排除，真实0保留，综合/制式一致 | 原failure保留；task-E-B-retest-source.json/.log，准确原方法体探针、非GUI |
| E-B-02 | P2 / 已定向复验关闭 | 原frontend/latest_info_page.py:392 | 修复后无时间准确未知；分列日期/时钟保留秒并正确组合，非法来源不抛错；与A来源一致 | 原failure保留；task-E-B-retest-source.json/.log，10组时钟/实际原方法体label文本通过 |


首次发现均有actualexit1原证据；修复后D15/A31及独立风险、B原方法体10组排行（每组两种方法）+10时间输入actualexit0，随后本轮最终整套与真实窗口复验。此前“GUI待验/Qt hold”文字属于阶段历史，详见E report，不代表当前状态。

QA基础设施历史：初始QSettings隔离准备失败在pytest前发生；首轮仓库内basetemp采样失败已定位并补跑；native初次原生200%尺寸及启动前DPI查询不满足目标，最终用已审计192并启动后重验；详情文字窗采用>10颜色且人工核对，主页面仍>100颜色。各原exit1日志保留，不列为产品缺陷、不隐藏为一次全绿。
