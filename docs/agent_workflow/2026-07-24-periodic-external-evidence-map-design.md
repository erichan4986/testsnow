# Periodic External Evidence Map Design

## 1. Goal

Build an auditable, compute-only bridge from validated external-material units
to admitted periodic-report facts and financial-scan findings.

The bridge answers only three narrow questions:

- `confirm`: does an external numeric observation agree with the same filing
  period and metric, after respecting the precision stated by the external
  source?
- `contradict`: does a same-period, same-metric numeric observation fall
  outside the filing value or range?
- `update`: does the external source provide a later explicitly named period
  for a metric whose latest admitted filing point is older?

It does not decide which source is true, alter the official fact, generate
prose, enter scoring, or render in the report. Unmappable evidence remains
unmapped rather than receiving a guessed relation.

## 2. Alternatives

### A. LLM semantic comparison

Ask an LLM whether every external card confirms, contradicts, or updates the
annual report.

Rejected. This would create a second semantic owner, make the relation
non-reproducible, and allow paraphrase or entity mistakes to become apparent
fact conflicts.

### B. Topic-family association only

Associate `financial_quality` cards with all financial facts and label them
`related`.

Rejected. It has high recall but cannot support the requested relation types;
it also makes one broad sentence appear to verify every metric in the family.

### C. Typed deterministic observation mapping (selected)

Extract only explicit target-company financial metric observations from
already validated v4 evidence units. Join them to the scanner's admitted
MetricSeries on exact metric and period identity. Keep all unsupported or
ambiguous cases as diagnostics/unmapped observations.

Selected because it preserves source identity, has deterministic failure
behavior, and creates a safe future input for freshness/display work without
changing today's report.

## 3. Existing Owners

The implementation must reuse, not duplicate, these owners:

1. `external_pack.py` and `curated_external_display.py` own canonical v4
   document/card/unit/scope validation. Mapping is called only after the
   display adapter returns `status=ok`.
2. `periodic_report_financial_scan.py` owns MetricSeries admission. It will
   expose a small public read result used by both the scanner and mapper so the
   mapper cannot consume a series the scanner rejected.
3. `periodic_report_metric_series.py` owns filing values, growth, periods,
   value bases, and formulas.
4. `periodic_report_financial_scan.py` owns finding identities and rule
   semantics.
5. The mapper owns only external typed-observation extraction and relation
   construction.

No LLM prompt, external producer, annual producer, report renderer, quality
gate, scoring, target price, risk, technical analysis, or recommendation rule
changes in this batch.

## 4. Public APIs

### 4.1 Shared scanner source reader

Add to `periodic_report_financial_scan.py`:

```python
read_periodic_financial_scan_source(
    *, stock_code: str, metric_series_pack: dict
) -> dict
```

Return shape:

```python
{
    "status": "ok|unavailable",
    "source_schema_version": "periodic_report_metric_series_pack.v1",
    "filing_series": [...],
    "derived_series": [...],
    "diagnostics": [...],
}
```

This is an in-process sanitized read model, not a context pack. The existing
scan builder must call it, preserving byte-equivalent scan output.

### 4.2 External mapping builder

New module `periodic_external_evidence_map.py`:

```python
build_periodic_external_evidence_map(
    *,
    stock_code: str,
    stock_name: str,
    metric_series_pack: dict,
    financial_scan_pack: dict,
    validated_external_display: dict,
) -> dict
```

`validated_external_display` is exactly the `display` returned by
`build_curated_external_argument_display(status=ok)`. The builder checks the
private taxonomy marker, v4 card/unit schemas, target entity, citation
identities, and required scalar fields, but does not redo source-document span
validation.

## 5. Output Contract

Schema: `periodic_external_evidence_map.v1`.

```python
{
    "schema_version": "periodic_external_evidence_map.v1",
    "stock_code": "688385",
    "stock_name": "复旦微电",
    "metric_series_schema_version": "periodic_report_metric_series_pack.v1",
    "financial_scan_schema_version": "periodic_report_financial_scan_pack.v1",
    "external_taxonomy_version": "external_argument.v4",
    "status": "ready|partial|empty|unavailable",
    "report_eligible": False,
    "scoring_eligible": False,
    "risk_score_eligible": False,
    "target_unit_count": 8,
    "target_financial_unit_count": 5,
    "typed_observation_count": 4,
    "mapping_count": 3,
    "finding_link_count": 1,
    "observations": [...],
    "mappings": [...],
    "unmapped_observations": [...],
    "diagnostics": [...],
}
```

