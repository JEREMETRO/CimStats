# 分段按钮切换后空白：复现与修复

2026-09-29。使用 B 的真实 `MainWindow` 公司页演示脚本，只读其工作树，把输出定向到本图表工作树。脚本依次切换默认、多公司、同期、默认，再缩至 920×680。数据为明确标记的合成历史，不是用户存档。

| 环境和状态 | 结果 | 实际页面截图 |
| --- | --- | --- |
| Windows 原生 Qt 平台，旧共享控件 `e6e004e` | 默认模式第一段蓝色与文字消失，另外两段可见 | [修复前 920×680](evidence/controls/segmented-page-before-920.png) |
| Windows 原生 Qt 平台，修复后控件 `5492cd0` | 默认模式蓝底、白字、图标完整 | [修复后 920×680](evidence/controls/segmented-page-after-920.png) |
| Qt offscreen，同样切换与重排 | 同样能复现；修复后完整显示 | 已实际打开 offscreen 页面截图；未将控件自身 `grab()` 的透明图当作页面故障依据 |

根因：选中项的 160 ms `QGraphicsOpacityEffect` 动画结束后没有从 `TogglePushButton` 移除。布局重排后的绘图层会留下空白。诊断中把动画暂时禁用，页面恢复；正式修复保留切换动画，在结束或被下一次切换中断时停止动画并移除旧效果。Fluent 控件自带 hover、pressed、focus 状态未变。

回归验证：`src/test_stats_controls.py` 检查动画完成后所有按钮没有遗留绘图效果，快速切换、resize、禁用再启用后选中键和互斥状态正确。图表与控件定向测试 61 项通过。截图为 96 DPI；125%/150% DPI 及真实用户存档仍由整体验收覆盖。
