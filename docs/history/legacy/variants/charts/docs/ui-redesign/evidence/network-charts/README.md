# Network chart rendering check

`network-modes.png` is an offscreen PySide6 screenshot using small synthetic fixtures from
`src/test_network_charts.py`. It checks the shared Fluent card treatment, stacked
category bars, adjacent company and period groups, original comparison slots, and
separate company pies. Its values and dates are test data, not a game save.

The network dashboard's real-save and narrow-window screenshots belong to the
page integration check after `NetworkChartPanel` is mounted.

`shared-axis-fixed.png` is another synthetic fixture rendered through the
integrated network dashboard. Both period company columns use the same 0–12
axis and show readable numeric tick labels after disabling QtCharts' automatic
label truncation.

`bar-gradients.png` is a synthetic side-by-side rendering check for a company
time column chart, a company horizontal category chart, and a network period
stacked column chart. All visible marks use the same-hue, low-contrast Fluent
gradient; the comparison period retains its lighter opacity.

`concise-legends.png` compares overall, company, and period line legends with
synthetic data. The fixture supplies the intended short card title `站点数`;
production card titles and unavailable-data reasons come from the network
descriptor, outside the renderer.

`quantity-modes.png` checks the revised data contract with synthetic values:
two companies have one full-range total trend each; a separate endpoint
`bar_result` supplies category horizontal bars and independent period ends.
The renderer reads each selected Bucket directly, including its observation
time and completeness, without averaging the historical buckets.

## Company and network Fluent data palette

`data-palette.png` is an actual offscreen PySide6 rendering at 1200×1120
logical pixels and 96 DPI from `src/qa_data_palette.py`, using synthetic
fixtures only. The chart code revision is `750e3be`. The image was opened
and checked against `references/07-windows-settings-chart.png`,
`references/04-网络数据2.png`, and `references/05-网络数据3.png`.
`data-palette-narrow.png` is the same category chart at 440×380 and
`data-palette-fullscreen.png` is its actual offscreen full-screen dialog
at 796×796, also opened and inspected.
`data-palette-period.png` is a 1200×420, 96 DPI dual-company period
rendering from the same script. Both cards use actual `NetworkChartPanel`
widgets and synthetic `NetworkChart` structures. Its left legend dots are
blue; its right legend dots, solid line and translucent dashed comparison
are green. The icon pixels for both companies and both periods are asserted
in `test_network_charts.py`. This regression checks the period descriptor's
company ID directly.

The opt-in source is `stats_tokens.DATA_CATEGORY_COLORS` for stable category
identities and `stats_tokens.DATA_COMPANY_COLORS` for company identities.
`ChartPanel.set_category_palette(tokens.DATA_CATEGORY_COLORS)` enables the
former on company cards; `NetworkChartPanel` enables it itself. The page
passes a save-wide company ID map through the existing
`set_company_palette` method. Functional icons use `tokens.ACCENT` or
`tokens.TEXT_SECONDARY`; only company identity badges take company color.
The city charts keep the original default category and company palette.
`DATA_CATEGORY_COLORS[0]` is the same bright `#1677FF` blue as the first
company trend. Orange, teal green, purple, rose and cyan distinguish the
remaining categories. Bar relief now changes HSV value slightly while
preserving the base color's opacity; pie wedges are also opaque. Only
trend areas and comparison periods use transparency. Hover tooltips include
a dot from the same series color.
`ChartPanel.set_mode_labels({'line': '趋势', 'trend-bar': '趋势',
'bar': '分布', 'pie': '比例'})` can opt a company card into semantic labels.
It changes only displayed text, keeping mode keys, saved preferences and
the city default labels intact. The network dashboard owns its external
Fluent mode selector and applies the same labels there.

`ChartPanel.set_compact_height(height: int)` and
`NetworkChartPanel.set_compact_height(height: int)` are the same public
height-budget interface. It fixes the card height and reduces internal
spacing and plot minimums without clipping axes. The accepted lower bound
is 180 logical pixels for simple series. At about 282 pixels of card width,
six categories plus a mode switch need about 230 pixels; the external
Fluent mode switch moves below the title, the legend uses two compact rows,
and a small pie keeps its total and unit while percentage details remain
available on hover. At roughly 263 pixels wide, the company line card was
checked at 200 pixels high. A larger assigned height expands the plot.
The API is opt-in, so city chart geometry stays at its existing defaults.

