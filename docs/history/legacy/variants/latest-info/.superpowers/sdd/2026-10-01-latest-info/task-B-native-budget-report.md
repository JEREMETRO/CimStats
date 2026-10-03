# B 原生整窗底部预算定点修复

根授权的唯一短 Qt/后台原生槽已结束，B 候选源重新冻结。当前只修复已有四模块、蓝紫独立极值卡版本的整窗底部裁切；随后收到的 Astra 新一轮红绿亮点卡、扩大趋势和三段选择器指导未在本槽实施，需协调负责人另行调度范围与验证。本报告不是新版视觉签收。

## 实际根因与最小修改

用 E 已准备的 `OwnWindowCapture`、`inspect_upper`、`viewport_geometry` 和独立数据期望函数，只读复用 helper；B 自有脚本与证据位于本目录。自有 HWND 后台 PrintWindow，不激活前台，不使用全局鼠标，不改 OS DPI。真实多人缓存通过现有 MainWindow/controller 正常完成异步载入。

修复前实际测量：

- 原生 frame 1462×971，DWM 可见 frame 1440×960，原生与 Qt client 均为 1436×900。
- page 与 viewport 1204×860，board 1204×868；纵向 range 0…8/value 0，横向 range 0/value 0。
- 原生字体下业务模块高 233、亮点区域高 158，main 高 512；提醒高 494。
- 三张图卡均高 282，映射到 viewport 的顶边 586、底边 867；viewport 最后可见行 859，三图全部超出 8px。结构、排行、占比三态一致。

生产源码仅三行变更：页头高 52→48；页头后留白 10→`SPACE_SM` 8；图表段前留白 12→`SPACE_SM` 8。共回收 10px。没有修改数据、共享壳体/统计类、任何字号/字重、282 图高、四卡结构、主辅角色或图表交互。

## 验证与实际退出

- 原生 RED 脚本捕获三态、检查全部数值/行数后，真实 scroll 8 断言失败；进程实际 exit 1。
- 新增 3 个页面回归用例，用上次实际原生 size hints 与 1204×860 viewport 构造明确组件 fixture。修复前全部因 scroll 8 失败：`3 failed, 61 deselected in 1.69s`，actualexit 1。
- 必要 B 页面检查：`64 passed in 11.02s`，actualexit 0。没有重跑全库或已冻结的图表测试。
- 修复后原生脚本 actualexit 0。三态下 page/viewport/board 均 1204×860；横纵 range/value 全部 0。
- 三图映射 viewport：趋势 `[0,576,288,282]`、客流 `[298,576,448,282]`、班次 `[756,576,448,282]`。三卡底边 857，全部边框与圆角在 viewport 内，底部剩余 2px。
- 两个分析卡排行各 10 行，占比各 11 项，结构态全部真实制式。每行完整处于所属图卡内，绝对值/比例实际字体测量完整；独立原始期望验证数字、顺序、Other 与百分比。百万环心完整。
- 四组图标与蓝紫标志条仍在；13 项指标和 16 项极值均可见、字体/字段/单位完整。RED 与 GREEN 的指标标题/数值/单位、极值字段/数值/单位逐项比较，字号、字重、字体家族及文本无一变化。
- source guards、primary 工程、真实 cache CSV/manifest/save/probe 哈希在各次运行前后不变；workers 实际停止。D 获授权并行的纯导出清理不在 B 的冻结 guard 中，不被误判为侵占。
- 最后独立进程查询：没有 Python/pythonw/parser_backend 残留，查询与字号比较 actualexit 0。

## 确切新证据

- `task-B-native-budget-green/structure.png`
- `task-B-native-budget-green/ranking.png`
- `task-B-native-budget-green/line_share.png`
- `task-B-native-budget-green/native.json`：真实 frame/client/viewport/board/图卡底边、29 个数值及字段字体、10/11 行与数据验证、保护哈希、退出码。
- `task-B-native-budget-red/native.json` 与三 PNG 保留修复前实际证据。
- `task-B-native-budget-test-red.log`、`task-B-native-budget-test-green.log` 保留必要页面 RED/GREEN。

B 已亲看修复后上述三张原生整窗 PNG，下边框/圆角完整，无整页滚动。独立 E 最终复验尚未执行。此机器 OS `GetDpiForSystem/GetDpiForWindow` 为 192；校准 Qt 基础 DPR 为 1，`QT_SCALE_FACTOR=1`，实际 effective DPR1。本证据不冒充真实系统 125% 或前台交互验收。四独立卡原有 5px 跨卡 widget 中心差保留为 P2 角色排布观察，没有增高或重推矩阵。

## 冻结 SHA256

| 文件 | SHA256 |
| --- | --- |
| frontend/latest_info_page.py | `4D2A17F8F4996A8A59C2B1A1DAEFC07F9E4A2C48A9E4DC897D79D959D5FC905F` |
| frontend/latest_info_charts.py（本槽未改） | `3D153B43D2FABF1D3E818F38B1B9390A5E8BAA83D651452F255B3C381865DA7A` |
| src/test_latest_info_page.py | `18F5E249E22B3DBC6858B0C03A7307EEAFE17079A114222328465C29FE5C7317` |
| src/test_latest_info_charts.py（本槽未改） | `62B047EE20D7ACF33EECB51D8BEAE9200E2B5DC14E50BA72CAD0D0FA45F13795` |
