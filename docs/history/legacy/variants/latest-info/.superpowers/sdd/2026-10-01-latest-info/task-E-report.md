# 包 E 预备与独立审查报告 — 2026-10-01

工作区固定 `D:/test/CIM2_SaveStats/.worktrees/latest-info`。状态：**预备产物已生成，产品最终验收未执行**；Qt/native/鼠标/全量 pytest 继续 hold。E 产品源只读，无另派任务、聊天轮询、跨聊天消息、stage 或 commit。

最新复验状态：**E-D-01、E-A-01 两项 P2 均已独立定向复验关闭**。D最新15纯测试、A最新31纯测试通过；A独立10组风险及真实25范围/600小时点通过。各段原失败发现保留历史，最新闭环见文末；GUI/native/实际125%/整库仍未验。

## 预备产物

- `docs/ui-redesign/qa_latest_info.py`：默认 inventory 仅标准库读取三套缓存；记录列/行数/哈希、身份、模拟时钟、确认当日班次与制式、Top10 原始记录、历史比例分子/分母和逐分组小时覆盖。显式 model/alerts 入口延迟导入纯模型，不导入 Qt；当前原生适配留待 D 接线完成后继续。
- `docs/ui-redesign/LATEST-INFO-ACCEPTANCE-2026-10-01.md`：13 来源/单位/范围表、组件/集成检查清单、风险输入矩阵、原生排期和证据格式。所有未执行项清楚标为待验。
- `.superpowers/sdd/2026-10-01-latest-info/task-E-cache-audit.json`：三套真实既有缓存，只读审查完整数据；非 fixture，非重新解析。
- `docs/ui-redesign/latest-info-evidence/README.md`：原生证据预留说明，当前无截图。

## 已执行准备检查

使用 Codex 已提供的 Python 3.12.14（无安装）：

```powershell
& 'C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B docs/ui-redesign/qa_latest_info.py
```

实际 exit 0，输出 `cache-inventory-only` / 3 cases / `protected_changed: []` / `product_acceptance: NOT RUN`。25 个保护文件（manifest、CSV、原存档和现有 probe）前后 SHA256 一致。此准备检查不运行新首页模型；后续新增授权的 A/C/D 纯审查见下文。Qt/native 和全量测试一直未运行。初次尝试 `py -3.12` 返回 `No installed Python found!`，这是启动器环境限制，不是产品失败；已用现有 bundled runtime 完成只读审查。最终 inventory 再验 exit0，`task-E-inventory.log` 保存实际退出码。

inventory 记录 HEAD `7057b9dbe14125794df7d0809ded12c76f5fa010`；产品源并行实施，最终验收时重新冻结并记录哈希，不能用当前 HEAD 代替未提交代码版本。

## 真实缓存审查发现与风险

1. 秋山市主缓存 75 条 / 完整车队 482 / 确认当日班次 4457，4 实际制式；望春市 59 / 376 / 5936，2 制式；多人 73 / 605 / 6745，2 制式。全部记录数与当日班次不同，不能读 manifest departure_count 冒充当日总数；原配车对象数也不能替代车队总数。
2. 总体系数按原历史整数：秋山市 `509691/178097=2.861873024251`；望春 `1045770/273631=3.821825743428`；多人 `1376429/493442=2.789444352122`。多人两个子集 `620296/228850`、`756133/264592`；严禁平均两个公司系数。
3. 全市分担率按公共交通 raw 值/分母：秋山市 `178097/329309×100=54.082032376886%`；望春 `273631/649078×100=42.156874828603%`；多人 `284091/911849×100=31.155487366878%`。不随公司和制式改变。
4. 三缓存当日有 24 小时观测但最后当前槽位是部分小时，不能称完整日。审查四类指标在昨日/前日均有逐组 24 小时；不能外推所有提醒指标均 complete。望春与多人四类指标各排除 6 条未来观测。
5. 三缓存本轮没有未知运行日；未启用班次 1047/256/307 均须排除。缺测、零分母、未知运行日和缺小时须另用明示风险输入，不能声称缓存已覆盖。
6. 真实公司没有同名，真实制式最多 4 类；同名稳定 ID 和 6 制式完整列表需要 fixture 辅助，fixture 不作为真实存档证据。
7. 原 `desktop_app.refresh_company` 平均间隔汇总多个有效运行日组；新版线路页按模拟当日、tick 精度及运营日规则。A 必须明确保留/迁移口径及差异，不能悄悄改为另一窗口。
8. 多人元数据地图名称本身为 quicksave 字样。已读 `extract_runtime_data.py:883/901`，其来源是 `m_mapName/m_scenarioName/m_cityName`，不是脚本 save.stem 回退；UI应展示真实 metadata，而不是凭文件名形状擅自推断。缺失来源仍须准确回退“未提供城市名称”。
9. 望春/多人旧历史 CSV 不含公司标识，需经 load_session 按独一原名称映射稳定玩家 ID。原缓存两名不重复可映射；同名无ID历史必须保留无法确定的身份，不得任意合并。

## 后续边界

父后续更新已同步：Hero 必须在主区上方全宽，4 核心（线路、车辆、收入、利润）与 9 辅助分层；三图同排预算须保留完整 Top10/制式，不能按旧右栏 Hero/7+6 等权设计验收。B→C 可串行运行严格 isolated offscreen 组件测试，**E 仍不启动 Qt**；离屏组件结果不能替代原生/真实125%验收。

A/B/C/D 最终差异/报告逐包读后继续审查。父明确释放 Qt/native 才可原生 1440×960、实际125%、920×680及完整行为验收，保存 frame/client/DPR/源码与缓存哈希/实际退出码。当前无原生结果、无截图、无整库通过结论。

## C 包纯提醒模型审查（新增授权，准备结束后执行）

审查只限 `src/latest_info_alerts.py` 与纯测试；C UI 不在本轮范围，不据此报 UI 缺陷。结论：本次限定范围内未发现纯模型规格/质量缺陷，不能外推为 GUI、已读持久化、异步或全项目通过。

### 实际测试和缓存对照

