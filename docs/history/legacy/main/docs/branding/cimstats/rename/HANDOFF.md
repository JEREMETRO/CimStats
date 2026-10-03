# 已废弃：CimStats 1.1.0 更名候选交接

**此方案已被用户最新决定替代：CimStats 0.1.0，作者 JEREMETRO。下文仅为历史记录，所有旧 01/02/03/04 补丁禁止应用。** 当前候选见 [current-0.1.0/LEGAL-HANDOFF.md](current-0.1.0/LEGAL-HANDOFF.md) 与该目录 HANDOFF.md。启动与关于弹窗使用独立 owner 的最新 bootstrap/main/navigation 候选，不可叠加此处旧主入口补丁。prepare_candidates.py 已设为拒绝运行；旧图标资产及验证证据仍可按新交接使用。

状态：仅盘点、精确候选和无 Qt 校验。尚未应用生产补丁，未改主索引，未构建、生成 EXE、覆盖 dist、启动 MainWindow 或 Qt 测试。现有项目保持 `D:/test/CIM2_SaveStats`，没有新建平级目录。主控先确认文件归属及编辑窗口，再接续应用。

用户指定的正式显示名为 **CimStats**，后续版本为 **1.1.0**。用户已批准第 5 方案图标，批准母版 SHA-256 为 `7930D9968E3F151D1C339E9AC6CC76A4CBD112CF715D43178358E88075A10431`。本交接已增补图标资产和接入候选。全部页面测试和 960p 截图经用户亲审通过后才可打包；图标批准不代表全页通过，也不构成打包许可。

## 候选及应用顺序

| 候选 | 精确文件 | 行为与依赖 |
|---|---|---|
| [01-display-version.patch](01-display-version.patch) | `frontend/desktop_app.py`、`frontend/templates/index.html`、`VERSION`、`README.md`、`CHANGELOG.md`、`docs/DEVELOPMENT.md`、`docs/桌面前端使用说明.md`、`docs/CIM2_统计中心指标口径.md` | 窗口显示 `CimStats v1.1.0`；新增 application display name 和 application version；网页标签改名，中文工作台标题保持；文档明确 1.1.0 准备中，1.0.0 仍是已发布版本。纠正当前桌面使用说明中绕过候选流程、直接覆盖 dist 的打包示例。 |
| [02-windows-product-resource.patch](02-windows-product-resource.patch) | `CIM2_SaveStats.spec` | 依赖 01。新增 Windows ProductName / FileDescription = CimStats；FileVersion / ProductVersion 从 VERSION 读取，固定版本为 `(1,1,0,0)`。默认保留 `CIM2_SaveStats.exe`、InternalName 和 OriginalFilename 以减小兼容性影响；不新增图标配置。 |
| [04-approved-icon.patch](04-approved-icon.patch) | `frontend/desktop_app.py`、`CIM2_SaveStats.spec`，以及 ICON-ASSET-MANIFEST 列出的 16 个资源新增项 | 依赖 01、02。从正式资源目录加载所有 PNG 尺寸至同一个 QIcon，设置应用/主窗口图标；Windows 显式任务栏标识在 QApplication 创建前设置为 `CimStats.Desktop`。EXE 使用同源多帧 ICO。资源先按清单复制到生产目标，再应用接线，不能指向 docs。 |
| [03-optional-executable-name.patch](03-optional-executable-name.patch) | `CIM2_SaveStats.spec`、`build_portable.ps1`、`publish_release.ps1`、`src/release_checks.py`、`src/verify_candidate.py`、`src/test_release_layout.py`、`README.md`、`docs/DEVELOPMENT.md`、`docs/桌面前端使用说明.md` | 可选，主控确定新版 EXE 文件名后才考虑。最新输入哈希以 01、02、04 已重建的内容为基线，然后把本候选全部耦合文件一起审查应用。1.1.0 起用 `CimStats.exe`；更早版本继续识别旧文件名。 |

