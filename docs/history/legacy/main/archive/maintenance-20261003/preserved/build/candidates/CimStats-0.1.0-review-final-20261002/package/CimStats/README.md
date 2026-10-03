# CimStats

Cities in Motion 2 存档统计桌面工具，作者 **JEREMETRO**。基于 Python、PySide6 和 Fluent Widgets。

**CimStats 0.1.0 已完成品牌与图表接入，正在进行最终校验和发布。** 旧 CIM2 SaveStats 1.0.0 是本地历史版本。运行版本以 `VERSION` 为准；公开源码不附带游戏、Unity 或探针 DLL，完整本地候选包与公开发布内容分别审查。

## 功能

- 最新信息：城市与模拟时间摘要、运营指标、线路亮点、统计图及关键变化提醒。
- 线路查询：筛选、详情、只读时刻表、线路与公司工作簿导出。
- 统计数据：公司、网络、城市三个子选项卡。公司与网络有各自比较模式，城市始终查询全市。
- 日期依据存档模拟时间，缺失不补零，不生成虚构趋势或比较基准。
- 图例显隐、悬停详情、适用的图形切换与放大；区间总值大图提供当前粒度平均值。
- 存档只读，解析结果和日志写入独立任务目录；不提供存档编辑。

## 使用与状态

当前验证环境为 Windows x64、Python 3.12，指标依据主要为 CIM2 v1.6.3。其他游戏版本、模组与系统组合尚不能保证兼容。

没有已确认的公开下载地址。不要把 `dist/` 或 `archive/` 的旧包当作本版 Release。现有本地包包含游戏和 Unity 相关材料，尚不作为可公开分发的发行包。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe CIM2_SaveStats.py
```

命令仅准备Python环境，不安装游戏运行库。解析仍需现有程序要求的本地游戏程序集、探针及相应运行环境，见开发说明。仅源码加pip依赖不保证可解析存档。

已知限制：多公司总体覆盖率暂不显示；无可靠观测时最大运行车辆不可计算；最终包体与原生系统缩放验证需单独记录，组件截图不能替代它们。

## 文档

- [用户指南](docs/USER_GUIDE.md)
- [指标口径](docs/DATA_DEFINITIONS.md)
- [开发与测试](docs/DEVELOPMENT.md)
- [发布流程](docs/RELEASE.md)
- [贡献指南](CONTRIBUTING.md) · [安全报告](SECURITY.md)
- [版本记录](CHANGELOG.md)
- [GNU General Public License v3.0](LICENSE) · [第三方声明](THIRD_PARTY_NOTICES.md)
- [公开分发审计](docs/REDISTRIBUTION_AUDIT.md)
- [项目声明：作者定位与非官方关系](docs/PROJECT_NOTICE.md)

正式截图在最终主窗口验收后选取并脱敏，不用设计图替代实现截图。CimStats是独立工具，不代表游戏开发商、发行商、Microsoft或Qt官方产品。
