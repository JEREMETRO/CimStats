# CimStats redistribution audit

审计日期：2026-10-02（Asia/Shanghai）。本轮范围：当前实际源码、spec/build/publish、旧 1.0.0 EXE 与历史 source.zip、可选 Bridge、系统字体与品牌候选。用户授权选择的项目自有代码许可为 **GNU General Public License v3.0，GPL-3.0-only**；作者 JEREMETRO。**该选择已确认；整个现有便携包和历史源码包尚未通过公开再分发审计。**

## 分发决定

| 材料 | 实际来源/证据 | 公开源码能否携带 | 公开二进制能否携带 | 必要整改/条件 |
|---|---|---|---|---|
| 项目自有 Python/C#/HTML/CSS/JS | 当前文件与源码控制哈希见 REDISTRIBUTION_EVIDENCE.json | 可携带确认属于项目自有的源文件，GPL-3.0-only | 可携带项目编译部分，但完整组合当前未通过 | 保留 copyright/许可/修改告知；不得把第三方反编译代码、游戏数据、字体轮廓一起泛称自有；按 GPL 提供相应完整源码 |
| 实际随包开源库 | 冻结模块/文件表匹配；许可副本有来源和 SHA | 按各自原许可；可提供项目依赖声明和相应源码，不必复制整个安装环境 | 条件允许；最终包的版本、许可、告知及源码义务未全验 | Qt Charts / Virtual Keyboard / Fluent GPL 路径、其他 LGPL/MPL/BSD/MIT 等分开处理；无商业授权证据 |
| Assembly-CSharp / firstpass / UnityScript | 从游戏 Managed 目录取得；旧 EXE 精确哈希见下表 | 不携带原 DLL 或从其提取的非项目自有实现 | **排除**，未取得公开再分发证据 | 改为用户合法安装提供所需运行库，或取得明确权利人授权；本轮不改构建行为 |
| UnityEngine.dll | 游戏安装与旧包一致哈希；托管 assembly version=0.0.0.0，不能当作 Unity 产品版本 | 不携带 DLL 或未获授权引擎源码 | **排除**，旧版适用授权未证实 | 现代 Unity runtime 条款不能替代该游戏/旧 Unity 授权；须查适用历史条款及实际授权主体 |
| Assembly-CSharp.probe*.dll | patch_singleton_probe.py 基于原游戏 DLL 的修改副本；当前/EXE/source.zip 哈希不同 | 补丁脚本的项目自有实现可按项目许可；DLL **排除** | DLL **排除** | 修改少量方法不会把整份游戏程序集变成项目自有；本地生成方式仍需另行核实适用法律和游戏条款 |
| 游戏自带 Boo/Zlib/Mono/System DLL | 版本与 SHA 见下表，名字提示开源来源但不是授权证据 | 具体原文/来源核定前不复制源码或 DLL | **暂排除实际游戏提供的二进制** | 核实准确对应上游版本、补丁、版权/许可及组合条件；不能以“都是私有”或“都是 GPL”概括 |
| SteamworksManaged.dll | assembly version 1.0.0.0；来源游戏 Managed | 不纳入允许清单 | **排除**，SDK/封装作者及分发条款未证实 | 查该确切封装与 Steamworks SDK 条款/授权；不能用 Steam 用户协议推导 SDK 分发权 |
| Optional Bridge source | optional/save_editing/CIM2RuntimeScheduleBridge.cs；反射辅助代码 | 可携带项目自有源码与说明，GPL-3.0-only | 单独项目 DLL 为条件候选，与游戏组合包仍未确认 | 保留对应源码与告知；建议公开源码不带 bin；声明非正常统计入口，不附游戏运行库 |
| Optional Bridge DLL | 4096 bytes，SHA 71804db097baa6665e5c40207bd41de7a704ad226079cef9f25de3a508b7eadd；仅 AssemblyRef mscorlib 4.0.0.0，无 managed resources | 公开源码建议排除编译产物 | 不将其等同游戏派生 DLL；可按条件单独判断，当前无发布批准 | bridge.rsp 虽含 /r:Assembly-CSharp，但实际产物未形成该 AssemblyRef；需绑定精确源码/工具链并确认游戏使用边界 |
| Microsoft VC/UCRT/API-set、Windows ICU | 旧 EXE 实際 native DLL 哈希清单；spec 有 System32 复制策略 | 不把系统二进制当项目源码带入 | 未核实对应取得方式/REDIST条件的文件 **暂排除** | 核实确切版本与允许分发清单；使用获准的 Redistributable/系统前置要求；并分别区分 ICU 上游开源授权与 Windows 文件来源 |
| Windows UI fonts | stats_typography 从本机 Windows Fonts 加载；FONT_FAMILY=Microsoft YaHei UI；无生产字体资产 | 可携带使用字体名称的代码；**不携带字体文件/字体子集** | 应用可使用用户系统字体；**不嵌入未经授权字体** | 本机显示不等于字体再分发；保持本机字体回退 |
| Matplotlib bundled fonts | 旧 EXE 实际 38 个 TTF；DejaVu/STIX/CM，与 Windows 字体分开 | 若复制需逐项遵循字体许可 | 许可条件下可候选携带，当前完整声明未全验 | 已保留 DejaVu/STIX 原文；CM 和其他字体的精确原声明及必要 notices 须复核；可移除不需要的图表/字体依赖减少义务 |
| 批准的 C+三柱符号 PNG/ICO/SVG | 用户已批准设计；16 个资源精确清单；母版无 href/image/text/font | 自有设计部分可候选；版权来源/资产授权声明待齐 | 条件候选，不等于第三方 IP 已清除 | 记录参考图权利链/是否受保护元素及项目资产许可；用户批准仅为设计批准；不得附带参考照片 |
| Segoe UI 字标完整单词 PNG | 用户资产生成流程，从 Segoe UI Semibold 输出文字图形 | 可候选携带完整词语图像，不能变成逐字图库 | Windows 字体 FAQ 支持一般文字图像/标志输出；依其条件 | 保持完整单词图形；不分发字体、不把字形本身重新许可；核对使用产品/系统授权条件 |
| 字标 SVG 与 outline JSON | review README/JSON 明示 Segoe UI Semibold glyph→path | **暂排除可编辑轮廓源** | **不据现有证据默认批准轮廓资产** | 官方 FAQ 对图形输出与字体格式转换有不同规则；缺乏该具体可编辑轮廓的明确范围证据，改为原创字标/可授权字体或进一步确认 |
| 实际存档、游戏数据、反编译研究、历史发布档案 | data/analysis/jobs/archive/docs 中可能混入非项目材料 | 不以目录整体作为已清除源码发布 | 不作运行时自动输入 | 按明确允许清单选择；公开 Git 历史若含原 DLL/旧包，同样不是纯源码发行；不要原样公开当前整仓库或历史档案 |

