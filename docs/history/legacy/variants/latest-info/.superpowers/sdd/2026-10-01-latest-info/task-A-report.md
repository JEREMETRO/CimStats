# 数据包 A 交付报告

状态：本包实现和纯模型验证完成，等待父会话集成及独立验收。工作区固定为 `D:/test/CIM2_SaveStats/.worktrees/latest-info`。本包未 stage/commit，未启动 Qt，未重新解析存档，未修改主目录缓存、存档、probe 或共享业务模型。

## 文件与接口

新增产品文件：`src/latest_info_model.py`。

新增测试文件：`src/test_latest_info_model.py`（E-A-01 定向修复后共 31 项纯模型测试；最新验证见末节）。

报告：本文件。真实复算证据：同目录 `task-A-real-audit.json`，包含 17 个筛选范围的 13 指标、分子/分母、极值键、10 条排行键、完整班次分类、观察点数，以及输入 CSV 和最终模型/测试的 SHA-256。

已兑现合同中的五种 frozen dataclass：`InfoValue`、`LineSummary`、`LineHighlight`、`ModeCount`、`LatestInfoSnapshot`，字段和顺序按冻结接口。数值计算使用 Decimal，缺测、不可计算比例为 None，真实观测零值保留。`build_latest_info(data, company_id='', mode='综合', *, cancelled=None)` 无 Qt 依赖；只读输入；取消抛既有 `QueryCancelled`。

`companies` 保存公司 ID 与显示名，即使公司重名也不混合；只对没有显式 ID 且名称唯一的旧数据做名称回退。`modes` 包括实际线路制式、正值车队制式和非未来历史中实际存在的制式，另含“综合”。模式别名复用 `display_mode`。`session_key` 优先使用 `save_key`；其次 `session_key`；由 D 为实际导入提供内容身份。城市名只用地图/场景名称，缺失为“未提供城市名称”，不借用存档名。

`lines` 是所选公司 ID＋制式的全部真实线路；四亮点、Top10、客流分类、班次分类、总班次共用这个范围。Top10 无“其他”伪线路和补零行，至多 10 条；缺测线路不参加相应极值/客流排名；空范围四项 line 均为 None、排行/分类为空、总班次 None，线路数为真实计数 0。

## 字段来源和口径

| 固定 ID | 来源 / 计算 | 范围 |
|---|---|---|
| line-count | 过滤后线路快照数量 | 公司 ID＋制式 |
| fleet | 公司 `车辆总数`；制式筛选时取 `车队[mode]` | 公司 ID＋制式；完整车队，不用运行对象数 |
| drive-minutes | Σ线路 `行车总时间`，即全日计划班次×单程分钟 | 公司 ID＋制式 |
| turnover | 当日全日计划发班总数 / 完整车队 | 公司 ID＋制式 |
| weekly-income | Σ线路 `每周收入` | 公司 ID＋制式；既有线路周收入快照 |
| weekly-expense | Σ线路 `每周支出` | 公司 ID＋制式；既有线路周支出快照 |
| profit | 线路周收入－周支出 | 同上 |
| interval | 全部已启用、运行日已知日组内正值相邻班次间隔的均值 | 旧首页日组口径，排除“未启用”和“运行日未知” |
| speed | 所选线路正值 `核定速度` 的算术均值 | 公司 ID＋制式 |
| passengers-per-run | Σ线路今日客流 / Σ全日计划发班数 | 公司 ID＋制式 |
| passengers-per-km | Σ线路今日客流 / Σ（全日计划发班数×地图里程） | 公司 ID＋制式；尊重 `字段可用性` |
| public-transport-share | 有效全市 public-transport 原始计数 / 对应原始总体分母×100 | 模拟当日截至模拟时钟；忽略公司/制式筛选 |
| transfer-coefficient | 所选公司 transport-by-type 总计数 / trip-types 总计数 | 模拟当日截至模拟时钟；全部制式 |

原 11 项保留旧首页的可信字段和定义；不把公司历史现金流、城市出行量或者网络运行车辆替换为同名线路/车队指标。线路每周收入/支出在 `load_session` 中来自 `收入_累计`/`支出_累计`，缩放为 102400；不是公司车型财务汇总的 100 倍缩放字段。

