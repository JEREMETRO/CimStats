# 架构与模块边界

CimStats 是 Python 3.12、PySide6 与 PySide6-Fluent-Widgets 桌面应用。保留现有模块边界，不为文档整理改写目录、业务或构建入口。

## 数据流

```text
.save -> 容器解压 -> 隔离运行时解析 -> 对象与历史数据
      -> 公司／网络／城市／最新信息模型 -> 查询快照
      -> 桌面展示、图表、XLSX／PNG 导出
```

- [save_container.py](../../src/save_container.py)定位负载；[extract_runtime_data.py](../../src/extract_runtime_data.py)加载解析用运行时。存档及原程序集不原地修改。
- [history_contract.py](../../src/history_contract.py)定义历史窗口和观测契约；[statistics_model.py](../../src/statistics_model.py)、[network_model.py](../../src/network_model.py)、[city_model.py](../../src/city_model.py)、[latest_info_model.py](../../src/latest_info_model.py)承担业务聚合。
- [statistics_page.py](../../frontend/statistics_page.py)协调筛选、模式与快照；[company_dashboard.py](../../frontend/company_dashboard.py)、[network_dashboard.py](../../frontend/network_dashboard.py)、[city_dashboard.py](../../frontend/city_dashboard.py)负责呈现，不重算另一套分母。
- [chart_canvas.py](../../frontend/chart_canvas.py)是共享绘图入口；[stats_charts.py](../../frontend/stats_charts.py)、[network_charts.py](../../frontend/network_charts.py)、[chart_details.py](../../frontend/chart_details.py)提供图卡、身份图例与放大详情。不得把已替换的 QtCharts 或外部 Pro 控件写成依赖。
- 导出读取展示所用查询快照；分类显隐、悬停和放大不改变业务值。过期异步任务不得覆盖最新快照。
- 静态 PNG 渲染完整快照时暂时禁用透明效果，避免永久／过渡透明宿主使图形缺失或淡化；完成或失败后恢复原启用状态，不修改界面动效策略。
- 统计页面将存档当前规范化线路的副本随网络模型任务传递；模型仅对所选公司的理论最大需求求和，并在快照中记录当前值上下文。需求摘要与历史平均车辆图分开取值，当前需求不构造历史比较，导出直接读取该快照。

## 共享界面与布局

- [app_shell.py](../../frontend/app_shell.py)统一导航、页面标题、文件区和子选项卡；[ui_kit.py](../../frontend/ui_kit.py)、[stats_controls.py](../../frontend/stats_controls.py)统一控件。
- [stats_tokens.py](../../frontend/stats_tokens.py)和[stats_typography.py](../../frontend/stats_typography.py)是颜色、尺寸及字体入口，不复制局部主题。
- [startup_surface.py](../../frontend/startup_surface.py)提供主窗口初始 Logo 遮罩与欢迎层共用的窗口预算、背景及标志坐标，不导入 Fluent 或业务模块。[startup_welcome.py](../../frontend/startup_welcome.py)在中央窗口覆盖导航和页面顶栏，负责首次打开入口与标志上移动效；`app_shell.py` 的正常页面顶栏保持独立。
- [startup_bootstrap.py](../../frontend/startup_bootstrap.py)先创建轻量主窗口，在[首帧门控](../../frontend/startup_readiness.py)确认 Logo 遮罩完成绘制后才调用 `initialize_content_async()`。后台准备依赖与类定义，主题和全部控件仍在主线程按事件回合构建；Logo 遮罩保持覆盖至所有页面就绪，再在欢迎层首帧绘制后启动过渡。构建期间仅窗口系统按钮可操作，业务输入和拖放在就绪后启用。同一原生窗口从 Logo 持续到欢迎与业务页面；正常启动不运行独立 helper。不透明子表面可能使 Qt 省略外层窗口绘制事件，门控必须覆盖这一分支。[启动传输](../../frontend/startup_transport.py)仅保留兼容诊断入口的鉴权与回收。解析与图表准备覆盖欢迎层，成功准备后显示页面，失败或取消返回欢迎层；取消后已经排队的完成结果不得重新载入。
- [window_chrome.py](../../frontend/window_chrome.py)复用现有无边框 Windows 窗口层提供共享自绘标题栏、系统移动／缩放与应用文件选择入口。仅导入存档使用 Windows 原生打开文件对话框，其系统外观是应用自有窗口标题栏规则的例外；其他应用自有窗口继续共享自绘标题栏。主窗口标题只有应用名称并显示应用图标；独立二级窗口隔离默认图标继承。已有 Fluent 遮罩弹层与菜单、工具提示保持原有形态。
- 统计页固定标题／文件操作、子选项卡、筛选；数据区共用一条纵向滚动，不为各公司另设滚动条，不产生整页横向滚动。
- 默认与同期各公司分组；多公司比较公共图。公司数量不改变模式。公司单栏四个指标图位固定，宽屏双公司对应行对齐，窄屏重排而不丢数据。
- 分析模式能力依据存档有效公司身份判断，单公司替换时清理失效的多公司模式；勾选数量只决定查询范围。共享画布在每种绘制路径按紧凑／放大身份控制数字数据标签；仅首页“客流结构”“班次结构”分布图允许小图常驻数量，其他小图不能由单系列或足够空间绕过禁标签规则。
- 内容宽度与显示预算由布局控制，不能用固定最大高度裁掉数据。摘要折叠必须释放真实绘图区高度；普通 resize 不重建整个图控件或反复查询。

## 文件与输出

源码入口 `CIM2_SaveStats.py` 和兼容的 `CIM2_*` 名称继续有效，产品显示名为 CimStats。`data/`、`game_runtime/Managed/`保留构建与解析依赖；`exports/`仅跟踪复用的目录数据。真实存档、解析中间文件、截图和构建产物放在忽略的 `jobs/`、`build/`、`dist/`，不成为文档树的一部分。

构建和验证见[开发说明](../DEVELOPMENT.md)、[发布说明](../RELEASE.md)及[验收清单](../testing/acceptance.md)。
