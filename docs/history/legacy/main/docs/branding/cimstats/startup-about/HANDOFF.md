# CimStats 启动图标与关于弹窗

## 当前接入状态（2026-10-02）

已按主会话授权接入主工程 CimStats 0.1.0。权威结果为 `integration-evidence/manifest.json`，其中列出 25 个生产文件的 SHA-256、保留的法律文件哈希、真实主窗启动记录及截图路径。共享 `desktop_app.py` 与审核过的最小锚点修改逐字节一致；除 MainWindow.__init__、MainWindow.build_ui、main 外，113 个既有函数内容不变。其他会话的 UI 和字体修改保留。

“关于”使用协议原名 **GNU General Public License v3.0**，作者 JEREMETRO。启动/弹窗检查 18/18、既有入口/导航/字体回归 5/5 通过。根启动器实际运行、真实 MainWindow、100%/125%/150%/175%/200% Qt 缩放均验收通过；只读 LICENSE/第三方声明、重复打开单实例、Esc/关闭与焦点恢复、页面与导航状态保留通过。这里使用 QT_SCALE_FACTOR，不代表已更改或测试所有 Windows 系统 DPI 配置。

实际窗口图片：`integration-evidence/native-scale-1/main-window-composited.png`、`about-composited.png`、`about-dialog.png`。前两张为应用区域的桌面合成截图，保留当时系统输入法工具条；普通 widget/native-window 抓图不能重现 DWM/Mica 背景，故不能用其透明区判断真实黑底。200% 仍保留原主窗 920×680 最小尺寸，当前竖屏逻辑宽度不足时主窗会超出屏幕；关于面板按可见区域适配且没有滚动溢出。未修改既有主窗最小尺寸。

五个最新真实主窗进程（不同 Qt 缩放、未清空 OS 缓存、隔离 QA 设置）观察到 bootstrap 至启动图标完成 Qt 绘制的中位数 309.763ms，真实 MainWindow 首次 Qt 绘制中位数 6431.504ms。以每次 `startup-trace.json` 为准。这是源码测试，带观察器和审阅窗口尺寸调整；不是冻结包双击计时，也不是 OS 合成器首个可见像素计时。图标覆盖了重导入与主窗构造期间，没有增加人为最短停留。父窗首帧后立即发关闭命令，所有 helper 正常回收。

可以冻结本模块源码；本会话未构建、上传或删除包体。冻结包仍须实测双击至图标/真实主窗、重复启动、关闭/失败无残留 helper、--backend 分流及关于文档按钮。构建必须收集 app_metadata、startup_bootstrap、startup_transport、startup_splash、startup_readiness、about_dialog（尤其动态 helper 分支），PySide6.QtSvg/PySide6.QtSvgWidgets、现有 Fluent/字体/动效依赖，VERSION、LICENSE、THIRD_PARTY_NOTICES.md 与 `frontend/static/branding/cimstats` 全部批准资源。无需重画图标或改写协议。

以下是接入前的候选记录，保留供追溯；不要在已接入主工程重复应用补丁或运行要求目标缺席的 `validate_candidates.py` / `prepare_patches.py`。当前只运行 `validate_integration.py` 检查。

## 接入前记录

本目录只含独立候选、精确补丁、测试与实际 Qt 组件图片。未改共享生产源码、根索引、业务数据或用户设置，未创建 worktree，未构建发行包。关于整页已按用户最新要求改成紧凑 Fluent 弹窗；旧 `evidence/scale-*/about.png` 仅为历史，见 `evidence/SUPERSEDED.md`。

## 接入文件与顺序

先由品牌 owner 应用当前 `rename/current-0.1.0` 的统一元数据、VERSION、批准图标和真实协议文件，然后主控核查本目录 `SOURCE-BASELINE.json` 的源哈希及唯一 old/new anchors，逐个新增以下文件。文件已存在时不要覆盖，先协调 owner。整个过程不需要修改公司、网络、城市或线路业务模块。

