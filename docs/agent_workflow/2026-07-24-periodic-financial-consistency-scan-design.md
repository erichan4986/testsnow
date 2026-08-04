# Periodic Financial Consistency Scan Design

> Date: 2026-07-24
> Status: Locked after two-pass Codex self-review
> Batch: Annual analysis architecture, Batch 3

## 1. Goal

Build a deterministic, auditable scan over the existing cross-period
`periodic_report_metric_series_pack.v1`. The scan identifies cross-metric
inconsistency, adverse divergence, metric direction reversal, and
cash-conversion weakness without reading source prose, calling an LLM, or
changing any report, score, target, risk score, technical conclusion, or
recommendation.

The result is a compute-only evidence object for the later external-evidence
mapping batch. It is not a second filing-fact producer and is not a report
selector.

## 2. Alternatives Considered

### A. Add more raw-text forensic regexes

Extend `_extract_financial_forensics()` in `periodic_report_extractor.py`.

Rejected. That path parses loosely structured prose and tables, already owns
legacy display observations, and cannot prove exact cross-period comparability.
Adding more rules there would deepen the split between auditable filing facts
and heuristic excerpts.

### B. Typed scan over MetricSeries (selected)

Consume the existing validated series, preserve fact/evidence identities, and
emit code-only deterministic findings. Use only exact period joins and shared
rule owners.

Selected because it preserves the producer/display boundary, gives Batch 4 a
stable mapping target, and does not change current reports.

### C. Replace all legacy financial forensics now

Migrate `_extract_financial_forensics()` consumers and renderers to the typed
scan in one batch.

Deferred. It would mix a compute-layer addition with report behavior migration,
source-intake compatibility, and quality-gate changes. The typed scan must be
accepted independently first.

## 3. Existing Owners And Non-Duplication Rules

1. `periodic_report_structured_facts.py` remains the only owner of filing facts,
   the operating-cash-flow/net-profit formula, and the 50% cashflow-quality
   threshold.
2. `periodic_report_metric_series.py` remains the only owner of comparable
   period points and growth calculations.
3. The scanner trusts arithmetic emitted by those in-process canonical owners.
   It validates typed identities and finite values but does not reimplement the
   growth or cash-conversion formula.
4. The scanner imports a public cashflow-quality predicate from the structured
   fact owner. It must not contain a literal duplicate threshold.
5. Legacy `_extract_financial_forensics()` remains unchanged and is not an
   input. Its observations are not merged with typed findings in this batch.
6. No renderer, scorer, risk rule, target-price path, Knowledge writer, or LLM
   prompt reads the new pack in this batch.

## 4. Batch 2 Comparability Repair

Before scanning derived histories, close one comparability gap in MetricSeries.

The current derived cash-conversion series groups by report type only. If one
year's accepted inputs are `as_reported` and another year's inputs are
`restated`, the points can enter one series even though the filing series keep
those bases separate.

Required repair:

1. `_filing_point_index()` retains the parent filing series `value_basis`,
   currency, and unit with each indexed point.
2. A derived point is admitted only when net profit and operating cash flow use
   the same value basis, currency, and unit for that period.
3. A mismatch emits `derived_input_dimension_mismatch` and rejects the derived
   point.
4. The accepted derived row carries `value_basis`.
5. `_build_derived_series()` groups by `(report_type, value_basis)`.
6. Derived series ids and payloads include `value_basis`.
7. Filing-fact admission requires `value_basis` to match
   `[a-z][a-z0-9_]{0,63}`. Existing `as_reported` remains valid; unsafe identity
   text is rejected rather than escaped differently by each consumer.

The repaired id is exactly:

```text
periodic-derived-series:{stock_code}:{report_type}:
operating_cash_flow_to_net_profit:{value_basis}:cash_conversion.v1:pct
```

`periodic_report_metric_series_pack.v1` is not persisted or consumed outside
the current intake context, so this pre-consumer bug fix does not require a
compatibility reader or schema-version bump.

No formula or value changes for valid existing inputs.

## 5. Public API And Output Contract

New module:

```text
scripts/utils/periodic_report_financial_scan.py
```

Public API:

```python
build_periodic_report_financial_scan_pack(
    *,
    stock_code: str,
    stock_name: str,
    metric_series_pack: dict,
) -> dict
```

Pack schema:

