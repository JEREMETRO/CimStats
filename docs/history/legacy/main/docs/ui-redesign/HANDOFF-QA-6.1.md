# 独立 QA 交接给新的 6.1 会话

交接日期：2026-10-01（Asia/Shanghai）。本轮仅只读核对现场并写交接文档，没有启动新验收、修改产品代码、清理、回滚或提交。旧 QA 会话到此结束；新 6.1 high 会话由主会话创建。

## 2026-10-01 线路 QA 后续补充

本节由线路独立 QA 补充，以下原交接现场和统计 QA 结论保留为历史记录。当前线路最新证据是 Windows 原生后台窗口渲染，不能与旧版前台屏幕采集或 offscreen 客户区截图混用。整理本节期间未启动 Qt、未改产品源码或索引；主程序／原生窗口唯一测试槽已经释放给主控协调，收到桌面恢复消息后也不能自动启动窗口。

线路 owner 使用 `PrintWindow(PW_RENDERFULLCONTENT)` 从测试程序本身的 HWND 捕获完整原生窗口，再按 DWM 可见边框裁取；标题栏来自实际系统窗口。三个倍率均使用现有解析缓存加载事实卡，以标明“测试数据.save”的连续班次验证容量。没有改 Windows 显示设置；150%／200% 是 Qt 相对倍率，实际 Qt DPR 分别为 1.5／2.0，不能称为修改 Windows 系统缩放后的硬件实测。

| Qt 相对倍率 | 完整窗口 PNG／原生可见边框像素 | 原生客户区像素 | 140 班行高 | 200 班行高 | 实际进程退出码 | 证据目录 |
|---|---|---|---|---|---|---|
| 100% | 1440×960 | 1436×900 | 24 | 29 | 0 | `line-evidence/background-window-render-width-fixed/` |
| 150% | 2160×1440 | 2156×1380 | 25 | 30 | 0 | `line-evidence/background-window-render-1.5x-width-fixed/` |
| 200% | 2880×1920 | 2876×1860 | 26 | 30 | 0 | `line-evidence/background-window-render-2x-width-fixed/` |

每个目录包含 `measurements.json`、`test-140-1440x960.png`、`test-200-1440x960.png`、独立 Tooltip 图，以及明确命名的客户区截图。高倍率文件名中的 1440×960 是目标逻辑整窗预算，真实 PNG 尺寸以上表和 JSON 为准。线路 QA 已查看六张实际完整窗口图和三张 Tooltip 图，并核对 PNG 哈希、尺寸及四份记录源码的当前哈希；三档源码一致。跨档汇总见 `line-evidence/background-window-render-final-handoff.json`，100% 的初次独立复核另见 `line-evidence/background-window-render-width-fixed/qa-handoff.json`。

当前可确认的布局：默认九张信息卡和 17 个事实字段完整显示，140 班全部可见，星期选项与时刻表标题同行；展开时星期选项在标题下独立一行，200 班全部可见，末班为次日 00:54。三个倍率的右侧横、纵滚动范围均为 0，矩阵 `row_offset=0`；展开摘要至首班次行间距 12px。显示字段控件宽 104px、所需 101px；公司／制式／显示列控件分别宽 206／100／92px，矩形互不相交。先前制式控件使用 Ignored 策略导致重叠，现为 Preferred；旧重叠证据保留，不重写为通过。

查询表底层仍有 14 列，查询界面及显示列菜单只允许其中 13 列：`QUERY_COLUMNS = range(14) - {4}`，折算 km 已排除，地图 km 保留；展开后的“所有列”指这 13 个查询列。导出和底层字段不因这项显示要求删除。此 13 列结论来自当前源码及线路 owner 的定向回归，后台两张容量图展示的是默认五个核心列，不能把它们写成展开菜单逐项实测。

班次 Tooltip 已使用 Fluent `ToolTip`。三档独立控件渲染均可读，包含发班序号、完整时刻、车型三行，浅色不透明像素比例约 80%／85%／85%，阴影模糊半径 25。当前源码使用 `QGuiApplication.screenAt(global_position)` 选择指针所在屏幕并按可用边界放置。它由程序发送 `QHelpEvent` 触发，独立控件图没有合成到主窗口；不能宣称真实前台鼠标悬停已通过。