**平均间隔范围差异**：旧首页把每条线路每个有效日组内的有效相邻间隔平铺后求均值，不按星期出现次数加权，不含跨午夜/首末班环回间隔。本包明确保留此定义并在 InfoValue.reason 中说明。新版线路页则以模拟当天运行日掩码选定实际班次，由 `prepare_schedule` 计算当日平均间隔；首页平均间隔因此不保证等于各线路页当日间隔的均值，不能混称同一窗口。三份总体缓存的旧首页间隔样本数依次为 16721、21286、26432。

线路“今日客流”是截至存档模拟时刻的线路累计快照；“当日发班数”仍是该模拟日完整计划班次，不能宣传为已实际发出的班次。存在未知运行日/不完整班次时，相关 InfoValue.complete 为 False，reason 说明“仅含已确认班次”。

新增指标和趋势均以模拟时钟构造当日窗口，绝不使用现实日期。趋势读取原始小时 HistoryData，当前小时区间截至模拟时钟，保留 Bucket 的 complete/partial_period。无小时观测为 None；综合趋势缺任一序列化制式类别、或合计时缺任一所选公司小时数据，则该点 None，不能显示部分和为总体。真实 0 小时仍显示 0。城市人口优先读取元数据明确值，缺少时回退模拟当日最后有效全市人口观测，缺源为 None；0 是有效明确值。

公共交通份额复用 `city_model.build_city_snapshot` 的同刻分类对齐和权重校验，不平均百分比，也不归一化三方式；正分子/零分母不能被其他小时的正分母掩盖。换乘复用 HistoryStore 的分子/分母观测配对，并复用 network_model 的原始计数合计。每个公司的当日分子/分母必须有匹配的有效小时；有公司缺整套输入则总体 None。各公司有效小时数量不同但各自分子/分母匹配时，保留各自全部有效计数再合计，不丢弃非共同小时。缺少制式对应分区出行量分母，所以换乘不跟随制式筛选，scope/reason 明示“所选公司、全部制式”。

## RED → GREEN 与实际验证

工作目录均为上述隔离工作区。解释器用已安装真实路径直接调用；`py -3.12` launcher 无注册不是测试失败，不安装 Python。运行工具使用已授权的 `sandbox_permissions=require_escalated`。纯模型命令全部带 `--noconftest`，避免全局 QApplication 夹具。

首次测试命令：

```powershell
& 'C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe' -X utf8 -m pytest --noconftest -q src/test_latest_info_model.py
```

实际首次 RED：退出 1，`18 failed in 0.40s`。每项失败为 `AssertionError: latest-info model is missing`，未写生产模块前先确认缺失接口导致断言失败，没有导入/环境错误混充需求失败。

最小实现后相同命令：退出 0，`18 passed in 0.10s`。

边界补测 `test_transfer_sums_each_company_valid_hours_without_discarding_unshared_hours`：实际 RED 退出 1，`1 failed, 20 passed in 0.26s`；错误值为 110/30，期望手算 210/50。根因是先按小时合并公司，使仅一家公司有配对观测的小时被总体摘要丢弃。修正为每公司先累计当日匹配计数再合计。同步增加真实零系数/缺整家公司输入、无效全市权重检查。

边界补测 `test_overall_trend_breaks_on_missing_serialized_mode_category`：实际 RED 退出 1，`1 failed, 21 passed in 0.26s`；错误点为 25，期望 None。根因是直接 HistoryStore 总计查询保留了缺类别小时的部分和。改为复用 `_quantity_trend` 先核对公司类别集合，再合计选中公司；单独选公交仍保留真实 25。

首次交付定向回归命令（后续同命令补测结果见末节）：

```powershell
& 'C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe' -X utf8 -m pytest --noconftest -q src/test_latest_info_model.py src/test_statistics_model.py src/test_network_model.py src/test_dashboard_model.py src/test_city_model.py
```

首次交付实际完整输出：

```text
........................................................................ [ 75%]
.......................                                                  [100%]
95 passed in 6.82s
```

退出码 0，无失败/警告。包含新增 22 项和相关既有 73 项。`git diff --check -- src/latest_info_model.py src/test_latest_info_model.py` 退出 0；这两个文件交付时为 untracked，未触碰索引。

## 真实缓存独立复算

只用 `load_session(Path(绝对缓存目录), tag)` 读取以下既有缓存：

