# Technical Analysis v2 Phase 2.2 Compression Plan

## Task 1: Characterize The Accepted Behavior

1. Run structure-path and trend-health tests.
2. Run state-machine and downstream identity tests.
3. Run renderer and report-quality tests.
4. Record the five-file runtime delta against `fdd0941`.

## Task 2: Remove Proven Duplication

1. Prove `_is_support_resistance` has no callers or exports with a repository-wide static search.
2. Delete the zero-call helper; do not add a test that locks a private implementation name.
3. Import and use the existing ATR implementation from `technical_indicators`; delete `_atr_series`.
4. Run structure and pattern behavior tests.

## Task 3: Consolidate Scenario Provenance

1. Preserve existing state-machine behavior tests as characterization tests.
2. Replace `_scenario_source_value` branching and `_scenario_candidate` with one resolver backed by a source specification map.
3. Use the resolver in both ladder creation and cache validation.
4. Keep exact source values, persisted `source_field`, side filtering, ordering, and dedupe unchanged.
5. Run state-machine and downstream tests.

## Task 4: Verify Budget And Quality

1. Measure runtime delta after each refactor.
2. Stop if the result exceeds `+360` or requires behavior changes.
3. Run focused technical suites, full pytest, CI grep gates, and `git diff --check`.
4. Write a separate read-only refactor audit with ranked future candidates.

## Completion Criteria

- All accepted Phase 2.2 tests pass.
- No scoring, risk, target, recommendation, collection, or report-output behavior changes.
- Runtime delta is at most `+360` against `fdd0941`.
- No new dead helper or duplicate scenario owner is introduced.
