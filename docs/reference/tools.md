# 解析、审计与发布工具索引

从仓库根目录使用已安装依赖的 Python 3.12。工具职责见下表；路径是当前仓库的相对路径，不指向本机安装目录或已结束任务的证据目录。

| 工具 | 用途 |
| --- | --- |
| [extract_runtime_data.py](../../src/extract_runtime_data.py) | 显式输入存档，解析运行时对象与历史，输出任务 CSV |
| [build_line_workbook.py](../../src/build_line_workbook.py) | 线路、班次、配车与核定速度工作簿 |
| [build_company_workbook.py](../../src/build_company_workbook.py) | 公司及分制式周化收支工作簿 |
| [build_passenger_workbook.py](../../src/build_passenger_workbook.py) | 客流与运行字段工作簿 |
| [build_field_inventory.py](../../src/build_field_inventory.py) | 现有运行时 CSV 的字段／记录清单，需显式提供实际输出 TAG |
| [extract_geometry_catalog.py](../../src/extract_geometry_catalog.py) | 本地安装资产中的车型及道路参数目录 |
| [audit_road_formula.py](../../src/audit_road_formula.py)、[audit_duration_formula.py](../../src/audit_duration_formula.py) | 程序集与独立里程／时间公式核对 |
| [audit_line_dates.py](../../src/audit_line_dates.py)、[audit_opening_date_formula.py](../../src/audit_opening_date_formula.py) | 创建、改线和平均客流时间基准核对 |
| [audit_runtime_metrics.py](../../src/audit_runtime_metrics.py)、[audit_running_vehicle_window.py](../../src/audit_running_vehicle_window.py) | 缓存／重算值和小时运行车辆口径核对 |
| [audit_company_period.py](../../src/audit_company_period.py)、[validate_company_period.py](../../src/validate_company_period.py) | 周化财务与报表范围核对 |
| [dashboard_qa.py](../../tools/dashboard_qa.py)、[legacy_ui_qa.py](../../tools/legacy_ui_qa.py) | 本地界面检查，证据写入忽略的工作目录 |
| [candidate_package.py](../../tools/candidate_package.py) | 显式源码／文档清单、构建输入快照和候选包核验，不自动发布 |
| [release_preflight.py](../../tools/release_preflight.py) | 只读文件与文档链接预检，报告不等于发布批准 |

主流程推荐使用桌面程序打开或拖入存档。命令行解析示例：

```powershell
$env:CIM2_PAYLOAD_DIR = Join-Path $PWD 'jobs/local-parse/payload'
$env:CIM2_EXPORT_DIR = Join-Path $PWD 'jobs/local-parse/exports'
.\.venv\Scripts\python.exe src/extract_runtime_data.py 'path/to/input.save'
```

部分探索脚本保留样例默认值，使用前检查其参数、输入和输出位置；未提供实际输入时不能声称已验证。单份存档的审计结论不代替全部数据、不同公司或多人场景的回归测试。工作簿工具使用实际解析 TAG，不能照搬私人样例名称。

运行与测试见[开发说明](../DEVELOPMENT.md)，候选包、标签和 Release 见[发布说明](../RELEASE.md)。