```python
{
    "schema_version": "periodic_report_financial_scan_pack.v1",
    "stock_code": "300308",
    "stock_name": "中际旭创",
    "source_schema_version": "periodic_report_metric_series_pack.v1",
    "status": "ready|partial|empty|unavailable",
    "report_eligible": False,
    "scoring_eligible": False,
    "external_mapping_eligible": True,
    "source_series_count": 3,
    "source_point_count": 9,
    "comparable_interval_count": 2,
    "findings": [...],
    "diagnostics": [...],
}
```

Status semantics:

- `unavailable`: top-level source schema/entity contract is invalid;
- `empty`: source pack is valid but has no admitted points;
- `partial`: admitted points exist but no exact cross-period interval can be
  scanned;
- `ready`: at least one exact comparable interval or admitted derived-ratio
  point was scanned. `ready` does not imply that a finding exists.

All counters describe admitted source rows, not raw list lengths:

- `source_series_count`: admitted filing plus derived series;
- `source_point_count`: admitted points across those series;
- `comparable_interval_count`: unique `(report_type, value_basis,
  from_period, to_period)` filing intervals with at least one admitted change.

## 6. Finding Contract

Each finding is code-first and contains no generated prose:

```python
{
    "finding_id": "periodic-financial:300308:annual:as_reported:2024-2025:revenue_growth_profit_contraction:net_profit+revenue",
    "rule_id": "revenue_growth_profit_contraction",
    "rule_version": "financial_consistency.v1",
    "category": "cross_metric_divergence|trend_reversal|cashflow_quality",
    "direction": "adverse|recovery",
    "report_type": "annual",
    "value_basis": "as_reported",
    "periods": ["2024", "2025"],
    "metric_keys": ["net_profit", "revenue"],
    "observations": [
        {
            "metric_key": "revenue",
            "value_kind": "growth_rate",
            "from_period": "2024",
            "to_period": "2025",
            "value": "8.00%",
        },
        {
            "metric_key": "net_profit",
            "value_kind": "growth_rate",
            "from_period": "2024",
            "to_period": "2025",
            "value": "-4.00%",
        },
    ],
    "input_refs": ["periodic:..."],
    "source_evidence": [{...}],
    "report_eligible": False,
    "scoring_eligible": False,
    "external_mapping_eligible": True,
}
```

Rules for all findings:

1. `finding_id` is deterministic from stock, report type, validated value basis,
   period span, rule id, and sorted `+`-joined metric identity. The validated
   value basis is already an identifier-safe token and is never normalized a
   second way.
2. `periods`, `metric_keys`, `observations`, `input_refs`, and
   `source_evidence` are deduplicated and deterministically sorted.
3. `source_evidence` contains only source document, block id, and hashes; no
   source text or excerpt is copied.
4. Every `input_ref` must be present in an admitted point participating in the
   finding.
5. Annual and semiannual observations never join.
6. Filing series join only when value basis, currency, and unit match exactly.
7. Zero growth does not count as positive or negative.
8. A growth observation includes `from_period` and `to_period`. A point
   observation includes `period`. Therefore two changes for the same metric can
   never become indistinguishable after sorting.

## 7. Deterministic Rules

### 7.1 Revenue growth with profit contraction

Emit `revenue_growth_profit_contraction` when, for the exact same interval and
dimensions:

```text
revenue growth > 0 and net-profit growth < 0
```

Direction is `adverse`. No materiality threshold is introduced.

### 7.2 Profit growth with operating-cash-flow contraction

Emit `profit_growth_cashflow_contraction` when, for the exact same interval and
dimensions:

```text
net-profit growth > 0 and operating-cash-flow growth < 0
```

Direction is `adverse`. This rule compares direction; it does not recreate the
cash-conversion ratio or its 50% threshold.

### 7.3 Growth direction reversal

For each filing metric independently, emit `growth_direction_reversal` only
when two adjacent, consecutive changes share their middle period:

```text
A -> B growth > 0 and B -> C growth < 0
```

The finding is `adverse` and covers periods `[A, B, C]`. The inverse
negative-to-positive move emits `growth_direction_recovery` with direction
`recovery`. Missing growth rates, zero growth, period gaps, or non-shared
boundaries emit no reversal finding.

### 7.4 Cashflow quality

For each admitted `operating_cash_flow_to_net_profit` point, call the shared
cashflow-quality predicate owned by `periodic_report_structured_facts.py`.

The public owner contract is:

