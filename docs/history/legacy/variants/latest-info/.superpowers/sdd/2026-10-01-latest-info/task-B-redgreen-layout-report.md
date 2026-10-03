# B 最终下区修订与冻结交接

本轮最新用户方向已实施，B 四源文件冻结。最后独立进程查询无 Python/pythonw/parser_backend 残留，Qt 槽已安全释放，供根生成新 manifest 并交 E 独立复验。本文对应 `task-B-redgreen-native-accepted`；旧 `native-final` 是增强选中状态前的历史图，不能绑定本次最终源签收。

## 可评审结果

1. 四独立亮点由旧蓝紫、线路标题/长说明/四行表，改为红色最大值、绿色最小值细条；短角色＋15px真实线路身份卡头，20px命中主值与12px单位独占一行，三项13px辅助字段/数值及12px单位在下方。左右12、上下8内边距，四项/卡共16值全部保留。原生自然卡高132，四卡主值 y33、辅助起点 y64一致；长身份真实换行时统一所有卡头高度，保持锚点，不缩字。真实 key、整卡鼠标及键盘跳转保留。
2. 图卡384/400/400、间距10，趋势保留统计页同源微渐变、两个真实 QLineSeries。**旧 e04 的 plot 未测**；本轮在同一真实数据、同一窗口字体下临时将现有趋势卡约束为旧288宽进行受控比较，plot为233.5×194.5；解除临时约束恢复新384宽后为329.5×194.5，绘图区宽增加96（约41.1%）。该受控比较没有旧图截图冒充新实测。
3. 两分析卡环径156、内孔比0.78，绘制与扇区命中同步，环心21px保持；百万1,376,429与6,745完整显示。默认分类绝对值/百分比并列，四字制式全宽保留，百分比列采用本列表最大实际文字宽，删除分类行冗余箭头。排行满宽十行、占比十条＋Other真实63条共十一项，精确值/单位/百分比及全分母均保留。
4. 第一层标题＋可见短范围菜单；第二层复用统计页 `FluentSegmentedControl` 的实际三段按钮，三个入口常驻，本页 `subtle=False` 采用共享 accent 蓝底白字，hover/焦点保留。重复 view_label 与旧独立动作删除。返回固定28×28槽；排行↔占比保持本卡 mode，分布/返回清除；两卡与页级范围独立。
5. 图卡首部与完整232px列表预算为304高，并采用实际内容 minimumSizeHint 自然增长，不压回282。最终页头40、首段4、main507（city65＋scope32＋modules233＋highlights153＋内部间隔24）、图段4、图卡304，共859；viewport860，剩余1px。没有修改共享 shell、A/C数据、D控制器、统计类、字体工具、主工程或 index。

## 最终原生证据

三张确切新图（B 已逐张亲看）：

- `task-B-redgreen-native-accepted/structure.png`
- `task-B-redgreen-native-accepted/ranking.png`
- `task-B-redgreen-native-accepted/line_share.png`
- `task-B-redgreen-native-accepted/native.json`：最终四源 SHA、保护哈希、13指标/16极值字段与单位的原生字体、列表数值/全宽、selected accent 实际像素、真 frame/client/viewport/board/底边、实际退出码。

自有 HWND 后台 PrintWindow；真实多人缓存经 MainWindow/controller 正常异步载入。原生 frame1462×971、DWM可见1440×960、client1436×900、viewport/board1204×860。三态横纵range/value全0，三图映射 viewport 为 `[0,555,384,304]`、`[394,555,400,304]`、`[804,555,400,304]`，底858，全卡边框/圆角完整。蓝色选中实际采样均为 `#0067c0`。所有行在所属卡内，名称/数字/单位/百分比均经字体宽高测量；默认有轨电车全文、排行各10行、占比各11项、总量全文均验证。

原生脚本 actualexit **0**；workers_stopped/source_unchanged/primary_unchanged/protected_unchanged 全true。临时INI已清理，cache CSV/manifest/save/probe只读且哈希不变。D获授权的纯导出清理未计入B冻结guard，未误报侵占。

本机OS DPI192，已校准Qt基础DPR1、进程`QT_SCALE_FACTOR=1`、effectiveDPR1。没有前台、全局鼠标、OSDPI或parser操作。真实系统125%及 E 的新控件独立事件复验尚未由本次B执行；不能将目录名 accepted 视为独立审计已签收。

## 必要测试与新控件合同

最终 `src/test_latest_info_page.py src/test_latest_info_charts.py`：**145 passed, 8 warnings in 27.67s，actualexit0**，日志 `task-B-redgreen-layout-final-tests.log`。8条warning均为已安装qfluentwidgets菜单的QHoverEvent弃用提示；未改共享包或屏蔽提示。按根要求不再追加广测。

新增需求经过 RED→GREEN：10个布局/分段用例原实现全失败；原生首轮实测超3px，更新字体预算3态测试均因scroll3失败；菜单入口三键和列表选择三键分别复现不响应后补键盘桥接；动态内容高度与长身份锚点各有明确负测。最终真实focus+QTest局部鼠标/按键验证三段左右切换、Enter/Return/Space激活、菜单打开/方向键/真实选项单次选择、勾选、返回三键单次激活及原禁用/自动重复行为。公开state JSON、同会话恢复/失效、来源门禁、缺测、零值、完整分母、真实key及单/双线合同回归通过。

E 绑定提示：`structure_button/ranking_button/share_button` 都指向实际可见分段item，无隐藏代理；`view_selector.currentKey()`为structure/ranking/line_share。`mode_combo`现为实际可见 `ModeMenu`（名称仍 rankingMode/departureRankingMode），保留 count/findData/currentIndex/currentData/setCurrentIndex 数据key API；真实popup为 `mode_combo.range_menu`，列表为 `.view`，item UserRole是真 QAction。分布时范围入口禁用，页级单制式隐藏重复入口但保留槽位。分类 `ModeRow.name`为实际全文label。环径156，sector有效内半径0.78，E原0.82径向采样仍在扇区内。

非阻塞P2：客流Other“其他线路（63条）”在32px中自然换行，文字完整可读；保留原布局，不为了该细节加高或扩大改动。

## 四源冻结 SHA256

| 文件 | SHA256 |
| --- | --- |
| frontend/latest_info_page.py | `91396772886297DFA33025B030F9743DBECAFF718B85693BC7DCEBE79FDF653E` |
| frontend/latest_info_charts.py | `84C4538CBEA404F483B36C07E6E65D92C1AF9D5A03982EE5D2D94ADE5BF3E69C` |
| src/test_latest_info_page.py | `0FEA4DE7C4BB638CD50BEF971535791ADA10C4D79777B5251F10F5C8A999E0B0` |
| src/test_latest_info_charts.py | `F2EAE4819D17E4CEF26D43C14095D51E0BF25AEFB0C68718E732E14A7A7D844A` |
