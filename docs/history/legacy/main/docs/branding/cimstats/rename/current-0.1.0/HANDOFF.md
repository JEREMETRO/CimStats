# CimStats 0.1.0 更名、元数据与许可候选交接

**最新授权变化：根法律文档与68份必要许可文本已实际新增，见 [ROOT-LEGAL-DEPLOYMENT.md](ROOT-LEGAL-DEPLOYMENT.md)。下列旧01补丁中的 LICENSE/NOTICES 新增块及84项整目录清单禁止原样应用，需按新的根法律文档与主控最新文档重建；品牌/版本/代码仍未应用。** 根审计入口为 `docs/REDISTRIBUTION_AUDIT.md`，当前适用验证是 `docs/REDISTRIBUTION_VALIDATION.json`。以下保留前阶段候选记录。

**当前唯一候选版本为 0.1.0，作者 JEREMETRO。** 旧 1.1.0 方案已标记废弃且旧生成器拒绝运行。本目录全部补丁/资产仅为精确候选，未应用；生产 VERSION 仍为 1.0.0，现有 dist/归档保持原样。未改索引、未运行 Qt、未构建/发布。全部页面测试与 960p 截图仍须用户亲审通过后才可打包。

## 应用材料与顺序

| 材料 | 文件与职责 | 约束 |
|---|---|---|
| `01-metadata-version-docs.patch` + JSON | 12 项：VERSION→0.1.0；新增 src/app_metadata.py、LICENSE、THIRD_PARTY_NOTICES.md；app_paths 的版本函数委托统一元数据；窗口标题读取 APP_NAME；网页标签、README、CHANGELOG 和当前文档 | 不改 desktop main/nav，不与入口 owner 争用；所有显示名称/作者/许可由一个元数据模块供给，VERSION 只有一份。保留旧设置与任务目录。 |
| `NEW-FILES-MANIFEST.json` | 84 个精确新增文件及生产目标、SHA-256；其中 3 项已在 01 patch，另 81 个 third_party_licenses/ 文件按清单复制 | 只应用清单指定文件，排除 __pycache__/.pyc/.pyo。勿连整个 candidate 目录复制；先核对目标尚不存在，避免重复覆盖 01 添加的 3 项。 |
| `../ICON-ASSET-MANIFEST.json` | 16 个已批准图标文件，暂存于 ../assets/frontend/static/branding/cimstats/ | 生产目标 frontend/static/branding/cimstats/；资产候选与批准母版哈希不变，旧 04 main/icon 补丁不能应用。 |
| `02-windows-resource-legal-packaging.patch` + JSON | spec 从统一元数据读取 ProductName/版本/作者/版权/许可范围，配置同源 ICO，显式收集根 LICENSE/NOTICES 与许可树；publish source.zip 纳入这些材料 | 先部署元数据、许可树和图标；frontend/static 已整体收集。spec 排除 docs/branding 审阅中间件，避免把旧候选/审计脚本当正式文档打入 EXE。默认文件名仍 CIM2_SaveStats.exe。 |
| 启动/关于 owner 的最新候选 | docs/branding/cimstats/startup-about/ 下 launcher/bootstrap、紧凑 About 弹窗及 desktop main/navigation | 由该 owner 维护；本候选只触及窗口标题/独立元数据 import。TECHNICAL_APPLICATION_NAME 用于 setApplicationName，APP_NAME 用于 displayName；保持显式 QSettings 键。 |
| `03-optional-executable-name.patch` + JSON | 9 个耦合文件：spec、构建、发布、release_checks、verify_candidate、回归测试和 3 份文档 | 可选，主控确定新 EXE 文件名后整体应用；不得只改 spec.name。新 VERSION.json 显式 executable=CimStats.exe；旧记录缺该字段时兼容 CIM2_SaveStats.exe，不用版本大小推断品牌。旧归档不重命名。 |

patch JSON 记录精确 old/new、阶段输入/输出哈希；SOURCE-BASELINE.json 记录读到的真实 dirty 内容字节哈希、HEAD、tracked status 与索引哈希。01 与 02 均可单独在当前基线做 git apply --check；03 依赖 01/02 的内存重建内容，不能直接在未应用主树上独立检查。对共享 desktop 文件，应用前由主控确认编辑窗口；生产若已漂移，按新内容重建候选，不强制套旧补丁。

## 元数据与关于弹窗

接口详见 API-CONTRACT.md。按用户最新要求，主面板许可名称由统一 `PROJECT_LICENSE_NAME` 给出英文原名 **GNU General Public License v3.0**；only/or-later 精确信息通过 SPDX 标识与详情/文档表达，GPL-3.0-only 选择不变。品牌 CimStats、作者 JEREMETRO、版本读取 VERSION。许可范围是项目自有源代码，不是游戏/Unity/探针或整包授权。

真实候选正文分别为 `new-files/LICENSE` 与 `new-files/THIRD_PARTY_NOTICES.md`；应用后位于项目根，由 shared helper 定位。适用范围、正式来源和仍未完成的整包公开分发核验见 LICENSE-AUDIT.md、LEGAL-HANDOFF.md。不得把项目许可选择和当前游戏运行库组合的公开发行授权混为一谈。

## 验证结果与限制

verify_candidates.py 全程在内存重建并核对 23 个阶段文件的补丁、锚点、哈希及 Python/spec AST；核对 84 个新增文件；检查英文原名许可、作者、BOM VERSION、冻结根/源码根和图标/协议路径；对可选发布校验通过 **51 项纯内存接受/拒绝检查**；两份 PowerShell 候选语法无错误。01/02 git apply --check 成功。索引及读取的生产源文件哈希保持，未创建 EXE 文件或导入 Qt。

正式证据见 STATIC-VALIDATION.json。批准图标此前通过 RGBA 尺寸/透明度、小尺寸光学校正、ICO 帧逐字节与独立解码检查，证据 ../ICON-VALIDATION.json；此次图标素材保持。Qt 运行、紧凑弹窗呈现、全页测试、960p 截图、用户亲审、Windows 资源序列化、最终冻结包及许可/源码义务尚未验证。静态检查通过不代表可打包或可公开发行。

关于弹窗 owner 的独立补充证据 `../../startup-about/evidence/document-buttons.json` 已只读核对：真实 LICENSE 与 THIRD_PARTY_NOTICES.md 均标记只读按钮路径验证通过，记录哈希与当前候选一致。LICENSE 为 35149 bytes / `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`；NOTICES 为 9351 bytes / `ec84c6052d0949e27177b0cc3580c29d9810181e3ee8204ed9b090edf66d04b1`。这是该 owner 的弹窗文档测试，不扩大为本轮运行 Qt、全页截图批准或整包分发审计结论。
