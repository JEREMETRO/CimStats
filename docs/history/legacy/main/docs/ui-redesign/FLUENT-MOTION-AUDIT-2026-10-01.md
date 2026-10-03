# 全页面 Fluent 状态与动效审查

实施起始基线 HEAD 90e922c；共享组件提交 d185d78，城市基础 040835a、筛选和公司预算 e4cf2fb 后，网络预算与生命周期提交 5f19eef。线路、城市折叠实例保持及新图表全屏仍有其他会话的在途改动。仅三个可达主导航：公司概览、线路查询、统计数据（公司/网络/城市）。车型参数/旧导出页构造函数未接入导航，不发明设置主页面。

## 设计与所有权

用户要求复用 Fluent 原生柔和阴影且卡片不移动、不改统计业务。库 1.11.3 的 CardWidget 只有背景动画；ElevatedCardWidget 动画 pos 上移3px，DropShadowAnimation 会反复安装并清除 graphicsEffect。当前适配器继承真正的 DropShadowAnimation，使用真正的 QGraphicsDropShadowEffect，保持库默认150ms线性颜色过渡、blur38、offset(0,5)、hover黑色alpha20。动画作用于透明窗口层中的轻量圆角source，避免把实际图表重绘为阴影输入，并保留实际卡片的已有opacity effect。仅裁掉source填充与滚动viewport以外区域；没有手绘同心圈。此前自绘方案已被用户否决并替换，旧截图与62项旧运行结果不作为此方案证据。卡片geometry/margins/cursor不变；嵌套表面以最内层hover为准；减少动画/Windows客户区动画关闭立即到目标。统一接口stats_elevation.attach_card_elevation(widget, radius=8)。

城市 owner 确认不占共享文件；线路 owner 独占 desktop_app 线路方法、line_query_page 和 line_schedule_view，由 owner 接入接口。此会话只接 overview 卡片构造函数、stats_controls、stats_motion、公司/网络/统计/图卡、日期/设置对话框。

## 审查矩阵（实施与证据持续更新）

| 页面/区域 | 可见控件与当前类 | 缺失或风险 | owner | 验证状态/证据 |
|---|---|---|---|---|
| 概览 | MetricCard/ExtremeMetricCard/ChartPanel: CardWidget | 已接真实库shadow，geometry保持 | 本会话 | 前版原生hover/reverse通过；最终overview构造由线路owner集成 |
| 线路 | 详情/摘要/时刻表QFrame；Fluent TableWidget | 已接shadow；保140默认/200展开容量 | 线路owner | 本轮空详情及九张真实卡片模拟Enter阴影通过，几何不变；真实鼠标未验收 |
| 统计筛选/空态 | CardWidget、ComboBox、SwitchButton、PushButton | 卡shadow与167/250ms可逆过滤动画已接入 | 本会话/UI | 前版原生按钮真实点击往返与反转通过；UI预算在e4cf2fb |
| 公司摘要/KPI | QFrame | shadow、summary surface逐帧预算已接入 | 本会话/UI | 首轮轮询漏采失败保留；实际plotAreaChanged事件严格超过两档，最新后台复核通过，产品未改 |
| 网络摘要/KPI | QFrame | shadow、连续预算、取消460cap已接入 | 本会话 | 三模式回归通过；本轮两策略真实plotArea、实例和恢复通过 |
| 城市摘要/KPI | QFrame；CollapseMotion | 共享motion保留margins/外部effect；city owner直接resize | 城市接入、本会话共享motion | 旧失败保留；本轮两策略实例、实际plotArea、中间高度及非默认状态保持通过 |
| 全页图卡/全屏 | ChartPanel QFrame；FluentChartView | shadow/reveal已接；hover与新全屏业务归chart owner | 本会话/chart owner | 前版切图与既有全屏往返通过；新全屏尚未纳入此轮 |
| Pivot/分析分段 | Pivot、TogglePushButton组合 | 分段与route reveal遵守共享减少动画策略 | 本会话 | 回归、前版快速切页/切模式通过 |
| 菜单/多选 | RoundMenu/CheckableMenu | 复用库popup | 本会话 | 前版原生打开/关闭通过 |
| 日期范围/日历 | QDialog、Fluent DateTimeEdit、CalendarPicker | Fluent日历替换默认Qt弹层；保精确时间及半开区间 | 本会话 | 日期范围回归、前版Fluent Calendar弹层检查通过 |
| 提醒阈值设置 | QDialog、Fluent DoubleSpinBox/按钮 | 已接弹入，保参数/返回语义 | 本会话 | 前版阈值对话框打开/关闭完成；相关shell回归通过 |
| 解析/导出/错误 | LoadingOverlay ProgressRing；系统文件dialog、Fluent MessageBox | 保真实加载链；错误/确认接库对话框 | 共享、本会话定向 | 缓存加载事件心跳/原生确认通过；return与减少动画回归通过 |
| 滚动 | StatisticsScrollArea | 保Fluent overlay/touch/key及viewport裁切 | 本会话 | 裁切RED→GREEN、callback lifecycle新增回归纳入612整库记录 |

