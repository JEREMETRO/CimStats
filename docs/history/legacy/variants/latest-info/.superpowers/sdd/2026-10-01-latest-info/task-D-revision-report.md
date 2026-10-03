# 包 D 第二轮功能接线交付（2026-10-02）

工作树：`D:/test/CIM2_SaveStats/.worktrees/latest-info`。只修改本轮授权的 `frontend/latest_info_controller.py`、`src/test_latest_info_integration.py`，以及 D 自身报告/证据。B 四文件、A/C 模型与提醒、共享 shell/exporter 未改；14 项保护源 SHA256 前后均一致。无主工程/主索引、save/cache/probe 写入，无 stage/commit，无 subagent 或其他聊天消息。

## 结果与未测边界

24 项 revision：正常 RED **18 failed, 6 passed, 43 deselected in 9.89s**（exit 1），最小修复后 **24 passed, 43 deselected in 8.72s**（exit 0）。最终受影响集成/统计导出回归 **72 passed in 33.46s**（exit 0）；独立纯导出 **15 passed in 2.36s**（exit 0）。第二轮控制器功能在本轮授权范围内交付，不以这些结果宣称整页视觉通过。

所有 Qt 运行启动前显式设置并断言 `QT_QPA_PLATFORM=offscreen`，禁 pytest 插件自动加载；D component/MainWindow 使用临时 INI，安装发现仅在测试边界禁用。无 MainWindow 前台输入、全局鼠标/键盘/cursor、OS DPI、native 截图、真实 parser/backend、整库测试或存档重新解析。最终 GUI 命令只选 D 集成文件 67 项（原 43 + 新 24）与原统计导出集成 5 项；没有扩展无关布局/整库回归。另用 --noconftest 执行 15 项 Qt-free 导出。

B 后续四业务模块上区视觉、E 的真实事件/native/真实缓存/系统缩放验收与 Astra 复审尚未执行本轮 D 签收，不由 D 代替。B 本地图表事件测试归 B；D 通过公开 restore 构造图态只证明持久化与新数据渲染，不能冒称旧→新鼠标事件矩阵通过。

## 最小产品改动

- 新增私有冻结上下文 `_ChartIntent`：data 对象引用、session_key 字符串、公开捕获的纯 state、目标 scope、目标 token。state 本身原样保留，来源 scope/session/mode 不被修改，不含快照/旧数值/百分比分母；不读 B 私有 pending 或私有 widget。
- `_snapshot_data` 记录当前确认快照对应的数据对象。普通重查只有确认快照/data 身份及 save-key/source scope 一致才公开捕获；没有确认快照时沿用匹配已有 pending，避免连续重查被空页默认态覆盖。
- `_invalidate(preserve_chart_state=False)` 默认清 pending；仅 `schedule_query` 显式保留。仍 token++、停 debounce、打断旧 workers、清 snapshot/alerts/页面/动作，重建当前会话元信息和全局筛选器；pending 绑定重建后实际目标 scope/token。
- `_receive` 原 token/session/scope/closing/page-valid 门禁原样保留。合法新快照 set_snapshot 后，只有 pending 的 data identity、save-key、目标 scope 和 token 全匹配才公开 restore。跨 scope 显式 `allow_scope_change=True`，同 scope 为 False；mode 验证由 B 执行。发布 snapshot_changed 前已完成恢复；成功接收即消费 pending，过期或错误 scope ready/failed 不消费当前记录。
- 当前失败、clear/set_session、换 save-key、同 key 新 data 对象、close 仍默认清 pending；不把旧图态带到新存档。LatestInfoTask、原取消/关闭、阈值/开关 setter、copy/menu/PNG/XLSX/原工作簿可用性与保存对话框守卫未改。

最终 B 合同已亲读并核对：capture 返回独立纯字典，scope 来源于确认 snapshot；无 snapshot 时返回同会话意图复制；restore 默认严格 session/scope，True 只放宽同 session scope；structure/ranking/line_share，两后者 mode 可为真实规范制式。无历史 API 落差待确认，不向用户再问权限。

## 测试改动及真实渲染证据

新增 9 个函数、24 个参数化用例：六组两图独立图态普通 refresh；阈值/关/开三项；连续 pending；四种公司切换图态；ranking/line_share 失效 mode 两项；连续范围及旧 ready/failed；错误 scope ready；三类会话更替；clear/失败/close 三项。

