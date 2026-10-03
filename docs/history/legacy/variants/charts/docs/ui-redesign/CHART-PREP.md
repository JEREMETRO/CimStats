# C 图表实施准备与接口风险

已阅读 README、DESIGN、PLAN、BASELINE，实际查看三张原图。图一要求同指标多公司共用一个绘图区；图二要求每家公司自己的图卡内区分本期实线与比较期虚线；图三默认是公司独立面板。后续要求删除原图的公司摘要大头部，三模式互斥。

## 现有接入点

- `ChartPanel.set_result(result, companies=None)` 接受 `Result`；`series`/`comparison` 以 `(company_id, group)` 索引，`Bucket.value=None` 表示缺失，`Bucket.start` 是 tooltip 的真实日期。保留 `set_mode`、`set_axis_spec`、`clear` 以及 `summary/bar/line/pie/trend-bar` 兼容。`trend-bar` 是现有时间柱图，`bar` 是分类横柱图；公司现金流应走前者。
- `line`/`trend-bar` 已对多家公司同一总计组走单图绘制，对普通组逐公司建图；页面必须传入筛选后的 `Result`，而非靠公司数量推断分析模式。单公司同图对比可沿用单公司分支。`_time_geometry()` 会按较长周期扩展槽位；曲线按桶序号对齐，tooltip 仍取原桶日期。
- `AxisSpec(lower, upper, step, scale, unit_suffix)` 与 `nice_axis()` 已存在。当前线/时间柱收集本期和比较期有效值，并用 `axis.scale` 缩放绘图；页面应按**同指标**的所有可见公司及比较期计算共享 `AxisSpec`，图表严格应用它，不按相同单位把不同指标合并量程。现金流负值仍需零基线。
- 现有 `_PALETTE`/`company_color()` 用 ID 哈希，页面也直接调用此函数。新增 `set_company_palette(dict[id, color])` 后，C 内全部公司线、柱、图例应优先使用传入映射，旧哈希仅作未传映射时的兼容回退；B 的名称色点也须采用相同映射。`stats_tokens.py` 与 `VISUAL-CONTRACT.md` 尚未到达，绘图样式须等其锁定。

## 实施风险与验证目标

1. **图例身份与周期。** 自定义图例目前按类别或公司建按钮，周期仅用独立文字，Qt 图例隐藏。要让同图比较显示公司身份、同期显示本期/对比线型，并保持每个公司所有断线段及周期一起切换；切换只改可见性，不改 `Result`。自定义图例布局目前最多三列且限宽 320，需要按卡片可用宽度换行；长名显示省略但保留全名提示/辅助名称。
2. **缺失与面积。** 折线已按 `None` 拆成多段；新增 `area` 应逐有效段建立轻透明 `QAreaSeries`，不得跨缺口填充。时间柱为保证时间槽对齐，当前把缺失值放成零高 `QBarSet`，悬停应只显示真实有效桶，不声称零是观测值。面积基线和负现金流需单独核验。
3. **同期不等长。** 当前按序号投影到本期时间槽，较长比较期不会截断；横轴末端可能显示本期范围外的投影日期。因此 tooltip 必须明确“本期/对比期”并显示原 `Bucket.start`，不可拿投影日期当真实日期。月粒度与 `[start,end)` 边界要沿用 `period_bounds`，不按固定秒数推算月桶。
4. **hover 联动。** 建议 `hover_offset_changed = Signal(object)` 发出相对**当前周期起点**的秒数；触摸到比较期桶时先按绘图槽位投影到当前时间轴，再发偏移。`set_hover_offset(seconds|None)` 在本图定位最近的有效槽位/高亮点，清空时撤销高亮，且绝不回发信号。重绘、隐藏图例、比较期更长和月粒度下要清理失效 hover，避免信号回环或指向缺失桶。
5. **窄卡与对齐。** `_adapt_axes()` 会随绘图区收缩刻度，但传入共享 `AxisSpec` 时当前跳过自适应；需保证双栏窄卡不裁掉轴标签，同时维持同指标量程/刻度一致。`_time_label_axis()` 已按宽度疏排完整日期，可在原机制上统一绘图区边界和标签基线。
6. **接口协调。** 图卡图标/全屏若由 C 增加独立公开入口，应先与 B 写入共同合约并通知；不要让页面读写 `chart_views` 等私有实现。C 不修改页面、tokens 或业务模型，样式只从 B 的 tokens 导入。

现有 `src/test_stats_charts.py` 已覆盖缺口、共享轴与 scale、负值、长期比较、真实比较日期、柱线时间槽及窄宽标签。实施阶段补 palette/area/hover 无回环及线型图例测试，并生成真实 QtCharts 图卡截图；本准备阶段不修改绘图代码，也不运行全量测试。