Status semantics:

- `unavailable`: scanner source admission, financial-scan identity, or
  validated-display contract is invalid;
- `empty`: valid inputs contain no target financial evidence units;
- `partial`: target financial units exist but produce no safe mapping;
- `ready`: at least one safe mapping exists. Unmapped siblings do not demote a
  ready pack.

`typed_observation_count` must equal `len(observations)`. All lists are uncapped
and deterministically sorted. The output contains no
external unit text, title, account, URL, source excerpt, prompt, rationale, or
generated prose.

## 6. External Typed Observation

Only cards with `entity_scope=target` and the `financial_quality` family enter
extraction. `target_with_peer_context` is deliberately excluded in v1 because
the numeric owner inside a comparison sentence may be the peer even when the
card as a whole concerns the target. `peer_or_industry` is also out of scope.
Neither can ever map to a target filing fact.

`target_unit_count` counts all units in `target` cards.
`target_financial_unit_count` counts the subset admitted to typed extraction.

Supported metric aliases:

- `revenue`: `营业收入`, `营收`, `來自客戶合同的收入`,
  `来自客户合同的收入`;
- `net_profit`: `归母净利润`, `归属于上市公司股东的净利润`,
  `歸屬於本公司股東的利潤`;
- `operating_cash_flow`: `经营活动产生的现金流量净额`,
  `经营现金流量净额`, `经营现金流` and traditional-Chinese equivalents.

Generic `收入`, `利润`, and `现金流` alone are not admitted. `扣非净利润`,
gross profit, investment income, EBITDA, adjusted profit/loss, target price,
and valuation multiples are outside this batch.

Each metric clause may yield:

- one amount observation in `亿元` or `万元`, normalized to `万元`;
- one year-on-year rate observation in `%` when an explicit `同比` relation is
  present.

An observation contains only code/data fields:

```python
{
    "observation_id": "external-observation:...",
    "metric_key": "revenue",
    "value_kind": "amount|growth_rate",
    "report_year": 2026,
    "report_type": "annual|semiannual",
    "period_origin": "explicit_unit|card_context",
    "period_anchor_unit_id": "external-unit:...",
    "modality": "reported|forecast",
    "modality_anchor_unit_id": "external-unit:...",
    "lower_value": "220000.00",
    "upper_value": "240000.00",
    "precision": "10000.00",
    "unit": "万元|pct",
    "is_range": True,
    "external_evidence": [{...}],
}
```

External evidence contains only source id, document hash, block id, unit id,
unit hash, numeric citation refs, and citation publish time.

## 7. Period And Modality Context

Period parsing is explicit and conservative:

- `YYYY年全年`, `YYYY年度`, `YYYY年报`, or bare `YYYY年` without any
  quarter, half-year, month, or day token -> `annual`;
- `YYYY年上半年`, `YYYY年半年度`, or `YYYYH1` -> `semiannual`;
- quarter, first-three-quarter, month, day, and undated periods are
  unsupported. Unsupported tokens are checked before the bare-year rule, so
  `2026年7月7日` can never become an annual reporting period.

A period explicitly stated in an earlier unit may flow only to later units in
the same validated card. It never flows across cards, source blocks, or source
documents. The anchor unit id is retained.

Parser precedence is fixed: first select the last explicit annual or
semiannual reporting-period match in the unit; only when none exists do
quarter/month/day tokens block the bare-year fallback. Therefore
`7月7日披露2026年半年度业绩预告` yields 2026 semiannual, while
`2026年7月7日披露业绩预告` yields no reporting period. A later explicit
reporting period replaces inherited context.

`预计`, `预告`, `预测`, `指引`, and `有望` set forecast modality. Modality may
also flow forward only within the same card. `实际`, `实现`, `已实现`, and
`报告期内实现` reset inherited forecast context to reported modality, with the
resetting unit retained as the new modality anchor. Publish time never supplies
a missing report year or report type.

