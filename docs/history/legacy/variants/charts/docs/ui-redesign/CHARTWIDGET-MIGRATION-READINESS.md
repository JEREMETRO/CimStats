# 官方 ChartWidget 迁移准备清单

> 历史调查记录。用户于 2026-09-29 放弃必须使用 Pro ChartWidget，当前实施以主仓库 `CHART-SETTINGS-REFERENCE.md` 的 PySide6 微渐变方案为准；本文件不再是实施门槛。

## 当前边界

用户要求使用 **Fluent Widgets 组件库现成图表组件**。目前代码仍是 PySide6 + `PySide6-Fluent-Widgets` + QtCharts/自绘，不是原生 WinUI 3，也不是官方 `ChartWidget`。既有 `FluentChartView` 保留待替换，其截图只能作为旧版行为记录。

2026-09-29 本机只安装 `PySide6-Fluent-Widgets 1.11.3`：`qfluentwidgets.ChartWidget` 不存在，`qfluentwidgets_pro` 模块不存在；`PySide6.QtWebEngineWidgets` 可用，`pyecharts` 未安装。官方 [Pro 组件页](https://qfluentwidgets.com/zh/pages/pro/)确认 `ChartWidget` 以 ECharts 绘图，支持直接图表配置或 pyecharts；[官方安装页](https://qfluentwidgets.com/zh/pages/install/)把 Pro 作为另外获取的组件库，并提示 Qt 绑定包不可混装。公开页面未给出当前 Pro 包的完整 Python API。未取得实际包与使用权限前，不编造导入名、构造器或调用方法，不用直接 WebEngine 代替它。

## 主窗口可达图形入口

| 页面/位置 | 现有代码 | 数据输入与交互 | 官方组件迁移范围 |
| --- | --- | --- | --- |
| 统计页公司卡（单公司、双公司、同期） | `company_dashboard.py` 调用 `stats_charts.ChartPanel`；现金流 `trend-bar`，其余趋势当前仍有 `line`/`area` 内部模式 | `company_result(Result, company_ids, include_comparison)`；`set_company_palette`、`set_axis_spec`；公司卡之间相对时间悬停联动 | 时间柱与统一的轻面积折线；B 负责移除公司页折线/面积可见二选一，C 保留公开图卡接口 |
| 统计页服务规模 | `statistics_page.py` 的 `line_panel`、`stop_panel` | `results['linecount']`、`breakdowns['stopcount']` | 轻面积折线、分类横条 |
| 统计页客流 | `statistics_page.py` 的 `passenger_panels`、`transfer_panel` | `breakdowns[metric]` 或 `results['transfer-coefficient']`；现有模式选择和设置值 | 时间柱、分类横条、轻面积折线、饼图，保留业务允许的切换 |
| 统计页城市 | `statistics_page.py` 的 `city_trends`、`mode_panel`、`density_panel` | `results`/`breakdowns`；城市指标选择 | 时间柱、轻面积折线、分类横条、饼图按实际可达模式 |
| 主窗口旧客流/班次卡 | `desktop_app.py` 的 `BarCanvas`、`PieView`，`MainWindow.passenger_panel` 与 `departure_panel` 实例化 | 今日客流/班次聚合：堆积条、Top 10 横条、总览饼与详情饼；点击制式段或饼片进入线路排行 | 同属可达图形，必须迁移并保持点击钻取、排行顺序、数值与占比 |
| `desktop_app.ChartWidget` | 同文件中一个继承 `QChartView` 的历史同名类 | 目前只发现类定义，未发现构造调用；不是官方 Pro 组件 | 在主集成确认无运行时/动态引用后避免名称混淆；不把它计为已迁移 |

## 现有图卡业务映射

`statistics_model.Result` 包含 `query`、`metric`、`series[(company_id, group)] -> list[Bucket]`、`comparison`、当前/对比窗口。`Bucket.value` 为 `Decimal | None`；`None` 是缺测，`0` 是观测零。tooltip 使用原值、单位和真实桶时间。`nice_axis`/`AxisSpec` 管理同指标共享量程与千/万/亿显示缩放。

| 模式 | 迁移输入规则 | 必须保持的行为 |
| --- | --- | --- |
| 时间柱 | `_time_geometry()` 的时间槽；公司/分类/同期各一序列，源值保留 `None`，只在显示轴上缩放 | 分组并列、细圆角、负值跨零线、零不冒充缺测；tooltip 原值与期间 |
| 轻面积折线 | 每个 `(company, group, period)` 的连续非缺测段；不跨 `None` 拼接 | 直线轮廓、低强度渐变面积与柔和阴影，前期虚线/文字，时间悬停联动 |
| 分类横条 | `summarize_buckets` 对当前/对比窗口聚合，类别顺序固定 | 类别色、同期并列、正负量程、汇总 tooltip |
| 分类饼 | 同一聚合结果中的正值切片，按公司独立算百分比 | 图例显隐、原值/占比提示、空态与点击钻取（旧首页） |
| 通用 | `set_result`、`set_mode_options`、`set_company_palette`、`set_axis_spec`、`set_hover_offset`、`hover_offset_changed`、`set_metric_menu`、全屏复制 | 对 B 保持公开入口；所有图形经同一官方组件渲染链，PNG 全页面导出一致 |

旧首页还有 `BarCanvas` 的 `(kind, labels, values, colors, unit)` 和 `PieView` 的切片点击信号。它们不走 `Result`，需要独立业务数据适配；禁止把排名数据假装为时间序列。

## 给页面集成方的共享颜色契约

`stats_tokens.COMPANY_COLORS` 是公司身份的唯一色表，前两色为 `#397CC3`、`#2C9B78`；`stats_tokens.CATEGORY_COLORS` 是独立的分类色表。公司名称色点、KPI 徽记、图例、当前期柱线必须直接使用同一准确颜色，不在绘制器二次调整色相、饱和度或亮度。操作仍使用 `ACCENT`。同期只用 `CHART_COMPARISON_OPACITY` 和明确的虚线/文字标识区分。文字、网格与表面分别使用 `TEXT_*`、`GRID_COLOR`、`CARD_BG`。B 在公司页消费此契约，官方 ChartWidget 适配器后续也必须复用这些值。

## 拿到官方 Pro 包后先验证的 API 与行为

1. 实际组件类的导入路径、版本、PySide6 兼容性、构造/销毁及主题切换；确认能与现有 Fluent Widgets 包共存。
2. 官方支持的配置输入、数据更新和渲染完成通知；仅在看到包内示例/API 后写适配器。
3. ECharts 配置经该组件传入后，细圆角柱、分组宽度、负零、断点、固定量程、轻面积渐变和柔和阴影是否实际生效；阴影不得掩盖相邻线，禁用平滑插值。
4. 组件公开的点击、悬停、图例事件如何回传 Python；验证跨卡相对时间联动、旧首页制式钻取和键盘可用性。
5. 全屏尺寸变化、DPI、离屏 PNG。现有 `stats_exports.export_png` 用 `QWidget.render` 抓整页；必须用真实组件试验是否捕获图面及异步加载后的最终帧，不能凭现有 QtCharts 测试推断。
6. 实际依赖与发布方式。截图元数据必须写组件的真实类名、包名和版本；列明未迁移入口。

阻塞项：真实 Pro `ChartWidget` 包和可用授权尚未提供。此文只完成迁移盘点，不声明组件接入或视觉验收。