| Check | Reference / rule | Result | Evidence |
| --- | --- | --- | --- |
| Stacked time bars, category lines, horizontal bars, pie and legend use the same stable category colors | Network plan and the two network reference images | Pass in synthetic rendering | `data-palette.png`; palette identity tests |
| Adjacent categories differ in hue and lightness | New color requirement | Pass for the six named transport/passenger categories | HSL assertions in `test_network_charts.py`; screenshot |
| Company line, light area and legend use company ID colors | Fluent chart reference and shared palette rule | Pass in synthetic rendering | Bottom chart of `data-palette.png` |
| Bright bars and opaque pies use the same hue as their lines and legend; only trend area is light | User's latest bitmap and Fluent chart rule | Pass in reopened synthetic screenshots | `data-palette.png`; gradient and palette tests |
| Tooltip color dot follows the actual series | Same-series hover rule | Pass in tests | `test_stats_charts.py`, `test_network_charts.py` |
| Hover marker and fullscreen preserve the series palette | Same-series color rule | Pass in tests and full-screen capture | `test_stats_charts.py`, `test_network_charts.py`, `data-palette-fullscreen.png` |
| Multicategory lines remain readable | Fluent reference favors clear marks and quiet background | Pass; fill is limited to single-category lines to avoid muddy overlapping areas | Upper-right chart of `data-palette.png` |
| Visible QtCharts series styling | User requires complete Fluent appearance | Pass for these card modes: QtCharts series are transparent and `FluentChartView` paints the marks, gradients and light areas | `data-palette.png`; renderer tests |
| City charts remain unchanged | Opt-in color requirement | Pass in test; city page screenshot not repeated in this check | `test_stats_charts.py` |
| Narrow chart layout and legend wrapping | Visual acceptance | Pass at 440×380 | `data-palette-narrow.png` |
| Four network cards at 282×230, including long title and mode switch | 1440×960 one-screen card budget | Pass for chart content: legend, axis, unit and card boundary visible; card capture is synthetic | `data-palette-four-column.png`; geometry tests |
| Company cards at 200 high, including a 263-wide column | Company default one-screen card budget | Pass for chart content in synthetic capture | `data-palette-company-compact.png`, `data-palette-company-narrow.png`; geometry tests |
| Two period cards keep each legend dot on its own company color | Same-series identity rule | Pass in actual card capture and icon-pixel test | `data-palette-period.png`; `test_network_charts.py` |
| Optional semantic mode text leaves city labels and mode keys unchanged | Trend / distribution / ratio rule | Pass in component test; company page does not expose a multi-mode selector in this isolated worktree | `test_stats_charts.py` |
| Real single/multi save at 1440×960 and 1920×1080, all KPI/chart bounds, H/V scroll maximum 0, plus 2560×1440 and continuous resize | Current whole-page hard gate | Not verified in this isolated chart worktree; requires UI page integration and real-save screenshots | Main UI workstream |

## Stable order and 180 px period cards

Chart revision `78bf84f` orders every network source by the ordered
`NetworkSnapshot.filters.companies` IDs. It then orders known categories by
the shared category-token order and unknown categories lexically. The same
order feeds trend series, stacked groups, horizontal bars, legend controls,
company-share pie slices and fullscreen copies. A regression deliberately
reverses both result dictionaries and the name-map insertion order, then
also reverses the selected company order to prove the filter order wins.

`compact-period-180.png` is an actual offscreen 550×180 logical-pixel,
96-DPI capture of a synthetic one-company comparison card. Its measured
height allocation changed as follows:

| Area | Before | After |
| --- | ---: | ---: |
| Header | 28 px | 28 px |
| Separate period legend | 23 px | 0 px; moved into header |
| Duplicate 本期/环比 description | 15 px | 0 px |
| Chart view | 98 px | 140 px |
| Effective QtCharts plot area | 49.5 px | 91.5 px |

The period legend still identifies both series and the dashed comparison
line remains visible. This capture was opened and checked for complete
axis labels, unit, legend and Fluent mode controls. The integrated
real-save page must still be recaptured after the UI branch incorporates
this revision.

Full test suite on that revision: 291 passed, one upstream Qt deprecation warning.

## Six-category period card at 400×180

`compact-period-categories-180.png` is an offscreen 400×180 logical-pixel
capture of a synthetic one-company period category card, with the same
external Fluent mode selector and hidden title icon used by the page. It was
opened and checked for all six category controls, both period labels, the
numeric axis, unit, dates and stacked marks. The six category controls share
one row, and the period position labels fit in the header. If the card narrows,
the legend wraps and the period labels return to their own row. These widgets
are Fluent controls; QtCharts supplies only transparent geometry beneath the
custom Fluent painter.

| Area | Before | After |
| --- | ---: | ---: |
| Category legend | 38 px, two rows | 18 px, one row |
| Separate period position row | 15 px | 0 px; moved into header |
| Chart view | 90 px | 120 px |
| Effective QtCharts plot area | 41.5 px | 71.5 px |

These measurements come from `src/qa_network_compact_geometry.py`. The real
dual-company page capture still needs repeating after UI integration. The
full local suite passed with 292 tests and one upstream Qt deprecation warning.
