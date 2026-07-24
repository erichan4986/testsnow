# Periodic Report Metric Series Design

> Date: 2026-07-24
> Status: Implemented and accepted
> Batch: Annual analysis architecture, Batch 2

## 1. Goal

Build an auditable cross-period metric layer on top of the existing
`periodic_report_structured_fact.v1` filing facts. The layer must reconstruct
history from local annual/semiannual report caches, preserve source identities,
derive comparable changes deterministically, and expose a stable input for the
later anomaly scanner.

This batch extends the existing fact owner. It does not introduce another
`AnnualFact` schema and does not select report prose.

## 2. Current State

The repository already has:

- `periodic_report_structured_facts.py`, which emits evidence-bound revenue,
  net-profit, and operating-cash-flow filing facts plus one per-period ratio;
- a latest-cache adapter that promotes the latest filing facts into the core
  fact table;
- a filing-fact Markdown writer, intentionally non-eligible for Knowledge;
- deterministic required financial metrics with broader single-period data.

The missing capability is cross-period assembly. The current report skill reads
only the latest matching cache for filing core facts, so it cannot represent a
three-year trend, identify a same-period conflict, or provide deterministic
change inputs to an anomaly scanner.

## 3. Scope

### In scope

1. Add a pure `periodic_report_metric_series.py` owner.
2. Assemble filing facts from multiple structured fact packs into comparable
   annual or semiannual series.
3. Rebuild those packs from all matching local caches for one stock and report
   type.
4. Emit exact source identities and hashes, without copying source prose.
5. Compute period-over-period absolute change and growth rate when valid.
6. Assemble the existing per-period operating-cash-flow/net-profit derived fact
   without introducing a second formula owner.
7. Publish the pack to `SkillContext` for later deterministic consumers.
8. Preserve the existing latest-cache core-fact behavior and report output.

### Out of scope

- No report rendering or display selection.
- No scoring, target price, risk score, technical analysis, or recommendation.
- No LLM, network, browser, Knowledge-note writes, or prompt changes.
- No anomaly conclusions; Batch 3 owns those rules.
- No fuzzy source matching or recovery from legacy notes.
- No expansion of the filing-fact metric universe in this batch.
- No comparison between annual and semiannual values.
- No inferred restatement model. Values with different `value_basis` remain
  separate series.

## 4. Architecture

### 4.1 Existing fact owner remains canonical

`build_periodic_report_structured_fact_pack()` remains the only owner of exact
periodic-report filing facts. The new layer accepts those packs and never
extracts numbers from raw text itself.

The cache adapter may call the existing evidence-pack, required-financial-
metrics, and structured-fact builders for each local file. This is orchestration,
not a second extraction path.

### 4.2 New pure series pack

Public API:

```python
build_periodic_report_metric_series_pack(
    *,
    stock_code: str,
    stock_name: str,
    fact_packs: list[dict],
) -> dict
```

Output schema:

```python
{
    "schema_version": "periodic_report_metric_series_pack.v1",
    "stock_code": "300308",
    "stock_name": "中际旭创",
    "report_eligible": False,
    "scoring_eligible": False,
    "source_pack_count": 3,
    "accepted_fact_count": 9,
    "rejected_fact_count": 0,
    "series": [...],
    "derived_series": [...],
    "diagnostics": [...],
}
```

Series identity is:

```text
stock_code + report_type + metric_key + value_basis + currency + unit
```

Annual and semiannual facts therefore cannot share a series. `as_reported` and
`restated` values also cannot be silently mixed.

### 4.3 Filing series point

Each accepted point contains compact provenance, not copied prose:

```python
{
    "period": "2025",
    "report_year": 2025,
    "numeric_value": "3824000.00",
    "normalized_value": "3824000.00万元",
    "fact_refs": ["periodic:300308:2025:annual:revenue"],
    "evidence_refs": ["financial_summary_table-0"],
    "source_evidence": [
        {
            "source_doc": "中际旭创_2025_annual_jina.txt",
            "source_block_id": "financial_summary_table-0",
            "source_excerpt_hash": "...",
            "source_block_hash": "...",
        }
    ],
}
```

