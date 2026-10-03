# Fluent 图表可见层自查

> 当前视觉实施记录。用户最终选择继续 PySide6 模拟 Windows 设置微渐变风格；官方 Pro `ChartWidget` 不再是依赖。此实现不是原生 WinUI 3 或官方 Pro 图表组件。

图卡仍使用原有 `ChartPanel` 和真实 `Result` 数据接口。QtCharts 保留坐标和序列数据；可见数据形状由 `FluentChartView` 绘制，后台形状透明。以下局部图片均由真实图卡在 Qt 程序中抓取，**数据是固定的合成演示 fixture**，生成器为 `src/qa_stats_charts.py`。

| 检查项 | 结果与证据 |
| --- | --- |
| 时间柱圆角、稀疏柱宽 | 通过；`evidence/charts/13-sparse-seven-demo.png`，7 桶单柱约 14px，清晰间隔，柱内仅同色轻微透明度渐变 |
| 密集分组与两公司颜色 | 通过；`evidence/charts/14-dense-forty-two-demo.png`、`01-overlay-demo.png`，42 桶自动收窄，双公司并列 |
| 同期现金流、负值、零值、缺测 | 通过；`02-period-demo.png`、`13-sparse-seven-demo.png`，负值跨零线，零值无点，缺测留空；本期/对比文字标识 |
| 轴线、水平网格、单位 | 通过；上述图中无 L 形轴线及装饰性刻度，少量淡水平线，单位横排于左上 |
| 唯一轻面积折线 | 通过；`03-area-demo.png`、`10-compact-line-demo.png`；`line` 模式直接呈现约 2px 轮廓、上沿 10% 向零线渐隐面积及低强度柔影；断点不连接，前期虚线，不显示逐点大圆圈 |
| 负值折线与缺测 | 通过；`17-line-cross-zero-demo.png`，正负面积分别向真实零线渐隐，缺测断开；单独非缺测点可见微小标记 |
| 分类横条与饼 | 通过；`15-category-and-pie-demo.png`、`16-category-period-demo.png`，类别色一致，饼环占比及原值中心摘要，横条同期并排及文字标识 |
| 图例、提示、空状态 | 通过；图例可切换类别；自动化用真实鼠标事件验证负值及饼片提示；全缺测显示中性空态、真实零值不冒充缺测 |
| 全屏和 PNG | 通过；`06-fullscreen-demo.png` 由全屏图卡抓图；正式 `export_png` 的新增测试验证导出文件含图形数据色 |

主窗口集成截图在 `evidence/company-integrated/`：`company-single-1600x1000.png` 六 KPI 与四图一屏，纵向滚动最大值 0；双公司默认、同图与同期截图及 920 窄窗均无横向滚动。图卡标题图标 18px、操作图标 16px，命中区常规 36px/紧凑 32px。截图使用主仓库 `db8dfe8` 页面与此工作树 `f2b1ec5` 绘制代码组合，B 后续全页/KPI/导航图标尺寸调整合入后仍须复验。历史首页 `desktop_app.py` 的可达图形需主集成继续核对，见替换表。
