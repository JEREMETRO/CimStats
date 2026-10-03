# 最新信息分包接口（已确认方案）

本次执行工作区：`D:/test/CIM2_SaveStats/.worktrees/latest-info`。父会话负责共享接线和测试排期；各包只写自己的文件，不另派代理或聊天，不向其他聊天发消息，不操作主项目索引。

## A → B / D：数据

A在 `src/latest_info_model.py` 定义以下数据类型。全部类型使用dataclass；数值统一允许 `Decimal | float | int | None`，缺测为None；不在数据层放Qt对象或颜色。

```python
@dataclass(frozen=True)
class InfoValue:
    key: str
    title: str
    value: Decimal | float | int | None
    unit: str = ''
    scope: str = ''
    reason: str = ''
    complete: bool = True

@dataclass(frozen=True)
class LineSummary:
    key: str
    name: str
    mode: str
    company_id: str
    passengers: Decimal | float | int | None
    departures: Decimal | float | int | None
    passengers_per_departure: Decimal | float | int | None
    passengers_per_vehicle_km: Decimal | float | int | None

@dataclass(frozen=True)
class LineHighlight:
    title: str
    line: LineSummary | None

@dataclass(frozen=True)
class ModeCount:
    mode: str
    value: Decimal | float | int | None

@dataclass(frozen=True)
class LatestInfoSnapshot:
    session_key: str
    company_id: str
    mode: str
    city_name: str
    simulation_time: datetime | None
    population: Decimal | float | int | None
    save_name: str
    companies: tuple[tuple[str, str], ...]
    modes: tuple[str, ...]
    metrics: tuple[InfoValue, ...]
    highlights: tuple[LineHighlight, ...]
    lines: tuple[LineSummary, ...]
    passenger_top10: tuple[LineSummary, ...]
    passenger_modes: tuple[ModeCount, ...]
    departure_modes: tuple[ModeCount, ...]
    total_departures: Decimal | float | int | None
    trend: Result | None
    scope_text: str

def build_latest_info(data: dict, company_id: str = '', mode: str = '综合', *, cancelled=None) -> LatestInfoSnapshot: ...
```

13指标固定ID顺序：`line-count`, `fleet`, `drive-minutes`, `turnover`, `weekly-income`, `weekly-expense`, `profit`, `interval`, `speed`, `passengers-per-run`, `passengers-per-km`, `public-transport-share`, `transfer-coefficient`。显示顺序可分层，数据顺序保持原11项加2项。

四亮点顺序：当日最大客流线路、当日最小客流线路、当日最多班次线路、当日最少班次线路。`lines`保留过滤后全部线路供真实钻取；Top10是至多10条真实线路，空范围不填零。

公共交通分担率为全市模拟当日有效观测比例，忽略公司/制式筛选；换乘系数为所选公司模拟当日有效历史总客流/总分区出行量，缺少对应制式分母时不跟随制式过滤，`scope/reason`须明示范围。趋势跟随公司+制式；读取原始小时实际观测，当前小时可注明部分观测；缺小时断线，不写未来小时。

原11项读取原有可信字段并保留定义；平均间隔与新版线路页时间范围差异需在A报告中明确，不把未启用/运行日未知组计入。城市名缺失用“未提供城市名称”；人口缺源None；以模拟时钟而非现实时间决定当天。`companies`用稳定ID对应显示名；`modes`完整保留实际存在制式。

## B → D：首页UI

`frontend/latest_info_page.py` 暴露 `LatestInfoPage(settings=None, parent=None)`：

- `set_session(data: dict)`：只设置元数据/公司/制式选择并清除旧快照；不重复在UI线程计算数据。
- `set_snapshot(snapshot: LatestInfoSnapshot)`：绘制A快照。
- `clear_session()`；`scope() -> tuple[str, str]`；`set_alert_panel(panel: QWidget)`；`export_target() -> QWidget`。
- 信号 `scope_changed(str, str)`、`open_save_requested()`、`line_requested(str)`、`share_requested()`、`report_requested()`、`line_export_requested()`、`company_export_requested()`。
- 公开 `company_combo`、`mode_combo` 便于行为验证。内部控件不作为跨包接口。
- 集成扩展 `set_workbook_availability(line_available: bool, company_available: bool)`：默认关闭，清空/新会话清状态；原线路/公司XLSX按钮及更多菜单只在当前快照有效且源文件存在时启用，分享/报告仍由快照有效性决定。D检查真实outputs及Path.is_file后调用公开接口，不接触B私有控件。该小API及必要动作测试由父在D sole component窗口临时移交D维护，时间/布局/图表仍归B且冻结。

