# F 增量复核记录

- 固定提交：0421ba54d2bbc04aff6c19c925b80789aacf9b35
- 审查范围：de9b624..0421ba5 中 desktop_app、stats_style、stats_charts 及新增回归测试。
- 结论：未发现本次增量引入的 P1/P2 阻断问题。本结论仅覆盖指定增量，不替代最终候选版本全量验证。

## 代码复核

1. FluentComboBox 的业务值通过 userData 传入；公司身份及空筛选哨兵保留。
2. TabWidget 清理时先隐藏旧页签和页面，再 clear 并延迟删除页面；替换导入和线路切换共用该清理路径。
3. FactCard/FactGroupCard 移除重复的点击发射，真实鼠标回归确认一次点击只触发一次。
4. 线路与公司 XLSX 导出入口及原有 export_file 分派保留；导出字节一致性回归通过。
5. 窄屏事实卡片使用滚动区域，并按视口宽度计算内容高度；延迟高度调整包含对象有效性检查。侧栏切换、窄屏滚动及页签重复替换回归通过。
6. 全局应用字体与 Fluent 字体族设置为 Microsoft YaHei UI，图表标题、图例、坐标轴及新增控件的字体回归通过。

## 验证证据

在本目录 snapshot 的固定提交副本中执行：

```text
py -3 -m pytest src/test_other_pages.py src/test_stats_shell.py::test_theme_initializes_light_fluent_app src/test_stats_shell.py::test_overview_flow_tracks_sidebar_width_without_window_resize src/test_stats_shell.py::test_line_details_scroll_and_tabs_replace_cleanly src/test_stats_charts.py::test_chart_uses_available_chinese_font_for_title_legend_and_axes -q -p no:cacheprovider --junitxml=../incremental-tests.xml
```

结果：16 passed；JUnit 记录 tests=16、failures=0、errors=0、skipped=0。
使用提交内正式 src/conftest.py，未加证据专用清理插件；本次组合执行无 Qt 生命周期崩溃。

未修改生产代码或仓库测试。本轮未重新审计已关闭的数据口径问题，也未执行构建或版本发布。
