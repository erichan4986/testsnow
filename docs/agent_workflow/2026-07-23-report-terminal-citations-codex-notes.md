# Report Terminal Citations Codex Notes

## Result

- Verdict: PASS
- Formal report generation: deferred and intentionally not run
- Commit/push: not performed

## Runtime Changes

- `deep_analysis_renderer.py`: removed section-local source lists and their dead accumulators/parameters; inline refs, citation merging, offsets, reserved aliases, visible filtering, and the sole global table remain owned here.
- `assembly_skills.py`: detaches that sole table from the deep-analysis renderer and appends it after risk and before the legal footer; competing global owners and residual local lists fail closed.
- `report_prose_quality.py`: resolves 4.4 refs against the terminal table so same-source warnings survive the layout change without treating repeated use of one ref as duplication.

## TDD Evidence

- Renderer RED: 2 failures for legacy/addendum local lists; GREEN: full renderer module passed.
- Assembly RED: 6 failures for missing detachment, order, and ownership checks; GREEN: `29 passed`.
- Prose RED: 2 failures for terminal URL/no-URL duplicate resolution; GREEN: `17 passed`.
- Combined citation modules: `117 passed`.

## Verification

- Formal-thin full-snapshot offset and reserved-ref focused checks: `4 passed`.
- Report quality/source boundary/prose: `133 passed`.
- Technical Analysis v2 Phase 2.3A focused regression: `84 passed`.
- Full offline suite: `2609 passed, 16 skipped`.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.

## Runtime Budget

Against `f17b859`, citation runtime numstat:

| File | Added | Removed | Net |
|---|---:|---:|---:|
| `report_prose_quality.py` | 35 | 15 | +20 |
| `assembly_skills.py` | 22 | 2 | +20 |
| `deep_analysis_renderer.py` | 5 | 73 | -68 |
| **Total** | **62** | **90** | **-28** |

The batch is below both the target of net non-growth and the `+60` hard stop. Combined with Phase 2.3A, the six runtime files are net `+109` (`+137 - 28`).

## Scope Audit

- No citation IDs, source identities, offsets, source selection, Chapter 4 prose, scoring, target price, risk, recommendation, technical formula, or LLM prompt changed.
- No data, knowledge notes, or reports were modified.
- Existing dirty-worktree changes were preserved.

## Deferred Acceptance Gate

Generate fresh reports once for the two bundled batches and verify that each has exactly one `## 引用来源`, located after `## 综合风险评分` and before the disclaimer, with no `本节引用来源` marker and no missing/unused refs.