1. `D:/test/CIM2_SaveStats/jobs/56dd6b5276cd4c5ba083815f8a30b515`，tag `秋山市n6 (2)_运行时`，模拟时间 `2013-05-21 23:59:13`。
2. `D:/test/CIM2_SaveStats/exports`，tag `望春市_test_运行时`，模拟时间 `2013-04-28 04:56:19`。
3. 同 exports，tag `quicksave.76561198362520556-76561198845688243_运行时`，模拟时间 `2013-04-10 23:59:22`。

独立 audit 用读取后的真实源字段重新手算 11 指标、线路极值、Top10、分类总数，另按原始 history 的指标/稳定公司 ID/模拟时间收集分子分母，比对实际模型。初次 17 范围全通过，最终代码再次复算，原指标及分类与首次独立算术一致；再以完整原始公司/制式类别集合逐小时验证趋势 332 点，全部通过。每份缓存所有对应 CSV 的 SHA-256 前后相同，最终证据 JSON 留存具体哈希。

| 缓存总体 | 线路 | 完整车队 | 全日计划班次 | 线路今日客流 | 当日历史换乘分子/分母 | 换乘系数 | 全市公共交通分子/分母 | 全市份额 |
|---|---:|---:|---:|---:|---|---:|---|---:|
| 秋山市 | 75 | 482 | 4457 | 509691 | 509691 / 178097 | 2.86187302425 | 178097 / 329309 | 54.0820323769% |
| 望春市 | 62 | 380 | 5468 | 13718 | 13718 / 7960 | 1.72336683417 | 7960 / 25969 | 30.6519311487% |
| 多人 quicksave | 73 | 605 | 6745 | 1376429 | 1376429 / 493442 | 2.78944435212 | 284091 / 911849 | 31.1554873669% |

多人子集：`76561198362520556` 完整车队 322，客流/分区出行 620296/228850，系数 2.71049158838；`76561198845688243` 完整车队 283，客流/分区出行 756133/264592，系数 2.85773190421。总体严格为 `(620296+756133)/(228850+264592)`，不是两个系数平均。任何公司或制式范围的全市份额相同。

班次分类总体：秋山市 公交3861、无轨电车359、水上巴士74、有轨电车163，和4457；望春市 有轨电车690、公交4778，和5468；多人 公交5317、有轨电车1428，和6745。每个范围分类和、真实线路和、总班次吻合，所有三份总体均保留完整10条Top10，极值/Top10完整键在 JSON。

人口分别为 147938、239163、292330；多人缺地图标签，城市名称准确显示“未提供城市名称”。三份新增历史指标都为 complete=False，因为模拟当日/当前小时尚未完成，不伪称完整全天。

最后缓存运行实际输出：

```text
PASS 秋山市n6 (2)_运行时 scopes 6 hour_points 144
PASS 望春市_test_运行时 scopes 4 hour_points 20
PASS quicksave.76561198362520556-76561198845688243_运行时 scopes 7 hour_points 168
ALL 17 SCOPES PASS; INPUT HASHES UNCHANGED
```

audit 通过标准输入运行只读 Python，进程退出 0，唯一持久输出为本报告目录下 JSON；模型哈希与最终本包源码相符。

## 限制和交接

- 本包不运行全量 pytest 或 Qt/native 验收：brief 明确禁止启动 Qt，且父会话统一安排相关窗口；完整集成与原生验收由 D/E 执行。本报告只声称以上 95 项纯模型回归通过。
- 模型接收既有规范化 dict。如果上游早已把缺失源转成数值 0 或用现实时间填补缺失模拟时间，本包无法仅凭规范化值还原来源是否存在；规范化输入本身缺失/None/非数值时保留缺测。当前三份真实缓存均有真实模拟元数据及人口，实际复算未遇到此来源歧义。未修改只读授权之外的 load_session。
- 为保持共享审计口径，调用 network_model 的 `_aggregate_result`/`_quantity_trend` 与 city_model 的 `_comparisons=False` 参数；共享模型没有被改写。父会话若后续调整这些帮助函数，应同时运行本包回归。
- 当前报告为作者逐行自审结果，未另派代理/聊天，遵守明确禁止再委派的边界。父会话后续独立审查及集成验收仍需进行。
- 无本包剩余工程阻碍。D 应在导入时提供稳定 `save_key`，在后台计算快照并检查导入身份/范围身份以拒收过期结果；A 快照为纯数据，不负责 UI 接线、异步队列及提醒算法。