“排除/暂排除”是本项目当前公开分发允许清单的决定，不声称所有同名开源组件在法律上都禁止再分发。许可条件满足后可重新纳入。没有进行 Git 历史改写、删除旧档案或远程发布。

## 官方许可依据与可确认边界

Steam 的 [Cities in Motion 2 页面](https://store.steampowered.com/app/225420/Cities_in_Motion_2/)确实链接该游戏 EULA；[EULA 入口](https://store.steampowered.com//eula/225420_eula_0)转到 [Paradox User Agreement](https://legal.paradoxplaza.com/eula)。当前官方文本更新于 2026-01-21，§1 给予受条件限制的个人使用许可，§5 支持非商业 UGC，但 UGC 权利只覆盖新增原创内容，不转让游戏或第三方材料。故 UGC/模组支持不证明可公开携带原游戏 DLL或整份修改游戏 DLL。[Steam Subscriber Agreement §2](https://store.steampowered.com/subscriber_agreement/)亦无本项目的独立游戏文件分发授权；相关适用法律例外不在本审计中推定。

[Unity Editor Software Terms §2.2](https://unity.com/legal/editor-terms-of-service/software)（2026-06-30）允许满足条件的创作者将 Runtime 与自己的项目集成分发；其开头亦区分创作者与其他主体。现有 UnityEngine.dll 由 CIM2 安装取得，未找到授权本项目抽出再打包的旧 Unity 条款/书面许可。不能把现代条款或 Unity 开源参考代码许可套到该 DLL。以上当前条款查阅不追溯认定用户过去的合同版本。

[Qt Charts 6.11.2](https://doc.qt.io/qt-6.11/qtcharts-index.html#licenses)、[Virtual Keyboard 6.11.2](https://doc.qt.io/qt-6.11/qtvirtualkeyboard-index.html#licenses-and-attributions)、[Qt licensing](https://doc.qt.io/qt-6.11/licensing.html)及实际 Fluent Widgets 许可支持选择项目 GPL v3 路径。LGPL/MPL/宽松许可及原生内置库保持原条款；完整对应源码、构建材料、告知/替换条件仍须完成。PyInstaller 的 [bootloader exception](https://pyinstaller.org/en/stable/license.html)不会单独决定项目许可。

[Microsoft font FAQ](https://learn.microsoft.com/en-us/typography/fonts/font-faq)区分 Windows 本机使用、完整词句文字图像/标志输出、字体文件/格式转换与嵌入。本报告依此区分运行 UI、PNG 字标与 outline 源；不宣告 Windows 字体获得 GPL。有关 VC 文件，[Microsoft redistribution guidance](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170)要求对应许可与 REDIST 清单，不能仅因 DLL 被找到就复制。

## 当前配置和旧包的具体问题

1. CIM2_SaveStats.spec：runtime_datas 遍历 staged Managed 的所有 *.dll（仅排除 mscorlib），另携带 data/UnityEngine.dll 与 fresh probe；显式 QtCharts、VC/ICU，docs 全目录只排除 performance。原生依赖/字体还可通过 hooks 被间接收集，不能只读 requirements 或明写的 binaries 判断包内容。parser_backend.spec 同样带探针与 UnityEngine。
2. build_portable.ps1：将合法安装里的全部 Managed DLL 复制到 staging 并生成 fresh probe；游戏原始 Assembly-CSharp 哈希限制是内容完整性证据，**不是版权/分发授权**。
3. publish_release.ps1：git archive 明确包含 data/Assembly-CSharp.probe.dll、data/UnityEngine.dll 和整个 optional/docs；跟踪的 optional/bin Bridge 与所有后来提交的 branding 中间件都会进入选定目录。当前 archive 命令未选根 LICENSE、THIRD_PARTY_NOTICES.md 或 third_party_licenses，spec 也未收集这些根目录法律文档。此轮添加文档不会自动改变包体。
4. 旧 EXE 实际含 16 个游戏相关 DLL、221 个其他 native DLL、38 个 Matplotlib 字体；当前生产 static 无字体文件，旧 EXE 无 Microsoft YaHei/Segoe TTF。Bridge DLL 未在旧 EXE 匹配。旧 source.zip 实际含 3 个 DLL，且没有任何 license/notice/copyright 命名条目。已提取的旧 EXE 5 个许可/元数据条目不能代表所有依赖告知齐全。
5. 旧源码包 probe SHA fd456ab75670a6b8b727f854d3a67b4a8f8aa046cd4574233c1d12f9a6753439；旧 EXE fresh probe SHA 43863094358ec5fe222b567a984746a96000c68bfa1ba362c6a78f1bd3ab885a；当前工作树 probe SHA 9ab2eca20d376e5ddca7733e674890917b6a4f5a2a28c92d8238d7bc3e7dd70e。不能混作同一文件，也不能声称历史源码 ZIP 已逐字包含 EXE 内探针；这是实际内容核对，不是重建结果。

## 实际游戏 DLL 清单

补充核验当前 docs 的隐藏/忽略文件：共发现 141 个 DLL/EXE/字体/ZIP/存档类路径，其中 137 个在 spec 已排除的 performance 内。其余 **4 个 DLL 当前会被 documentation_datas 收集**：`docs/ui-redesign/card-comparisons-evidence/runtime/2880x1920-200pct-cache/` 与 `docs/ui-redesign/city-evidence/runtime/2880x1920-200pct-cache/` 各含 UnityEngine.dll 和 Assembly-CSharp.probe.dll，精确哈希见 REDISTRIBUTION_EVIDENCE.json 的 docs_packaging_scan。spec 的文件系统 rglob 不遵循 .gitignore；即使移除显式 runtime_datas，仍须过滤这些文档证据目录，否则受限 DLL 可从 docs 路径再次入包。git archive 则只取 HEAD 已跟踪文件，这些忽略缓存不会仅因位于 docs 就自动进入源码 ZIP；后续提交 branding 中间件或其他证据文件仍会改变其归档内容。本轮法律审计脚本仅内存读取二进制，未将 EXE/DLL 提取到 docs。

下列 assembly version 是 CLI 元数据版本；多个 0.0.0.0 不能推导游戏/Unity 产品版本。游戏范围按本项目审计的 CIM2 v1.6.3 记录；当前 Steam 目录 Assembly-CSharp 已被修改，与审计原版哈希不同，未改动安装目录。

| 旧 EXE 内文件 | CLI assembly version | SHA-256 | 当前公开决定 |
|---|---|---|---|
| `data/Assembly-CSharp.probe.dll` | 0.0.0.0 | `43863094358ec5fe222b567a984746a96000c68bfa1ba362c6a78f1bd3ab885a` | 排除，授权/原许可尚未核实 |
| `data/UnityEngine.dll` | 0.0.0.0 | `f2bb33a090672618cfbcaeb0989e549471d00f99c5615f90715c8661a5bf2f7b` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/Assembly-CSharp-firstpass.dll` | 0.0.0.0 | `187c5e9cd532e5cc9b1e0558949b0cf4ba0b147f8ce331a43f29c899675598d8` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/Assembly-CSharp.dll` | 0.0.0.0 | `2bd1ca1353c228fbbcc04df2355d9cbc545f29ddd06ec1c10a6dd62d7bfda4d2` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/Assembly-UnityScript-firstpass.dll` | 0.0.0.0 | `2485adc91f6531523c525ec1f42cb8bf2706d574f2f141111ff2cd11ab9db953` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/Boo.Lang.dll` | 2.0.9.5 | `554ed425a426b88ace0cb93e099a0c20e37e409d1996ae72b45a68f2e3df0cd0` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/Ionic.Zlib.dll` | 1.9.1.8 | `f38d5476765dc1db212732800669a22794daae3bd387dd060366b384d3678db1` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/Mono.Posix.dll` | 2.0.0.0 | `50a58942461e5a1663f655025b1b6c2b786ed33cce8f500338d5052cd2af6060` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/Mono.Security.dll` | 2.0.0.0 | `847ccfeff97e42fc8c45494efa75fcd1c27c01c5583d4a494a53dbedf49fb5ef` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/SteamworksManaged.dll` | 1.0.0.0 | `a84843b76da51ad16745f6ab9d698ca72097eeb1f91c7a2c2d012bbcce6e9e40` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/System.Configuration.dll` | 2.0.0.0 | `7bc4f3160a2d7f89a23a9657012da60a43db1b3b3d0cab960b44a297d34d105d` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/System.Core.dll` | 3.5.0.0 | `f25b9777fbaf4f05a147823006bff0dc6dca3a77354c951666f9e0530e3ad8bb` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/System.Security.dll` | 2.0.0.0 | `730e84cb417d29a27023836871daafa05d3cef76919ecc220a08899e5eae6ec3` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/System.Xml.dll` | 2.0.0.0 | `ba9480df7bea4bbcae96466cca739d2b6b419a9b3f9cb8db9e631688389fbddf` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/System.dll` | 2.0.0.0 | `b2b0feb6a16daa1b9383fbcca0b8960cfdebac30e4f161925cf5be8093853a33` | 排除，授权/原许可尚未核实 |
| `game_runtime/Managed/UnityEngine.dll` | 0.0.0.0 | `f2bb33a090672618cfbcaeb0989e549471d00f99c5615f90715c8661a5bf2f7b` | 排除，授权/原许可尚未核实 |

完整 native、字体、root DLL、Bridge、图标源及源控制文件的精确哈希记录于 `REDISTRIBUTION_EVIDENCE.json`，不是凭文件名猜测。

## 建议公开清单与整改顺序

公开源码建议选择项目自有源码、作者文档、依赖声明、根 LICENSE/NOTICES、必要原许可、已明确授权资产；排除游戏/probe/Unity DLL、未核实游戏自带开源 DLL、未确认系统 DLL/字体、字标 outline 源、原始参考图/用户存档与 archive 历史二进制。Bridge 带自有源代码与说明，默认排除 bin。`REDISTRIBUTION_PUBLIC_MANIFEST.json` 为建议白名单/排除规则，**未执行过滤或发布**；源码若放 Git，须另核对历史中的所有受限材料，不能只修当前 release ZIP。

要发布二进制，先消除游戏/probe 等阻断项：确认权利或改为用户合法安装提供；随后核定 Qt/其他 native 与字体的精确依赖并提供相应源码/原声明；收集根法律文件，过滤 docs/branding 审阅中间件、无用 pytest/Cython/setuptools 等间接依赖；使用独立、干净、明确文件允许清单的构建与源码包流程，再对精确 EXE/源码包检查并按项目原有功能/截图门槛验证。仅清理文档、标 GPL、免费发布或称“个人使用”不会授权复制游戏文件。

本轮已实际新增：根 `LICENSE`（标准 GPL v3 原文）、根 `THIRD_PARTY_NOTICES.md`、`third_party_licenses/` 的 68 份有来源/哈希的必要原文及 PROVENANCE.json、本审计和证据/公开建议清单。许可选择未改为 MIT/商业；未对游戏或字体重新许可；未改 VERSION、品牌入口、业务/构建/发布代码或 Git index，未构建、上传、删除/改写历史包。