首页自己持有与其他页一致的紧凑标题/文件/操作行；集成时隐藏旧首页外部header。标题“最新信息”，打开存档主按钮，原XLSX/分享/报告次按钮；窄窗可收纳更多菜单，动作不能丢失。生产按钮在无有效快照时禁用对应导出/分享，打开存档持续可用。

布局复核裁定：城市Hero必须保留在主区上方全宽紧凑卡中，不退入260px提醒窄栏；城市/日期星期时间/人口/存档应有明显层级和分区。4项核心（线路、车辆、收入、利润）与9辅助指标分层，核心略大，不以13卡全部等权排布。底部可采用趋势/较宽Top10/班次三卡同排，以保留Hero预算及完整分类；所有卡片仍满足共享21px主值/12px单位，不缩小字体删项。

`frontend/latest_info_charts.py` 只消费LineSummary/ModeCount/Result，沿用共享字体/颜色/轴/tooltip。时间趋势使用共享ChartPanel；分类图允许独立适配现有分类绘制方式，不将排行伪装成时间数据，不修改共享图表源。Top10默认完整10条；保留综合/制式钻取和返回动作。班次默认环形+完整制式列表，原有有效班次排行/返回入口继续可达。快照所有制式计数与图一致，非正值不伪造扇区。

## C → D：提醒

`src/latest_info_alerts.py`：

- `default_alert_filters(simulation_time, company_ids: tuple[str, ...]) -> FilterState`：上一完整模拟日 `[昨日00:00,今日00:00)`，比较前一日；使用hour粒度，稳定ID选定公司，支持全部公司。
- `build_latest_alerts(store: HistoryStore, filters: FilterState, thresholds=(5,20,100), cancelled=None) -> DashboardResult`：复用原 `build_dashboard/alerts_for_result`；无法计算不生成，不新增门槛。无可比数据允许返回空alerts，不能假装当前有报警。

`frontend/latest_info_alerts.py` 暴露 `LatestInfoAlertsPanel(settings=None, parent=None)`：

- `set_snapshot(snapshot: DashboardResult | None, session_key: str, companies: dict[str,str])`，`clear_session()`、`mark_read(alert)`、`mark_all_read()`；`thresholds`属性返回三阈值；`alerts_enabled`属性返回开关值。
- 信号 `thresholds_changed(object)`、`enabled_changed(bool)`；父接收后重新计算提醒，开关只改变展示/主动查询，不改变原警报判定。
- 右栏最多显示5条真实提醒、真实未读数；“全部”对话框保留所有提醒、单条/全部已读；点击详情显示指标/原值/公司/两期窗口与原reason。
- 阈值入口迁入首页，用原设置键和默认值；已读复用 `stats_alerts._alert_id` 身份，不拷贝重写算法。不能继续在统计页显示第二份提醒UI。
- 无数据/不能比较/无达标提醒用准确空态；不造严重性、墙上时钟时间或线路警报。

## 执行限制与报告

模型pytest必须 `--noconftest`，因为全局 `src/conftest.py` 会自动创建QApplication。Qt/native暂时等待父会话明确放行；此期间B/C只写测试与设计，不写未经失败验证的GUI实现。纯模型可立即RED→GREEN。各包不提交、不stage，由父会话在独占索引窗口统一限定提交。

报告写到 `.superpowers/sdd/2026-10-01-latest-info/task-A-report.md`、B/C对应文件。最终聊天回复只给状态、修改文件、测试摘要与未完成条件，父会话通过读取报告/等待结果协调；不自行发送跨聊天消息。
