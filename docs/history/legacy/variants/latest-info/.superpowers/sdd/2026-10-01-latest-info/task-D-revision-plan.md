# D 第二轮接线方案：最终公开合同与验证准备

2026-10-02 实施更新：父已授 D Qt 窗口，本方案24项实际 RED为18失败/6通过，最小 controller 修复后24全通过，最终受影响72项及纯导出15项通过。交付以 `task-D-revision-report.md`、两个 revision patches 和最终 hash 为准；以下准备阶段等待窗口的文字保留为历史设计，不再是当前阻塞。未改 B/C/A/shared 或做视觉签收。

当前阶段：父已确认 B 最终合同稳定，D 已亲读最终报告/capture 源码并核对 page/charts SHA256。历史捕获时序落差已修复，不再是待确认事项。D 已准备 24 项 revision 用例，但未执行 RED，controller 产品未改。C 当前独占 Qt；父释放 D 窗口后执行 24 项实际 RED→最小 controller 修复→必要受影响回归。未 stage/commit，未写主工程/其他产品，无需再向用户确认方案。

## 最终公开合同（以本节为准）

- `capture_chart_state()` 返回独立新字典：session_key、真实来源 scope、两图独立 `{view, mode}`。view 为 structure/ranking/line_share，structure.mode=None；ranking 和 line_share.mode 可为真实规范制式，None 表示当前页面范围内所有制式。没有 Qt 对象、snapshot、数值或旧分母。
- 当前 capture 已在无 snapshot 但同会话 pending 时返回纯意图的独立复制；有 snapshot 时来源 scope 取已接受 snapshot，而非已改变的全局 combo。重复范围变化沿用来源意图；clear/new-session 重置。
- `restore_chart_state(state, *, allow_scope_change=False) -> bool` 必须已有合法当前 snapshot；严格 session、合法 scope，默认严格匹配 scope。True 只放宽同存档 scope 匹配，不放宽会话或新 snapshot 门禁。单卡 mode 无效回 structure，另一卡有效状态仍恢复。ranking/line_share 用当前数据重绘。
- D 原样保存/恢复公开 state，不改其来源 session/scope/mode，不读私有 pending/widgets；同存档跨范围显式传 allow_scope_change=True，并在自己的包装记录中同时匹配 data identity、save-key、目标 scope 和 token。set_data 保留有效状态，clear 重置。
- 最终冻结文件指纹：page `23FFC47E1797C72E7B9C6654BA2BBA4A51A2DA5E4B7AF7C961F9DA3122501640`；charts `802AAE44EA1B26574CCD82DB24C117A42C70B930D3341E577F4F7A1EF129EC2D`。D 不写 B 四文件。
- 用户允许合并环图＋完整列表、环心总量；最新返回文字/图标由 B 控制，D 测试不依赖历史文案。后续四业务模块视觉改版不改变此状态合同。

## 2026-10-02 静态测试准备更新（最新阶段）

父后续已明确捕获时序，不再提新 API；D 等 B 最终实测。最新状态合同保留原 JSON shape，但 line_share.mode 可以为实际规范制式（ranking↔line_share 保留图内 mode，返回结构清 mode，不改 global）。D 必须 opaque 保存/恢复，不能假定 line_share.mode 永远 None，合法性由 B 判断。已在同范围恢复、同会话公司范围切换和单卡失效模式中补 4 个参数，当前共 9 个函数、24 个准备用例，尚未执行；下文 20 为早期准备记录。

父转交并亲读 B 稳定文档 `task-B-revision-report.md`：最终名称为 `capture_chart_state()` 和 `restore_chart_state(state, *, allow_scope_change=False) -> bool`；JSON-safe 新字典包含 session_key、来源 scope、passengers/departures 独立 view/mode，综合 ranking.mode=None；允许跨 scope 只放宽同 session 的范围匹配，单卡失效 mode 回 structure。`set_data` 保留有效状态，`clear` 重置。

