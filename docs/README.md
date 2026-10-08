# 文档索引

文档按用途组织，不区分“现行”与“过去”。只要仍用于运行、开发、数据解释、界面约束或发布，就是本仓库的必要文档；相同规则归并到一个主题，不保留重复副本。

## 使用与协作

| 文档 | 用途 |
| --- | --- |
| [用户指南](USER_GUIDE.md) | 运行、打开存档、筛选与导出 |
| [指标口径](DATA_DEFINITIONS.md) | 聚合规则与模型入口 |
| [开发与测试](DEVELOPMENT.md) | 环境、共享组件、测试与输出 |
| [构建与发布](RELEASE.md) | 构建、标签、Release 和发布前验证 |
| [协作约定](../AGENTS.md) | 修改边界、冲突处理和交付要求 |
| [贡献指南](../CONTRIBUTING.md) · [安全报告](../SECURITY.md) | GitHub 协作入口 |
| [版本记录](../CHANGELOG.md) | 发布变化 |
| [项目声明](PROJECT_NOTICE.md) · [第三方声明](../THIRD_PARTY_NOTICES.md) | 项目与依赖说明 |

## 需求与设计

| 文档 | 用途 |
| --- | --- |
| [产品需求](requirements/product.md) | 页面、范围、默认／公司／同期三种分析模式 |
| [图表需求](requirements/charts.md) | 色柱图例、圆柱、间距、字体、放大摘要与标签 |
| [地图显示](requirements/map-display.md) | 地图数据、方向指标、目录排序、筛选确认与摘要、染色口径和面板停靠 |
| [最新信息](requirements/latest-info.md) | 当日趋势、线路亮点、提醒与导出状态 |
| [架构](design/architecture.md) | 数据流、模块职责、布局与输出边界 |
| [控件契约](design/controls.md) | 共享接口、筛选、菜单、状态和动效 |
| [视觉设计](design/visual-design.md) | 样式来源、图形规格和布局预算 |

## 数据参考与验收

| 文档 | 用途 |
| --- | --- |
| [历史指标](reference/history-metrics.md) | 环形历史、增量／存量、配对分母、总体与最后日摘要 |
| [线路指标](reference/line-metrics.md) | 里程、时间、配车、创建日期、平均客流与周化财务 |
| [运行时解码](reference/runtime-decoding.md) | 存档容器、对象图、探针和输出限制 |
| [字段清单](reference/field-inventory.md) | 可读取、可计算与不可推断的边界 |
| [几何与车型](reference/geometry-and-vehicles.md) | 车型、道路与目录数据 |
| [居民寻路与票价](reference/passenger-routing.md) | 群体参数、票价、随机效用和换乘机制 |
| [多人同步](reference/multiplayer.md) | 共同城市模拟、玩家归属与锁步同步 |
| [工具索引](reference/tools.md) | 解析、工作簿、公式审计和发布预检 |
| [验收清单](testing/acceptance.md) | 数据、界面、自动测试和发布检查 |

## 仓库目录

```text
CimStats/
|-- README.md, LICENSE, CHANGELOG.md
|-- CONTRIBUTING.md, SECURITY.md, THIRD_PARTY_NOTICES.md, AGENTS.md
|-- VERSION, requirements-*.txt, pytest.ini, .gitattributes, .gitignore
|-- CIM2_SaveStats.py, parser_backend.py, *.spec
|-- build_portable.ps1, publish_release.ps1
|-- .github/
|   |-- ISSUE_TEMPLATE/
|   `-- pull_request_template.md
|-- docs/
|   |-- README.md, USER_GUIDE.md, DATA_DEFINITIONS.md
|   |-- DEVELOPMENT.md, RELEASE.md, PROJECT_NOTICE.md
|   |-- requirements/   product.md, charts.md, latest-info.md, map-display.md
|   |-- design/         architecture.md, controls.md, visual-design.md
|   |-- reference/      数据、公式、运行时、多人及工具参考
|   `-- testing/        acceptance.md
|-- frontend/           桌面界面、共享图表与视觉资产
|-- src/                解析、模型、导出与回归测试
|-- tools/              开发、构建和只读预检工具
|-- data/               解析资源
|-- game_runtime/Managed/
|-- exports/            复用的车型和道路目录
|-- optional/           可选存档编辑桥接源码及说明
`-- third_party_licenses/
```

`jobs/`、`build/`、`dist/`和工作区缓存是忽略的本地产物，不属于发布目录。已结束的派工、重复报告和机器绑定路径不再放入文档树；有效规则已归入上方主题，原提交仍可在 Git 中追溯。

根目录协作文件与 `.github` 模板采用 [GitHub 识别的位置](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file)。GitHub 不规定统一业务目录，项目目录保持现有实现和构建约定。新增或移动必要文档时同步本索引、显式打包清单和文档健康检查。
