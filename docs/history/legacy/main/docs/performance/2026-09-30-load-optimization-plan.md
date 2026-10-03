# CIM2 SaveStats loading performance plan

Goal: reduce real-save open-to-interactive latency, preserving all data and exports.
Execution: this authorized performance session implements and verifies sequentially; UI and independent QA remain separate owners.

## Baseline and ownership

- Main checkout HEAD at start: d7ef6b290c802c84607c52abdc20e66259510122. No applicable AGENTS.md found in project/parents.
- UI owns frontend/desktop_app.py, pages, controls and loading_overlay.py. Performance owns src parser changes, docs/performance and (by UI handoff) parse_progress.py and its tests. Worker changes require coordinated patch.
- data worktree contains independent QA documentation and is reserved; do not reset. charts occupancy must be confirmed before reuse. Work in main only in agreed paths until confirmed.
- Existing tracked probe modification SHA256: 9AB2ECA20D376E5DDCA7733E674890917B6A4F5A2A28C92D8238D7BC3E7DD70E. Preserve it; copy runtime dependencies into temporary directories before running.

## Measurement contract

- Serial benchmarks only, coordinate heavy-workload window with UI/QA.
- Real single and multiplayer saves, immutable SHA256 before/after; Saturday held out where possible.
- Fresh process for each measured run, fresh jobs/payload/export directory, isolated runtime DLL copies. Distinguish process/runtime cold from filesystem cache cold: do not flush OS cache or label it cold without evidence. Measure repeated same-process opens separately if warranted.
- End-to-end starts immediately before MainWindow.start_parse, includes parser process startup, decompression, .NET graph deserialization, extraction, CSV writes, workbook generation/validation, Python query model, statistics aggregate and visible chart drawing.
- Completion requires matching save_path, current company/network snapshots, no query workers/timer, and one forced QWidget render. Parser 100 event is recorded separately and does not prove interactive readiness.
- Sample parent/child RSS, CPU seconds, thread counts and system used/available memory every 100ms. Keep raw event/sample records, source hashes, environment and medians/range. Profiling overhead runs are labelled diagnostic and excluded from comparisons.

## Tasks

- [x] Add isolated serial benchmark harness and backend segmented profiler. Read baseline hot spots before implementing.
- [x] Hypothesis from evidence: minimize repeated reflection, duplicate graph traversal, or per-element Python/.NET calls before considering concurrency. No raw graph parallelism without thread-safety evidence; include IPC costs if testing processes.
- [x] Write failing regression tests for chosen optimization, then minimal implementation. Verify full history identity/total/live slots and byte-identical CSV output on both real saves; compare normalized snapshots and workbook contents, ignoring ZIP timestamps.
- [x] Compare baseline and optimized real end-to-end runs under identical settings (initial target 3 runs each/save; stop expanding if variance and conclusion are stable). Preserve unsuccessful experiments only as documented evidence, revert only own changes.
- [x] User superseded elapsed/RSS prediction: implement actual phase/count events for all sizes/runtime modes, keep numeric 0–99 until ready; validate nine immutable real saves including empty-line cases.
- [x] Verify cancel/failure/stale-result/export paths, commit own paths only after checking staging, report evidence and limitations to controller/UI/QA.

## Correctness boundaries

Use the existing NETWORK-INDEPENDENT-QA.md, NETWORK-ONE-SCREEN-INDEPENDENT.md and independent data-worktree QA checklist. Company total groups stay separate from categories. Multiplayer overall is 5 KPI/7 charts without joint coverage. Single-company coverage uses Any total; last-day KPI, endpoint stocks and transfer ratio of summed numerator/denominator retain their semantics. No earlier readiness event or hidden wait is used to claim speedup.

## Investigation ledger

- UI released the serial benchmark window and main/src ownership; reserved data worktree stays untouched. Main checkout used because charts owner is unknown. UI stable commit cac727a arrived during baseline sampling; parser paths unchanged.
- Diagnostic single cProfile: load_root 10.286s, field 120127 calls/3.097s, history_rows .435s, CSV ~.984s. Diagnostic overhead is excluded from comparison.
- First multiplayer non-cProfile: load_root 14.491s, MemoryStream(Python bytes) constructor 13.123s, prepare_payload .568s, history_rows .330s. Native serializer is therefore not the principal cost; pythonnet byte[] conversion is.
- Hypothesis: System.IO.File.ReadAllBytes returns a managed byte[] directly, avoiding per-byte Python/.NET conversion while preserving MemoryStream semantics and closing the file before deserialization. No thread pool needed; graph parser is kept serial.
- RED: py -3 -m pytest -q src/test_payload_loading.py -> 3 failed on old implementation, each rejects Python bytes crossing into MemoryStream. Tests also cover missing/explicit refresh and deserializer error propagation.
- Ruling: keep eager workbooks and all CSVs for this change. They are visible export guarantees and not the measured main bottleneck. No deferred/incomplete readiness semantics.

- Original 39.8%/45.0% are uncontrolled observations: independent QA exposed Windows path filtering/empty frontend manifest. Fixed36373d4 snapshot12 runs,99 Python/19frontend files before/after checked, one buffer argument difference: single40.3%, multiplayer44.5% elapsed reduction; no new parallel parser. CSV/workbook/session exact equality.
- Actual progress RED/GREEN count and input validation; nine real saves all actual counters/outputs/read-only hashes PASS. Archived elapsed model excluded from product/spec.
- UI owner resolved obsolete fixed-height assertion in87bd452. Final full src suite:363 passed/81.24s, one existing QFluent deprecation warning; targeted performance/progress/UI32 passed. Real cancel/failure controls repeated PASS. Runtime/spec syntax and release docs exclusion verified.

- Audit correction: normalize Windows hash paths; reject empty/missing records/files, changed UI and source mutation (7 regressions PASS). Mixed legacy explicitly disqualified and retained.
- Fixed full application snapshot/internal isolated runtime, AB/BA/AB order; 12 runs completed, all6 paired CSV/XLSX/session equality PASS. No city UI/parser changes included.
