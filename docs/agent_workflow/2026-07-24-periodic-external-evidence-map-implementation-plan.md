# Periodic External Evidence Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and `superpowers:test-driven-development`.
> Execute tasks in order and observe every RED before implementation.

**Goal:** Deterministically map validated target-company external financial
observations to admitted periodic filing points/changes as confirm,
contradict, or update, with optional exact financial-finding links.

**Architecture:** The financial scanner exposes and reuses one sanitized
MetricSeries reader. A new pure mapper consumes that read model, an exactly
recomputed scan, and a previously validated external display. It emits only
typed identities and numbers. Synthesis publishes the result without any
display, score, risk, or recommendation consumer.

**Tech Stack:** Python standard library (`Decimal`, `hashlib`, `re`), existing
v4 external display contract, MetricSeries/financial scan, pytest.

---

## File Map

Runtime:

- Modify `scripts/utils/periodic_report_financial_scan.py`: public admitted
  source reader shared by scan and mapper.
- Create `scripts/utils/periodic_external_evidence_map.py`: external typed
  observation parsing, exact relation mapping, output contract.
- Modify `scripts/utils/report_skills/synthesis_skills.py`: publish the map
  after an ok curated external display.

Tests:

- Modify `tests/utils/test_periodic_report_financial_scan.py`.
- Create `tests/utils/test_periodic_external_evidence_map.py`.
- Modify `tests/reporter/test_synthesis_skills.py`.

## Task 1: Shared Scanner Source Reader

### Files

- Modify `tests/utils/test_periodic_report_financial_scan.py`
- Modify `scripts/utils/periodic_report_financial_scan.py`

- [ ] Add a failing import/test for
  `read_periodic_financial_scan_source()`. Build a valid mixed filing/derived
  MetricSeries fixture and assert status, sanitized series, and diagnostics.
- [ ] Add a regression that mutates duplicate ids and malformed points, then
  asserts the reader rejects exactly the rows the scan builder rejects.
- [ ] Snapshot `build_periodic_report_financial_scan_pack()` before the
  refactor and assert its full output is unchanged after using the reader.
- [ ] Run:

```bash
PYTHONPATH=.:scripts/utils PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_financial_scan.py -q -p no:cacheprovider
```

  Expected RED: missing public reader.
- [ ] Move top-level source admission, duplicate-id rejection, filing/derived
  admission, and compact diagnostics into the reader. Make the scan builder
  call it. Do not change rule functions or pack schema.
- [ ] Re-run and confirm all existing scanner tests plus reader tests GREEN.

## Task 2: Mapper Admission And Typed Observations

### Files

- Create `tests/utils/test_periodic_external_evidence_map.py`
- Create `scripts/utils/periodic_external_evidence_map.py`

- [ ] Add helpers that create source facts through
  `build_periodic_report_metric_series_pack()`, a scan through
  `build_periodic_report_financial_scan_pack()`, and external display through
  canonical v4 document/pack/display builders. Do not hand-author a valid
  display envelope.
- [ ] Add failing pack tests for invalid MetricSeries, mismatched scan,
  malformed display, no target units, and no periodic source. Assert complete
  unavailable/empty contracts and all eligibility flags false.
- [ ] Add failing entity-boundary tests proving peer and
  target-with-peer cards never create observations/mappings.
- [ ] Add failing extraction tests for:
  - period/modality inherited within one card;
  - no inheritance across cards;
  - publication date plus explicit half-year precedence;
  - explicit actual language resetting forecast modality;
  - revenue and net profit in one unit;
  - amount plus同比 rate in one clause;
  - longest metric aliases and generic-term rejection;
  - RMB/no-marker acceptance and HKD/USD rejection;
  - scalar/range grammar, negative values, reversed/mixed ranges, and exact
    precision normalization.
- [ ] Run the new test module. Expected RED: missing mapper module/API.
- [ ] Implement the complete top-level pack constructor, input checks, target
  card walk, card-local context, metric clause splitting, period/modality
  parsing, amount/rate parsing, compact external evidence, observation ids,
  deterministic collision resolution, and unmapped reason rows.
