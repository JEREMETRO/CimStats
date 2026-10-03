# 第二轮证据目录

当前完成A限定纯核验：42个独立边界/状态检查，三缓存25范围325指标/600聚合点/672公司小时点一致，汇总actualexit0，见`A-pure-review.json`。第二轮实际局部事件已运行，发现返回Enter/Return缺口；当前未通过，尚无原生截图/导出及视觉签收。脚本与取证矩阵见[独立验收计划](../LATEST-INFO-REV2-QA-PLAN-2026-10-01.md)。

后续真实缓存与fixture分别标注，历史latest-info-evidence不覆盖；记录稳定源hash、实际事件/期望/图态、OS与进程DPR、尺寸及实际exitcode。功能结果与视觉签收分别记录。

## 脚本准备结果

`raw-oracles.json`为标准库独立读取原始CSV/manifest生成的期望：三缓存25范围、672公司小时点；全CSV/manifest/原save/probe全文hash前后不变。另有六制式1000总量/0.5%小类、17条/7条Other/5257余量、零尾、部分缺测与空态5组明确输入。缺测尾项按实际剩余集合计数，已知量/未知key/complete分别记录，不把未知值补零或画100%。这些是期望生成结果，不是当前产品通过结果。

三份准备脚本：

- [原始数据期望](../qa_latest_info_rev2_oracles.py)：独立排序、分母、百分比、Other集合和真实公司小时点；无产品或Qt导入。
- [局部事件验收](../qa_latest_info_rev2_events.py)：准备真实QTest局部鼠标/键盘、独立扇区坐标、两图三态/真实key及总数可见检查。
- [真实整窗验收](../qa_latest_info_rev2_native.py)：准备临时INI、自有HWND PrintWindow、正确缩放标签、真数据/导出与异步长值/同会话范围fixture。

独立语法/import/默认检查actualexit0，Qt及产品模块均未导入，见`.superpowers/sdd/2026-10-01-latest-info/task-E-rev2-preparation.json`。events/native默认只报告准备状态；本轮没有使用--run，没有QApplication、窗口、事件或新PNG/XLSX。

最终执行前由父移交独占Qt及稳定源码，生成source-lock后补绑定四业务组图标、四独立极值卡max蓝/min紫角色条与字段关联；不锁旧CORE/aux或强制共享行标题。总数必须实际可见、有单位、全文可读，隐藏标签不得计为无裁切。运行证据保存于新的events/native子目录，禁止覆盖历史证据。所有视觉结论仍需真实整窗与父/Astra签收。

## 首次实际Qt结果（待修复）

`final-source-lock.json`冻结140源、68保护文件及125主源；`final-raw-oracles.json`重新生成三缓存25范围/672小时点期望。`events-e01/events.json`在真实秋山18号返回Enter动作失败，前17动作及原exit1保留。`return-key-diagnostic/matrix.json`独立12项证明：两图ranking/share的Return/Enter均不发clicked（8失败），Space正常（4通过），每个失败的鼠标对照也正常；焦点确实获得。

限定发现为E-B-REV2-01 P2，详见E的`task-E-rev2-findings.md`。两次Qt已退出，source/protected/primary hash未变，26候选SHA匹配，见`interim-integrity.json`。父要求先交B短修复槽，本轮尚未启动native或限定回归。后续新源码锁/新目录复验，不能把当前RED与作者103或旧native证据拼成最终通过。
