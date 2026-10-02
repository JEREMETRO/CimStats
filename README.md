# CimStats

Cities in Motion 2 存档统计桌面工具，作者 **JEREMETRO**。基于 Python、PySide6 和 Fluent Widgets。

## 下载

从 [Releases](../../releases) 页面下载 `CimStats.exe`，双击即可运行，无需安装 Python 或其他依赖。

| 项目 | 要求 |
|---|---|
| 系统 | Windows 11 x64 |
| 游戏 | Cities in Motion 2 v1.6.3 |
| 存档 | `.save` 格式，支持单人/多人 |

## 功能

- **最新信息**：城市信息摘要、运营指标、亮点线路、统计图及关键变化提醒。
- **线路查询**：替代游戏中线路面板，可在统一窗口筛选显示字段、支持线路与客流基本信息查询与排序，时刻表查询，智能计算发班数、首末班车时间、车公里人次、单班人次等统计信息，支持线路与公司工作簿导出。
- **统计数据**：分为公司、网络、城市三个子选项卡，替代游戏中数据面板，支持多公司环比和单公司同比，支持一个“月”内的历史统计数据查询。

## 快速开始

1. 下载并运行 `CimStats.exe`
2. 点击"打开存档"或将 `.save` 文件拖入窗口
3. 等待解析完成，浏览各统计页面
4. 需要时导出图表或工作簿

## 开发

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe CIM2_SaveStats.py
```

详见[开发说明](docs/DEVELOPMENT.md)。

## 文档

- [用户指南](docs/USER_GUIDE.md)
- [指标口径](docs/DATA_DEFINITIONS.md)
- [开发与测试](docs/DEVELOPMENT.md)
- [发布流程](docs/RELEASE.md)
- [贡献指南](CONTRIBUTING.md) · [安全报告](SECURITY.md)
- [版本记录](CHANGELOG.md)
- [GNU General Public License v3.0](LICENSE) · [第三方声明](THIRD_PARTY_NOTICES.md)
- [项目声明](docs/PROJECT_NOTICE.md)

## 许可

项目自有源代码采用 [GNU GPL v3.0](LICENSE)。第三方组件保留各自原许可，详见[第三方声明](THIRD_PARTY_NOTICES.md)。

CimStats 是独立社区工具，与 Paradox Interactive、Colossal Order 或 Unity 无官方关联。
