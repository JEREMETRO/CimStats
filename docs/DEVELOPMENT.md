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

组件测试默认使用离屏模式；系统 DPI 和真实窗口验收在桌面上进行。需要测试存档的用例使用本地输入，存档不提交到仓库。

## 调整输出位置

命令行解析可使用 `CIM2_PAYLOAD_DIR` 和 `CIM2_EXPORT_DIR` 指定中间结果及导出目录。`CIM2_RUNTIME_DATA_DIR` 和 `CIM2_MANAGED_ROOT` 可覆盖解析资源的位置。

## 构建

参见[构建与发布](RELEASE.md)。版本来自根目录 `VERSION`，界面元数据在 `src/app_metadata.py`。界面字体复用 `frontend/stats_typography.py`，数据处理保留原始分组和完整性标记。

应用外壳在 `frontend/app_shell.py`，通用控件在 `frontend/ui_kit.py`。图表数据由调用方构造 `ChartData` 和 `Series`，绘制、悬停与缩放由 `frontend/chart_canvas.py` 负责。

触控输入由 `frontend/touch_input.py` 统一管理，通过共享主题安装并自动覆盖后续创建的控件。回归使用 `src/test_touch_input.py` 的 QTest 触屏设备事件，覆盖点按、子控件起始滚动、长按上下文、图表取值、文本选择、菜单及中断清理；不要用直接调用辅助方法或 QScroller.scrollTo 代替实际触控事件验收。离屏 Qt 路径通过后仍须记录物理触屏是否可用。

图表修改遵循[图表与对比模式需求](requirements/charts.md)。公司与同期色柱图例共用 `SeriesLegend`，不能用位置说明替代；更新共享绘图时同时验收普通图、放大图和导出。

业务约定见[产品需求](requirements/product.md)，结构与共享接口见[架构](design/architecture.md)和[控件契约](design/controls.md)。[文档索引](README.md)列出全部必要文档；目录、链接、GitHub 协作入口及发布清单由 [test_repository_documentation.py](../src/test_repository_documentation.py)检查。协作边界见[AGENTS.md](../AGENTS.md)。

线路真实整窗测试可通过 `CIM2_LINE_TEST_SESSION_DIR` 和 `CIM2_LINE_TEST_SESSION_TAG` 指向现有解析目录及文件前缀，只读复用；缺失时跳过并报告，不能用固定旧城市目录代替通用 fixture。Windows 原生命中回归需单独设置 `QT_QPA_PLATFORM=windows` 运行 `src/test_elevation_native_input.py`，完整测试默认离屏并明确报告该项 skip。
