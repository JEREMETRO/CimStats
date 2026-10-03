# 主工程图表集成复核

2026-10-02。图表范围可以冻结：主工程定向回归 171 passed / 0 failed（44.49s），加载实际主工程源码的补充回归 236 passed / 0 failed（4.71s），真实51282条记录的71个场景无跳过、无失败。没有待解决的图表阻塞项。本结论限于图表集成，不代替整个发布包的验收。

## 主工程文件与最终 SHA-256

实际路径根为 `D:/test/CIM2_SaveStats`。集成前文件保存在本目录 `before/frontend`；不是覆盖主工程整个分支。原候选补丁 SHA-256 为 `ab3e8f8c2f3aa7a23f2d1b47957fd645828d1a7c08ff96f2a1809fe88fdf1743`，历史候选保留不变。集成后另有预算兼容、单列高度释放和隐藏表性能三项修正，因此冻结必须以以下主工程哈希为准。

| 文件 | 最终 SHA-256 |
| --- | --- |
| `frontend/chart_details.py` | `7369e5240ec906c9f22363dbb557ca877071ec5824017daf6d9a44a9f0e606fa` |
| `frontend/stats_charts.py` | `c717ec5964bc3db8e0be1b23611fcc5a0c96298852e5d4ee813d6beec15e139d` |
| `frontend/fluent_chart_view.py` | `e561239eb3fcc2142457661589e6980acd587c2bc45c90fe62d65fb2a942191d` |
| `frontend/network_charts.py` | `ca7cd0c1196e67feb74bc80db62e8c85cc9ec7ede62adc580984eb92c265c559` |
| `frontend/company_dashboard.py` | `ccbf7aa73f4826aeaee7e8d97af9036f6c463400c7ab017a55471cbeaf575306` |
| `frontend/statistics_page.py` | `d4c1d7942cbed0d627691c9488f0959759a1e73e9725caafb16cad74c24c60cd` |

共享字体文件未改，SHA-256：`41cde0463ad76f31a62e5b51d7a9f72419708146ecf22abccfc1265dd462851b`。保留主工程共享配色、字体、motion、线宽及 pie hide_center；未改 desktop_app、启动、品牌或构建文件，未打包、上传或删除。

## 主工程原失败逐项归因

之前的 9 failed 没有用补充回归结果遮盖；全部对应原主工程用例已重新验证。

| 原失败 | 归因与处理 |
| --- | --- |
| time marks skip zero | 旧断言忽略真实零值；按最新规则核对10、-3、0三个真实点，缺失仍排除，负值悬停断言保留。 |
| title/summary Chinese font | 旧断言将强调字体也固定为微软雅黑；验证共享 Segoe Variable 字体列表及中文回退，图轴/图例中文字体原检查保留。 |
| mode labels opt in | 旧断言要求默认名称不同；更新为统一“趋势”，自定义名称及模式键行为检查保留。 |
| stopcount same category color | 旧断言要求两家公司颜色完全相同；改为类别色相保持、公司深浅不同，数量与同类别对齐检查保留。 |
| chart header metric menu | 指标菜单已按用户要求移除；改为无额外菜单且全屏动作保留。 |
| page metric menu swapping | 更新为四个固定指标、正确模式及真实数据绑定，没有恢复用户已删除的控件。 |
| overview all fonts YaHei | 集成前已有旧断言失败；允许共享强调字体与中文回退，侧栏及页面重排断言保留。 |
| narrow page ranking rows | 集成前已有旧断言失败。代码证据：StructureAnalysis默认structure视图，show_ranking才创建ranking rows；改为先验证真实制式行，再选择排行验证真实排行行，其余窄屏滚动断言保留。 |
| filter collapse mid-flight | 实际性能回归，未放宽时间断言。隐藏表ResizeToContents在布局中扫描数据；改为Interactive，showEvent才计算列宽。原105/100ms中间帧及收起/展开端点、选择和查询token断言原样通过。 |

另外关闭独立复核发现的单列旧高度预算回弹P2：clear_compact_height显式解除预算，公司/共享图两条退出路径均接入；新增default、companies两种模式往返宽窄回归。主工程 compact 页面预算与饼图文字最低高度分别保留。

