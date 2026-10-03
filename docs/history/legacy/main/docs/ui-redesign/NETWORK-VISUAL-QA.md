# 网络页视觉验收记录

日期：2026-09-29。以下图片来自实际 `MainWindow` 和网络页，数据由
`capture_network_demo.py` 生成并在界面标注为演示记录，不是游戏存档。
另已按真实加载链截取[单人和多人存档页面](real-save-evidence/README.md)，包括单人宽窗六 KPI 同排、单人窄窗重排、下部图卡、动画结束后的分类横条与饼图。

| 场景 | 截图 | 核对结果 |
| --- | --- | --- |
| 总体数据 | [1600×1000](network-visual-evidence/network-overall-1600x1000.png)、[完整内容](network-visual-evidence/network-overall-content.png) | 两公司时五项摘要同排，下方七图集中排列；不显示没有联合口径的覆盖率卡和图，其他图轴可读 |
| 多公司对比 | [1600×1000](network-visual-evidence/network-companies-1600x1000.png)、[完整内容](network-visual-evidence/network-companies-content.png) | 两公司摘要使用各自标识色，覆盖率为各公司总组曲线，九图含分公司客流 |
| 单公司同期 | [1600×1000](network-visual-evidence/network-period-1600x1000.png)、[完整内容](network-visual-evidence/network-period-content.png) | 两公司等宽双栏；对应图共量程，纵轴数字完整；同期柱颜色较浅 |
| 窄窗 | [920×680](network-visual-evidence/network-overall-920x680.png) | 五项摘要换为三列、两行；横向滚动条最大值为 0 |
| 图卡交互 | [时间柱](network-visual-evidence/network-trend-bar-card.png)、[构成饼图](network-visual-evidence/network-pie-card.png)、[全屏](network-visual-evidence/network-chart-fullscreen.png) | 图形切换与全屏可见；柱体是低对比、同色系微渐变 |
| 日期 | [选择器](network-visual-evidence/network-date-picker.png)、[日历弹层](network-visual-evidence/network-calendar-popup.png) | 沿用全局时间选择器 |

色彩自查覆盖公司/网络的折线、轻面积、时间柱、分类横条、堆积柱、饼图、图例与 KPI 图标。同一公司使用稳定身份色；同一类别使用稳定类别色；时间柱、分类横条和堆积柱均有同色系微渐变，比较期保留较低透明度。双公司同期实存截图中右侧绿色曲线与“本期／环比”图例色点一致。城市页保留原默认配色。网络图形切换显示“趋势／分布／比例”，具体按钮由图卡能力决定。

窗口截图包含合成演示和两份真实 `.save`，实际取数证据另见 [网络总体取数复核](NETWORK-AGGREGATION-AUDIT.md)。完整回归为 305 项通过、1 条既有 qfluent 弃用警告；尚未在实体高 DPI 显示器或鼠标悬停场景下复核。
