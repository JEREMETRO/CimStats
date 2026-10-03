# CimStats

Cities in Motion 2 存档统计工具，作者 **JEREMETRO**。支持单人和多人存档，提供最新信息、线路查询及公司、网络、城市统计。

## 下载运行

前往 [Releases](https://github.com/JEREMETRO/CimStats/releases) 下载 `CimStats_x64_v0.1.0_pre.exe`，双击运行，打开或拖入 `.save` 存档即可使用。

- 系统：Windows 11 x64
- 存档：Cities in Motion 2 v1.6.3 的 `.save` 文件
- 预编译版本无需安装 Python

## 从源码运行

安装 Python 3.12，克隆仓库后在项目目录打开 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe CIM2_SaveStats.py
```

## 功能

- **最新信息**：城市摘要、运营指标、亮点线路和关键变化提醒。
- **线路查询**：筛选线路与公司，查看客流、发班、首末班车和时刻表，导出线路及公司工作簿。
- **统计数据**：公司、网络和城市统计，支持多公司环比、单公司同比及小时、日、周、月粒度切换。
- **导出**：图表与工作簿导出。

## 文档

- [用户指南](docs/USER_GUIDE.md)
- [指标口径](docs/DATA_DEFINITIONS.md)
- [开发与测试](docs/DEVELOPMENT.md)
- [构建与发布](docs/RELEASE.md)
- [版本记录](CHANGELOG.md)
- [贡献指南](CONTRIBUTING.md) · [安全报告](SECURITY.md)

项目自有源码采用 [GNU GPL v3.0](LICENSE)。第三方组件保留各自许可，详见[第三方声明](THIRD_PARTY_NOTICES.md)和[项目声明](docs/PROJECT_NOTICE.md)。