所有行需默认/选中/hover/pressed/focus/disabled/loading适用状态，连续进出、切页中断、折叠逆转、菜单开关、全屏往返；静态截图不代表动效通过。五组Qt模拟记录物理目标、逻辑window/client/viewport、DPR、实际PNG像素。原生只报告此机实际配置。最终以缓存真实单/多人为主要视觉来源；原始save/probe只读hash保全，不重复解析。

## 最新验收要求及可用证据

1. 筛选/摘要折叠逐帧扩大实际图表viewport与plotArea，取消旧高度上限；company owner已提交在途修改，network独立补齐。图表对象须保持相同，展开恢复原尺寸。
2. 三个分析模式使用同一筛选网格和物理操作锚点，comparison固定host预留；城市保持自己的语义。
3. 同一位置同一个CHEVRON_DOWN_MED按167ms收起/250ms展开旋转，可从当前角度中途反向；禁止图标替换跳变。系统减少动画直接到目标。
4. stock-library-comparison/measurements.json已刷新为库默认Linear和带坐标的QEnterEvent，进程exit0。库与adapter的alpha均0→4→13→20，blur38、offset(0,5)一致；库卡片上移3px，adapter四帧几何不变。滚动裁切回归先RED后GREEN，悬停中销毁卡片也正常退出。
5. 真实chart hit由新chart owner独占：有限真实线点、实际bar/stack矩形和pie真实count/ratio；空白/隐藏/缺失/插值不能伪造点。共享动效不改其实现。

共享组件本地提交d185d78（未推送）。最新36项定向回归exit0，含网络三模式预算、阴影裁切与效果所有权、悬停中销毁、箭头逆转、减少动画与消息返回值。网络预算先三项失败再修复通过：overall图高中间帧不变，companies/period受460上限。两份原save和probe SHA256与开始一致，probe既有修改保留且未提交。

线路view退出异常的原始证据仍待其owner对照；无坐标QEvent Enter只能列为假设。后来发现另一处确定中断缺陷：强制CollapseMotion.finish仅deleteLater，旧动画仍Running；已补animation.stop。线路owner最新联合83 passed in 72.89s、exit0，覆盖新增强制finish Running→Stopped、切页恢复、共享阴影和网络预算。此为确定修复的证据，不能推断旧退出异常已被归因。

此前原生全页运行停在同步QWidget.grab阶段，未验收通过。新脚本用屏幕捕获、每张图前Qt事件回执、20ms事件心跳和可见筛选按钮真实点击往返；同时保留stall trace与last-stage，完成新的原生运行后才能判断窗口是否正常工作。截图更换本身不证明GUI健康。该脚本输出单独时间戳目录，保存实际motion系统策略及测试override，不能把forced运行说成实际系统策略。

## 原生全页记录与待复验项

`motion-evidence/native-multi-system-1790822054/measurements.json` 保存一次完整缓存多人存档原生运行：283项记录、281通过、2失败，进程正常结束但退出码1。因此这轮不能称为整体验收通过。原生 Windows client 为1440×940逻辑像素，实际 DPR=2，PNG=2880×1880；screen逻辑1440×960、available1440×912，frame为(7,0,1440,969)。脚本默认physical_target=1920×1080、scale=1未用于原生窗口，不代表此机100%或1920×1080实测。

