# 图卡与共享分段控件阶段视觉自查

2026-09-29。按 `README.md`、`DESIGN.md`、`VISUAL-CONTRACT.md`、`NETWORK-PLAN.md`、`VISUAL-ACCEPTANCE.md`、`CONTROL-SPEC.md` 复查，并实际打开公司原图 01/02/03 与本阶段运行截图。原图中的示例数值、旧日期输入和已删除的公司装饰摘要均不作为业务依据。以下截图均为 PySide6 程序实际绘制，数据明确使用 `src/qa_stats_charts.py` 的固定演示结果，不是用户存档。

## 截图与环境

- 图卡：[多公司同图](evidence/charts/01-overlay-demo.png)、[同期对比](evidence/charts/02-period-demo.png)、[面积断点](evidence/charts/03-area-demo.png)、[图形切换与指标入口](evidence/charts/04-mode-control-demo.png)、[指标菜单展开](evidence/charts/05-metric-menu-demo.png)、[全屏](evidence/charts/06-fullscreen-demo.png)、[400 像素窄卡](evidence/charts/07-narrow-demo.png)、[窄卡分段](evidence/charts/08-narrow-mode-demo.png)。
- 紧凑图卡和页面试排详见[紧凑布局验收](COMPACT-CHART-ACCEPTANCE.md)。
- 控件：[常规和紧凑分段](evidence/controls/segmented-demo.png)、[hover](evidence/controls/segmented-hover.png)、[键盘焦点](evidence/controls/segmented-focus.png)、[pressed](evidence/controls/segmented-pressed.png)。
- 截图元数据：[图卡 JSON](evidence/charts/README.json)、[控件 JSON](evidence/controls/README.json)。Qt offscreen，96 DPI；图卡基准为 1120×470，图形切换为 600×470，窄卡为 400×470，全屏实际截图 796×796。控件为 680×190。图卡代码提交 `813f033`，共享控件提交 `e6e004e`。

| 关键要素 | 原图/MD依据 | 本次结果 | 实际截图或测试证据 |
| --- | --- | --- | --- |
| 分段切换蓝底白字、常规/紧凑尺寸、图标与文字 | 原图 01/02/03；CONTROL-SPEC §3 | 通过 | `segmented-demo.png`、`04-mode-control-demo.png` |
| 分段 hover、pressed、键盘焦点、禁用与 160 ms 选择动画 | CONTROL-SPEC §3；VISUAL-ACCEPTANCE | 通过；动画结束后清除效果，已在真实 Windows 页面复核 | 控件四态截图；[动画缺陷回归](CONTROL-ANIMATION-REGRESSION.md)；`src/test_stats_controls.py` |
| 图卡白底轻边、标题 16 半粗体及 20 像素线性图标 | 原图图卡；DESIGN §5；CONTROL-SPEC §2 | 通过 | `01-overlay-demo.png`、`04-mode-control-demo.png` |
| 图卡内具名图形模式、无 ComboBox；按指标只显示允许选项 | CONTROL-SPEC §2–3 | 通过；`set_mode_options(('line', 'area'))` 显示折线/面积，单一允许模式隐藏无意义切换 | `04-mode-control-demo.png`、`08-narrow-mode-demo.png`；图表控件测试 |
| 指标入口置于图卡标题、菜单为 Fluent 浮层 | CONTROL-SPEC §2；主会话接口要求 | 通过；指标动作和交换位置由页面创建 | `04-mode-control-demo.png`、`05-metric-menu-demo.png`；`set_metric_menu` 测试 |
| 图例色点、文字与右侧紧凑排列 | 原图 01；DESIGN §5 | 通过；修正过图标压字 | `01-overlay-demo.png` |
| 窄卡标题不被图例挤压、图例换到下一行，分段完整可见 | CONTROL-SPEC §2；DESIGN §6 | 通过 | `07-narrow-demo.png`、`08-narrow-mode-demo.png`；窄卡布局测试 |
| 紧凑宽卡标题/模式/全屏同行，绘图区约145像素且轴完整 | DESIGN §5–6；主会话紧凑要求 | 通过；完整页面一屏仍差37像素，属于页面整合未通过 | `09-compact-cashflow-demo.png`、`10-compact-line-demo.png`、`12-compact-page-probe.png`；[量测说明](COMPACT-CHART-ACCEPTANCE.md) |
| 全屏轻按钮与图卡完整放大 | 原图 01/02；DESIGN §5 | 通过；offscreen 全屏按其可用 796×796 画面核验 | `06-fullscreen-demo.png`；全屏测试 |
| 蓝/绿公司色、同期浅色虚线、并排时间柱、缺失断点、轻网格轴 | 原图 01/02；VISUAL-CONTRACT §5 | 通过；演示数值与原图不同属有意差异 | `01-overlay-demo.png`、`02-period-demo.png`、`03-area-demo.png`；图表模型测试 |
| 外壳 Mica、导航/Pivot、筛选、KPI、整页滚动与真实存档 | DESIGN §4/§6；CONTROL-SPEC §2 | 未验证；属于页面整合范围 | 本阶段仅运行图卡与控件，没有整页截图 |
| 125%/150% DPI、1366×768/920×680 页面、空值/错误弹窗 | DESIGN §4/§6；VISUAL-ACCEPTANCE | 未验证；需整页与不同 DPI 环境 | 当前仅 96 DPI 图卡截图；空值逻辑有单元测试但无状态截图 |

组件范围内没有已知未通过项。当前 400 像素图卡截图用于验证图例换行；完整页面宽度、Mica 背景、入口菜单与指标交换的整合效果必须由页面会话用真实存档再验收。