D 据此只在 `src/test_latest_info_integration.py` 追加 9 个测试函数、20 个参数化用例（`-k component_revision`），函数内延迟导入 Qt；覆盖双图普通重查、阈值/关/开、连续 pending、3 类图态公司切换、失效模式单卡复位、连续目标范围＋旧 ready/failed、错误 scope ready、3 类会话更替、clear/失败/close。测试用实际页面及公开 capture/restore/C setter；恢复 spy 调用真实恢复方法，不替换图表渲染。直接设公开状态仅用于 D 持久化门禁测试，不冒称 B/E 真实鼠标事件等价验证。

20 项尚未执行，既不是 RED 也不是 GREEN；没有 Qt/pytest 启动。controller 产品仍未改，等待 B→C→D 的明确 Qt 窗口，先实际运行正常 RED 后再实现最小产品修改。controller SHA256 仍为 `A27528E0C488776540E454AE79B399E45B8EE973DADC0A17AD4A9C8A2E8FD336`。

此前静态发现的 capture/pending/来源 scope 问题已由 B 修正并实测；顶部最终合同和当前源优先。本包跨范围用例通过恢复 spy 要求来源 state 原样且显式 allow_scope_change=True，不允许来源伪造。

实现设计继续使用独立 context 包装 state：origin data identity/save-key/source scope、target scope/token 与显式跨范围标志；不修改 state 内任何来源字段。capture 到默认/None 会话的空页时不覆盖合法 pending；新结果门禁后 set_snapshot、按匹配记录 restore、消耗 pending，再发布 snapshot_changed。旧 ready/failed 直接拒绝且不清当前记录；当前失败/clear/new-session/close 一律丢弃记录。下方早期 API 示意名以本节实际名称为准。

依据：`docs/ui-redesign/LATEST-INFO-REVISION-2026-10-01.md`、`docs/ui-redesign/astra-visual-audit-2026-10-01/ASTRA-AUDIT.md`、同目录 `OLD-ANALYSIS-INTERACTIONS.md`。D 可写范围仅 `frontend/latest_info_controller.py`、`src/test_latest_info_integration.py`；B page/charts、A 原始地图与模型、C 提醒视觉、共享 shell 均不可写。

## 静态根因

1. controller 的 `schedule_query` 无论来源都调用 `_invalidate`，而 `_invalidate` 调用 page.clear_session、page.set_session。因此同存档同范围的 refresh、threshold、alerts enabled 变化也销毁图态。
2. 旧 B 的 set_snapshot 重新给两图 set_data；其中班次 set_data 无条件回 structure，客流下拉也重建。仅让 controller 少 clear 一次，无法保证两图完整三态保留。
3. page 的 `_scope_changed` 在发 scope_changed 前已 `_clear_snapshot`。D 不能依赖该信号后读取旧范围图态，更不能从私有 chart 控件推断上一范围。
4. 连续重查时，第一次失效已令 snapshot=None、清空图内容；第二次重查若从已清空 page 再捕获，原用户图态会被默认态覆盖。需要一个只属于当前身份/范围的 pending 记录，而不是每次无条件读 page。
5. `_receive` 现有 token/session/scope/closing/page-valid 门禁必须保持；只在合法新快照呈现后恢复图态，不能通过保存旧 snapshot 维持视觉。

## 历史接口分析（已落实，不再请求确认）

早期能力分析记录如下；最终名称及实现语义均已落实为顶部 capture_chart_state/restore_chart_state，不再按早期示意名称接线。

