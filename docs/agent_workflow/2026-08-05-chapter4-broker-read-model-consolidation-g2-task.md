# Chapter 4 Broker Read-Model Consolidation G2 Task

Implement the locked design in
`2026-08-05-chapter4-broker-read-model-consolidation-g2-design.md` against
baseline `77dd423`.

## Allowed Runtime Files

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

## Allowed Tests

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/test_runtime_hygiene.py`

## TDD Order

1. Add a failing snapshot test for lossless broker metric, period, range, and
   memo status; then add optional `MaterialRow` fields and adapter assignments.
2. Add failing formal-thin tests proving a prebuilt snapshot overrides a
   conflicting absent raw memo, generic attribution is not duplicated, empty
   rows fail closed, source order is stable, and refs use one global offset.
3. Replace the raw memo renderer with the row formatter and pass all broker
   snapshot rows to formal-thin without using the formal-medium selector.
4. Add hygiene assertions and remove `_broker_research_memo_section`,
   `_broker_row_author`, `_max_snapshot_ref`, and `broker_citation_offset`.
5. Run focused, reporter, full, CI, diff-check, and offline-smoke gates.

## Stop Conditions

- Runtime line count grows after tests are green.
- A forbidden file, memo schema, producer, prompt, selector, score, risk,
  technical, target-price, recommendation, data, knowledge, or report output
  must change.
- Formal-medium output or external citation IDs change.
- Title parsing, a second broker row type, a cap, or dedupe is introduced.

Write final evidence to
`docs/agent_workflow/2026-08-05-chapter4-broker-read-model-consolidation-g2-implementation-notes.md`.
