# 包A：真实首页快照

先读 `docs/ui-redesign/LATEST-INFO-CONTRACT.md`，它是冻结接口和精确要求；再读计划任务2及Global Constraints，不重启需求梳理。用户已确认完整方案/真实自动提醒/独立6.1聊天。

只写 `src/latest_info_model.py` 和 `src/test_latest_info_model.py`；必要纯模型数据audit输出写本包报告目录。参考共享statistics_model/dashboard_model/network_model/city_model及frontend/report_model，但不得修改它们。不得Qt、不得stage/commit、不得向其他聊天发消息或另派任务。

先失败测试，再最小实现，再通过；使用pytest --noconftest避免全局Qt夹具。重点独立证明：同名公司ID/制式筛选、原11指标+2指标、四极值及Top10范围、总体系数110/30而非平均、城市份额独立、缺小时断线、模拟时刻截断、零分母/缺测None。覆盖真正统计分子/分母不只验证字符串。

读取真实缓存需使用主目录绝对路径：`D:/test/CIM2_SaveStats/jobs/56dd6b5276cd4c5ba083815f8a30b515`，tag `秋山市n6 (2)_运行时`；另主目录exports的望春市和多人quicksave。只用load_session读取既有缓存，不重新解析或修改存档/probe。清晰区分原11指标来源（线路快照/车队/周收入）与历史城市/网络值；平均间隔源范围差异写报告，跳过未启用/运行日未知。

报告写 `.superpowers/sdd/2026-10-01-latest-info/task-A-report.md`，包含接口兑现、字段来源/范围、失败→通过命令与实际输出、真实复算、限制。最终回复简短给状态、文件、测试摘要及阻碍；父聊天会读取结果。

