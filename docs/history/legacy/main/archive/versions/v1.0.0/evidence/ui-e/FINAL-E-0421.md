# Final E review — fixed integration candidate

Commit: `0421ba54d2bbc04aff6c19c925b80789aacf9b35`. Review tree stayed detached; no production source files were modified. All measurements use the requested client-area logical pixels, not the Windows title-bar frame. DPR is Qt `QT_SCALE_FACTOR`; the native Windows GUI check is performed separately by Root.

## Result

- **Statistics page size/DPR matrix:** 20 cases across 1920×1080, 1600×900, 1366×768, 1024×768, and 920×680 at Qt DPR 1.0, 1.25, 1.5, and 2.0. All requested client sizes were achieved. Every case recorded 0 px horizontal overflow and 0 widget-bound issues.
- **Runtime fonts:** all visible widget classes, menus/actions, chart titles/legends, and chart-axis labels/titles returned `Microsoft YaHei UI` from `QFontInfo`; zero mismatches. This covers the empty/loaded old pages and all three statistics charts in each of the four DPR runs. Windows title-bar text is excluded.
- **Retained pages:** 60 states (empty overview, loaded overview and loaded line page × five sizes × four DPRs). All 20 loaded line-page narrow/wide cases report all nine fact cards fully visible when scrolled to each card. Overview metric-to-chart gap measured 16 px in all states. Outer page overflow was 0 px. At narrow widths, the table keeps its own horizontal scrolling for remaining columns.
- **Fluent controls:** company/mode selectors and line selectors are `qfluentwidgets.ComboBox`; search is `LineEdit`; line table is `TableWidget`; column/field buttons are `DropDownPushButton`; schedule tabs are `TabWidget`. Current run recorded these classes consistently at each size and DPR.
- **Menus:** column and fact-field popups were opened and visually inspected at 920×680 at all DPRs; all actions report the target font. Both menus fit the visible capture, and action labels/check states are present.
- **Breakpoint/continuous resizing:** 28 samples across breakpoints and 20 px down/up resizing; max horizontal overflow 0 px and max widget-bound issues 0. Window minimum client width is 920 logical px; narrower requests are clamped to 920.
- **Targeted state checks:** long duplicate names wrap without collision; the empty-state alert list leaves no text remnant; group/type/trip bars expose 6/5/5 categories; city share exports public transport 17.03%, walking 80.12%, and private car 2.85%.

## Final-commit exports

| Artifact | Result | Size | SHA-256 |
|---|---|---:|---|
| `dashboard-full.png` | Full board PNG, 810×5107 px | 352,494 bytes | `e230d02ff9b4b82b0a2bc4d708bb30b0b7a7519a3dbc72bf6136bd554cfba878` |
| `dashboard.xlsx` | Workbook: filter + company/service/passenger/city sheets | 142,840 bytes | `0e86e43f2e3e4c1c184df79bd427eed0f8c1cf8a831aabdea2a9f50536381bd5` |

XLSX sheet row counts (including headers): 筛选条件 4, 公司数据看板 865, 服务规模看板 353, 客流数据看板 265, 城市数据看板 497.

## Evidence

- Statistics 20-case matrix, screenshots and per-image SHA-256: `stats-100/evidence.json`, `stats-125/evidence.json`, `stats-150/evidence.json`, `stats-200/evidence.json` and adjacent PNGs.
- Empty/loaded overview and line-page top/bottom screenshots, runtime widget/chart/menu fonts, control class names, 16 px gap, and per-card reachability: `legacy-100/evidence.json`, `legacy-125/evidence.json`, `legacy-150/evidence.json`, `legacy-200/evidence.json` and adjacent PNGs.
- Chart axes/legend and stats-menu `QFontInfo` across all 4 DPRs, plus final-hash export metadata: `exports/deep-evidence.json`, `font-125/deep-evidence.json`, `font-150/deep-evidence.json`, `font-200/deep-evidence.json`.
- Supplemental duplicate-name, checkable-menu, category-count and empty-state evidence: `supplemental/supplemental-evidence.json` and adjacent screenshots.
- Breakpoints/continuous resize measurements: `resize/resize-evidence.json`.

Visual review used offscreen Qt screenshots at 920×680 (100% and 200%) for the statistics page and old line page, plus the empty home and menu popups. Runtime font-family checks are direct `QFontInfo` reads, not visual estimates. Root separately reports that native Windows checks covered the home, line and statistics pages, field menu, and full PNG; its full 167-case run and 18 old-page cases passed.
