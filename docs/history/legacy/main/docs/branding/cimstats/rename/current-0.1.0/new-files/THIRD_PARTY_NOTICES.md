# CimStats third-party notices / 第三方许可声明

CimStats · 0.1.0 · JEREMETRO

## 项目许可与范围

Copyright © 2026 JEREMETRO. 项目自有源代码按 **GNU General Public License version 3 only（GPL-3.0-only）** 提供；完整正文见同目录 `LICENSE`。本项目选择的是第 3 版，不自动包含后续版本。第三方代码、字体、库、游戏程序集、Unity 文件及由游戏程序集生成的探针保持各自原有权利和许可，不因本项目的许可证或关于页标识而重新许可。本软件按现状提供，不附带担保；具体条件见各许可证。

该许可选择基于实际使用的 Qt Charts 与 PySide6-Fluent-Widgets 社区版本。下列声明及保存的副本用于保留上游许可与署名，**不表示当前便携 EXE 或含游戏 DLL 的 source.zip 已完成公开再分发授权核验**。

## Qt、Fluent Widgets 与打包器

- PySide6、Essentials、Addons、shiboken6 的已安装 6.11.2 元数据声明 `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`；这不是所有 Qt 模块的统一许可。Qt Charts 在开源路径为 GPL v3，另有商业许可。现有包还包含 Qt Virtual Keyboard，其开源路径同为 GPL v3。其他模块及嵌入的第三方组件须逐项遵循其上游文件。Qt 著作权属于 The Qt Company Ltd. 及各贡献者。
- PySide6-Fluent-Widgets 1.11.3 的实际许可文本为 GNU GPL v3；上游 PySide6 分支说明另提供商业授权。未发现本项目已取得商业许可的证据。保留上游条款，不添加本项目自创的“禁止商业使用”条款。
- PySideSix-Frameless-Window 0.8.2 的实际 PySide6 包许可为 LGPL v3；应使用 PySide6 分支证据，不能用其他分支的许可代替。
- PyInstaller 的 bootloader exception 允许产物采用符合依赖许可的其他许可证。项目选用 GPL v3 的原因是依赖，而不是“使用 PyInstaller 必须 GPL”。
- `third_party_licenses/` 保留安装包及官方精确版本源码中的原始许可、NOTICE、版权和字体许可文件；其原作者及版权行以原文为准。Qt 文件中附带的 `LicenseRef-Qt-Commercial.txt` 只是条款副本，不是商业授权证明。

官方来源：

