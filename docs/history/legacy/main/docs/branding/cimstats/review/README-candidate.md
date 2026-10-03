# CimStats · 第 5 案图标候选

状态：**candidate，等待用户审稿**。创建于 2026-10-02。全部资产仅在本审核目录中；本任务未替换正式图标，未更改首页或程序代码，未创建发布包。首页装饰也必须等图标批准后再由首页负责人接入。1.1.0 打包仍需用户最终截图批准。

## 审稿入口

- `cimstats-review-light-dark-candidate.png`：浅深底并排，256 px 主图、独立横排字标组合、16/20/24/32/48/64/128/256 px 真实栅格尺寸。
- `cimstats-small-pixels-candidate.png`：16/20/24 px 原图及最近邻 8 倍放大，用于观察真实像素与留白。
- `cimstats-home-review-candidate.png`：首页大卡片低干扰背景示例；数据为示例，未连接实际首页。

## 可编辑源文件

| 文件 | 用途 |
| --- | --- |
| `cimstats-symbol-candidate.svg` | 透明应用符号母版，48×48 设计坐标，默认 256×256 输出 |
| `optical-candidate/cimstats-symbol-{16,20,24}-candidate.svg` | 对应目标像素的小尺寸光学校正版 |
| `cimstats-lockup-light-candidate.svg` / `cimstats-lockup-dark-candidate.svg` | 符号与 CimStats 字标独立组合，560×144，不放进小应用图标 |
| `cimstats-arc-candidate.svg` / `cimstats-bars-candidate.svg` | 从相同母版提取的 C 弧、三根柱，保留坐标以便重组 |
| `cimstats-home-light-candidate.svg` / `cimstats-home-dark-candidate.svg` | 960×320 透明装饰画布，右侧裁切构图，不透明度 5.5% / 7.5% |
| `raster-candidate/cimstats-{size}-candidate.png` | 八个目标尺寸的真实 RGBA PNG |
| `raster-candidate/cimstats-{size}-{light,dark}-candidate.png` | 同尺寸图标在审稿用浅底 / 深底上的实际合成 PNG |

所有 SVG 使用原生路径、分组和线性渐变。无内嵌位图、无外部资源引用、无脚本、无 SVG text 字体依赖。字标由本机 Segoe UI Semibold 转成路径，可编辑轮廓，但不是仍可输入文字的文本对象。符号的 `c-arc`、`statistics-bars` 与两条渐变均可单独调整。

## 设计与光学校正

实际查看参考图片右侧第 5 案：蓝青 C 包围三根上升统计柱。候选保持这两项识别要素和 C 下端收束轮廓，去掉图标内小字、底板与复杂反光。参考原图：`D:/test/.codex-remote-attachments/01a0eae5-fd28-7a93-be3d-3bea2b0c0b98/e7f9f2dd-0313-4094-b9fe-231ab4f418bc/1-Photo-1.jpg`。

母版 C 使用 `#086CC7 → #079FCE → #0CCAB4`，柱形使用 `#087FD3 → #0CC6B2`；形状直视、圆角轻微，无外投影。字标以轮廓外接框垂直居中。

32、48、64、128、256 px 由母版相同几何直接栅格化。16、20、24 px 的 C 沿用母版，三根柱分别按目标像素调整宽度、间距、顶端和基线，使柱与下弧分开。三版不能误称为母版无差别缩放；需要由调用方按目标尺寸选择。24 px 检查曾发现相邻柱在半透明阈值下相连，现已收窄柱宽并抬高柱底，最终八个尺寸均保持 C 加三柱共四个独立的半不透明连通区域。

## 已完成验证与限制

- 使用 sharp / librsvg 在目标尺寸直接渲染 SVG；审稿图真实尺寸行按 1 PNG 像素对应 1 审稿图像素合成。聊天预览可能缩放，需打开原图 100% 查看。
- 八个 PNG 均核对准确尺寸、RGBA 透明通道、边界余量与四个独立形状；16/20/24 的最近邻放大已人工查看。
- XML 检查确认 SVG 无 image、text、script、foreignObject、use 或任何 href；SHA-256 与数值结果见 `verification-candidate.json`。
- 在审稿浅底 `#F7F9FC`，完全或近乎完全不透明的图标像素中约 50%–55% 达到 3:1；深底 `#172231` 为 100%。此抽样排除半透明抗锯齿边缘，不代表所有壁纸、系统强调色或高对比模式均通过。青绿亮部在浅底上的对比较弱，依靠整体轮廓识别。
- 未验证真实任务栏、开始菜单、标题栏、ICO 编码或 Windows 缩放选择；未制作 MSIX 全套部署资产。16 px 三柱已可分开，但高度信息与圆角仍受像素限制。
- 首页背景仅验证独立示例布局。图案避开关键指标区，移动端或窄卡片接入时应隐藏装饰或重新布置，避免与数据重叠。该候选未接入生产首页。

## 官方指导与适用边界

以下均为 2026-10-02 查阅的 Microsoft 官方来源：

1. [App icons](https://learn.microsoft.com/en-us/windows/apps/design/style/app-icons-and-logos)：应用品牌图标用于系统中的应用识别与启动，与应用内部功能图标是不同用途。
2. [Design guidelines for Windows app icons](https://learn.microsoft.com/en-us/windows/apps/design/iconography/app-icon-design)：参考简洁隐喻、48×48 网格、圆角、克制渐变及浅深背景对比原则。官方通常建议避免字母和文字；本设计保留用户指定的 C 作为品牌字母符号，完整应用名独立排版，不宣称逐条完全符合所有建议。
3. [Construct your Windows app’s icon](https://learn.microsoft.com/en-us/windows/apps/design/iconography/app-icon-construction)：参考透明背景和多尺寸输出指导。本次八个审稿尺寸覆盖要求，但不是完整系统部署资产集合。
4. [Segoe Fluent Icons font](https://learn.microsoft.com/en-us/windows/apps/design/iconography/segoe-fluent-icons-font)：该字体提供应用 UI 功能符号。本品牌图标不使用其字形，也不把功能图标字体规则套作品牌标志认证。

本候选参考 Fluent / Windows 设计指导，**没有微软认证、微软背书或官方图标身份**。仅借用设计指导，无框架迁移或 WinUI 工具链安装。

## 可复现材料

`generate-candidate.cjs` 生成 SVG 和真实目标尺寸栅格；`wordmark-outline-candidate.json` 保存字标轮廓，生成阶段也不需要字体。`compose-review-candidate.py` 合成审稿 PNG 并审计 SVG / 栅格尺寸。生成工具使用本机现有依赖，其本机路径不属于 SVG 的运行依赖。
