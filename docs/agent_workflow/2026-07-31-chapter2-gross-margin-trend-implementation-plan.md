# Chapter 2 Gross-Margin Trend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development and execute tasks in order. Stop at every stated hard gate.

**Goal:** Add an optional, auditable three-year gross-margin row to the existing Chapter 2 financial trend table.

**Architecture:** The structured-history adapter owns direct-value admission and same-row calculation fallback. Its reader returns amount and ratio points separately; MetricSeries receives only amounts. FinancialTrendView formats the optional ratio and ValuationRenderer only lays out validated cells.

**Tech Stack:** Python 3.10, `Decimal`, pytest, existing SkillContext/report pipeline.

---

## Locked Scope

Runtime files:

- `scripts/utils/reporter/data_fetcher.py`
- `scripts/utils/structured_financial_history.py`
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- `scripts/utils/periodic_report_financial_trend_view.py`
- `scripts/utils/reporter/sections/valuation_renderer.py`

Tests:

- `tests/reporter/test_structured_financial_history_provider.py`
- `tests/utils/test_structured_financial_history.py`
- `tests/utils/test_periodic_report_fulltext_intake.py`
- `tests/utils/test_periodic_report_financial_trend_view.py`
- `tests/reporter/test_valuation_renderer.py`

No changes are allowed in MetricSeries, FinancialScan, scoring, target price, risk,
technical analysis, Chapter 3/4, synthesis or prompts.

## Task 1: Provider And Optional Cache Metric

- [ ] Add provider RED test proving A-share history refresh returns a raw
  `indicator` collection from `stock_financial_abstract`, while HK keeps ratio data
  in its existing `profit` rows.
- [ ] Add adapter RED fixtures for:
  - A direct `毛利率` from exact `YYYY1231` column;
  - HK direct `GROSS_PROFIT_RATIO` from FY CNY row;
  - same-row `GROSS_PROFIT / revenue` fallback;
  - same-row `(revenue - OPERATE_COST) / revenue` fallback;
  - rejection of `TOTAL_OPERATE_COST`, split-row inputs and conflicting direct values;
  - old cache with no gross margin remaining valid and diagnostic-free.
- [ ] Run the named provider/cache tests and verify RED for missing indicator and
  missing `gross_margin` cells.
- [ ] Extend the provider with one raw call:

```python
"indicator": ak.stock_financial_abstract(symbol=code).to_dict("records")
```

- [ ] In `structured_financial_history.py`, split constants into required amount
  metrics and optional ratio metrics. Add compact helpers that return one candidate
  shape:

```python
{
    "value": Decimal("41.23"),
    "source": source_row,
    "origin": "direct" | "derived",
    "source_field": "GROSS_PROFIT_RATIO" | "derived",
    "formula_version": "" | "gross_margin.v1",
    "input_fields": tuple[str, ...],
}
```

- [ ] Resolve each year using direct candidates first. Equal duplicates collapse;
  conflicting direct values emit `conflicting_period_values` and block fallback.
  If no direct candidate exists, evaluate the two same-row formulae in fixed order.
- [ ] Persist optional cells and all selected field/value inputs under one source row
  hash. Do not emit `missing_metric` for gross margin.
- [ ] Run provider/cache tests GREEN.
- [ ] Measure runtime delta against `7c7d483`; stop if total exceeds `+100` at this
  checkpoint.

## Task 2: Verified Ratio Points And Intake Plumbing

- [ ] Add reader RED tests asserting one cache read returns:

```python
amount_points, ratio_points, diagnostics
```

  Ratio points must contain `metric_key=gross_margin`, `unit=pct`, two-decimal
  `numeric_value`, `origin`, formula/input provenance and source hashes.
- [ ] Add negative reader tests for tampered origin, formula, input fields, selected
  field values and row hash. Each must suppress the ratio point or reject the cache.
- [ ] Change the reader signature atomically and update all repository callers.
  Amount point serialization remains byte-for-byte equivalent.
- [ ] Change the intake private helper to return `(metric_series_pack,
  gross_margin_points)`. Pass amount points only into
  `build_periodic_report_metric_series_pack()` and pass ratio points only into
  `build_periodic_report_financial_trend_view()`.
- [ ] Add intake assertions that MetricSeries contains only the existing three metric
  keys while the view receives optional gross margin.
- [ ] Run cache/intake tests GREEN.
- [ ] Run grep proving `gross_margin` does not appear in
  `periodic_report_metric_series.py` or `periodic_report_financial_scan.py`.
- [ ] Stop if cumulative runtime delta exceeds `+150`.

## Task 3: View Projection And Renderer

- [ ] Add view RED tests for:
  - three direct years and `+x.xpct` latest change;
  - mixed direct/derived values with `*` and derivation note;
  - one missing year rendered as `—`;
  - all years missing omitting `gross_margin`;
  - duplicate/conflicting ratio points omitting only the ratio row;
  - three complete points extending the deterministic summary without causes.
- [ ] Extend the view builder signature with `gross_margin_points=()` and produce the
  exact optional object defined by the design. Validate stock identity, annual year,
  finite numeric value, fixed `pct` unit, unique year and allowed origin.
- [ ] Compute latest change as latest ratio minus prior ratio, quantized to one decimal
  and suffixed `pct`. Never calculate gross margin in the view.
- [ ] Add renderer RED tests proving the row appears after cash conversion, malformed
  ratio objects fail closed without suppressing base rows, and old views render
  unchanged.
- [ ] Extend `_financial_trend_table()` to validate and append the already formatted
  optional row. It must not import `Decimal`, read cache points or inspect formula
  inputs.
- [ ] Run view/renderer tests GREEN.
- [ ] Measure five-file runtime delta; stop above net `+200`.

## Task 4: Verification And Local Refresh

- [ ] Run focused tests for all five test modules.
- [ ] Run the full repository test suite.
- [ ] Run `bash tools/ci_grep_gates.sh` and `git diff --check`.
- [ ] Confirm MetricSeries/FinancialScan have zero diff.
- [ ] Only after all tests pass, run the explicit structured-history refresh for
  中际旭创、复旦微电、黑芝麻智能. Never fetch during an ordinary report run.
- [ ] Compare old/new cache amount points and stop on any loss or change.
- [ ] Generate the three no-PDF reports and inspect Chapter 2 values, markers,
  percentage-point changes and source disclosure.
- [ ] Run report quality, source-boundary and prose gates. Environment-only technical
  data failures may be documented but must not hide a financial/source error.
- [ ] Write implementation notes with RED/GREEN evidence, runtime numstat, cache
  comparison, report paths, blockers, warnings and deviations.

## Final Stop Conditions

- MetricSeries or FinancialScan requires modification.
- Any amount history point changes after refresh.
- A ratio lacks exact direct or same-row derived provenance.
- Runtime net delta exceeds `+200`.
- Focused/full/CI/source-boundary regression.
