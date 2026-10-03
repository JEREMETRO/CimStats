# 线路指标取值逻辑（Cities in Motion 2 v1.6.3）

## 线路里程

最终线路里程调用 `LineData.CalculateSegmentLength(stopIndex)`，对每个线路站点求和。其路径分支调用 `GetRoadLength`：

- 普通道路加入 `RoadData.m_length`。
- 高速道路加入 `RoadData.m_length >> 1`，即整数除以 2。
- 普通道路在对应路口增加固定点修正：道路数不超过 2 时加 `0x2800`；道路数超过 2 时，有红绿灯加 `道路数 × 0x23 << 10`，无红绿灯加 `道路数 × 0x14 << 10`。
- 每个站点路径段累加后，加入“下一站 `GetQuickPosition()` − 当前站 `GetQuickPosition()`”的有符号差值，再取 `max(0, value)`；这不是重新计算一条三维直线距离。

显示单位是 `固定点 / 1,024,000` 公里。独立公式与程序集调用的逐段核对需对实际输入重新执行，不能以其他存档的审计结果代替。

线路整理中的`地图里程`取折算前的有效道路长度：逐站遍历 `m_path[0 : Length-1]`，读取每段引用道路的 `RoadData.m_length`，排除最后的站点连接段。`RoadPathSegment.m_length` 是路径搜索缓存值，不是 `GetRoadLength` 的输入，不能直接累加。导出工作簿按当前统计口径将该值乘以 2；车公里人次和行车总里程使用乘 2 后的地图里程作为公里分母。`折算里程`按程序集 `LineData.CalculateSegmentLength` 重算并保持游戏显示值，不再额外放大：先以该道路长度为基础，快速道路减半，普通道路按路口道路数和信号灯增加修正，再加入相邻站点 `GetQuickPosition` 差值并取非负值。多人生存档中的 `m_lineLength` 仅作缓存，不直接信任。

线路信息表的`核定速度`以放大后的地图里程和程序集读取的单程时间计算：`地图里程 / 单程时间(分钟) × 60`，单位为 km/h。该值是线路统计口径的平均核定速度，不替代车型资产中的 `VehicleObject.m_maxSpeed`；后者以原始内部值保存在 `CIM2_车型尺寸速度目录.csv`，并可与车型长度、容量、加速度、制动等字段联合统计。

站点覆盖半径是另一套独立参数，不能用来反推线路里程。`StopObject.GetCatchmentArea` 对站点类型的 `m_catchmentArea` 求平均，再乘以站点自身的覆盖系数（构造函数默认 150），最后左移 10 位返回；它描述站点周边乘客吸引范围，不参与 `LineData.CalculateSegmentLength`。因此线路的道路里程与站点覆盖半径不需要相等；审计时分别记录有效道路里程、游戏折算里程和站间直线距离。

## 预计时间

`SelectionPanel.CalculateDuration` 先调用 `LineData.TickPaths(false)`。有路径且路径未失效时，每个站点区间使用 `SelectionPanel.GetRoadLength`（与 `LineData.GetRoadLength` 的 IL 相同），再加相邻站点快速坐标差；没有路径时使用站点位置的 `FixedMath.VectorLength3D`。

每个区间分别调用：

```text
(distance * 16 / VehicleTypeObject.m_averageSpeed
 + VehicleTypeObject.m_stopTime * 60 * stops) * GameState.m_frameTimeSpan
```

其中除法是整数除法，最后按 5 分钟槽位向上取整，最低 10 分钟。v1.6.3 车辆类型参数来自 `GameShared.bundle`：公交 3300/12，有轨电车 3500/8，无轨电车 3400/8，地铁和单轨 8000/15，水上巴士 5000/30。

## 最大配车需求

`SelectionPanel.CalculateNeededVehicles` 建立 7 天 × 288 个五分钟槽位的缓冲区。按 `m_activeDays` 选择时刻表，将每个班次从 `departure` 到 `departure + m_estimatedDuration` 的槽位计数；最大槽位计数写入 `m_vehiclesNeededTop`，平均值为槽位总数左移 10 位后除以 2016。

多人成档中，线路缓存可能是零、10 分钟、1 辆等未重建值。程序因此分别报告缓存值和独立重算值；缓存无效时使用上述重算值，缓存有效但与当前路径不一致时标记为“路线已变化”。

## 开线日期

线路没有单独的开线日期字段。线路对象继承的 `ObjectData.m_buildTime` 在 `AddObjectAction.AddObject` 创建对象时写入并序列化保存；`LineData.m_lineEditTime` 仅在 `InsertStop` 或 `RemoveStop` 时更新，代表最近改线日期。共享站点的 `StopData.m_buildTime` 不能作为线路开线日期。

`SetActiveAction.ApplyAction` 只调用 `LineData.SetActive` 修改 `m_active`，程序集没有保存“首次启用时间”的字段。因此导出中的“开线日期”采用 `m_buildTime`，这也是游戏 `InfoTool.FormatObjectInfo` 计算平均客流时使用的日期基准；若要严格区分“创建线路”和“首次启用”，当前存档无法无损恢复后者。

平均客流的整数计算顺序与面板一致：

```text
elapsed = max((simulationTime.Ticks - m_buildTime) >> 10, 1)
averageFixed = (m_totalTransported * 864000000000) / elapsed   # 整数除法
显示值 = FormatNumberFixed(averageFixed)                      # 固定点右移 10 位
```


## 周化财务与运行值

线路 `m_income`、`m_expenses`为固定点周化估计，显示先除以 1024，再按货币子单位除以 100；导出除以 102400。能源、燃料、维护、司机成本采用以下尺度：

```text
能源 = 电力估算 × 电力价格 / 102400
燃料 = 燃料估算 × 燃料价格 / 102400
维护 = 维护估算 × 3 × 维护工资 / (1440 × 102400)
司机 = 司机估算 × 司机工资 / (1440 × 102400)
```

这是 `CompanyData.SimulationTick`按七天标尺、约四分之一周时间常数平滑的周化运行估计，不是过去三天、半周或最近七天实际金额之和。周收支报表日期使用模拟时刻所在自然周，观测截止点另示；与[历史期间现金流](history-metrics.md)分开。

`m_vehiclesRunning`每 tick 累加运行车辆，每小时写入 `hourly_average × 1024`；这是小时平均运行量，不是车辆资产数或瞬时峰值。真实时刻表发班按日期掩码与记录统计，工作簿按周一至周四、周五、周六、周日分类。

实现与验证：[build_line_workbook.py](../../src/build_line_workbook.py)、[build_company_workbook.py](../../src/build_company_workbook.py)、[extract_runtime_data.py](../../src/extract_runtime_data.py)。输入存档和反编译中间报告不随文档提交。
