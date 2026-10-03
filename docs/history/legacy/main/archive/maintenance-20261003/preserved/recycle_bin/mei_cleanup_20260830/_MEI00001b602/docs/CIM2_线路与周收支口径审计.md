# CIM2 v1.6.3 口径审计

## 线路里程、预计时间、最大需求

线路整理使用车辆路线和时刻表重新计算，不直接信任多人存档中可能过期的 `LineData` 缓存。

- 里程：`LineData.CalculateSegmentLength`。每个路径段调用 `GetRoadLength`，普通道路使用道路长度，快速路使用道路长度的一半；普通道路再按路口道路数和信号灯追加固定点修正；每个站点最后加入下一站与当前站 `GetQuickPosition()` 的有符号差值（不是三维直线距离），再取非负值。
- 预计时间：`LinePanel.CalculateDuration`。车型速度和停站时间来自 `VehicleTypeObject.CalculateDuration`；首个车库站不计停站时间；结果按 5 分钟向上取整，最低 10 分钟。
- 最大配车需求：`LinePanel.CalculateNeededVehicles`。按 7 天、2016 个五分钟槽，使用 `m_activeDays` 和每个发班记录覆盖预计行程时长，取同时运行车辆峰值。

`src/audit_road_formula.py` 已对当前 quicksave 的 73 条线路逐段验证，手工道路公式和程序集 `CalculateSegmentLength` 的最大差异为 0。

## 开线日期与平均客流

线路对象继承 `ObjectData.m_buildTime`。`AddObjectAction.AddObject` 在新对象加入模拟时把它设置为 `GameState.m_simulationTime`；`LineData.Serialize/Deserialize` 会持久化该字段。`LineData.m_lineEditTime` 仅在插入或删除线路站点时更新，是最近改线日期。

`InfoTool.FormatObjectInfo` 的平均客流公式为：

```text
elapsed = max((simulationTimeTicks - m_buildTime) >> 10, 1)
average = (m_totalTransported * 864000000000 / elapsed) / 1024
```

因此站点的 `m_buildTime` 不能代替线路开线日期。当前 quicksave 的 73 条线路均晚于其最早站点时间，已验证该差异普遍存在。

## 周收支与运行值

线路 `m_income` 和 `m_expenses` 是固定点的周化估计，线路界面显示时右移 10 位，即除以 1024，再按货币子单位除以 100，最终导出除以 102400。

能源、燃料、维护、司机支出按 `CompanyData.SimulationTick` 直接换算：

```text
能源 = 电力估算 × 电力价格 / 102400
燃料 = 燃料估算 × 燃料价格 / 102400
维护 = 维护估算 × 3 × 维护工资 / (1440 × 102400)
司机 = 司机估算 × 司机工资 / (1440 × 102400)
```

这些估算的尺度是 7 天标尺、半周平滑的周化值，不是当前存档已经过的 3 天，也不是简单地把最近 7 天逐日相加。

`m_vehiclesRunning` 每个模拟 tick 累加正在运行的车辆数；每小时结算为：

```text
hourly_average × 1024
```

历史写入点使用 `HistoryData.SetData`，其时间戳是整点；当前存档最后完整槽位为 2013-04-10 23:00，当前模拟时间为 23:59:22。运行车辆历史值仅作为诊断，不再放入正式公司周收支表。真正的时刻表发班次数来自线路时刻表的日期掩码与发班记录，在线路工作簿中按周一至周四、周五、周六、周日分别统计。

周收支中的收入、支出和各项估算是 `SimulationTick` 按 7 天标尺、约四分之一周时间常数进行平滑更新的周化估计，不是把当前周一至存档时刻的金额简单相加。它反映按当前运行状态预计一周的值，因此报告日期采用当前模拟时间所在周的平滑周期：周一为起始日，周日为结束日；存档时刻仅是数据观测截止点，不作为周期结束日。
