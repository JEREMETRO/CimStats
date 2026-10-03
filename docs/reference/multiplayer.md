# Cities in Motion 2 v1.6.3 多人模式同步机制

## 结论

多人模式采用“各端本地执行同一套模拟、玩家操作按帧锁步同步”的方式。它不是每家公司一套居民/交通/经济模型，也不是主机持续发送完整城市状态；每个客户端都持有一份完整 `GameState`，并在相同的模拟帧上执行场景、道路、车辆、居民、城市和公司经济的 tick。

从工程含义说，这是一个共享网络状态的共同模拟：公司的经营权是分开的，但城市交通系统和居民需求环境是共同的。物理实现上，各端分别重算同一状态；网络传输的主要内容是“谁在第几帧做了什么”，而不是每帧的车辆坐标、居民坐标或财务快照。

## 反编译范围

- 程序集：`game_runtime/Managed/Assembly-CSharp.dll`
- 版本：游戏 `v1.6.3`
- SHA-256：`2BD1CA1353C228FBBCC04DF2355D9CBC545F29DDD06EC1C10A6DD62D7BFDA4D2`

## 联机初始化阶段同步的参数

`Networking.SetLevel` 通过 `NetworkView.RPC("SetLevelName", RPCMode.Others, ...)` 广播以下开局参数：

| 参数 | 含义 |
|---|---|
| `levelName` | 地图/关卡名称 |
| `rulesets` | 规则集文件名或规则集列表 |
| `companyCount` | 公司数量 |
| `playersPerCompany` | 每家公司允许的玩家数 |
| `cityGrowth` | 城市增长设置 |
| `goalType`、`goalTarget` | 游戏目标及目标值 |
| `timelimit` | 时间限制 |
| `loans` | 贷款规则 |
| `lobbyID` | Steam 大厅标识（由 `SetLevelName` 的第十个参数携带） |

规则集随后由 `RulesetData` 序列化并压缩，通过 `SetRulesetData` 广播；没有规则集时发送 `ClearRulesetData`。因此街机、普通、专家的差异首先体现在同一份规则集参数上，而不是三套不同的居民模拟程序。

已确认的规则项包括：车辆容量、维护、质量、能源、加速度和购置成本；车库速度、容量、维护、能源和成本；站点覆盖范围、维护、质量、能源和成本；时间速度、玩家增长效应、私家车数量与加速度、居民数量与速度。程序集中的键名依次为 `vehicle-capacity`、`vehicle-maintenance`、`vehicle-quality`、`vehicle-energy`、`vehicle-acceleration`、`vehicle-cost`、`depot-speed`、`depot-capacity`、`depot-maintenance`、`depot-energy`、`depot-cost`、`stop-catchment`、`stop-maintenance`、`stop-quality`、`stop-energy`、`stop-cost`、`time-speed`、`growth-player`、`car-amount`、`car-acceleration`、`citizen-amount`、`citizen-speed`。这些是开局共同参数，不是每帧重复发送的状态量。

玩家加入时，`JoinServer`/`PlayerJoined` 同步：玩家名、平台 ID、性别、头像和服装样式、皮肤/头发/衬衫/帽子颜色、公司名、公司标志、公司颜色、公司索引以及 ready 状态。`PlayerCompany`、`PlayerReady`、`PlayerNotReady`、`PlayerLoaded` 和 `StartLoading`/`StartSession` 负责公司选择、准备状态、加载状态和会话开始状态。

## 每帧实际同步的内容

### 两种网络消息

`GameState.SendPlayerData` 和 `GameState.SendPlayerFrame` 先把数据放入 `BufferedPlayerData` 链表。该记录明确包含：

- `m_player`：玩家索引；
- `m_type`：消息类型；
- `m_data`：压缩后的动作数据；
- `m_frameIndex`：帧号。

`GameState.Update` 再通过 `NetworkView.RPC` 广播：

- `PlayerData(playerIndex, dataType, compressedData)`：有动作时发送；
- `PlayerFrame(playerIndex, dataType, frameIndex)`：没有动作时发送空帧。

两次 RPC 的 `RPCMode` 常量都是 `1`，对应 Unity 的 `RPCMode.Others`，即发送给其他节点而不再次发送给本节点。空帧分支在 `LocalPlayer.SendEmptyFrame` 中可直接确认；有动作分支在 `LocalPlayer.SendAction` 中先 `DataSerializer.Serialize`，再 `CompressBuffer`，远端在 `RemotePlayer.DataAvailable` 中 `UncompressBuffer` 后反序列化。

### 动作包的结构

`PlayerActionGroup.Serialize` 写入该组的帧索引以及首、尾动作引用；每个动作还带有 `PlayerAction.m_frameIndex` 和链式的 `m_nextAction`。当前程序集中的玩家动作及其传输字段如下：

