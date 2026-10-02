# CimStats — Third-party notices

Copyright © 2026 JEREMETRO.

## Project license and scope

Project-owned source code is licensed under **GNU General Public License v3.0, GPL-3.0-only**. The complete, unmodified license is in `LICENSE`. The program is provided without warranty as described in the applicable licenses. Copyright and license notices for third-party material remain with their respective owners; this project does not relicense them.

项目许可仅涵盖项目自有源代码。游戏、Unity、系统运行库、字体及品牌参考材料保留各自原有权利。

## Included open-source components

以下组件包含在 CimStats 0.1.0 发布包中：

| 组件 | 版本 | 原许可 |
|---|---|---|
| Python (CPython) | 3.12.10 | PSF-2.0 |
| PySide6 | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Addons | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Essentials | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| shiboken6 | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6-Fluent-Widgets | 1.11.3 | GPL-3.0-only |
| PySideSix-Frameless-Window | 0.8.2 | LGPL-3.0-only |
| darkdetect | 0.8.0 | BSD-3-Clause |
| matplotlib | 3.10.9 | PSF-based (matplotlib) + component/font terms |
| numpy | 1.26.4 | BSD-3-Clause |
| scipy | 1.17.1 | BSD-3-Clause |
| openpyxl | 3.1.5 | MIT |
| pillow | 12.2.0 | MIT-CMU |
| lxml | 6.1.0 | BSD-3-Clause |
| psutil | 7.2.2 | BSD-3-Clause |
| pythonnet | 3.1.0 | MIT |
| clr_loader | 0.3.1 | MIT |
| certifi | 2026.4.22 | MPL-2.0 |
| charset-normalizer | 3.4.7 | MIT |
| chardet | 7.4.3 | 0BSD |
| cffi | 2.1.1 | MIT-0 |
| pycparser | 3.0 | BSD-3-Clause |
| packaging | 26.2 | Apache-2.0 OR BSD-2-Clause |
| python-dateutil | 2.9.0.post0 | Apache-2.0 / BSD-3-Clause |
| six | 1.17.0 | MIT |
| kiwisolver | 1.5.0 | BSD-3-Clause |
| contourpy | 1.3.3 | BSD-3-Clause |
| cycler | 0.12.1 | BSD-3-Clause |
| fontTools | 4.x | MIT |
| pyparsing | 3.3.2 | MIT |
| et_xmlfile | 2.0.0 | MIT |
| Jinja2 | 3.1.6 | BSD-3-Clause |
| MarkupSafe | 3.0.3 | BSD-3-Clause |
| Pygments | 2.21.0 | BSD-2-Clause |
| setuptools | 84.0.0 | MIT |
| typing_extensions | 4.15.0 | PSF-2.0 |

完整许可文本位于发布包内 `third_party_licenses/` 目录。Qt Charts 使用 GPL v3 开源许可路径。Fluent Widgets 社区版为 GPL v3。

官方参考：[Qt licensing](https://doc.qt.io/qt-6.11/licensing.html)、[Fluent Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)、[Frameless Window](https://github.com/zhiyiYo/PyQt-Frameless-Window)。

PyInstaller 的 [bootloader exception](https://pyinstaller.org/en/stable/license.html) 不单独要求应用 GPL。

## Game runtime components

Cities in Motion 2 is developed by Colossal Order and published by Paradox Interactive. 发布包包含用于解析存档的游戏运行时组件（Assembly-CSharp、UnityEngine 等），这些组件属于游戏本身，权利归各自权利人。本项目与这些公司无官方关联。

用户需要合法拥有 Cities in Motion 2 才能使用本工具解析存档。本工具不修改游戏文件，仅读取存档数据。

## Fonts

发布包包含 Matplotlib 自带的 DejaVu 和 STIX 字体（按原始许可分发）。应用界面使用 Windows 系统字体（Microsoft YaHei UI / Segoe UI），不嵌入字体文件。

## Brand assets

CimStats 图标为项目原创设计。Segoe UI 字标仅用于完整词语的图形输出，不分发字体文件。
