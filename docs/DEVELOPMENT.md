# CimStats 开发说明

## 环境要求

- Windows x64
- Python 3.12
- Cities in Motion 2（本地安装，用于解析存档）

主要依赖：PySide6 6.11.2、PySide6-Fluent-Widgets 1.11.3、matplotlib、openpyxl。

## 快速开始

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe CIM2_SaveStats.py
```

## 项目结构

| 目录 | 用途 |
|---|---|
| `frontend/` | UI、共享控件与品牌资源 |
| `src/` | 解析、统计、导出及测试 |
| `tools/` | 开发工具与构建脚本 |
| `docs/` | 用户和开发文档 |
| `data/` | 运行时数据文件 |

## 游戏依赖

解析使用游戏托管程序集（Managed DLL）和本地探针。环境变量 `CIM2_MANAGED_ROOT` 可指定游戏安装目录的 `CIM2_Data/Managed` 路径。

其他环境变量：
- `CIM2_RUNTIME_DATA_DIR`：运行时数据目录
- `CIM2_PAYLOAD_DIR`：输出目录
- `CIM2_EXPORT_DIR`：导出目录
- `CIM2_ASSEMBLY_SOURCE` / `CIM2_PROBE_OUTPUT`：探针生成路径

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

组件测试可使用 `QT_QPA_PLATFORM=offscreen` 进行无头运行。主窗口和系统 DPI 测试需要真实桌面环境。

## 构建单文件 exe

```powershell
$env:CIMSTATS_LOCAL_REVIEW_BUILD = '1'
$env:CIM2_BUILD_MANAGED_ROOT = '<游戏 Managed 目录>'
$env:CIM2_BUILD_PROBE_PATH = '<探针路径>'
py -3.12 -m PyInstaller --clean CIM2_SaveStats.spec
```

输出位于 `build/onefile-dist/CimStats.exe`。

## 构建说明

- 使用 PyInstaller 6.22.2
- spec 文件为 onefile 模式，所有依赖内嵌
- 构建需要游戏运行时 DLL（从合法安装获取）
- 版本号在 `VERSION` 和 `src/app_metadata.py` 中统一管理

## 代码规范

- 强调字体使用 `frontend/stats_typography.py`
- UI 遵循 Fluent 设计规范
- 数据处理保留原始分组和完整性标记
- 测试覆盖核心解析和统计逻辑