|能力|需要的公开契约|
|---|---|
|捕获两图状态，例如 `capture_analysis_state()`|返回不持有 QWidget、旧 LineSummary、snapshot、图形数据的独立不可变值；客流、班次分别记录 structure / ranking / line_share，ranking 保留原始规范 mode key；综合排名与结构必须可区分。不得使用百分比标签、下拉 index 或显示文字当身份。默认状态也要可捕获。|
|恢复两图状态，例如 `restore_analysis_state(state)`|只能应用在 page 已接受的当前 snapshot 上；两图独立校验，ranking(mode) 的 mode 在当前该图有效制式中不存在时仅该图回 structure；合法综合 ranking 与 line_share 基于新 snapshot 重建，绝不复用旧值/分母/线路 key。恢复不得触发 page.scope_changed、改变全页 company/mode 或发线路跳转。同存档受控跨范围恢复须有显式公开能力（例如 allow_scope_change）或 B 公开的纯图态适配，不偷改状态里的 scope 绕门禁。|

最终 B 已明确清理/更新/模式验证与新字典语义。D 不读取 passengers/departures 的私有 view/mode/expanded/stack/ring 或 mode_combo 来实现持久化，不向 B 文件加临时 API。

跨范围捕获时序已明确：page 在清理前保留纯意图，清理后 public capture 返回其独立复制，来源 scope 为确认 snapshot 的旧范围。不再需要附加通知或新 API。

建议双方职责：D 负责当前身份/范围/token 的保存和消费；B 负责每图结构及制式合法性、基于新数据渲染状态。只有这两个公开能力即可围绕现有 clear/set_session/set_snapshot 接线，无需扩大 page 的数据接口。

## D 最小状态门禁设计（合同已稳定，实施待实际 RED）

pending 记录只包含捕获值及上下文：当前 data **对象身份**、save_key/session_key 字符串、来源全页 `(company_id, mode)`、本次目标范围、目标 token、是否父允许的同存档跨范围视图恢复。它不是历史缓存、settings 持久化或另一份业务 snapshot。来源范围不伪造；目标范围只用于当前查询门禁。

同存档同范围普通重查：

1. 只有当前确认 snapshot 的身份/范围与 data/page 匹配时，才通过 B 公共能力捕获两图状态。
2. 如果当前 snapshot 已因上一轮重查清空，只能沿用身份/范围完全匹配的已有 pending；不得捕获被清理页面的默认值覆盖它。
3. 保留原 token++、停止 debounce、requestInterruption、snapshot/alerts 清空、动作禁用及页面内容清空路径。pending 的目标 token 随本次重查更新，图态记录自身不包含旧数据。
4. 新结果通过原 token、当前 data/session、scope、closing、page-valid 门禁后，先 page.set_snapshot(new_snapshot)，然后仅对匹配 pending 调用 B 恢复接口。工作簿可用性、C set_snapshot 和 snapshot_changed 发布保持原行为；对外发布前两图已在新数据上恢复。
5. 成功消费后立即清 pending；旧 token 的 ready/failed 不能消费或抹掉当前 pending。

阈值与开关仍用公开 `set_thresholds` / `set_alerts_enabled`，不依赖 C enable_switch 等视觉控件。enable=false 仍不主动 C 查询，enable=true 仍按真实模拟时钟与原窗口查询，图态保留独立于提醒查询。

上下文失效策略：

|事件|pending 与图态处理|
|---|---|
|手动 refresh、阈值变更、提醒开关变更，同数据/同身份/同范围|捕获或沿用匹配 pending，合法新快照后恢复两图，各自维持状态。|
|连续重查 / 前轮已清空 snapshot|沿用匹配 pending，更新目标 token；不从空页取默认态。|
|同存档公司或全局制式变化|保留纯图态意图，显式标记受控 scope transition；绑定新目标范围/token。在新 snapshot 通过门禁后，由 B 公开跨范围恢复接口重新校验图内制式并重绘。不能复用任何旧值、旧分母、旧线路 key。|
|同范围新数据令某图钻取制式消失|B 在恢复时仅该图归 structure，另图合法状态仍保留；使用新 snapshot 的可用制式，不使用全局 combo 列表冒充该图可用数据。|
|换存档/set_session、clear、解析取消、当前查询失败、close|无条件丢弃 pending，清空快照/提醒/旧分类与旧展开数据。|
|同一 data 对象内 save_key/session_key 被修改|视为身份改变，丢弃 pending；不能只比对象 identity。|
|旧 ready、旧 failed、错误 session/scope 的结果|原门禁直接拒绝，当前 pending 不受它影响。|