默认建议先审查 **01 → 02 → 图标资源新增 → 04**：正式显示品牌与已批准图标统一，EXE 文件名兼容现有入口。若主控决定同时更改新版 EXE 名，再接续 03；不能只改 spec 的 `name`，否则现有构建、校验与发布会找不到 EXE。04 编号在 03 之后是因为图标批准在首次候选准备后到达；实际依赖顺序以上述顺序和各 JSON 的 requires 为准。

每份 `.json` 保存精确 old/new 锚点及每阶段输入、输出 SHA-256（UTF-8、LF 规范化）。`SOURCE-BASELINE.json` 保存最新读取源文件的原始字节 SHA-256、HEAD、已有 tracked dirty 清单与补丁哈希；它才是准确源基线，不能把 HEAD 当作 dirty 文件的内容基线。没有全文件源码副本，也没有自动 apply 模式。

当前 01、02 已分别通过 `git apply --check`（只检查，不写文件或索引）。04 和 03 依赖前置阶段，不能直接在未应用的主树上独立检查；验证脚本按 **01→02→04→03** 在内存重建并核对 20 个阶段文件哈希，且对两份 PowerShell 候选做语法解析。Python/spec 候选均完成 AST 解析；可选发布校验代码在纯内存中通过 24 项兼容/拒绝测试，未生成假 EXE 文件。

## 只读品牌盘点

| 当前入口 | 当前值/情况 | 候选决定 |
|---|---|---|
| `frontend/desktop_app.py` 主窗口标题 | `CIM2 存档统计工作台 v{APP_VERSION}` | 01 改为 `CimStats v{APP_VERSION}`，中文页面名及页面路由均保持。 |
| 同文件 QApplication | `setApplicationName("CIM2 SaveStats")`；没有显式 display name 或 application version | 保留技术 application name，增加 `setApplicationDisplayName("CimStats")`、`setApplicationVersion(APP_VERSION)`。避免不必要地改变可能用于隐式设置路径的标识。 |
| 独立“关于”入口 | 当前 frontend/src/tools 的源码扫描未发现 `about`/“关于”入口 | 不为更名新增页面或弹窗；未来若增加，由主控使用 CimStats 和 APP_VERSION。 |
| `frontend/templates/index.html` | 浏览器 title 为 `CIM2 存档统计`；h1 为 `存档统计工作台` | title 改为 `CimStats · 存档统计`；h1 保留。此文件仍被现有 spec 收集，纳入盘点。 |
| 根目录 VERSION / app_paths | VERSION = `1.0.0`；前端读取打包中的 VERSION | 01 仅改 VERSION 为 1.1.0；不改读取函数。 |
| 当前 `dist/VERSION.json` | 正式版 1.0.0，源提交 `0421ba54d2bbc04aff6c19c925b80789aacf9b35`，EXE 名 `CIM2_SaveStats.exe` | 全程只读。文档明确它仍是已发布包，不把它冒充 1.1.0。 |
| 当前 EXE Windows VersionInfo | FileDescription、FileVersion、ProductName、ProductVersion、OriginalFilename、InternalName 均为空 | 02 准备新增版本资源；实际 PE 写入须以后在获准构建后验证。 |
| spec / 打包脚本 | `name="CIM2_SaveStats"`；没有 `version=` 和 `icon=` | 02 只新增版本资源。03 才可选择改新版 EXE 名；源入口 `.py` 和 `.spec` 文件名继续保留。 |
| 统计、首页、线路、公司导出 | `stats_exports.py`、`latest_info_exports.py` 与 workbook 生成器未找到旧软件品牌字符串；现有标题是业务/游戏名称 | 不添加品牌水印、导出说明或新元数据。`Cities in Motion 2 存档数据导出` 是游戏/内容名称，保留。 |
| CSV/XLSX 名称及解析契约 | `CIM2_*` 真实输出名被读取器、目录、字段与测试使用 | 全部保留，不能批量替换 CIM2 前缀。 |
| 当前文档标题 | README、桌面使用说明、统计口径标题含旧软件品牌 | 01 改当前标题；只追加准备中的版本记录，不改写已有 1.0.0 及历史记录。 |
| 历史证据、历史计划、旧归档和迁移脚本 | 保留旧名称及真实路径用于复核 | 不改名、不删、不覆写，包括既有发布/归档中的 README 和 EXE。 |