| 动作 | 同步字段 |
|---|---|
| `AddObjectAction` | 新对象的完整对象数据（`WriteObject`） |
| `RemoveObjectAction` | 对象 ID（24 位） |
| `InsertStopAction` | 线路对象 ID、站点对象 ID、插入序号 |
| `RemoveStopAction` | 线路对象 ID、删除序号 |
| `SetNameAction` | 对象 ID、子项、编号、新名称 |
| `SetTimeTableAction` | 线路对象 ID、完整时刻表数组 |
| `SetActiveAction` | 线路对象 ID、启用/停用标志 |
| `SetVehicleAction` | 原车库 ID、新车库 ID、槽位、车辆 ID、车辆编号、车型标识 |
| `SetSpeedAction` | 游戏速度 |
| `KickPlayerAction` | 被投票玩家索引、投票值 |
| `UpdateLaneFlagAction` | 道路对象、车道标志 |
| `SetTicketPricesAction` | 运输制式标识、单线/一区/二区/全区票价及三种月票价 |
| `SetWagesAction` | 驾驶员、维护、检查员工资，检查员数量，上座率/拥挤参数 |
| `SetZonesAction` | 颜色、笔刷大小、区域位置数组 |
| `TakeLoanAction` | 贷款完整对象数据 |
| `PetitionAction` | 接受标志、请愿索引、场景标识 |
| `SaveGameAction` | 存档文件名 |

`AddSegmentAction`、`RemoveSegmentAction`、`UpdateSegmentAction`、`PathFindAction` 继承的是独立的 `Action`，不是 `PlayerAction`；它们用于内部路径/道路处理，不能据此说成是玩家每帧直接广播的动作。路径查找结果是否进一步由道路/线路操作触发，要看相应的 `PlayerAction`，而不是把 `PathFindAction` 当作完整城市快照。

## 是否主机权威

程序集证据不支持“主机计算后把完整结果下发给客户端”的模型：

1. `GameState.Update` 在每个节点都从本地 `BufferedPlayerData` 取出消息，并用 `RPCMode.Others` 广播 `PlayerData`/`PlayerFrame`。
2. `RemotePlayer.DataAvailable` 只把远端动作组放入本地 `ActionManager`，没有写入车辆位置、居民位置、公司财务或城市指标的网络快照。
3. `ActionManager.UpdateFrame` 遍历本地 `m_players`，要求每个玩家在同一输入帧就绪；`ApplyFrame` 再在本地执行所有动作。
4. `GameState.SimulationStep` 随后在本地依次调用 `ScenarioManager.SimulationTick`、`ObjectManager.SimulationTick`、`TransportManager.SimulationTick`、`CityManager.SimulationTick`、`CompanyData.SimulationTick` 和 `DataManager.SimulationTick`。

所以更准确的表述是：服务器/主机负责大厅、连接、初始参数、消息转送和部分会话控制；模拟状态采用多节点复制的确定性锁步。不存在证据表明某一个主机节点持续拥有唯一的居民、交通或经济模拟权威，也没有发现运行中的状态哈希/完整快照纠偏机制。若各端程序集、地图、规则集或随机数种子不一致，锁步结果可能产生漂移。

## 锁步与延迟处理

- `ActionManager.Awake` 在多人模式把 `m_bufferedActionFrames` 设为 `4`，单机为 `1`，并把输出帧初始化为负的缓冲帧数。
- `ActionManager.UpdateFrame` 对所有玩家调用 `CanChangeFrame`；未准备好时在 `m_frameLock` 上等待。
- `RemotePlayer.CanChangeFrame` 以 `PlayerActionQueue.CheckFrame` 检查目标帧，未收到该帧时设置 `m_waitingForFrame`；超过接收时间会触发超时提示并最终断开玩家。
- `LocalPlayer.FrameFinished` 从本地队列弹出当前帧动作；无动作发送空帧，有动作发送压缩动作组。
- 所有玩家完成当前帧后，`UpdateFrame` 才递增 `m_inputFrame`；`SimulationStep` 再应用动作并推进共同的城市模拟。

这意味着联机中的“共同模拟”不是共享内存，而是共享帧序列和操作顺序。居民出行、换乘、线路客流、车辆运行、公司收入支出等结果属于共同城市状态的派生结果，不按公司分别运行一套需求模型；不同公司只决定谁可以发出哪些经营操作，以及这些操作作用于哪家公司资产。

`GameState.InitializeNetworkCompany` 还给出了更直接的公司层证据：公司索引相同的玩家会引用同一个 `CompanyData`；不同公司对象则一起进入同一个 `GameState.m_companies` 数组，由同一条 `SimulationStep` 轮流推进。从交通运输工程角度看，居民、活动地点、道路容量和出行需求构成统一市场，各公司的线路、票价、班次和运力是同一市场中的不同供给方案；一家公司改变服务水平会改变共同网络中的路径阻抗与客流分配，而不是只改变一套属于该公司的“私有居民”。

## 仍不能从该程序集单独确认的事项

- Steam/Unity 底层传输层是否在 RPC 之外做可靠重传、排序或加密；
- 某些 `WriteObject` 对象内部字段的具体压缩策略；
- 网络异常时是否存在未在 `Assembly-CSharp.dll` 中实现的底层回滚或连接恢复；
- 不同游戏模式是否在外部配置文件中另有规则集覆盖。

这些事项不影响当前核心结论：v1.6.3 的游戏逻辑层同步的是初始化参数、玩家状态和按帧玩家动作；城市模拟在各端共同锁步推进，而不是主机独占计算后同步完整结果。
