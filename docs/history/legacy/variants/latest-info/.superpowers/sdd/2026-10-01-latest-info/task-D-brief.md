# 包D：导出与唯一集成者

先读 `docs/ui-redesign/LATEST-INFO-CONTRACT.md` 和计划任务5/Global Constraints。用户已确认完整方案、真实自主日对日提醒以及独立GPT-6.1聊天；无需重问。

你是唯一应用接线者。初始阶段只写新的 `frontend/latest_info_exports.py`、`src/test_latest_info_exports.py` 和新的集成失败测试 `src/test_latest_info_integration.py`；共享接线必须等父明确放行。A/B/C其他会话同时写自己的新模块，接口已冻结。不要修改它们，不stage/commit，不另派任务，不向其他聊天发消息。

先纯导出RED→GREEN：`build_share_summary(snapshot) -> str` 从真实快照构造中文摘要，标明城市/存档/模拟时刻/公司和制式/指标范围；`export_latest_info_xlsx(snapshot, alerts, path) -> None` 报告真实13指标、4极值、Top10、全部班次分类/总数/占比、提醒/两期窗口及缺测说明，缺测空值不可写成0或Excel错误；数值保持可计算类型，所有sheet/字符串中文。PNG调用现有export_png，延迟Qt导入避免纯测试启动Qt。不新增PDF/Word依赖。分享与报告菜单后续接同一快照，文件保存取消/换存档不能导出旧快照。

模型测试用pytest --noconftest，不创建QApplication；现有Python在 C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe，sandbox直接执行可能Access denied，父用require_escalated运行纯模型基线73passed。按需要走工具自动审批，不安装新解释器，不把进程启动失败视为测试失败。

共享源和Qt/native当前hold：不能现在改desktop_app/statistics_page/stats_integration或跑GUI。可只读写精确接线方案/失败测试。得到父放行后再运行GUI RED并实现：导航“最新信息”；旧首页函数委派LatestInfoPage；单个取消/过期保护的异步查询生成A快照+C提醒；所有重新载入/失败/取消清理；共享打开存档与原工作簿导出保留。首页新header替换旧首页header，其他页保持原样。迁移统计页提醒列表/开关/阈值入口，同时让统计查询沿用同一阈值配置、不恢复重复提醒UI。保留e4cf2fb筛选动画与5f19eef生命周期，保留线路已有重载选择清理、平均间隔过滤、隐藏line_footer，不改build_lines/show_line/refresh_lines业务。

正式接线文件：worktree frontend/desktop_app.py、statistics_page.py、stats_integration.py、stats_text.py 与必要的本包新控制器模块（如需 `frontend/latest_info_controller.py` 在报告说明）；仅首页/提醒相关hunks。父以后根据主目录新HEAD合并，不能把整个旧工作树文件覆盖主源。

报告写 `.superpowers/sdd/2026-10-01-latest-info/task-D-report.md`。初次完成独立导出/接线方案后简短回复阶段状态，待父同会话启动集成；最终报告含精确hunks、接口、RED→GREEN、真实导出核查、处理的生命周期和限制。

