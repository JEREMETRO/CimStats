# 0.1.0 法律文档与关于页接口交接

最新显示约定：按用户要求使用原名，`PROJECT_LICENSE_NAME` 已改为 **GNU General Public License v3.0**，About 主面板直接消费该值；only/or-later 精确信息保持在 SPDX 与详情/文档。本次仅调整显示名称，GPL-3.0-only 的选择和许可范围不变。`TECHNICAL_APPLICATION_NAME` 必须供 bootstrap 的 `setApplicationName` 保留 `CIM2 SaveStats`，`setApplicationDisplayName` 使用 APP_NAME=CimStats，既有显式 QSettings 键保持。新增资产清单已排除 __pycache__、.pyc、.pyo；这些测试缓存不应用。

真实候选文档已落盘，均未应用到生产路径：

- `D:/test/CIM2_SaveStats/docs/branding/cimstats/rename/current-0.1.0/new-files/LICENSE`
- `D:/test/CIM2_SaveStats/docs/branding/cimstats/rename/current-0.1.0/new-files/THIRD_PARTY_NOTICES.md`
- `D:/test/CIM2_SaveStats/docs/branding/cimstats/rename/current-0.1.0/new-files/src/app_metadata.py`
- `D:/test/CIM2_SaveStats/docs/branding/cimstats/rename/current-0.1.0/NEW-FILES-MANIFEST.json`

应用后真实目标分别为项目根 `LICENSE`、`THIRD_PARTY_NOTICES.md`、`src/app_metadata.py` 与 `third_party_licenses/`。关于页继续使用已交接的 `project_license_path(root)`、`third_party_notices_path(root)` 和 `application_metadata(root)`。生产文件尚不存在时，按钮不能假装已成功打开；候选检查请使用本目录 `new-files` 下真实正文。

许可决定：用户已授权选择适合许可；**项目自有源代码 GPL-3.0-only** 已依据已安装精确包、现有 EXE 实际内容及上游官方许可核对。Qt Charts 和 Fluent Widgets 社区版是 GPL v3 的主要依据；实际 Qt Virtual Keyboard 亦为 GPL v3 / 商业双路径。Frameless PySide6 0.8.2 是 LGPL v3。`LICENSE` 为现有 EXE 中已保留的 GPL v3 全文原始副本，SHA-256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`。本项目明确选择 v3 only；不从通用附录模板推断 or-later。

官方链接及依赖/版本表已写入 `THIRD_PARTY_NOTICES.md`，证据详见 `DEPENDENCY-EVIDENCE.json`、`FROZEN-RELEASE-EVIDENCE.json`、`SUPPLEMENTAL-UPSTREAM-EVIDENCE.json`。后者验证了官方 PyPI 精确版本源码包 SHA-256，只提取许可证，未安装/执行。

**没有定案的范围是整包公开再分发，而不是项目自有代码的许可选择。** 现有 EXE 的 16 个游戏/Unity/探针/Managed 文件，游戏授权、探针衍生程序集再分发、随游戏提供的 Mono/Boo/Zlib/Steamworks 材料的精确声明，以及 Microsoft/ICU/Qt 内置第三方组件的最终发行义务尚未完整核实。不能显示“整个软件及运行库均 GPL”或“当前便携包可自由再分发”。关于页元数据已有精确范围提示：项目自有源代码；第三方组件与游戏运行库分别适用其原有许可。

此轮未改生产源码、索引、历史包或 EXE，未构建、未启动 Qt。整包发行核验与全部页面测试/960p 截图用户亲审仍为后续事项。旧 1.1.0 更名/图标入口补丁已废弃，不能叠加到启动 owner 的 main/bootstrap 补丁。