## 父审查修复：真实存档文件名（2026-10-01）

父会话指出真实 `MainWindow.on_completed` 输入提供 `save_path`，初版只读 `save_name` 或 `tag`，导致当前存档误显示导出缓存 tag（如“秋山市n6 (2)_运行时”）而非实际“秋山市n6 (2).save”。确认初版存在该缺口后，本包新增五个测试实例，并把原无实际文件来源 fixture 的期望修正为准确缺名称。

新增实例检查：Unicode Windows 路径 `D:/存档/秋山市n6 (2).save` 和反斜杠等价路径、真实路径优先于旧 `save_name`、无路径时明确 `save_name` 可用、只有 tag 时不伪装为文件名。

RED 命令为上述解释器加 `-X utf8 -m pytest --noconftest -q src/test_latest_info_model.py`，实际退出 1：`5 failed, 22 passed in 0.57s`。两种路径返回“秋山市n6 (2)_运行时”，路径优先测试返回“旧存档.save”，两个准确缺名称测试错误返回 tag；全部失败符合本次修复目标。明确名称回退测试在初版已通过，确认兼容既有行为。

最小修复：`LatestInfoSnapshot.save_name` 先取 `PureWindowsPath(data['save_path']).name`（兼容 Unicode 及两种 Windows 分隔符），路径缺失时取明确 `save_name`，二者缺失则为“未提供存档名称”。`tag` 保持导出缓存身份用途，不再用于实际存档文件名；其他计算和合同类型不变。

GREEN 使用首次交付同一五文件定向回归命令，实际退出 0：

```text
........................................................................ [ 72%]
............................                                             [100%]
100 passed in 7.75s
```

包含本包 27 项和既有相关 73 项，无失败/警告。随后再次只读加载三份缓存，全部 17 范围的 13 指标、总班次、Top10、四极值和输入哈希保持不变；纯 `load_session` 缓存没有实际 `save_path`，因此明确显示“未提供存档名称”，不借 tag 推断源文件。真实导入路径语义由新增实际路径 fixture 验证，未伪造真实缓存的来源路径。

audit 退出 0，输出三个 `PASS ... scopes 6/4/7 unchanged metrics/counts/rankings` 和 `PASS all 17 scopes; final source hashes recorded`。JSON 的 `post_save_name_fix_validation` 记录本次复验，`source_sha256` 更新为修复后模型/测试，原审计源码哈希保留在 `pre_save_name_fix_source_sha256`。未新增权限范围之外的文件，未启动 Qt、未 stage/commit。

## 标签一致性补记（2026-10-01）

按父会话要求，最后一项 InfoValue.title 直接复用 `statistics_model.METRICS['transfer-coefficient'].label`，显示“平均换乘系数”，与共享指标和另外页面一致。key、计算和单位未改。此项仅为共享名称引用，按父要求未增加标签镜像测试、未重复运行此前通过的 100 项回归；E 后续独立核查。JSON 保留已复算的模型版本哈希，并另记录本次仅标签调整后的当前源码哈希。

## E-A-01 定向修复（2026-10-01，等待 E 复验）

已读取独立 `task-E-report.md` 的 A 风险章节、`task-E-A-risk-review.py` 和 JSON。确认初版日级 transfer query 的缺陷：虽然两侧小时集合匹配，01 时缺有轨类别的部分客流 100 仍被并入完整出行分母 30，导致 `(120+100)/(30+30)=220/60`。仅 complete=False 不足以解决分子/分母有效范围不同。这一发现成立，本节修复替代此前“日级查询配对后合并”的实现说明。

先新增四项纯模型风险测试：

- `test_transfer_excludes_hour_with_missing_serialized_mode_category`：a@00 公交100＋有轨20／分区出行30；a@01 仅公交100／分区出行30。预期 4、complete=False、reason 明示类别完整与排除；趋势仍 `[120, None, None]`。
- `test_transfer_keeps_company_specific_complete_paired_hours`：上述 a 之外，b@01 完整公交80／出行20；预期 `(120+80)/(30+20)=4`，仍不要求公司有效小时交集。
- `test_transfer_returns_missing_when_no_complete_mode_hour_can_be_paired`：没有任何类别完整且安全配对小时，预期 None。
- `test_transfer_excludes_hour_with_missing_serialized_journey_category`：分区出行分类缺测时，同样排除该小时，不能把完整客流除以部分分区计数。

