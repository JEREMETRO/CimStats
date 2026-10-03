# 包B交付：页面与分类图完成，offscreen组件槽已释放

工作区：`D:/test/CIM2_SaveStats/.worktrees/latest-info`。本报告记录包B组件阶段，不代表应用外壳集成或原生整窗验收。

## E审查P2修复与本次槽释放

父核对确认的E-B-01/E-B-02均已修复，仅改本包三份源码。排行先剔除对应字段的None、NaN及无穷值，再排序和取最多十条；真实0保留，不用缺测补足十条。全缺测显示“当前范围暂无有效排行数据”，不产生编号行。综合客流仍消费A的passenger_top10，制式客流及综合/制式班次使用真实lines。

set_session模拟时间采用与A一致的来源优先级：simulation_time优先；缺少该值时组合metadata当前日期和当前时间，日期存在而时间缺少时使用00:00:00；缺少日期、只有时钟或时间无效时显示未知。不会使用现实时间，也不会因解析异常中断载入。

新增18项参数化回归先得到真实RED：17 failed、1 passed、30 deselected（唯一通过项为有效simulation_time对照），actualexit=1；排行修复后9 passed、39 deselected，actualexit=0；时间修复后9 passed、39 deselected，actualexit=0。最后按下述严格offscreen命令跑全部B回归：**48 passed in 7.44s，actualexit=0**。所有测试进程正常退出，本次B组件槽已释放给父/D，源码和测试冻结；没有继续启动Qt或扩大验证范围。

父已通知C完成103项定向回归并正常退出，包含真实提醒面板挂载；这是C交付证据，本包没有重跑C。B本次修复后的实际外壳与整窗验证仍待D/E。

本次三份源码SHA256：

- latest_info_page.py：`af114b49d09d3f83496c878e03185136920733c7ce41c68e676fe955df227eb6`
- latest_info_charts.py：`908f09f7d63a17263aad0e1d86d421dc37b66740376fb7008190c788561807c2`
- test_latest_info_page.py：`24d3a723f13816faf48a27efa567b862ad14234bc9622d578e992fc7e8a57991`

下文组件图片、几何和metadata JSON属于此前30项通过时的视觉基线，保留原始文件及哈希，未重拍。此次修复未改布局，旧图不作为新源码截图证据。

## D后续集成扩展的归属

父通知E已独立关闭E-B-01/E-B-02，并将新增`set_workbook_availability(line_available, company_available)`接口、相关`_set_actions`与session清理及受影响动作测试的有限维护权交给D。该后续扩展由D先行为RED、最小修改再执行B回归，验证与交付证据归D集成包；B不再修改源码、测试或启动Qt。

本报告顶部三份哈希仅对应B两项P2修复后48项通过的冻结版本。D后来修改产生的哈希与回归结果应记在D交付中，不能替换上述B版本或归入本次B测试证据。D维护范围不包含B时间、布局或图表。

## 交付文件与边界

- `frontend/latest_info_page.py`：最新信息页面、主区城市Hero、4核心+9辅助指标、4完整亮点、三图、260px提醒接口、范围/动作信号及响应式。
- `frontend/latest_info_charts.py`：真实线路Top10、班次环图/完整制式列表、制式钻取、综合排行/返回、真实线路身份动作。
- `src/test_latest_info_page.py`：最终48个组件用例。
- 本报告及同目录4张组件PNG、`task-B-component-metadata.json`。

只修改上述包B文件/产物；共享token/control/elevation/motion/ChartPanel和应用外壳保持只读。本包没有stage/commit、没有派代理或聊天、没有跨聊天发送消息。报告替换了旧“仍hold/未实现”状态。

## 冻结接口

`LatestInfoPage(settings=None,parent=None)`；`set_session(data)`只读取元数据/公司/制式并清旧快照，不调用模型计算；`set_snapshot(snapshot)`消费A实际dataclass；`clear_session()`、`scope()`、`set_alert_panel(panel)`、`export_target()`均已实现。公开`company_combo`、`mode_combo`和冻结七个信号：scope_changed、open_save_requested、line_requested、share_requested、report_requested、line_export_requested、company_export_requested。

