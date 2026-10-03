# B 图表返回按钮键盘修复

根授权的唯一短 Qt 槽已结束。仅修改 `frontend/latest_info_charts.py` 和 `src/test_latest_info_charts.py`，候选源重新冻结。没有启动 MainWindow、原生窗口或 DPI 检查，没有使用全局鼠标或前台操作。

## 缺口与修复

E 的独立事件矩阵发现：`TransparentToolButton` 有焦点时，Enter/Return 不触发 clicked。B 用真实焦点及本地 `QTest.keyClick` 复现两个图、排行/占比两个视图、Enter/Return 两个键的全部 8 种失败组合；Space 的 4 种组合正常。

`icon_button` 改为外观相同的 `AccessibleToolButton` 子类。只处理 Enter/Return：启用且不是自动重复的按下事件调用一次原生 `click()`，对应松键事件只消费；Space 完全保留 Qt 原生处理。禁用时不触发。按钮尺寸、图标、提示、无障碍名称、布局、数据和公开状态合同没有变化。共享统计代码与页面源码没有修改。

## 实际验证

- 新增 17 个参数化用例：12 个双图/双视图/三键真实焦点与单次激活；3 个禁用三键不激活；2 个 Enter/Return 自动重复与松键不重复激活、第二次真实按键仍可激活。
- RED：`10 failed, 7 passed, 42 deselected in 3.98s`，实际进程退出码 `1`。8 个返回矩阵失败及 2 个单按钮 Enter 失败都因 clicked 次数为 0，焦点断言均已通过。
- GREEN：整个 `src/test_latest_info_charts.py` 为 `59 passed in 9.81s`，实际进程退出码 `0`。日志分别为 `task-B-return-key-red.log` / `task-B-return-key-green.log`。
- 与 E `return-key-diagnostic/matrix.json` 中所有现存源的 SHA256 比较，差异只有获授权的上述两文件，比较命令退出码 `0`。
- Qt 测试进程实际退出后独立查询：没有 Python/pythonw/parser_backend 进程残留。

未重跑页面测试或视觉渲染；本次行为测试不代表整窗、原生 DPI 或 E 后续独立事件复查已通过。上一版组件视觉证据保留其原始源码哈希，最终新 manifest 由根重新生成。

## 冻结 SHA256

| 文件 | SHA256 |
| --- | --- |
| frontend/latest_info_page.py（未改） | `7A744950B475ACDC9135AE158D3F329FEAFF7E7DEBE4425262A49AB3FFBE1599` |
| frontend/latest_info_charts.py | `3D153B43D2FABF1D3E818F38B1B9390A5E8BAA83D651452F255B3C381865DA7A` |
| src/test_latest_info_page.py（未改） | `A2E0CBC1F0AAD0BBC427B88B3581738879910FEF41F0E3BA6A487B1AF39E85BD` |
| src/test_latest_info_charts.py | `62B047EE20D7ACF33EECB51D8BEAE9200E2B5DC14E50BA72CAD0D0FA45F13795` |
