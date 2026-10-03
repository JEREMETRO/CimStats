# 分享摘要精简候选（仅准备，2026-10-02）

状态更新：根随后授予限定写入许可，候选已应用并冻结；同组15项纯测试全部通过、actualexit0、Qt未加载。最终证据为`application-final.json`及`applied-BEFORE-AFTER.md`。下文保留最初准备阶段记录，不代表当前仍待应用。

E 当前唯一 Qt 验收、产品及测试全冻结。本目录只含 D 自有候选/对照/静态证据；未应用补丁，未写产品或测试，未执行 pytest/Qt，未输出工作簿，未修改缓存或主树/index。

## 最小候选

`share-summary.candidate.patch` 只改 `build_share_summary`：

- 存档、模拟时刻各一次，城市、人口保留；公司（含稳定ID）和制式合并为一个“范围”行，删分享里的冗长 scope_text 说明。
- 13项标题、值与单位不变，移除每项重复 scope/reason 段落。
- 公共交通分担率保留“全市”短标签；选具体制式时换乘系数保留“全部制式”短标签；综合范围不重复同范围标签。
- 已知数值但完整性不足时仍保留“部分观测”短标记。缺测仍为 `—`，真实0及Decimal原精度使用原 `_display`；不改数值/单位/缺测规则。
- 四极值原有明细循环完全不变：真实线路名、制式、稳定公司身份、客流与班次；总班次保留。
- 删除固定尾注“缺测显示为—，不按零值统计。”。六sheet XLSX的范围、观测状态、缺测理由、说明及PNG/controller/按钮门禁全部不变。

候选保留部分观测标记，是观测状态的短标签；详细缺测/口径原因仍可在原XLSX查看。本目录实际 before/after 可供父判定最终文字边界，不直接询问用户。

## 实际前后文案

`BEFORE-AFTER.md`、`before.txt`、`after.txt` 来自当前函数与候选函数实际执行现有纯导出数据fixture。示例556→432字符，27→24行；不是原生/真实存档验收截图或新的测试通过证据。对照保留13项和四极值，缺测与零规则未改。

准备脚本通过 NoQt import guard 阻止 PySide6/qfluentwidgets/stats_exports，未运行任何测试函数/pytest。仅调用现有 fixture 构造与两个摘要函数，写本目录对照；静态 compile候选。`candidate-metadata.json` 记录除分享函数外所有7个函数 AST相同、极值明细循环 AST相同、冻结源与候选SHA256。

## 必要纯测试预案（尚未应用、尚未执行）

`share-tests.candidate.patch` 仅适配现有摘要测试，不删除其他14项；仍保持当前15个参数化执行用例。

1. 父在 E 结束后明确给源码写入许可，再只应用测试候选；运行 `pytest --noconftest -q src/test_latest_info_exports.py`，确认正常摘要需求 RED。新增断言在旧实现中缺“全部制式”短标签、仍存在理由/尾注，预计失败；尚未运行，不冒称1 failed/14 passed。
2. 只应用分享函数候选，再用相同15项纯测试 GREEN。当前测试改写保留城市/存档/时刻/稳定ID/制式、缺测、四极值，补13标题/单位、重复范围/理由/尾注去除、真实0、Decimal120.250001完整精度、部分观测、综合范围不重复“全部制式”。
3. 原其余14项继续验证六sheet数值与原因、分类真实0/缺测、提醒两窗口、空范围、非有限值、公式注入及无Qt导入。新候选未修改 XLSX 函数；不跑 Qt/整窗/整库，也不重新解析存档。

解释器按既有 `C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe -X utf8`，禁pytest插件自动加载。当前没有写入许可，不应用；若父不接受短标签细节，仅调整本目录候选，不突破E源锁。
