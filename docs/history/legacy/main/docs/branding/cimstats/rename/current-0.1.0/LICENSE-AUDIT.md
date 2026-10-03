# CimStats 0.1.0 许可选择与分发边界审计

2026-10-02；作者 JEREMETRO；本轮仅准备候选和只读证据，未改生产文件、索引或历史包，未构建或启动 EXE/Qt。

## 已确认的项目许可选择

用户授权选择适合当前实际依赖的开源许可。项目自有源代码选用 **GNU General Public License v3.0，GPL-3.0-only**。按用户最新要求，关于弹窗显示英文原名，精确 v3 only 范围保留在 SPDX 与本地文档。这是明确的项目许可选择，不是把上游库重新许可。完整 GPL 正文已从现有 EXE 内的实际许可证副本逐字保留为 `new-files/LICENSE`，SHA-256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`。作者、版权、适用范围和免责声明记录在 `app_metadata.py` 与 `THIRD_PARTY_NOTICES.md`，不修改 FSF 标准许可正文。

主要选择依据为实际使用的社区版 Fluent Widgets 和 Qt Charts；仅看 PySide6 提供 LGPL 选项就为整个组合选择 MIT，会漏掉模块及依赖的 GPL 条件。没有发现商业 Qt 或 Fluent Widgets 授权凭据。项目明确选择 v3 only，不把通用 GPL 附录中的示例作为上游或本项目的 or-later 授权。许可选择与条款概要是基于下列证据的判断；不构成整个游戏运行库组合已获公开分发授权的结论。

| 核心组件 | 现有 EXE 实际证据 | 许可依据与结论 |
|---|---|---|
| PySide6 / shiboken6 | 冻结模块版本常量 6.11.2 | 已安装对应元数据提供 LGPL-3.0-only / GPL-2.0-only / GPL-3.0-only 选项；Qt 模块仍须分别检查。[Qt for Python 官方说明](https://doc.qt.io/qtforpython-6/) |
| Qt Core / Charts | DLL 资源版本 6.11.2.0；Qt Charts ProductName 标明 Qt 6.11.2 | [Qt Charts 6.11.2 官方许可](https://doc.qt.io/qt-6.11/qtcharts-index.html#licenses)为商业或 GPL v3；本项目未证实商业授权，采用 GPL v3 开源路径。 |
| Qt Virtual Keyboard | 实际归档包含 Qt6VirtualKeyboard.dll | [Qt Virtual Keyboard 6.11.2 官方许可](https://doc.qt.io/qt-6.11/qtvirtualkeyboard-index.html#licenses-and-attributions)同为商业或 GPL v3；其内含第三方模块条款仍需最终核实。 |
| PySide6-Fluent-Widgets | 冻结模块常量 1.11.3；EXE 内实际 GPL 全文 | 已安装精确包与 [PySide6 分支 LICENSE](https://github.com/zhiyiYo/PyQt-Fluent-Widgets/blob/PySide6/LICENSE)支持 GPL v3；[上游 README](https://github.com/zhiyiYo/PyQt-Fluent-Widgets/blob/PySide6/README.md)另说明商业授权路径。保留上游措辞，不替项目新增“禁止商业使用”条款。 |
| PySideSix-Frameless-Window | 冻结模块常量 0.8.2；EXE 内实际 LGPL 全文 | 实际 PySide6 包与 [PySide6 分支 LICENSE](https://github.com/zhiyiYo/PyQt-Frameless-Window/blob/PySide6/LICENSE)均为 LGPL v3。不能用其他分支 GPL 文本代替。 |
| darkdetect | 冻结常量 0.8.0；EXE 内 LICENSE | BSD-3-Clause，保留原文。 |
| CPython | python312.dll 实际资源版本 3.12.10 | PSF 及历史许可/版权全文已保留；不能把审计所用独立 Python 3.12.14 当成 EXE 运行库版本。 |
| PyInstaller | 当前安装 6.22.2；本轮未构建 | [官方例外说明](https://pyinstaller.org/en/stable/license.html)允许符合依赖许可的产物采用其他许可；它不是本项目必须选 GPL 的原因。 |

## 证据范围与保存文件

- `FROZEN-RELEASE-EVIDENCE.json`：只读解析实际 1.0.0 EXE 的 CArchive/PYZ 表、反汇编常量和 DLL 版本资源；未执行包内代码。EXE SHA-256 `7538cc6315a2adcc6b508dfaba0614326419fed53352f612f630dbaaf68b3c4d` 与正式 VERSION.json 相符。归档内 5 份实际许可/元数据已保存于 `frozen-evidence/`。
- `DEPENDENCY-EVIDENCE.json`：48 个已安装分发包的精确元数据、哈希、直接依赖/旧构建表匹配及当前 EXE 模块匹配标记。读取 importlib.metadata，不导入 Qt。安装环境版本与未来 0.1.0 实际包不能混同；模块匹配本身也不足以证明已安装的版本就是旧 EXE 版本。核心版本由冻结常量另行确认。
- `SUPPLEMENTAL-UPSTREAM-EVIDENCE.json`：Cython 3.2.4、openpyxl 3.1.5、et_xmlfile 2.0.0 的官方 PyPI 精确版本 sdist URL、官方 SHA-256 和每份许可成员哈希。仅内存下载、校验并提取 5 份 license/licence/copying 文本，未安装/执行源码。
- `NEW-FILES-MANIFEST.json`：84 个精确新增候选文件，含元数据、根 LICENSE、第三方声明，以及 81 个上游许可副本/补充许可正文。73 个来自已安装包，另有 CPython 1 个、官方 sdist 5 个、Qt 所需 GPL/LGPL 通用正文 2 个。字节码缓存不在清单中。
- `new-files/THIRD_PARTY_NOTICES.md`：完整中文适用范围、48 项版本/许可概览、官方来源、16 个实际游戏运行库条目、尚未证实的公开分发边界与源码义务。原始版权行保留在各许可副本；概要不替代原文。

现有 EXE 内完整许可提取只得到 5 项，不能据此断言旧包已完整履行所有署名和许可义务。新候选保留的文本也不等于完整公开分发合规认证。PySide6 安装许可树的商业条款副本并不证明使用者持有商业许可证。

## 尚未确认的整包再分发范围

现有 EXE 含 16 个游戏/Unity/探针/Managed 文件，精确路径见声明和冻结证据。`Assembly-CSharp.probe.dll` 为游戏程序集修改副本，不能仅因补丁脚本为项目自有代码就把 DLL 宣告 GPL。Assembly-CSharp、Assembly-UnityScript、UnityEngine、Steamworks 等材料尚无充分证据证明本项目具有面向公众再分发权。Mono/System、Boo、Ionic.Zlib 等材料可能分别为开源许可，须核对游戏随附的具体版本、来源和声明；不能将 16 个文件全部视为私有，亦不能将它们统一改为 GPL。

Microsoft VC runtime、Windows ICU、Qt 各模块内置第三方代码及字体等原生材料，仍须按最终实际归档逐项核对再分发条款、版权及适用源码义务。当前 root spec 确实嵌入 Managed DLL；当前发布脚本也将探针和 UnityEngine.dll 放入 source.zip。此次候选保持这些运行行为，但已在 README/声明明确项目许可证不能清除其权利边界。

公开发行前应先取得和核实相应授权，或另行设计合法安装依赖方式并验证功能及组合许可；为所分发的 GPL 组件提供相对应的完整源码及构建材料，满足相关 LGPL 条件，保留精确版权与修改声明。此轮没有把上游主页链接当作履行源码义务的替代品，也没有追溯重写历史 EXE 或源码归档。

上述剩余项不会阻止关于弹窗准确显示“项目自有源代码采用 GPL 第三版”或打开真实许可正文；它们会限制“整个当前便携包已可自由再分发”等表述。新品牌 0.1.0 尚未构建/发布，最终依赖和归档仍须复核；全部页面测试与 960p 截图用户亲审门槛保持。
