# External Producer v4 Batch D1 Dead Bridge Removal Notes

日期：2026-07-23
状态：accepted

## Scope

Batch D1 removes the preview-era curated-external-to-synthesis bridge after the v4 canonical pack and display-envelope cutover.

Deleted:

- `scripts/utils/curated_external_to_synthesis_items.py` — 248 lines
- `tests/utils/test_curated_external_to_synthesis_items.py` — 238 lines

Retained:

- `scripts/utils/curated_external_full_body_viewpoint_claims.py`, because preview, source-packet and selection callers still import it.
- all v4 source document, scope, pack, narrative-plan and report-adapter modules.

## Call-Graph Proof

Repository search for the module and its three public functions found only the deleted module and its exclusive test file. No entry script, report skill, preview, config or runtime module imported the bridge.

Post-deletion search returns zero non-workflow matches for:

- `curated_external_to_synthesis_items`
- `build_curated_external_synthesis_items`
- `build_curated_external_synthesis_markdown`
- `map_source_kind_to_topic`

## Verification

- Pre-deletion exclusive tests: `20 passed`.
- Focused v4 + Chapter 4 contracts: `164 passed`.
- Full offline suite after deletion: `2576 passed, 16 skipped in 53.06s`.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.

## Result

- Runtime net change: `-248` lines.
- Test net change: `-238` lines.
- No replacement adapter or compatibility branch was added.
- Blocker: none.
- Warning: none specific to D1; combined fresh-report acceptance passed.
- Deviation: none.

Combined fresh-report acceptance: PASS. See `2026-07-23-chapter44-retirement-and-external-v4-d1-report-acceptance.md`.
