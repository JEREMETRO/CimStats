# 公司统计页视觉自查

2026-09-29。已实际打开并对照[同图对比原图](references/01-overlay-comparison.png)、[同期对比原图](references/02-period-comparison.png)、[双公司默认原图](references/03-side-by-side.png)和[Windows 设置页图表参考](references/07-windows-settings-chart.png)。当前验收依据为[图表视觉实施规范](CHART-SETTINGS-REFERENCE.md)：程序继续使用 PySide6 Fluent 风格实现；公司现金流固定时间柱，其余趋势固定轻面积折线，不显示折线/面积切换。

## 截图元数据

截图由 `capture_company_demo.py` 启动真实程序生成，使用**合成演示历史记录**：两家公司、2024-01-01 至 2024-01-14 每小时八项公司指标。界面标有 `DEMO — synthetic history.save`，数字不代表真实存档或业务默认值。平台 Windows、Qt 逻辑 DPI 96，窗口尺寸见文件名。截图包含 B 的页面比例提交 `4b33eec` 和 C 的绘图提交 `f2b1ec5`、验证提交 `b437676`；合并基线为 `21c4262`。

| 模式与窗口 | 实际页面 | 全部内容/状态 |
| --- | --- | --- |
| 默认，1600×1000 | [窗口截图](company-visual-evidence/company-default-1600x1000.png) | [完整数据区](company-visual-evidence/company-default-content.png) |
| 多公司同图，1600×1000 | [窗口截图](company-visual-evidence/company-companies-1600x1000.png) | [完整数据区](company-visual-evidence/company-companies-content.png) |
| 同期，1600×1000 | [窗口截图](company-visual-evidence/company-period-1600x1000.png) | [完整数据区](company-visual-evidence/company-period-content.png) |
| 默认，920×680 | [窄窗截图](company-visual-evidence/company-default-920x680.png) | 横向滚动最大值 0 |
| 单公司默认，1600×1000 | [窗口截图](company-visual-evidence/company-single-1600x1000.png) | 六 KPI、2×2 图和坐标轴可见；纵向滚动最大值 0 |

附加状态：[日期弹窗](company-visual-evidence/company-date-picker.png)、[日历](company-visual-evidence/company-calendar-popup.png)、[指标菜单](company-visual-evidence/company-metric-menu.png)、[全屏图卡](company-visual-evidence/company-chart-fullscreen.png)。

## 对照检查

| 关键要素 | 结果 | 实际截图或测试证据 |
| --- | --- | --- |
| 外壳、导航、标题文件区与子页 | 通过 | 完整窗口截图；标题底座 40px、图标 22px，Pivot 图标 18px；图标和正文层级较原版协调 |
| KPI 与公司身份色 | 通过 | 主数字及公司名为深色；彩色圆点、18px 辅助图标、图例和当前曲线共用公司色；六项顺序和单位可见 |
| 筛选与三种分析语义 | 通过 | 默认按公司分图，同图共享四图，同期按公司对比；模式选中态在宽、窄窗均可见 |
| 指标菜单和固定图形类型 | 通过 | 六指标菜单与四卡互换测试；现金流固定时间柱，其他指标固定轻面积折线；旧面积偏好不恢复切换控件 |
| 时间柱形状和微渐变 | 通过 | 单公司、同图、同期现金流图均为细圆角柱；柱内同色从顶部微亮到底部基准色。单公司截图中首柱中心 x=325，y=570/600/640 的 RGB 分别为 `(72,134,200)`、`(66,130,198)`、`(59,125,196)`，可量化验证微渐变 |
| 趋势轻面积与图内坐标 | 通过 | 单公司、同图、同期截图：曲线下淡渐变、淡水平网格、横排单位、清晰日期轴；同期用实虚线和文字区分；C 的图形测试覆盖负值、零线与缺测断开 |
| 全屏和 PNG | 功能测试通过 | 全屏截图沿用相同图形；PNG 导出由集成与图表测试覆盖，完整输出尺寸和状态恢复已验证 |
| 单公司宽窗一屏四图 | 通过 | 1600×1000 单公司截图；六 KPI 和四图坐标轴同屏，纵向滚动最大值 0 |
| 窄窗重排与操作可用 | 通过 | 920×680 截图，横向滚动最大值 0；筛选、模式、提醒和导出入口仍可见 |
| 真实存档、鼠标 hover 实景、125%/150% DPI、错误与键盘焦点 | 未验证 | 本组截图使用合成数据和 96 DPI；离屏截图流程未能稳定触发鼠标 hover 提示，这些状态仍需最终实机验收 |

阶段回归：116 项相关测试通过，1 条既有 qfluent 弃用警告。截图证明本轮公司页比例与当前绘图效果；不把 PySide6 绘制称为原生 WinUI 控件。
