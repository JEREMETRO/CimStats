# 已选首页卡面与强调字体

用户已决定默认浅蓝，仅保留浅蓝/深蓝两模式；深蓝改为既有WinUI强调蓝。此决定替代之前四方案待选状态。

城市摘要卡默认 `light`：`#F1F7FF` → `#E3EFFF`，深蓝文字。保留 `dark`：`#0067C0` → `#005FAF`，白字。代码调用为 `page.city.set_visual_variant('dark')`，恢复为 `'light'`；没有新增产品切换控件。卡高仍65/136逻辑像素，四/两列，复用已批准SVG，文字6px净空；更名入口、数据及下方图表逻辑不在卡面修改范围。

字号18以上或粗体强调的首页西文/数字由共享 `frontend/stats_typography.py` 提供字体。常规大值保留Regular400，重点、城市名称、时间、人口、环图总量及混合粗体线路名使用Semibold600。中文继续Microsoft YaHei UI回退。

采用实际注册的Segoe UI Variable字族，20px以上Display光学轴36、14–19pxText轴20、更小强调Small轴8；不存在独立Display/Text字族时不填假字体名称。缺Variable时首选Segoe UI，进程内读取系统已有字体，无字体安装或随包复制，内部状态/日志记录回退。

字体依据：[微软Windows字体指导](https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/typography)及[Qt字体轴接口](https://doc.qt.io/qt-6/qfont.html#setVariableAxis)。实际测试使用本机Qt6.11.2，未将当前在线Qt文档版本当本机版本。

## 当前验证

- 同一真实多人缓存 `jobs/a15a66a7b97e4497a699cc0e729e2358`，Szczecin，2013-04-10 23:59:22。两模式×宽/窄共4组合，实际独立Qt组件渲染退出0；配色切换前后字段、数据、13指标、16极值、图表尺寸/位置一致。
- 所有本页可见大号/粗体ASCII字母或数字QLabel逐一检查：实际glyph使用Segoe UI Variable并有fvar表，含混合中文的线路名称。强调字号/字重对应400/600。
- 原有page/charts回归146项通过，30.64秒，实际退出0。日志 `component-regression.log`，9条依赖弃用警告。
- 共享字体有Variable及无Variable各36个实际plain/QSS/rich形状测试通过，实际退出0。中文glyph回到Microsoft YaHei UI，Variable glyph为真实变量字体且400/600匹配。仅改变opsz的同28px样本实际宽度211→218，排除了只改属性未影响形状的假验证。
- 无Variable测试在新进程实际数据库没有Variable，只跳过可选的Variable系统字体加载；Segoe UI与中文字形由实际字体引擎生成，不修改系统字体。内部状态明确fallback_used=true、variable_available=false。
- 字体证据：`../home-review/typography-verification.json`、`typography-fallback-verification.json`。字体helper冻结SHA256：`41CDE0463AD76F31A62E5B51D7A9F72419708146ECF22ABCCFC1265DD462851B`。

预览：`context-light-multi-offscreen.png`、`context-dark-multi-offscreen.png`、`city-two-modes-wide.png`、`city-two-modes-narrow.png`。长文字构造边界另存fixture，不当真实存档。负责人已亲看默认首页及两模式对照。

这些为1204×860实际首页组件上下文，没有启动MainWindow、没有伪造原生1440×960窗口或系统DPI验收。主程序、其它页面字体和全项目验收由主控协调。1.1.0仍待全项目验收和用户最终截图认可。

## 精确接入

`home-selected.patch`仅包含page、latest_info_charts字体工厂及新增SVG三文件；`home-selected-manifest.json`记录前后SHA。页面候选 `41274912900B4BF02560C77F31259AF09975CC039879A85595A51F4DABC05272`；图表候选 `27BFCC3FC9038C62DC726CE0B3029BFB1A796C0F25544457EFD8CD3650C5758A`；SVG `FD14FC5E3D06382B1B6EC8A41A1F768CCB8FCCD4753B1BF2F3B04FE0101E6431`。

补丁SHA `268C7C518FB1E3FD682C4F480F706CBD670D5233B268BEA085C2A75D8F6EAFC5`，主树git apply --check实际退出0。共享helper由主控独立精确接入，其他owner调用同接口，不各自实现。

主控已应用三文件补丁，负责人已独立读取根文件确认：根page实际SHA `C45E94047FFE7BC52099CCDF22B759EC71E20E24F1592DA02212CD6030EF5A3B`，根charts `889449582D555D891FB9F1D5CCEEB78D02B3565F4A84C1BB0F639085241764C6`；二者与工作树标准换行文本完全一致，字节SHA差异来自git apply后的换行。根SVG与helper实际SHA分别为上述FD14FC、41CDE。未操作根index。

根统计三页、线路/时刻表已有共享强调字体调用。源扫描发现的共享stats_charts标题及22px总结、fluent_chart_view粗体圆环总计/百分比遗漏，已由共享图表owner补齐，并由主控独立接入字体小补丁。字体补丁仅含两文件，无菜单、大图布局或交互改动，SHA256为 `89d3f8370707ca966a9742a55df7e6dc7d9e99b4ea0d272f40b766c548619033`。标题保留根14px/600，摘要22px/700，圆环数字与百分比11px或14px/700；四条绘制路径的字体及文字矩形检查通过，普通单位字体保留。证据位于charts工作树 `docs/ui-redesign/root-chart-small/font-only/font-and-geometry-verification.json`。

负责人已独立读取当前根两文件，确认与字体候选标准换行文本完全一致，AST检查实际退出0。根stats_charts实际SHA为 `626C5C00682505489D91678BDB166C53257972F17DB67B8EF12D13E0A8292F16`；根fluent_chart_view为 `5F8860FDAE5B68AB24A7531F4762CD9686D2FC5EE7A973E53CD44BCE4E0AF7C3`。根helper仍为41CDE，首页page/charts仍为上述C45E/8894。已发现的强调字体源遗漏闭合；这是源接入与组件检查，不代替主窗口native、五档DPI及全项目视觉验收。主控拒绝的大图兼容改动仍单独修正。