- [Qt Charts 6.11.2 licensing](https://doc.qt.io/qt-6.11/qtcharts-index.html#licenses)
- [Qt Virtual Keyboard 6.11.2 licensing](https://doc.qt.io/qt-6.11/qtvirtualkeyboard-index.html#licenses-and-attributions)
- [Qt module licensing](https://doc.qt.io/qt-6/licensing.html)
- [Qt for Python licensing](https://doc.qt.io/qtforpython-6/)
- [Qt for Python third-party licenses](https://doc.qt.io/qtforpython-6/licenses.html)
- [Fluent Widgets PySide6 LICENSE](https://github.com/zhiyiYo/PyQt-Fluent-Widgets/blob/PySide6/LICENSE) and [README](https://github.com/zhiyiYo/PyQt-Fluent-Widgets/blob/PySide6/README.md)
- [Frameless Window PySide6 LICENSE](https://github.com/zhiyiYo/PyQt-Frameless-Window/blob/PySide6/LICENSE)
- [PyInstaller license and exception](https://pyinstaller.org/en/stable/license.html)

## 已核对的依赖清单

下表版本来自当前安装环境。第三列仅表示在现有 **1.0.0 EXE** 的模块/文件表中发现匹配组件；不是未来 0.1.0 构建证明，也不是仅凭已安装就判断已分发。开发和构建依赖一并记录以保留其条款。完整元数据、路径、哈希及匹配依据记录在审计证据中。

| 组件 | 当前安装版本 | 现有 EXE 中匹配 | 上游许可声明概览 |
|---|---|---|---|
| beautifulsoup4 | 4.14.3 | 有 | MIT License |
| certifi | 2026.4.22 | 有 | MPL-2.0 |
| cffi | 2.1.1 | 有 | MIT-0 |
| chardet | 7.4.3 | 有 | 0BSD |
| charset-normalizer | 3.4.7 | 有 | MIT |
| clr_loader | 0.3.1 | 有 | MIT |
| colorama | 0.4.6 | 有 | License :: OSI Approved :: BSD License |
| contourpy | 1.3.3 | 有 | License :: OSI Approved :: BSD License |
| cssselect | 1.4.0 | 有 | BSD-3-Clause |
| cycler | 0.12.1 | 有 | License :: OSI Approved :: BSD License |
| Cython | 3.2.4 | 有 | Apache-2.0 |
| darkdetect | 0.8.0 | 有 | BSD-3-Clause |
| dnfile | 0.18.0 | 未匹配 | MIT License |
| et_xmlfile | 2.0.0 | 有 | MIT |
| iniconfig | 2.3.0 | 有 | MIT |
| Jinja2 | 3.1.6 | 有 | License :: OSI Approved :: BSD License |
| kiwisolver | 1.5.0 | 有 | License :: OSI Approved :: BSD License |
| lxml | 6.1.0 | 有 | BSD-3-Clause + LICENSES.txt component terms |
| MarkupSafe | 3.0.3 | 有 | BSD-3-Clause |
| matplotlib | 3.10.9 | 有 | Matplotlib license (PSF-derived) + font/component terms |
| more-itertools | 11.0.2 | 有 | MIT |
| numpy | 1.26.4 | 有 | BSD-3-Clause + bundled component terms |
| openpyxl | 3.1.5 | 有 | MIT |
| packaging | 26.2 | 有 | Apache-2.0 OR BSD-2-Clause |
| pillow | 12.2.0 | 有 | MIT-CMU |
| pluggy | 1.6.0 | 有 | MIT |
| psutil | 7.2.2 | 有 | BSD-3-Clause |
| pycparser | 3.0 | 有 | BSD-3-Clause |
| Pygments | 2.21.0 | 有 | BSD-2-Clause |
| pyinstaller | 6.22.2 | 未匹配 | GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones) |
| pyinstaller-hooks-contrib | 2026.7 | 未匹配 | GPL v2 + exception / Apache-2.0; see preserved text |
| pyparsing | 3.3.2 | 有 | MIT |
| PySide6 | 6.11.2 | 有 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6-Fluent-Widgets | 1.11.3 | 有 | GPL v3 community / separately purchased commercial license |
| PySide6_Addons | 6.11.2 | 有 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Essentials | 6.11.2 | 有 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySideSix-Frameless-Window | 0.8.2 | 有 | LGPL v3 (PySide6 branch) |
| pytest | 9.1.1 | 有 | MIT |
| python-dateutil | 2.9.0.post0 | 有 | Apache-2.0 / BSD-3-Clause (file-specific) |
| pythonnet | 3.1.0 | 有 | MIT |
| PyYAML | 6.0.3 | 有 | MIT |
| scipy | 1.17.1 | 有 | BSD-3-Clause + bundled component terms |
| setuptools | 84.0.0 | 有 | MIT |
| shiboken6 | 6.11.2 | 有 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| six | 1.17.0 | 有 | MIT |
| soupsieve | 2.8.3 | 有 | MIT |
| typing_extensions | 4.15.0 | 有 | PSF-2.0 |
| UnityPy | 1.25.3 | 未匹配 | MIT |

CPython：现有 EXE 的 `python312.dll` 文件版本为 3.12.10；PSF 等版权及许可全文保存在 `third_party_licenses/CPython/LICENSE.txt`。openpyxl 3.1.5、et_xmlfile 2.0.0、Cython 3.2.4 的缺失许可副本取自 PyPI 官方精确版本 source distribution，并校验其官方 SHA-256；未安装或执行这些源码。

## 游戏、Unity、探针与其他非项目材料

本项目是 Cities in Motion 2 存档分析工具，不是游戏发行版。名称及商标权归各自权利人。本项目许可证不授权再分发游戏或 Unity 程序集，也不改变 Steamworks、系统运行库等材料的条款。

现有 EXE 实际包含以下文件。`Assembly-CSharp.probe.dll` 是基于游戏程序集生成的修改副本；项目自有的补丁脚本可以采用项目许可，但生成的 DLL 不能据此视为完整项目自有作品。`Boo.Lang.dll`、`Ionic.Zlib.dll`、Mono/System 等文件可能包含分别适用开源许可的材料，须核对具体随游戏分发的版本和原始声明，不能把全部文件笼统标为私有或笼统 GPL。

- `data/Assembly-CSharp.probe.dll`
- `data/UnityEngine.dll`
- `game_runtime/Managed/Assembly-CSharp-firstpass.dll`
- `game_runtime/Managed/Assembly-CSharp.dll`
- `game_runtime/Managed/Assembly-UnityScript-firstpass.dll`
- `game_runtime/Managed/Boo.Lang.dll`
- `game_runtime/Managed/Ionic.Zlib.dll`
- `game_runtime/Managed/Mono.Posix.dll`
- `game_runtime/Managed/Mono.Security.dll`
- `game_runtime/Managed/SteamworksManaged.dll`
- `game_runtime/Managed/System.Configuration.dll`
- `game_runtime/Managed/System.Core.dll`
- `game_runtime/Managed/System.Security.dll`
- `game_runtime/Managed/System.Xml.dll`
- `game_runtime/Managed/System.dll`
- `game_runtime/Managed/UnityEngine.dll`

这些随游戏取得的二进制文件尚无足够证据证明本项目可以向公众再分发。当前构建脚本嵌入 Managed DLL，当前发布脚本的 source.zip 也包含探针与 Unity DLL；因此新加 LICENSE 与声明不能解决该公开发行边界。公开分发前须核对权利人许可，或重新设计为由用户合法安装提供运行库，并另行验证功能与组合许可。现有历史包保持原样，审计不追溯替换它们。

现有包还含 Microsoft VC runtime、Windows ICU 或其他原生库的可能路径；必须以最终 EXE 的实际文件清单核对对应再分发条款，不能凭包内 DLL 即认定项目 GPL 覆盖它们。

## 分发前尚需完成

GPL 的源码义务不仅是提供本项目 Python 文件：选择适用的分发方式，提供所分发 GPL 组件相对应的完整源码和必要构建材料，保留版权、许可及修改声明；适用 LGPL 的组件还须满足其重新链接/替换及调试修改等条件。许可文本、版权声明和对应源码路径应对接收者可获取。逐项核实 Qt 和原生库的版本、第三方条款与对应源码，确认游戏/Unity/探针的分发权，再审核最终精确 EXE。仅把本声明嵌入包或提供一个上游主页链接，不等于所有义务已履行。

0.1.0 尚未构建或发布；最终依赖清单须在构建后复核。全部页面测试和 960p 截图仍须用户亲审通过后才可打包。
