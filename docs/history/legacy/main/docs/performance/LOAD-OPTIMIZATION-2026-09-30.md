# 存档加载性能与真实进度验证（2026-09-30）

## 修改与结论

`load_root` 将 Python bytes→pythonnet逐字节封送改为 `.NET File.ReadAllBytes` 返回托管byte[]，再构造 MemoryStream，保留完整反序列化、内存流隔离和所有导出。未增加线程池/多进程并行，运行时GC/线程池线程不代表开启多核存档解析。固定源码补测中单人耗时减少40.3%，双人44.5%；真实阶段/计数进度已取代时间/RSS预测。

## 独立审计更正

此前分析器用 `k.startswith('frontend/')` 筛选Windows反斜杠路径，实际取得空集合，使“全部相同frontend SHA”断言失效。规范化原12条记录后，19个前端文件中 stats_controls.py/statistics_page.py 存在两套SHA：单人旧2A/1B、新1A/2B，双人旧/新各1A/2B。旧39.8%/45.0%中位减少仍为观测值，**不能作为严格同UI控制结果**。旧原始数据完整保留；[benchmark-summary.json](evidence/benchmark-summary.json) 已明确controlled_source_comparison=false、matching_frontend_source_hashes=null及两组真实清单。

新分析器规范Windows路径，严格校验完整固定清单，拒绝空集合、缺失记录/文件、前端哈希变化与运行中源码变化。7项轻量回归通过。默认旧数据分析拒绝混UI；只有显式 `--allow-mixed-legacy` 才允许生成带无效控制标记的历史摘要。

## 固定完整源码三轮配对补测

从 Git `36373d46f147d0e88b6e913970b0314b71b75b89` 导出项目内部忽略的snapshot，包含固定frontend/src、VERSION、目录CSV等。使用同一修正过的benchmark/profiler，旧variant从该版本提取器的原样副本仅替换一处MemoryStream参数为PAYLOAD.read_bytes()，通过同一诊断wrapper执行；新variant直接执行原样提取器。没有复用旧cac727a提取逻辑或在途城市UI。

记录的99个实际执行Python文件（19个frontend）在每次前后都与对应固定清单完全一致；两个variant仅src/extract_runtime_data.py该参数表达式不同。具体清单、harness哈希、runtime/save SHA与实际执行顺序见 [source-manifest.json](evidence/fixed-source-20260930/source-manifest.json)、[run-order.json](evidence/fixed-source-20260930/run-order.json)。每档顺序旧/新、新/旧、旧/新，合计12次，其他会话避开真实解析窗口，未修改主项目UI。

Windows同工作站，Python3.12.10，16逻辑CPU/32GiB，Qt offscreen1920×1080。每次新GUI及后端进程、新job/payload/导出、隔离DLL副本，无缓存解析结果复用；OS页缓存暖且未受控，不称物理磁盘冷启动。计时从start_parse前至当前存档session及双snapshot就绪、query workers/timer结束、遮罩隐藏，并实际grab统计页首帧。原生EXE/真实显示器验收尚由主控安排。

| 样本 | 旧三次 / 秒 | 新三次 / 秒 | 中位数变化 | 耗时减少 |
| --- | --- | --- | --- | --- |
| 单人 望春市6 | 22.453、22.902、22.866 | 13.255、13.656、13.783 | 22.866 → 13.656 | 40.3% |
| 双人 quicksave | 28.498、29.010、28.645 | 15.893、15.577、15.986 | 28.645 → 15.893 | 44.5% |

| 分段中位 / 秒 | 单人旧 → 新 | 双人旧 → 新 |
| --- | --- | --- |
| 运行时导入 | 0.731 → 0.740 | 0.732 → 0.741 |
| 解压及落盘 | 0.404 → 0.403 | 0.586 → 0.572 |
| MemoryStream构造/旧封送 | 9.009 → 0.011 | 12.670 → 0.012 |
| load_root整体 | 10.145 → 1.035 | 14.065 → 1.360 |
| 线路提取及预扫描 | 3.869 → 3.627 | 5.229 → 4.932 |
| 历史提取 | 0.379 → 0.350 | 0.337 → 0.335 |
| CSV写入合计 | 0.411 → 0.399 | 0.374 → 0.374 |
| 线路工作簿 | 1.914 → 1.898 | 2.163 → 2.332 |
| 公司工作簿 | 0.946 → 0.946 | 0.907 → 0.977 |
| load_session | 0.425 → 0.439 | 0.420 → 0.427 |
| HistoryStore | 0.149 → 0.149 | 0.121 → 0.119 |

嵌套时间不可重复相加（load_root包含MemoryStream；UI session包含HistoryStore）。树峰值RSS三次中位：单人571.7→528.6MiB（减少7.5%）；双人675.5→627.5MiB（减少7.1%）；每次子进程峰值线程数均19，没有新增并行解析。100ms采样可能漏掉短峰值；系统内存受其他应用影响，未归因给本优化。全部数据见 [fixed-benchmark-summary.json](evidence/fixed-benchmark-summary.json)。

## 正确性与验证

