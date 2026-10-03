# CIM2 SaveStats v0.5.0

发布日期：2026-09-25（本地发布；未配置远程仓库）。
构建源码提交：`aea0c9151d181c0c0dc447ebd5594f6a85891681`。
开发分支：`fix/save-parser-v0.5.0`。正式发布标签：`v0.5.0`。

- 可执行文件：`package/CIM2_SaveStats.exe`，内置运行依赖。
- 源码：`source.zip`，由上述 Git 提交导出，仅包含运行、构建、测试和相关文档。
- 完整历史源码与归档：项目根 Git 仓库。
- 校验：`SHA256SUMS.txt`、`manifest.json`。
- 验证范围与限制：`VALIDATION.md`。

修复短填充存档定位、trolley 识别、线路显示名、中文日志编码；新增两列今日客流效率指标；
移除不可用时刻表编辑入口。真实存档不会被修改。

旧版本保持在 `archive/versions/v0.4-schedule-editor/`，未覆盖。
构建包已纳入根 Git 仓库，不创建嵌套仓库。