## 8. Numeric Parsing And Precision

Accepted forms are scalar or inclusive ranges with explicit units, for
example `22亿元`, `22至24亿元`, `8-10亿元`, `19.64%`, and
`19.64%至30.52%`.

`人民币`/`RMB` is accepted when stated. A clause containing `港元`, `美元`,
`美金`, `HKD`, or `USD` is rejected. When no currency marker is present,
Chinese `亿元`/`万元` is treated as CNY, matching the canonical filing-metric
contract.

Normalization uses `Decimal`. Commas are removed; NaN/infinity, signs without
digits, reversed ranges, mixed units, and more than one candidate value for the
same metric/kind/unit are rejected.

Metric aliases are matched longest-first. A clause starts at one metric alias
and ends before the next supported metric alias, preventing a revenue amount
from being assigned to net profit in a multi-metric sentence. Range grammar
accepts a shared trailing unit or the same unit on both endpoints; different
endpoint units are rejected. A leading minus belongs to a number, not a range
separator.

For scalar observations, the displayed decimal precision defines an implied
rounding interval. Example: `382.4亿元` has precision `0.1亿元` and represents
`382.35` through `382.45`亿元 for relation comparison. This is not a business
threshold; it is source-representation precision. Explicit ranges use their
stated inclusive endpoints without expansion.

## 9. Relation Algorithm

For each typed observation:

1. Find admitted filing candidates for the same metric, report year, and
   report type. Amounts target a filing point. Growth rates target the exact
   prior-year-to-current-year change.
2. If more than one value basis matches, emit `ambiguous_value_basis` and do
   not choose a preferred basis.
3. If exactly one target exists:
   - target inside the external range or scalar precision interval ->
     `confirm`;
   - target outside -> `contradict`.
   Forecast ranges use the same containment test; `relation_basis` records
   `forecast_range_contains_filing` or `forecast_range_excludes_filing`, so a
   contradiction means the forecast missed, not that the filing is false.
4. If there is no exact-period target and the external year is later than the
   latest admitted filing year for that metric, map `update` to that latest
   filing point with `relation_basis=newer_period_observation`. Values from
   different periods are not compared.
5. Same-year different report types, older external periods, missing filing
   metrics, and missing exact growth intervals remain unmapped.

One external observation creates at most one mapping. Multiple independent
external sources may each map to the same filing target; they are not collapsed
because their evidence identities differ.

Before any relation is built, the mapper rebuilds the deterministic financial
scan from the supplied MetricSeries pack and requires byte-equivalence with the
supplied `financial_scan_pack`. A stale or independently assembled scan fails
closed with `financial_scan_mismatch`; source counts alone are not considered
sufficient binding.

## 10. Mapping Contract

```python
{
    "mapping_id": "periodic-external-map:...",
    "relation": "confirm|contradict|update",
    "relation_basis": "...code...",
    "observation_id": "external-observation:...",
    "target_kind": "filing_point|metric_change",
    "target_id": "periodic:...|periodic-series:...:change:2024-2025",
    "metric_key": "revenue",
    "report_type": "annual",
    "value_basis": "as_reported",
    "target_periods": ["2025"],
    "target_value": "3824000.00",
    "external_lower_value": "3823500.00",
    "external_upper_value": "3824500.00",
    "unit": "万元",
    "input_refs": ["periodic:..."],
    "filing_evidence": [{...}],
    "external_evidence": [{...}],
    "linked_finding_ids": [],
    "adjudication": "none",
    "official_fact_mutated": False,
    "report_eligible": False,
    "scoring_eligible": False,
}
```

Exact growth mappings link any validated financial-scan finding whose
observation has the same metric and interval and whose input refs contain the
target change refs. Amount and update mappings do not infer finding links.

`confirm` and `contradict` are compatibility relations only. They do not rank
the external source above the filing, and the fixed `adjudication=none` and
`official_fact_mutated=false` fields prevent a later consumer from treating the
map as an automatic correction.

