# E 第二轮实际事件发现

> 历史验证记录：下文保留早期 e01–e04 的失败证据。键盘返回、分享冗余、底部裁切和长数值排版已修复并完成后续验证；当前交付状态和验证范围以 `docs/ui-redesign/LATEST-INFO-FINAL-2026-10-02.md` 为准。

## E-B-REV2-01 — P2：返回图标不响应Enter/Return

产品源只读。首次真实秋山局部事件`events-e01`完成前17个动作，18号动作失败：rankingReturn可见、启用且已获得焦点，Key_Return(16777220)后仍为公交ranking，没有返回structure。原exit1及前后两图状态/坐标/信号/输入身份保留。

随后用实际LatestInfoPage/Controller、明确17线路输入，通过真实鼠标进入两图的ranking/line_share，再直接对已获焦点的实际TransparentToolButton投递QTest.keyClick；没有tooltip事件、show_*或被测命中函数。12项定向复验actualexit1：

|图|视图|Return|Enter|Space|
|---|---|---|---|---|
|客流|ranking|失败，clicked=0|失败，clicked=0|通过，clicked=1|
|客流|line_share|失败，clicked=0|失败，clicked=0|通过，clicked=1|
|班次|ranking|失败，clicked=0|失败，clicked=0|通过，clicked=1|
|班次|line_share|失败，clicked=0|失败，clicked=0|通过，clicked=1|

8个失败均已确认focus/visible/enabled=true；每个失败后的鼠标返回对照均正确。Space四项保持全页scope及另一图不变。问题是当前ToolButton没有Enter触发处理，不能归因为QA焦点失效，也不能删Enter断言或直接调用show_structure代替。

源码定位：`frontend/latest_info_charts.py:82`的icon_button构造TransparentToolButton；`:491`建立rankingReturn/departureReturn，`:556`仅将clicked连到show_structure；当前返回控件没有额外Enter/Return处理。需B在当前返回控件上补齐两键与鼠标/Space相同的单次返回语义，保留焦点/tooltip/accessibleName及两图独立性。

验证的charts SHA256为`6638f7ef5cc49ec389e95b45bcda1d95b3931fc550ca6ce37fb0157b29c9cf82`，page为`7a744950b475acdc9135ae158d3f329feaff7e7debe4425262a49ab3ffbe1599`。完整140源冻结、68保护文件（缓存含原XLSX/CSV、原save/probe及主index）、125主源、26候选路径均核对未变。

证据：

- `docs/ui-redesign/latest-info-rev2-evidence/events-e01/events.json`：真实秋山第18事件及原exit1。
- `.../return-key-diagnostic/matrix.json`：12项实际局部Qt事件、focus/信号/状态及鼠标对照。
- `.superpowers/sdd/2026-10-01-latest-info/task-E-rev2-return-key-check.py/.log`：最小复验及actualexit1。
- `.../interim-integrity.json`：产品/保护文件/主源不变、26候选SHA匹配。

两次Qt进程均已返回，worker停止及窗口清理成功。原生MainWindow、PNG/XLSX/真实复制与最终限定回归尚未启动；全矩阵未完成，不能签收。按照父最新指示交回槽给B短修复；后续使用新源锁和新证据子目录复验，不覆盖本次RED。

## E-B-REV2-01复验：已关闭

source-lock-after-keyboard.json：仅B授权charts及charts test改变，26候选路径匹配。return-key-diagnostic-e02实际12/12通过actualexit0，每项clicked=1；原RED不覆盖。events-e03真实三缓存与五必要边界共458局部事件actualexit0，worker/源/保护检查通过。e02的排行容器目标错误与修正另见driver-adjustments，不算产品缺口。

## E-B-REV2-02 — P2：四独立卡同视觉行字段基线不一致

首次完成DPR校准后的真实多人MainWindow native-multi-dpr1.0-e04，DWM1440×960、实际Qt window/screen DPR1、OS192、进程factor1，背景自有HWND PrintWindow。13指标、四图标、16字段及单位的字体/宽度/语义检查先执行；最后按highlight_grid实际视觉row=0分组的客流字段中心为496.5、496.5、491.5、491.5，同一行差5px超过原约定2px。不是响应式分行误判。max/min客流卡突出第一行，班次卡突出第二行，各自QGridLayout的行高因20px/13px字形不同，导致相同字段基线错开。

原actualexit1及trace保留native.json，实际整窗real-default.png已生成（1440×960，非桌面截图）。当前断言未删除、未改产品；后续native图态/导出/容量fixture尚未执行，不能把截图存在称为验收通过。workers_stopped/source_unchanged/protected_unchanged均true。可由B统一每字段行高/基线并保留独立卡/对应极值字重；最终视觉是否接受由根/Astra审阅真实PNG。

证据：docs/ui-redesign/latest-info-rev2-evidence/native-multi-dpr1.0-e04/native.json及real-default.png。

## E-COPY-REV2-03 — 分享仍有未要求的重复说明

真实多人build_share_summary的只读输出share-summary.txt确认：公司/制式之后仍附长“指标范围”，13指标逐项附重复范围，末尾无条件“缺测显示为—，不按零值统计。”。用户要求未明确请求的说明禁止添加。产品源frontend/latest_info_exports.py:51/55/65；已有报告及必要tooltip的原始口径/source字段按合同保留，不应为前端删减而删除。clipboard_modified=false。首页latestScope长说明与ranking计数现已隐藏，本轮不误报其为可见说明。

### 根/Astra视觉判定后的修正（不覆盖e04原失败）

根与Astra已实际看e04整窗：5px测量是QLabel widget中心，不是文字baseline；按用户四独立卡最新合同，仅为局部角色布局观察，不单独阻塞。E已将此项改为记录实际grid视觉行和center差，保留每卡13+16实际文字/单位/数值宽高、字段/value/unit非重叠及卡内/行间边界检查。不能再称5px为已测文字基线缺陷。

真实待修是整页底部三卡下边框未完整。e04确有DWM1440×960，native/Qt client1436×900，DPR1、OS192；viewport/board/scroll range/card bottom数值未在e04保存，不能补造“9px实测”。约9px为根/Astra截图观察。已有数据写e04-existing-layout-observations.json；新驱动将在upper断言前及三态各保存viewport/board/scroll/card rectangle。保持无Qt，待B原生预算修复与D分享删减及父再转槽。
