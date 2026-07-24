# Periodic Financial Consistency Scan - Codex Notes

## Verdict

Accepted. Batch 3 is compute-only, deterministic, and has no report, scoring,
risk, target, technical-analysis, recommendation, Knowledge, or prompt
consumer.

## Implemented

- Exposed the existing cashflow-quality threshold and predicate from
  `periodic_report_structured_facts.py`; the existing risk signal and the new
  scanner share that single owner.
- Repaired MetricSeries derived-point comparability by validating
  `value_basis`, requiring matching input dimensions, and grouping derived
  series by `(report_type, value_basis)`.
- Added `periodic_report_financial_scan.py` with a complete v1 pack contract,
  strict typed admission, deterministic diagnostics, and seven code-only
  rules:
  - revenue growth with profit contraction;
  - profit growth with operating-cash-flow contraction;
  - growth direction reversal;
  - growth direction recovery;
  - weak cashflow quality;
  - cashflow-quality deterioration;
  - cashflow-quality recovery.
- Published `periodic_report_financial_scan_pack` immediately after the
  in-memory MetricSeries build in periodic fulltext intake.

## TDD Evidence

- Task 1: 3 import failures RED; shared threshold/predicate GREEN.
- Task 2: 3 derived-basis contract failures RED; all structured-fact and
  MetricSeries tests GREEN.
- Task 3: missing scanner module RED; admission/status tests GREEN.
- Task 4: two missing divergence findings RED; cross-metric rules GREEN.
- Task 5: six missing reversal/cashflow findings RED; all seven rule families
  GREEN.
- Task 6: two absent intake context values RED; intake publication GREEN.

## Implementation Self-Review 1

The identity/dimension/missing-data pass found four contract defects. Each was
captured by a failing regression test before repair:

1. empty filing series was counted as admitted;
2. `1000.000` filing values were silently rounded instead of rejected;
3. `10.000%` growth values were silently rounded instead of rejected;
4. derived-point evidence could be unrelated to its two filing inputs.

Repairs require non-empty series, exact canonical two-decimal input strings,
and exact equality between derived evidence and the union of the resolved net
profit/operating-cash-flow input evidence. Focused result after repair:
`91 passed`.

## Implementation Self-Review 2

The determinism/leakage/owner pass found two fail-closed defects and one test
gap:

1. a non-scalar schema was stringified into the unavailable pack;
2. nested upstream diagnostic or malformed series-identity payloads could pass
   through diagnostics;
3. annual/semiannual join isolation lacked a direct regression fixture.

Repairs accept only a string source schema and compact scalar diagnostic
identity values. Nested payloads are dropped. The mixed report-type fixture
passes without a cross-metric finding. Focused result after repair:
`94 passed`.

The audit also confirmed that the scanner contains no copied 50% threshold,
does not recompute cash conversion, does not parse source prose, and does not
infer missing ratios as healthy or weak.

## Verification

- Focused structured-fact/MetricSeries/scanner/intake: `94 passed`.
- Downstream extraction/material/synthesis/renderer/quality/source boundary:
  `342 passed`.
- Full offline suite: `2690 passed, 16 skipped`.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- Module compilation: passed.
- `git diff --check`: clean.
- Scope audit: only periodic fulltext intake writes the new context key; tests
  inspect it; no downstream runtime reads it.

## Read-Only Cache Smoke

Cache root: `/Users/erichan/testsnow/data/raw/periodic_reports`.

- 中际旭创: 2 filing series, 2 points, `partial`, 0 comparable intervals,
  0 findings; diagnostics preserve missing net-profit ratio input and an
  unanchored filing fact.
- 黑芝麻智能: 2 filing series, 2 points, `partial`, 0 comparable intervals,
  0 findings; diagnostics preserve missing net-profit ratio input and a
  missing required metric.

Only one annual cache exists for each stock, so `partial` and zero findings are
the correct result. No network, LLM, browser, report generation, Knowledge
write, or cache mutation occurred.

## Delta And Scope

Runtime delta against the Batch 2 checkpoint:

- new scanner: +824 lines;
- MetricSeries: +27 / -6;
- structured facts: +10 / -1;
- intake skill: +8 / -0;
- total runtime net: +862 lines.

Test delta:

- new scanner tests: +694 lines;
- existing focused tests: +134 lines;
- total test net: +828 lines.

The locked design had no line budget. The larger scanner is isolated and
contains validation, deterministic evidence identity, and seven rule families;
no existing owner was duplicated. No file outside the approved runtime, test,
and workflow-document scope changed.

## Blockers / Warnings / Deviations

- Blockers: none.
- Warnings: representative local caches contain only one year, so real
  cross-year findings cannot be demonstrated until additional annual caches
  are present. Synthetic contract fixtures cover all rules and transitions.
- Deviations: none.