所有测试文件仅作定向修改；原文件备份在 `before/src`，修改前/初次修改后/最终哈希见 `final-manifest.json`。新加隐藏表回归确认主页面布局时ValuesModel.data读取为0。

## 动画实际证据

原诊断记录：105ms等待后实际125ms，动画currentTime仅22ms，卡片仍120px；性能记录有12672次ValuesModel.data（约61ms）。修正后再次对照：重新打开旧autosize行为读取13680次，105ms等待实际172ms；延后计算读取0次，同等待实际110ms、动画currentTime59ms、卡片116px（原120px）。这些测量包含首次显示及离屏绘制，不能当作原生帧率指标；关键是去掉隐藏模型扫描并保持原时间行为测试通过。

原行为复现日志 `timing-hidden-autosize.txt` 与修正日志 `timing-deferred-autosize.txt` 含每次帧的墙钟时间/currentTime/height/min/max和性能统计。最终主工程原时间断言通过，没有免测或大幅延长等待。

## 真实数据与排版

全部现金流、客流、出行量 flow 指标开放入口在小时/日/周/月粒度均核对总量与平均粒度卡；真实零计入平均，缺失排除，部分桶不外推。城市出行量显示整体范围，两个公司指标分别显示公司卡。存量、比例和已有平均指标不增加重复均值。

大图无滚动，明细表隐藏；粗周期短区间显示全部真实数值，密集长周期保留全部柱和可选数值。柱间距共用、柱宽及字号有上限、公司深浅图例一致。饼图左右标签按扇区位置排序，测量真实文字宽高，预留两侧与底部空间，数值和百分比无色底。小图空间够时单行；大图数值13px、百分比11px分行。中心只显示加粗总数和单位，长金额无法放入圆孔时在预留底部单行完整显示。

`evidence/audit.json`记录逐场景原数值、均值、分母、碰撞、字体和源文件哈希。所有大图从主工程实际全屏入口生成，1440×960、DPR1。截图是Qt离屏渲染，不是原生桌面抓取。主控已目视检查最终饼图、分区出行量和此前现金流等代表图；独立只读审查确认预算退出和隐藏表处理无新增P1/P2。

- [companies-transport-by-group-pie / large.png](D:/test/CIM2_SaveStats/.worktrees/charts/docs/ui-redesign/root-integration/evidence/day/companies-transport-by-group-pie/large.png)：1440×960。
- [companies-transport-by-group-pie / small.png](D:/test/CIM2_SaveStats/.worktrees/charts/docs/ui-redesign/root-integration/evidence/day/companies-transport-by-group-pie/small.png)：400×356。
- [companies-trip-types-trend-bar / large.png](D:/test/CIM2_SaveStats/.worktrees/charts/docs/ui-redesign/root-integration/evidence/day/companies-trip-types-trend-bar/large.png)：1440×960。
- [trip-number / large.png](D:/test/CIM2_SaveStats/.worktrees/charts/docs/ui-redesign/root-integration/evidence/day/trip-number/large.png)：1440×960。
- [cashflow / large.png](D:/test/CIM2_SaveStats/.worktrees/charts/docs/ui-redesign/root-integration/evidence/day/cashflow/large.png)：1440×960。
- [cashflow / large.png](D:/test/CIM2_SaveStats/.worktrees/charts/docs/ui-redesign/root-integration/evidence/month/cashflow/large.png)：1440×960。

## 最终日志

- `main-regression-freeze.txt`：主工程171 passed，唯一warning为已有QFluentWidgets QHoverEvent弃用警告，未新增失败。
- `supplemental-regression-freeze.txt`：236 passed，日志明确导入D:/test/CIM2_SaveStats/frontend中的四个实际模块。
- `real-main-audit-freeze.txt`与`evidence/audit.json`：71场景，skipped=[]，failures=[]，四个源码哈希已和最终主工程核对。
- `final-manifest.json`：冻结文件、测试、截图的校验记录。

所有Qt进程均短时离屏运行并已结束，没有遗留桌面交互或后台Qt测试。
