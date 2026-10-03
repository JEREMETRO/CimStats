# E 第二轮控制器限定静态审查

结论：在本次冻结控制器、24项revision测试及已交付公开图态合同范围内，未发现需要修复的问题。未启动Qt、执行pytest或导入产品；不代表真实事件、异步运行或整窗验收通过。

## 版本与独立检查

| 文件 | 本次实读SHA256（与父提供一致） |
|---|---|
| frontend/latest_info_controller.py | 655388a81cbf82d2130485f3fd5a3bf8fdbf46ba78f23c20aa60c1e1a8294b13 |
| src/test_latest_info_integration.py | 944cebed09bd4d66b1d63fcd17b9e2fd0bcf2a28e683a360d750ec4592ef53fc |

标准库AST检查实际exit0，记录于`task-E-rev2-D-static-review.json`：仅4个既有controller方法改变，新增_remember_chart_intent；16个其余方法及LatestInfoTask原样；_receive前4个语句含原token/会话/scope门禁原样。revision为9个函数、24个参数化用例，系源码计数，未执行。检查前后两源及D修订前参照字节一致，无Qt模块导入。

## 状态链审查

| 项目 | 源码证据与覆盖 |
|---|---|
| data对象与saveKey | :90–102仅接受同data对象及同会话pending；确认快照还要求_snapshot_data同对象、snapshot与捕获state同saveKey。:135–145换会话先clear；测试:818覆盖新key、同key新对象、同对象新key。 |
| sourceScope | :97–102捕获state.scope须等于确认snapshot的公司/mode；保留原state，不将其改写为目标scope。测试:738的restore spy原样转调真实restore，断言来源state完整且显式True。 |
| targetScope与token | :104–123先递增token、停止计时器并中断旧worker、清旧数据，再将intent绑定重建筛选器后的实际scope和新token。:185–188恢复时再次同时核对data、saveKey、targetScope、token。 |
| 连续pending | 无确认snapshot时保留身份匹配的已有intent，不从空页重新捕获默认态；每次invalidate重绑最新目标。测试:724三次refresh、:787连续p1/p2范围切换。 |
| 旧ready/failed | :175–179在消费pending之前拒绝旧token、旧会话、错误scope、closing或失效页。_failed原样先核对token；旧失败不invalidate。测试:787旧ready/failed、:806当前token错误scope不吞pending。 |
| 不恢复旧数值 | intent保存公开纯state，不保存snapshot或数值。:181–188先安装合法新snapshot，再恢复视图意图；完成后才发布snapshot_changed。测试:738核对p2唯一真实key、200人次/8班/100.0%，不是旧范围两行或旧占比。 |
| refresh/阈值/开关/同会话范围 | 只有schedule_query显式preserve=True，阈值/开关沿原方法进入此路径。同scope恢复False，跨scope恢复True，失效图内mode按公开合同由B单卡清除。测试:685六种双图组合、:704三种提醒重查、:738四种公司切换、:770两种失效mode。 |
| 新会话/当前失败/clear/close | _failed、clear_session默认invalidate不保留；set_session先clear，stop_workers先closing再clear。测试:818三类会话替换、:836清空/当前失败/关闭；原:494另覆盖旧失败忽略及当前失败清快照。 |

B的公开capture/restore语义引用已交付`task-B-revision-report.md`；未读取或执行B当前活动页面/图表源。D的72项Qt及15项纯导出结果是作者证据，本次未重跑。最后B视觉修订后的真实事件、信号投递、重绘、整窗及缩放仍由E获得独占槽后验证。

本次仅写E审查证据/报告及更新E待验状态；产品只读，不联系或写入D，不启动Qt。B现持视觉实施/Qt槽，E等待父正式转交。
