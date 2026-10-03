# 包C：真实提醒集中模块

先读 `docs/ui-redesign/LATEST-INFO-CONTRACT.md`，它是冻结接口与精确要求；读计划任务4及Global Constraints。已确认首页自主上一完整模拟日vs前一日，无法计算不生成，不镜像统计页当前任意窗口。

只写 `src/latest_info_alerts.py`、`frontend/latest_info_alerts.py`、`src/test_latest_info_alerts.py`。共享alerts_for_result/build_dashboard/read ID/阈值只复用；不修改原statistics_page/stats_integration/stats_alerts，入口移除由D处理。不要stage/commit、向其他聊天发消息或另派任务。

可立即先做纯模型RED→GREEN，pytest --noconftest并确保测试不创建QApplication。Qt窗口暂hold；GUI先写失败测试/设计，等待父明确放行后跑失败测试再最小实现。

提醒filters按照模拟时钟上一完整日比较前一日，hour粒度，所选稳定公司ID；继承confirmed、完整、等长、原阈值、转正负/规模/相对量/百分点/绝对值规则；不可比/缺测/换乘系数不生成提醒。保持现有session read身份与settings键。没有真实数据则空态，不填警报，不造严重性和钟表时间。

Fluent右栏最大5项、真实未读数、单项详情/全部列表、单项/全部已读；阈值和开关集中首页，signals见冻结接口。可把阈值设置/全部列表做准确Fluent对话框，不增加运营评价。持久化开关可新增首页专用键，但需记录且不重设已有read IDs。

报告写 `.superpowers/sdd/2026-10-01-latest-info/task-C-report.md`：模型接口、GUI接口、真实规则复用、缺测空态、测试命令实际输出、Qt待放行项目及限制；最终简短回复，父读取结果继续接线。