扫描范围为当前 frontend、src、tools、根 README / CHANGELOG / VERSION / 打包发布脚本、当前开发/桌面说明/口径文档；历史目录仅作归类，不做全量品牌替换。`docs/ui-redesign/motion-evidence/native-multi/motion-a04e2rf3` 有拒绝访问，宽范围文件遍历已报告该限制；所有候选文件和受保护契约均可读取并做哈希核对，该历史运动取证子目录不在更名候选范围内。

## 必须保留的契约

- `QSettings("CIM2SaveStats", "Desktop")`（桌面、统计提醒、首页提醒），以及现有设置键；不引入用户设置迁移。
- `.savestats-workspace` 文件名及内容 `CIM2_SaveStats`；`src/app_paths.py`；`%LOCALAPPDATA%/CIM2_SaveStats/jobs/` 和项目 jobs 定位。
- 项目目录、`CIM2_SaveStats.py` / `.spec` 技术文件名、`--backend` 分发、环境变量、缓存与 session 标识、字段和读取契约。
- `CIM2_*` 真实导出、车型目录、存档字段、历史发布记录、归档包及校验凭据。
- 中文页面名称、图表/对话框的业务标题与 Fluent 导航图标；没有增加“关于”页、品牌水印或说明文案。`frontend/latest_info_page.py` 未改动，首页微渐变卡面和图标复用继续由原首页 owner 负责。

若采用 03，旧归档仍由同一个发布校验器按版本核验，包必须恰好含单个预期 EXE、README.md、VERSION.json；不允许双 EXE。源码 ZIP 中的技术入口名保持。指向 `dist/CIM2_SaveStats.exe` 的外部快捷方式、启动脚本和杀进程工具需在新版正式发布后更新；它们不在仓库控制范围。发布进程占用检查同时覆盖旧、新 EXE 名，不停进程。

03 的版本阈值 `(1,1,0)` 是该可选方案的发布命名约定。如果主控决定只做显示更名、继续保留旧 EXE 名，不要应用 03，也不要单独应用其发布校验改动。

## 已批准图标资产与正式接入

批准来源为主控转述的用户明确批准。批准母版和三份现有 16/20/24 光学校正版都保留原始 SVG 字节；未重绘或修改路径、颜色、渐变。SVG 的 title/desc 中仍有批准前的 candidate/pending 字样，故在资产清单中记录后续批准而不篡改已批准源哈希。

正式资源目标：`frontend/static/branding/cimstats/`。当前该生产目录不存在；所有资源仅暂存在本目录的 [assets/frontend/static/branding/cimstats](assets/frontend/static/branding/cimstats)。[ICON-ASSET-MANIFEST.json](ICON-ASSET-MANIFEST.json) 为每个文件指定暂存路径、唯一生产目标、字节长度、SHA-256 和源 SVG 哈希；主控应逐项核对，若目标已有不同内容则先协调，不能整目录覆盖。

16 项资源：1 份母版 SVG、3 份光学校正 SVG、11 份透明 PNG（16/20/24/32/40/48/64/96/128/256/512）、1 份 Windows ICO（前 10 个尺寸，最大 256）。16/20/24 从对应光学 SVG 直接渲染；其余从批准母版只改变输出 viewport 后直接栅格化，不从大 PNG 缩小。所有文件为本地确定性 SVG 渲染，不引入图像生成或设计变化。

[ICON-VALIDATION.json](ICON-VALIDATION.json) 核验所有源和资产哈希、SVG 的外部引用/脚本限制、11 个准确 RGBA 尺寸、透明边界、各尺寸 C 加三柱的 4 个半不透明连通区域。已有审稿的 8 个尺寸逐像素完全一致；新增 40/96/512 也通过结构检查。ICO 独立封装各尺寸 PNG，不让编码器重新缩放小图；目录项、每帧原始 PNG payload 和 Pillow 独立解码后的像素全部核验一致。已实际打开批准的小像素审稿图与新渲染的 256 PNG 检查。

