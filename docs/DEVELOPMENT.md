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
