# 最新状态：根目录法律文档已按用户授权新增

后续新增授权已执行构建准备：主 `CIM2_SaveStats.spec`、`build_portable.ps1`、`publish_release.ps1` 已整改为本地目录候选／只读核验；旧16项source_controls是当时法律审计基线，不再表示这些已授权脚本仍未修改。详见 `docs/preflight/BUILD-PREPARATION.md`。此会话没有改VERSION、入口或业务代码；启动owner正在接入生产0.1.0和metadata。未冻结源码、未构建、未上传；原LICENSE/NOTICES及旧正式包仍保留字节。

2026-10-02 后续发布准备已新增 `docs/PROJECT_NOTICE.md`、只读 `tools/release_preflight.py` 和 18 项内存回归检查；README/RELEASE 只补充必要入口。当前复核见 `docs/preflight/REVIEW.md`，v2 源码清单为 239 可包含、4639 排除、468 待确认；旧 dist 清单为 1 可包含、16 排除、261 待确认。普通依赖与游戏运行文件分别分类；未构建、复制包体、删除、上传或修改 VERSION/索引。图表平均值的新要求已获用户明确授权转交图表子会话统一处理。本节为后续准备状态，不改变下述法律证据或历史品牌候选的限制。

用户授权执行发布计划的文档与分发边界事项。本轮已实际新增：

- `D:/test/CIM2_SaveStats/LICENSE`
- `D:/test/CIM2_SaveStats/THIRD_PARTY_NOTICES.md`
- `D:/test/CIM2_SaveStats/third_party_licenses/`（68 份有来源和哈希的必要许可文本，另有 PROVENANCE.json）
- `D:/test/CIM2_SaveStats/docs/REDISTRIBUTION_AUDIT.md`
- `D:/test/CIM2_SaveStats/docs/REDISTRIBUTION_EVIDENCE.json`
- `D:/test/CIM2_SaveStats/docs/REDISTRIBUTION_PUBLIC_MANIFEST.json`
- `D:/test/CIM2_SaveStats/docs/REDISTRIBUTION_VALIDATION.json`

根 LICENSE 与已验证 GPL v3 正文完全一致。根 THIRD_PARTY_NOTICES 为本轮实际包/边界审计版本，比旧 new-files 候选覆盖更准确，并只按实际旧包匹配选择许可材料；旧 48 个全部安装依赖表只作审计证据，不再等同运行依赖。44 个旧包匹配组件中包括被间接收集的开发库，应在最终构建中考虑去除；没有因此声明它们是必要正常运行依赖。

**原 01-metadata-version-docs.patch 中的 LICENSE/THIRD_PARTY_NOTICES 新增块已经与新根文件冲突，整份旧 01 不可原样应用。** 主控后续应用品牌元数据时必须删去这两项新增并按最新 README/CHANGELOG 等源文档重新生成剩余补丁；不可覆盖本轮根法律文件。旧 NEW-FILES-MANIFEST 的 84 项不再是整目录应用清单，尤其不可将 81 个旧许可候选全部复制覆盖当前选择的 68 项。旧 verify_candidates 的“所有目标不存在”检查因合法新增根文件而不再适用于当前主树；该历史结果不能表示品牌补丁已应用。

元数据 candidate 仍为 `APP_NAME=CimStats`、作者 JEREMETRO、英文原名 `GNU General Public License v3.0`，SPDX GPL-3.0-only；VERSION/metadata/入口/业务/spec/build/publish 未应用或改动。根 Git index、已有正式 EXE 和 source.zip 哈希保持，未构建、上传或改写 Git 历史。

分发边界已形成明确决定：游戏/Unity/探针与未核实的游戏自带 OSS/System/native 文件排除公开允许清单；Windows 字体不打包；字标可编辑 Segoe 轮廓暂排除；批准符号资产仍需明确资产授权/参考来源记录。Bridge 不是自动认定的游戏派生 DLL：4096 bytes，仅 AssemblyRef mscorlib 4.0.0.0、无 managed resources，历史源码与当前源码相符；公开源码建议带自有 C# 源及说明，不带 bin，也不附游戏 DLL。完整组合包仍未通过授权/源码义务核验。

现有 spec/build/publish 的游戏文件收集、根法律文件遗漏、System32/native 来源、整个 docs/optional 的递归选择、以及公开 Git 历史内二进制都是后续工程整改；本轮只记实际事实与必要整改，没有改变构建代码。旧删除/回收站规则由主控对应开发规范处理，本审计不把工程规则与版权授权混为一谈。

特别补充实际 docs 风险：含忽略/隐藏文件扫描后确认非 performance 的 UI 证据缓存有4个 Unity/探针 DLL，spec 文件系统 rglob 会收集，位置与哈希已进入 docs/REDISTRIBUTION_EVIDENCE.json。不能只删 runtime_datas 后认为无游戏DLL；同样要过滤文档证据目录。git archive 仅取HEAD已跟踪内容，不能把这4个当前忽略缓存误报为必然进入源码ZIP。本轮未向docs新增二进制，只读取其元数据/哈希。