RED 精确命令：

```powershell
& 'C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe' -X utf8 -B -m pytest --noconftest -p no:cacheprovider -q src/test_latest_info_model.py
```

实际退出码 1，`3 failed, 28 passed in 0.30s`。三项错误值依次为 220/60、300/80 和 220/50，均应为 4；第四项无安全配对输入在原实现已有 None，作为保留边界。完整输出与 `actual_exitcode=1` 保存为同目录 `task-A-EA01-red.log`。

最小实现只改 `src/latest_info_model.py`：新 `_transfer_value` 仍调用共享 HistoryStore 的小时 transfer 查询，逐公司读取已序列化的 `transport-by-type` 与 `trip-types` 类别集合，再对每小时每个实际观测时刻检查两侧类别均完整且时间配对、分母为正。只累计安全小时的原始分子/分母；不同公司分别累计各自有效配对小时，然后计算总体计数比，不平均系数，也不限制为公司共同小时。缺类别/未配对/无有效分母的观测小时排除；有选定公司完全没有安全配对小时时保持总体 None。缺任何小时或当前小时部分观测时 complete=False。

reason 现在明确“仅累计各公司全部已序列化制式及分区出行类别完整、分子/分母配对的有效小时”，列出各公司有效小时数与被排除的观测小时数。E 原例返回 4，a 有效配对1小时，排除1个缺类别观测小时。此前 110/30 总体和 210/50 不同有效小时回归仍通过；制式筛选仍不进入换乘范围。未改 statistics_model/network_model/city_model 或其他包文件。

GREEN 精确命令：

```powershell
& 'C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe' -X utf8 -B -m pytest --noconftest -p no:cacheprovider -q src/test_latest_info_model.py src/test_statistics_model.py src/test_network_model.py src/test_dashboard_model.py src/test_city_model.py
```

实际退出码 0，完整输出：

```text
........................................................................ [ 69%]
................................                                         [100%]
104 passed in 6.53s
```

包含 A 31 项＋既有相关 73 项，无失败/警告；完整日志 `task-A-EA01-green.log` 含 `actual_exitcode=0`。本轮仍没有 Qt、MainWindow 或全量测试。

修复后再次 `load_session` 只读加载原 A 的三份缓存，核对全部 17 范围的 13 指标、总班次、Top10、四极值，全部与此前独立复算数值一致；输入 CSV 哈希前后一致。真实缓存均有完整类别配对观测，本次修复未改变这些已有有效值。审计 JSON 新增 `post_EA01_validation`，保存每个范围的当前系数/complete/配对 reason；`post_EA01_source_sha256` 记录本轮源码，历史审计哈希未覆盖。

实际缓存输出（进程退出 0）：

```text
PASS 秋山市n6 (2)_运行时 scopes 6 category-safe transfer and all numeric metrics/rankings/counts unchanged; cache hashes unchanged
PASS 望春市_test_运行时 scopes 4 category-safe transfer and all numeric metrics/rankings/counts unchanged; cache hashes unchanged
PASS quicksave.76561198362520556-76561198845688243_运行时 scopes 7 category-safe transfer and all numeric metrics/rankings/counts unchanged; cache hashes unchanged
PASS all 17 scopes after E-A-01; source hashes recorded
```

当前模型 SHA-256 `b3f9f3aab68463a605dfbef5395411a75192996bc973aec1e450d483c59cd0aa`；测试 SHA-256 `18bbbbb0c6a468e89b30ebc2c316981fad53129165502b978f259f259157dbb9`。`git diff --check` 退出 0；两个本包源文件保持未暂存。未运行 E 脚本 main（它会写 E 所有的 JSON），未覆盖独立证据；E 的复验尚待父会话安排，不以作者测试宣称 E 已关闭该发现。

## 城市来源与逐公司趋势修订交付（2026-10-02）

