# 稳定版独立验收：真实加载、事件进度与五组模拟布局

日期：2026-09-30。范围：主项目 `8f7984f` 的两份真实存档加载与 Qt 缓存布局；随后针对 UI 边界修复 `36373d4` 复测。城市页在途实现、打包 EXE 和五组 Windows 原生屏幕设置不在此次通过范围。原始小型证据见 [independent-final-evidence](independent-final-evidence)；完整隔离 job 与 session 留在本机临时目录 `C:\Users\Administrator\AppData\Local\Temp\CIM2_QA_8f7984f_20260930`。

截图：[单人真实加载就绪](independent-final-evidence/single-real-load-ready.png)、[双人真实加载就绪](independent-final-evidence/multi-real-load-ready.png)、[200% 模拟双人网络总体](independent-final-evidence/multi-network-qt-200pct.png)、[150% 模拟双人网络同期](independent-final-evidence/multi-network-period-qt-150pct.png)。

## 真实存档加载

使用根目录当时的已修改探针 DLL 的**实际磁盘字节**制作临时 runtime，GUI 与解析 job 输出均在独立临时目录。`benchmark_load.py` 的成功终点包括公司和网络双 snapshot 就绪、query timer/workers 结束、遮罩隐藏及统计页首帧 `grab`。每份只运行一次，Qt offscreen 1920×1080；OS 文件缓存未受控，因此这不是物理磁盘冷启动，也不是最终打包 EXE 的原生测速。

| 真实存档 | 到就绪/首帧 | 解析器完成 | 两者间隔 | 父子进程树峰值 RSS | 子进程峰值 RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| `望春市6.save` | 13.761 s | 12.135 s | 1.626 s | 528.7 MiB | 388.9 MiB |
| 双人 `quicksave...save` | 15.809 s | 14.054 s | 1.755 s | 628.0 MiB | 487.4 MiB |

- 本轮两份 normalized session 与性能会话此前的 `actual-single-1`、`actual-multi-1` session 逐字段完全相等。每份 15 类 CSV 的 SHA-256 与 `correctness-comparison.json` 全部一致；各两本 XLSX 的 ZIP 内文件仅 `docProps/core.xml` 生成时间元数据不同，其余成员字节一致，覆盖工作表、单元格与公式。真实 `.save` 和根目录 probe 的本轮前后 SHA-256 分别保持 `9D6F8C3C…A8496`、`79A6D641…B360C`、`9AB2ECA2…DD70E`；probe 在测试开始前已有 Git 修改，未恢复或覆盖。
- 单人/双人分别捕获 58/66 条真实进度事件；每类已出现的计数满足整数、`0 <= done <= total`，最终为线路 `59/59`、`73/73`，历史 `58098/58098`、`51746/51746`，CSV 均 `15/15`，校验均 `2/2`。按事件重放阶段模型时数值不回退，完成前最高 96%，显式 `finish()` 才为 100%。真实 GUI 两次最终遮罩均已隐藏；此次结果未连续录屏，不能仅凭末帧证明每个中间帧无闪动。
- 另用 offscreen MainWindow 直接调用复现 `done=0,total=0` 曾把遮罩文案显示为 `0/0`，虽然模型拒绝该事件。实现方修复提交 `36373d4` 合入 QA 树后，独立复测无效 `0/0` 不再改变最后有效文案，合法 `0/2` 与 `2/2` 仍显示，`2/2` 时 UI 环为 96% 而非提前 100%。相关 `test_ui_refinement.py`、`test_parse_progress.py`、`test_parse_events.py` 共 **26 passed**（5.68 s）。实际失败/取消/超时仅有实现方证据与这些组件回归，本轮未再启动真实故障注入。

## 五组 Qt 模拟窗口布局

独立启动五个 Qt offscreen 进程，按目标物理像素/缩放设逻辑窗口，以前述真实解析生成的 session 缓存重排单人及双人数据。每组记录 16 个页面状态，其中 12 个公司默认/网络总体核心状态（摘要展开、折叠、恢复）均为 H/V 最大滚动值 `0/0`、图卡不重叠；重新计算严格视口边界（不使用脚本允许的额外 1 像素容差）也无越界。展开时单人公司 6 KPI/4 图、双人公司 12 KPI/8 图、单人网络 6 KPI/8 图、双人网络 **5 KPI/7 图且无联合总覆盖率**；折叠时 KPI 内容隐藏而图数不变。两张抽查截图分别展示双人网络总体及仍需滚动的同期模式。

