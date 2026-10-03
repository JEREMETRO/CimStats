# 当前元数据接口：CimStats 0.1.0

此目录取代此前 1.1.0 候选。生产版本仍为 1.0.0，未应用候选或打包。

新模块生产目标为 `src/app_metadata.py`，已准备的精确新增文件位于 `new-files/src/app_metadata.py`。它只导入标准库，模块导入时不读取 VERSION，不导入 desktop_app、PySide6、qfluentwidgets、pythonnet 或其它重模块；启动入口可以在 QApplication 之前安全地导入。不要在启动页里导入 desktop_app 来获得名称或作者。

稳定接口：

```python
from app_metadata import (
    APP_NAME, APP_AUTHOR, TECHNICAL_APPLICATION_NAME, PROJECT_LICENSE_SPDX, PROJECT_LICENSE_NAME,
    PROJECT_LICENSE_SCOPE, WINDOWS_APP_ID, ICON_SIZES,
    bundle_root, application_version, application_metadata,
    icon_directory, icon_png_paths, icon_svg_path,
    project_license_path, third_party_notices_path,
)
```

`APP_NAME = 'CimStats'`；`APP_AUTHOR = 'JEREMETRO'`。版本只读生产根/冻结根中的 VERSION，候选 VERSION 内容为 `0.1.0`，模块中不重复写死版本。`application_metadata(root=None)` 返回不可变对象，字段为 `name / version / author / license_spdx / license_name / license_scope`；另有 `copyright_notice / no_warranty_notice / redistribution_notice` 字段供关于页呈现 GPL 适当法律声明。签名保持兼容，后 3 个字段有默认值。

`TECHNICAL_APPLICATION_NAME = 'CIM2 SaveStats'` 供 bootstrap 的 `setApplicationName` 保留原有技术标识；`setApplicationDisplayName` 使用 `APP_NAME`。显式 `QSettings('CIM2SaveStats','Desktop')` 和既有键、任务目录均保留。模块作为脚本运行时输出元数据 JSON，供后续构建清单读取；导入时无文件 I/O。

协议结论为 `GPL-3.0-only`。按用户最新要求，主面板显示英文原名 **GNU General Public License v3.0**，不作中文翻译；only/or-later 的精确信息通过 SPDX 与详情/文档表达，范围为项目自有源代码。实际使用的 Qt Charts 官方许可为商业或 GPLv3，不能仅因 PySide6 的 LGPL 选项就把整应用声明为 MIT；项目未发现商业授权凭据。GPL 的 “or later” 授权不能从通用 GPL 文本末尾的示例推定；本项目按用户选择协议的授权明确选择 v3 only。真实 LICENSE 与 THIRD_PARTY_NOTICES.md 已落盘，官方来源、精确包、现有 EXE 证据和未核实的整包再分发边界见 [LEGAL-HANDOFF.md](LEGAL-HANDOFF.md)。项目自有代码的许可选择已确认；整包公开发行授权未确认。

图标生产目标为 `frontend/static/branding/cimstats/`。资源文件仍暂存在 `../assets/frontend/static/branding/cimstats/`，清单为 `../ICON-ASSET-MANIFEST.json`，批准 SVG SHA-256 为 `7930D9968E3F151D1C339E9AC6CC76A4CBD112CF715D43178358E88075A10431`。

`icon_png_paths(root=None)` 返回 `(size, absolute_path)` 元组序列（16/20/24/32/40/48/64/96/128/256/512），供调用方在 QApplication 初始化后构造同一个 QIcon；`icon_svg_path()` 返回批准 SVG 的生产路径。显示 PNG 时由调用方按目标像素选择，16/20/24 为光学校正版。`WINDOWS_APP_ID` 是任务栏标识，不能用作 QSettings 应用键。

关于页显示项目 GPL 信息时还应提供第三方声明入口。`project_license_path()` 和 `third_party_notices_path()` 分别指向运行根 LICENSE 与 THIRD_PARTY_NOTICES.md，打包候选会收集它们。不要在关于页声称游戏/probe DLL 是 GPL、整个旧 EXE 已开源或已获商业授权。

入口 owner 负责 `CIM2_SaveStats.py` 的轻量启动顺序、desktop_app 的 main / navigation 精确接线；本会话不直接修改这些共享 hunks。原 1.1.0 补丁中的 main/icon hunk 已被本接口约定取代，不要与新入口候选叠加应用。
