# 当前图表候选：公司色阶、紧凑图例与粒度平均卡片

现金流排版追加修正后的当前补丁与截图请见 [CHART-CASHFLOW-ALIGN-REVIEW.md](CHART-CASHFLOW-ALIGN-REVIEW.md)。本文保留上一轮均值及图例变更说明。

2026-10-02。本轮仅写 charts 工作树与候选目录，主工作区六个图表文件与 manifest 的 before 散列一致。候选尚未集成主程序，未自行打包或发布。本文取代 CHART-FIXED-PREVIEW-REVIEW.md 的旧版本状态。

## 交付与基线

- 可应用补丁：`root-chart-candidate/CHART-ROOT-COMPATIBLE.patch`。
- SHA-256：`7c01c9ee6108dc242958627733cee6b3238f877463f3694bd1b51e58828bd533`，130626 bytes。
- 图表工作树 HEAD：`5edf6397f01a5da1b2bb67cf9cc1fe26be631285`，本轮改动为未提交工作树变更。
- 逐文件 before/candidate 散列与 merge base 见 `root-chart-candidate/manifest.json`；chart trio merge base `de1d930`，其他文件 base `f525605476168b212ff7a9ce031ff127b684f05e`。
- 当前主工作区只读 `git apply --check --ignore-space-change --ignore-whitespace` 通过。应用前重新核对 before hashes；不要整目录覆盖主工作区。
- 保留主程序共享字体、SurfaceMotion、CompactLegendButton、palette、绘图参数和布局修正；未修改共享 stats_typography 或业务数据模型。

## 本轮实现

同一制式/类别保留同一色相，不同公司的柱使用稳定色阶。色阶按完整公司 palette 的身份顺序分配，筛选公司不会变色，也不按六家公司循环复用。时间堆叠及端点横柱都应用相同规则；单类别已有公司图例的图不重复追加。图例色样来自实际柱段颜色。小图优先把类别与公司图例合在一行，实际宽度放不下才换行；多类别小图允许两行。行容器复用，24 次模式切换和尺寸变化回归通过。

所有 `flow` 区间求和指标的大图卡片统一显示每家公司“区间总值＋当前粒度平均值”。当前涵盖现金流、分制式客流、分群体客流、票制/分区行程及城市出行量。日、小时、周、月粒度分别使用对应均值标题；stock、比例、coefficient、原本已平均的指标保留原口径。

原 card.values 仍来自原业务 summarize_buckets。均值按公司、当前/比较期分别对齐实际 bucket.start/end，真实零值计入，缺失某类别的时段排除，不外推不足整期的时段。精确 Decimal 均值保留，卡片仅把显示数值四舍五入到最多两位小数。悬停均值可查看参与时段数与缺失处理口径。缺测时区间总值和均值可能使用不同样本：总值保留业务模型的已知值汇总，均值仅使用类别数值齐全的时段。

卡片按数字实际宽度统一尺寸，目标宽度最多 420 px，窗口变窄时换行。数字及单位保留实际最小宽度，修复现金流小数数字被压缩的问题。卡内重新测量后再计算外层高度，真实两公司卡均为 80 px。

此前用户要求保留：仅卡片和大图、固定视口无滚动、适配真实变化的量程、粗粒度全值、密集时段悬停/点击、数字无色底、总值只显示加粗数字、字号及柱宽上限。详细柱宽最多 48 px，普通标签 10–13 px，总值 12–15 px。

## 当前同版真实截图

来源：主工作区 51282 行真实缓存，build_dashboard → build_network_snapshot → descriptor → fullscreen，实际共享样式和字体。所有大图 1440×960、DPR 1、Qt offscreen；截图无原生窗口边框。

`evidence/chart-company-shades/` 下仅这些 `final-*` 目录是当前版本：

| 目录 | 内容 | 数值标签 | 小图实测 |
| --- | --- | --- | --- |
| final-day | 公司价值、现金流趋势、分制式客流 | 8 / 8 / 24 | 分制式 400×195，一行图例 |
| final-hour | 现金流、分制式全期 96 时段 | 0 / 0，完整真实柱保留 | — |
| final-zoom | 小时 12×放大、8 时段 | 48 | — |
| final-groups | 分群体客流 | 56 | 400×208，两行图例 |
| final-tickets | 票制/分区行程 | 36 | 400×208，两行图例 |

每个目录含 screenshot 与 measurements.json。全部卡片高度 80 px，数值宽度达到 sizeHint，标签重叠计数 0，默认表隐藏，横向滚动值 0。所有截图 chart_details 哈希为 `13f852caa70bf4bde7c44644fe9f61d94d8f36d0be0d77a2bf82d42101ff5702`。

日均客流：六进公交 507,926.5 人次，八连交通集团 513,613 人次；对应区间总量 2,031,706 / 2,054,452，真实 4 个日桶。小时均客流 21,163.6 / 21,400.54 人次，真实 96 个小时桶。放大保持所选区间的总值和均值，不改成局部视窗均值。

截图已逐张查看，不能把测试数量当作用户视觉确认。未开展当前候选的原生输入、窗口边框或五档 DPI 验收；原生验收由主任务在代表截图核验后安排。

## 验证

`src/verify_chart_root_candidate.py` 强制使用 after/frontend 图表模块及主工作区依赖，最终 **220 passed in 6.12s**，日志 `chart-company-average-green.txt`。覆盖所有 flow / 非 flow 指标口径、四种粒度、真实零值、缺失类别、比较期、精确与显示均值、长小数数字宽度、布局高度、所有双公司柱图及紧凑图例、固定视窗与标签/命中。

均值实现与最后宽度修正经独立静态审查；审查不运行 Qt。所有本轮 Qt 子进程已退出，协调 Qt 槽已释放。
