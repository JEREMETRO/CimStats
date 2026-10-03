# 共享接口与文件归属（实施基线）

必须先读P1、P2、REVISION。不得根据旧P2的high/xhigh执行，全部medium。不得生成agent或额外会话。针对负责范围先写行为测试再实现，提交自己文件。

## A: 数据（src/dashboard_model.py, src/statistics_model.py, src/test_dashboard_model.py, docs/CIM2_统计中心指标口径.md）

复用statistics_model Query/Result/Bucket/HistoryStore/Alert。
在dashboard_model.py提供：
- FilterState(companies:tuple[str,...], start:datetime,end:datetime,grain:str='day',comparison:tuple[datetime,datetime]|None=None)，冻结dataclass。
- DashboardResult(filters:FilterState, results:dict[str,Result], breakdowns:dict[str,Result], alerts:list[Alert])。
- build_dashboard(store:HistoryStore, filters:FilterState, thresholds:tuple=(5,20,100), cancelled=None)->DashboardResult。
- default_window(simulation_time)->tuple[datetime,datetime]，到当日00:00不含当天、前7日。
results包含所有BOARDS metric（city-mode-share也包含）及transfer-coefficient；可合并指标用group='__total__'；NO_GROUP_TOTAL保持group=None分组。breakdowns包含全部metric的group=None原分类数据，供客流/站点/城市bar/pie展示。公司空选择时不得误解释为全选：公司结果为空，城市照常。
transfer-coefficient注册METRICS/BOARDS且HistoryStore.query可用，与Result一致；Bucket保留分子分母、完整度、raw；summarize_buckets正确聚合系数。不得改变既有指标单位和合法负值。alerts跨四看板去重生成，不为系数生成好坏评价。查询检查取消。提供测试。

## B: 外框和页面（frontend/desktop_app.py, frontend/statistics_page.py, frontend/stats_style.py, src/test_stats_shell.py）

重写StatisticsPage，保持构造(settings=None,parent=None)、set_session(data)、clear_session()、stop_workers()给desktop_app调用；保留所有其他页业务。引用A接口和C组件；依赖未合并时用contracts写代码，不等待、不实现重复接口。
data已有history/simulation_time/companies，companies含公司标识/公司名称。新增save_key由root接入真实文件内容指纹。页面属性：snapshot:DashboardResult|None、board_host:QWidget（完整四看板容器）、alerts_host:QWidget（D占位）、export_button:QPushButton、alert_toggle:QCheckBox、thresholds tuple、session_key str。信号snapshot_changed=Signal(object)，export_requested=Signal()。root接入D。
工具区公司多选用弹出菜单避免大列表；grain、start_edit/end_edit、compare_combo、compare_start/end、settings_button、alert_toggle/export_button。外框负责open、当前存档。所有控制随窄窗换行。页面worker后台build_dashboard，token防止旧响应。结果更新发snapshot_changed；export点击发export_requested。提供set_thresholds(tuple)重查与preference QSettings。阈值弹窗可由B实现，保留已有三阈值默认5/20/100。
ChartPanel接口见C。公司六卡（满意度三切换）和最多三个选择的趋势；服务五卡+linecount趋势+stopcount分类；客流三ChartPanel独立mode选择+系数卡及趋势；城市卡+选择趋势+方式bar+密度分组。指标卡按公司值分开，名称长时换行。布局不可固定整个页面最小高度。旧statistics_page测试由root改为新行为测试，不为兼容旧UI保留隐藏表格。

## C: 图表（frontend/stats_charts.py, src/test_stats_charts.py）

ChartPanel(title:str, modes:bool=False, default_mode:str='line', settings=None, settings_key:str='', parent=None)。属性mode_combo（当modes=True）；方法set_result(result:Result|None, companies:dict[str,str]|None=None), set_mode(mode:str), clear()。模式summary/bar/line/pie/trend-bar；选择按钮仅summary/bar/line/pie中文。summary仅每公司大数字，bar按类别汇总横条，line按bucket.start时间线，trend-bar时间柱。每公司pie分别显示。城市mode-share是3比率，不归一，用bar。
可添加set_axis_range(lower,upper,step)给同量纲图对齐；稳定公司颜色company_color(company_id)不随选择变化；分类配色稳定，每公司小图保证类别色一致。legend可点击但不更改原Result，切换保留真实总量。tooltip只对象/时间/指标/数值/单位。缺失折线断开，不能补零或连接缺口。
nice_axis(values)->AxisSpec(lower,upper,step,scale=1,unit_suffix='')；轴整数、0锚、负值支持、缩放后整数；QtCharts均复用。实际值精度保留。时间tick适配宽度避免挤压。ChartPanel尽量sizeHint合理，可垂直扩展，窄窗图例换行或明确独立区域不叠图。

## D: 后续接口（frontend/stats_exports.py, frontend/stats_alerts.py及各自测试）

先不执行，基于稳定集成分支。读取DashboardResult，独立AlertsPanel.set_snapshot(snapshot,session_key,companies)和持久化已读。export_xlsx(snapshot,path,companies)；export_png(board_host,path)完整区域非viewport。root接线，不改B文件。

## Root独占

frontend/stats_text.py集中显示词典、共享入口接线、src/test_statistics_page.py旧测试替换、集成验证脚本、版本/发布文档/计划矩阵。不在A/B/C并行期改它们拥有文件。代码整合后root完整复核。

## 依赖检查

|生产者→消费者|共享内容|裁定|
|A→B/C/D|Result及DashboardResult|复用既有模型，新增接口如上，A拥有定义|
|B→D|snapshot_changed、host、session_key|root接线，D不改页面|
|C→B|ChartPanel|构造参数及set_result按本契约|
|Root→B/C/D|stats_text|按需通过root追加，不自行加解释|
|A/B/C自身|测试与实现|各自只改负责文件，需求覆盖完整|

SDK/model选择以当前工具可用清单为准，不研究价格或调用web，不重复调查已核实字段。
