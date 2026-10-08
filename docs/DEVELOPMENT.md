# CimStats 开发说明

## 环境与启动

使用 Windows x64 和 Python 3.12。在仓库根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe CIM2_SaveStats.py
```

主窗口打开后，选择或拖入 `.save` 文件。解析结果写入 `jobs/`，不需要将生成的结果提交到仓库。

## 目录

| 目录 | 内容 |
|---|---|
| `frontend/` | 界面、共享控件和图标 |
| `src/` | 存档解析、统计计算、导出和测试 |
| `data/`、`game_runtime/Managed/` | 解析资源 |
| `exports/` | 车型和道路参考目录 |
| `tools/` | 构建和开发工具 |
| `docs/` | 用户及开发文档 |
| `jobs/`、`build/`、`dist/` | 本地运行与构建产物，不提交 |

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

组件测试默认使用离屏模式；系统 DPI 和真实窗口验收在桌面上进行。界面截图与输入验收在创建控件前调用共享 `initialize_theme`，确保使用程序的字体与强调色，而非 Fluent 默认主题。需要测试存档的用例使用本地输入，存档不提交到仓库。

地图输入测试截图记录实际窗口尺寸、设备像素比和主题强调色；原生缩放验收可设置 `CIM2_TEST_EXPECTED_DPR`，比例不符时直接失败。`QT_SCALE_FACTOR` 会与系统缩放叠乘，不能用该变量或截图文件名代替实际设备像素比。

应用窗口通过 `frontend/window_workarea.py` 使用当前屏幕的 `availableGeometry()`，该矩形已经扣除任务栏并以逻辑像素表示，不再扣任务栏、标题栏或乘除 DPI。窗口显示、还原及屏幕、缩放、工作区变化时只修正越界几何，合法用户布局保留；小工作区允许窗口低于设计最低尺寸，内容使用已有响应式与滚动，不压缩共享字体、边距、间距或图表。切换页面不申请新的窗口尺寸。辅助应用窗口使用同一检查；最大化与全屏保留原生窗口状态。离屏渲染没有真实桌面工作区，几何回归显式模拟任务栏四边、负坐标多屏和逻辑缩放矩形。诊断请求尺寸使用 `fit_window_to_workarea(window, requested_size=QSize(...))`，并记录实际窗口与工作区边界。

## 调整输出位置

命令行解析可使用 `CIM2_PAYLOAD_DIR` 和 `CIM2_EXPORT_DIR` 指定中间结果及导出目录。`CIM2_RUNTIME_DATA_DIR` 和 `CIM2_MANAGED_ROOT` 可覆盖解析资源的位置。

## 构建

参见[构建与发布](RELEASE.md)。版本来自根目录 `VERSION`，界面元数据在 `src/app_metadata.py`。界面字体复用 `frontend/stats_typography.py`，数据处理保留原始分组和完整性标记。

应用外壳在 `frontend/app_shell.py`，通用控件在 `frontend/ui_kit.py`。图表数据由调用方构造 `ChartData` 和 `Series`，绘制、悬停与缩放由 `frontend/chart_canvas.py` 负责。

触控输入由 `frontend/touch_input.py` 统一管理，通过共享主题安装并自动覆盖后续创建的控件。回归使用 `src/test_touch_input.py` 的 QTest 触屏设备事件，覆盖点按、子控件起始滚动、长按上下文、图表取值、文本选择、菜单及中断清理；不要用直接调用辅助方法或 QScroller.scrollTo 代替实际触控事件验收。离屏 Qt 路径通过后仍须记录物理触屏是否可用。

图表修改遵循[图表与对比模式需求](requirements/charts.md)。公司与同期色柱图例共用 `SeriesLegend`，不能用位置说明替代；更新共享绘图时同时验收普通图、放大图和导出。

业务约定见[产品需求](requirements/product.md)，结构与共享接口见[架构](design/architecture.md)和[控件契约](design/controls.md)。[文档索引](README.md)列出全部必要文档；目录、链接、GitHub 协作入口及发布清单由 [test_repository_documentation.py](../src/test_repository_documentation.py)检查。协作边界见[AGENTS.md](../AGENTS.md)。

线路真实整窗测试可通过 `CIM2_LINE_TEST_SESSION_DIR` 和 `CIM2_LINE_TEST_SESSION_TAG` 指向现有解析目录及文件前缀，只读复用；缺失时跳过并报告，不能用固定旧城市目录代替通用 fixture。Windows 原生命中回归需单独设置 `QT_QPA_PLATFORM=windows` 运行 `src/test_elevation_native_input.py`，完整测试默认离屏并明确报告该项 skip。
