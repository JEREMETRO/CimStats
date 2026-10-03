# E 第二轮 A 独立纯核验 — 2026-10-02

限定结论：**未发现必要产品修复项**。42个独立边界/状态检查通过；三缓存25范围的325指标、600原聚合点、672逐公司小时点核对一致。最终汇总actualexit0。此为纯源/模型/只读数据结论，未Qt，不代表B/D接线或视觉通过。

| 范围 | E独立证据 |
|---|---|
| 文件头不是固定offset | 0/3/32玩家、共享类型引用/对象引用/null声明均读取相同名称；地图字段位置随结构变化 |
| 有界拒错 | 一次rb读取16384；有效前缀所有截断长度、错版本/根类型/流标记、超玩家/字符串、越界类型/对象引用、坏UTF16/环境、扫描诱饵均拒绝 |
| 城市显示/原始追溯 | 核验Eixeia/Budapest/Ljubljana/Szczecin/Reeve Delta/North City及通用内部标识；内在数字与未核验地区/版本不乱删；raw reference/name/ID保留 |
| 旧缓存不猜城市 | 即使旧无来源文本看似真实城市也拒绝；可靠原始来源后备可用；真实头优先于filename |
| 窄共享diff | report_model移去授权5字段后AST与HEAD相等；extractor移去授权地图块/字段后其余AST与HEAD相等；未导入extractor/CLR |
| 逐公司趋势 | 三个真实ID同名fixture各自缺口/缺类别/真实0/未来新类别；其他公司的缺测不抹去本公司；原聚合共同缺口保持；单公司/具体mode/无时钟/无数据/无法解析同名身份均核验 |
| 原13公式 | 新独立算式输入全部13值，以及负利润/缺收入/零分母；三真实缓存13值＋单位/范围/reason/complete均与E历史独立基线相等 |
| 真实名称/数据 | 秋山→Eixeia、望春→Ljubljana、双人→Szczecin；原CSV按真实公司唯一原名映射玩家ID逐小时直接复算，非调用被测_quantity_trend生成期望 |
| 保护 | 全部涉及CSV/manifest/三原save/probe全文SHA256、A及纯依赖源码SHA前后相等；未重parse/未Qt/未pytest/未触及B活动源 |

执行仅标准库独立脚本`task-E-rev2-A-review.py`，没有重跑作者80/167项或49头读取。真实读回和边界定向结果合并，不声称单次45项pytest全绿。

证据：`task-E-rev2-A-review-final.json`（最终汇总及源/保护hash）、`task-E-rev2-A-review-real.json`（25范围逐点）、`task-E-rev2-A-review-edges.json`（42检查）、`task-E-rev2-A-review-edges.log`（实际exit0）。最终JSON同步至新rev2证据目录`A-pure-review.json`。

原失败保留：首轮三个探针问题分别为字节replace误改tick而非对象引用、legacy历史只给唯一公司原名而期望漏映射ID；修正后真实325/600/672已通过。追加算式fixture曾误给全市数据“同名公司”身份导致None，正确无公司输入定向通过。均为E输入/采样问题，无产品改动；原exit1 JSON/log未删除。最终源/保护一致后再做纯汇总。

REV2计划已按父核验的直接用户授权更新：环图＋完整列表可合并替代独立堆积条，环心总数/单位、绝对数/百分比及三态/扇区列表钻取仍核验；返回排行用“返回结构图”。旧28项GREEN不视为合并后结果。Qt仍归B，E等待后续稳定接口与正式窗口转交。
