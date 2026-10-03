# 当前图表候选：供视觉审查

此文为较早版本记录。当前候选、补丁散列、真实截图及测试结论请以 [CHART-COMPANY-AVERAGE-REVIEW.md](CHART-COMPANY-AVERAGE-REVIEW.md) 为准。

2026-10-02。本轮只修改 charts 工作树和候选目录，未写主工作区或主工作区 Git index。主工作区此前由主任务应用的字体补丁保持。当前大图候选尚未集成，也未获得视觉确认。

## 当前候选

- 补丁：`root-chart-candidate/CHART-ROOT-COMPATIBLE.patch`
- SHA-256：`fc983cd625856cac55122140c5c6045ecfede7b382cbd54d1ff2a9e7c89855df`
- 大小：116607 bytes。前后文件散列与每文件 merge base 见 `root-chart-candidate/manifest.json`。
- 基于当前主工作区逐文件合并，保留 SurfaceMotion、共享字体、CompactLegendButton、palette、绘图参数和主任务的布局修正。`git apply --check --ignore-space-change --ignore-whitespace` 在主工作区只读检查通过。
- 不要用候选的整个 frontend 目录覆盖主工作区。应用前重新检查 before hashes；主工作区若已应用菜单补丁或有其他新改动，应重新生成候选。

## 已按用户要求实现

仅显示汇总数据卡及大图；明细表保持隐藏。详细视图无 QScrollArea，画布固定在窗口内。全期概览保留真实点/柱，放大及前后窗口控件不扩大画布。折线量程按可见原始值的变化设定，柱形量程从零覆盖完整可见堆叠；刻度精度随真实步长变化。

短周期/粗粒度有足够空间时显示全部数值，长周期/细粒度默认隐藏密集标签，悬停与点击可读对应真实数据；点击绘制单点文字的回归已覆盖。字号按实际文字测量、点位间距及柱形宽高适配，普通值 10–13 px，总值 12–15 px、粗体且仅显示数字。标签无背景填充。柱内文字在共享深色字和白字之间按对比度选择，透明对比期颜色按实际背景合成后判断。详细图柱宽最多 48 px。多公司卡片及卡内指标按可用宽度换行。

原业务 summarize_buckets、原始数值、公司/对比期、真实零值、缺失值、original_total 均保留。网络模型没有将不同公司聚合为一根柱。

## 最新实际 Qt 截图

`evidence/chart-fixed-preview/final-day/`、`final-hour/`、`final-zoom/` 的 line.png / stack.png 与 measurements.json 是本次最终候选生成。其他旧截图均是历史过程，不能用来判断当前实现。

来源为主工作区真实 51282 行缓存，流程 build_dashboard → build_network_snapshot → descriptor → fullscreen；实际使用主工作区共享 stats_typography 与 stats_tokens。截图 1440×960、DPR 1、Qt offscreen，无原生窗口边框。

| 场景 | 折线标签 / 命中点 | 堆叠分段标签 / 柱顶总值 / 命中分段 | 重叠 | 最大柱宽 |
| --- | --- | --- | --- | --- |
| day 全期 4 天 | 8 / 8 | 16 / 8 / 16 | 0 | 48 px |
| hour 全期 96 时段 | 0 / 192 | 0 / 0 / 384 | 0 | 4.90 px |
| hour 放大 12×、8 时段 | 16 / 16 | 32 / 16 / 32 | 0 | 48 px |

所有场景无默认明细表、滚动值为零。放大段折线 555–605 万、每格 5 万，柱形 0–7 千、每格 1 千；全期量程涵盖真实全期变化。单期卡片 80 px，指标字号 21 px 与主工作区 WinUI 一致；单位基线偏差 0。

## 验证与边界

`src/verify_chart_root_candidate.py` 强制从 after/frontend 加载四个图表模块并使用当前主工作区依赖。最终 159 passed in 4.80s，日志 `chart-fixed-preview-candidate-green.txt`。覆盖高基数极窄波动、细刻度文字区分、六公司卡片不撑宽窗口、长周期完整数据、固定窗口导航、无色底与字号/柱宽上限、悬停及合成 Qt 点击。

旧工作树紧凑图例测试中的 340 px / 位图图标宽度预期与当前主工作区不一致；主工作区基线复现 358 px 最小宽度。已改为当前共享控件的可见性、布局边界和隐藏类别行为检查，未为迁就旧预期修改主任务控件。

静态独立审查已关闭密集点击零高区域、细刻度格式、多公司卡片撑宽、极窄范围候选为空四项 P2；最终 delta 无新的 P1/P2。审查未运行 Qt。

尚未执行原生桌面鼠标/键盘、原生边框或五档 DPI 验收。当前截图与合成 Qt 输入不能作为原生输入验收；按主任务指令，先审查 1440 代表截图再安排这些检查。当前没有视觉批准或最终集成结论。

Qt 子进程均已退出，本轮协调 Qt 槽已释放。