捕获 helper：`D:/test/CIM2_SaveStats/docs/ui-redesign/capture_line_window.py`，支持 `--scale 1`、`--scale 1.5`、`--scale 2`。仅在获得唯一窗口测试槽后使用，并先为新批次安排新目录；当前 helper 的固定输出目录会覆盖同名证据，不应为了读图再次执行。前台完整验收脚本为 `D:/test/CIM2_SaveStats/docs/ui-redesign/qa_lines.py`，已修正窗口外独立 Qt 基准倍率探测及小窗口车库换行断言，语法检查通过；这两项准备不等于最新完整批次已经运行。

当前输入桌面不可访问，三档记录 `foreground_hwnd=0`、`foreground_verified=false`、`screen_grab=false`。前台屏幕捕获、真实鼠标进入／离开、悬停与持续交互动画验收仍待环境恢复及重新分配窗口槽。旧的前台失败、被遮挡截图、异常尺寸截图原样保留；后台通过只确认本节覆盖的容量和视觉布局，不能替代前台输入、全局动效、整库测试或最终 EXE 验收。后台 helper 没有记录缓存捕获前后哈希基线，本节不据此新增“缓存未变”的验收结论。

## 工作区与提交

- 统一项目：`D:/test/CIM2_SaveStats`。所有新证据留在项目内，不新增平级目录。
- 主工作区分支：`feature/company-fluent-20260929`。
- 本次读取 HEAD：`90e922c62f2c52c45dda12987b1b10f079a6f9f4`。索引为空，工作树含大量城市、线路和全局动效在途改动；HEAD 不能代表当前全部界面实现。
- 旧 QA worktree：`D:/test/CIM2_SaveStats/.worktrees/data`，分支 `feature/company-fluent-data`，HEAD `0dae7b4`。它是此前 QA 文档开发现场，当前实现应以主工作区和各 owner 稳定交付为准，不能把旧 worktree 业务文件整体合回主项目。
- 其他现存 worktree：`.worktrees/charts`（`feature/company-fluent-charts`，`de1d930`）；`.worktrees/ui`（`feature/company-fluent-ui`，`1a546e2`）。保留现场，不归档或删除。

相关稳定提交：

| 提交 | 已交付范围 |
|---|---|
| `8f7984f` | 避免存档字节跨运行时封送，报告实际解析事件进度 |
| `36373d4` | 忽略分母为零的解析进度，避免显示 `0/0` |
| `e4331fa` | 修复性能对照 Windows 路径哈希筛选并补固定源码证据 |
| `dca9806` | 将独立性能／UI QA 报告及小型证据整合到主项目 |
| `1960178` | 所有公司模式满意度下拉替换 KPI 标题；移除独立行；公司名称行收窄 |
| `90e922c` | 独立窗口／模式矩阵报告、测量和截图 |

## 当前未提交现场与所有权

本次读取的已跟踪修改包含：`.gitignore`、`data/Assembly-CSharp.probe.dll`、`docs/CIM2_统计中心指标口径.md`；前端 `company_dashboard.py`、`desktop_app.py`、`fluent_chart_view.py`、`network_charts.py`、`network_dashboard.py`、`report_model.py`、`statistics_page.py`、`stats_alerts.py`、`stats_charts.py`、`stats_controls.py`、`stats_exports.py`、`stats_integration.py`、`stats_range_picker.py`、`stats_style.py`；src 中的 `dashboard_model.py`、`display_rules.py`、`extract_runtime_data.py`、`network_model.py` 及多份既有测试。

未跟踪实现包括城市／卡片比较、线路、全局动效：`frontend/card_comparison_label.py`、`city_dashboard.py`、`line_query_page.py`、`line_schedule_view.py`、`stats_dialogs.py`、`stats_elevation.py`、`stats_motion.py`；`src/card_comparisons.py`、`city_model.py`、`line_schedule.py`、相关测试与字段调查脚本。另有各 owner 计划、审查记录、截图及归档现场。此清单只表示交接时状态，编辑前重新读取实际 status，不据此推断文件空闲。

旧 QA 当前没有独占产品文件，也没有测试进程或索引占用。共享文件须先由新会话与 owner 确认区块，不能整体覆盖或混入他人的未提交修改。

