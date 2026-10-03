# CimStats 城市与时间摘要卡：四套候选

> 最新决定已覆盖下文待选状态：默认浅蓝、保留WinUI正蓝白字代码模式，强调西文/数字换Segoe UI Variable。实现与新验证见 `home-selected/DELIVERY.md`。下文四方案为历史审稿记录，不作为当前配色选择或当前源码的验收。

2026-10-02。图标已获用户批准，卡面配色待用户最终选择。本轮只在 `latest-info` 工作树准备候选；主工程首页及默认原版保持不变，未运行 MainWindow 或构建安装包。

## 批准与最新要求

已在主控会话核对用户消息：先批准图标及蓝色微渐变卡面，然后明确允许深蓝白字，要求加上原版做多个方案比选，由用户最后决断。

批准图标：`D:/test/CIM2_SaveStats/docs/branding/cimstats/review/cimstats-symbol-candidate.svg`，SHA256 `7930D9968E3F151D1C339E9AC6CC76A4CBD112CF715D43178358E88075A10431`。派生资源的全部路径、渐变节点及顺序与该源逐项核对一致，仅调整说明元数据；有效不透明度由卡片绘制一次应用。

## 四套同尺寸候选

|方案|卡面|文字|背景元素|
|---|---|---|---|
|A 原版|原白色卡面|既有深蓝及次级色|保持原版无装饰|
|B 浅蓝|`#F1F7FF` → `#E3EFFF`|主文字 `#18314F`，次级 `#465D79`|获批 C 弧及三柱，6.5%|
|C 深蓝|`#123D70` → `#1A4A82`|白色，次级 `#DCE9F7`|获批 C 弧及三柱，8%|
|D 蓝青深色|`#153E6E` → `#15556B`|白色，次级 `#DCE9F7`|获批 C 弧及三柱，8%|

方案名称和字母均置于比选图的卡片外。SVG等比绘制、右侧裁切、沿既有12px圆角限制，实际绘制文字及其周围6px保留阅读底面。装饰不生成控件，不承接鼠标、键盘、焦点或提示，不增加计时器和动画。

宽屏保留65逻辑像素和四列，窄屏保留136逻辑像素和两列；不修改原重排尺寸公式、卡片布局、真实字段、13指标、16亮点或下方三张图。候选默认仍为A；没有向用户增加配色设置入口。

## 实际预览与验证

输出目录：`D:/test/CIM2_SaveStats/.worktrees/latest-info/docs/branding/cimstats/home-review/`。

- `city-four-variants-wide.png`：同一真实多人数据的四卡对照；卡片932×65。
- `city-four-variants-narrow.png`：同一数据的两列适配对照；卡高136。
- `context-A-multi-offscreen.png` 至 `context-D-multi-offscreen.png`：实际 LatestInfoPage 整体组件预览，1204×860，没有伪造主程序窗口、导航或960p原生截图。
- `fixture-long-A-narrow.png` 至 `fixture-long-D-narrow.png`：显式构造的长名、大人口、长存档容量边界；与真实存档比选分开标识。延续原文字省略及完整悬停信息，不冒称该构造为真实存档。
- `verification.json`：实际脚本退出0；8个配色/宽窄组合的字段、几何、13/16、三图位置和滚动状态与同布局原版一致；SVG有效，Fluent Enter/Leave悬停事件仍工作。A卡与直接加载主工程原始组件的同数据渲染像素完全一致。
- 各渐变抽样21位置：B主/次文字最低对比11.349/5.821，C为8.952/7.265，D为8.256/6.700；装饰避开绘制文字区域。
- 现有首页组件回归68项通过，13.13秒，实际退出0；日志 `home-review/page-regression.log`。

数据为只读真实缓存 `D:/test/CIM2_SaveStats/jobs/a15a66a7b97e4497a699cc0e729e2358`，标签 `quicksave.76561198362520556-76561198845688243_运行时`。同一最新信息快照，城市Szczecin、模拟时刻2013-04-10 23:59:22、人口292330。指标、曲线、极值和19条提醒均由现有数据模型计算。原始两份XLSX存在后才启用对应预览按钮。所有设置使用临时INI，未运行解析器或写缓存。

负责人亲看宽屏四卡、完整A/B/C/D上下文和D长文字边界，圆角、文字净空及数值层次可读。仅以所示独立组件范围作结论；不能将offscreen字体与原生字体、合成悬停与前台指针、进程缩放与真实系统DPI混同。

## 精确补丁与接入边界

产品候选仅两文件：

1. `frontend/latest_info_page.py`：新增局部 `CitySummaryCard` 绘制；`_build_city()`使用该卡，给人口标题稳定名称。默认原版A。保留既有elevation和surface motion；不改 `_build_header()`、`_reflow()`及数据绑定。
2. `frontend/static/cimstats/home-decoration.svg`：由获批符号派生的静态装饰，无重复透明度。

现有 `.spec` 已包含 `frontend/static`。冻结资源按 `_MEIPASS/frontend/static/cimstats/` 定位，开发按模块目录定位，不读审稿目录或当前工作目录。缺失/无效资源只省略装饰，保留卡面和全部数据。QtSvg的冻结依赖仍需最终打包验证，此轮未构建。

准备文件：`home-review/home-candidates.patch`及 `home-review/home-candidates-manifest.json`。精确补丁以主工程 `latest_info_page.py` SHA256 `C565909D47F52E27679CCC095B9E466ECC7E40279C188B8A763864FEBF08D79D` 为基线；候选 SHA256 `605F92D37857B6518B17E995051836412FB7E6BE28B360C487C4586A1B4DAD31`。SVG SHA256 `FD14FC5E3D06382B1B6EC8A41A1F768CCB8FCCD4753B1BF2F3B04FE0101E6431`。提交前重新核当前主树并作精确应用，不能整文件覆盖同行更改。

更名入口、版本、应用图标、共享主题、设置key、模型/提醒/导出、下方统计图和探针均不在此次首页补丁边界。工作树辅助脚本和报告仅供复现，不作为新的产品设置或说明。

## 下一步

四套配色等待用户选定，不先将B作为正式版本。选定后仅固定该卡的视觉方案并进行主控分配测试槽内的真实单/多人1440×960主窗口、DPI与前台交互检查，由主控亲自看图。最终安装包继续等待全项目验收和用户截图认可。