| 目标物理/缩放 | Qt DPR | 逻辑窗口 | 实际视口 | 截图像素 | 核心 12 状态 | 双人网络同期剩余 V 滚动（展开/折叠） |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| 2880×1920 / 200% | 2.00 | 1440×960 | 1168×769 | 2880×1920 | 12/12 通过 | 446 / 300 |
| 1920×1080 / 100% | 1.00 | 1920×1080 | 1648×877 | 1920×1080 | 12/12 通过 | 138 / 0 |
| 2560×1440 / 125% | 1.25 | 2048×1152 | 1776×949 | 2560×1440 | 12/12 通过 | 66 / 0 |
| 3840×2160 / 175% | 1.75 | 2194×1234 | 1922×1031 | 3840×2160 | 12/12 通过 | 0 / 0 |
| 2560×1600 / 150% | 1.50 | 1707×1067 | 1435×864 | 2561×1601 | 12/12 通过 | 351 / 205 |

这是**逻辑窗口的高 DPI 模拟和缓存重排**。Qt offscreen 的 `screen.geometry()` 边长仅 400–800 逻辑像素，与表中的目标屏幕及可用几何不符；150% 因逻辑取整产生 1 像素的截图差。不能据此声称五组 Windows 系统缩放原生最大化通过，也不能声称每组均重新解析真实存档。实现方的 Windows 原生 175% 普通 Mica type 2 截图是 1440×960 逻辑窗口，不是该屏幕最大化硬门槛；连续 `showEvent` 无闪黑、实体鼠标/触控、其余四组原生设置仍待验。

## 性能对照口径：原缺口已修复并独立复核

初版 `analyze_benchmarks.py` 用 `k.startswith('frontend/')` 过滤源哈希；Windows 原始键为 `frontend\\...`，导致 `matching_frontend_source_hashes={}`，空集合错误通过“同前端源码”断言。初版 12 次记录实有两种前端源码状态，因此原 **39.8%/45.0%** 只保留为历史观测值。性能会话提交 `e4331fa` 修正 Windows 路径规范化，并明确标旧汇总 `controlled_source_comparison=false`、哈希集合为 `null`。

新实验由固定提交 `36373d4` 导出完整应用快照；旧/新变量仅将 `MemoryStream(PAYLOAD.read_bytes())` 与 `MemoryStream(File.ReadAllBytes(...))` 对调，同一修正测量器、同一 runtime 与存档。每档按旧/新、新/旧、旧/新运行三对。独立逐份核对 12 个 `fixed-*/result.json`：每次运行前后均与对应的 99 文件 manifest 完全匹配，19 个前端文件的清单非空且全程相同；两 manifest 只有 `src/extract_runtime_data.py` 不同。生成基线提取器与固定源码按文本比较也仅有这一处参数表达式差异。两种变量的根 probe 哈希均为 `9AB2ECA2…DD70E`；[固定来源清单](../performance/evidence/fixed-source-20260930/source-manifest.json)及[执行顺序](../performance/evidence/fixed-source-20260930/run-order.json)可追溯。修正后 `fixed-benchmark-summary.json` 标 `controlled_source_comparison=true` 并列出 19 个前端哈希；Windows、空清单、缺文件、源变更等七项定向测试独立执行 **7 passed**。

| 固定源码对照 | 旧变量三次中位 | 新变量三次中位 | 耗时减少 | 父子进程树峰值 RSS 中位 |
| --- | ---: | ---: | ---: | ---: |
| 单人 `望春市6.save` | 22.866 s | 13.656 s | 40.277% | 571.7 → 528.6 MiB |
| 双人 `quicksave...save` | 28.645 s | 15.893 s | 44.519% | 675.5 → 627.5 MiB |

上述数字由原始 `result.json` 重新计算并与[新汇总](../performance/evidence/fixed-benchmark-summary.json)一致；六对正确性记录各有 15 类 CSV 字节、两本 XLSX 工作表/单元格/公式与 normalized session 一致。**前述源码对照缺口已关闭。**结论限于当前源码程序的 Qt offscreen、进程/运行时冷启动与未受控 OS 文件缓存，且每档仅三对；固定变量验证的是这一处跨语言字节封送成本，不能推断最终打包 EXE、物理磁盘冷加载或所有硬件上的提速比例。我的两份单次独立新流程加载用于正确性与量级交叉检查，不被混入这三对统计。