| 候选新增文件 | 生产目标与职责 |
|---|---|
| `candidate/frontend/startup_transport.py` | `frontend/startup_transport.py`；标准库进程所有权、只绑定 127.0.0.1 的临时端口、随机 token 验证、首帧握手、close/EOF 与有限时回收。字节接收线程不触碰 Qt。 |
| `candidate/frontend/startup_splash.py` | `frontend/startup_splash.py`；独立进程 GUI 主线程上的透明 144×144 窗口，96px 批准 SVG，仅图标，无文字、进度、标语或人为最短停留。 |
| `candidate/frontend/startup_readiness.py` | `frontend/startup_readiness.py`；观察父窗口真实 Paint 事件，当前绘制分派结束后关闭启动页，不用 show() 调用代替 ready。 |
| `candidate/frontend/startup_bootstrap.py` | `frontend/startup_bootstrap.py`；先启动轻量 helper，父进程创建 QApplication，首帧握手后导入重模块，在 GUI 主线程创建 MainWindow。消费统一名称、技术 applicationName、显示名、版本和图标接口。 |
| `candidate/frontend/about_dialog.py` | `frontend/about_dialog.py`；复用 MessageBoxBase 和项目 SurfaceMotion。每个父窗口一个关于实例，Esc/关闭回到原焦点，两个文档按钮打开真实本地只读文档。主面板消费人类可读 `metadata.license_name`，不直接展示 SPDX。 |

随后只合入三份精确补丁：

1. `01-launcher.patch`：保留 `--backend` 的原最早分发及 `prepare_embedded_qt()`，其后最早分流 `--startup-splash`；根 main 委托 bootstrap。helper 分支不进入 bootstrap/desktop_app。
2. `02-navigation.patch`：增加 NavigationItemPosition 导入，保留原三项导航，在底部增加 `selectable=False` 的“关于”动作。直接打开弹窗，不加 pages，不调用 navigate，不改选中 route、标题或原有导航函数。
3. `03-direct-desktop-entry.patch`：仅把 `desktop_app.main` 改为委托同一个 bootstrap。bootstrap 导入的是 MainWindow 类，绝不调用 desktop_app.main，因此没有双入口递归或第二 QApplication。直接运行 desktop_app.py 仍会先完成其重 import；推荐入口仍是根启动器。

不要叠加旧 `rename/01-display-version.patch`、`04-approved-icon.patch` 的 main hunks，它们已被品牌 owner 新接口及本 bootstrap 取代。更名 owner 对 MainWindow 窗口标题的独立 hunk仍需保留。补丁在当前混合主树上逐份 `git apply --check`；共享文件变化后重新核查锚点，不能按旧快照覆盖整文件。

本轮 baseline：根启动器 SHA-256 `b592363f81ade5c4023484fb90dbc709652036624f45e3d1123748afeab0910b`；`frontend/desktop_app.py` SHA-256 `044883c89cc88b42a45f561c0e1ce04aa69183acb9f88b506420f488ddc06879`。最新值与所有新增文件/补丁锚点以重新生成的 `SOURCE-BASELINE.json` 为准。

## 元数据与文档边界

唯一元数据生产目标为品牌 owner 的 `src/app_metadata.py`。版本只读 VERSION；本目录不重复写死版本、名称、作者或许可。测试临时 root 中的 0.1.0 仅为隔离 fixture，不是第二生产来源。批准图标只消费统一资源路径；母版 SHA-256 为 `7930D9968E3F151D1C339E9AC6CC76A4CBD112CF715D43178358E88075A10431`。

`LICENSE` 和 `THIRD_PARTY_NOTICES.md` 已从品牌 owner 当前新增文件候选复制到临时 root，真实按钮路径验证通过；正文 SHA 与字节长度记录在 `evidence/document-buttons.json`。协议主面板按用户最新要求显示许可证英文原名，由品牌 owner 的 `license_name` 字段维护，不自行翻译。项目自有代码许可的候选核定与整包公开再分发审计是不同范围；本候选不声称游戏、探针或整个便携包均可按项目许可再分发。

## 实际组件验证与测时

本机现有 Python 3.12、PySide6 6.11.2；所有测试均为 offscreen，未创建业务 MainWindow，未操作全局鼠标、实际用户 INI 或存档。隔离套件覆盖：真实 Fluent 底部动作保持原三页栈/lines 选中；原 navigate AST 不变；单实例、Esc、焦点恢复；真实协议/第三方声明只读内容；图标完成绘制、hide/show 恢复；主窗替身首帧后关闭；缺图降级；父进程突然退出；恶意 token 拒绝；卡住子进程有限时回收。完整项目测试包含业务主窗口，按主控槽限制本轮未执行。