Unmapped rows contain only `observation_id`, metric/value kind/period identity,
unit id, and one fixed reason code. They never copy text.

Observation ids are SHA-256 identities over unit id, metric, value kind,
period, report type, modality, normalized bounds, precision, and extraction
ordinal. Mapping ids are SHA-256 identities over observation id, target id,
relation, and relation basis. Duplicate ids with different payloads fail
closed; identical duplicates collapse deterministically.

## 11. Pipeline Integration

`SynthesisSkill._build_curated_external_deep_analysis_display()` already runs
after periodic fulltext intake and validates the canonical external pack. After
an `ok` display is built, it calls the pure mapper when both
`periodic_report_metric_series_pack` and
`periodic_report_financial_scan_pack` exist, then writes:

```text
periodic_external_evidence_map
```

The display, evidence profile, Chapter 4, citation numbering, scoring, risk,
and recommendation do not read this key in Batch 4. External-only pipelines
without periodic intake remain unchanged and do not fabricate a map.

## 12. Determinism And Safety

- No LLM, embedding, fuzzy match, or generated summary.
- No source text in output.
- No mapping from peer/industry evidence to target facts.
- No period inference from publication time.
- No annualization of semiannual data.
- No preferred value basis when more than one basis is admissible.
- No relation from generic narrative direction words alone.
- All ids derive from validated identities and canonical numeric fields.
- All mappings/evidence/diagnostics are deduplicated and sorted.
- All eligibility fields remain false.

## 13. Failure Modes And Required Tests

| Failure mode | Required behavior |
|---|---|
| invalid MetricSeries or scan identity | unavailable complete pack |
| malformed/unvalidated external display | unavailable |
| peer or target-with-peer card contains target-like metric | never mapped |
| target card lacks financial family | out of scope |
| card-leading period/modal context | inherited only within card |
| explicit actual language follows forecast context | modality resets |
| period context would cross cards | second card remains unmapped |
| publication date plus explicit half-year | explicit half-year wins |
| quarter/month/day/undated claim | unmapped |
| foreign-currency amount | unmapped |
| revenue and profit in one unit | two metric observations |
| generic profit/income language | no observation |
| exact same-period scalar | confirm using precision interval |
| exact same-period explicit range | confirm/contradict by containment |
| same-period forecast range | relation basis says forecast result |
| newer explicit period | update without value comparison |
| same-year annual vs semiannual | unmapped |
| multiple filing value bases | ambiguous, no mapping |
| exact growth interval in finding | linked finding id |
| external order changes | byte-equivalent output |
| nested/prose payload supplied | no output leakage |
| periodic packs absent in pipeline | no context key fabricated |
| valid integrated inputs | context key present, no display mutation |

## 14. Files And Budget

Runtime:

- add `scripts/utils/periodic_external_evidence_map.py`;
- modify `scripts/utils/periodic_report_financial_scan.py` to expose/reuse one
  admitted-source reader;
- modify `scripts/utils/report_skills/synthesis_skills.py` only for context
  publication.

Tests:

- add `tests/utils/test_periodic_external_evidence_map.py`;
- modify `tests/utils/test_periodic_report_financial_scan.py`;
- modify `tests/reporter/test_synthesis_skills.py`.

Workflow documents may be added. No other runtime/config/data/Knowledge/report
file is in scope.

Runtime target is net +450 lines and hard stop is net +650 lines against
`cd80dec`. Tests and workflow documents do not count. If correctness requires
LLM comparison, fuzzy matching, report consumption, or a second MetricSeries
validator, stop and return to design.

## 15. Acceptance

1. Two design self-reviews are documented and repaired before implementation.
2. Every behavior starts with a failing test.
3. Focused mapper/scanner/synthesis tests pass.
4. Existing external v4, periodic, renderer, quality, and source-boundary
   suites pass.
5. Full offline pytest, CI gates, compilation, and `git diff --check` pass.
6. Canonical local v4 packs plus local annual caches produce a well-formed
   read-only mapping smoke without report/data/Knowledge writes.
7. Scope audit proves the new key has no report/scoring/risk consumer.
8. Implementation receives two post-code self-reviews; every defect found is
   captured by a failing regression test before repair.