- 6对真实存档（两档各3轮）全部15类CSV逐字节SHA一致，2本工作簿所有工作表/单元格/公式一致，完整normalized session一致。仅排除job/outputs/manifest/save_key/managed_root路径或运行标识，XLSX ZIP时间不要求字节相同。见 [fixed-correctness-comparison.json](evidence/fixed-correctness-comparison.json)。
- 根存档SHA保持9D6F8C3C…A8496 / 79A6D641…B360C；原tracked probe仍9AB2ECA2…DD70E，未覆盖、还原或提交。每次读snapshot副本、before/after哈希不变。
- 产品提交8f7984f后全src363 passed；本次仅性能记录/脚本/文档修正，分析器7项定向回归通过，没有重跑在途城市全src。真实取消约0.031秒停止且无100/completed/manifest；坏容器正常失败。产品数据/KPI/比值/总组语义不变。
- 独立QA另测13.761/15.809秒，CSV/session一致，但未混入本控制三轮。原生缩放、最终EXE及动画独立验收由主控协调。

## 重现与隔离

`fixed_source_benchmark.py`从固定提交建立内部snapshot，严格使用全新输出目录；`--resume`只允许修补无成功记录的初始化失败，不能覆盖已完成的实验。已完成记录/大缓存均保留。重现需在干净副本或换新证据目录运行，再执行 `py -3 docs/performance/analyze_benchmarks.py --fixed` 和 `py -3 docs/performance/compare_results.py --fixed`。运行前协调串行真实负载窗口。

小型原始result/backend-stages、完整manifest/order和分析摘要纳入Git；DLL、payload、CSV/XLSX、session及snapshot缓存隔离ignore。GUI打包spec排除docs/performance研发目录，避免多GB测试缓存进入EXE。没有新增依赖或改变系统设置。

## 真实阶段和计数进度

按用户最终指令，产品已经移除耗时/RSS预测和大小范围开关。`ParseProgressEstimator` 保留兼容名字，内部仅消费 `CIM2_PROGRESS` 的阶段完成与整数 done/total。0%始终是合法的等待开始状态，不显示未知。固定阶段预算为：payload 0–8、反序列化8–20、线路20–50、历史50–65、CSV65–70、线路工作簿70–82、公司工作簿82–90、校验90–96、图表准备96–99。百分比表示阶段完成度，不能解释为剩余耗时或所有对象的统一百分比。

线路使用实际已处理线路/总线路；历史根据循环缓冲区有效槽位预先计数，提取每组后报告真实累计行数，最终断言与输出一致；CSV按关闭后的15个文件计数。线路工作簿单位是已完成工作表+最终保存（线路数+3），公司工作簿为4张表+保存，校验在每本工作簿完整扫描并关闭后上报1/2、2/2。已知空线路用阶段完成事件，不伪造分母。同步解压、原生反序列化和最终保存只上报调用前后实际里程碑；调用期间进度保持不动。100ms节流仅减少日志数量，不按时间增加完成量。失败、取消、坏计数和晚到任务不完成；只有公司/网络双snapshot、查询任务结束、图表实际绘制、当前任务仍匹配的 ready 检查通过，才将模型完成值设为100%并收起遮罩（失败/取消共用隐藏路径不设置100%）。

本地LocalLow目录共44份存档，选取7份覆盖6.4–25.7MB及零线路/不同历史规模；加项目单人/双人，共9份重新用真实事件串行解析。每份计数最终与解析诊断一致，15类CSV逐字节、2工作簿所有工作表/单元格/公式、完整 normalized session 与原记录完全一致；事件单调、完成前≤99%，最终遮罩隐藏。7份外部样本源哈希及项目存档/probe均保持不变。验证见 [actual-progress-validation.json](evidence/actual-progress-validation.json)，重现 `py -3 docs/performance/validate_actual_progress.py`。

| 只读存档 | 线路数 | 历史行数 |
| --- | ---: | ---: |
| 望春市6.save | 59 | 58098 |
| quicksave.76561198362520556-76561198845688243.save | 73 | 51746 |
| 广通市1.save | 18 | 102912 |
| 石胜市3.save | 35 | 67590 |
| 和政市8K2New1.save | 76 | 107520 |
| 秋山市n6.save | 75 | 111360 |
| 逸景市.save | 0 | 74 |
| 布江市.save | 0 | 75 |
| 望春市_test.save | 63 | 83717 |

真实计数回测耗时仅作记录，不混入前述同UI源码的三轮性能比较；期间全量回归也执行过，不用于速度归因。此前的耗时拟合保留为历史研究证据，`fit_progress.py`不再写产品校准文件。外部21.3MB零线路存档只需约4.5秒，20.4MB/75线路存档约16秒，支持放弃文件大小预测的决定。

同GUI重复打开（每组n=1、仍新后端/job）：单人25.431→13.834秒，双人30.447→16.385秒，遮罩均已隐藏；只报告观测值，不声称统计稳定性。最终新EXE尚未打包实测；打包spec已纳入parse_events.py，同一实际事件协议不按frozen模式禁用，最终发布/原生验收由主控安排。主GUI spec排除 docs/performance 研发证据目录，避免将多GB隔离DLL/payload/job缓存打入EXE。