| 会话 | 职责／协调点 |
|---|---|
| `01a0eae5-fd28-7a93-be3d-3bea2b0c0b98` | 主控，创建新 6.1 high QA 会话、统筹稳定交付 |
| `01a0f35c-52b5-79c3-83af-8867e7b492dc` | 全页面 Fluent 控件／悬停阴影／共享动效；当前 `stats_elevation.py` 等在途 |
| `01a0f090-642e-7e62-afc4-530a8b90584c` | 城市与卡片比较；共享 statistics/company/network 文件曾由其修改 |
| `01a0f32e-5ffd-7bb3-af5a-89ba7d4b4c80` | 线路页面 owner；独占 desktop_app 线路构建／刷新／选择及线路布局区块、line_query_page |
| `01a0f335-5f0d-7b62-81d9-fc1b87bab5dd` | 线路时刻表 owner |
| `01a0f33d-8729-7552-a944-b136de8bb799` | 线路独立 QA |
| `01a0f354-9400-71a3-80c1-140b51179638` | 共享代码 review |
| `01a0f045-7888-7e32-a731-0681bdd9e968` | 原 UI owner，满意度修复 `1960178` 已稳定 |
| `01a0f056-cd33-7621-b9d9-d3a33160639d` | 加载性能与进度 |
| `01a0ec22-c81f-7092-9f13-afa1cc839df8` | 本旧 QA，会在交接后停止使用 |

用户已要求测试用例广播给主控和测试会话，并将 UI 问题下派对应子会话修正。后续必要协调由新的 6.1 会话接续；不要唤醒旧 QA 执行新验收。

## 真实存档、缓存与保全

主要存档：

| 绝对路径 | 本次只读 SHA-256 |
|---|---|
| `D:/test/CIM2_SaveStats/data/望春市6.save` | `9D6F8C3CFBED87B4F592DC7DDFC53BC9336030766AE19D6B82BE8B841E4A8496` |
| `D:/test/CIM2_SaveStats/data/quicksave.76561198362520556-76561198845688243.save` | `79A6D64128493F1ECA2634DC2C9E8C463A1CF0A547A51901A9D2901674BB360C` |
| `D:/test/CIM2_SaveStats/data/Assembly-CSharp.probe.dll` | `9AB2ECA20D376E5DDCA7733E674890917B6A4F5A2A28C92D8238D7BC3E7DD70E` |

probe 长期处于已修改状态，必须保留，不恢复、覆盖或提交。data 另有 `望春市_Friday.save`、`望春市_Friday2.save`、`望春市_Saturday.save`，未在本次交接重新解析。此前性能会话找到过游戏 LocalLow 的秋山市 n6，能源口径应由城市 owner 提供当前已确认原档位置，不猜路径。

界面多数核验可复用：

- `D:/test/CIM2_SaveStats/docs/performance/evidence/actual-single-1/session.json`
- `D:/test/CIM2_SaveStats/docs/performance/evidence/actual-multi-1/session.json`

缓存对应真实存档解析结果，不等于当前源代码重新解析结果。`MainWindow.on_completed()` 后应明确 `navigate(2)` 再捕统计页，或导航到目标页面再捕图；它可能自动返回概览。Python 可用 `py -3`（此前为 3.12.10）；`python` 曾无输出退出。独立偏好、runtime/jobs/export 隔离保存；不要让测试写入正式偏好或原档。

## 已完成的独立 QA 与证据

1. 满意度统一：修复前单／双缓存、五种逻辑窗口尺寸 920×680、1440×960、1600×1000、1920×1080、2560×1440，公司默认／多公司／同期、网络总体／多公司／同期、城市、筛选展开／折叠共 130 状态。发现多公司模式 20 状态独立满意度行、30 个卡片静态标题；默认／同期正确。未检出横向滚动或图表矩形重叠，≥1440 核心公司默认／网络总体无纵向滚动。修复后以及公司名称行收窄后，各定向 20 状态问题为空；15 项标题替换、同步与偏好保存检查通过。

   报告：`D:/test/CIM2_SaveStats/docs/ui-redesign/evidence/ui-matrix-2026-09-30/README.md`。修复前 `matrix.json`；修复后 `after-fix/`；最终标题收窄后 `after-title-tightening/`。脚本：`docs/ui-redesign/qa_ui_matrix.py`。误停概览产生的 50 张首轮图片保留在 ignored `superseded-overview-captures/`，不能用于统计页验收。

