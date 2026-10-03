# 1.0.0 候选验收索引

P1、P2、P3 与 REVISION 共同生效。此文件只记录开发验证，不增加页面说明。

## 需求与实现对应

|要求及来源|责任|实现|验证依据|
|---|---|---|---|
|P1/P3 Qt、系统标题栏、三个侧栏入口与折叠保存|B/Root|desktop_app、stats_style|test_stats_shell、test_other_pages；Root 实际点击三个入口|
|P1/P3 原公司概览筛选、排行、饼图、指标切换|B/Root|desktop_app|test_other_pages；root-legacy 首屏及底部截图|
|P1/P3 原线路查询搜索、排序、制式/公司、详情/班次/字段|B/Root|desktop_app|test_other_pages；Root 实际线路选中和时刻表|
|P1/P3 原两个 XLSX 导出保留|B/Root|desktop_app|test_existing_xlsx_exports_keep_identical_bytes；候选真实存档校验|
|P1/P3 单存档、默认全部公司、城市只一次、稳定身份/颜色|A/B/C|report_model、dashboard_model、stats_charts|test_dashboard_model、test_stats_shell、test_stats_charts|
|P1/P3 最近七完整日、日粒度、此前七日|A/B|default_window、statistics_page|test_dashboard_model、test_statistics_page|
|P1/P3 小时/日/周/月及五种比较、无历史不补零|A/B|statistics_model、statistics_page|test_statistics_model、test_stats_shell、F period-probes|
|P1/P3 取消/旧查询拒绝/存档切换与关闭|A/B/Root|statistics_page、desktop_app|test_statistics_page、test_other_pages；F 审核|
|P1/P3 公司六指标、三满意度、最多三指标、异单位小图|B/C|statistics_page、stats_charts|test_stats_shell；F final7276c899|
|P1/P3 服务五指标、站点分制式、运行车辆均值|A/B/C|dashboard_model、statistics_page|test_dashboard_model、test_stats_shell；F 缺失公司行复核|
|P1/P3 三客流独立四视图与选择保存|B/C|statistics_page、stats_charts|test_stats_charts；E 模式切换截图|
|P1/P3 总量/类别累计/周期趋势/占比；多公司分别展示|A/C|statistics_model、stats_charts|test_dashboard_model、test_stats_charts|
|P1/P3 群体及制式同一乘车人次，分区游戏类别出行量|A|statistics_model|真实样本 real-data.json 三组分子/分母|
|P1/P3 换乘系数汇总分子除以分母、两位小数、零分母—|A/B|statistics_model、statistics_page|test_dashboard_model、test_stats_shell；3.1513/2.6771/2.4776|
|P1/P3 图例显隐不改变统计总量/系数|C|stats_charts|test_stats_charts 图例、饼图及模式切换|
|P1/P3 公司现金流/城市出行量柱状趋势，其余折线|B/C|statistics_page|test_stats_shell、test_stats_charts|
|P1/P3 城市六指标、经济指标替代GDP、能源原始值|A/B|statistics_model、statistics_page|test_dashboard_model；城市看板截图|
|P1/P3 城市三种方式条图、加权且不归一|A/B/C|city-mode-share results|F incremental-af454be7：19/29/39%，合计87%|
|P1/P3 提醒覆盖四看板、阈值/开关/单条全部已读/持久化|A/D|dashboard_model、stats_alerts|test_dashboard_model、test_stats_alerts、test_stats_integration|
|P1/P3 提醒身份含存档/公司/指标/窗口，变化产生新提醒|D/Root|stats_alerts、stats_identity|test_stats_alerts、test_stats_identity|
|P1/P3 完整PNG、五张XLSX页、单位/时间/完整度、同快照|D/Root|stats_exports、stats_integration|test_stats_exports、test_stats_integration；E PNG/XLSX|
|P1/P3 去除明细/原始小时入口、不增加业务页面|B/Root|statistics_page、desktop_app|三个导航入口及可见文案复核|
|P2/P3 无新说明/备注、数值悬浮限定内容、缺失—|Root/B/C/D|stats_text 及展示组件|test_tooltips_use_approved_metric_label_not_model_explanation；E 文案清单|
|P2/P3 0基线、负值完整、整数1/2/5步长、有效零范围|C|nice_axis、轴自适应|test_stats_charts；负值/极大数/瞬时小尺寸回归|
|P2/P3 同单位比较小图量程一致、时间轴周期对齐|B/C|set_axis_spec、_time_geometry|test_stats_shell；F 小时和部分月份独立复核|
|P2/P3 1400/1000断点、边距20/12、卡片16、可达滚动|B/C|statistics_page|dashboard_qa geometry/overflow；E 断点连续缩放|
|P2/P3 五种尺寸×四种缩放、长名/同名/空态/菜单|E/Root|真实 MainWindow 渲染|E matrix/supplemental；Root root-af454be|
|P3 独立分支、子会话、medium上限、主会话集成|Root/A–F|六个原任务、各 feature 分支|Git merge 历史、CONTRACTS、progress|
|后续要求：全部审核后版本1.0.0，正式包不覆盖|Root|VERSION、build_portable、verify_candidate|最终 VERSION.json / validation.json / VALIDATION.md|

## 审核证据位置

- Root：`jobs/ui-qa/real-data.json`、`root-legacy/`、`root-af454be/`、`root-dates/`。2026-09-27 全量 163 passed；仅一条依赖 QFluentWidgets 的弃用警告。混合子集曾暴露测试间 Qt 对象残留，正式 conftest 加入逐测试销毁后原5项组合及全量均通过。
- F：`jobs/review-f/final7276c899/RECHECK.md` 与 `incremental-af454be7/RECHECK.md`。数据身份、聚合、时间对齐、异步及新增城市绑定阻塞项已关闭。
- E：`D:/test/CIM2_SaveStats-ui-review-e/jobs/review-e/`。中间版本报告不能代替修复后报告；最终报告须绑定最终提交。
- 候选：`build/staging/v1.0.0/`，只有构建后真实存档验证及桌面检查通过才可认定候选验收完成。正式 `dist` 未被本任务替换。

## 构建前门槛结论

> 以下结论记录首次候选构建前的阶段结果，已被随后用户首页视觉反馈撤销整体交付资格。当前以 VISUAL-REVIEW.md 的追加要求和修复后证据为准。旧候选保存在 build/rejected/v1.0.0-de9b624，不能交付。

- F 最后生产代码增量 `12b9f95` 审核通过，独立时间/数据位置8组通过；测试生命周期问题由 `c2f913c` 正式清理设施闭环。
- E `final-12b9f95/REPORT.md` 确认三个剩余视觉阻塞全部关闭：日期完整、空态提醒无残影、5/6分类图无叠印。Root 检查对应真实渲染及小时/跨年窄图。
- 版本变为1.0.0后只变更版本/文档，最终矩阵、候选运行和验证凭据在固定提交上生成；最终包体结论见候选目录 `VALIDATION.md` 与 `validation.json`。
