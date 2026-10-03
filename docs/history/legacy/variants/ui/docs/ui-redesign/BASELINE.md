# 归并核验与开发基线

日期：2026-09-29。归并完成后、产品代码修改前核验。

- 原始主分支提交：2617bdee29c832c7673146a0f3e0eafa8d31ef25。
- 七个旧工作区路径均已移出D:/test；Git工作区登记仅剩主项目。
- 执行归档核验脚本after：2,658个需保留文件映射、1,048个独有blob、479种主项目已存哈希、1,682个原有制品均通过。
- 回收站记录共14项，工作区及登记均可恢复；没有清空回收站，不计作已释放磁盘空间。
- 基线测试：`py -3.12 -m pytest -q`，167 passed，1 warning，29.36秒。警告为Fluent Widgets的QHoverEvent弃用警告，不是测试失败。
- 主项目独有参考图、两个inspect探针、清理归档不收录进本轮产品提交，不删除、不覆盖。
- 应用原生create_worktree工具返回Not a git repository（聊天根目录为D:/test）；改为在真实Git项目内使用Git工作区初始化，路径限定为D:/test/CIM2_SaveStats/.worktrees/。

详细清理证据见主项目archive/workspace-consolidation-2026-09-29/清理报告.md及同目录清单。
