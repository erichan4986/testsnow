# Chapter 2 Gross-Margin Trend Design

## Status

- Date: 2026-07-31
- State: proposed
- Scope: optional three-year gross-margin display in Chapter 2
- Risk level: Level 3 because the change extends a structured financial source contract

## Goal

Add one `毛利率` row to the existing three-year financial trend table. Prefer a
direct annual gross-margin ratio from the structured provider. When it is absent,
derive the ratio only from exact fields in the same issuer, year, provider row and
reporting basis. Keep the result display-only and auditable.

This batch does not add R&D intensity, adjusted profit, inventory, receivables,
capital expenditure, non-CNY normalization or a second report table.

## Approaches Considered

### A. Add gross margin to generic MetricSeries

This would make MetricSeries support both amount and ratio dimensions, add a
percentage-point change formula and extend FinancialScan admission. It is a sound
future direction if several ratios are added, but it is excessive for one optional
display metric and would expand three shared contracts.

### B. Calculate gross margin in the renderer

This minimizes initial plumbing but makes Markdown own source selection, financial
formulae and provenance. It would also create a second financial interpretation
path. Rejected.

### C. Extend the verified history cache with one optional ratio

Recommended. The structured-history adapter remains the single extraction and
calculation owner. Its reader returns amount points and validated ratio points
separately. MetricSeries continues to receive only the existing amount points;
`FinancialTrendView` receives the compact ratio points and owns display formatting.

## Source Contract

### Direct values

The adapter accepts direct annual gross margin in this order:

1. A-share `stock_financial_abstract` row whose exact indicator label is `毛利率`
   and whose exact annual column is `YYYY1231`.
2. HK `RPT_HKF10_FN_GMAININDICATOR.GROSS_PROFIT_RATIO` from an FY CNY row.

The provider boundary returns raw rows only. Field selection, annual-period
recognition and value admission remain in `structured_financial_history.py`.
The A-share indicator payload is wide: the adapter must project each exact
`YYYY1231` column into that year and construct the source-row identity from the
indicator label plus the selected date column. It must not expect `REPORT_DATE` on
that payload or admit quarter/semiannual columns.

### Derived fallback

Derivation is allowed only when no valid direct value exists for the year. The
fixed order is:

1. `gross_profit / revenue * 100` when both exact fields exist in the same row.
2. `(revenue - operating_cost) / revenue * 100` when the exact cost-of-sales field
   exists in the same row.

Exact field mappings:

- A-share revenue: `TOTAL_OPERATE_INCOME`, fallback `OPERATE_INCOME` only under the
  existing revenue rule.
- A-share gross profit: `GROSS_PROFIT`.
- A-share operating cost: `OPERATE_COST` only. `TOTAL_OPERATE_COST` is forbidden
  because it may include period expenses and taxes.
- HK revenue: `OPERATE_INCOME`.
- HK gross profit: `GROSS_PROFIT`.

No cross-row, cross-dataset, cross-year, cross-currency or cross-provider join is
allowed. Revenue must be positive. All inputs and outputs must be finite decimals.
The derived result is rounded to two decimal places with `ROUND_HALF_UP`.

If direct candidates conflict, the year is unavailable; derivation must not hide a
direct-source conflict. Equal duplicate direct values may collapse deterministically.

## Cache Contract

Keep `structured_financial_history_cache.v1`. Gross margin is an additive optional
metric, so existing v1 caches remain valid and continue producing the three amount
series.

An admitted cache cell uses:

```json
{
  "value": "41.23",
  "source_field": "GROSS_PROFIT_RATIO",
  "origin": "direct"
}
```

or:

```json
{
  "value": "41.23",
  "source_field": "derived",
  "origin": "derived",
  "formula_version": "gross_margin.v1",
  "input_fields": ["GROSS_PROFIT", "TOTAL_OPERATE_INCOME"]
}
```

`revenue`, `net_profit` and `operating_cash_flow` remain required only by their
existing consumers. Missing gross margin never removes a record, amount point,
MetricSeries or FinancialScan finding.

Implementation must split the current metric constant into required amount metrics
and optional ratio metrics. It must not append `gross_margin` to the existing
required-metric loop. Absence of the optional ratio produces neither `missing_metric`
nor another warning diagnostic.

The cache reader's internal signature changes atomically for its four repository
call sites and returns three collections:

1. existing verified amount source points;
2. compact verified gross-margin points;
3. diagnostics.

Gross-margin points contain only stock/year identity, decimal value, `direct` or
`derived` origin, source identity and formula/input-field provenance. They never
enter MetricSeries.

## Pipeline And Display

1. `fetch_structured_financial_history_rows()` adds raw A-share indicator rows;
   HK direct ratio remains in the existing profit rows.
2. The structured-history adapter stores optional gross-margin cells and validates
   provenance.
3. Periodic-report intake partitions the reader output: amount points build the
   unchanged MetricSeries; gross-margin points go only to `FinancialTrendView`.
4. `FinancialTrendView` aligns optional ratio points to the same selected three
   years as the amount rows.
5. `ValuationRenderer` appends one row to the existing table and performs no
   calculation.

The additive `financial_trend_view.v1` field is either absent or:

```json
{
  "metric_key": "gross_margin",
  "label": "毛利率",
  "unit": "%",
  "values": ["33.4%", "35.2%*", "38.1%"],
  "origins": ["direct", "derived", "direct"],
  "latest_change": "+2.9pct",
  "derivation_note": "* 为同源同年财务字段计算值。"
}
```

