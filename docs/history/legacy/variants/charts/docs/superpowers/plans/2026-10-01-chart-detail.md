# 完整数值与详细图 Implementation Plan

> 2026-10-02 v2 已按主控视觉反馈完成代码整改和166项相关回归；旧全有/全无表格回退仅保留普通紧凑图，详细时间图由可滚动完整画布承载所有值。最新证据与剩余代表图确认/五档复验见 `docs/ui-redesign/CHART-DETAIL-V2-HANDOFF.md`。Qt已释放。以下旧任务账本保留为历史准备记录。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除三点指标入口，提供真实口径统计卡、充分展开的大图与每个数据值的可读常驻关联。

**Architecture:** 使用现有图表结果和克隆。新增chart_details模块管理只读统计/数值表/标签布局，实际标记继续由FluentChartView绘制和命中。

**Tech Stack:** Python、PySide6 QtCharts/Qt表模型、既有Fluent控件。

**Spec:** `docs/ui-redesign/CHART-DETAIL-DESIGN-6.1.md`。

**Execution:** 用户已经明确授权实施；按该授权在本会话继续，不重复请求设计批准。执行测试/采集仍受“不抢Qt”协调约束。

**Current ledger:** 数据与布局模型13项已通过（--noconftest，明确无QApplication），源码/窗口用例与真实缓存采集脚本已准备；Qt用例/五档采集/原生复验待串行窗口，因此任务与提交仍未完成。2026-10-02主控明确首页E占Qt槽，已继续完成短系列未知总量、窄表数字优先及跨期/整柱选择关联整改。详见 `docs/ui-redesign/CHART-DETAIL-STATUS-6.1.md`。

## Global Constraints

- 保留f525605；只使用现有charts工作树，不写主目录或主索引。
- 不改存档/probe/缓存；不重新解析，不改变统计口径。
- 不抽样隐藏数据值；最小11px、详细12px，完整数值区始终展开。
- 原生/其他Qt测试取得串行窗口；本地事件模拟不登记原生通过。

## Review Focus

- 比例/平均跨系列被求和：统计卡逐系列使用summarize_buckets验证。
- 真实0与None混同：完整数值区和标签覆盖测试。
- 图例隐藏改变堆积底层口径：原总/可见总独立测试。
- 密集标签抽样或叠字：全有或全量关联区、记录计数和矩形碰撞测试。
- CityChartPanel自定义全屏路径：通过父QDialog自动详细模式及继承接口验证，不改城市业务。

### Task 1: 真实统计与完整数值区

**Files:** 新建frontend/chart_details.py、src/test_chart_details.py；修改stats_charts.py/network_charts.py接入。

**Interfaces:** `summary_cards(result, companies, comparison_label='对比') -> list[dict]`；`value_rows(panel) -> list[dict]`；`ChartNumbers(panel)`支持refresh、数据行和选择真实点。

- [x] 写流量/存量/比例/平均、None/0、比较期间和隐藏堆积合计测试，运行见失败。
- [x] 实现模型与Qt表模型，接入普通/详细图，完整数据不依赖图例可见性。
- [ ] 定向验证；提交该任务自有文件。

### Task 2: 完整标签与详细图

**Files:** chart_details.py、fluent_chart_view.py、stats_charts.py、network_charts.py、src/test_chart_details.py。

**Interfaces:** `place_value_labels(requests, bounds, obstacles=()) -> list | None`；None表示全部值通过完整数值区提供，不能返回子样本。

- [ ] 写稀疏完整标签、密集无碰撞/完整行、放大复用结果/隐藏偏好/图幅扩大、轴单位/次刻度测试，见预期失败。
- [x] 接入实际点/矩形/扇区的标签请求；采用不重叠位置与引线，失败时全量数值区。
- [x] 详细模式自动识别QDialog，统计卡顶部、图幅stretch、字体/网格/饼尺寸调整。
- [ ] 验证原97项hover/图表回归，补DPR/resize联动记录。

### Task 3: 删除入口与交付

**Files:** stats_charts.py、network_charts.py、company_dashboard.py、statistics_page.py、现有受影响测试/QA与验收记录。

- [ ] 写无三点入口且保留满意度/默认图/模式/全屏的测试，先失败。
- [x] 移除按钮、菜单生成/接线/位置依赖；保留满意度/默认图与图型/全屏业务。
- [ ] 独立只读审查；最终全库与五档真实缓存模拟、串行原生验收分开记录。
- [ ] 精确提交；生成仅本轮补丁，等待主协调者整合，不回填root。
