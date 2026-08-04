# Chapter 2 Gross-Margin Trend Implementation Notes

## Result

- Verdict: `PASS_WITH_WARNING`
- User-approved repository review waiver was applied before implementation.
- Two design self-reviews and two implementation self-reviews were completed.
- Locked scope was respected; MetricSeries, FinancialScan, scoring, targets, risk,
  technical analysis, Chapter 3/4 and prompts were not modified.

## Requirement-Test Matrix

| Requirement | Implementation | Verification |
|---|---|---|
| A/H direct annual margin | provider + structured-history adapter | provider/cache tests |
| Same-row derivation only | `gross_profit/revenue`, then `(revenue-operating_cost)/revenue` | split-row and `TOTAL_OPERATE_COST` negative fixtures |
| Direct conflict blocks fallback | annual candidate resolution | conflict fixture |
| Amount and ratio isolation | cache reader returns three collections | reader/intake tests and zero MetricSeries/FinancialScan diff |
| Optional display row | FinancialTrendView + ValuationRenderer | view/renderer tests |
| Percentage-point change | view formatting | `+1.6pct` fixture |
| Malformed data fails closed | cache/view/renderer guards | malformed origin, NaN and marker mismatch fixtures |
| Optional provider failure preserves amounts | provider best-effort indicator call | provider failure fixture |

## RED / GREEN

- Batch 1 RED: 4 failures; GREEN: 14 passed.
- Reader RED: 3 failures; GREEN after verified ratio projection.
- View/renderer/intake RED: 4 failures; GREEN after optional projection.
- Self-review guards RED: 3 failures; GREEN after fail-closed fixes.
- Final focused suite: `70 passed`.
- Full suite: `2818 passed, 16 skipped`.
- `tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.

## Runtime Budget

Against `81b26bc`, the five runtime files are net `+158` lines:

- financial trend view: `+44`
- intake skill: `+1`
- provider: `+6`
- valuation renderer: `+16`
- structured financial history: `+91`

This exceeds the `+140` target but remains below the `+200` hard stop. The extra
guards cover malformed-cache validation, non-finite ratios, display marker
consistency and optional-provider failure isolation.

## Cache And Report Verification

The three canonical caches were explicitly refreshed after tests passed. Removing
`gross_margin` from the refreshed records produced zero diff against the pre-refresh
amount snapshots.

Latest three-year direct margins:

- 中际旭创: `33.0% / 33.8% / 42.0%`, latest `+8.2pct`
- 复旦微电: `61.2% / 56.0% / 56.2%`, latest `+0.2pct`
- 黑芝麻智能: `24.7% / 41.1% / 41.0%`, latest `-0.1pct`

Fresh reports:

- `reports/中际旭创_20260731.md`
- `reports/复旦微电_20260731.md`
- `reports/黑芝麻智能_20260731.md`

中际旭创 and 复旦微电 passed quality, source-boundary and prose gates. 黑芝麻智能
passed source-boundary and prose gates; report quality failed only for the known
unavailable HK daily/weekly/volume technical data. Its Chapter 2 trend rendered
correctly and was not affected by that environment limitation.

## Warning / Deviation

- Warning: runtime net is `+158`, above the soft target and below the hard stop.
- Warning: the HK report retains the known technical-market-data quality failure.
- Deviation: none from the approved functional design or locked runtime scope.
