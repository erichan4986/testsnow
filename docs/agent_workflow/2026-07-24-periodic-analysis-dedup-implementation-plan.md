# Periodic Analysis Dedup Implementation Plan

> Execute inline with TDD. Preserve every existing public contract and stop on
> the runtime budgets in the locked design.

**Goal:** Remove narrow contract duplication and repeated per-run cache parsing
without changing accepted annual-analysis behavior.

**Architecture:** Batch A extracts only evidence identity and finite Decimal
conversion. Batch B materializes cache files once inside the intake pipeline and
projects the existing outputs from those prepared rows.

## Task 1: Contract primitives (Batch A)

**Files:**
- Create `scripts/utils/periodic_report_contract_utils.py`
- Create `tests/utils/test_periodic_report_contract_utils.py`
- Modify `scripts/utils/periodic_report_metric_series.py`
- Modify `scripts/utils/periodic_report_financial_scan.py`
- Modify `scripts/utils/periodic_external_evidence_map.py`

1. Add tests proving finite-only Decimal conversion and deterministic four-field
   evidence deduplication across multiple groups.
2. Run the new test and confirm RED because the module does not exist.
3. Implement the two primitives only.
4. Replace the three local evidence merge functions and local generic Decimal
   conversions; retain every caller-specific regex, suffix, precision, and
   negative-zero rule.
5. Run the new test plus MetricSeries, FinancialScan, and ExternalMap tests.
6. Measure `scripts/` numstat against `d1be180`; stop if Batch A is not net
   negative.

## Task 2: One-run cache materialization (Batch B)

**Files:**
- Modify `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- Modify `tests/utils/test_periodic_report_fulltext_intake.py`

1. Add a pipeline test with two local annual caches. Count `Path.read_text` and
   `build_periodic_report_evidence_pack` calls. Assert one read per file, one
   structured evidence build per valid file, and exactly one separate display
   evidence build for the latest file.
2. Run that test and confirm RED from repeated reads/builds.
3. Add one private path-identified material loader and projections for the six
   existing outputs. Preserve mtime/path latest selection and period/path series
   ordering.
4. Delegate public cache wrappers to the private material/projection path while
   preserving signatures and direct-call behavior.
5. Add/retain fixtures for semiannual display-vs-structured report type, mixed
   valid/read-failed files, no cache, and equal-mtime path tie-breaking.
6. Run the full intake test file and architecture suite.
7. Measure Batch B runtime delta; stop above `+30`, and accept line-neutral only
   when the call-count test passes.

## Task 3: Verification and acceptance

1. Run all ten architecture test files.
2. Run the full offline pytest suite.
3. Run `bash tools/ci_grep_gates.sh`, Python compilation, and
   `git diff --check`.
4. Run `scripts/run_黑芝麻智能.py --fast-test` without network/LLM refresh. If
   local market/PDF environment blocks the entry, record it and run the report
   quality/source/prose checks on any fresh Markdown that was produced.
5. Record runtime/test/docs numstat, removed helpers, behavior parity, warnings,
   and remaining opportunities in
   `docs/agent_workflow/2026-07-24-periodic-analysis-dedup-acceptance.md`.
