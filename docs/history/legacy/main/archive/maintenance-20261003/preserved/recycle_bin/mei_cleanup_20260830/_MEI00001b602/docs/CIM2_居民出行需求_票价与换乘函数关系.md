# CIM2 居民出行需求、票价与换乘函数关系

## 结论

可以通过反编译确认主要函数关系，但不能把居民选择还原成一个没有随机项的单一确定函数。v1.6.3 的实现是：先为公共交通网络寻找一条综合代价最小的路径，再计算该路径的票价和质量，最后把公共交通与步行、私家车进行带随机扰动的比较。

本报告对应的程序集为：

`D:\Program Files (x86)\Steam\steamapps\common\Cities in Motion 2\CIM2_Data\Managed\Assembly-CSharp.dll`

SHA-256：`2BD1CA1353C228FBBCC04DF2355D9CBC545F29DDD06EC1C10A6DD62D7BFDA4D2`

## 1. 居民群体参数

`CitizenData` 的静态数组按社会群体顺序排列：

| 社会群体 | TimeImportance | MoneyImportance | QualityImportance | CarProbability |
| --- | ---: | ---: | ---: | ---: |
| BlueCollar | 5 | 5 | 3 | 40 |
| WhiteCollar | 7 | 3 | 6 | 50 |
| Student | 3 | 10 | 2 | 20 |
| BusinessPeople | 10 | 1 | 10 | 60 |
| Pensioner | 2 | 4 | 7 | 30 |
| Tourist | 1 | 2 | 9 | 10 |

### 私家车初始概率

`CitizenData.TickInit` 先用居民 ID 派生的固定随机值：

```text
r = ((citizenID >> 11) & 255) * 1,000,000 >> 8
```

随后比较：

```text
r < CarProbability[group]
    * CityData.m_privateCarMultiplier
    * GameState.m_privateMotoring
```

满足时生成私家车车辆预制体，否则不生成。这是“是否有私家车”的门槛，不是公交线路之间的选择概率。

## 2. 公共交通路径搜索

### 调用参数

`CitizenData.TickIdle` 为公共交通创建：

```text
PathFindAction(
    requiredMask = 0,
    groupPenalty = 102400,
    qualityPenalty = QualityImportance[group],
    costPenalty = MoneyImportance[group],
    startSegments,
    endSegments,
    randomSeed
)
```

私家车路径搜索使用相同的 `requiredMask` 和 `groupPenalty`，但质量、成本惩罚均为 10。

### 段代价

`PathFindAction.Execute` 对每个图段使用固定点整数计算：

```text
segmentRef = segmentLength
              * (1024
                 + segmentQuality * qualityPenalty
                 + segmentCost * costPenalty)
              >> 10
```

连接到相邻段时，先加入连接长度：

```text
candidateLength = previousLength
                  + connectionSegmentLength
                  + currentSegmentLength
```

若当前段和前一段的 `m_groupObject` 引用不同，再加：

```text
candidateRef += groupPenalty       // 公交调用时为 102400
```

代码还用 `candidateRef >> 1` 和 `FixedMath.Random` 生成随机微扰，用于近似同值路径的排序稳定化。因此路径选择存在确定的代价主项，也存在可重复于同一随机种子的微小随机项。

### `m_groupObject` 的含义边界

`Segment.m_groupObject` 是一个序列化的对象引用。当前静态程序集能够确认它只用于“引用相等比较”，不能仅凭字段名证明它就是公司、线路或换乘站。把它解释为“发生组切换时的惩罚键”是准确的；把它直接解释成“换乘次数”是不准确的。

## 3. 票价函数

票价存放在 `CompanyVehicleTypeData`，字段为：

```text
m_singleLine
m_oneZone
m_twoZones
m_allZones
m_singleLineMonthly
m_oneZoneMonthly
m_twoZonesMonthly
m_allZonesMonthly
```

`CitizenData.TickIdle` 遍历最终路径的每个 `TransportPathSegment`，按线路所属公司和车辆类型 `LineData.m_type.m_loadIndex` 取得对应车型票价，并以 `LineData.GetZone(stopIndex)` 与下一个站点的区域值建立位掩码。

