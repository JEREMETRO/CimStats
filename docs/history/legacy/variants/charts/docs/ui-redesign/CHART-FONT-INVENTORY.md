# 图表强调西文字体接入盘点（2026-10-02）

当前基线5edf639；三个公共图表文件已接入主树共享helper，未新建/复制helper，不更改全局QSS或应用默认字体。未持有Qt槽，不启动QApplication/主窗口。最新候选与测试边界见 CHART-FONT-CANDIDATE.md。

主控接口确认：frontend/stats_typography.py，emphasis_font(size, weight=QFont.Weight.DemiBold)和emphasis_families(size)。公共图表由本owner唯一修改：chart_details.py、stats_charts.py、fluent_chart_view.py；company_dashboard.py/statistics_page.py强调位置交由已盘点的统计页owner统一接入，本树不另造相同字体hunk。network_charts.py当前无额外强调入口，继承公共图表接入。

| 自有文件 | 强调位置 | 当前字号/字重 | 接入范围 |
| --- | --- | --- | --- |
| frontend/chart_details.py | DetailSummary 名称/期间 heading | 14px/600 | 混合公司名、期间内西文/数字；中文fallback保留 |
| frontend/chart_details.py | DetailSummary number | 24px/600 | exact_number完整数值；与12px单位基线联合复验 |
| frontend/stats_charts.py | panelTitle | FONT_SIZE_CHART_TITLE / DemiBold | 标题内西文/数字 |
| frontend/stats_charts.py | summary_label | 22px/700 | 汇总强调；现有显式YaHei family需局部去掉，避免盖过helper |
| frontend/fluent_chart_view.py | _draw_pie_center 小饼total_text | minimum / Bold | 绘制时用强调font；常规单位必须恢复原常规字体 |
| frontend/fluent_chart_view.py | _draw_pie_center 大饼total_text | 14px/Bold | 同上；中文总计仍常规原字体 |
| frontend/company_dashboard.py | KpiCard.value | FONT_SIZE_KPI /600 | 公司指标所有数字和西文缺失文本 |
| frontend/company_dashboard.py | CompanyGroup.name_label | FONT_SIZE_BODY /600 | 混合公司名中的西文/ID数字 |
| frontend/statistics_page.py | MetricTile.value / 分公司value / CategoryTile分类value | 17px/600、15px/600 | 此文件主树首页26等改动在他人ownership内，只做自有类局部hunk接入，禁止覆盖整文件 |
| frontend/statistics_page.py | MetricTile.owner / 分类badge | 11px/600 | 粗体混合公司名/序号内西文/数字 |
| frontend/statistics_page.py | page heading | FONT_SIZE_CHART_TITLE /600 | 混合标题中的西文/数字，局部接入 |
| frontend/statistics_page.py | 已选tab强调 | QSS font-weight600 | 由UI owner控件样式接入，避免本分支另写全局选择器 |

network_charts.py 自有代码中的图例11px、placeholder正文等当前不大且非粗体，未发现额外强调font入口；图表顶部标题与详细汇总/饼中心走上述继承路径。

常规图面值12px、日期/轴12px、完整数值表13px、单位12px保持当前字体，不扩大本次指定的强调范围。若已继承强调属性则在接入时复核，不能把普通中文整体替换。

接口确认后的最小验证：真实Latin face选择及不存在时可读fallback、混合中文不缺字；24px数值与12px单位baseline和宽度；200%/125%等DPI当前详细汇总和饼中心不裁切，保持常驻数值数量/碰撞0。只跑相应新增字体/布局用例与必要代表图，不重启166项全轮。
