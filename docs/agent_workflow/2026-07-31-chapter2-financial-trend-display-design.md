# Chapter 2 Financial Trend Display Design

## Status

- Date: 2026-07-31
- State: locked
- Scope: display-only projection of validated structured annual financial history
- Placement: Chapter 2, after `最新财务快照` and before peer valuation comparison

## Problem

The pipeline now builds an auditable multi-year `periodic_report_metric_series_pack`,
but the pack is compute-only and the report still shows only the latest quarterly
snapshot. Readers cannot see whether revenue, attributable net profit, and operating
cash flow have improved or deteriorated over the latest three annual periods.

The fix must expose a narrow display projection without granting the source pack
general report or scoring authority. It must not move Eastmoney API data into the
official annual-report material layer or alter Chapter 3/4.

## Decision

Add one deterministic `FinancialTrendView` projection between the validated metric
series and `ValuationRenderer`.

The renderer consumes only the projection. It must not parse the raw metric-series
pack. The source pack retains:

- `report_eligible: false`
- `scoring_eligible: false`

The projection has explicit Chapter 2 display authority only. It cannot be consumed
by scoring, target-price, risk, technical-analysis, executive-summary, Chapter 3, or
Chapter 4 code.

The builder must reuse `read_periodic_financial_scan_source()` as the only sanitized
MetricSeries reader. It must not duplicate schema, identity, point, evidence, or
eligibility validation already owned by that reader.

## Alternatives Rejected

1. Parse the full pack inside `ValuationRenderer`: fewer initial lines, but combines
   contract validation, period selection, trend interpretation, and Markdown layout.
2. Render financial-scan findings: the scan models anomalies and consistency checks,
   not a stable three-year value table, so it cannot be the display read model.
3. Add the rows to Chapter 4 material snapshots: Eastmoney structured API history is
   not official annual-report prose and must not inherit annual-material authority.

## Projection Contract

The builder accepts:

- `stock_code`
- `periodic_report_metric_series_pack`

It returns a dictionary with:

- `schema_version: financial_trend_view.v1`
- `status: ready | unavailable`
- `display_eligible: true` only when ready
- `scoring_eligible: false`
- `stock_code`
- `years`: exactly three ascending consecutive integers
- `rows`: exactly three base metric rows, in fixed order
- `cash_conversion`: one fixed display row aligned to the same years; individual
  values may be unavailable
- `summary`: one deterministic, descriptive sentence
- `source_label`: fixed Eastmoney structured-data disclosure

Each base row contains:

- `metric_key`
- `label`
- `unit: 亿元`
- `values`: three amount strings in `亿元`, aligned to `years`
- `latest_growth_rate`: one-decimal display text parsed from the exact source growth
  string, or `—`; it is never recomputed from displayed amounts

The cash-conversion row contains three percentage strings or `—` and always uses
`latest_growth_rate: —` because a ratio's year-over-year change is not part of the
source contract.

The projection never carries source excerpts, raw cache payloads, LLM text, findings,
or scoring fields.

An unavailable result has the same schema and stock identity, `status: unavailable`,
`display_eligible: false`, `scoring_eligible: false`, empty years/rows/summary, and no
partially admitted values.

## Admission Rules

The shared sanitized reader first enforces source schema, stock identity, eligibility,
series identity, dimensions, point integrity, and derived-input provenance. The view
builder then fails closed unless all conditions hold:

1. The shared reader returns `status: ok`.
2. Revenue, attributable net profit, and operating cash flow each have one valid
   annual series with the same non-empty `value_basis`, currency `CNY`, and unit
   `万元`.
3. The three base series share exactly selectable latest three years, and those years
   are consecutive. Older stored history remains ignored by this projection.
4. Every selected base metric has exactly one finite point for each selected year.
5. The latest growth value must come from the exact latest consecutive interval
   already present in the validated series. The projection may add a sign and format
   it to one decimal place, but must not recompute it from displayed amounts. A
   missing latest growth value displays `—`.

Semiannual series, mixed value bases, duplicate candidate series, malformed points,
non-consecutive periods, and fewer than three common years make the whole view
unavailable. The renderer silently omits the subsection.

Cash conversion is optional. A missing value for a selected year displays `—`, which
is expected when attributable net profit is non-positive. Missing cash conversion
does not reject an otherwise complete view.

## Deterministic Summary

The summary describes direction only and uses no inferred cause:

- strictly rising twice: `连续增长`
- strictly falling twice: `连续下滑`
- negative to positive: `由负转正`
- positive to negative: `由正转负`
- all negative: `持续为负`
- otherwise: `存在波动`