对同一公司、同一车型：

```text
跨越 2 个区域 -> m_twoZones
跨越 1 个区域 -> m_oneZone
其他情况      -> m_allZones
```

在单区域情况下还会计算：

```text
singleLineTotal = m_singleLine * m_tempNumLines
```

如果 `singleLineTotal < m_oneZone` 且为正数，采用单线票价总和；否则采用一区票价。多公司或多车型路径会分别累计，并比较自定义车型票价与 `m_generalVehicleTypeData` 的通用票价，选择较低的有效方案。月票按完全相同的区域分类分别计算。

### 月票的日均等效价格

住所和工作地点之间的通勤路线会进入月票判断：

```text
monthlyPrice * Random(25..40) < regularPrice
```

满足时，普通一次出行价格被替换为：

```text
effectivePrice = (monthlyPrice + 21) / 42
```

因此月票不是简单地按一次乘车收取整月价格，而是转换成带随机门槛的日均等效成本。

### 玩家调价边界

`SetTicketPricesAction.ApplyAction` 直接写入上述七个票价字段，然后调用 `CompanyData.CheckTicketPriceOffsets`。该函数按价格相对于最优价格的偏差进行滞后检查：偏差达到约 ±3 个内部单位后，偏移量在约 ±60 的范围内调整，并向零回归。它影响价格偏移提示/状态，不改变“路径按成本惩罚搜索、再按票价计算效用”的总体结构。

## 4. 公交、私家车、步行的最终比较

### 进入比较的量

在 `CitizenData.TickIdle` 中，局部量可按以下方式对应：

```text
Lwalk = 步行路径长度；无步行路径时为起终点直线距离 + 204800
Lcar  = 私家车路径长度；无私家车路径时为 -1
Lpt   = 公共交通路径长度 + 102400；无公共交通路径时为 -1
Tpt   = 7 * Lpt
Qpt   = 100 - (线路质量总和 / 公共交通段数)
```

私家车和步行的比较基准包含固定范围的随机扰动：

```text
Twalk = Lwalk * Random(17..24)
Tcar  = Lcar  * Random(2..9) + 1024000
Cwalk = (Lwalk * Random(43..58)) >> 19
Ccar  = (Lcar * (fuelPrice + Random(-15..30))) >> 19
Qwalk = Random(73..88)
Qcar  = Random(93..108) + vehicleQuality - 50
```

不存在对应路径时，相应量被钳制为正数或跳过。上述常数是游戏内部固定点单位，不应直接当作分钟或货币单位。

### 三个效用分量

代码把公共交通相对于当前替代方式的差异归一化到百分比量级：

```text
timeScore    = 100 * (Talternative - Tpt) / Talternative
moneyScore   = 100 * (Calternative - fare) / Calternative
qualityScore = 100 * (Qalternative - Qpt) / Qalternative
```

然后：

```text
timeScore    = Clamp(timeScore    * TimeImportance[group]    / 10, -100, 100)
moneyScore   = Clamp(moneyScore   * MoneyImportance[group]   / 10, -10000, 100)
qualityScore = Clamp(qualityScore * QualityImportance[group] / 10, -100, 100)
totalScore = timeScore + moneyScore + qualityScore
```

这里的 `Talternative`、`Calternative`、`Qalternative` 由可用的步行/私家车候选以及 `m_methodFilter` 决定，代码存在两次候选比较和模式过滤分支；因此不应把它简化成“只比较公交和汽车”。

票价增加会使 `moneyScore` 单调下降，时间更长会使 `timeScore` 下降，线路质量变差会使 `qualityScore` 下降；但最终选择仍受随机扰动、路径可达性、方法过滤器和月票分支影响。

### 最终模式值

`local 0x52` 最终被映射为：

```text
0 -> 步行分支（TickInitWalking）
1 -> 私家车分支（TickInitDriving）
2 -> 公共交通分支（TickInitTransport）
```