- [ ] Re-run the extraction/admission subset and confirm GREEN before relation
  logic is added.

## Task 3: Confirm, Contradict, Update, And Finding Links

### Files

- Modify `tests/utils/test_periodic_external_evidence_map.py`
- Modify `scripts/utils/periodic_external_evidence_map.py`

- [ ] Add failing same-period amount tests for exact scalar, rounded scalar,
  containing range, excluding range, and forecast-range relation-basis codes.
- [ ] Add failing same-period同比 tests for confirm and contradict against one
  exact MetricSeries change.
- [ ] Add failing update tests proving a later explicit year maps to the latest
  filing point without numeric comparison, while same-year mixed report type
  and older periods remain unmapped.
- [ ] Add failing ambiguity tests for multiple value bases and missing exact
  growth intervals.
- [ ] Add a failing finding-link test where an exact external growth
  observation agrees with a growth observation participating in a financial
  scan finding. Add a negative test for amount/update observations.
- [ ] Add full-output determinism tests under card, unit, series, and citation
  order permutations, plus duplicate-id collision fixtures.
- [ ] Observe RED, then implement exact target indexes, representation-precision
  containment, relation construction, update selection, finding-link indexing,
  deterministic ids, dedupe/collision handling, counters, and status.
- [ ] Recursively assert mappings/unmapped/diagnostics contain no forbidden
  prose-bearing key or nested payload. Confirm GREEN.

## Task 4: Pipeline Publication Without Consumption

### Files

- Modify `tests/reporter/test_synthesis_skills.py`
- Modify `scripts/utils/report_skills/synthesis_skills.py`

- [ ] Add a failing unit test around
  `_build_curated_external_deep_analysis_display()` using a canonical v4 pack
  file plus periodic MetricSeries/scan context. Assert the display remains
  byte-equivalent and `periodic_external_evidence_map` is added.
- [ ] Add failing regressions for absent periodic packs and non-ok external
  display: no fabricated map key.
- [ ] Observe RED, import the mapper in both package import branches, and call
  it only after display status `ok` and only when both periodic packs exist.
- [ ] Set the context key. Do not mutate display, evidence profile, citations,
  or synthesis text.
- [ ] Run focused mapper/scanner/synthesis tests and confirm GREEN.

## Task 5: Two-Pass Implementation Self-Review

- [ ] Review 1: entity ownership, period context, report-type/value-basis
  ambiguity, scan binding, numeric precision, and exact refs. For every defect,
  add a failing regression test before repair.
- [ ] Review 2: order invariance, hash collisions, non-finite/nested values,
  prose leakage, foreign currency, eligibility flags, and scope consumers. For
  every defect, add a failing regression test before repair.
- [ ] Measure runtime delta against `cd80dec` after each pass. Stop if net
  runtime exceeds +650 lines.

## Task 6: Acceptance

- [ ] Run focused tests:

```bash
PYTHONPATH=.:scripts/utils PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_financial_scan.py \
  tests/utils/test_periodic_external_evidence_map.py \
  tests/reporter/test_synthesis_skills.py \
  -q -p no:cacheprovider
```

- [ ] Run external v4, periodic, renderer, quality, and source-boundary
  downstream suites.
- [ ] Run full offline pytest, CI grep gates, module compilation, and
  `git diff --check`.
- [ ] Run read-only local smoke using canonical 中际旭创/复旦微电/黑芝麻智能
  v4 packs and available local annual caches. No network, LLM, browser, report,
  Knowledge, data, or config writes.
- [ ] Audit with `rg` that only Synthesis writes the new context key and no
  renderer/scoring/risk/target/recommendation code reads it.
- [ ] Write
  `docs/agent_workflow/2026-07-24-periodic-external-evidence-map-codex-notes.md`
  with RED/GREEN evidence, two implementation self-review repairs, tests,
  runtime delta, smoke output, and verdict.
- [ ] Commit accepted Batch 4 as:

```text
feat: map external evidence to periodic facts
```