Rules are applied in this fixed order for each metric: negative-to-positive,
positive-to-negative, all-negative, strictly rising, strictly falling, otherwise.
Zero does not count as positive or negative for sign-transition rules.

The summary covers the three base metrics in fixed order. It must not use investment
language, confidence language, explanations, forecasts, recommendations, or risk
labels. Cash conversion appears only as table data and is not interpreted when any
selected year is missing.

## Rendering

`ValuationRenderer` reads `financial_trend_view` from `ctx` and renders it after the
latest financial snapshot and before peer valuation comparison:

```markdown
### 近三年财务趋势

| 指标 | 2023 | 2024 | 2025 | 最新同比 |
|------|------|------|------|----------|
| 营业收入（亿元） | ... | ... | ... | +...% |
| 归母净利润（亿元） | ... | ... | ... | -...% |
| 经营现金流（亿元） | ... | ... | ... | +...% |
| 现金转换率 | ... | ... | ... | — |

> **趋势观察**: ...
>
> 数据来源：东方财富结构化年度财务数据；仅用于趋势观察，不替代年报确认，不参与评分。
```

Amounts convert deterministically from `万元` to `亿元` and display two decimal
places. Growth and cash conversion display one decimal place with `%`; positive
growth includes `+`. Missing optional values display `—`.

No footnote is added. This follows the existing Chapter 2 convention used by the
latest financial snapshot, which identifies the structured provider inline rather
than treating it as a Chapter 4 narrative source.

## Data Flow

1. Periodic-report intake loads the structured history cache.
2. Existing code builds `periodic_report_metric_series_pack`.
3. The projection builder consumes the existing sanitized financial-scan reader,
   selects the display window, and returns only formatted display fields.
4. Intake stores `financial_trend_view` in the
   same `SkillContext`.
5. `ValuationRenderer` consumes only `financial_trend_view`.
6. Missing or unavailable projections leave existing Chapter 2 output unchanged.

No new fetch, cache, LLM call, material taxonomy, or pipeline stage is introduced.

## Failure Modes And Guards

| Failure mode | Visible symptom without guard | Guard / test |
|---|---|---|
| Two years labeled as three-year trend | Misleading title and comparison | Require exactly three common consecutive years |
| Annual and semiannual periods mixed | False trend | Admit annual series only |
| Different value bases combined | Incomparable values | Require one shared `value_basis` |
| Raw compute pack becomes general report input | Eligibility boundary erosion | Shared reader enforces source flags; renderer accepts view only |
| Duplicate metric series selected arbitrarily | Non-deterministic values | Reject duplicate annual candidate series |
| Missing cash-conversion year suppresses useful table | Sparse company loses all history | Allow `—` only for cash conversion |
| Missing cache changes Chapter 2 | Regression in ordinary runs | Snapshot-style no-view renderer test |
| Trend prose implies causes or advice | Unsupported analysis | Fixed direction vocabulary tests |
| Display values affect scoring or conclusions | Behavioral regression | Context isolation and downstream regression tests |

## Allowed Scope

Runtime changes should be limited to:

- `periodic_report_financial_trend_view.py`, beside the existing periodic
  metric-series/financial-scan modules
- `periodic_report_fulltext_intake_skill.py` for context plumbing
- `valuation_renderer.py` for Markdown rendering

Tests should be limited to `test_periodic_report_financial_trend_view.py`, the
existing intake test module, and `test_valuation_renderer.py`. Do not modify scoring,
target-price, risk, technical-analysis, executive summary, Chapter 3/4 material
selection, source citation logic, LLM prompts, or data fetching.

## Verification

Required focused tests:

1. Ready view from three common consecutive annual years.
2. Older history is truncated to the latest three years.
3. Fewer than three years, year gaps, duplicate series, mixed value basis, wrong
   schema, stock mismatch, or eligibility violation fail closed through the view or
   shared reader.
4. Semiannual rows never enter the view.
5. Missing cash conversion renders `—`; non-positive net profit is not estimated.
6. Amount, growth, sign, and precision formatting are stable.
7. Summary direction vocabulary is deterministic and cause-free.
8. Renderer placement is snapshot -> trend -> peer comparison.
9. Missing view leaves the existing valuation output unchanged.
10. Intake stores only the compact display view alongside the compute-only pack.

Run focused tests, affected downstream reporter tests, `tools/ci_grep_gates.sh`, and
`git diff --check`. A full report rerun is deferred until the implementation and
focused regressions pass.