公共交通候选不可达时不会进入公交分支；私家车路径、车辆预制体或方法过滤器不满足时也会回退。公交出行不是“先抽一条线路再决定换乘”，而是先生成整条公共交通路径，再进入这里的方式比较。

## 5. 换乘决策

### 没有独立换乘概率函数

最终路径保存在：

```text
CitizenData.m_transportPath.m_path[]
```

每个元素是 `TransportPathSegment`，包含：

```text
m_line
m_stopIndex
m_cLenFrom[]
m_cLenTo[]
```

因此，在相邻路径段之间：

```text
path[i].m_line != path[i+1].m_line
=> 乘客在该站换乘
```

`CitizenData.TickTransport` 到达下一目标站后，检查下一段的 `m_line`；线路不同就寻找下一辆对应车辆，递增 `m_transportIndex`，继续执行下一段。换乘本身没有另一个“换乘概率”或“换乘票价函数”。

### 换乘相关的实际代价

连接长度由图中的连接对象提供：

```text
Segment.GetConnectionLengthFrom(i) = m_cLenFrom[i]（数组为空则为 0）
Segment.GetConnectionLengthTo(i)   = m_cLenTo[i]（数组为空则为 0）
```

`Segment.AddConnections` / `TransportPathSegment.AddConnections` 只负责扩充连接对象数组并保存对应长度数组；本身不计算等待时间，也不生成换乘概率。路径搜索把连接长度加入候选段长度，并在 `m_groupObject` 引用变化时增加 `groupPenalty`。这就是静态代码能确认的换乘抑制机制。

等待下一辆车、车辆拥挤导致的不满意、实际换乘失败等，是路径生成后的运行时状态；它们不能从 `PathFindAction` 的静态代价式单独推出。

## 6. 可以验证与不能唯一确定的部分

可以直接由程序集确认：

- 社会群体的时间、金钱、质量和私家车权重；
- 公共交通路径的长度、质量、成本和组切换代价；
- 区域票价、单线票价和月票日均等效公式；
- 最终模式比较中的三个效用分量及其权重；
- 换乘由 `TransportPathSegment` 序列中的线路变化决定。

需要实时对象图或运行日志才能确定：

- 每条实际道路/线路段的 `m_quality`、`m_cost` 数值；
- `m_groupObject` 对应的业务对象类别；
- 某个居民在给定时刻使用的随机种子和随机结果；
- 具体候选路径因 `m_methodFilter` 被过滤的原因；
- 等车、拥挤、不满意和再次规划对后续行为的影响。

因此，基于本程序集可以建立“可执行的模拟器”和可重复的单次决策回放，但不能仅靠静态反编译声称所有居民的总体客流是一个无随机误差的解析函数。

## 7. 对现有解析器的建议

现有存档解析应把以下字段作为运行时验证输出，而不是自行拟合：

`LineData.m_estimatedDuration`、`LineData.m_lineLength`、`LineData.m_vehiclesNeededTop`、`TransportPathSegment.m_cLenFrom`、`TransportPathSegment.m_cLenTo`、`Segment.m_quality`、`Segment.m_cost`、`Segment.m_groupObject`。

其中，线路统计中的“换乘次数”可以由相邻 `TransportPathSegment.m_line` 的变化计数得到；“换乘连接长度”应单独汇总 `m_cLenFrom/m_cLenTo`，不能把它误记为线路里程或首末站覆盖半径。

## 8. 重复站点、来回换乘和绕路的交通工程解释

这几类现象通常不是一个错误参数造成的，应分别诊断：

### 同一走廊重复站点

两条或多条线路在同一走廊设置大量重叠站点时，居民会把它们视为多个近似等价的候选。若线路质量、票价和到站等待成本接近，固定点随机微扰可能让不同居民选择不同线路，也可能在重新规划后换到另一条线路。它不一定表示居民在比较“线路名称”，而是在比较若干个网络段组合。

### 一直换来换去

从交通工程角度，常见原因是：

