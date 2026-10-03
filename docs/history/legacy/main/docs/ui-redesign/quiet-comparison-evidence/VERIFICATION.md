# 默认比较说明与网络卡片边界验证

2026-10-02，真实多人存档缓存，无重新解析。

- 无效比较标签隐藏且不占布局空间；原因在数值/城市对应行 tooltip，可访问说明保留。有效比较和真实缺失值 — 保持。
- 四文件边界：card_comparison_label.py、company_dashboard.py、network_dashboard.py、city_dashboard.py 的 CityTile 提示；不修改公共图表、模型或查询。
- 定向测试实际 exit 0，30 passed in 2.83s：test_quiet_card_comparison.py、test_card_comparisons.py、test_network_dashboard.py、test_city_dashboard.py。
- 网络底边新增回归在修复前实际断言失败，修复后通过。实测原 summary 卡 150px / host 92px / tile 96px / visible 92px；展开高度按 minimumSizeHint 设置下限后，卡 154px / host 96px / tile 和 visible 均 96px。
- 1440×960 / Qt DPR 1：公司同期展开、摘要折叠后恢复滚动范围均 0；当前未复现先前 1px 滚动，不声称覆盖其他缩放或后续图表改动。
- 最终截图与几何：../motion-evidence/focus-False-1790918405/。company-period-restored.png、network-restored.png、city-default.png、geometry.json。实际采集 exit 0，源码冻结，原存档与 Assembly-CSharp.probe.dll 哈希保持。
- 最终使用 Qt offscreen QWidget.grab；不代表原生鼠标或系统 Mica 验证。首次 focus-False-1790918193 的 --qt-render helper 图表绘制不完整，保留原记录但不作为最终图面证据。
- verified.patch 包含精确跟踪文件变更；新增 test_quiet_card_comparison.py 和 qa_quiet_comparison_geometry.py 保留为单独文件。未暂存、未提交、未打包；Qt 已释放。