```python
CASHFLOW_QUALITY_WEAK_THRESHOLD_PCT = Decimal("50")

def is_cashflow_quality_weak(ratio_pct: Decimal | None) -> bool:
    return ratio_pct is not None and ratio_pct < CASHFLOW_QUALITY_WEAK_THRESHOLD_PCT
```

The existing risk-signal builder is changed to call this function. The scanner
also calls it; neither caller contains its own threshold literal.

- weak point -> `cashflow_quality_weak`, direction `adverse`;
- previous non-weak point followed by weak point ->
  `cashflow_quality_deteriorated`, direction `adverse`;
- previous weak point followed by non-weak point ->
  `cashflow_quality_recovered`, direction `recovery`.

Transitions require consecutive years, the same report type, and the same value
basis. A missing ratio point is unknown, never healthy.

## 8. Consistency Validation

The scan validates source records before using them.

### 8.1 Top-level contract

The pack is unavailable when:

- schema is not `periodic_report_metric_series_pack.v1`;
- stock code differs from the requested stock;
- `report_eligible` or `scoring_eligible` is not explicitly false;
- `series`, `derived_series`, or `diagnostics` is not a list.

An unavailable return is still a complete schema object. It uses the requested
stock identity, `source_schema_version` copied as a scalar string when possible,
all counters set to zero, empty findings, and exactly one top-level diagnostic.

Top-level diagnostic codes are fixed:

- `unsupported_source_schema`;
- `source_stock_mismatch`;
- `source_eligibility_violation`;
- `malformed_source_collections`.

Duplicate filing or derived `series_id` values are ambiguous. Every occurrence
of that id is rejected and one `duplicate_source_series_id` diagnostic is
emitted. The scanner never chooses the first or last row.

### 8.2 Filing series records

An admitted filing series must have:

- the exact stock-bound series id;
- metric in revenue/net profit/operating cash flow;
- report type annual/semiannual;
- non-empty value basis, CNY currency, and `万元` unit;
- unique, increasing positive years;
- finite decimal point values;
- exact fact ids for stock/year/type/metric;
- compact valid source-evidence SHA-256 identities;
- changes with consecutive, existing point periods, exact participating point
  refs, `periodic_growth.v1`, finite optional growth rates, and no duplicate
  interval.

A malformed series is omitted and diagnosed. The scanner does not recompute
absolute change or growth: MetricSeries is the sole formula owner and the pack
is handed to the scanner in process without persistence.

The stable row-level diagnostic codes are:

- `duplicate_source_series_id`;
- `invalid_filing_series_contract`;
- `invalid_filing_point_contract`;
- `invalid_filing_change_contract`.

Each contains only available scalar identity fields from `series_id`,
`metric_key`, `report_type`, `value_basis`, `report_year`, `from_period`, and
`to_period`.

### 8.3 Derived series records

An admitted cash-conversion series must have:

- exact stock-bound id, report type, value basis, formula version, and percent
  unit;
- unique increasing periods;
- finite decimal values;
- exact derived fact id and two exact filing input refs;
- compact valid source evidence.

The scanner verifies that both input refs resolve to admitted filing points for
the same stock, report type, value basis, and period. It does not recompute the
ratio; `periodic_report_structured_facts.py` remains the sole formula owner.

Derived row failures use `invalid_derived_series_contract`,
`invalid_derived_point_contract`, or `unresolved_derived_input_refs`.

### 8.4 Upstream diagnostics

Compact upstream diagnostics are copied into `diagnostics` with
`origin="metric_series"`. Only `code`, `metric_key`, `source_doc`,
`report_year`, and `report_type` are retained. They remain diagnostics and
never become anomaly findings. This preserves conflicts, gaps, missing anchors,
and invalid inputs without claiming that missing data is a company anomaly.

## 9. Pipeline Integration

After building `periodic_report_metric_series_pack`, the existing periodic
fulltext intake skill calls the pure scanner and writes:

```text
periodic_report_financial_scan_pack
```

The scanner receives the already-built pack, so local caches are not read a
second time. The skill always writes a well-formed scan pack, including when no
cache exists or the source pack is unavailable.

No downstream consumer is added in this batch.

## 10. Determinism And Safety

- Use `Decimal`; reject NaN and infinity.
- Do not parse Chinese prose or numeric strings outside typed values.
- Do not infer missing periods, restatements, currency conversion, or annualized
  semiannual values.