公开 restore spy 调用实际 B restore，未替换渲染。跨公司 scope 检查捕获的来源 state 完全原样传回且显式 True。另从真实卡片公开 visible_share_rows/visible_ranking_rows 核对选 p2 后仅有 `p2|bus|1`：客流 `200 人次`、班次 `8 班`、线路占比 `100.0%`，不会留下旧范围两行与66.7%/33.3%。同时检查原 snapshot 失效、导出动作禁用、新 snapshot 对象、snapshot_changed 发布时已恢复状态。

第一轮完整集成实际 **4 failed, 63 passed in 29.19s**：唯一失败是四种真实工作簿可用性组合仍用旧菜单文字“线路 XLSX/公司 XLSX”查找 QAction，实际 B 已统一“导出线路 XLSX/导出公司 XLSX”；按钮状态全部符合预期。仅适配本测试两处文字，保留真实源文件/目录、按钮/menu 同步、换范围与换存档禁用检查。没有为通过测试修改 B 或删断言。后续 72 项全部通过，包含加强的实际图表行检查。

## 实际命令、退出与日志

解释器统一：`C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe -X utf8`。工作区如顶部。GUI 设置 `QT_QPA_PLATFORM=offscreen`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`；入口代码先 assert offscreen 再调用 `pytest.main(args)`。精确参数/退出/日志亦记录在 `task-D-revision-commands.json`。

|阶段|pytest args|实际结果|日志|
|---|---|---|---|
|正常需求 RED|`-q src/test_latest_info_integration.py -k component_revision`|18 failed, 6 passed, 43 deselected；exit 1|task-D-revision-red.log|
|同集合 GREEN|同上|24 passed, 43 deselected；exit 0|task-D-revision-green.log|
|首次受影响集成|`-q src/test_latest_info_integration.py`|4 failed, 63 passed；exit 1；旧文字断言|task-D-revision-integration-first.log|
|最终受影响 GUI|`-q src/test_latest_info_integration.py src/test_stats_integration.py`|72 passed；exit 0|task-D-revision-final-gui.log|
|纯分享/XLSX导出|`--noconftest -q src/test_latest_info_exports.py`|15 passed；exit 0|task-D-revision-pure-export.log|
|静态语法/保护方法/补丁|`task-D-revision-verify.py`（不导入产品或 Qt）|两文件语法、18 方法及 receive 门禁 AST 一致；exit 0|task-D-revision-integrity.log|

最早24项 GREEN在补强真实行检查之前；补强后24项随完整集成首次63项通过及最终72项通过。未把未跑的状态/视觉回归记为通过，也不重跑无关整库。

## 精确交付与指纹

- `task-D-revision-controller.patch`：相对修订前实际 controller 的最小产品 diff。
- `task-D-revision-tests.patch`：相对上一轮 D 测试最终源的新增24项/实际行检查/两处文本适配 diff。生成前将43项基线重建并验证其 SHA256 精确等于独立记录 `9BB0EE450404D561B3AB766B3F982876FD75309F7D70981F8752D114C4532ABA`，未以猜测基线出 patch。
- `task-D-revision-integrity.json`：两源 SHA256、18 方法原样及 receive 令牌/会话/范围/closing 门禁 AST 原样。`task-D-revision-protected-before.json` / `task-D-revision-protected-after.json`：B4+A/C+exporter+shared14源全数不变。cached diff 为空；指定源 diff --check exit 0。
- controller 最终 SHA256：`655388A81CBF82D2130485F3FD5A3BF8FDBF46BA78F23C20AA60C1E1A8294B13`。
- 集成测试最终 SHA256：`944CEBED09BD4D66B1D63FCD17B9E2FD0BCF2A28E683A360D750EC4592EF53FC`。

B frozen page SHA256 `23FFC47E1797C72E7B9C6654BA2BBA4A51A2DA5E4B7AF7C961F9DA3122501640`、charts `802AAE44EA1B26574CCD82DB24C117A42C70B930D3341E577F4F7A1EF129EC2D` 在 D 退出后的保护检查时均一致。父随后将窗口交 B 四业务模块视觉，B 自有文件之后可依法变更，此记录不是未来视觉版已测声明。父此前刷新7项 peer 依赖仍不是 D 交付，不复制整棵 worktree。

所有 D Qt 测试及各 subprocess 已返回退出，未再启动 Qt；父已在交接前复查无 Python/Qt 并正式将窗口交 B 后续视觉，D 不再启动 Qt 或改产品。确认与释放记录见 `task-D-revision-slot-release.json`；D 等待必要修复转交，不主动联系其他聊天。历史共享 patch 仍未 apply，本轮仅交付两个 revision patches，不扩大到主树合并。
