# Periodic Financial Consistency Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:test-driven-development` and execute each task in order. Every
> runtime behavior must be preceded by an observed failing test.

**Goal:** Add a compute-only, auditable cross-period financial scan over the
existing MetricSeries pack while preserving unique formula owners and report
behavior.

**Architecture:** Structured facts continue to own the cash-conversion formula
and weak-quality predicate. MetricSeries continues to own comparable periods and
growth. A new pure scanner validates typed identities, joins only exact
dimensions/intervals, and emits deterministic code-only findings. The intake
skill publishes the result; no downstream consumer is added.

**Tech Stack:** Python standard library (`Decimal`, `re`, collections), existing
pytest suite, SkillContext.

---

## File Map

Runtime:

- Modify `scripts/utils/periodic_report_structured_facts.py`: expose the current
  cashflow-quality predicate and keep its current risk builder on that owner.
- Modify `scripts/utils/periodic_report_metric_series.py`: lock safe value-basis
  ids and derived-series dimension grouping.
- Create `scripts/utils/periodic_report_financial_scan.py`: pure scan contract,
  admission, rules, deterministic output.
- Modify
  `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`: build
  and publish the scan pack from the in-memory MetricSeries result.

Tests:

- Modify `tests/utils/test_periodic_report_structured_facts.py`.
- Modify `tests/utils/test_periodic_report_metric_series.py`.
- Create `tests/utils/test_periodic_report_financial_scan.py`.
- Modify `tests/utils/test_periodic_report_fulltext_intake.py`.

## Task 1: Shared Cashflow-Quality Owner

### Files

- Modify `tests/utils/test_periodic_report_structured_facts.py`
- Modify `scripts/utils/periodic_report_structured_facts.py`

- [ ] Add a failing test importing
  `CASHFLOW_QUALITY_WEAK_THRESHOLD_PCT` and
  `is_cashflow_quality_weak`, asserting `49.99 -> True`, `50 -> False`, and
  `None -> False`.
- [ ] Run:

```bash
PYTHONPATH=.:scripts/utils PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_structured_facts.py \
  -q -p no:cacheprovider
```

Expected RED: import failure for the new public names.

- [ ] Add exactly one public threshold and predicate:

```python
CASHFLOW_QUALITY_WEAK_THRESHOLD_PCT = Decimal("50")


def is_cashflow_quality_weak(ratio_pct: Optional[Decimal]) -> bool:
    return ratio_pct is not None and ratio_pct < CASHFLOW_QUALITY_WEAK_THRESHOLD_PCT
```

- [ ] Replace the current inline `ratio_value < Decimal("50")` condition with
  the predicate. Do not alter rationale, severity, ids, or score eligibility.
- [ ] Re-run the focused test and confirm GREEN.

## Task 2: Repair Derived-Series Comparability

### Files

- Modify `tests/utils/test_periodic_report_metric_series.py`
- Modify `scripts/utils/periodic_report_metric_series.py`

- [ ] Add failing tests proving:
  1. an unsafe `value_basis` token is rejected;
  2. net-profit and OCF inputs with different bases reject the derived point
     with `derived_input_dimension_mismatch`;
  3. valid 2024 `as_reported` and 2025 `restated` derived points form two
     derived series, each with the exact basis-bearing id and payload.
- [ ] Run only those tests and observe RED against the current grouping.
- [ ] Add `_valid_value_basis()` using `[a-z][a-z0-9_]{0,63}` and use it during
  filing-fact admission.
- [ ] Make `_filing_point_index()` retain `value_basis`, `currency`, and `unit`
  from its parent series without mutating canonical point payloads.
- [ ] In `_validated_derived_row()`, require both indexed inputs to have one
  common `(value_basis, currency, unit)` tuple and return that basis.
- [ ] Group derived rows by `(report_type, value_basis)` and emit:

```text
periodic-derived-series:{stock}:{type}:operating_cash_flow_to_net_profit:
{basis}:cash_conversion.v1:pct
```

- [ ] Run all MetricSeries and structured-fact tests; confirm GREEN.

## Task 3: Scanner Pack Admission And Status

### Files

- Create `tests/utils/test_periodic_report_financial_scan.py`
- Create `scripts/utils/periodic_report_financial_scan.py`

- [ ] In the new test file, build source packs through
  `build_periodic_report_metric_series_pack()` rather than hand-writing valid
  MetricSeries payloads. Keep small mutation helpers for malformed-source tests.
- [ ] Add failing tests for:
  - wrong schema, stock mismatch, and eligibility leakage -> complete
    `unavailable` pack with one fixed diagnostic;
  - no points -> `empty`;
  - one admitted filing point -> `partial`;
  - duplicate source series ids -> reject every duplicate and diagnose once;
  - NaN/invalid point and malformed evidence hashes -> omit and diagnose.
