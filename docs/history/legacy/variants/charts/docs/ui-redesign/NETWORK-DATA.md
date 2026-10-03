# 网络数据展示模型交付说明

本包只从同一个 `DashboardResult` 派生网络页数据，不重新读取或修改存档。公开入口为 `network_model.build_network_snapshot(snapshot, options, companies, cancelled=None)`；输入、输出 dataclass 与 `NETWORK-PLAN.md` 的 N 接口一致。`companies` 仅返回本次筛选的真实公司 ID 与名称。取消回调返回真时抛 `QueryCancelled`，由页面现有异步 token 负责拒收过期快照。

## 消费约定

- `NetworkSnapshot.summaries`：overall 一套六位置；companies 和 period 各公司一套六位置。顺序固定为线路、设施、车辆、覆盖率、客流/出行、换乘系数。`NetworkOptions` 的三个口径开关仅改变相应位置；车辆选最大时给出不可用原因。
- `NetworkSnapshot.charts`：overall 八卡；companies 九卡，末卡为 `company-passengers`；period 每公司八卡。非 period 的 `Result.comparison` 和比较窗口均为空。period 每张卡只含其所属公司的当前及比较数据；没有比较窗口时保留当前数据并给出原因。
- overall 可合并的图表用 `('__selected__', group)` 作为**展示结果键**；其 `Result.query.companies` 仍是真实所选 ID。此键不得作为真实公司查询条件。站点、跨公司覆盖率保留实际公司键，因为不存在可靠总体值。companies 模式的 `company-passengers` 保留各公司总客流，份额分母仅取所选公司；任一所选公司本期没有客流历史时整卡不可用。仅部分时段缺测时，各公司在该时段的展示值一同置为缺失，防止份额分母只包含部分公司；原始快照保持不变。
- `NetworkChart.allowed_modes` 是图卡能力：小时线路/站点仅 bar；其他粒度 line/bar；覆盖率、换乘系数仅 line；车辆 line/bar；三类分类及公司份额 trend-bar/pie。小时覆盖率保留卡位并显示不可用原因。

## 聚合边界

- 存量在每个桶内取各公司、各分类共同的末观测时刻；时刻错开就不给总体值。站点只有游戏历史分类明细，不提供跨公司或跨制式去重总量。
- 车辆平均先在每个共同观测小时把公司值相加，再按共同小时数加权；缺某公司的小时不当零，并保留不完整标记。小时均值无法推出瞬时峰值，因此最大车辆摘要和车辆图不可用。
- 换乘系数用有效分子总和除以有效分母总和。零分母、缺一侧来源或来源小时不匹配的有观测桶不可合并；完全无观测桶不补零，已有有效桶的结果标记为不完整。
- 覆盖率缺少跨公司空间去重依据：多公司总体数值不可计算，`details` 保留各公司查询值；单公司沿用真实查询结果。分制式客流与分群体客流是同一客流的不同分解，摘要只读取 `transport-by-type` 或按选择读取 `trip-types`，不会重复相加。
- 无历史、不可合并和不支持的能力以 `None` 数值及原因表示；仍可计算的部分观测值保留，但 `complete=False` 并标记范围不完整。本层不插值、不补零、不推断峰值、不生成增长箭头。

## 本包自查

| 关键要素 | 原图/MD依据 | 本次结果 | 实际证据 |
| --- | --- | --- | --- |
| 三模式与所选公司边界 | `NETWORK-PLAN.md` 布局与模式 | 通过：overall/companies/period；不足两家公司退回 overall，空选择不查询全部 | `test_network_modes_have_fixed_summary_and_chart_contracts`、`test_company_mode_falls_back_with_one_selected_and_empty_selection_stays_empty` |
| 六摘要固定位置与三口径开关 | `NETWORK-PLAN.md` 摘要固定六位置 | 通过：设施、车辆、客流切换只改对应摘要位 | `test_summary_switches_keep_six_positions_and_separate_flow_metrics`、`test_maximum_vehicle_is_unavailable_not_peak_of_hourly_averages` |
| 八/九图与单公司同期身份 | `NETWORK-PLAN.md` 图表清单 | 通过：8/9/每公司8；同期只含该公司比较，其他模式清空比较 | `test_network_modes_have_fixed_summary_and_chart_contracts`、`test_period_without_comparison_reports_missing_period_without_inventing_it` |
| 日期和粒度能力 | `NETWORK-PLAN.md` 时间与图表能力 | 通过：沿用输入 `FilterState` 的真实范围；小时线路/站点只 bar、覆盖率无小时趋势 | `test_chart_capabilities_reflect_grain_without_removing_cards`；日期预设沿用既有 `test_stats_view_model.py` |
| 存量、车辆、系数、分类缺测 | `NETWORK-PLAN.md` 数据约束 | 通过：同末时刻、共同小时加权、有效分子/分母，不补缺失类别 | `test_stock_total_rejects_different_latest_observation_times`、`test_vehicle_total_aligns_hours_before_weighted_average_and_keeps_missing`、`test_transfer_coefficient_uses_combined_counts_not_company_ratio_mean`、`test_category_missing_from_one_company_is_not_assumed_zero` |
| 覆盖率、站点、最大车辆限制 | `NETWORK-PLAN.md` 数据约束 | 通过：无法去重/无瞬时来源均显示不可用及原因 | `test_stop_categories_and_coverage_do_not_gain_invented_totals`、`test_maximum_vehicle_is_unavailable_not_peak_of_hourly_averages` |
| 页面视觉、交互态、截图 | `VISUAL-ACCEPTANCE.md` 纯数据会话说明 | 不适用：本包没有 UI 或绘图代码；实际视觉仍待 UI/图表会话及整体验收 | 本包没有运行界面截图，不声称视觉验收 |

接口下游仍须保证图例显隐不改结果/饼图分母，并按 `reason` 与 `complete` 展示不可用及范围不完整状态；这些行为由 UI/图表会话验证。
