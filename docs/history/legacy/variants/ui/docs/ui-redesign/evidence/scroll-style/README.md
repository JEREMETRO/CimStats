# 滚动条与卡片切换样式复验

真实双人存档，1440×960 完整窗口截图：

最终合并版本的所有模式与分辨率见 [完整截图目录](../../one-screen-evidence/README.md)。

| 页面 | 截图 |
| --- | --- |
| 网络总体 | [查看](network-overall-1440x960.png) |
| 网络多公司 | [查看](network-companies-1440x960.png) |
| 网络同期 | [查看](network-period-1440x960.png) |
| 网络同期，筛选收起 | [查看](network-period-collapsed-1440x960.png) |
| 城市默认 | [查看](city-default-1440x960.png) |

三个统计滚动区共用 `StatisticsScrollArea`，使用 Fluent 覆盖式滚动条；原生 Qt 滚动条不可见，实际滚动范围仍保留。设计参照 [Microsoft 的滚动控件规范](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/scroll-controls) 中轻量滚动指示和悬停展开的处理。紧凑切换按钮统一由 `FluentSegmentedControl` 绘制浅色选中态，覆盖 KPI 与图表的所有网络模式；大尺寸筛选模式按钮保留强调色。

自动检查涵盖鼠标滚轮、触控板像素增量、方向键、Page Up/Down、Home/End，以及触控滚动器的绑定和滚动；焦点位于数字输入框时，方向键继续由输入框处理。截图与校验脚本为 `src/qa_stats_scroll_style.py`。未接入物理触控屏，触控手势的设备端体验仍需实机确认。
