# 统计页 Fluent 图形绘制替换表

> 当前实施入口清单。用户最终选择在现有 PySide6 图卡中模拟 Windows 设置风格，官方 Pro `ChartWidget` 不再是依赖。外观以主仓库最新 `CHART-SETTINGS-REFERENCE.md` 为准。

用户参考：主仓库 `docs/ui-redesign/references/07-windows-settings-chart.png`。统计页仍使用 PySide6 的数据接口，图形可见层由受控绘制实现。

| 可见部分 | 当前路径 | 替换方式 | 验证 |
| --- | --- | --- | --- |
| 时间柱、双公司/同期并列柱 | `ChartPanel._time_bars`、`_combined_time_bars` 的 `QBarSeries` | 后台 series 保留数据与坐标；前台绘制按密度限宽、圆角、分组的细柱，零值不画点，缺测不画柱 | 稀疏 7 桶、密集 14+ 桶、双公司、同期、正负和零 |
| 分类横条 | `_bar_charts` 的 `QHorizontalBarSeries` | 同一前台绘制器生成细圆角横条；维持类别顺序与正负基线 | 多类别、同期、负数 |
| 折线、面积 | `_append_time_segments` 的 `QLineSeries`、`QAreaSeries` | 隐去默认形状，前台绘制 2px 圆端折线与仅填充的低透明度面积；每个非缺测连续段独立 | 缺测断点、同期虚线、常态无点 |
| 分类饼 | `_pie_charts` 的 `QPieSeries`/slice | 前台绘制细分隔的环形饼及中心摘要；图例保留可操作 | 类别切换、占比、空值 |
| 坐标/网格/单位 | `_value_axis`、`_style_category_axis`、`_time_label_axis` | 隐去轴线与刻度短线，仅保留淡水平参考线及必要零线；单位在绘图区左上横排 | 正负量程、窄卡、数值单位 |
| 图例、提示、选中 | `_build_legend`、`_series_hover`、`_bar_hover`、`_show_hover_target` | Fluent 按钮及自主绘制命中区，单点高亮与原值提示；不可见组不绘制 | 图例显隐、hover、键盘焦点 |
| 全屏、PNG | `_open_fullscreen`、`QWidget.grab` | 复用相同绘制器与数据描述，随 plotArea/设备像素比重新绘制 | 全屏与抓图同款、缩放不失真 |
| 空状态 | `_render`、`_pie_charts` | 图卡表面内的中性空态文字，无默认图表标题 | 全缺测、全零饼 |

`frontend/desktop_app.py` 还含旧版 `PieView`/`ChartPanel`/`ChartWidget`，须由主集成检查是否仍是用户可达页面；该文件由公司页工作流维护，此分支不并发改动。规划中的 `frontend/network_charts.py` 尚不存在，网络页图形待恢复该工作流时套用同一风格。以上两项不视为已验收。
