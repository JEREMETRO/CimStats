# 真实存档常驻变化验收

2026-10-02。actual process exit 0，24 个场景全部通过。1440×960 / Qt offscreen DPR 1 / QWidget.grab；不代表原生鼠标、系统 Mica 或图表负责人尚未集成的新版本验收。

使用已有单/多人存档缓存；未重解析，临时独立 INI，不改产品默认上一完整周，不制造历史基准。

多人 simulation 2013-04-10 23:59:22：有效日 04-09→04-10，对照 04-08→04-09；默认周 04-01→04-08 对照 03-25→04-01 无有效基准。单人 simulation 2013-04-18 23:59:11：有效日 04-17→04-18，对照 04-16→04-17；默认周 04-08→04-15 对照 04-01→04-08 有历史。

| 场景 | 常驻有效变化 | 无基准项 | 滚动范围 | 单位基线最大差 |
|---|---:|---:|---:|---:|
| multi-week-company | 0 | 12 | 0 | 0.0 |
| multi-week-network | 0 | 5 | 0 | 0.0 |
| multi-week-city | 0 | 6 | 0 | 0.0 |
| multi-week-company-peer | 12 | 0 | 0 | 0.0 |
| multi-week-network-peer | 12 | 0 | 41 | 0.0 |
| multi-day-company | 12 | 0 | 0 | 0.0 |
| multi-day-company-restored | 12 | 0 | 0 | 0.0 |
| multi-day-network | 5 | 0 | 0 | 0.0 |
| multi-day-network-restored | 5 | 0 | 0 | 0.0 |
| multi-day-city | 6 | 0 | 0 | 0.0 |
| multi-day-city-restored | 6 | 0 | 0 | 0.0 |
| multi-day-company-peer | 12 | 0 | 0 | 0.0 |
| multi-day-company-period | 12 | 0 | 0 | 0.0 |
| multi-day-network-peer | 12 | 0 | 41 | 0.0 |
| multi-day-network-period | 12 | 0 | 443 | 0.0 |
| single-week-company | 6 | 0 | 0 | 0.0 |
| single-week-network | 6 | 0 | 0 | 0.0 |
| single-week-city | 6 | 0 | 0 | 0.0 |
| single-day-company | 6 | 0 | 0 | 0.0 |
| single-day-company-restored | 6 | 0 | 0 | 0.0 |
| single-day-network | 6 | 0 | 0 | 0.0 |
| single-day-network-restored | 6 | 0 | 0 | 0.0 |
| single-day-city | 6 | 0 | 0 | 0.0 |
| single-day-city-restored | 6 | 0 | 0 | 0.0 |

有效项逐项检查 amount/direction/full_text，标签及所有祖先 visible，旧 HEAD ComparisonLabel 与当前标签的有效 full_text 完全相等。涨、跌、持平都常驻；无效比较隐藏、不占行，并在 tooltip 保留原因。默认周无基准截图仅证明无比较场景，不替代有效变化截图。

亲看 multi-day-company.png、multi-day-network.png、multi-day-city.png、multi-week-company-peer.png：现金流↑+57.65%、线路↑+15.25%、人口↑+0.42%、轨道较上日持平实际可见。三页有效日摘要折叠恢复后数量、显示与基线保持。

网络 companies 模式滚动范围 41px、period 模式 443px 已记录，不声称全部模式一屏无滚动。公司 period 与默认、网络 overall、城市本轮滚动范围均 0。

source hashes 与原始保存哈希见 real-comparison-visibility.json，changed_sources=[]、original_data_preserved=true、no_reparse=true；共享helper 41CDE0463AD76F31A62E5B51D7A9F72419708146ECF22ABCCFC1265DD462851B。主控告知首页三文件范围外修改，本轮 source_before_import 已包含其时点实际版本且 source freeze 未变化；不扩称首页验收。

未暂存、未提交、未打包。窗口关闭、实际进程 exit 0，主 Qt 时段已正式释放。
