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

## 共享界面与布局

- [app_shell.py](../../frontend/app_shell.py)统一导航、页面标题、文件区和子选项卡；[ui_kit.py](../../frontend/ui_kit.py)、[stats_controls.py](../../frontend/stats_controls.py)统一控件。
- [stats_tokens.py](../../frontend/stats_tokens.py)和[stats_typography.py](../../frontend/stats_typography.py)是颜色、尺寸及字体入口，不复制局部主题。
- 统计页固定标题／文件操作、子选项卡、筛选；数据区共用一条纵向滚动，不为各公司另设滚动条，不产生整页横向滚动。
- 默认与同期各公司分组；多公司比较公共图。公司数量不改变模式。公司单栏四个指标图位固定，宽屏双公司对应行对齐，窄屏重排而不丢数据。
- 内容宽度与显示预算由布局控制，不能用固定最大高度裁掉数据。摘要折叠必须释放真实绘图区高度；普通 resize 不重建整个图控件或反复查询。

## 文件与输出

源码入口 `CIM2_SaveStats.py` 和兼容的 `CIM2_*` 名称继续有效，产品显示名为 CimStats。`data/`、`game_runtime/Managed/`保留构建与解析依赖；`exports/`仅跟踪复用的目录数据。真实存档、解析中间文件、截图和构建产物放在忽略的 `jobs/`、`build/`、`dist/`，不成为文档树的一部分。

构建和验证见[开发说明](../DEVELOPMENT.md)、[发布说明](../RELEASE.md)及[验收清单](../testing/acceptance.md)。