D先调用set_session再交当前快照；B拒绝不同session_key或不同scope的快照，并在清空后拒绝旧结果。相同key重复导入的异步generation仍由D的worker token负责。打开存档始终可用；无有效快照时四个生产动作及更多菜单动作禁用。窄窗更多菜单保留全部动作。线路动作传真实LineSummary.key，不按显示名查线路。

Hero文件名在set_session阶段优先真实save_path basename，使用PureWindowsPath兼容正/反分隔符；其次明确save_name；不使用tag/运行时标签冒充文件名。城市日期/星期12px、HH:MM:SS时钟21px分列；完整模拟时间保留tooltip和accessibleName；人口21px与紧邻12px“人”单位分开。缺名/缺时间/缺人口准确显示未知或“—”。

## 1440×960设计预算与实际组件几何

现有整窗扣除经验为可见框1440×960约客户1436×900，展开导航192、左右20，内容约1204×860。本包按更保守1200×852组件测试；父D需隐藏首页旧外部header，避免重复占位。该扣除是布局依据，不是本包原生测量。

最终实测offscreen、DPR=1.0、组件与board都是1200×852，纵向滚动maximum=0，未发现可见文字字高裁切。主区928，间隔12，右栏260。以下几何均相对于实际组件：

| 区域 | x,y,w,h | 内容 |
|---|---|---|
| 标题/动作 | 0,0,1200,56 | 最新信息；开存档primary；XLSX/分享/报告次操作 |
| 城市Hero | 0,64,928,88 | 城市29px；日期/星期12；秒级时钟21；人口21/人12；存档 |
| 范围 | 0,160,928,36 | 稳定公司ID/完整制式/口径 |
| 四核心 | 首卡0,204,226,70 | 线路数、车辆、周收入、利润同排 |
| 九辅助 | 首卡0,282,179,58 | 五列两行5+4；仍21主值/12标题及单位 |
| 四亮点 | 首卡0,414,226,144 | 名称及客流/班次/单班人次/车公里人次全部保留 |
| 今日趋势 | 0,566,255,270 | 共享ChartPanel子类，保留原Result/曲线/tooltip |
| 客流Top10 | 263,566,383,270 | 给十条完整排行更多宽度 |
| 班次结构 | 654,566,274,270 | 左环图84×78；右完整六制式168×120 |
| 提醒接口 | 940,64,260,788 | 专供C真实提醒面板 |

主内容设计总高836，留16px余量。城市Hero是主区顶部全宽入口，未放进提醒右栏。三卡底部同排，Top10宽于另外两卡。班次环图实际位置663,676,84,78；制式行0为751,655,168,20，行5为751,755,168,20，全部名称/计数/占比可见。极大总数或右侧字段超宽时，该卡局部切回上下布局，不缩字号、不删分类；155000总数移到环图旁维持21px。

窄窗680×580实测board680×2020，滚动maximum1440，全部指标/最后排行/制式保留，无可见文字字高裁切；右栏移到主内容后，图卡纵向堆叠，Hero重排为148px。长线路身份完整存储于Qt文本、tooltip和accessibleName，绘制可省略；不删除第十条。原生125%缩放/真实外壳尚未验证。

## 图表与提醒接线说明

趋势使用TodayTrendPanel(ChartPanel)。仅覆写共享小时标签格式hook：同一天在紧凑横轴显示HH:MM，完整日期在Hero及共享tooltip中；不修改Result、时间范围、小时缺测、点值、共享图表源或其他页接口。缺小时保留None/断线，实际0保留。父预审指出的`__selected__`仅在传入公司名映射中别名为“所选公司合计”，数据身份不变；单公司名称来自snapshot.companies。

Top10只消费真实LineSummary/ModeCount，不制造时间序列。默认最多十条真实记录，不足十条如实显示；模式选择钻取实际lines并返回综合。班次默认左环图+右六制式完整列表，列表显示真实计数/总数/占比；非正/缺测值不产生可点击扇区。环/分类行钻取及班次Top10/返回入口均可达。点击测试直接发送局部QMouseEvent，不使用全局鼠标/焦点操作。

