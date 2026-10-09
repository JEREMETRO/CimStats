# CimStats 构建与发布

当前正式版为 **0.2.0**，下载见 [0.2.0 Release](https://github.com/JEREMETRO/CimStats/releases/tag/v0.2.0)。更新与未修复的已知问题记录在[版本记录](../CHANGELOG.md)，发布说明不得将已知问题列为已修复。

根目录 `VERSION` 统一驱动关于页面、EXE 文件／产品版本及包名。0.2.0 发布说明以 0.1.3 为对照，重点介绍新增地图页面及单线、线网、规划功能。三项已知问题的功能路径、操作与现象见[版本记录](../CHANGELOG.md#已知问题)。

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

交付目录沿用 `dist/v<版本>/`，仅放 `CimStats_x64_v<版本>.exe`、`CimStats_<版本>_source.zip` 和 `SHA256SUMS.txt`。`dist/CimStats.exe` 为当前本地版本的快捷副本，替换前保留旧副本。候选包、内嵌文件清单、核验记录、发布说明及文档修订放在被忽略的 `jobs/release-<版本>-<日期>/`，构建中间文件保留在 `build/`。移动和复制后核对 SHA-256，旧版本目录保留。原 EXE、源码快照和已冻结 ZIP 保持构建时内容，文档修订单独记录对应提交。

本地候选包标记为 `local_review_only`，公开发布条件由核验记录中的 `public_blocking_files` 和 `remaining_gates` 列出。公开预检通过后再创建正式标签和上传资产，包完整性核验仅确认文件与冻结清单一致。

## 发布前验证

1. 执行 `python -m pytest -q`及发布工具测试，核对文档健康检查；实际检查项见[验收清单](testing/acceptance.md)。
2. 运行 EXE，分别加载单人和多人存档。
3. 核对最新信息、线路查询和统计数据。
4. 验证图表及工作簿导出。
5. 更新 `VERSION`、应用元数据和 `CHANGELOG.md`。

本地自动界面验收可用 `CimStats.exe --ui-smoke --save <真实存档> --output <新的验收目录> --expected-dpr 1`。该入口通过正常启动和包内后端解析，不改变普通启动；隔离设置、工作目录与截图，记录同一原生主窗口的 Logo 首帧→界面准备→欢迎页顺序、原存档 SHA-256、实际 DPI、工作簿解析结果、主页面、400×190 图卡和同窗口放大。地图等待当前视角完整帧，记录单线、线网、规划及线网右侧标签在两种窗口尺寸下的截图。真实同期柱在普通、紧凑和放大视图中分别命中，检查所属系列、真实日期和浮层范围；同时检查正式标题无版本、二级窗口无图标。后续 DPI 验收可用 `--job <已解析的真实作业目录>` 复用真实数据，并设置相应 `QT_SCALE_FACTOR` 和 `--expected-dpr`。测试须查看截图和文字绘制边界；自动截图本身不等于视觉验收。诊断输出不得放进发布包。完成退出验收后，可另用新目录加 `--keep-open` 留下加载真实存档的同一 EXE 窗口供复核。

仅检查正常冷读取全过程时，在上述 `--save` 入口加 `--loading-profile-only`。独立诊断模块记录统计、地图快照与首帧时刻、连续界面事件间隔、提前进入地图的响应、进程与内存、存档校验和及持久化缓存状态；请求 1440×960 窗口，在真实可用工作区内约束并记录实际尺寸，保留真实动画。该模式不接受复用作业目录，源码和冻结程序使用相同记录字段，诊断结果写入指定的新目录。

全部视图及辅助应用窗口按实际屏幕工作区验收，记录屏幕逻辑矩形、可用工作区、窗口／外框几何和实际设备像素比；不同任务栏位置、多屏及还原后的窗口保持可达。不能强制固定屏幕之外的大窗口冒充目标分辨率，也不能以请求尺寸代替实际尺寸。高度不足时先消耗可伸缩空白，再使用既有滚动与响应式布局，保留共享字体、边距、间距和图表尺寸。

地图诊断另用真实 Qt 鼠标与键盘事件验收拖移缩放、选线后的悬停搜索及回车、目录排序保留选线、建筑命中菜单的原生名单与单选／全选，以及客流输入与滑块双向同步、确定前保持地图和确定后收起更新。地图截图等待当前完整帧和导航动画结束后至少 300 毫秒，证据记录窗口与画布实际尺寸，不能用文件名中的请求尺寸代替屏幕限制后的实际尺寸。日间、全日、高峰平均间隔和客流图例分别截图，核对图例独立区域与地图视口不相交；`map-current.png` 通过正式导出入口生成，按实际地图高度加图例区域高度核对完整图像尺寸，图例不得覆盖地图内容。输入或状态核对失败会使验收失败，原有图卡与工作簿检查继续执行。

## 发布版本

源码提交到 `main`。预览版本使用如 `v0.1.0-pre.1` 的标签，正式版本使用如 `v0.1.0` 的标签。已有 `Test` 预览版保留原下载地址。

在通过验证的对应提交创建标签及 [GitHub Release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)，预览勾选 pre-release，上传 EXE，并在说明中列出版本变化、对应提交和 SHA-256。已发布版本保留，后续版本使用新标签，不覆盖已有资产。合入 `main` 不代表已经构建或发布新的 EXE。

公开发布说明优先鸣谢贡献者，链接其 GitHub 主页与 PR，重点介绍其实际贡献；维护者的合并调整仅作简要补充，不以合并过程取代版本更新。不在公开 Release 中列出“验证”章节、测试数量或内部检查记录；这些记录保留在忽略的工作目录中。仍未修复的已知问题继续单独列出。

必要文档由 [candidate_package.py](../tools/candidate_package.py)的显式清单统一选择，源码快照包含 `AGENTS.md`与完整的用途文档；构建包仅纳入清单，不递归打包截图、报告或缓存。增加文档时同步清单与[文档索引](README.md)，发布预检复用同一清单。候选包核验不自动上传或创建 Release。
