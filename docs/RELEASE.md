# CimStats 构建与发布

当前正式版为 **0.1.1**，下载见 [0.1.1 Release](https://github.com/JEREMETRO/CimStats/releases/tag/v0.1.1)。更新与未修复的已知问题记录在[版本记录](../CHANGELOG.md)，发布说明不得将已知问题列为已修复。

## 构建单文件 EXE

按[开发说明](DEVELOPMENT.md)安装依赖，在仓库根目录的 PowerShell 中执行：

```powershell
$env:CIMSTATS_LOCAL_REVIEW_BUILD = '1'
$env:CIM2_BUILD_MANAGED_ROOT = Join-Path $PWD 'game_runtime/Managed'
$env:CIM2_BUILD_PROBE_PATH = Join-Path $PWD 'data/Assembly-CSharp.probe.dll'
.\.venv\Scripts\python.exe -m PyInstaller --clean --distpath dist --workpath build/pyinstaller CIM2_SaveStats.spec
```

输出为 `dist/CimStats.exe`。`build/` 为中间产物，`dist/` 为构建结果，均不提交源码仓库。

需要保留源码快照和完整核验记录的本地验收包使用以下流程，源码整合与测试完成后冻结，再构建唯一目录，保留已有产物：

```powershell
python tools/candidate_package.py freeze --output docs/preflight/local-review.json
.\build_portable.ps1 -Build -SourceManifest docs/preflight/local-review.json -ManagedRoot game_runtime/Managed -BaseAssembly game_runtime/Managed/Assembly-CSharp.dll -LocalReviewWithGameRuntime
```

该流程同样生成单文件 `build/candidates/<唯一名称>/package/CimStats/CimStats.exe`。核验直接检查 EXE 内嵌的版本、法律文本、图标和需要审查的依赖，不能以不存在的 `_internal` 目录代替；旁边保留可读文档和源码核验记录。冻结清单放在被忽略的 `docs/preflight/*.json`，不得复用已有输出文件。本地验收不会上传、修改版本或覆盖已发布资产。

## 发布前验证

1. 执行 `python -m pytest -q`及发布工具测试，核对文档健康检查；实际检查项见[验收清单](testing/acceptance.md)。
2. 运行 EXE，分别加载单人和多人存档。
3. 核对最新信息、线路查询和统计数据。
4. 验证图表及工作簿导出。
5. 更新 `VERSION`、应用元数据和 `CHANGELOG.md`。

本地自动界面验收可用 `CimStats.exe --ui-smoke --save <真实存档> --output <新的验收目录> --expected-dpr 1`。该入口通过正常启动和包内后端解析，不改变普通启动；隔离设置、工作目录与截图，记录同一原生主窗口的 Logo 首帧→界面准备→欢迎页顺序、原存档 SHA-256、实际 DPI、工作簿解析结果、主页面、400×190 图卡和同窗口放大。真实同期柱在普通、紧凑和放大视图中分别命中，检查所属系列、真实日期和浮层范围；同时检查正式标题无版本、二级窗口无图标。后续 DPI 验收可用 `--job <已解析的真实作业目录>` 复用真实数据，并设置相应 `QT_SCALE_FACTOR` 和 `--expected-dpr`。测试须查看截图和文字绘制边界；自动截图本身不等于视觉验收。诊断输出不得放进发布包。完成退出验收后，可另用新目录加 `--keep-open` 留下加载真实存档的同一 EXE 窗口供复核。

## 发布版本

源码提交到 `main`。预览版本使用如 `v0.1.0-pre.1` 的标签，正式版本使用如 `v0.1.0` 的标签。已有 `Test` 预览版保留原下载地址。

在通过验证的对应提交创建标签及 [GitHub Release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)，预览勾选 pre-release，上传 EXE，并在说明中列出版本变化、对应提交和 SHA-256。已发布版本保留，后续版本使用新标签，不覆盖已有资产。合入 `main` 不代表已经构建或发布新的 EXE。

必要文档由 [candidate_package.py](../tools/candidate_package.py)的显式清单统一选择，源码快照包含 `AGENTS.md`与完整的用途文档；构建包仅纳入清单，不递归打包截图、报告或缓存。增加文档时同步清单与[文档索引](README.md)，发布预检复用同一清单。候选包核验不自动上传或创建 Release。