5 次新源码进程测时，系统文件缓存未清，详见 `evidence/timings.json`：

| 阶段 | p50 | 范围 |
|---|---:|---:|
| 最小 Qt 导入 | 124.7 ms | 120.2–136.3 ms |
| 最小 Qt 模式外部 spawn → QApplication 创建 | 202.4 ms | 199.2–226.4 ms |
| desktop_app 仅导入 | 1042.7 ms | 1026.0–1106.9 ms |
| helper Popen 调用 | 7.35 ms | 6.61–7.63 ms |
| 外部 spawn → helper 实际 Paint 完成 | 403.6 ms | 395.8–412.5 ms |
| bootstrap 进入 → helper Paint 完成 | 281.2 ms | 277.1–291.1 ms |
| QWidget 替身首次 Paint | 902.3 ms | 893.6–911.8 ms |
| 替身 Paint → close 命令 | 0.138 ms | 0.114–0.153 ms |

helper 自身最小 Qt 导入 p50 132.0 ms。相比仅一个最小 Qt 进程创建 QApplication，外部 spawn 到 helper 首帧增加约 201 ms；两者终点不同，不能把差值视为完整启动时间增量。独立进程的收益是父 GUI 在重 import 与同步构造窗口时，helper 的 GUI 仍能处理绘制及关闭事件。`evidence/responsiveness.json` 记录父 Python 忙 1 秒时子 Qt 完成 6 次 Paint/18 次 timer，hide/show 恢复像素相同，退出码 0；这是 offscreen 恢复，不是原生遮挡/DWM 验证。

首帧握手 5 秒是失败上限，正常一收到 Paint 确认就开始重导入，未设置固定等待或最短显示时长。helper 提前失败立即降级。失败/退出 finally 回收，正常关闭等候最多 2 秒，再 terminate 等候 1 秒，必要时 kill；这些是异常清理上限，不是正常画面停留。

当前实际弹窗图为 `evidence/dialog-scale-{1,1.25,1.5,1.75,2}/about-dialog.png`；同目录有 `about-dialog-small-parent-420x320.png` 和尺寸/字体/scrollRange 证据。中文正文沿用现有 fallback；西文名称、版本、作者使用 `stats_typography`。显示空间不足时以可见屏幕/父窗口交集约束弹窗，正文可滚动，关闭区域固定可用。正常父窗口无正文滚动、两个文档按钮完整。

## 仍待主控排槽与未来打包决策

当前 Paint 时间是 Qt 绘制证据，不能称为真实桌面首次可见或 DWM 呈现。真实 MainWindow 构造/ready 时长、主窗口内底部动作、原生遮挡恢复、系统五 DPI、标题栏/任务栏图标与真实主窗口截图仍待主控排槽。它们没有被 QWidget 替身替代，也未宣称已通过。

源码 Python 启动页覆盖不了单文件 bootloader 在解释器之前的解包等待。未启动既有冻结 EXE、未构建新 EXE，故没有冻结分段实测。PyInstaller windowed 的 stdin/stdout/stderr 可为 None，因此本候选使用本机控制 socket；同 exe 子进程按其 worker 语义复用 extraction，不设置会重置为新实例的 PYINSTALLER_RESET_ENVIRONMENT。实际构建工具版本/重入参数/解包继承仍须对确切版本验证。

若最终用户要求从点击 EXE 起尽早出现图标，必须先测启动到解释器入口之间的真实耗时；若其占主导，需另行选择 PyInstaller 原生 splash 或 onedir。原生 splash 可以覆盖更早阶段，但需验证只图标、关闭交接和 worker 抑制；onedir 减少单文件解包，却改变发行目录。两项均属后续打包调整，当前没有选型或正式打包。

依据：[Qt GUI 线程规则](https://doc.qt.io/qt-6/threads-qobject.html)、[PyInstaller windowed 标准流和同 exe 子进程](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)、[PyInstaller 运行路径](https://pyinstaller.org/en/stable/runtime-information.html)。
