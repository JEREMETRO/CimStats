# 包B：最新信息布局

先读 `docs/ui-redesign/LATEST-INFO-CONTRACT.md`，它是冻结接口与精确要求；读计划任务3及Global Constraints。用户已确认完整增量方案和独立6.1聊天。

只写 `frontend/latest_info_page.py`、`frontend/latest_info_charts.py`、`src/test_latest_info_page.py`。只读共享token/control/elevation/motion/ChartPanel，不修改它们、不stage/commit、不向其他聊天发消息、不派其他任务。

初始Qt窗口hold：先检查另外两页真实代码与规范、设计1440×960内容预算、写有意义的失败测试。等待父会话发送Qt放行后才运行QApplication，确认失败再写GUI实现；不要因为纯模型/Qt不允许而改全局夹具。当前可只读/写测试并报告准备好。

页面真正替换旧首页，保持13指标/四完整极值、今日小时趋势、完整Top10、完整制式班次和约260px右栏；名字“最新信息”。按接口信号独立组装header/action，开存档primary，XLSX/分享/报告真实动作由D接入。纯Fluent城市卡，无插图/宣传语；统一共享12/21字号与圆角/阴影/动效，默认主值21而不是让单位跟着巨大。内容一屏优先减少padding、响应式而非小字删内容。小窗允许滚动。

趋势复用共享ChartPanel。排行/制式分类不伪装时间序列；保留旧有效综合Top10/钻取/返回及班次排行操作。不要改其他页的图表接口或业务。空数据、缺数据、10个长名字和6类制式均需完整；实际数据不足10条则真实实际数，不填示例。

报告写 `.superpowers/sdd/2026-10-01-latest-info/task-B-report.md`：布局预算、界面接口、测试及Qt排期状态、产物/截图真实性、限制。待A文件完成再使用其真实dataclass，不另建重复快照模型。