04 接入的运行图标由所有目标尺寸 PNG 组成同一个 QIcon，避免依赖 Qt 的 ICO 解码插件；通过 `app.setWindowIcon` 设置默认窗口图标，并对主窗口显式设置同一个图标。Windows `CimStats.Desktop` 是版本无关的任务栏分组标识，不是 QSettings key，不改变用户配置目录；旧 Python 分组/固定快捷方式的图标缓存可能需在最终发布后重新固定。该 Shell API 未在本会话调用，真实任务栏效果尚未验证。

现有 spec 的 datas 已把整个 `frontend/static` 加入冻结资源，故新 PNG/SVG 目标在复制后沿用现有打包路径，不重复加 datas 条目。EXE 的 `icon=` 精确指向相同生产目录下的 `cimstats.ico`。批准 SVG 和 PNG 可供首页 owner 复用；本候选没有修改首页业务文件或蓝色微渐变卡面。

运行 API 接法依据 [Qt QGuiApplication windowIcon](https://doc.qt.io/qt-6/qguiapplication.html#windowIcon-prop)，任务栏标识依据 [Microsoft SetCurrentProcessExplicitAppUserModelID](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-setcurrentprocessexplicitappusermodelid)。当前校验仅覆盖候选源和图像容器，不宣称真实任务栏、系统 DPI 选择、Qt 图标加载或 EXE 内图标已经通过。

spec 当前遍历收集 docs（仅排除 performance）；本目录候选资料可能随未来构建一起进入 EXE。该既有行为未改动，后续主控若要排除开发/品牌候选资料，应作为独立打包范围决定审查，不能混入显示更名。

## 应用窗口与风险

`frontend/desktop_app.py` 已有首页/界面修改且未提交，是主控共享入口。只在 owner 窗口确认后合入两处精确编辑。其余业务源码不得从旧快照整文件回灌；主树已有 UI 比较隐藏、网络高度、线路与图表变更，本候选没有覆盖它们。`docs/CIM2_统计中心指标口径.md` 可能是数据 owner 文件，候选只替换第一行标题，也需主控确认。

如果源文件 SHA 已漂移，停止直接应用这次候选，在最新源码中重新核对每个 old/new 锚点后重新准备；不要强制应用、丢弃其他 owner 修改或据 HEAD 恢复整文件。主控可以用 `.json` 中的锚点做局部编辑，但必须保留已有换行风格，并重新记录最终源哈希。

`prepare_candidates.py` 和 `validate_candidates.ps1` 都只有候选/校验模式：前者仅输出本目录补丁、清单、基线，在内存解析 Python/spec 并核验发布守卫；后者只读源码、在内存重放候选、解析 PowerShell、写本目录校验报告。两者都不启动 Qt 或构建，不调用 git add / commit / reset。

本宿主的 `py -3.12` 启动器报告无已安装 Python；已使用 Codex 随附 Python 3.12.14 做纯静态和内存验证，不安装依赖。随附运行时没有 PyInstaller，因此未执行真实 PyInstaller API/资源序列化。版本对象接法依据 [PyInstaller 官方 usage](https://pyinstaller.org/en/stable/usage.html) 和 [官方 EXE API 源码](https://github.com/pyinstaller/pyinstaller/blob/develop/PyInstaller/building/api.py)，类型字段依据 [官方 versioninfo 源码](https://github.com/pyinstaller/pyinstaller/blob/develop/PyInstaller/utils/win32/versioninfo.py)。实际构建时还需核对最终使用的 PyInstaller 版本。

主控接续：确认候选源文件 owner → 重核 SOURCE-BASELINE 与精确锚点、ICON-ASSET-MANIFEST 的源/目标哈希 → 应用 01、02、资源新增、04（如选择更名 EXE 再应用 03）→ 等 charts 释放 Qt 槽后验证 Qt 多尺寸图标、标题栏和任务栏并执行本版全部页面测试 → 收集本版 960p 截图给用户亲审 → 用户通过后才允许构建候选 → 对确切 EXE 做版本资源、图标、真实存档与发布验证。构建和发布未在本会话执行。