当轮系统客户区动画关闭，没有强制动画覆盖。2618次事件心跳，最大间隔859ms；每张图的事件回执与可见筛选按钮点击往返均通过，保留原save/probe hash。前端文件在首轮运行中轮询至结束未变，但轮询发生在导入之后，不能据此证明整个进程自启动就冻结了源代码。定点脚本已改为任何前端导入之前读取源码hash，并与退出时核对。

两项原始失败均保留：`nav-1-card-hover`测到未选中线路的空详情卡，所有样本hovered=false/level=0；仍须测真实屏幕鼠标接收控件及暴露关系，不能仅凭空态判为无效。`city-summary-plot-fill`真实plotArea从177增加至248，但在减少动画策略下发生一次view实例更换；仍须验证当前直接resize版本、强制动画中间帧，以及曲线/图例/结果/全屏/查询状态，不能把旧失败改为通过或放宽动画检查。

`qa_motion_focus.py`复验空详情与实际选中线路卡的阴影，公司/网络/城市实际plotArea在关闭动画和强制开启动画下的高度、view/result实例、展开恢复，城市非默认曲线/图例/既有全屏和后台查询状态；原存档不重新解析。后台模式使用带正确坐标的QEnterEvent/Leave，不能证明真实鼠标接收。5f19eef新增的10项生命周期回归已由线路root确认纳入下述612整库记录；已有36项与83项结果仍只说明当时对应源状态。

后续线路 owner 曾报告100%/150%/200%各69项检查、每档正常退出，并报告200%前台与hover通过；这些是此前源版本的owner报告，不能替代本轮真实输入证据。`line-evidence/final-full-pytest.log`保存整库612 passed、1条库内部deprecated QHoverEvent警告、195.80s、ACTUAL_PROCESS_EXIT_CODE=0。线路root已确认对应源及包含新增lifecycle回归。

随后用户追加“展开摘要至矩阵留白过大”等线路反馈，line view改为展开时星期独立一行、取消矩阵居中留白，并修复筛选控件宽度与浅色tooltip。69×3及612是这些追加改动之前的证据。线路root最新报告100%/150%/200%后台整窗渲染均actual exit0、sourcehashmatch、140/200全见、筛选互不重叠、字段按钮宽度及浅色tooltip核验完成；这属于后台渲染证据，真实鼠标缺口仍在。

## 首轮后台定点结果（原始失败保留）

`motion-evidence/focus-True-1790843960/measurements.json`保存已获得独占Qt窗口后的一次后台定点：45项，44通过，唯一失败`company-animated`，进程正常结束、实际退出码1。因此不能称为整体验收通过。HEAD导入前与结束均为`5f19eeff6eb65443536588deb626bd854f01831f`；前端与非测试src源码在任何前端导入之前取hash，结束无变动。原save/probe hash保全，未调用原始解析。窗口client1440×900、DPR1、frame(540,314,1440,958)，屏幕WinDisc2880×1920。785次心跳，最大间隔516ms。

空详情和选中真实多人公交201线路的九张卡片均通过模拟Enter阴影检查：库shadow到目标，卡片外像素变化，geometry不变。这证明组件与背景窗口绘制，不能把`receiver=null`、`actual_pointer_observed=false`改判为原生鼠标通过。InputDesktop读取失败error5，foreground HWND为0；记录`actual-native-pointer-and-foreground-unverified`，`acceptance_complete=false`。

网络和城市在关闭动画及强制动画下，真实plotArea增长、view/result实例保持、展开恢复、查询token/worker/timer/snapshot保持均通过。网络强制时间序列第一图卡高263→291→311，plotArea174.5→202.5→222.5；城市图卡高247→284→317，plotArea158.5→195.5→228.5。城市折叠前后保留line模式、BlueCollar曲线及隐藏“步行”图例；既有全屏clone的模式/图例/result与页面查询状态保持。该证据仅覆盖既有全屏，待合入的新全屏设计仍须专项验收。

