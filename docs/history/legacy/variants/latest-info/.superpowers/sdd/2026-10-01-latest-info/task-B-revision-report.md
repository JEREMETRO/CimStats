# 包B第二轮修订交付（2026-10-02）

**历史阶段记录**：用户随后再次否决三组长卡，并补充模块图标、间距统一和四个独立蓝紫极值条要求。最新实现、103项组件回归、四真实范围A+C组件截图与冻结哈希见同目录`task-B-business-report.md`；下述容量fixture及旧哈希不代表当前候选。

仅修改包B四个自有源码/测试文件及本目录证据。未修改统计页共享源码、模型、controller、提醒源码、Git index或主树。所有B Qt进程已经结束，B独占离屏验证时段可释放给C→D→E。没有进行原生窗口、全局鼠标、MainWindow、整套测试或真实存档视觉验收。

## 对本轮用户要求的逐项覆盖

|要求|落实及证据|验收边界|
|---|---|---|
|卡片排布及合并|四项核心运营、九项辅助指标、四张线路亮点分别合并成三组白色卡面。核心数字24px、辅助21px，线路亮点仅对应极值19px强调；删除说明按钮、指标右上角范围标签和线路起讫显示，保留单位及缺失原因tooltip。|离屏实际字体布局检查与新版PNG已核对。|
|结构图合并|独立堆积条已移除；环心显示总数/单位，六种制式旁显示准确数量和百分比；缺失总量不强行补成100%。|完整、不完整、零值及六位环心检查通过。|
|排行/占比/返回|稳定标题当日客流结构、班次结构。线路排行/线路占比同卡切换，保留图内真实mode；返回制式分布清除图内mode。返回图标固定28px占位并支持键盘。其他线路（N条）按真实剩余线路统计，零值保留行但不绘扇区。|扇区、列表、按钮和键盘本地真实事件及双卡独立状态通过。|
|趋势图统一|直接继承ChartPanel._append_time_segments及FluentChartView绘制，没有首页重写绘图效果。复用统计页微渐变、线宽、坐标轴、图例、悬浮信息和公司颜色。仅提供line模式；实际QLineSeries按选中公司绘制单线/双线，没有QAreaSeries及面积图选项。|用户最后要求微渐变后，已删除先前关闭微渐变的override；绘制方法对象身份和单/双线检查通过。|
|颜色统一|制式色调用ChartPanel._category_color并注入统计页实际使用DATA_CATEGORY_COLORS；公司ID按统计页同规则排序映射DATA_COMPANY_COLORS。未知制式复用共享稳定映射。|比较实际统计ChartPanel实例，不以默认静态色板冒充交通统计色板。|
|提醒|保留右上260×494宿主，底部三图使用整页宽度。|B图片仅为宿主占位；C实际提醒及D接线待集成验收。|
|城市与范围|采用A的可靠地图来源解析及来源tooltip；同会话范围变更只保存图态，不携带旧数值或扩大snapshot范围。保留D的set_workbook_availability与导出门禁。|来源/时间/身份/范围组件检查通过；真实存档地图来源及controller路径待A/D/E联验。|
|1440及系统缩放|离屏组件1204×852、DPR1、纵向滚动0；上区932×494，三图288/448/448×282。|此为容量样例，不能等同1440×960整窗或Windows125%缩放验收；交E原生复核。|

## 已确定的公开图态合同

`LatestInfoPage.capture_chart_state()`返回新建字典：`{'session_key': str|None, 'scope': (company_id, mode), 'passengers': {'view': 'structure'|'ranking'|'line_share', 'mode': str|None}, 'departures': 同上}`。structure的mode为None；ranking及line_share都支持真实图内制式key，None代表页面允许范围内的全部制式。返回值不含快照、线路值、Qt对象或私有widget。2026-10-02授权指导要求排行与占比互切保留mode，此合同已同步更新。

`LatestInfoPage.restore_chart_state(state, *, allow_scope_change=False) -> bool`仅在本页已有门禁接受的当前snapshot时恢复。无snapshot、session_key不等、非法scope、默认strict下scope不等均拒绝且不改变现有图态。`allow_scope_change=True`只放宽同会话scope匹配；当前图内制式不存在时该卡回structure，另一张卡继续恢复自己的有效状态。综合ranking与line_share始终从当前snapshot重绘，不恢复旧数值。返回True代表页面身份门禁接受，单卡失效mode回structure属于有效安全恢复。

每卡公开`capture_state()/restore_state(state)`、`show_structure()/show_ranking(mode=None)/show_line_share(mode=当前图内mode)`。set_data普通更新保留有效状态；clear重置structure。保留原PassengerRanking三参数入口，新增可选total参数；不传时严格从完整passenger_modes求总量。两卡set_data均新增可选关键字`scope_mode='综合'`，只决定当前页面范围的显示与图内选择入口，不重算或扩大传入线路范围。DepartureStructure原三参数入口兼容。

同一snapshot重绘自动保留双图状态；全局范围变化时B保留纯图态意图并先清空旧数据，接受新snapshot后按上述同会话规则恢复。controller清空/重建过程由D使用capture/restore合同衔接；换存档不恢复。

## 当前验证状态

父在初始静态阶段后明确授予B独占串行offscreen Qt槽，全部采用临时INI、减少动效，无用户设置写入。最初新增26项实现前全部失败（4.95s，actualexit=1）。后续用户需求分别先确认失败后修正：旧标题/返回、真实其他N、删除说明/徽标、实际交通色板、亮点字段宽度。

最新全体组件回归：`src/test_latest_info_page.py src/test_latest_info_charts.py`，**94 passed in 12.95s，actualexit=0**，应用实际Microsoft YaHei UI字体。此时趋势关闭微渐变。其后用户明确要求与统计页同样微渐变，单/双线测试先**2 failed in 1.27s，actualexit=1**，删除首页绘制override后，趋势限定模式及单/双线/共享方法身份检查**3 passed, 52 deselected in 1.08s，actualexit=0**。不把前一次94项描述成最后微渐变改动后的全文件重跑。

本轮最终渲染退出0，三张PNG已重新生成；最终结构、占比图逐张查看，排行图此前同一布局已查看，之后只改变趋势共享微渐变和占比环径。曾发现实际字体下136px占比环隐藏825,684，复现为两项RED，改152px后随94项通过，最终PNG环心数字完整可见。

证据：`task-B-revision-structure.png`、`task-B-revision-ranking.png`、`task-B-revision-line_share.png`，元数据`task-B-revision-component-metadata.json`，渲染器`task-B-revision-render.py`。均为明确容量fixture、离屏组件截图，未声称真实存档/原生整窗视觉通过。最终元数据short_numeric_labels为空、vertical_scroll=0，两个公司共享折线带微渐变。

最终源码SHA256：

- frontend/latest_info_page.py：23FFC47E1797C72E7B9C6654BA2BBA4A51A2DA5E4B7AF7C961F9DA3122501640
- frontend/latest_info_charts.py：802AAE44EA1B26574CCD82DB24C117A42C70B930D3341E577F4F7A1EF129EC2D
- src/test_latest_info_page.py：8F9515C8BD69CC859332564CC4A8376550918AE7B2D15522AD2CBE56F359B65E
- src/test_latest_info_charts.py：C3C0FFCA34DDC6AA37118B2D097B92D5276AD4E4FC32E19DE249BEFF29C0D6F4

后续：D使用以上公开图态合同衔接controller及导出状态；C接入提醒；E进行真实存档、1440×960整窗、125%系统缩放和原生全屏交互验收。B不把离屏容量证据冒充这些未执行项。
