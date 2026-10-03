# 包E：独立审查与原生验收

先读 `docs/ui-redesign/LATEST-INFO-CONTRACT.md` 与计划任务6/Global Constraints。你是独立验收者，只读产品源，不另派任务，不向其他聊天发消息，不stage/commit。用户已确认完整方案，无法计算的提醒不生成。

初始A/B/C/D正在分包实施，Qt/native窗口尚未释放。先准备验收清单与 `docs/ui-redesign/qa_latest_info.py`（依赖接口按冻结契约），独立检查风险输入和真实缓存字段。不要启动Qt、鼠标、全库测试；不要轮询其它聊天。报告写 `.superpowers/sdd/2026-10-01-latest-info/task-E-report.md`。准备完成后在最终回复里给预备状态/风险，父会话会在组件/集成就绪后同会话继续派审查与验收。

主缓存绝对路径 D:/test/CIM2_SaveStats/jobs/56dd6b5276cd4c5ba083815f8a30b515，tag 秋山市n6 (2)_运行时；另望春市和多人quicksave缓存。只读、不要改存档或probe，不把测试fixture当真实存档，不把模拟DPI当真实屏幕。

组件就绪后逐包看最终diff/报告，审查规格和质量：真实13指标来源/单位/范围、公司同名ID、综合/制式筛选、总体系数用总量比、缺测/零分母、全市分担率独立、缺小时断线、10条Top10（足够线路时）、所有制式/班次总数、四亮点同字段。提醒前一完整模拟日/前一日，仅complete+confirmed数据沿原规则，已读ID与阈值正确。别从字符串截图推断模型语义。

集成得到父明确放行后，在1440×960原生整窗核验无长滚动、文字/图例完整、10条排行、全部班次类别、提醒真实空态/容量、动作/键盘焦点/tooltip/减少动画/加载取消和反复导入。125%实际缩放与920×680重排也核对，记录frame/client/真实DPR/缓存/代码哈希。未能实际改系统缩放就注明模拟或未测，不能捏造通过。模型/GUI全量检查只在独占窗口运行，保存实际exitcode日志。

收敛报告写 `docs/ui-redesign/LATEST-INFO-ACCEPTANCE-2026-10-01.md`，截图 `docs/ui-redesign/latest-info-evidence/`，缺陷用紧凑ID/严重性/具体路径/复现/预期交父修复。本包准备阶段不能宣称未实施功能通过。

