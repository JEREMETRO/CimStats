# CimStats 构建与发布

当前预览版为 **0.1.0**，下载见 [GitHub Releases](https://github.com/JEREMETRO/CimStats/releases)。

## 构建单文件 EXE

按[开发说明](DEVELOPMENT.md)安装依赖，在仓库根目录的 PowerShell 中执行：

```powershell
$env:CIMSTATS_LOCAL_REVIEW_BUILD = '1'
$env:CIM2_BUILD_MANAGED_ROOT = Join-Path $PWD 'game_runtime/Managed'
$env:CIM2_BUILD_PROBE_PATH = Join-Path $PWD 'data/Assembly-CSharp.probe.dll'
.\.venv\Scripts\python.exe -m PyInstaller --clean --distpath dist --workpath build/pyinstaller CIM2_SaveStats.spec
```

输出为 `dist/CimStats.exe`。`build/` 为中间产物，`dist/` 为构建结果，均不提交源码仓库。

## 发布前验证

1. 执行 `python -m pytest -q`及发布工具测试，核对文档健康检查；实际检查项见[验收清单](testing/acceptance.md)。
2. 运行 EXE，分别加载单人和多人存档。
3. 核对最新信息、线路查询和统计数据。
4. 验证图表及工作簿导出。
5. 更新 `VERSION`、应用元数据和 `CHANGELOG.md`。

## 发布版本

源码提交到 `main`。预览版本使用如 `v0.1.0-pre.1` 的标签，正式版本使用如 `v0.1.0` 的标签。已有 `Test` 预览版保留原下载地址。

在通过验证的对应提交创建标签及 [GitHub Release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)，预览勾选 pre-release，上传 EXE，并在说明中列出版本变化、对应提交和 SHA-256。已发布版本保留，后续版本使用新标签，不覆盖已有资产。合入 `main` 不代表已经构建或发布新的 EXE。

必要文档由 [candidate_package.py](../tools/candidate_package.py)的显式清单统一选择，源码快照包含 `AGENTS.md`与完整的用途文档；构建包仅纳入清单，不递归打包截图、报告或缓存。增加文档时同步清单与[文档索引](README.md)，发布预检复用同一清单。候选包核验不自动上传或创建 Release。
