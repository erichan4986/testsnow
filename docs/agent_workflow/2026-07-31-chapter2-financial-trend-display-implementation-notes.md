# Chapter 2 Financial Trend Display Implementation Notes

## Result

- Verdict: PASS
- Formal report rerun allowed: yes
- Formal report rerun performed in this task: no
- Fast-test sample report rerun: yes
- Network/LLM/browser use: none

## Modified Files

Runtime:

- `scripts/utils/periodic_report_financial_trend_view.py` (new)
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- `scripts/utils/reporter/sections/valuation_renderer.py`

Tests:

- `tests/utils/test_periodic_report_financial_trend_view.py` (new)
- `tests/utils/test_periodic_report_fulltext_intake.py`
- `tests/reporter/test_valuation_renderer.py`

Workflow:

- `docs/agent_workflow/2026-07-31-chapter2-financial-trend-display-design.md`
- `docs/agent_workflow/2026-07-31-chapter2-financial-trend-display-implementation-plan.md`
- this file

## RED / GREEN

1. Projection module:
   - RED: import failed with `ModuleNotFoundError` before runtime creation.
   - GREEN: happy-path projection test passed.
2. Duplicate derived-series boundary:
   - RED: duplicated cash-conversion series incorrectly produced a ready view.
   - GREEN: only duplicate annual display candidates now reject the view.
3. Intake plumbing:
   - RED: `financial_trend_view` was absent for ready and missing-cache cases.
   - GREEN: ready and unavailable views are both published without changing intake status.
4. Renderer:
   - RED: Chapter 2 contained no `近三年财务趋势` subsection.
   - GREEN: snapshot -> trend -> peer ordering and fail-closed omission pass.
5. Self-review repair:
   - RED: duplicate irrelevant semiannual series suppressed an otherwise valid annual view.
   - GREEN: irrelevant semiannual duplicates are ignored; duplicate annual display candidates remain rejected.
6. Quote degradation repair:
   - RED: a ready three-year view disappeared when the live quote was unavailable.
   - GREEN: Chapter 2 now renders the local structured trend without live valuation metrics; no-view behavior remains unchanged.

## Verification

- Focused after acceptance repair: `49 passed in 3.04s`
- Affected downstream: `319 passed in 8.77s`
- Full suite after the acceptance repair: `2808 passed, 16 skipped in 55.39s`
- `tools/ci_grep_gates.sh`: all gates passed
- `git diff --check`: clean

## Real Cache Projection

All three local structured-history caches produced `status: ready` for 2023-2025:

- 中际旭创: revenue, net profit, and operating cash flow all `连续增长`; cash conversion `87.3% / 61.2% / 100.9%`.
- 复旦微电: revenue `连续增长`, net profit `连续下滑`, operating cash flow `由负转正`; cash conversion `-98.4% / 127.9% / 337.5%`.
- 黑芝麻智能: revenue `连续增长`, net profit `存在波动`, operating cash flow `持续为负`; unavailable cash-conversion years remain `—` and are not estimated.

These checks read local cache only and did not generate reports.

## End-To-End Sample

`python3 scripts/run_黑芝麻智能.py --fast-test` refreshed:

- `reports/黑芝麻智能_20260731.md`
- `reports/黑芝麻智能_20260731.html`

The Markdown contains Chapter 2 with the 2023-2025 table, cash conversion, trend
summary, and source disclosure. Because live quote access was unavailable in the
sandbox, it exercised the new narrow fallback and displayed no fabricated valuation
metrics. Source-boundary and prose checks passed. The general report-quality check
still reports missing daily/weekly/volume/volatility sections because the sandbox
could not fetch HK market data; this is unrelated to the financial-trend projection.
PDF export also remained unavailable because sandboxed Chromium could not register
its macOS Mach port.

## Runtime Delta

Feature-specific runtime delta:

- new projection module: `+128`
- valuation renderer: `+67` net
- intake imports/build/store plumbing: `+5`
- total: `+200`

This meets the design hard limit exactly. The implementation removed duplicate display ownership from the renderer: labels, formatted values, summary, and source disclosure are owned by the view; the renderer owns only envelope/cell validation and Markdown layout.

## Boundary Audit

- `ValuationRenderer` contains no reference to `periodic_report_metric_series_pack`.
- The raw MetricSeries pack retains `report_eligible: false` and `scoring_eligible: false`.
- Only `periodic_report_fulltext_intake_skill` builds the display view.
- The view is not passed into synthesis, scoring, target price, risk, technical analysis, executive summary, Chapter 3, Chapter 4, or source citation code.
- No new fetch, cache, LLM call, prompt, pipeline stage, or material taxonomy was introduced.

## Blocker / Warning / Deviation

- Blocker: none.
- Warning: runtime delta reaches the `+200` hard limit; future expansion should replace or simplify code rather than append more view rules.
- Acceptance repair: replaced the unresolved `List` annotation with `list` and added a type-hint resolution regression test; runtime delta is unchanged.
- Deviation: the expanded admission tests were initially green because the first minimal implementation already generalized to those cases. A separate duplicate-derived-series RED was added before completing the boundary behavior. No production behavior was accepted without a demonstrated RED for each functional layer.