set_alert_panel只挂载C的QWidget，替换旧panel时隐藏/移除旧panel；范围变化、载入新存档、clear_session调用已挂载panel的公开clear_session。此前组件图使用准确“未载入可比数据”空态，无示例报警。C后续已完成真实面板挂载定向回归；本次B修复后的整窗260px容量仍待D/E复核。

## RED/GREEN与实际验证

初期hold阶段：仅AST及--collect-only --noconftest，先14后17个用例，不启动Qt。

父明确放行严格offscreen后：

1. 未建页面时17个setup报ModuleNotFoundError，准确记录为入口缺失，不把它当行为RED。
2. 最小可实例化页面建立后，17个用例真实FAIL：缺Hero/指标/图卡/动作及清空行为；再实现GUI。
3. 首轮16pass/1fail定位动态排行行需等事件循环显示，显式show修正即时可见状态。
4. 合计身份别名用例先RED KeyError再GREEN。
5. 组件图发现数值/占比越界，新增几何回归RED；定位FullLabel的Ignored策略使固定宽数字列占位为零，固定列改Fixed策略后GREEN；脚注字高也修正。
6. 小时轴可读格式先RED再GREEN；大班次总数不覆盖环图先RED再GREEN。
7. 父Hero预审：真实存档路径优先/不可用tag以及秒级分区用例先4fail/1pass，再实现并GREEN；人口单位连接几何先RED再GREEN。
8. 父最后班次布局预审：环图左/完整列表右几何先RED，再局部重排并GREEN。
9. 上一存档/范围结果拒绝、窄窗更多菜单、非正/缺测环图局部点击等追加边界回归初始已通过；未虚称每个后加覆盖都经历新实现RED。

完整本包命令（首次交付30项、本次P2修复后48项使用相同命令）：
`QT_QPA_PLATFORM=offscreen CIM2_REDUCED_MOTION=1 ...Python312/python.exe -X utf8 -m pytest -p no:cacheprovider -q src/test_latest_info_page.py --tb=short`
首次交付结果：**30 passed in 5.15s；actualexit=0**；本次最终结果见报告顶部：**48 passed in 7.44s；actualexit=0**。每测临时INI QSettings；创建页面前assert platformName为offscreen。测试/渲染进程都正常退出，无仍运行的Qt进程；**本次包B组件槽已释放给父/D**。

没有MainWindow、真实桌面/native HWND、QCursor.setPos、QtTest.mouseMove、全局键鼠/焦点或系统DPI操作；没有读取真实QSettings。减少动画通过隔离进程环境控制。渲染使用共享initialize_theme，其theme API默认save=False，已只读确认；不会持久化真实设置。

三份源码最终AST和逐行尾空白检查通过。一次合并命令中pytest24pass后，升级权限子进程的git diff --check因Not a git repository退出1，未当作成功证据；普通受限子进程git status可读。本包后续测试用独立命令明确打印actualexit=0，源码格式检查改为直接读取实际三文件。没有为校验操作Git索引。按父限制未跑全库；全套及原生验收归D/E。

## 产物真实性和后续条件

同报告目录的`task-B-component-wide.png`、`task-B-component-narrow.png`、`task-B-component-empty.png`、`task-B-component-large-total.png`均由此前实际offscreen QWidget.grab生成，已查看；使用明确容量fixture，不是存档/原生截图证据。fixture有十个长名字、六制式、955人次、155班，公交34/155=21.9%，缺测与真实0保留；大数场景独立为155000。元数据JSON保留首次交付源码SHA256、平台、DPR、组件几何、宽窄滚动、文字检查及正常退出码；本次P2修复源码哈希见顶部，未覆盖旧图片元数据。

本包自审已检查冻结接口、字段完整性、真实身份、动作禁用、重入/旧结果、分类正值与布局、字号、文件名和秒级时间；遵守本包禁止再派代理，独立审查仍由父/E承担。无声修改共享源或删失败测试均未发生。

后续必须由D接入实际应用外壳、动作/导出和C提醒；C真实挂载定向组件验证已完成，本次B修复后的整窗容量、真实数据/全库回归、原生1440×960、125%实际缩放、导航开合及共享全屏图操作待D/E确认。这里不宣称这些已通过，不发布或替换EXE。