1. 换乘惩罚过低，换乘节省的车内时间大于换乘不便；
2. 班次间隔过大或不协调，乘客错过车辆后重新规划；
3. 重叠线路的服务质量/拥挤度快速变化，使另一条线路暂时变成较优方案；
4. `m_groupObject` 没有把两条实际不同的服务组区分开，导致路径层面的组切换惩罚不足；
5. 车辆故障、满载和等待状态触发运行时重新选择。

建议的调整顺序是：

```text
先提高 groupPenalty
再缩短并协调重叠线路的发车间隔
再检查车辆容量、拥挤和故障率
最后才调整价格和群体权重
```

可用于实验的寻路惩罚组为：

```text
0       无换乘抑制
102400  原始值
204800  强换乘抑制
```

如果提高 `groupPenalty` 后仍反复换乘，应优先检查班次间隔、车辆满载、故障和线路方向，而不是继续增大惩罚。

### 刻意绕路

绕路可能是合理的广义费用结果：直达线路虽然距离短，但可能票价更高、质量更差、拥挤更严重，或者步行/接驳连接更长。只有在以下情况下才可视为异常：

- 绕路路线的时间、票价、质量和换乘次数都不占优；
- 绕路只因极小的代价差反复出现；
- 路径包含明显的重复站点或循环段。

此时应检查 `Segment.m_cost`、`Segment.m_quality`、连接长度 `m_cLenFrom/m_cLenTo` 以及线路方向对象，而不能只看线路显示里程。

### 可以调整的参数及交通含义

| 参数 | 交通工程含义 | 对异常行为的作用 |
| --- | --- | --- |
| `groupPenalty` | 换乘惩罚/换乘不便 | 增大可减少不必要换乘和绕路换乘 |
| `qualityPenalty` | 对服务质量差异的敏感度 | 增大后更偏好高质量线路，可能增加绕路以避开拥挤 |
| `costPenalty` | 对线路成本/票价差异的敏感度 | 增大后更偏好便宜线路，可能接受更长路线 |
| `m_cLenFrom/m_cLenTo` | 接驳和站点连接距离 | 过小会使换乘看起来异常便宜，过大会抑制合理换乘 |
| 发车间隔/日期班次 | 等候时间和错过车辆风险 | 间隔过大或不同步会造成重复改道 |
| 车辆容量、质量、故障率 | 运行可靠性和拥挤服务水平 | 满载、故障会触发不满意和重新规划 |
| 票价字段 | 广义费用中的货币成本 | 只应在确认价格导致绕路时调整 |

不建议直接修改 `m_methodFilter` 来“禁止换乘”。它是交通方式可用性过滤器，不是换乘次数控制器；误改可能把整个公共交通方式过滤掉。

## 9. 街机、普通、专家模式是否改变换乘参数

程序集中的难度名称对应 `Arcade`、`Normal`、`Expert`。难度通过 `RulesetData` 应用规则项，已确认的规则项包括：

```text
vehicle-capacity, vehicle-maintenance, vehicle-quality,
vehicle-energy, vehicle-acceleration, vehicle-cost,
depot-speed, depot-capacity, depot-maintenance, depot-energy, depot-cost,
stop-catchment, stop-maintenance, stop-quality, stop-energy, stop-cost,
time-speed, growth-player, car-amount, car-acceleration,
citizen-amount, citizen-speed
```

其中没有 `transfer-penalty`、`group-penalty` 或类似的直接换乘规则项。因此：

- 三种内置难度不会直接把 `groupPenalty` 改成不同数值；
- 它们会通过居民速度、私家车数量、站点覆盖、车辆容量/质量和运营经济条件间接改变公交分担率和换乘次数；
- 如果加载了自定义 ruleset，仍需逐项读取其规则值，不能仅凭“街机/普通/专家”名称假定所有参数相同；
- 多人游戏必须使用一致的规则集和程序集，否则居民路径和重新规划可能出现不同步。

因此，针对重复站点和来回换乘，最有效的工程化做法是单独建立“换乘惩罚 + 班次可靠性 + 拥挤/故障”对照实验，而不是依赖切换难度模式来修正。