本节为当前 A 状态，替代上文与旧城市来源或旧授权范围有关的限制。已读取 `docs/ui-redesign/LATEST-INFO-REVISION-2026-10-01.md` 与 `docs/ui-redesign/astra-visual-audit-2026-10-01/ASTRA-AUDIT.md`。所有修改仍在指定 worktree；没有写主工程、重解析存档、启动 Qt/MainWindow/后端、写 cache/save/probe、stage/commit 或另派代理/聊天。

### 当前交付及有限文件变更

- 新 `src/map_name_source.py`：纯 Python 的有界存档元数据头解析、城市标准化、来源保留、可靠 metadata 后备和即时显示入口。新 `src/test_map_name_source.py` 验证格式、边界、原始值、加载器及隔离 extractor 元数据段。
- `src/latest_info_model.py`/测试：城市来源统一解析；快照追加默认 trace 字段及最后一个默认 `company_trend: Result | None=None`，保持旧构造兼容、13项指标及原聚合趋势。
- `src/extract_runtime_data.py`：仅地图 metadata 块，11行新增/10行删除；删除 `SAVE.stem.split('_')[0]` 及场景文件名回退，输出原始引用与明确来源。
- 父追加授权 `frontend/report_model.py`：仅最终 metadata 映射新增五行直接透传，无其他 hunk；保留原地图名称键兼容，不给旧缓存补造来源。字段为“地图原始引用/地图原始名称/地图内部标识/地图名称来源/地图名称说明”。父最终候选须单列该共享文件窄 diff 审核。
- 公开接口和 B/D 接线说明：`task-A-map-interface.md`。B.set_session 调用 `display_session_city_name(data)`，与快照城市同源；B 普通折线消费 `company_trend.series`，公司真实 ID 从 `snapshot.companies` 取名称。不写死公司数。

### 文件头证据及可信来源规则

对原游戏 `Assembly-CSharp.dll` 用 dnfile/dncil 做只读 IL 检查，没有加载 CLR 或运行游戏/解析 backend；证据 `task-A-map-header-il.txt`。核验真实格式为 `FD` 单字节标记后紧随 UInt32 大端版本2013120900，然后根对象/共享类型声明 `GameState+SerializableMetaData`。按字段顺序读取 UInt32 simulationFrame、六个 Int64 ticks、UInt24/FF 玩家数组及对象/共享类型引用，再读取 unique UTF-16BE 原地图字符串和 environment。长度按 UTF-16 code unit，支持代理对；玩家声明数量影响地图起始偏移，因此不写死153位置。对象定义是排队声明，无 PlayerData 内联反序列化。

只读取一次最多16KiB文件头；字符串最多2048 code units，玩家声明最多32。根类型、版本、对象/共享类型引用、长度/编码或后继 environment 不合法即 unknown，不扫描匹配城市文本，不解压 payload，不解析完整 save。只支持已核验 schema；完整 payload 有效性不属于此读取器的验证范围。

优先真实 save_path 文件头，之后仅信任来源精确标为 save-header:m_originalMapName 或已知 runtime 原地图字段的 metadata。没有来源标记的旧“地图名称”，即使看似正常城市文本，也不能区分旧 extractor 的文件名回退，因此返回“未提供城市名称”；不根据 tag 或文件名猜测。

完整保留 raw_reference/raw_map_name/internal_id/source。Workshop 引用去掉结构性 `:ID:` 前缀；Eixeia1.1、Reeve Delta Map、Budapest地区版本、Szczecin别名地区的剥离限四个已核验ID与原名组合。一般数字如 District 9、Route 66、City 2、Sector 1.1 保留；一般版本只剥显式 v/version 后缀。明确 ASCII snake/kebab 内部标识通用可读化，如 north_city→North City、river_delta_2→River Delta 2，并保留原标识。

### 逐公司趋势口径

综合查询经 `_quantity_trend` 对每公司已序列化制式类别完整性校验后，以 `(真实公司ID,'总计')` 提供各公司序列；具体制式以 `(真实公司ID,中文制式名)` 提供原 query 序列。每公司缺小时/类别保留 None，其他公司缺测不会抹掉本公司有效点，末端限定到模拟时间。单公司、多公司按实际筛选 ID 保留，不平均、不补零。原 `trend` 再经既有 `_aggregate_result` 聚合，仍保留原公司共同范围缺口。指标和 Top10/极值/模式汇总计算未被城市或逐公司字段修改。