指定纯测试命令（现有 Python 的执行权限需要授权 escalation，实际获准执行）：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe' -X utf8 -B -m pytest --noconftest -p no:cacheprovider src/test_latest_info_alerts.py -k 'not gui' -q
```

实际结果 **23 passed, 7 deselected in 0.11s，exit 0**。禁用全局 conftest、pytest 插件自动加载、缓存和字节码，GUI 函数完全 deselect；没有 QApplication、鼠标或全量测试。完整日志 `task-E-C-pure-tests.log` 含 `actual_exitcode=0`。

E 另用 `qa_latest_info.py --phase alerts --output .superpowers/sdd/2026-10-01-latest-info/task-E-C-cache-review.json` 从三套真实缓存 load_session / HistoryStore 生成原规则对照。actual exit 0；`qt_modules_imported=[]`，保护文件 SHA256 无变化。`task-E-C-cache-review.log` 保存实际退出码，JSON 保存全部真实提醒（原值、窗口、reason、稳定 ID）及结果。

| 缓存 / 范围 | 默认 (5,20,100) 实际提醒数 | (7,30,250) 实际提醒数 |
|---|---:|---:|
| 秋山市全部公司 | 4 | 3 |
| 秋山市空公司选择（仅城市） | 2 | 1 |
| 望春全部公司 | 3 | 2 |
| 望春空公司选择（仅城市） | 2 | 1 |
| 多人全部公司 | 19 | 9 |
| 多人 ID 76561198362520556 | 11 | 7 |
| 多人 ID 76561198845688243 | 11 | 3 |
| 多人空公司选择（仅城市） | 3 | 1 |

两套阈值、全部/单公司/空公司范围逐一比较完整 DashboardResult 与直接 `build_dashboard`，全部相等；所有真实提醒只来自 confirmed 指标、两期 complete 且非 None 数据桶；无 transfer-coefficient 提醒、无选外公司提醒，立即取消均传播 QueryCancelled。默认窗口独立检查为模拟昨日00:00至今日00:00，对比前日00:00至昨日00:00，hour 粒度。

### 逐项审查与接线条件

- 日窗口：`src/latest_info_alerts.py:8` 使用 parse_time 和午夜归一，跨年/闰日测试覆盖；不读现实时间。真实缓存窗口与独立计算一致。
- 公司 ID：输入 tuple 原样进入 FilterState；同名公司 p1/p2 风险测试分别产出身份准确提醒。全部公司必须由 D 传所有稳定 ID，`()` 沿原 dashboard 表示无公司，城市指标独立。这是已文档化原语义，不判为 C 缺陷。
- 不可比抑制：直接复用 build_dashboard→alerts_for_result；不等长、无比较、缺小时、未确认能源指标、零分母、换乘系数、无历史以及阈值边界都有指定纯测试；真实缓存对照验证未新增规则/门槛/严重性。
- 原规则复用：`src/latest_info_alerts.py:21` 只包装原 build_dashboard，thresholds/cancelled 原样传递，无复制算法。输出完整原 DashboardResult；城市三方式源提醒未重复。
- 测试质量：纯测试延迟新模型 import，GUI import 全部在 fixture/GUI执行内部；本轮 `-k 'not gui'` 完全避开 GUI。未把 C 初始22测试或其自述当本轮证据，以 E 实测23项为准。
- 待 D 验证：新请求 token/会话范围过滤过期 worker、set_session 即时清理、无需访问统计页的自动查询、阈值重算、全部公司ID、关闭提醒停止主动查询；C 包纯函数无法负责过期结果送达 UI 的判定。
- 待 C GUI 验证：stats_alerts._alert_id 的直接复用/旧阈值键/持久化/全部列表/详情/焦点，当前不作结论。多人缓存实际19条，足够真实检验“摘要最多5条、全部保留19、真实未读数”容量，无需制造填充提醒。

审查 C 模型 SHA256 `cf4e4d8ab7fbbe3fb9ff64e8f37f1511935fa8a4c639f2e724268100865d8219`；原 dashboard `4d6d18a90a03c412ba69e1eb4ba5a7bb7ab4ffd058b89c12544136263f22a793`；原 statistics_model `14e80c9913e6a0f481ffe91079c4fadd38129a91dcbb467aad1a2eecaa9f5b68`。具体运行源码哈希以 JSON 为准，C GUI 后续变动不沿用本结论。

## D 包纯导出审查（新增授权）

D 报告与其 `task-D-verify-cache.py` 已核实：其缓存 smoke 消费实际 A.build_latest_info dataclass + C 提醒，不是手工投影；这构成已有数据→导出链证据，但不是 GUI 集成通过。E 另以三套既有真实缓存独立生成/回读，验证真实 A→C→D 链。

指定 `src/test_latest_info_exports.py` 以同一现有 Python / `--noconftest -p no:cacheprovider` / 禁用插件自动加载执行：**12 passed in 2.07s，exit 0**，日志 `task-E-D-pure-tests.log`。

E 纯导出探针 `task-E-D-review.py` 显式阻断 Qt 导入，实际三缓存及长 Unicode/换行/前导=和@名称输入的回读均无差异：13指标数值/缺测/单位/范围/reason/完整性、Top10完整行、全部班次分类与占比、两期提醒原值/窗口/reason；没有公式或 Excel 错误。额外复制的特殊文本输入明确标为风险输入，不作为另一份真实存档。`task-E-D-review.json` 保存源码SHA256和工作簿，`qt_modules=[]`，运行中被审源哈希无变化。

**实际发现 E-D-01 / P2 / 待 D 修复**：`frontend/latest_info_exports.py:102` 将 `alerts.filters.companies=()` 的提醒公司范围写成“全部公司”。原 dashboard 和 C 已冻结空 tuple=无公司选择，仍可生成全市提醒。这会把只查询全市提醒的报告错误标为查询全部公司。复现：实际多人快照，提醒 filters 公司空 tuple、仅真实 city 提醒，导出 XLSX，“范围与说明”提醒公司值为“全部公司”；预期“无公司选择（仅全市指标）”或等义准确标签。证据 `task-E-D-empty-company-scope.xlsx`，独立探针 actual exit **1**（因为确认该发现，其他4组回读0差异），完整 `task-E-D-review.log`。最初探针JSON记录定位105，随后逐行核实实际语句为102，修复定位以本报告102为准。

D 原测试没有空公司选择导出标签断言，故12项通过未覆盖此错标。E 产品源不改、不跨聊天消息，由父读报告交 D 修复。现阶段不判定“旧快照导出”是否已解决：应在 D 保存对话框返回后检验 token/session 的集成实现中核验，纯 exporter 的冻结接口只接收传入快照，没有当前会话判据。

## A 包独立数据审查（新增授权）

已读 A 产品源、纯测试、最终报告及被复用 shared helper 的具体实现。作者原报告95项不是 E 的通过证据；E 指定纯模型实测 **27 passed in 0.09s，exit0**（含后增5项存档名称边界），日志 `task-E-A-pure-tests.log`。无 Qt/conftest/全库测试。

真实 Unicode Windows 路径修复已存在且通过：`PureWindowsPath(save_path).name` 优先于显式旧显示名；正反斜杠均取 `秋山市n6 (2).save`；无源路径时保留明确 save_name，只有 export tag 时不冒充真实存档名称。snapshot 的 session_key 仍由 D 传入内容身份，不能把文件显示名用作会话身份。

E 实际三缓存25范围（秋山市10、望春6、多人9，含全部/稳定ID子集、综合/实际制式）独立算术：原10项非间隔指标、全市分担率、总量换乘、同一线路集合、Top10值/行数、完整班次/客流分类和总班次均吻合；全市份额在筛选间不变，保护文件前后哈希一致。JSON `task-E-A-cache-review.json` 保存实际13指标、筛选与失败列表，`qt_modules_imported=[]`。原11项中平均间隔另用原 desktop_app 的日组相邻差算法比对这25范围，也全部一致：总体样本数 16721 / 22172 / 26432，均值 17.160157885294 / 15.104636478441 / 15.585275423729 分钟。

E 选用的望春真实缓存是 `jobs/68efa...` / 2013-04-18，与 A 自审使用 exports 望春市_test / 2013-04-28 不同；因此线路59 vs62、车队376 vs380与作者报告不同是**来源差异**，不是产品算错。E 三缓存范围及标签保持可复读，不混用两份望春证据。

### 公共接口与 helper 语义

- 五个公开 dataclass 均 frozen、字段/顺序匹配契约；数值 Decimal/None，未含 Qt 对象或颜色。E 额外验证快照 frozen、13固定ID、明确人口0、Unicode basename、同名且无ID历史不任意关联、查询中途取消与输入不变，均符合预期。
- `_quantity_trend` 的类别合计要求每个已序列化类别在该小时有值；`_aggregate_result` 的 flow 合计要求每个选定公司该小时有值，已核对源码与既有缺类别/缺公司小时用例。这项复用保持原语义，不机械要求复制公开/私有算法。
- City helper 按同刻完整已序列化城市类别取分担率，并验证正分子零权重无效；metadata人口优先、历史回退为最后有效城市值，0保留。公司和制式未进入 city 过滤。
- 每公司先日累计配对客流/分区出行后再合并，使不同公司有效小时数不同但各自配对时不丢真实计数；这修复路径已核对。但是日级配对只检查小时集合相同，没有充分检查该小时分制式类别完整性，见下列新发现。

### 实际发现 E-A-01 / P2 / 待 A 修复

位置 `src/latest_info_model.py:278`（日级 transfer query→aggregate；原共享 HistoryStore 内配对按时间集合）。明确风险输入不是存档：公司a，00时公交100+有轨20、分区出行30；01时仅公交100，有轨类别缺测、分区出行30。趋势正确为 `[120, None, None]`，但换乘仍为 `(100+20+100)/(30+30) = 3.666666666667`，complete=False。

缺类别小时的分子是部分制式客流，分母却是同小时完整总分区出行量；仅标“部分观测”不能把不同有效范围变成配对的总量比。预期保持不可计算 None，或只使用完整类别且配对的00时计数 `120/30=4` 并明确有效观测范围；不能把01时部分分子与完整分母并入。需要同时保留“公司有效小时不同但各自完整配对时保留全部计数”的已修复行为。

E `task-E-A-risk-review.py` 独立复现：6组覆盖通过，上述一组失败，实际 exit **1**；`task-E-A-risk-review.json` / `.log` 保留输入、结果、趋势、源码SHA256与无Qt证据。没有修改 A 或 shared helper。作者现有27项没有把“缺序列化类别”与系数一起断言，已有缺类别用例仅验证趋势，因而不会发现此问题。

风险审查源码 SHA256 `2438b25ffaef67ab06dc381788345a96c81946b76bfed5dbb0b5c64e099ab3bf`，纯模型测试 SHA256 `84159dbd070736cb4474983c669f6647a99c56820aa20954cfcadbe6aaf99799`。native/GUI/实际125%未验；A新缺陷和D范围错标待父协调修复后定向复验。

补充真实趋势独立核验：25范围 **600 个小时点** 按原 HistoryData 的稳定公司ID、序列化类别集合与制式独立求和；缺公司/类别观测则该点 None，排除未来小时。`task-E-A-cache-review.json` 每点留存 expected/actual/start/end，600点0差异；最终 model phase actual exit0，无Qt导入、保护哈希无变化。此结果不消除独立类别缺测输入上的 E-A-01。

## 本轮收敛状态

预备工作与 C/A/D 已授权纯审查已完成；最终产品验收尚未完成。待父协调 **E-D-01、E-A-01 两项 P2** 后定向复验，再按明确排期继续 B/C组件与D集成、原生/真实缩放/全量测试。当前未运行 MainWindow、QApplication、鼠标、GUI、全库测试，不声明未实施功能通过。

## E-D-01 定向复验 — 已关闭

父明确通知 D 修复已交付后，只读最新 exporter/测试。修复仅使空 `alerts.filters.companies` 标签为“无公司选择（仅全市指标）”，非空仍按所选稳定ID逐个写入。D新增3个参数化用例，分别空选择、单ID、多个同名公司ID。

E 最新指定纯测试实际 **15 passed in 2.11s，exit0**，完整 `task-E-D-retest-pure.log`；没有重跑整库。E 原探针新增 `--scope-only` 重放路径，使用此前已核对真实多人缓存生成的 `task-E-D-real-multi.xlsx` 作为冻结数据来源，避免导入当时正在修改的 A。此为真实工作簿记录的投影重放，**不是新解析、不是新A→D当前链验收**；原失败JSON/log/XLSX保留未覆盖。

实际空/单/多范围各生成新XLSX并回读：空选择提醒标签正确，3条真实城市提醒；单ID显示“八连交通集团 [76561198845688243]”，11条记录；多ID显示两家公司及稳定ID，19条记录。首页公司范围仍是“全部公司”，不与提醒选择混淆。13指标、全部分类、Top10、两期原值/窗口/reason回读全部0差异。`task-E-D-retest.json` 保存全部来源和三工作簿SHA256，`qt_modules=[]`、`active_A_imported=false`、被审源与原工作簿前后hash一致，探针 actual exit0 (`task-E-D-retest.log`)。

修复版 D SHA256 `fbb113069285b5889be16c620641cc2b9e827cd3b05204626d182ef63e807a15`；最新D测试 `acab2a5b76b6ea0ba9ec79c50cb1159f3740f4caecf4ac634b620c82d57a24c3`；冻结来源工作簿 `3891d39e9cf7beb470ffa4f10717b0da4ce65fc52c4f3e835a1adde10abe7f7d`。**E-D-01 定向复验通过并关闭**；GUI保存对话框和旧快照保护仍待D集成验收。

A已由父通知稳定，将接续E-A-01独立复验；此段D结论不沿用/判断A活动源。

## E-A-01 定向复验 — 已关闭

父明确通知 A 源码/测试稳定并提供最终报告后，E只读核查 `_transfer_value`：复用共享 HistoryStore 的小时查询，逐公司核对已序列化客流制式和分区出行类别在每个观测时刻均完整，且两侧时间配对、分母正；分别累计各公司安全小时的原始分子/分母再取总量比。没有把多个公司的有效小时取交集，也未平均系数；没有安全小时的选定公司仍使总体缺测。reason 明示有效及排除的观测小时。

E 最新指定 A 纯测试：**31 passed in 0.12s，actual exit0**，日志 `task-E-A-retest-pure.log`；未重跑作者73项或整库。原独立风险探针新增 `--retest`，保留旧 failure JSON/log，单独生成 `task-E-A-retest-risk.json` / `.log`。**10组独立风险全部通过，actual exit0**：

- E原例 a@00公交100+有轨20/出行30，a@01缺有轨：结果明确 **4**，complete=False，趋势仍 `[120,None,None]`；旧 **220/60** 从未作为可接受值。
- 分区类别缺测：完整00时120/(20+10)，01时分区少一类，结果4；reason 明示有效1小时、排除1小时。
- 公司不同安全小时：a仅00时120/30，b仅01时60/20，综合 `(120+60)/(30+20)=3.6`；不是平均3.5，也不是无共同小时而缺测。
- 没有任何完整类别小时：None；保留“有公司无安全小时，总体系数不可计算”原因。
- 真实0/20仍是0；总体另一选定公司完全缺输入则None。
- 存在正客流但分母0的小时，与其分子一起排除；只留100/20=5。
- 取消测试覆盖查询中途与后段回调（后段第81次回调抛QueryCancelled），输入未变；同名无ID历史不任意关联、frozen数据及Unicode文件名仍通过。

考虑修复改变历史系数从日级改为小时配对，E用最新A再核验三真实缓存 **25范围/600小时趋势点**：全部0差异；既有有效系数/指标/分类/Top10保持独立原始计数结果，全市分担率仍筛选不变。输出另存 `task-E-A-retest-cache.json` / `.log`，actual exit0、`qt_modules_imported=[]`、25个保护文件哈希前后一致。旧的首次25/600证据未覆盖。没有重复无关整库回归。

修复版A SHA256 `b3f9f3aab68463a605dfbef5395411a75192996bc973aec1e450d483c59cd0aa`；最新A测试 `18bbbbb0c6a468e89b30ebc2c316981fad53129165502b978f259f259157dbb9`。风险运行前后A哈希一致，最终再读hash也一致；无Qt模块导入。

**E-A-01 定向复验通过并关闭**。当前两项P2均闭环，尚无本轮未关闭的A/D纯审查发现。仍不声明整个产品、GUI、原生视觉、实际125%或旧快照保存对话框保护通过；继续等待父同会话提供B/C/D最终审查和明确排期，不自轮询或触发Qt。

## B 包独立规格与质量审查 — 两项 P2 待修复

父明确交付 B 最终三文件/30组件用例/四图/元数据并要求只读审查。E已完整阅读页面、分类图、测试、B报告、最新契约以及被复用 ChartPanel/SurfaceMotion 的相关方法；未导入产品GUI模块，未启动 Qt/QApplication/MainWindow/全库测试，未占用 C 组件槽，未改产品或其他包文件，未发送跨聊天消息。

审查基线 HEAD `7057b9dbe14125794df7d0809ded12c76f5fa010`，三个文件均是该基线上的未提交新文件。SHA256 与 B 组件元数据精确一致：

| 文件 | SHA256 |
|---|---|
| frontend/latest_info_page.py | c6659da52cb62fdb92f36f96867fb323516cb82fba54c172530fda560e73b7be |
| frontend/latest_info_charts.py | b6e2c7fdeca4e2ce79e0771cd39d8eaddf6a2177dba39c9242bc01c8aea2de47 |
| src/test_latest_info_page.py | c3415500174fd3fbe7905bd202fe49fd023123dc21c78466434644a5076a1202 |

### E-B-01 / P2 / 缺测线路被纳入下钻排行

位置 `frontend/latest_info_charts.py:225`（客流制式钻取）及 `:455`（班次综合/制式排行）。筛选条件只核对制式，未排除被排行字段为 None 的 LineSummary；排序把缺测放在最后，但不足10条时仍把它们编号为有效名次。客流默认综合消费A的 `passenger_top10`，A已排除缺测，因此同一组数据在综合和制式钻取间还会出现有效排行条数不一致。

独立明确风险输入：同制式 known(客流5/班次2)、zero(0/0)、missing(None/None)，两条有效观测，实际两种下钻都传3条至 `fill_ranking`，客流脚注为“公交 · 3条 · 人次”，缺测线路随后被 RankingRow 编号第3。仅有missing时两种排行仍传1条、显示第1名，而非无有效排行。这些都是实际线路身份，不是造假线路；问题是把不可排序的缺测赋予名次。

预期：按被排行字段剔除缺测/无效数值，再排序并取最多10条；保留真实0，不为补足10条把缺测纳入。全缺测应有准确空态；线路详情仍可由其他真实线路入口访问。需要覆盖客流综合返回/制式、班次综合/制式、有效值+0+None和全None，不改A数据集合或把缺测改为0。现有30用例的短Top10仅截断A的top10，缺测测试仅覆盖指标/环图，未覆盖这两条排序路径。

### E-B-02 / P2 / 元数据缺模拟时间会使载入接口抛错

位置 `frontend/latest_info_page.py:392`。`set_session` 无条件把 `simulation_time or metadata['当前时间']` 交给共享 `parse_time`，该函数是 `datetime.fromisoformat` 且不接受None/单独时钟。`_set_city` 虽支持clock=None的未知态，但缺失输入根本到达不了该函数。A契约允许 simulation_time=None；A已对缺模拟时间有现成纯测试。

独立风险输入 `{'save_key':'explicit-risk-input'}`：实际 `ValueError: Invalid isoformat string: 'None'`。仅提供元数据 `当前日期='2013-05-21', 当前时间='23:59:13'` 而无顶层simulation_time：实际同类错误，输入字符串为'23:59:13'；A会把日期和时间合并。完整顶层时间'2013-05-21 23:59:13'的控制输入成功，秒值不丢失。

预期：只解析存在且合法的模拟时间；日期/时间分列时按与A一致的来源组合；无合法时间时clock=None并显示“未提供模拟时间”/“—”，不读墙上时钟，不中断元数据载入。补缺失时间/日期时间分列的组件用例，保持完整时间/秒数及当前禁用状态行为。现有B session fixture总是提供完整simulation_time，`clear_session`直接传None绕过该解析，因此原30项不覆盖此问题。

### E 独立证据与通过边界

E只运行标准库 `task-E-B-source-review.py`，由 AST 提取实际 numeric、PassengerRanking._render、DepartureStructure._render_ranking、LatestInfoPage.set_session 及共享 parse_time 的原方法体，在记录对象上执行明确风险输入。没有修改逻辑后再验证，也没有import产品/Qt；这是源逻辑探针，**不是GUI实例化或完整组件测试**。`task-E-B-source-review.json` / `.log` 保存2组排行、3组时钟输入、实际结果、准确源码与四图哈希。实际exit **1**（上述发现）；`qt_modules_imported=[]`，被审源码前后hash一致。由父读报告转 B 修复；E未直接修改产品。

E已实际查看四张B产物 wide/narrow/empty/large-total：宽版1200×852图片中Hero在928px主区顶部全宽，4核心+9辅助分层，四亮点字段完整，底部趋势/较宽Top10/班次三卡同排，十条排行与六制式名单/计数/占比均可见。班次默认左环右名单，大数155000图片局部上下排且21px数字移至环旁，无覆盖。空态无示例数据或报警；680×580窄图只展示滚动视口上部，后续内容可达性来自作者几何/测试，**E不能从该单张截图独立声称已滚到底检查**。

这四张都是明确容量fixture的offscreen QWidget截图，DPR1.0，不是真实存档、不是原生整窗、不是实际125%。B元数据报告wide滚动0/narrow滚动1440、字高检查无裁切、正常exit0；B作者报告30 passed in5.15s/actualexit0。**E未重跑这30项**，仅核对测试内容和元数据/源hash，作者结果不冒充E实测。

除上述两项，限定源码/已给图片范围内未发现额外必要修复：13固定ID与4核心选择一致，MetricCard消费实际InfoValue.value/unit/scope/reason且缺测和0分开；四亮点字段来自同一LineSummary；完整时间/真实Windows basename优先逻辑存在；scope/session不符和clear后旧结果被拒绝，切换即清图/指标/提醒并禁用生产动作；七个信号、更多菜单和打开按钮接线存在且没有按显示名跳线。线路/公司XLSX、分享/报告在本包仅发请求，实际动作由D后续集成验证。

趋势直接复用ChartPanel，Result原对象和None点未改；当天小时标签仅覆盖格式hook，tooltip仍沿共享完整时间；__selected__仅改显示名映射。分类图使用共享font/token/类别色/elevation，页面使用共享SurfaceMotion，不复制时间图源。环图只为正数生成扇区；列表保留缺测与0，两种钻取有返回入口。减动画行为只读核对，未执行动画/hover/键盘。

仍待C真实panel260px容量、D外壳/异步generation/保存对话框/全屏和真正动作，真实数据长数值+实际单位的排版，以及整窗/导航展开收起/hover/focus/实际125%。当前桌面前台输入不可达；后续若父提供后台HWND图片，也只作为后台原生渲染证据，不外推前台交互或125%通过。B本轮结论为**两项P2待修复，布局及其余限定源码接口无额外发现**。

## C 提醒GUI独立源码审查 — 限定范围无必要修复项

父明确交付 C 最终源码/测试/报告，要求在 B 短修复slot期间只读审查。E完整读取C402行GUI、24行纯模块、363行测试、C报告及原stats_alerts身份函数/原统计页阈值键。**没有运行Qt/GUI/全库/新提醒查询或真实挂载**，没有读取真实QSettings，没有写产品或跨聊天消息。

结论：本轮源码与独立状态/选择逻辑检查范围内，**没有发现需要交C修复的可复现缺陷**。此结论不等于C运行/原生/集成验收通过。HEAD仍为7057b9dbe14125794df7d0809ded12c76f5fa010，C三文件为未提交新文件。

| 审查文件 | SHA256 |
|---|---|
| frontend/latest_info_alerts.py | 851f52798054fb9f9c8ccded667275e3d6b13573740b11f26dada25706e656d2 |
| src/latest_info_alerts.py | cf4e4d8ab7fbbe3fb9ff64e8f37f1511935fa8a4c639f2e724268100865d8219 |
| src/test_latest_info_alerts.py | 3eeff8189da08bd52460e32679172eaa9d707fac668914c643f488cbb96afb79 |
| 被直接复用frontend/stats_alerts.py | 99b445750604265ae0fb313e2ab5d61fce876b4aaa8c54e8f5cf38920ba8c134 |

### 身份、设置、关闭与接口

- C GUI `:15`直接import原 `_alert_id`，不复制身份算法。session_key、稳定公司ID、组、指标、两期窗口及原值决定身份，显示名不参与。`:155`读取旧stats_alerts/read_ids，过滤损坏类型；`:208`保存时合并现存ID，保留历史已读。mark_read在`:198`先核对当前真实alerts，旧/外来对象不改变当前数据；重名公司额外显示ID。
- 原三个statistics阈值键/默认5、20、100一致，`:160`要求三非负有限数值，实际改变才写入并发thresholds_changed；同值无重复事件。阈值模态只有Accepted才取值，取消/旧会话reject不应用。
- 首页开关使用latest_info/alerts_enabled。`:172`保留alerts及read IDs，只清展示、关闭旧对话框并发enabled_changed，重复值不重复事件。**停止主动查询和取消正在运行worker仍由D监听处理**；C没有store/worker/query入口，不能声称该面板独自实现查询停止。
- 冻结构造与set_snapshot/clear_session/mark_read/mark_all_read/thresholds/alerts_enabled/两个信号均存在。同名src纯模块与frontend GUI的namespace在报告和GUI测试明确区分，未误导入Qt模块覆盖纯入口。

### 摘要、全量、详情、空态与旧对话框

- `:151`未读来自全量alerts；`:277`摘要只迭代alerts[:5]，不按未读数冒充总数；`:366`全量迭代完整alerts。所有行绑定真实alert对象的详情/已读按钮，列表更新后同时刷新摘要和全量未读数。
- `:335`详情保留指标、公司显示名+稳定ID、组、未格式化Decimal before/after及unit、两个精确半开模拟窗口和原reason；摘要沿原_display_number显示两位，不从摘要字符串推断数值语义。没有额外严重性/现实时间/线路报警。
- `_comparable`只控制空态，沿confirmed/非transfer/同长比较/完整非None桶判断；不改变模型alerts。关闭、无可比、可比未达阈值三种文字分开；数据行不足不补示例。
- `set_snapshot`先`:307`reject所有登记的旧列表/详情/阈值，再换状态和刷新；clear_session同路。`:299`的exec finally移除登记并deleteLater，全部对话框finally清_list_dialog。C源码没有识别过期worker的token，仍由D送入前核对会话/范围/generation；这是冻结责任边界，未判为C缺陷。
- 行文字使用共享font/FullLabel或明确PlainText+换行；共享token/elevation/reveal沿用。摘要长身份/值保留完整tooltip/accessibleName，全量内部滚动；运行时focus、嵌套模态行为和文字几何留待释放Qt后核验。

### E独立原方法体检查与作者运行证据分离

E标准库 `task-E-C-source-review.py` 通过AST执行C状态/选择原方法体及原stats_alerts._alert_id，在明确记录端点（设置/信号/布局/对话框）上检查。输入是E此前真实多人缓存JSON已验证的19条提醒记录重放；**不是新HistoryStore查询、不是新Qt挂载，也不是对作者真实modal执行的复验**。_row端点仅记录真实alert与expanded标志，不产生Qt widget；因此该探针无法证明排版或实际信号投递。

实际 **16项检查通过，exit0**：19条/摘要5/全量未读19、全量保留所有原对象、单条/全部已读（含历史ID合并）、改名身份不变/同名ID、值变新ID、拒绝非当前alert、关闭保留数据且通知/同值幂等/恢复、旧阈值键及无效阈值不写、clear拒绝三个登记旧dialogs、exec finally清登记/删除、空态完整与6种不可比情况、源hash不变且无Qt。`task-E-C-source-review.json` / `.log`保存来源SHA256、源码前后hash、每项结果与actual_exitcode=0，qt_modules_imported=[]。

C作者报告 **103 passed in19.27s/exit0，无skip**，其中23纯+12GUI、原提醒5项、相关纯63项。E已读测试内容：fixture只有GUI请求时才创建offscreen QApplication，临时INI，主题不写真实配置；真实模态取消/应用、已读全量/详情、开关重启/损坏设置及三缓存挂载均有实际行为断言。测试中真实缓存不存在时仍有明确optional skip，但本地所声明CSV存在、作者本轮报告103无skip；没有全局GUI opt-in/hold skipif。**E本轮没有重跑作者103/12GUI或再次跑已验证的23纯项**。

C报告真实挂载4/9/19条，260×788 panel、B1200×852/纵向滚动0；这是作者offscreen真实数据组件证据。望春C使用exports/望春市_test/04-28；E此前jobs/68efa...为04-18、3条，不同输入不把9vs3当缺陷。E本轮只确认作者测试路径及文件存在，没有新生成4/9/19或独立实测几何。B当前仍在修复slot，E没有读取/执行活动B源，也不沿用旧Bhash宣称最终挂载通过。

父同步的 `refreshed-peer-baseline.json` 七文件明确DependencyBaselineOnly，只作为接下来集成的依赖基线，不列为本工程交付、不据此声称E独立核实主目录变化。D接线、取消/主动查询停止、统计页重复入口移除、真实dialog/键盘、完整系统回归与native/实际125%仍待父排期。本轮C无新增必要缺陷；B两个P2等待稳定修复交付后定向复验，E不会与活动源竞争。

## E-B-01 / E-B-02 定向纯源复验 — 两项已关闭

父明确通知B代码已稳定、D已接Qt槽后，E仅只读B修复/追加18个GUI用例，不读D活动源、不启动Qt或执行pytest。B报告当时仍是上一轮30项版本、作者正在补报告；父已从实际工具输出核实新增18项RED17fail/1pass、排行9与时钟9GREEN、最后全部48项7.44s/actualexit0。这个48项是**父提供的作者运行证据，不是E执行结果**；E AST独立数参数化定义也为48项，未collect或运行。

E原 `task-E-B-source-review.py` 新增显式 `--retest`，输出另存 `task-E-B-retest-source.json` / `.log`；原failure JSON/log未覆盖，旧JSONSHA256仍为 `31036c7ba71e747599518527cfd096bff7d86a2ef3920e67a7802fab59a5db10`，actualexit1保留。复验执行原numeric/排行/set_session/_set_city/共享parse_time方法体，端点是标准库记录对象，**不是GUI实例化**。

E实际复验 **10组排行输入（每组两种排行方法）+10组模拟时间输入全部通过，actualexit0**，qt_modules_imported=[]，新源码前后hash一致：

- E-B-01：已按相应字段numeric非None过滤，再排序/截取；综合和公交制式均检查。原known+zero+missing仅留下known/zero，脚注为2条；全缺测为空0条。NaN/inf同样被排除，真实0和有限负数保留数值顺序。源码fill_ranking空态文字已改为“当前范围暂无有效排行数据”，不为凑10条加缺测行；无改A线路集合或把缺测转0。**E-B-01关闭**。
- E-B-02：set_session候选来源与A一致：顶层模拟时间优先，缺顶层时按元数据日期+时钟组合；日期仅有时沿A既有午夜约定；不存在或parse异常均clock=None。原缺失输入不再抛错，_set_city实际原方法体在记录label上得到“未提供模拟时间”/“—”；分列日期+23:59:13正确显示2013-05-21/周二/23:59:13。明确None、只有时钟、坏顶层/坏元数据均准确未知，有效顶层不被另一元数据时钟替代；无读现实时间。**E-B-02关闭**。

| 修复版文件 | SHA256 |
|---|---|
| frontend/latest_info_page.py | af114b49d09d3f83496c878e03185136920733c7ce41c68e676fe955df227eb6 |
| frontend/latest_info_charts.py | 908f09f7d63a17263aad0e1d86d421dc37b66740376fb7008190c788561807c2 |
| src/test_latest_info_page.py | 24d3a723f13816faf48a27efa567b862ad14234bc9622d578e992fc7e8a57991 |

旧四张组件图未重拍、task-B-component-metadata.json仍属于旧sourcehash；新复验JSON明确author_component_metadata_hash_matches=false、图片状态为旧fixture图。此差异为预期版本差异，**图片不作为修复后的运行或排版结论**。本轮修复逻辑不改布局，前次图片只保留历史组件布局观察；未来统一Qt回归覆盖48项和最终D+C集成。

当前E-A-01、E-D-01、E-B-01、E-B-02四项既有P2全部独立定向复验关闭；C限定源码审查无必要发现。E只写QA探针/报告/验收文件，未改产品/缓存/probe/设置，未Qt/消息其他聊天。D控制器/共享接线活动中，本轮不争源；待D最终稳定报告再整体只读审查，native/MainWindow/实际125%仍hold。

## D 最终接线只读审查 — 无阻断项，转入独占验证

父提供最终D报告及slot-release明确Qt全退出，并后续放行E独占整套与真实MainWindow背景验收。E先读controller、已审exporter、四共享diff、B公开workbook可用性微小hunks、旧五测试适配及新增集成测试；本节为运行前结论。**限定源码审查未发现必须先修复的阻断项**。

- Controller唯一worker捕获请求token、data、稳定scope、阈值、开关；A取消回调→C独立日查询，缺A模拟时钟仍发布可计算首页且不查询C，关闭提醒同样跳过C。scope/threshold/enable/session先清快照/动作/旧提醒、取消旧worker并增token；receive再核对token、当前会话key、scope/closing/page有效性，旧失败也被拒绝。
- 新worker父对象在关窗期间保留；MainWindow在wait超时ignore并等finished重试，原parser/统计关闭链保留。历史线路build/show/refresh、cancel_parse以及统计schedule/submit/stop/thresholds共8个方法E独立AST与本树HEAD一致。取消/失败/重导入清旧行与worker回填拦截代码存在；运行验证接续。
- 复制/分享/报告基于同一确认快照；报告对话框返回重验snapshot/alerts/token/data/key。原XLSX来源需is_file，复制前后重验source和session/token，保留字节复制。B公开set_workbook_availability默认False，set_session/clear重置、按钮及窄菜单同步，仅原line/company受文件状态约束，share/report仍按快照有效性。
- 四共享hunks集中在首页替换、主header唯一入口、提醒迁移、异步生命周期及源启动bootstrap。统计页7controls/fields及bottom索引同步，原DashboardTask/阈值键/查询/导出保留；stats_integration仅移除第二提醒创建/刷新，不删统计导出。stats_text仅overview文案。
- 五旧测试适配保留身份、制式、导航/重导入、原XLSX字节、unknown时刻表行和窄窗动作；旧equal首页控件断言换到新公共页面。非有效间隔None替代旧0符合冻结定义；金额断言按显示两位精度，非删除行为覆盖。
- controller显式区分src.latest_info_alerts纯模型与frontend.latest_info_alerts界面。desktop bootstrap在SRC后加入PROJECT保障异cwd；正式CIM2_SaveStats.py与spec入口/path已只读核对。源码入口新增隔离subprocess真实MainWindow用例存在；打包EXE未运行或重建，不外推为EXE启动验收。

`task-E-D-integration-source.json`记录14文件当前SHA256、8受保护方法AST、7个peer最终哈希，检查exit0。父最终peer JSON实际更新line_query_page与test_line_query_layout，其他5项未变；7项均匹配，**只作依赖基线，不是本工程候选**。主HEAD后续变动由父合并阶段核验，本树仍7057b9+明确peer刷新，不能整分支/整树覆盖主源。D132/纯82是作者证据；E尚未据此声明整套通过，下一阶段独立执行并记录排除与原因。


## E 最终独占运行、真实窗口及释放 — 当前最终结论

E已完成旧版功能限定QA，既有四P2全部关闭。**用户否决当前视觉，不能把782功能/几何通过写成视觉合格；父已暂缓主源应用，Astra审计由父安排。** 本节替代前文阶段性“未Qt/hold”的运行状态；历史过程保留。E只写QA文件/证据，不stage/commit、不消息其他聊天、不改父DELIVERY。用户要求未明确请求的说明禁止添加，文案审查见copy-audit；产品只读未删改。重构前主源baseline截图只准备，不启动，等待明确Qt放行。

整套实际首轮773passed/1failed/13deselected、220.43s、exit1；唯一test_standalone_uses_local_app_data失败由E basetemp在标记仓库内导致，既有jobs_directory正确走workspace分支。外部tmp实证命中LOCALAPPDATA，app_paths规范化源及AST与HEAD一致；CRLF/LF原字节差异不是产品改动。父后放行局部offscreen click/key/focus后，9项补跑5.24s/exit0（该采样项+8原受限项）。合计782不同pass，最后5项仍未执行。详见suite-combined、原suite.log、targeted-result/log、sampling-diagnosis；不能写成单次782pass/exit0。QSettings隔离是独立临时INI，首个准备失败未启动pytest，证据保留。

Native最终四份metadata均actualexit0：native-autumn-scale1.json, native-multi-scale1.json, native-all-scale1-25.json, native-multi-scale1-25-detail.json。秋山/多人DWM可见截图1440×960、实测DPR1；三缓存1800×1200、实测DPR1.25。宽窗scroll0、13指标/4亮点/Top10十条/全部真实类别，21px数值/12px单位，数字宽度足够，PNG人工核对。三缓存提醒4/3/19与独立缓存结果相等。多人扩展/收起、920×680逻辑客户端（可见PNG924×740或1154×910）、范围/旧token/全市比例/已读/旧阈值与stat同步/开关/真实linekey/取消清理都passed。

真实多人追加模态：原_show_all/_show_details及原exec运行，自有dialog no-activate，局部定时背景捕获后reject；全部19行对象、未读19、详情公司76561198845688243、205445.19→356672.09货币、本期04-09→04-10/对比04-08→04-09及原因完整。单/all读后状态、dialog登记清理通过。16个亮点数字available>=required，未发现密集数值裁切。详情文字窗颜色判据从主图>100改为>10且人工图审，两轮原日志均保留；原判据exit1不等于产品缺陷。

实测OS_GetDpiForSystem/Window192=200%。系统DPI未设置，进程factor0.5/0.625，对应QtDPR1/1.25；不是实际OS125。初次默认200%窗口被最小逻辑920×680撑大到1866×1431，不冒充1440；已备份first-system200。启动前GetDpiForSystem96而启动后192是QA初始化采样问题，最终显式已审计base192并启动后assert；失败log保留。所有最终PNG为PrintWindow自有HWND，不是桌面pixels；foregroundHWND与当前QA HWND不同，未原生点击/键盘/鼠标移动/系统DPI变化。真实前台hover/Tab与parser/backend/EXE未测。

导出实际产品PNG独立于native截图、六表XLSX读回13指标/Top10/全部提醒/总班次。最终标准库consolidation核验当前D14源/所有native源及保护文件、26条artifact hash/PNG尺寸/XLSX ZIP一致，actualexit0。native原save_path来自manifest精确值，不从tag猜名。当前验收MD顶部/表格/README均改为实际最终结论，历史缺陷表保留。

所有QA执行进程实际退出，最后Get-CimInstance独占槽读查无Python/CIM2_SaveStats进程，QtAllExited=true / PythonProcessesRemaining=0，见slot-release。E不再运行Qt/整套、不扩测试，独占已释放；父已暂缓apply，七项peer仍只是依赖基线，不整树覆盖。E旧版QA交付包含qa_latest_info.py、qa_latest_info_native.py、验收MD、证据README/PNG/XLSX/metadata及E脚本日志报告。


## 原主首页视觉基线补采完成；Qt再次全部退出

父转原协调者明确放行一次只读原主MainWindow后，E已从D:/test/CIM2_SaveStats加载同真实多人缓存，manifest精确save_path；用原on_completed/navigate及toggle_passenger既有动作采默认与原综合Top10两张1440×960背景PrintWindow PNG。输出astra-visual-audit-2026-10-01/before-main-multi-1440x960.png、before-main-multi-top10-1440x960.png及metadata，actualexit0；主frontend/src全部py/CIM2_SaveStats.py以及原save/CSV/manifest/probe前后hash一致。实测OS192/200%、process factor0.5/DPR1，与新稿scale1可直接按同目标比较。两图人工查看无透明黑背景，包含真实原首页/条形饼图/原Top10；不是新逻辑、不是桌面/前台采集。窗口立即close、统计worker停止，最后进程读查Python/CIM2_SaveStats为0，QtAllExited=true。未发送跨会话，Astra由父联系。用户视觉否决、未请求说明禁止添加仍有效；报告顶/README已更新。782结果仅旧功能几何，不外推新视觉或修订版。

## 第二轮准备 — 仅静态计划，未Qt

已完整核对ASTRA-AUDIT、OLD-ANALYSIS-INTERACTIONS及LATEST-INFO-REVISION，实际查看可靠旧main默认/Top10图。新增LATEST-INFO-REV2-QA-PLAN-2026-10-01.md及独立latest-info-rev2-evidence/README。计划逐项双图三态真实局部事件、独立CSV排序/分母/坐标、单击优先级、稳定mode/key、两图独立与普通refresh/scope/session；新逐公司真实折线、地图头raw trace/规范名、提醒与新导出、DPR1/进程125/物理小窗分开。未导入产品、未QApplication、未跑pytest、未改源、未stage/commit/消息/代理。B当前Qt独占，D稳定后等待父给稳定API/hash与正式Qt转交；旧782不作第二轮等价/视觉证据。功能与父/Astra视觉独立签收，用户未请求说明禁止添加仍优先。

## 第二轮 A 独立纯审查完成；合并结构授权已纳入

独立限定无必要产品修复发现。42边界/状态检查实际exit0；三缓存25范围325指标/600原聚合点/672逐公司点一致，原13值/单位/范围/reason/complete不变。旧无来源filename不信、变长头/有界拒错/一般内部名与rawtrace/真实ID缺口及未来时刻已核验；共享两文件授权hunks以外AST与HEAD相等。全部CSV/manifest/原save/probe及A/纯依赖源全文hash不变，未Qt/pytest/backend/作者全套/活动B源。脚本first及recheck中的E字节构造、公司名ID映射、全市owner输入问题已定位，原exit1保留，定向42边界exit0与真数据读回合并，非单次45项pytest。详见task-E-rev2-A-findings.md、review-final.json及新rev2目录A-pure-review.json。

父核验B直接userMessage 01a0f83a-4ad7-7803-b223-aafb1e1d8d49已允许堆积/饼图合并；REV2计划现在环心总数/单位+完整列表绝对数/占比，独立堆积默认/点击不再拒收，扇区/列表钻取与三态仍保持；返回为“返回结构图”，旧28GREEN不可外推新合并。B仍持Qt，E后续事件/原生/视觉等待稳定接口和正式转交，不自判通过。

## 第二轮验收规格再次更新 — 2026-10-02最新Astra人类指导

已读ASTRA-AUDIT顶部新指导，REV2计划改固定业务标题/制式分布-线路排行-线路占比正常化名称，统一返回图标≥28x28/tooltip+accessibleName返回制式分布/键盘焦点、默认隐藏disabled箭头及卡头稳定。ranking↔line_share保留内mode，统一back清内mode但不改global或另一图；单制式页面内“全部制式”不得越界，D按opaque保持真实line_share.mode。其他线路N为实际合并数，零尾只列不画slice，未知不假归一化。前端只必要说明，source/formula/完整窗口/缺测细节保留详情与报告；首页负责人在实施聊天逐项报告，非首页文字。旧28/87作者GREEN不当最后规格结果。此轮仅文档更新，无Qt/活动B源/产品写入；A限定纯核验已完成且未因无源变更重复。

## 第二轮四模块与共享微渐变规格更新 — 2026-10-02

已同步Astra顶部最新四业务模块指导：13项各一次、核心/辅助字重层级、标签/值/紧邻单位同时可读、四极值全字段、无说明按钮/起讫/徽标；真实字体及真实缓存整窗签收，94作者组件结果不代替。只读统计页实际opt-in交通色路径，计划记录六规范key独立颜色期望与全存档稳定公司ID色板注入；实际渲染未验。趋势保留共享ChartPanel/FluentChartView微渐变、真实公司QLineSeries/单公司序列，无面积选项，同名公司需真实短身份及完整tooltip。C现持Qt，C→D→B追加视觉修订→E；本轮只改E计划/文案审查/报告，未启动Qt、未改产品、未重复A核验。

## 第二轮D冻结控制器限定静态审查完成 — 2026-10-02

未发现必要修复问题，详见`task-E-rev2-D-static-review.md/.json`。父提供两源SHA实读一致，静态AST仅4个既有controller方法改变/新增remember，16个方法与worker原样、receive旧门禁原样；9函数24参数用例只计数未执行。独立核查data/saveKey/sourceScope/targetScope/token、连续pending、旧ready/failed拒收、新快照先安装再恢复纯state、refresh/阈值/开关/同会话scope保态及新会话/当前失败/clear/close清态。无Qt/产品导入/pytest/作者结果重跑，产品源前后不变；没有真实事件或整窗通过结论。B现持视觉实施/Qt，E最后由父转槽。

## 三份第二轮独立脚本准备 — 2026-10-02

已写qa_latest_info_rev2_oracles.py/events.py/native.py，仅E QA源/证据。原始CSV oracle实际exit0：三缓存25范围/672公司小时点，5组明确fixture，完整保护hash不变；不运行A既有42边界或产品模型。Other按真实剩余集合数量记录，未知key与已知量/complete分开、完整分母缺测不画100%。语法、三模块import及两个GUI脚本默认路径actualexit0，qt_modules/product_modules均空，events/native未执行；first日志与preparation.json保留。

准备事件使用实际局部QTest鼠标/键盘，期望不调用被测_hit/排序/%函数，坐标独立从原始权重及控件bounds计算；palette沿真正opt-in实例比独立常量。native准备单MainWindow/临时INI/自有HWND PrintWindow、真数据与XLSX读回复用既有A指标证据，OS/进程缩放明确区分。总数三态实际可见/单位/全文、长值不resize异步交付及同会话范围更新已加准备断言与独立fixture。

最新父核验人类要求已跟随：四业务组各共享Fluent图标，四极值独立卡/max蓝min紫角色条、每卡四值共16与真实key/字段语义，不写死旧无图标、无色条或共享rowheaders。最终模块/图标/角色条与字段关联还需B稳定源码绑定；脚本尚未运行Qt，不能将语法、原始期望或作者数量视为界面通过。B仍持独占槽，E等待父正式转交。

## 第二轮E独占实际事件RED — E-B-REV2-01待B短修复

父正式转E槽后，140源/68保护文件/125主源固定，26候选SHA匹配；raw oracle三缓存25范围672小时点再次exit0。最终源码绑定模块IconWidget、独立角色条及极值grid；QA准备路径斜杠、排行总数不适用、完整换行与card字段语义假设只改E驱动器，见driver-adjustments。未改产品。

真实秋山events-e01第18动作Return失败，原actualexit1及18条事件保留。定向实际Qt12项再次exit1：两图ranking/line_share下Return和Enter均clicked=0（8失败），Space均clicked=1（4通过）；焦点/启用/可见真实确认，8项鼠标对照均返回成功，无tooltip干扰或show_*。确认为当前TransparentToolButton缺少Enter处理，非驱动焦点失效。详见task-E-rev2-findings.md、return-key-diagnostic/matrix.json及原日志。

产品源/全部保护文件/主源及26候选SHA仍一致；两次Qt已返回、workers均停止。按父最新指示暂不启动native或必要回归，交回槽给B最小修复；后续新锁/新目录复验，不覆盖RED。当前尚未完成全事件/整窗/导出/视觉签收，不以作者103代替。

## 2026-10-02修复后独立复验与原生RED

新source-lock-after-keyboard.json核准140源/26候选，只B charts/test两个授权改动；原RED锁及8失败日志保留。12返回键actualexit0（12pass，每项clicked1），events-e03 actualexit0（真实三缓存＋5明确边界共458局部动作，四极值独立key包含鼠标/Return/Space）。events-e02容器目标失败属于E驱动错误，修正为实际row.action，原exit1不删除。

原生e01/e02/e03因OS DPI误作Qt基础DPR未过装载门禁，保留失败。当前WinDisc校准baseQtDPR1，factor1取得实测windowDPR1、OS192及DWM1440×960。native-multi-dpr1.0-e04 real-default.png为当前真实多人MainWindow自有HWND PrintWindow，父/Astra可审；actualexit1：同视觉row0客流字段中心496.5/496.5/491.5/491.5，5px不齐（E-B-REV2-02）。未删除断言或改产品。剩余图态PNG/导出/一次长值fixture及三缓存/两DPR矩阵、限定回归尚未执行。

实际share-summary.txt及copy-budget确认长范围重复和固定缺测尾注仍存在（E-COPY-REV2-03），未写剪贴板。用户“未让我写的说明禁止写”已记录copy-audit并持续遵守；首页隐藏范围/排行计数不误报为可见。

最终140产品源、68缓存/原save/probe/index保护、125主源、26候选全部未变。worker停止、窗口退出，Get-Process python/pythonw/parser_backend无进程。slot-release-after-native-findings.json确认Qt槽交回父；实际OS125与前台输入未验，视觉待根/Astra。

## 最终证据只读复核（2026-10-02）

本轮只读检查父执行记录，未启动Qt、修改产品或QA脚本。最终锁source-lock-final-post-aux.json（SHA256：34BE7ACBCCB567979D9BEF867ABB46030658D7C65F5A33ADD3A71FD59A9A6270）140源匹配；页面SHA256为c565909d47f52e27679ccc095b9e466ecc7e40279c188b8a763864febf08d79d。

父执行的五份最终native.json均exit0，合计285动作、48截图；核对全部截图hash及10份原XLSX复制的源/目标hash。记录确认源与保护文件未变、worker停止，六表导出含13指标、16极值、Top10及提醒读回通过。此处为证据复核，非E重新执行导出或界面测试。

| 配置 | 动作/截图 | 默认视口 | 纵向滚动最大值 |
| --- | --- | --- | --- |
| 多人 DPR1 | 61/12 | 1204×860 | 0 |
| 秋山 DPR1 | 56/9 | 1204×860 | 0 |
| 春山 DPR1 | 56/9 | 1204×860 | 0 |
| 多人 DPR1.25 大窗 | 56/9 | 1205×872 | 0 |
| 多人 DPR1.25 小窗 | 56/9 | 917×680 | 1773 |

前五份记录后续图态因侧栏收起变宽，不能据此称三个图态均在原宽度通过。父补充stable-sidebar记录独立exit0（61动作、12截图），排行/占比/返回六项均1204×860、滚动0、三卡完整可见。补充记录不计入上表。百万总数1,376,429人次以21px完整显示；长值167,901,234,706人次以18px页头回退完整显示；同范围16极值字段单位间距均5px。重复长范围及固定缺测尾注检查均false。

E此前独立controls-e03实际195动作通过，属于辅助布局修复前页面913967…，图表源与最终版一致；不称为最终页面独立重跑。E原生e05因空owner读回None与空字符串比较失败（57动作），父修正QA归一化。父e06/e07暴露真实辅助字段间距−2px，产品最小布局修复后最终证据通过。原返回键、驱动目标、DPI假设、分段边框断言及上述失败记录均保留，不计为通过。

最终回归日志确认146 passed、8 warnings、28.71s，属于父执行。实际系统125%和前台交互未验证；DPR1.25来自进程缩放。E本轮未做最终图片视觉签收。Other63条图例换行仍为已知P2，未宣称修复。用户禁止未请求说明的要求继续适用。
