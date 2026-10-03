# 图表悬停修复交接（2026-10-01）

## 工作树与文件归属

- 图表隔离工作树：`D:/test/CIM2_SaveStats/.worktrees/charts`，分支 `feature/company-fluent-charts`，当前已提交基线 `de1d930`。工作树有未提交修改，**不要清理或重置**。
- 此轮只在图表工作树修改了 `frontend/fluent_chart_view.py`、`frontend/stats_charts.py`、`src/test_stats_charts.py`、`src/test_network_charts.py`。`frontend/network_charts.py` 此轮尚未修改。
- 主工作树 `D:/test/CIM2_SaveStats` 同时有其他会话未提交的 `frontend/fluent_chart_view.py`、`frontend/stats_charts.py`、`frontend/network_charts.py` 及大量页面文件变更。图表工作树与主工作树互不自动同步；接手者须先与全局 6.1 会话、城市页会话明确共享引擎的编辑窗口，再整合。**不要覆盖、重置或提交主工作树中其他人的修改。**
- 主工作树的 `frontend/fluent_chart_view.py` 另有饼图中心隐藏与线宽参数修改；`frontend/stats_charts.py` 另有卡片立体效果、动画、时间轴适配修改；`frontend/network_charts.py` 另有动画策略修改。图表工作树这四个未提交文件仅用于本轮悬停调查；整合时需逐块合并，不宜整文件复制。

## 已确认根因与本轮证据

1. 透明 QtCharts 系列仍接收 hover。`ChartPanel._series_hover` 原先对连续线段上的任意坐标使用无限制最近观测点，因而把插值位置报告成真实观测。新测试 `test_interpolated_line_position_is_not_an_observed_hover` 先失败，实际返回 2024-01-01 的值 2；小范围补丁将其限制为横纵坐标都与真实观测一致。该测试随后通过。
2. `ChartPanel.set_hover_offset` 原先对其他图表中的所有观测取无限制最近点。缺失的 2024-01-02 槽会高亮 2024-01-01。新测试 `test_missing_slot_does_not_link_to_nearest_real_bucket` 先失败；补丁改为只接受相同时间槽（误差小于 0.5 秒），随后通过。
3. `FluentChartView._draw_time_bars` 原先将真实数值 0 与缺失值一起跳过。新测试 `test_observed_zero_bar_has_visible_finite_hover_target` 先失败；补丁为真实 0 画 3 像素基线圆点和 8×8 有限命中框，随后通过。
4. 上述三项曾单独运行：先 `3 failed`，修改后 `3 passed`。**没有对最新所有未提交修改运行完整测试。**

## 当前未运行的新测试与待修问题

- 刚写入 `src/test_stats_charts.py` 的 `test_actual_line_mouse_hover_clears_on_blank_and_does_not_use_segment` 尚未运行；它要求真实鼠标在插值线段无提示，悬停观测点显示真实日期/数值，离开到空白时隐藏提示。测试目前将 `fluent_chart_view.QToolTip.hideText` 作为补丁目标，而 `fluent_chart_view.py` 尚未导入 `QToolTip`，首跑可能是测试设置错误；先修正测试设置再确认预期失败。`FluentChartView.mouseMoveEvent` 目前对空白只清除联动状态，并未主动调用 `QToolTip.hideText`。
- 刚写入 `src/test_network_charts.py` 的 `test_hidden_network_stack_segment_does_not_leave_a_blank_gap` 与 `test_zero_network_stack_value_has_real_hover_target` 尚未运行。调查已见 `_draw_network_stacks` 在计算总高度和逐段降低 bottom 时包含隐藏段，可能在可见段下方留下空隙；真实零值段也没有可用命中图形。这些是待验证假设，不能宣称已修复。
- 旧测试 `test_fluent_time_marks_skip_zero_and_missing_and_keep_original_hover_value` 仍断言只有 2 个 time-hit，与新真实零值行为冲突，需要按产品要求更新为“保留零值、跳过缺失”，并先看失败结果。
- 尚未覆盖：横向柱真实 0；饼图圆环、空心与隐藏扇区；同一横轴多个系列的正确目标；有限 near/far 阈值；命中后的 tooltip 消失；DPR、滚动、resize、全屏及卡片折叠伸缩后坐标；真实缓存数据的手动鼠标悬停取证。不能补零或改统计口径。
- 时间序列 tooltip 已使用观测 `bucket.start` 与原始 `bucket.value`；汇总柱使用真实窗口，网络端点使用 `bucket.observed`。仍需复核真实系列名、比较期与数值单位在所有图型一致。

## 交接建议

1. 保留图表工作树全部未提交修改，先确认全局会话与城市会话的共享文件归属和整合顺序。
2. 继续按失败测试 → 最小修复 → 通过测试的顺序处理新测试与其他图型。不要让透明 QtCharts 后端的 hover 重新把插值位置变成观测。
3. 完成后跑图表定向测试及整个项目测试，使用真实缓存数据在页面中手动悬停记录 tooltip，再将小范围补丁交全局会话整合验收。

## 6.1 接续结果（2026-10-01）

- charts 分支提交 `f525605`：`Fix observed chart hit geometry and tooltip lifecycle`。原工作树干净，旧会话四个未提交文件及失败测试已接续保留，没有重置。主目录 frontend 未修改。
- 本轮代码文件：`frontend/fluent_chart_view.py`、`frontend/stats_charts.py`、`frontend/network_charts.py`；测试含原交接两文件与新增 `src/test_chart_hover_geometry.py`，只读真实缓存工具为 `src/qa_chart_hover.py`。
- 修复真实点有限圆形距离/最近系列选择、真实柱矩形/堆积段、零值/隐藏段、饼图期间提示、空白/离开/数据更新后的提示关闭、同槽联动及 resize 后并排柱标记偏移。高密度同槽零值无法逐个指向时，有限基线标记列出全部实际可见零值；不补零、不造柱高度。
- 最终定向 **97 passed**；全库 **310 passed，1 条既有 qfluentwidgets 弃用警告**。12 项几何事件检查在五档 DPR 1/1.25/1.5/1.75/2 全部通过。独立只读审查提出的问题已先复现再修复，最终没有重要发现。
- 真实 quicksave 既有缓存共 51,282 行，五档 Qt offscreen 模拟各四种图形均完成实际 viewport 事件的 hit/blank 验证，保存实际图与 QTipLabel 提示图。**这些是模拟，不是实体鼠标或 Windows 系统显示矩阵验收。**
- 完整验收记录：`D:/test/CIM2_SaveStats/.worktrees/charts/docs/ui-redesign/CHART-HOVER-ACCEPTANCE-6.1.md`；证据在同工作树 `docs/ui-redesign/evidence/hover-6.1/`，包含全库原始日志、每档坐标/DPR/提示字符串与截图。
- 主目录可逐块应用的代码/测试补丁：`docs/ui-redesign/CHART-HOVER-6.1.patch`。在主目录执行 `git apply --check --whitespace=error` 已通过，尚未实际应用。补丁不包含主目录原有的 `hide_center`、`line_width`、`SurfaceMotion`、elevation 或 network 动效修改，不能整文件复制替代。
- 原生鼠标、整合后城市/公司/网络整页折叠动画命中、五档实际 Windows 显示验收仍待串行测试窗口协调。全局/UI 会话告知正轮流测试；本会话遵守未经用户授权不发跨会话消息，已请求协调消息授权。没有把截图当作鼠标命中证明，也没有登记原生通过。
