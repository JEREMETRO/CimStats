# CimStats 0.1.0 本地目录候选构建准备

本轮只准备脚本与核验。图表、启动／关于整合完成并由主控确认源码冻结后再构建，不抢先打包当前施工源码。用户要求公开前审核包体。

`build_portable.ps1` 默认仅显示准备状态。实际构建必须给出 `-Build`、精确源码快照与 `-LocalReviewWithGameRuntime`。输出为独立的新目录 `build/candidates/CimStats-0.1.0-review-<时间与随机标识>/package/CimStats/`，启动文件为 `CimStats.exe`，支持文件置于 `_internal`。目录布局按照 [PyInstaller 官方 spec 说明](https://pyinstaller.org/en/stable/spec-files.html)；减少每次启动解包是选择该布局的目的，尚未据此声称实测耗时改善。

已整改主 spec、build 和 publish：

- 主 spec 按明确清单选择七份最终文档、68 份已核哈希的原许可、当前构建依赖的必要许可文本、16 项图标、单一 VERSION、元数据与运行时按文件调用的源码。其余可导入的启动／关于模块由依赖分析收集。不会递归带入 docs、static 或 src 内的缓存、测试证据 DLL、截图和历史候选。
- 每个候选有独立工作、缓存和 Managed 阶段目录。脚本没有 Remove-Item、Move-Item、Git 写入、上传、旧 dist 替换或阶段目录清理。失败也保留证据；已有候选目录拒绝覆盖。
- 源码快照涵盖选定源码、构建脚本、批准图标、版本、最终文档和许可；构建前后均比较哈希，也检查增加／缺少文件和 Unity 输入变化。未提交的集成源码用该精确快照绑定，HEAD 仅作来源背景，不能冒称全部内容已提交。
- 当前解析仍需游戏依赖；只对本地审核候选收集明确的 14 项 Managed DLL、现有 Unity 数据 DLL 和新生成探针，不改解析架构。原始基准程序集仍必须匹配 `2bd1ca1353c228fbbcc04df2355d9cbc545f29ddd06ec1c10a6dd62d7bfda4d2`。阶段输入及最终文件均列路径和 SHA-256。
- 构建后生成 `review-inventory.json`、`source-snapshot.json`、`runtime-inputs.json` 与 `CorrespondingProjectSource.zip`。项目源码 ZIP 排除 DLL、真实存档、旧包和研发证据；它不是第三方完整对应源码的替代品，也还需公开前脱敏检查。
- `publish_release.ps1` 改为只读候选核验，`-CheckPublicRelease` 对当前本地游戏依赖候选明确失败。它不会因文件完整性通过就把本地候选标为公开可分发，GitHub 操作留待主控及用户审核。

主 spec 是此次构建入口；历史独立 `parser_backend.spec` 与 `src/verify_candidate.py` 的旧单文件布局不用于此流程。新版工具核验完整目录哈希，不使用旧三文件布局检查。包后端、GUI、导出、启动耗时和退出仍需在真实候选上验证，当前准备测试不能代替它们。

源码冻结后才执行以下步骤；现在未执行：

```powershell
$python = Join-Path $env:LOCALAPPDATA 'Programs/Python/Python312/python.exe'
& $python -B tools/candidate_package.py freeze --output docs/preflight/freeze-0.1.0-reviewed.json
# 使用已核验原始程序集所在的本地目录，勿传入已修改的安装程序集。
./build_portable.ps1 -Build -Version 0.1.0 -PythonExe $python `
  -SourceManifest docs/preflight/freeze-0.1.0-reviewed.json `
  -ManagedRoot '<已核验本地 Managed 目录>' `
  -BaseAssembly '<原始 Assembly-CSharp.dll 路径>' -LocalReviewWithGameRuntime
# 将下方占位符替换为脚本返回的完整候选路径。
./publish_release.ps1 -CandidatePath '<本地候选路径>' -PythonExe $python
```

当前已找到保留的本地原始依赖副本：`recycle_bin/mei_cleanup_20260830/_MEI00000cb02/game_runtime/Managed`，其中 Assembly-CSharp.dll 哈希与上述审计基准一致；读取并复制到新阶段目录不会移出或删除该副本。正式构建仍会再次检查哈希。当前 Steam 安装目录的 Assembly-CSharp.dll 以及旧 `_build_runtime` 中的程序集均不是该基准，不可替代。

公开发布待核：游戏／探针再分发边界、精确新包的依赖许可及对应源码、字体与资产、源码／截图隐私、干净环境功能测试、用户最终包体审核。普通 Qt 等开源 DLL 与项目 Bridge 不因 DLL 后缀被当成游戏程序集。

包顶层另提供可直接打开的许可、通知和精选说明，其哈希与同一源码快照一致。开发文档中指向本地预检记录的入口继续用于施工仓库；公开快照整理时需移除或替换这类入口，不能因当前工作区链接存在就认定源码 ZIP／发行包也包含全部研发证据。
