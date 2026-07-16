# Annual Producer v2 Coverage Repair - Codex Notes

## Scope

Implemented the approved source-only coverage-repair design without touching
report generation, renderers, scoring, target price, risk, technical analysis,
recommendation, LLM prompts, collection, configuration, raw data, or reports.

## Implemented

- Added the schema-owned `annual_checkbox_tail()` syntax helper and replaced
  the producer-local checkbox parser.
- Replaced material-pack note-level recovery with fragment-level exact coverage
  proof and `covered` / `actionable_uncovered` / `invalid_legacy` outcomes.
- Added diagnostics for covered, actionable, invalid, and cross-note duplicate
  legacy fragments while retaining `v1_needs_recovery_count` as the actionable
  compatibility alias.
- Adapted only actionable fragment text from mixed legacy notes.
- Replaced family-equality bundle stopping with continuation plus explicit
  independent-argument checks for technology, operating, financial, business,
  and market assertions.
- Kept checkbox family admission in the producer and exact SourceUnit matching
  in the material pack.

## Verification

- Focused annual-producer suite: `283 passed`.
- Downstream renderer/quality/source-boundary suite: `187 passed`.
- `bash tools/ci_grep_gates.sh`: passed.
- `git diff --check`: clean.
- Runtime delta relative to `aa7bdd9`, across the four governed runtime files:
  - `annual_argument_schema.py`: `+54`
  - `annual_report_material_pack.py`: `+84`
  - `periodic_report_evidence_pack.py`: `+30`
  - `periodic_report_narrative_evidence_cards.py`: `+91`
  - total: `+259`, below the `+270` hard stop.

## Eight-Stock Local-Cache Gate

Refreshed annual narrative cards with the local-cache preview command only. No
network access or report generation occurred. The worktree cache contained only
Black Sesame; the other seven refreshes used the pre-existing local main-repo
periodic-report cache.

| Stock | Actionable recovery fragments | Adapter uses |
| --- | ---: | ---: |
| Black Sesame | 6 | 3 |
| Changchun High-Tech | 0 | 0 |
| Sanhua Intelligent Controls | 0 | 0 |
| Zhongjian Technology | 5 | 4 |
| SGT Micro | 9 | 5 |
| Espressif | 18 | 11 |
| Zhongji Innolight | 2 | 1 |
| Fudan Microelectronics | 0 | 0 |

## Stop Condition

The gate requires zero `v1_actionable_needs_recovery_count` for every stock.
Five stocks remain nonzero, so the task stops here: do not generate reports,
archive v1 notes, or remove the v1 adapter.

The remaining fragments include concrete facts such as product roadmaps,
cash-flow explanations, product portfolios, lifecycle statements, and industry
competition observations. Reclassifying them as invalid solely to satisfy the
gate would lose source material and violate the design. The next task must
improve v2 SourceUnit/card coverage for those source blocks, then rerun this
same local-cache gate.
