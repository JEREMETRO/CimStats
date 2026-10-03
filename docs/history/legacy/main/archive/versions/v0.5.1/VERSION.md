# CIM2 SaveStats v0.5.1

构建源码提交：4c1d930。标签：v0.5.1。本地发布，未配置远程。

日常唯一入口：项目根 dist/CIM2_SaveStats.exe。
该目录恰好包含 EXE、README.md、VERSION.json 三个文件。
本目录为正式历史归档，source.zip 为构建时源码快照；不修改 v0.4 或 v0.5.0。

新版的 jobs 位于项目根；独立便携版位于 LOCALAPPDATA/CIM2_SaveStats/jobs。
旧数据迁移清单见 MIGRATION.json；逐文件凭据在项目根 jobs/migrated/2026-09-25/migration.json。
非正式 repaired 包已移至 archive/builds 并标注，不作为日常入口。

发布工具另补充 Git 属性，使今后的归档按原始字节保存，防止换行转换破坏校验值。
当前包也应用此规则；不改变已构建 EXE，source_commit 仍精确指向实际构建源码。