公司强制动画的展开基线为图卡237、第一图plotArea147.5；十次25ms等待后的时间序列仅出现图卡264/325、plotArea174.5/235.5两档，展开后恢复237/147.5，view/result/query保持。严格检查要求时间序列自身超过两档高度，因此当轮失败。不能把展开基线加入动画样本后改称三档通过。主控随后安排UI owner记录实际on_progress/plotAreaChanged时间，区分采样遗漏和布局耗时，结果见下一节；当轮measurements.json不改写。

多数PNG来自本进程自有HWND的PrintWindow客户区绘制，既非屏幕截图也不含系统标题栏。`city-fullscreen-state`的一次PrintWindow位图被稀疏颜色采样规则拒绝，原始尝试记录保留，保存PNG使用Qt客户区render回退。静态查看回退PNG可见真实曲线，但不足以证明被拒绝的原始位图有效或PrintWindow缺口已消除；`native-window-render-unavailable`仍保留。城市恢复PNG的曲线/图例与测量记录相符。

首轮结束后已明确释放Qt给主控，后续线路后台高DPI短批次与UI公司诊断均由主控分配窗口。本会话只维护证据文件，没有仅凭进程空闲自行开新Qt测试。

## 采样诊断与最新后台复核

UI owner的`qa_company_timing.py`在独占窗口运行，`motion-evidence/focus-True-1790844921/diagnostic.json`保留实际事件时间：首图plotArea在约46/78/110/138/181/209/213ms发生148.5/151.5/162.5/180.5/230.5/236.5/235.5七档变化，未计入展开基线147.5。两次标称qWait(25)实际约85/106ms，期间发生多次绘图与布局事件，返回后轮询漏过中间值。reflow通常3–5ms、首次约10.6ms。该证据定位了轮询漏采，未据此修改产品预算或声称屏幕实际展示了每一档事件值。

QA改动仅为折叠前连接第一张可见图的plotAreaChanged，事件记录各图真实plotArea、panel、view/result实例及单调时间；折叠结束、展开之前断开。十点轮询继续保留并加单调时间。超过两档panel和plotArea的严格阈值保持，改用实际变化事件计数，不加入展开基线。`focus-True-1790845011/qa-focus-observation.patch`保存精确差异。已恢复`focus-True-1790843960/qa_motion_focus-original.py`，SHA256与预先记录的`6b6ee8456fe59bb574e21a9557c23a1ee2cc3cffa4323aede585ccc8c4ab4ae1`完全一致，原失败可按原脚本复核。

UI随后运行完整`qa_motion_focus.py --background-render`，工具记录实际exit0、45项全部通过，证据为`motion-evidence/focus-True-1790845011/measurements.json`。本会话读取UI完成记录、复核JSON和QA差异，没有重复Qt运行。新复核的公司事件panel六档238/241/262/285/325/326，plotArea六档148.5/151.5/172.5/195.5/235.5/236.5；所有事件view/result ID与展开基线一致。其余页面两策略、展开恢复、状态保持、九卡模拟阴影和原存档保护仍通过。两轮前端与非测试src源码hash逐项相同，原save/probe hash相同；新轮source-freeze通过，产品实现未变。四份当前QA脚本完成静态语法检查，未导入或启动Qt。

新轮仍记录`actual-native-pointer-and-foreground-unverified`和`native-window-render-unavailable`，`native_pointer_verified=false`、`acceptance_complete=false`。45/45只表示本轮后台与模拟事件逻辑检查通过，不表示原生鼠标或全屏PrintWindow缺口消失；新全屏设计仍在本轮范围之外。原3960轮45/44/1、原原生283/281/2及其退出码均保持原值。新的实际进程退出记录单独保存，不能用它覆盖旧记录。

UI已正式释放Qt，本会话接管QA证据归档。City随后提交`5d80e64`并释放index，主控授予本会话独占证据提交窗口；提交前HEAD为`5d80e64be291e89787c6cdb23cb4a7aa34492831`。本次只提交QA脚本、审查和精确证据清单，不触产品源码，不启动Qt，不推送。定点结论仍按各轮实际源码hash限定，HEAD更新本身不构成新增整库验收；City其他未运行单元、线路与主页在途文件不纳入本次提交。`motion-evidence/submission-manifest.json`记录精确候选文件与SHA256。
