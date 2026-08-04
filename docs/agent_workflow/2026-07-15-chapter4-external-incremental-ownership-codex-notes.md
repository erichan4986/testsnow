# Chapter 4 External Incremental Ownership - Codex Notes

## Result

- status: implemented
- scope: snapshot selector plus formal-medium/formal-thin renderer wiring
- network/report generation: not run
- producer, profile, quality gates, scoring, target, risk, technical, recommendation, prompts: unchanged

## RED / GREEN

1. Baseline: snapshot + renderer focused suite, `135 passed`.
2. RED: new public selector import failed during collection.
3. GREEN: snapshot selector tests, `29 passed` at first green.
4. RED: two formal-thin integration tests failed because checklist rendering still used the local curated projection.
5. GREEN: snapshot-global external rows and baseline-only citation offset, `2 passed`.
6. Final focused/downstream: `367 passed`.

## Requirement-Test Matrix

| Requirement | Implementation | Test evidence |
|---|---|---|
| External rows must add information relative to visible annual/broker owners | `select_incremental_external_display_rows()` | exact duplicate, shared theme, event delta, new anchor, new context fixtures |
| Long external claim may retain an owner clause when it adds a condition | asymmetric containment in `_external_incremental_reason()` | owner-superset-with-event fixture |
| Bucket priority applies after delta filtering | selector continues narrative -> reasoning -> topic | rejected narrative / accepted reasoning fixture |
| Formal-medium 4.4 consumes only selected 4.3 external rows | view model passes selected external rows to `_select_price_path_rows()` | rejected external absent from 4.3 and 4.4 fixture |
| Formal-thin owners include every rendered broker memo row | renderer constructs owner rows from all renderable snapshot broker rows | seven-broker-row fixture |
| Formal-thin snapshot refs receive only the Chapter 4 baseline offset | checklist map renders MaterialRows with `annual_citation_offset` | expected ref 18, forbidden double-offset ref 29 fixture |
| Empty incremental selection is distinct from missing collection | both layouts use the incremental-empty copy | formal-medium and formal-thin empty fixtures |
| Formal-rich and legacy thin remain on curated projection | old `_external_viewpoint_map_section()` path retained | full renderer suite |

## Runtime Ledger

Independent pre-batch replacement ledger (tests/docs excluded):

| Runtime file | Net |
|---|---:|
| `deep_analysis_material_snapshot.py` | +89 |
| `deep_analysis_renderer.py` | +14 |
| Total | +103 |

The total is below the `+120` hard stop. The existing external eligibility,
bucket order, citation identity dedupe, and price-path selector remain single
owners; no parallel selector was added.

## Verification

- focused + downstream: `367 passed in 3.75s`
- `bash tools/ci_grep_gates.sh`: all gates passed
- `git diff --check`: clean
- `py_compile` for both runtime files: passed

## Blocker / Warning / Deviation

- blocker: none
- warning: formal report generation is intentionally deferred to local acceptance
- deviation: none