`source_evidence` keeps document, block, and hashes in one identity record so
repeated block ids in different reports cannot collide. All list fields and
evidence records are unique and sorted. Exact duplicate facts collapse into one
point while retaining every provenance identity.

### 4.4 Changes

Consecutive-year points in one series produce:

```python
{
    "from_period": "2024",
    "to_period": "2025",
    "absolute_change": "12345.67万元",
    "growth_rate": "12.34%",
    "input_refs": ["...2024...", "...2025..."],
    "formula_version": "periodic_growth.v1",
}
```

Rules:

- absolute change is emitted for two valid comparable consecutive-year points;
- growth is emitted only when the previous value is strictly positive;
- zero or negative bases emit `non_positive_growth_base` and omit growth;
- a gap larger than one year emits `non_consecutive_period_gap` and no change;
- no CAGR is emitted in this batch;
- values are calculated with `Decimal` and rendered to two decimals.

### 4.5 Derived cash-conversion series

`periodic_report_structured_facts.py` remains the sole owner of
`operating_cash_flow_to_net_profit`. Its derived row gains `stock_code`,
`report_year`, `report_type`, `period`, and
`formula_version = cash_conversion.v1`.

MetricSeries validates and assembles those existing derived rows. It does not
recalculate the formula. A derived point is admitted only when its two input
filing facts correspond to accepted, non-conflicted filing points for the same
period. Exact duplicate derived rows merge provenance; conflicting values fail
closed. The operating-cash-flow sign therefore remains the behavior already
locked by structured-fact tests.

The derived point unions `source_evidence` from the two accepted filing points.
If either input point is missing or conflicted, or if `input_refs` do not match
the accepted fact ids, the derived row is rejected with a diagnostic.
More than one accepted value basis for either input is also ambiguous and
rejects the derived row rather than choosing one series.

The derived series is compute-only: `report_eligible=False` and
`scoring_eligible=False`.

## 5. Admission And Conflict Rules

A filing fact is accepted only when all of these hold:

1. source type is `periodic_report_filing_fact`;
2. pack and fact stock codes equal the requested stock code;
3. report type is `annual` or `semiannual`;
4. report year is a positive integer and matches `period`;
5. metric key is one of the existing Phase A filing metrics;
6. `normalized_value` is a parseable `万元` amount;
7. currency is `CNY`, unit is `万元`, and value basis is non-empty;
8. source document, source block id, evidence refs, excerpt hash, and block hash
   are present.
9. fact id exactly matches stock, period, report type, and metric; hashes are
   lowercase SHA-256 values and numeric values are finite fixed-point decimals.

Rejected facts are diagnosed and omitted.

For the same metric dimensions and period:

- identical numeric values are deduplicated and provenance is merged;
- different numeric values produce `conflicting_period_values`;
- a conflicted period is omitted from the canonical series, so downstream
  calculations cannot silently choose one value.

An invalid pack schema, entity mismatch, malformed fact, incompatible unit, or
unparseable value is fail-closed and diagnosed.

## 6. Local Cache History Adapter

The existing cache matcher becomes reusable:

```python
_find_periodic_report_cache_files(...) -> list[Path]
```

`_find_latest_periodic_report_cache_file()` delegates to it and still returns
the most recently modified match, preserving existing behavior.

New public helper:

```python
build_periodic_report_metric_series_from_cache(
    *, stock_code, stock_name, cache_dir, report_type
) -> dict
```

It:

1. finds every matching local cache for the requested report type, including
   the existing `hk/` directory;
2. reads each file independently;
3. builds one existing structured fact pack per readable non-empty cache;
4. passes `source_doc=cache_file.name` into the fact pack;
5. invokes the pure series builder;
6. appends deterministic cache diagnostics for unreadable, empty, or
   yearless files.

An exception while processing one historical cache emits
`cache_processing_failed` for that document and does not prevent the remaining
local history from being assembled.

