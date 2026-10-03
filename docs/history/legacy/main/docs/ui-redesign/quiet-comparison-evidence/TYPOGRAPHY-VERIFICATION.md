# 字体与数字单位组件验证

2026-10-02，仅独立 offscreen QApplication 与 QWidget，未创建 MainWindow，未改系统 DPI、鼠标、用户 INI，未修改唯一共享 helper。

共享 helper 最终 SHA256：41CDE0463AD76F31A62E5B51D7A9F72419708146ECF22ABCCFC1265DD462851B。五个接入文件的改前/改后哈希见 typography-hashes.json，接入差异见 typography-only.patch；不包含原静默比较改动或主控统计页接线。

22 项定向回归初次通过（2.06s），动态基线修复后仍 22 passed in 2.08s / actual exit 0，日志 typography-component-tests.log。

原 AlignBaseline 显示为居中而未对齐字体基线。components-scale-1-normal-before 保留同字体、原对齐机制重建后的局部图和 actual exit 1；公司、网络基线差 4px，城市见测量文件。修复采用底对齐并按 QFontMetricsF descent 差补偿内容边距，FontChange/ApplicationFontChange/DevicePixelRatioChange 自动更新。按 label contentsRect、alignment、字体 ascent/descent 测得修后基线差均 0，未硬编码 4px、未改字号或卡高。

正常/紧凑尺寸，进程 QT_SCALE_FACTOR 1/1.25/1.5/2（不代表原生系统缩放），8 个实际独立进程均 exit 0，数值宽度未超出分配区域。测试中文货币/人及西文 USD/%、大数 12,345,678.9、缺失 —、涨跌与持平；动态把数值/单位换为 17/14px 后，三页组件基线差仍 0。

Variable 实际 glyph family Segoe UI Variable，中文 Microsoft YaHei UI；富文本数字 glyph weight 600、前缀 400。缺 Variable 的独立进程只模拟 SegUIVar.ttf 加载失败，保留真实 Segoe UI 加载，actual exit 0；先前错误地跳过整个初始化的诊断保存在 invalid-loader-simulation.json，不能据此判定 helper 失败。最初缺中文字形也是探针未镜像应用离屏字体加载，已纠正环境，不修改产品全局样式。富文本 glyphRuns 必须按 block 实际文本长度取样，默认空范围不作为字体失败。

components-scale-*-after/measurement.json 与局部 cards.png 记录字形、字号、opsz、单位基线、宽度、有效与无效比较以及源码冻结；每进程产品文件 hash 前后保持。

真实存档有效变化常驻仍待主窗口专属时段，以上组件证据不替代该验收。未 stage/commit，全部组件进程已退出。
