# CIM2 公司数据 Fluent 重构实施计划

> **For agentic workers:** 使用 superpowers:executing-plans 在分配的独立子会话中逐项执行。用户明确要求子会话，不使用子代理。用户已批准在保存计划、完成清理核验后初始化分支和工作树并开始派发；无需重复请求实施许可。

**Goal:** 将现有统计页重构成按原图及用户修订实现的Fluent公司分析界面，保留真实口径和原有统计功能。

**Architecture:** 继续使用已有统计快照和异步查询；新增纯展示/日期辅助层，拆出公司面板；改造现有ChartPanel；UI页面作为状态与交互唯一入口。各子会话按文件所有权独立提交，主会话只在合约、集成、验收节点集中检查。

**Tech Stack:** Python 3.12、PySide6、PySide6-Fluent-Widgets 1.11.3、QtCharts、pytest，依赖不主动升级。

**Spec:** [DESIGN.md](DESIGN.md)。原图嵌入 [README.md](README.md)，UI及图表会话必须实际打开三张PNG。

## Global Constraints

- 所有项目内容集中于D:/test/CIM2_SaveStats，新工作树仅位于该目录的.worktrees中；最多三个实施工作树，不再创建平级目录。
- 删除须进入Windows回收站，禁止永久删除、强制Git清理。保留主目录独有资料、现有dist/data/jobs/archive及用户探针。
- 模式只有默认模式、多公司对比、同期对比且互斥；删除公司摘要头部装饰，保留名称色标。
- 默认上一完整周，上一完整日/日历自定义；同期默认上一等长时段，可设置其他周期。
- 四默认图位、六指标切换；全中文；不增加无依据指标/运营评级，不修改原始存档或游戏程序集。
- 公司/网络/城市三个子选项卡，网络接收服务+客流；既有解析、导出字段及指标计算保持兼容。
- GPT-6 Sol high负责UI、图表和数据；GPT-6 Luna high负责独立验收；常规任务不用Astra。
- 子会话不可再次创建子会话/子代理/工作树，不相互合并分支；只提交自己的文件。不提交构建产物或截图巨量历史。

## Review Focus

1. 日期边界、周一午夜、月末和模拟时间而非电脑日期：D测试锁定。
2. 三模式互斥且选择两家公司不自动叠加比较：B页面回归锁定。
3. 比较时段不等长、空值、负值和单位/量程一致：C图表与D辅助层测试锁定。
4. 异步切换存档/公司时旧快照不回填且导出不串数据：B集成回归锁定。
5. 长名、小屏、DPI及独立绘图区域对齐：E截图验收锁定。

## 0. 初始化与子会话阶段

- [ ] 验证清理报告与归档映射、旧七路径不存在、Git worktree list仅主项目、正式EXE哈希未变。
- [ ] 完整基线测试一次；记录通过数及已知失败。与基线无关的UI工作不得通过删除或跳过测试掩盖失败。
- [ ] 建立集成分支feature/company-fluent-20260929；只提交本轮docs/ui-redesign和.worktrees忽略规则，不收录清理归档或用户探针。
- [ ] 分支feature/company-fluent-ui、feature/company-fluent-charts、feature/company-fluent-data从同一合约提交分出；工作树为.worktrees/ui、.worktrees/charts、.worktrees/data。
- [ ] B先检查原图与视觉合约并报告是否存在冲突；C可同步阅读/补测试，收到视觉合约确认后再实现绘制；D纯日期/展示层独立并行。B和C不得擅自改动已锁定接口。
- [ ] 每包提交完成后汇报提交号、修改文件、验证命令与结果、截图/文档位置、剩余风险；不声称整项目完成。

## 1. 模块接口合约（B/C/D共同遵循）

保留现有FilterState、DashboardResult、Result、Query及业务指标ID。现有ChartPanel.set_result(result, companies=None)、set_mode(mode)、set_axis_spec(spec)、clear()保持可用。

新增src/stats_view_model.py由D所有：

```python
def preset_window(simulation_time, preset: str) -> tuple[datetime, datetime]: ...
# preset='previous_full_week'|'previous_full_day'；custom由UI提供，不在此猜日期。
def resolve_comparison(start: datetime, end: datetime, preset: str,
                       custom: tuple[datetime, datetime] | None = None) -> tuple[datetime, datetime]: ...
# preset='previous'|'previous_week'|'previous_month'|'custom'；无效区间抛ValueError。
def company_result(result: Result, company_ids: tuple[str, ...], *,
                   include_comparison: bool = True) -> Result: ...
# 返回新Result/Query并筛选series/comparison，不修改输入；空tuple为无公司，不是全部。
```

dashboard_model.default_window(simulation_time)改为上一完整周，复用preset_window。B持有analysis_mode='default'|'companies'|'period'，range_preset与comparison_preset独立；只有period才为FilterState设置comparison。

新增frontend/stats_tokens.py由B所有：PAGE_BG、CARD_BG、BORDER、TEXT_PRIMARY、TEXT_SECONDARY、ACCENT、COMPANY_COLORS、GRID_COLOR，以及设计文档的间距字号值；供C导入。不把业务数据放进主题模块。B最早交付该模块与视觉合约确认提交。

ChartPanel由C增补：

```python
def set_company_palette(self, palette: dict[str, str]) -> None: ...
def set_hover_offset(self, seconds: float | None) -> None: ...
hover_offset_changed = Signal(object)  # float秒（相对当前周期起点）或None；程序联动不回发
```

