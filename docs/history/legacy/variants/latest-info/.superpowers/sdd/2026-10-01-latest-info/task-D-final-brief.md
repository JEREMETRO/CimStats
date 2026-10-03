# D 最终 brief

授权范围交付完成；产品与测试均在 `.worktrees/latest-info`，未 stage/commit，未写主树/主索引，未发消息至其他聊天，未派代理。D 当前 idle，全部自身 Qt 进程已退出，E 独占后不再启动 Qt 或改产品。

- 候选 tracked hunks：`task-D-shared-candidate.patch`，仅 4 个共享产品源 + 5 个受影响旧测试。包含最小 desktop bootstrap 根路径修复；保护方法与原有查询业务不变。
- 新文件：`frontend/latest_info_controller.py`、`frontend/latest_info_exports.py`、`src/test_latest_info_integration.py`（43 项）、`src/test_latest_info_exports.py`（15 项）。
- B 小能力 hunks：公开 `set_workbook_availability`、默认/会话清状态、按钮/menu 启用同步，以及 B 两项既有测试补可用性前提；不整文件认领 B 产品。
- 验证：`task-D-final-bootstrap-gui.log` **132 passed, 3 deselected, exit 0**；`task-D-final-pure.log` **82 passed, exit 0**；最后补正式 launcher 后 `task-D-final-all-integration.log` **43 passed, exit 0**。132 与 43 为两次实际执行，不称为 133 项单次验证。
- 三项排除：`test_fact_card_real_mouse_click_emits_once` 的 FactCard/FactGroupCard 两个参数用例因实际鼠标输入不在授权范围；`test_close_cancels_real_parser_thread_and_backend` 因真实 ParseWorker/backend 不在授权范围。其余旧页面筛选、导航、清理、字节复制均保留验证。
- 入口：frontend 优先同名模块冲突实际 RED→GREEN；异 cwd、清 PYTHONPATH 真实 MainWindow 构造/关闭实际 RED→GREEN。根正式 launcher 与 PyInstaller pathex 已核查，正式 launcher 独立用例通过；未构建/运行 packaged exe。
- 保护：24 方法 AST 与 HEAD 一致，15 文件语法验证；`git diff --check` exit 0，cached diff 为空。132 运行后父再次刷新 line_query_page/test_line_query_layout，E 核验最新依赖。
- 父 7 项依赖基线均排除 D patch；最新记录 `refreshed-peer-baseline-final.json`，不整 worktree copy。

完整行为、RED/GREEN、SHA256、纯缓存 XLSX 回读及准确边界见 `task-D-report.md`；最终 GUI 参数见 `task-D-final-gui-args.json`。最新 integration SHA256：`9BB0EE450404D561B3AB766B3F982876FD75309F7D70981F8752D114C4532ABA`。