- [ ] Run the new test module and observe RED from missing module/API.
- [ ] Implement constants, a complete `_empty_pack()` constructor, top-level
  admission, deterministic diagnostics, duplicate-id rejection, filing-point
  validation, and status/counters. Do not implement anomaly rules yet.
- [ ] Run the new module tests and confirm the admission/status subset GREEN.

## Task 4: Cross-Metric Divergence Rules

### Files

- Modify `tests/utils/test_periodic_report_financial_scan.py`
- Modify `scripts/utils/periodic_report_financial_scan.py`

- [ ] Add failing tests for:
  - revenue growth positive plus net-profit growth negative;
  - net-profit growth positive plus OCF growth negative;
  - both metrics moving in the same direction -> no finding;
  - different interval/report type/value basis -> no join;
  - exact input refs and compact source evidence union;
  - no prose-bearing key in recursive findings.
- [ ] Observe RED because findings are empty.
- [ ] Build an admitted change index keyed by:

```python
(report_type, value_basis, currency, unit, from_period, to_period, metric_key)
```

- [ ] Implement only the two sign rules from design. Build observations with
  explicit intervals and findings with sorted metrics/refs/evidence.
- [ ] Run the scanner module and confirm GREEN.

## Task 5: Reversal And Cashflow-Quality Rules

### Files

- Modify `tests/utils/test_periodic_report_financial_scan.py`
- Modify `scripts/utils/periodic_report_financial_scan.py`

- [ ] Add failing tests for positive-to-negative reversal,
  negative-to-positive recovery, zero/missing growth, and non-shared interval
  boundaries.
- [ ] Add failing tests for weak ratio, missing ratio after a loss,
  healthy-to-weak deterioration, weak-to-healthy recovery, non-consecutive
  ratio points, unresolved input refs, and basis-separated transitions.
- [ ] Observe RED for missing rule ids.
- [ ] Implement same-series adjacent-change reversal and recovery.
- [ ] Validate derived series/points and resolve both input refs to admitted
  filing points. Call `is_cashflow_quality_weak()`; never duplicate `50`.
- [ ] Implement weak point and exact consecutive transition findings.
- [ ] Add exact-finding-id collision removal/diagnostic and stable final sorting.
- [ ] Add determinism test by reversing source pack/list order and comparing
  full JSON structures. Confirm GREEN.

## Task 6: Intake Publication

### Files

- Modify `tests/utils/test_periodic_report_fulltext_intake.py`
- Modify
  `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`

- [ ] Add a failing skill test asserting
  `periodic_report_financial_scan_pack` is always present for a known stock,
  has the v1 schema, and is report/scoring ineligible.
- [ ] Add a failing no-cache test asserting a well-formed `empty` scan pack.
- [ ] Add a missing-stock regression asserting the skip path does not fabricate
  a scan pack because no entity identity exists.
- [ ] Observe RED for the absent context key.
- [ ] Import the pure builder, call it immediately after MetricSeries is built,
  and write the context key. Do not read caches again.
- [ ] Run intake plus scanner tests and confirm GREEN.

## Task 7: Two-Pass Implementation Self-Review And Acceptance

- [ ] Self-review pass 1: audit identity, dimensions, missing-data semantics,
  exact refs, and duplicate handling. Add failing regression tests for every
  issue found, then fix.
- [ ] Self-review pass 2: audit non-finite values, deterministic order, recursive
  prose leakage, annual/semiannual isolation, and no second threshold/formula.
  Add failing regression tests for every issue found, then fix.
- [ ] Run focused suites:

```bash
PYTHONPATH=.:scripts/utils PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/utils/test_periodic_report_structured_facts.py \
  tests/utils/test_periodic_report_metric_series.py \
  tests/utils/test_periodic_report_financial_scan.py \
  tests/utils/test_periodic_report_fulltext_intake.py \
  -q -p no:cacheprovider
```

- [ ] Run downstream extraction/material/synthesis/renderer/source tests selected
  from the existing Batch 2 acceptance set.
- [ ] Run full offline pytest, `bash tools/ci_grep_gates.sh`, module compilation,
  and `git diff --check`.
- [ ] Run read-only local-cache smoke for 中际旭创 and 黑芝麻智能. Do not use
  network, LLM, browser, Knowledge writes, or report generation.
- [ ] Audit with `rg` that the new context key is written by intake/tests only
  and not read by report, score, risk, target, or Knowledge code.
- [ ] Write
  `docs/agent_workflow/2026-07-24-periodic-financial-consistency-scan-codex-notes.md`
  with RED/GREEN evidence, self-review repairs, tests, runtime delta, smoke
  output, warnings, and final verdict.
- [ ] Commit the accepted Batch 3 checkpoint as:

```text
feat: add periodic financial consistency scan
```
