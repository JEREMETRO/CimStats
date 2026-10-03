# E 驱动器调整记录

首次freeze准备命令actualexit1，尚未Qt：Windows Path.relative_to字符串使用反斜杠，父提供SHA清单使用斜杠，查字典产生KeyError；不是产品SHA不匹配。仅将QA source-lock键规范为as_posix。一次补丁因hunk顺序未匹配而拒绝，没有产品写入；随后定向重下QA补丁。

绑定最终源码时修正准备阶段假设：排行为列表态，不要求环心总数；结构/占比必须有实际可见总数及单位。B长总数允许完整换行，按实际字形换行bounds检查，不拿单行宽度判完整多行失败。四独立极值卡使用实际grid字段/数值/单位和独立角色条，不强制整张card的accessibleName重复四字段；真实身份须可访问，字段在可见行中关联。四业务组按最终metric_modules/IconWidget绑定。以上均只修改E QA驱动器，产品只读。

2026-10-02键盘修复后：新源锁140源与候选26路径匹配，仅charts及对应test两文件按B授权改变。12键独立复验12/12通过，单次clicked=1；原RED脚本/日志/源锁另保留。

`events-e02`原exit1保留：前25项状态动作成功，第26项把局部鼠标投到RankingRow空白中部而非当前实际箭头action。源码仅action.clicked发line_requested，未约定整排行行可点；这是E驱动目标绑定错误。改投真实row.action，不改产品、断言或发被测方法。新证据另写e03。

原生四极值字段对齐断言按highlight_grid.getItemPosition的实际视觉行分组；同一行各字段中心差仍<=2，完整记录行列，继续13+16字段/单位/字体检查。四卡响应式分行不再跨行要求同y。

native-multi-dpr1.0-e01原exit1发生在装载真实缓存前的DPR门禁。独立只读屏幕采样dpi-diagnostic-e01确认OS192但Qt screen DPR0.5（factor0.5），不是产品排版失败。E bootstrap先建QApplication后导入Fluent，与真实程序及旧可靠baseline先导入desktop/Fluent再建app的顺序不一致；Fluent依赖的进程DPI初始化因此过迟。QA bootstrap调为先导入Fluent后构建app，不调用系统DPI setter，仍重新测GetDpiForSystem及实际window DPR；原失败保留，新native子目录e02。

长值/同会话范围fixture加入显式--capacity-fixtures，仅多人DPR1运行一次。其他原生矩阵只做真实数据，避免重复容量渲染。

原生比例定位结论修正：e02/e03完整pre-app导入也未改变DPR，故Fluent过迟初始化假说未成立。当前WinDisc虚拟屏幕Qt基础DPR实际1，与OS192/96的2不同；旧baseline环境不能代替本次屏幕校准。采样factor.5→QtDPR.5确立当前base1。父亦只读确认，按新--qt-base-dpr=1计算factor1/1.25，继续实测windowDPR与OS192门禁。未改系统DPI或全局环境。e01/e02/e03失败保留；e03完整退出/源hash记录native.json。

根/Astra看图裁定四独立卡5px仅widget中心的角色差异，无文字baseline实测，非单独阻塞。驱动不再套用已失效共享矩阵全列中心<=2合同，改记录角色布局观察。保留fontMetrics完整、数字/单位语义、各卡水平/行间非重叠、card内部bounds；增加viewport_geometry并在upper检查前保存page、viewport、board、各scroll min/max/value、三图card矩形/bottom/完整包含，再按各真实图态记录。纯AST检查通过，未启动Qt。

2026-10-02用户msg01a0fa63新合同预备（无Qt）：旧蓝紫/288趋势/隐藏当前动作不再是验收规则。新display-contract按短角色、红/绿两family（同角色统一）、一主值独行＋三辅助、全部16数值/语义/单位/真实key检查；不要求不同业务字段跨卡共享表格。适配换行身份并保留主20/辅>=13/单位>=12及字重、完整内容、数值单位紧邻/不重叠/卡内边界。

事件目标通过可见三段完整名称及真实clicked接口绑定；三段始终可见/启用、真实checked/selected状态与capture_state一致、同排不重叠且坐标跨态固定。源码现read-only可见B的ViewSegments(FluentSegmentedControl)实际TogglePushButton/isChecked，及ModeMenu.range_menu保留currentData原API；B仍在编辑，不把当前source当最终冻结或运行通过。独立目标不调用被测show_*作为动作。

原生在任何upper门禁前保存真实viewport、board、scroll min/max/value及三卡viewport底边；宽窗全三态要求完整卡框和zero整页滚动；响应式小物理窗另记。新增实际trend.chart_views的QChart.plotArea矩形与series类，旧e04数值未采就明示未测。解析/语法/import仅标准库，PySide/qfluent模块=[]，未占B的Qt槽。

458事件/12key旧通过按原hash保留。换真实selector后将定向验证三态鼠标/键盘/左右键、localMode菜单、双图独立、mode保持/清除、返回和本次环图几何/总量；不因准备变化重复A42或历史782。实际键盘与菜单绑定等B最后源码冻结/新源锁/父正式Qt移交后核验。

限定新controls入口task-E-latest-controls-check.py已准备，默认Qt-free；未来--run必须新源锁＋父正式slot。仅真实多人新三段9组合/两卡左右箭头与Tab、实际ModeMenu鼠标及Return/Enter/Space打开→局部菜单Down到真实item→单次选择→checked/data key→排行占比保mode/返回清mode，两图scope独立。使用真实menu.view.viewport点击或局部key，当前行来自实际Down，不直接触发action/emit或调用show_*。

D同会话刷新通过实际schedule timer/worker验证纯状态意图，scope-control安排触发真实scope signal/worker并按raw company/mode可用性判断保留/清除；显式新session替换需回structure。仅另用六制式fixture覆盖新环图几何/0.5%与replacement，不重跑旧five-boundary458。原生三真实缓存各新图态、实际row/highlight跳key与输出读回仍另跑既定矩阵。上述均仅AST/默认路径检查，通过时Qt模块为空；尚未声称新控件事件通过。

新controls e01/e02原exit1保留、事件0：准备驱动严格QWidget矩形无交叠门禁误判Fluent分段共享边框。实际三rect为[11,35,70,26]、[81,35,70,26]、[150,35,70,26]，最后两段仅共享1px边框，完整名称未交叠；属于根禁止追加的非阻塞像素P2 gate。改为继续记录原矩形，保留full advance/visible/checked/固定坐标及font-metric文字跨度不交叠，未改产品或状态断言。另manifest真实output_files注入只读load_case_data.outputs，复现解析完成数据的原工作簿路径，后续只复制到QA目录并校验源字节，绝不写原文件。
