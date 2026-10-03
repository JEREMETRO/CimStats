# 最新信息 E 背景窗口与导出证据

2026-10-01 旧版功能限定验收完成；用户已否决视觉，视觉未通过，父暂缓主源应用。真实缓存 MainWindow、自有 HWND PrintWindow；无桌面截图或前台鼠标键盘验证。系统实际192 DPI/200%，仅QA进程QT_SCALE_FACTOR=0.5/0.625，实测DPR1/1.25；实际系统125%未测。用户最新要求：未明确请求的说明不得添加；copy-audit只读记录删减对象。

- 当前DPR1：autumn-frame1440-scale1.png、multi-frame1440-scale1.png（DWM可见/像素精确1440×960）。对应native-autumn-scale1.json、native-multi-scale1.json。
- 进程125%：三缓存 *-frame1440-scale1-25.png（1800×1200，相当1440×960布局），metadata native-all-scale1-25.json。
- 多人窄客户端920×680：multi-client920x680-scale1.png / scale1-25.png。导航收起、响应式重排/预期滚动、范围及已读/阈值/取消由JSON记录。
- 真实19条全量与详情：multi-0-dialog-scale1-25-detail.png、multi-1-dialog-scale1-25-detail.png；metadata native-multi-scale1-25-detail.json记录19行、原值/ID/窗口/原因与清理。
- 产品导出为 *-board-scale*.png，与native整窗分开；*-report-scale*.xlsx是实际六表导出，openpyxl读回13指标、Top10、完整提醒及总班次。final-evidence.json复核字节hash、PNG尺寸、XLSX ZIP。
- 所有当前metadata记录源/CSV/manifest/原save/probe哈希，前后不变，actualexit0。专用qa-native-*.ini仅QA设置，不是用户注册表配置。

历史初次系统200%最小窗：autumn-frame1440-first-system200.png（1866×1431），对应native-first-system200.json及原native-scale1.json；不能算1440通过。首轮同名PNG/XLSX按first-system200备份保留，原metadata中的原路径不能指向其后更新文件作历史证据。旧B fixture图只作旧hash历史，不代表当前真实窗口。

完整结论、13来源表、五项受限排除及四项P2关闭见[验收报告](../LATEST-INFO-ACCEPTANCE-2026-10-01.md)。逐次日志位于.superpowers/sdd/2026-10-01-latest-info；782不同用例来自首轮773pass/1fail/13deselected和定向9pass两次运行。

另获独占放行采集重构前主工程真实背景首页：[默认状态](../astra-visual-audit-2026-10-01/before-main-multi-1440x960.png)、[原Top10](../astra-visual-audit-2026-10-01/before-main-multi-top10-1440x960.png)。同多人缓存/进程DPR1/可见1440×960，metadata为before-main-multi-metadata.json；主源/保护hash不变，actualexit0。功能几何结果不作为新视觉批准。
