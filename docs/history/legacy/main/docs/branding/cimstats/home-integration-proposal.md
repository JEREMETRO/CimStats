# CimStats 首页背景接入候选方案

日期：2026-10-02。状态：仅准备，等待用户审核图标；未修改生产源码、生产图标或背景，未启动 Qt、构建或操作 Git 暂存区。

## 已核对的请求与参考

已在主控会话核对用户直接请求：软件更名 CimStats；Astra/high 按第5草图绘制 SVG；首页使用其部分元素美化大卡片；图标需要用户审核。首页本阶段仅准备接入边界，更名和图标由各自负责人处理。

已实际查看参考图 `D:/test/.codex-remote-attachments/01a0eae5-fd28-7a93-be3d-3bea2b0c0b98/e7f9f2dd-0313-4094-b9fe-231ab4f418bc/1-Photo-1.jpg`：第5方案为蓝青 C 弧与三根递增统计柱。

已实际查看已验收首页 `D:/test/CIM2_SaveStats/.worktrees/latest-info/docs/ui-redesign/latest-info-rev2-evidence/native-multi-dpr1.0-postaux-stable-sidebar/real-default.png` 和 Astra 的 `docs/branding/cimstats/review/cimstats-home-review-candidate.png`。后者为独立装饰示意，有示例数据，不能作为实际程序效果截图或接入验收证据。

## 推荐接入

装饰对象限定为城市摘要卡 `LatestInfoPage.city` / `cityCard`。城市名称、模拟日期和时间、人口及单位、存档名称保留原值和文字排版；不将字标、宣传语或新指标放入卡片。

从最终获批图标的同一 SVG 提取 C 弧和柱形路径，生成专用静态装饰 SVG。宽屏保留现有65逻辑像素卡高及四列结构，窄屏保留136逻辑像素及两列结构；不增加内容最小宽度、留白占位或图卡挤压。图形等比绘制，在右侧边缘裁切，只表现部分品牌轮廓。浅色背景以约5.5%有效不透明度作为初始视觉候选，最终以实际960p截图核对后确定。当前程序明确初始化浅色主题，此轮不添加深色主题功能。

装饰绘制在卡面之后、文字和控件之前，沿既有12px圆角裁切。文字区域及其周围至少6px保留纯净阅读底面；空白不足时减少可见图形面积，不改变原排版。装饰不承接鼠标、焦点、tooltip或辅助功能内容，也不参与任何布局尺寸测量。

现有 `cimstats-home-light-candidate.svg` 的 viewBox 为960×320，内部已有0.055透明度和固定位置，不适合直接拉伸到65px高卡片；不能重复叠加透明度。实际接入应从获批符号/独立弧柱路径按真实卡高构图，避免比例失真、柱形消失或装饰完全越界。

其他考虑过的处理：仅在边缘放柱形会弱化第5方案 C 的识别；把整个候选示意卡搬入首页需要扩大卡高，影响既有图表空间。因此推荐 C 弧与柱形的局部边缘构图。无需把装饰扩散到四组指标、四张极值卡、提醒栏或下方图表。

## 精确文件与职责边界

|文件|后续获批后的改动|负责人|
|---|---|---|
|`frontend/latest_info_page.py`|局部摘要卡绘制类和 `_build_city()` 的实例创建；原 `card()` 公共工厂保持用途；不改 `_build_header()`、数据绑定、`_reflow()`尺寸公式和图表逻辑|首页|
|`frontend/static/cimstats/home-decoration.svg`|新增获批路径派生的静态背景；记录来源与最终批准版本；审核前不创建生产资源|首页，来源为获批图标|
|`docs/branding/cimstats/home-integration-proposal.md`|本准备记录；后续添加真实接入截图和核对结果|首页|
|`docs/branding/cimstats/review/*`|候选符号、弧柱、字标和预览；首页只读，不修改或移入生产|Astra图标负责人|
|`frontend/desktop_app.py`、启动入口、版本及标题文案、`.spec`品牌字段|更名任务边界，首页不修改|更名负责人/主控|

开发路径使用模块所在 `frontend/static/cimstats/`；冻结程序路径使用既有 `_MEIPASS/frontend/static/cimstats/` 约定。不通过当前工作目录或审稿文档路径加载。现有 `CIM2_SaveStats.spec` 已包含 `frontend/static`，因此无须首页自行修改打包清单。资源缺失或 SVG 无效时保留原白色卡面及所有数据。新增 QtSvg 绘制依赖在正式打包阶段核对收集结果，不能仅凭开发环境可用签收冻结包。

不修改 `latest_info_controller.py`、`latest_info_charts.py`、数据模型/提醒/导出、共享 tokens/style、QSettings、存档/缓存字段及旧归档。更名负责人不覆盖首页文件；主控若发现新的共同修改先协调精确补丁，再接入。

## 已验收源码基线

此次仅只读核对主树：

- `frontend/latest_info_page.py` SHA256：`C565909D47F52E27679CCC095B9E466ECC7E40279C188B8A763864FEBF08D79D`
- `frontend/latest_info_charts.py` SHA256：`84C4538CBEA404F483B36C07E6E65D92C1AF9D5A03982EE5D2D94ADE5BF3E69C`
- `frontend/latest_info_controller.py` SHA256：`655388A81CBF82D2130485F3FD5A3BF8FDBF46BA78F23C20AA60C1E1A8294B13`

该基线证明准备方案对应目前已接入的首页；不是后续任意改动的验收结果。实施时重新核对当前文件，保留主控全项目阶段新增修改。

## 用户批准后的核对

主控记录具体获批 SVG 文件与哈希后，首页才制作生产派生资源并应用局部绘制补丁。主 Qt 测试槽仍由主控分配，本轮未使用。

在同一真实存档及范围下对照前后960p截图：卡高、四列/两列、所有文字边界、13指标、16亮点值、三图宽度及滚动位置一致；长城市名、长存档名和大人口值完整可读。实际检查窄宽窗口与系统缩放、鼠标悬停和键盘、PNG导出背景一致、资源缺失回退；装饰为静态，不增加动画或后台计时器。此前的原统计图交互复验结果保留，新增验证聚焦绘制和可读性。

用户审核图标及最终实际截图之前，不替换正式应用图标，不打包1.1.0。
