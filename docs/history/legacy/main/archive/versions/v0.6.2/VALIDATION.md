# v0.6.2 验证记录

- 构建源码提交：`96e8361cf645a80b3571a07317e6e1e913d14401`；冻结 EXE SHA-256：`f99cad27f46671700605c30edff7c8f62daeab2af8c1794f9e1765f6da337c55`。`release_checks.py candidate`、发布脚本中的 73 项测试及发布后包体检查通过。
- 对确切 EXE 运行 `verify_candidate.py`：单人 `秋山市n3.save`、`秋山市n4.save`、多人 quicksave 和 Modifier 工程的 `望春市_test.save`、`望春市_Friday2.save`，共五份。每份输入 SHA-256 未变，UTF-8 解析成功，各输出两份无错误单元格的 XLSX；见原样保存的 `validation.json`。其中 `job` 是隔离工作树的实际验证路径。
- 已审计基准程序集备份：`D:\test\CIM2_Modifier\jobs\backups\Assembly-CSharp.dll.2BD1CA1353C228FB.bak`，SHA-256 为 `2bd1ca1353c228fbbcc04df2355d9cbc545f29ddd06ec1c10a6dd62d7bfda4d2`。构建在临时目录由此备份重新生成探针，SHA-256 为 `43863094358ec5fe222b567a984746a96000c68bfa1ba362c6a78f1bd3ab885a`。其余 Managed DLL 取自游戏安装目录；打包后使用 `CArchiveReader` 抽取并逐文件比对 15 项内容，详见 `embedded_runtime.json`。
- 即使外部 `CIM2_MANAGED_ROOT` 指向已修改的安装目录，冻结版解析进程仍使用其内嵌程序集与探针；对 n3 的 62,671 条历史行和当前公司价值与基准探针输出一致。冻结版 GUI 在 Windows 隐藏启动后保持运行 10 秒。
- 使用实际 Windows 主窗口做四看板、多公司、多分组、比较、排序、原始小时追溯、查询中关闭与连续切换存档检查。`evidence/overview.png`、`lines.png` 显示原有现代化界面，`statistics.png`、`chart_dates.png` 显示新增看板与可见日期坐标。这些交互截图来自同一提交的源码 GUI；冻结 EXE 另做启动与后端验证。
- 真实公司价值复核：多人两家公司及单人一家公司，历史期末值与当前快照分别相差 3.31、1.57、1.28 货币单位，见 `evidence/real_value_check.json`。独立验收另核对部分小时的平均值在小时／日／周／月粒度一致、1%→2% 不误触 5 百分点提醒、缺失小时断线、公司颜色固定、同名标签与无效筛选清空旧结果。
- 对 Modifier 程序集快照的字段名顺序及 IL 操作码序列比较见 `evidence/assembly_compat.json`；解析相关 `DataSerializer`、`HistoryData`、`CompanyData`、`DataManager`、`PlayerData` 结构检查一致。此项与两份存档实测支持当前样本的兼容性，不推断所有未来模组版本。
- 发布前旧正式版 `dist/` 与既有 `archive/versions/v0.5.1/package/` 均验证为 v0.5.1 且内容匹配；发布脚本将新包送入主目录 `dist/`，旧归档未覆盖。主目录的两个未跟踪研究探针未修改。
- 发布后主目录重跑 73 项测试，`release_checks.py` 对 `dist/` 和本归档包体均通过，归档清单所列文件哈希全部相符，`dist` EXE 与归档 EXE 逐字节一致；从主目录 `dist/CIM2_SaveStats.exe` 隐藏启动后保持运行 10 秒。
