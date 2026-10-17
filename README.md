# CimStats

Cities in Motion 2 存档统计工具，作者 **JEREMETRO**。支持单人和多人存档，提供最新信息、地图显示、线路查询及公司、网络、城市统计。

## 下载运行

前往 [0.2.1 正式版](https://github.com/JEREMETRO/CimStats/releases/tag/v0.2.1)下载 `CimStats_x64_v0.2.1.exe`，双击运行，打开或拖入 `.save` 存档即可使用。既有正式版与 `Test` 预览版保留在 Releases 中。

相较于 0.2.0，0.2.1 新增城市同期对比及单线 PNG、JPG、矢量 PDF 导出，地图采用矢量绘制，改善缩放细节与站点定位，并修复规划菜单取消勾选和搜索展开动画。

- 系统：Windows 11 x64
- 存档：Cities in Motion 2 v1.6.3 的 `.save` 文件
- 预编译版本无需安装 Python

“打开存档 → 地图显示”在大型存档解析和首帧准备期间仍需等待，全城视图及连续缩放可能出现短暂停顿，见[版本记录](CHANGELOG.md#已知问题)。

## 从源码运行

安装 Python 3.12，克隆仓库后在项目目录打开 PowerShell：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe CIM2_SaveStats.py
```

## 功能

- **最新信息**：城市摘要、运营指标、亮点线路和关键变化提醒。
- **地图显示**：单线方向与指标、线网筛选及染色、建筑服务线路选择与多线比选，支持地图导出。
- **线路查询**：筛选线路与公司，查看客流、发班、首末班车和时刻表，导出线路及公司工作簿。
- **统计数据**：公司、网络和城市统计，提供默认、多公司对比、同期对比，以及小时、日、周、月粒度切换。
- **导出**：图表、工作簿与单线成品线路图，支持画幅、日夜风格、公司标志及信息字段设置。

## 文档

- [文档索引与目录结构](docs/README.md)
- [产品需求](docs/requirements/product.md) · [图表需求](docs/requirements/charts.md) · [协作约定](AGENTS.md)
- [用户指南](docs/USER_GUIDE.md)
- [指标口径](docs/DATA_DEFINITIONS.md)
- [开发与测试](docs/DEVELOPMENT.md)
- [构建与发布](docs/RELEASE.md)
- [版本记录](CHANGELOG.md)
- [贡献指南](CONTRIBUTING.md) · [安全报告](SECURITY.md)

项目自有源码采用 [GNU GPL v3.0](LICENSE)。第三方组件保留各自许可，详见[第三方声明](THIRD_PARTY_NOTICES.md)和[项目声明](docs/PROJECT_NOTICE.md)。