父已明确范围语义：普通同存档/同范围重查必保留；同存档公司/全局制式变化允许保留纯图态及仍有效的图内制式。line_share 与综合 ranking 用新 snapshot 重绘，两图独立；失效图内 mode 仅该图回 structure；换存档全部重置。D 不把旧范围 pending 当作新范围状态，也不偷换其来源 scope，而是通过 B 明确公开的受控跨范围能力，保留来源身份、绑定新目标 scope/token，且在接收合法新 snapshot 后才恢复。任何过程中旧 snapshot/旧比例都不可闪回。

如果范围连续变化而 snapshot 仍为空，只能沿用同 data/同存档的已有纯意图记录，更新目标范围/token 并保留来源上下文；旧 token ready/failed 仍被拒绝。若 B 页先清理导致未捕获到纯意图，必须调整公共捕获时序契约，不以空页默认状态覆盖上一意图。

## 依赖稳定后准备的集成用例

不先猜 API 写实现或假 chart。D 的状态保持测试将使用实际 A 快照+B 实页+C 公开方法+controller，恢复断言经 B 公共状态能力读取；真实堆积段/扇区/列表/综合Top10/线路占比/返回等事件等价矩阵归 B/E，D 不以直接调用恢复接口冒称事件已验。

- 参数化两个独立图态：structure/ranking(综合)/ranking(制式)/line_share；操作一个图后另图保持，普通 refresh 的合法新 snapshot 前后相等。
- 改提醒阈值与公开开关触发重查：snapshot 立刻 None、导出动作禁用、token 增加；结果确认后恢复两图，C 的原查询规则不变。
- 第一轮清空后连续第二/第三轮重查：仍恢复最初有效状态，不被空页默认态覆盖。
- 当前结果与旧结果交错：旧 ready/failed 不消费当前 pending，不回填旧 key/旧范围。
- 同存档换公司/全局制式：综合 ranking 与 line_share 保持但数值/比例/排序取新范围，仍有效的图内 mode 保持，失效 mode 仅对应图回 structure；连续范围改变验证目标 token/scope。
- 换存档、clear/失败/close：pending 清除，两图结构态重置，禁止旧 snapshot 闪回。
- 同 data 对象修改 save_key 后重查：不能恢复旧会话状态。
- 同范围模拟可用模式变化：一图失效制式归 structure，另一图有效状态保留；1–2条/无线路/真实零/缺测边界由 B 明确状态契约后核查。
- 既有 report/share/original XLSX 的 token/data/snapshot/save-key 对话框门禁与 key 跳线路保持，选必要受影响回归，避免无关整库重跑。

## 当前证据与后续门槛

静态读取时 controller SHA256 `A27528E0C488776540E454AE79B399E45B8EE973DADC0A17AD4A9C8A2E8FD336`；D 集成测试 SHA256 `9BB0EE450404D561B3AB766B3F982876FD75309F7D70981F8752D114C4532ABA`。本阶段未修改它们。首轮 132/82/43 只证明当时限定测试，不能用于第二轮图态或视觉签收。

最终公共状态接口已稳定，范围语义/捕获时序均已确认；当前 C 独占，无 D Qt。24 项正常需求用例已准备，父释放 D 窗口后先实际运行 RED，再最小实现并做必要受影响回归，保留所有取消/identity 守卫。随后 E 真实事件矩阵/真实缓存/native截图，再由父与 Astra 复审，D 不替代最终视觉验收。A company_trend 接口已由 A/B 接入；本包不改模型或趋势业务，也不妨碍其快照发布。
