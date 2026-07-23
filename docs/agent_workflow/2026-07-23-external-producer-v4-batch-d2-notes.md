# External Producer v4 Batch D2 Completion Notes

Date: 2026-07-23
Status: accepted pending user commit decision
Branch: `codex/pipeline-stabilization`

## Scope Completed

- changed the structured external-risk provenance label from the stale
  `curated_external_argument_v3` to version-neutral `curated_external_argument`;
- extended the existing v4 cutover test into the sole static guard for retired external imports/literals,
  public-contract ownership, and the single display-envelope writer;
- merged duplicate selector-incomplete and source-input-degraded pack construction into `_failure_pack`;
- removed the zero-value `_build_target_cards` wrapper;
- added characterization assertions for failure-pack document and diagnostics contracts.

No selector, schema, prompt, source acquisition, canonical pack, config, data, knowledge, report, scoring,
technical-analysis, target-price, recommendation, or risk-score behavior changed.

## RED / GREEN Evidence

### Task 1: Version-neutral provenance and cutover guard

RED:

- `test_assembly_collects_structured_risk_card_without_changing_risk_score_input` failed with
  `curated_external_argument_v3 != curated_external_argument`.
- `test_runtime_has_no_retired_external_pipeline_references` failed with the same literal in
  `utils/report_skills/assembly_skills.py`.

GREEN:

- the targeted assembly test passed: `1 passed`;
- the v4 cutover/owner test passed: `2 passed`.

### Task 2: Failure-pack contract preservation

Characterization baseline before refactor:

- selector-incomplete retains validated `source_documents`, empty `cards`, empty `citations`, and exactly one
  rejection reason;
- source-input-degraded retains no `source_documents` and has no `rejection_reasons` key.

GREEN after refactor:

- `tests/utils/test_external_pack.py`: `16 passed`;
- final direct core regression (`external_pack`, cutover, recommendation): `46 passed`.

## Verification

- focused/downstream suite: `246 passed in 6.93s`;
- full offline suite: `2577 passed, 16 skipped in 50.53s`;
- `bash tools/ci_grep_gates.sh`: all gates passed;
- `git diff --check`: clean.

## Ownership Audit

- `_curated_external_argument_cards` has exactly one active dictionary writer:
  `scripts/utils/curated_external_display.py`;
- no active runtime hit for `curated_external_argument_v2`, `curated_external_argument_v3`, v2/v3 argument-pack
  schemas, or `curated_external_to_synthesis_items`;
- `test_external_v4_cutover.py` additionally asserts the unique scope, family, builder/reader, and display-owner
  functions by AST.

## Runtime Numstat

| File | Added | Removed | Net |
|---|---:|---:|---:|
| `scripts/utils/external_pack.py` | 21 | 23 | -2 |
| `scripts/utils/report_skills/assembly_skills.py` | 1 | 1 | 0 |
| Total runtime | 22 | 24 | -2 |

Test changes add regression coverage but are not part of the runtime budget.

## Blocker / Warning / Deviation

- Blocker: none.
- Warning: no report rerun was performed by design; D2 changes only provenance metadata and pack construction
  deduplication, and snapshot/renderer downstream contracts are in the focused suite.
- Deviation: none.

## Post-Review Narrow Repair

- renamed the final stale `v3`-worded assembly test;
- reformatted `_failure_pack` calls and signature without changing runtime line count;
- replaced an unnecessary second top-level document copy with `list(source_documents)`, preserving the validated
  document objects supplied by the existing validation path;
- retained the original equality-based public contract test because `_valid_source_documents` already copies raw
  input mappings before pack construction; raw-input object identity was never the old public contract.

## Final State

The External Producer v4 Batch D deletion/compression exit gate is complete: active runtime has one scope owner,
one family owner, one strict pack reader/builder owner, and one display-envelope writer. Runtime is net-negative and
all required tests/gates pass.