The view builder owns every formatted field above. The renderer validates this
envelope and joins cells only. Existing views without `gross_margin` remain valid.

Example:

```markdown
| 毛利率 | 33.4% | 35.2%* | 38.1% | +2.9pct |
```

- A derived value receives `*`.
- The latest change is the exact latest ratio minus the prior-year ratio and is
  displayed in percentage points, not relative percent growth.
- If either latest point is missing, latest change is `—`.
- Missing individual years display `—`; the base three-year table remains ready.
- If all three years are unavailable, omit `gross_margin` and render no empty row.
- If any displayed value is derived, append to the existing source disclosure:
  `* 为同源同年财务字段计算值。`

The deterministic trend summary adds `毛利率连续上升`, `毛利率连续下降` or
`毛利率存在波动` only when all three values exist. Otherwise it leaves the current
three-metric summary unchanged. It never infers causes or recommendations.

## Ownership And Compatibility

- `structured_financial_history.py`: direct/derived ratio admission and provenance.
- `periodic_report_metric_series.py`: unchanged.
- `periodic_report_financial_scan.py`: unchanged.
- `periodic_report_financial_trend_view.py`: optional ratio alignment, formatting
  and descriptive direction.
- `valuation_renderer.py`: envelope validation and Markdown layout only.

Existing v1 caches without gross margin remain readable. Existing reports omit the
row until an explicit cache refresh supplies enough data. Ordinary report generation
remains cache-only and makes no new network request.

## Failure Modes And Tests

| Failure mode | Guard | Required test |
|---|---|---|
| Optional margin removes valid amount history | Gross margin is not a required record metric | Cache with three amounts and no margin remains valid |
| Total operating cost is mistaken for cost of sales | Explicitly forbid `TOTAL_OPERATE_COST` | Only that field present yields no derived margin |
| Fields from two rows are combined | Formula inputs must belong to one row hash | Split-row revenue/cost fixture yields no ratio |
| Direct conflict is hidden by derivation | Conflicting direct values block the year | Conflict plus derivable profit row remains unavailable |
| Quarterly value enters annual history | Exact `YYYY1231` / FY admission | Quarterly columns and H1 HK rows are ignored |
| Relative growth shown for a ratio | View computes percentage-point delta only | 35% to 40% renders `+5.0pct`, not `+14.3%` |
| Derived value is indistinguishable | Persist origin and render `*` | Mixed direct/derived three-year fixture |
| Missing ratio suppresses Chapter 2 | Optional alignment uses `—` | Base table remains ready with all margin points absent |
| Ratio leaks into scoring | MetricSeries receives amount points only | Context and owner isolation assertions |
| Renderer recomputes ratio | Renderer consumes formatted view cells | AST/grep gate and malformed-view fail-closed test |

## TDD Batches

### Batch 1: Provider And Cache

- Add A-share raw indicator rows to the existing provider result.
- Admit direct HK/A values.
- Add same-row derived fallback and provenance.
- Preserve old v1 cache readability and byte-stable no-op writes.

### Batch 2: Reader And Intake

- Return amount points and ratio points separately from one cache read.
- Keep MetricSeries input unchanged.
- Pass only ratio points to the display view.

### Batch 3: View And Renderer

- Align optional points to the selected three-year window.
- Format values, derived markers and percentage-point change.
- Add one table row and conditional source note.

### Batch 4: Verification

- Focused source/provider/intake/view/renderer tests.
- Full repository suite, CI grep gates and `git diff --check`.
- Explicitly refresh the three canonical caches only after unit tests pass.
- Generate 中际旭创、复旦微电、黑芝麻智能 reports and inspect Chapter 2.

## Allowed Runtime Scope

- `scripts/utils/reporter/data_fetcher.py`
- `scripts/utils/structured_financial_history.py`
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- `scripts/utils/periodic_report_financial_trend_view.py`
- `scripts/utils/reporter/sections/valuation_renderer.py`

`periodic_report_metric_series.py` and `periodic_report_financial_scan.py` are explicit
no-change files. Tests may change only their corresponding provider, cache, intake,
view and renderer test modules. Canonical cache JSON may change only through the
explicit refresh command after implementation tests are green.

## Prohibited Changes

- No scoring, target price, risk, technical analysis, executive summary, Chapter 3
  or Chapter 4 changes.
- No LLM prompt or synthesis changes.
- No historical annual-text parsing.
- No live fetch during ordinary report generation.
- No fuzzy field names, manual stock overrides or industry-specific rules.
- No second gross-margin calculation owner.

## Budget And Stop Conditions

- Runtime target: net `+140` lines across allowed files.
- Runtime hard stop: net `+200` lines.
- Stop if MetricSeries or FinancialScan must be changed.
- Stop if a provider does not expose exact same-row fallback fields.
- Stop if canonical cache refresh loses any existing amount point.
- Stop if any report-facing value lacks direct or derived provenance.
- Stop on source-boundary, quality-gate or full-suite regression.

## Self Review

The design initially considered adding gross margin to MetricSeries. That would
force amount and ratio change semantics into a shared compute contract for one
display-only metric, so the final design keeps MetricSeries unchanged.

The first fallback draft allowed revenue and cost from separate provider rows. That
would make row selection and restatement identity ambiguous. The final rule requires
all formula inputs in one row and gives direct conflicts precedence over derivation.
