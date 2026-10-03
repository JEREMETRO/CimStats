# 图表字体与根兼容候选最终交付（2026-10-02）

根目录未写入、共享索引未写入。主 Qt 已释放，确认本任务 pytest/qa/候选验证 Python 进程全部退出。
图表行为候选提交5edf639；字体改动另见 CHART-FONT.patch，当前未提交。

## 当前代表图

evidence/chart-font/representative-1440x960/line.png 和 stack.png：真实51282行缓存，经原Result与fullscreen克隆链，1440×960/DPR1/offscreen。不是原生桌面截图，也不是旧v2截图。
line192数值/192命中/192表行；stack384分段+192公司合计=576数值/384分段命中/576表行；两图标签碰撞0。公司分别六进公交、八达交通集团，真实companies模式独立列。全部时间点以横向滚动画布访问，无采样。隐藏类别后原总量保持。摘要高度109px；强调数字24px/600/opsz36，实际Segoe UI Variable glyphRuns的fvar表236bytes，宽度足够，数字与12px单位基线差0。混合中文实际YaHei fallback由窗口用例验证。

截图源码完整hash及PNG hash见 SOURCE-MANIFEST-FONT.json；原始测量详见该目录measurements.json。共享helper唯一根源41CDE0463AD76F31A62E5B51D7A9F72419708146ECF22ABCCFC1265DD462851B，未复制/改写helper。

## 精确根兼容补丁

root-chart-candidate/CHART-ROOT-COMPATIBLE.patch仅含6生产文件（新增chart_details.py；stats_charts.py、fluent_chart_view.py、network_charts.py、company_dashboard.py、statistics_page.py）。完整before与candidate after SHA256见该目录manifest.json。after是隔离候选，不是已经实际写入的根代码；实际根before/after目前相同。

限定改动：删除三点指标菜单全部创建、布局及页面调用链；保留默认四卡/满意度选择；增加大图公司周期摘要、全点值与独立公司堆积列、缩放/横向滚动、完整辅助表及真实值选择定位；包含根尚未接入的f525605已验收悬停/零值修复。
保留根最新CompactLegendButton、SurfaceMotion/elevation、motion_policy、line_width/line_style/hide_center，保留公司/统计页现有共享字体调用与_reflow_company。未改首页浅蓝3文件、其它统计字体文件、网络模型、线路字体或helper。

根旧stats_charts.py标题172行字体声明，对应after176–178行emphasis_css(16/600)+apply_emphasis_font；旧summary240行对应after226–228行22px/700共享font。删除旧QSS字体以防覆盖opsz。标题/摘要候选已修，根当前仍旧，不能表述为已根接入。

## 验证与范围

- 字体+detail窗口17 passed（1.79s），真实字号/字重/opsz、Variable拉丁fvar、中文fallback、数字单位基线/宽度验证。
- 最终工作树7个相关图表文件148 passed（6.67s）；旧固定YaHei首选font测试改为共享首选family并检查实际中文字形fallback。
- 根兼容候选在当前根依赖下导入4个候选图表模块，hover/detail/model/emphasis47 passed（3.49s）。首次候选遗漏前版hover导致7失败，已补齐，不以首次结果签收。
- git apply --check对当前根exit0；差异检查通过；无实际应用、无根索引操作。
- 共享接口强制Segoe UI fallback的纯绘制调用通过；本轮未模拟字体库缺Variable后的实际glyphRuns。原生输入此前工具无法列出Qt窗口，缺口保留。五档DPI按主控要求未重跑，待代表图视觉审阅。