- Do not cap findings. Duplicate source series ids fail closed before rule
  evaluation, so one rule invocation can produce at most one payload for a
  finding id. A remaining finding-id collision emits
  `conflicting_finding_identity` and removes that id entirely.
- Findings are sorted by finding id; diagnostics by stable code and identity
  fields.
- No raw source excerpt, URL, prompt text, or report prose enters the pack.
- Recursive contract tests reject keys named `text`, `source_excerpt`,
  `raw_text`, `url`, `prompt`, or `rationale` anywhere in findings.

## 11. Failure Modes And Required Tests

| Failure mode | Required behavior | Test |
|---|---|---|
| Wrong pack schema or stock | unavailable empty pack | top-level fixtures |
| Display/scoring eligibility leaks | unavailable | eligibility fixture |
| Annual joins semiannual | no finding | mixed-type fixture |
| Filing bases differ | no cross-metric join | basis fixture |
| Derived inputs have different bases | reject before series assembly | MetricSeries regression |
| Derived years use different bases | separate derived series | MetricSeries regression |
| Point contains NaN/infinity | omit and diagnose | non-finite fixtures |
| Change points/refs are malformed | omit series and diagnose | change contract fixture |
| Ratio input refs do not resolve | omit point and diagnose | ratio input fixture |
| Revenue up, profit down | one adverse divergence | positive fixture |
| Revenue and profit both up | no divergence | negative fixture |
| Profit up, OCF down | one adverse divergence | positive fixture |
| Intervals do not match | no divergence | interval fixture |
| Positive growth reverses negative | one 3-period adverse finding | reversal fixture |
| Negative growth turns positive | one recovery finding | recovery fixture |
| Zero or missing growth | no reversal | zero/missing fixture |
| Weak cash conversion | shared-rule finding | weak fixture |
| Ratio absent after loss | no healthy/weak inference | missing-ratio fixture |
| Weak status crosses threshold | exact deterioration/recovery | transition fixtures |
| Same input order changes | byte-equivalent output | determinism fixture |
| Findings include source prose | contract fails | leakage fixture |
| Duplicate source series ids | reject every duplicate row | ambiguity fixture |
| Two same-metric changes lose interval identity | observations retain both intervals | reversal contract fixture |
| No cache / one year | empty/partial well-formed pack | intake fixtures |
| New pack reaches report/scoring | no consumer added | scope audit/downstream tests |

## 12. Files

Runtime:

- add `scripts/utils/periodic_report_financial_scan.py`;
- modify `scripts/utils/periodic_report_metric_series.py` only for derived
  value-basis comparability;
- modify `scripts/utils/periodic_report_structured_facts.py` only to expose and
  reuse the existing cashflow-quality predicate;
- modify
  `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py` only to
  build and publish the scan pack.

Tests:

- add `tests/utils/test_periodic_report_financial_scan.py`;
- modify `tests/utils/test_periodic_report_metric_series.py`;
- modify `tests/utils/test_periodic_report_structured_facts.py`;
- modify `tests/utils/test_periodic_report_fulltext_intake.py`.

Workflow documentation may be added under `docs/agent_workflow/`.

No configuration, cache, data, Knowledge, report, renderer, quality-gate,
scoring, target, risk, technical-analysis, recommendation, or prompt file may
change.

## 13. Acceptance

1. Each behavior is introduced by a failing test and then made green.
2. Both design self-reviews are documented and all blocker/must-fix findings are
   repaired before implementation.
3. Focused structured-fact, MetricSeries, scan, and intake tests pass.
4. Existing extraction, material, synthesis, renderer, quality, and source-
   boundary downstream suites pass.
5. Full offline pytest, CI grep gates, module compilation, and
   `git diff --check` pass.
6. Read-only local-cache smoke produces a well-formed partial/ready scan without
   network, report generation, or file mutation.
7. Scope audit proves that only the intake skill writes the new context key and
   no report/scoring/Knowledge consumer reads it.
8. If implementation requires new arbitrary thresholds, raw-text parsing, a
   second fact/ratio owner, or report integration, stop and return to design.

## 14. Design Review Status

Two Codex self-reviews are complete. Round 1 removed duplicate formula
ownership and locked comparability/status behavior. Round 2 locked temporal
observation identity, safe value-basis syntax, diagnostics, and unavailable
output. No blocker or must-fix remains; the design is implementation-plan
ready under the user's standing autonomous approval.