2. 解析与性能：此前单／双真实加载准备完成约 13.761／15.809 秒；15 CSV、2 XLSX 内容及完整 session 与基线一致。固定代码 AB/BA/AB 各三组最终对照为单人 22.866→13.656 秒（40.277%），多人 28.645→15.893 秒（44.519%）；19 frontend／99 Python 完整源码哈希核对，仅 extractor 内存流参数变量。旧 39.8%／45.0% 是未控制源码的历史观测，不引用为最终因果结果。

   报告：`docs/ui-redesign/NETWORK-FINAL-INDEPENDENT-QA-2026-09-30.md`；固定性能证据位于 `docs/performance/evidence/fixed-source-20260930/`、`fixed-baseline-*/`、`fixed-optimized-*/`；真实加载和五缩放测量小型证据在 `docs/ui-redesign/independent-final-evidence/`。

3. 网络／城市证据：参阅 `NETWORK-ONE-SCREEN-QA.md`、`NETWORK-REFINEMENT-EVIDENCE-REVIEW.md`、`CITY-ENERGY-EVIDENCE-QA.md`。用户亲自确认没有“总覆盖率”字段，不能发明总体联合覆盖率。城市能源等后续业务改动应以 owner 当前证据为准，不能把早期未确认结论写成新实现通过。

## 验收限制与当前待处理

- 上述 130/20 状态为 Qt offscreen 逻辑窗口和缓存检查，不是原生屏幕缩放、原生最大化、Mica 动态、当前线路／城市最终版或 EXE 验收。
- 先前五组缩放模拟有 2880×1920 200%、1920×1080 100%、2560×1440 125%、3840×2160 175%、2560×1600 150%。offscreen screen geometry 不代表目标硬件；图像有舍入可能。不要放大截图冒充原生截图。
- 原生 Mica type2 曾仅由实现截图提供；未获得完整原生最大化、持续动画闪烁证据。动态效果是用户明确指出的漏项；旧静态验收不能代替悬停阴影、快速往返、切页中断、折叠反向与菜单／全屏过程验收。
- 性能三组配对仍有 OS 文件缓存未控制边界，未验证最终打包 EXE；不要重复重解析作为纯视觉检查。
- 当前 `FLUENT-MOTION-AUDIT-2026-10-01.md` 仍是实施中的审查矩阵，多行“待实测”；`LINE-ACCEPTANCE-2026-10-01.md` 明写最终整库测试／原生采集待完成。旧 QA 本次仅阅读，不认可这些在途工作已经通过。
- 全局动效 owner 正采用 `stats_elevation.attach_card_elevation()` 透明共享绘制层，避免卡片位移和 graphicsEffect 冲突。实际最终接口、性能和各页接入范围需要 owner 稳定交付后核对。
- 线路容量验收要求与来源需区分：1440×960 基准、最多 200 班 10×20，合成班次仅作容量测试；小逻辑窗口允许保留全部内容的明确滚动。路线字段、时刻表业务由线路 QA 接续核对，旧统计 QA 不能替其签字。

## 新 6.1 会话下一步

先与主控及城市／线路／动效 owner 确认最终稳定提交和编辑窗口，读取实际工作树，建立当前源码清单；不要据 90e922c 旧证据直接宣布当前页面通过。使用真实缓存开展当前版本全页可达状态核验，围绕变化区域验证悬停进入／停留／离开、快速往返、切页中断、折叠反向、菜单与全屏往返，记录连续帧、效果参数与像素变化，核对阴影裁切、opacity 共存、尺寸不动、卡片/图表不重叠及性能。按五组分辨率／缩放分别注明模拟或原生来源；仅在变化或失败需要时扩大测试。

发现问题将可复现条件和证据交主控／对应 owner，待稳定修复后定向复验。最终结果包含当前提交、未提交边界、实际覆盖与残余限制。旧会话到此停止，不再启动测试或清理现场。