set_mode额外接受'area'（折线+轻面积），保留原summary/bar/line/pie/trend-bar调用兼容。颜色映射以UI对本存档公司稳定排序分配为准，图表不要重复散列出另一套公司色。C添加可选图标/全屏头部接口时需先写入本合约并通知B，不能使B依赖未说明的私有属性。

B负责公司面板的同指标量程计算与set_axis_spec调用（从各公司当前/比较有效数值合并后nice_axis）；C负责正确应用统一量程、刻度、scale及绘图时间/hover坐标。B不改C内部绘图。

导出兼容：保留StatisticsPage.snapshot_changed、export_requested、snapshot、session_key、_names()。新增StatisticsPage.export_target() -> QWidget返回当前子选项卡完整内容容器，stats_integration调用该方法导出PNG；XLSX维持原快照字段范围，不改变业务汇总。

## 2. B：视觉负责人＋外壳和公司页面（Sol high）

**所有权：**frontend/statistics_page.py、frontend/desktop_app.py、frontend/stats_style.py、frontend/stats_text.py；新增frontend/stats_tokens.py、frontend/company_dashboard.py、frontend/stats_range_picker.py；frontend/stats_integration.py；页面/外壳/身份/集成相关测试。禁止编辑stats_charts.py和D的数据文件。

**输入：**三张原图、DESIGN.md、现有快照、D纯函数与C图表公共接口。

- [ ] 实际查看三张原图，记录观察及用户后续覆盖项到docs/ui-redesign/VISUAL-CONTRACT.md；锁定tokens，先提交此阶段并报告，让C基于同一规范继续。
- [ ] 增加模式语义、固定筛选、默认快捷日期、取消自定义不查询、图位切换同步、导出目标等行为测试；确认旧实现不能满足新增断言。
- [ ] 拆出公司面板与日期弹窗，实现三子选项卡、三分析模式、四图六指标、紧凑公司标识、导航/文件区和全套控件状态；按已定响应式规则重排。
- [ ] 使用D函数查询和筛选结果，保留token过期结果保护、提醒/阈值/导出；无数据/错误时清理旧图。
- [ ] 页面相关测试通过；用固定演示fixture生成基准模式截图，真实存档回归另行验证；不要用空白截图代替有数据状态。
- [ ] 显式提交所属文件，报告合约、完成行为和待集成项。若C/D接口尚未到达，先写针对公开合约的测试，不永久写伪数据降级路径。

## 3. C：Fluent图表（Sol high）

**所有权：**frontend/stats_charts.py及必要新增stats_chart_*.py、src/test_stats_charts.py、新增src/test_stats_chart_fluent.py、图表专项QA脚本。禁止修改页面、tokens或D模块。

- [ ] 查看全部原图，特别是图一公共图卡和图二周期线型；阅读B锁定视觉合约。其到达前可分析、写测试，不自行发明相冲突的视觉系统。
- [ ] 增加palette、area、统一axis/scale、断点、不等长比较、图例及hover offset无回环测试；保留已有完整时间轴/缺失值测试。
- [ ] 实现完整图卡标题/图例/轻网格/字体/tooltip/全屏，新增公共接口，适配同图多公司和同公司周期比较。使用原QtCharts能力，避免引入WebView/新图形库。
- [ ] 运行图表测试，生成线/柱/面积与两种对比截图；确认真实数值及单位不受视觉重构影响。
- [ ] 显式提交所有权文件并报告，不通过大面积重命名接口给页面造成额外兼容负担。

## 4. D：日期与公司展示数据辅助（Sol high）

**所有权：**src/stats_view_model.py、src/dashboard_model.py、src/test_stats_view_model.py、src/test_dashboard_model.py。原则不修改statistics_model.py；若发现原业务口径问题先报告，不夹带修复。

- [ ] 测试上一完整周示例2024-03-01→02-19/02-26；周一午夜、上一日、跨年、闰日、上月同期有效日期、自定义非法区间。
- [ ] 测试company_result不会修改输入、空选择/重名靠ID隔离、include_comparison=False清除比较、保留Bucket缺失/完整性信息和单位。
- [ ] 实现公开纯函数并将default_window切换为完整上一周；修正旧测试中滚动七天的已过时断言，不能放松其他业务断言。
- [ ] 运行所属测试及statistics_model回归；报告返回接口和边界案例；显式提交所属文件。

## 5. 集成、E验收及交付（后续阶段）

- [ ] 主会话在阶段完成时集中查看结果，按D→C/B依赖顺序合入集成分支；若B的token先提交可先合入该提交并同步C，避免双方直接合并。
- [ ] 集成后完整pytest一次，失败由所属会话针对性修复，不反复全量测试；功能稳定后启动Luna high独立验收子会话，复用空闲工作树，不另建第四个。
- [ ] E核验三模式×单/双公司、四图六指标、日期/同比、全屏/导出；验证长名、空值负值、历史不足、快捷切换、旧结果隔离。
- [ ] E核对1600×1000、1920×1200、1366×768/920×680以及125%/150%DPI；截图可见基线、hover和弹窗，记录窗口逻辑尺寸，不把设备像素数误当布局尺寸。
- [ ] 先一组完整截图集中审查一次，再按问题单修正并复验受影响部分。交付实际程序截图、行为清单和测试证据；暂不覆盖现有正式dist、不发布新版本。

主会话等待使用事件型wait_threads，每次最多60秒，不高频读取完整聊天或重复检查同一状态。子会话阶段完成/失败/需要协调时才集中处理。派发详情记录于DISPATCH.md。