No history cap is applied. Glob results are deduplicated by resolved path before
deterministic sorting. Duplicate language/revision files are retained as inputs
so exact duplicate values can merge and conflicting values can fail closed.

Each structured fact pack's compact diagnostics are copied into series
diagnostics with `source_doc`, `report_year`, and `report_type`. Raw text and
source excerpts are never copied. Only `code`, `metric_key`, `source_doc`,
`report_year`, and `report_type` are retained from input diagnostics.

No matching cache returns a well-formed empty MetricSeries pack with
`source_pack_count=0`; it does not return `{}` or raise. Series, points, changes,
source evidence, and diagnostics are sorted by documented ids/periods/codes so
the same inputs produce byte-equivalent data regardless of glob order.

The pipeline sets the result under:

```text
periodic_report_metric_series_pack
```

No renderer reads that key in this batch.

## 7. Existing Fact Schema Adjustment

`build_periodic_report_structured_fact_pack()` receives an optional
`source_doc=""` parameter. When non-empty, the pack, each filing fact, and each
derived fact include it. Derived facts also gain stock/period metadata and a
formula version. Fact ids remain unchanged because source document is
provenance, not fact identity.

The existing invalid-number display bug is fixed by importing
`InvalidOperation`; a focused test locks the fail-safe behavior.

## 8. Failure Modes And Tests

| Failure mode | Required behavior | Test |
|---|---|---|
| Annual and semiannual values mix | Separate series ids | mixed report-type fixture |
| Same period has two values | Omit point and diagnose conflict | conflict fixture |
| Same value appears in two language caches | One point, merged refs/docs | duplicate fixture |
| Two glob patterns match one path | One input pack, not duplicated | cache matcher fixture |
| Previous value is zero/negative | Absolute change only; growth omitted | base fixtures |
| Available years have a gap | No pseudo-YoY change; gap diagnostic | sparse history fixture |
| Entity mismatch | Reject and diagnose | mismatched stock fixture |
| Missing evidence hashes | Reject and diagnose | malformed provenance fixture |
| Unit/currency mismatch | Reject and diagnose | incompatible dimension fixture |
| Invalid normalized amount | Reject without exception | malformed numeric fixture |
| NaN/infinite numeric value | Reject as invalid | non-finite fixture |
| Derived ratio loses OCF sign | Negative ratio retained | negative OCF fixture |
| Net profit is non-positive | No ratio; diagnostic | loss fixture |
| Derived input has two value bases | Reject as ambiguous | value-basis fixture |
| One historical cache parser fails | Keep other years; diagnose failed cache | adapter isolation fixture |
| Cache has several years | Points sorted oldest to newest | cache adapter fixture |
| Cache has duplicate same-year revisions | Conflict or dedupe, never mtime winner | cache adapter fixture |
| Fact-pack metric is missing/unanchored | Compact source diagnostic retained | diagnostic propagation fixture |
| Existing latest core facts change | Latest mtime behavior unchanged | regression fixture |
| Metric series leaks into report | No renderer/consumer changes | scope audit and downstream tests |

## 9. Files

Runtime:

- add `scripts/utils/periodic_report_metric_series.py`;
- modify `scripts/utils/periodic_report_structured_facts.py`;
- modify `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`.

Tests:

- add `tests/utils/test_periodic_report_metric_series.py`;
- modify `tests/utils/test_periodic_report_structured_facts.py`;
- modify `tests/utils/test_periodic_report_fulltext_intake.py`.

No configuration, report, Knowledge, data, prompt, scoring, technical-analysis,
or renderer file may change.

## 10. Acceptance

1. New tests demonstrate RED before runtime edits and GREEN afterward.
2. Existing structured-fact, intake, synthesis, renderer, and source-boundary
   suites pass.
3. Full offline pytest, CI grep gates, and `git diff --check` pass.
4. Local-cache smoke test returns a valid one-point series pack where only one
   annual cache exists, without modifying cache or report files.
5. Scope audit confirms no report consumer reads the new context key.
6. Runtime additions stay focused; if implementation needs a second extractor,
   fuzzy matching, persistence, or report logic, stop and return to design.
