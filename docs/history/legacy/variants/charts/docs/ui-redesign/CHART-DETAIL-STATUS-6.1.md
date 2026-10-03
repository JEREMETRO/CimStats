# 图表详细版交接状态（2026-10-02）

基线 f525605，feature/company-fluent-charts。本轮源码未提交；主目录及主索引未写。候选被视觉验收阻断，不可集成或打包。

## Qt 已释放

本次原生 QA Python PID15996 经命令行核实后关闭，再次查询无本次QA Python残留。Qt已释放给UI定向检查，后续图表GUI复验需重新协调窗口。

原生控制工具最后一次list_windows只返回四个ChatGPT和资源管理器，未返回图表窗口。未进行真实鼠标输入，native-pointer报告的external_native_expected只是等待状态。进程与Explorer均Session2，不归因为会话不同。原生报告实际屏幕2880×1920/DPR1、客户端1400×880；不能称原生200%通过。

## 当前证据

最新布局 representative-1440x960 下line/bar/time-bars/stack/pie.png；bar两公司并排。五档同名图目录1920x1080-100、2880x1920-200、2560x1440-125、3840x2160-175、2560x1600-150。位置均为 docs/ui-redesign/evidence/chart-detail-6.1。每目录measurements.json包含实际DPR/图片尺寸、四源hash、标签和表行数。150%实际2561×1601为像素舍入。五档均离屏模拟，不证明OS显示设置或原生指针。

相关回归最终157 passed/18.91s，日志chart-detail-targeted-final.txt。纯模型13 passed，禁用conftest并断言无QApplication；未重复无关全库。25案例复用Result/标签碰撞0/隐藏原总不变。密集图当前图内标签0、表完整，因此不满足主控最新逐点/逐段常驻标值要求。

## 主控阻断待修改

1. 图面每有效点、堆积段及柱顶合计常驻，完整表不能替代；重做密度/缩放平移策略。
2. 汇总卡压紧名称日期，突出KPI数值，减少约120–145高的空白。
3. 网络多公司须公司并列、公司内分类堆积，核实修复四段同柱。
4. 对齐趋势/分布/比例全局命名。
5. 核实折线无插值，解释圆滑来源。

先纯修改，GUI重新排期。原生鼠标/动画未验证；旧f525605的310项/hover证据不代替本轮。

## 所有权及补丁

生产6个：新增frontend/chart_details.py；修改stats_charts.py、network_charts.py、fluent_chart_view.py、company_dashboard.py、statistics_page.py。测试6个：新增src/test_chart_details.py、test_chart_detail_widgets.py；修改test_stats_chart_fluent.py、test_stats_fluent_page.py、test_stats_charts.py、test_network_charts.py。QA2个：修改src/qa_stats_charts.py，新增qa_chart_details.py。其余本工作树证据文档。未改主目录、主索引、OS显示、保存、probe或缓存。

CHART-DETAIL-6.1-DRAFT.patch 为当前14个源码/测试/QA文件对f525605的精确快照。SOURCE-MANIFEST-6.1.json含14源hash/基线/补丁hash。反向检查仅证明对应本树，不证明可直接应用主目录。保留主树首页26、SurfaceMotion/elevation、城市hide_center/line_width、网络预算等新改动，禁止整文件回填。