### RED/GREEN 与实际缓存证据

同一 Python312 解释器，所有 pytest 加 `-X utf8 -B -m pytest --noconftest -p no:cacheprovider`，不加载全项目 conftest/Qt：

| 阶段 | 实际结果 | 证据日志 |
|---|---|---|
| 新地图模块尚未实现 | 32 failed，exit1 | task-A-map-red.log（初次工具正文被截断，保留实际返回输出及汇总，不声称完整堆栈） |
| 初版地图模块 | 32 passed，exit0 | task-A-map-green.log |
| 快照接线尚未实现 | 4 failed,31 passed，exit1 | task-A-map-model-red.log |
| extractor 元数据段旧回退 | 2 failed,32 deselected，exit1 | task-A-map-extractor-red.log |
| 第一轮相关回归 | 142 passed，exit0 | task-A-map-integrated-green.log |
| 通用内部标识/逐公司字段尚未实现 | 10 failed,69 passed，exit1 | task-A-company-map-extra-red.log |
| 地图+逐公司相关七文件 | 167 passed in 8.65s，exit0 | task-A-map-company-green.log |
| 加载器原始字段尚未透传 | 1 failed,41 deselected，KeyError地图原始引用，exit1 | task-A-map-loader-red.log |
| 最后加载器接线定向两文件 | 80 passed in 0.33s，exit0 | task-A-map-loader-green.log |

167项命令文件为 `src/test_map_name_source.py src/test_latest_info_model.py src/test_statistics_model.py src/test_network_model.py src/test_dashboard_model.py src/test_city_model.py src/test_latest_info_exports.py`。最后新增加载回归后按父要求不重复全套；80项命令为 `src/test_map_name_source.py src/test_latest_info_model.py`。隔离 extractor 测试用 AST 仅执行授权元数据块，不导入/运行完整 extractor，不能视作后端端到端验收。

49份真实存档（44游戏 Saves＋5项目data）的16KiB头均识别为已核验版本、已知名称，输入头哈希/大小/mtime_ns前后不变；证据 `task-A-map-real-headers.json` 保留该次源码哈希，不用后来文档缩进更改覆盖历史版本。注意游戏 quicksave.save 是 Eixeia；项目双人 quicksave.76561198362520556-76561198845688243.save 是 Szczecin，不能以 quicksave 文件名合并判断。

随后只读原秋山、望春6、双人三份 manifest 对应实际存档和已有缓存：秋山实际 analysis 路径为 Eixeia，望春6为Ljubljana，双人为Szczecin。`task-A-map-company-real-audit.py` 独立调用 load_session 并注入 manifest 的实际 save_path（仅内存），比较纯即时显示与模型城市/原始引用，逐范围对 E 原独立JSON的13指标数值和聚合点，并逐公司逐小时用原始 transport-by-type 行与完整类别直接相加复算。结果保存 A 所有的 `task-A-map-company-real-audit.json`，未运行 E main 或覆盖 E 文件。

```text
PASS autumn Eixeia scopes 10 company points 240
PASS spring Ljubljana scopes 6 company points 144
PASS multi Szczecin scopes 9 company points 288
PASS all existing metric values and aggregate points unchanged; company points independently verified
```

实际退出0，共25范围、325指标值、600原聚合点与既有独立证据一致，672新逐公司点与原历史计数相符。每份 cache 所有 CSV 全文件SHA-256前后不变；每份 save 仅声明16KiB头SHA-256、size、mtime_ns不变，未声称完整save哈希。`git diff --check` 退出0。

当前六文件精确哈希在新真实审计JSON `source_sha256`：地图模块 d18afae65c270720ff4219ceb69921b8d1d40f557667818f7aa8e3bb3378db38；模型 e2c3abf1f5972c19a31025f39fdc822e4b9c39eac765c2f28b6b11cbdce0c8f6；extractor 51388ec97cb68f43b2f701280b54484aba7251874dce8cdf77c103d254ffc506；report_model 0570cbf6831f4d82bbaee6f9613b8f5d066e7ee7af7babc8f56942f33b4d7b79。A 工程交付完成；页面折线、布局和原生验收由 B/D/E 与父接续，本节不声称 UI 已验收。
