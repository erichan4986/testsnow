# Formal-Medium Chapter 4.4 Retirement Implementation Notes

日期：2026-07-23
状态：accepted

## Modified Files

Runtime:

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Tests:

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`

Workflow:

- `docs/agent_workflow/2026-07-23-formal-medium-chapter44-retirement-implementation-plan.md`
- this notes file

## RED / GREEN Evidence

### View-Model Contract

RED:

- 3 migrated 4.3/citation tests passed.
- `test_formal_medium_view_model_unifies_source_layers_and_visible_citations` failed because runtime returned `['4.1', '4.2', '4.3', '4.4']` instead of the required three-section tuple.

GREEN:

- Removed formal-medium 4.4 construction and the dedicated price-path selectors.
- `tests/utils/test_deep_analysis_material_snapshot.py`: `48 passed`.

### Public Renderer Contract

RED:

- `test_formal_medium_public_render_ends_after_external_variables` failed through public `DeepAnalysisRenderer.render()` with `KeyError: '4.4'` at the stale renderer lookup.

GREEN:

- Removed the stale lookup and `_formal_medium_price_path_section()` fixed template.
- `tests/reporter/test_deep_analysis_renderer.py`: `69 passed`.

## Verification

- Focused snapshot + renderer: `117 passed in 1.17s`.
- Report quality + source boundary + prose quality: `129 passed in 0.56s`.
- Full offline suite: `2596 passed, 16 skipped in 51.66s`.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.

## Runtime Numstat

| File | Added | Removed | Net |
|---|---:|---:|---:|
| `deep_analysis_material_snapshot.py` | 1 | 40 | -39 |
| `deep_analysis_renderer.py` | 0 | 60 | -60 |
| **Runtime total** | **1** | **100** | **-99** |

The batch remains within the designed deletion range of -85 to -105 runtime lines.

## Profile Contracts

- `formal_medium`: `Chapter4ViewModel.sections` now contains only 4.1, 4.2, and 4.3; public renderer output has no 4.4 heading or generic condition template.
- `formal_thin_external_rich`: both full-snapshot citation-offset tests pass and now explicitly assert no 4.4.
- `formal_rich`: existing legacy sourced `### 4.4 外部观点与待验证变量（Preview）` fixtures remain unchanged and pass.
- Material snapshot rows and citation allocation are unchanged; only the display projection was removed.

## Blocker / Warning / Deviation

- Blocker: none.
- Warning: none specific to this implementation; fresh report prose gates retain existing non-blocking theme warnings.
- Deviation: none.

Fresh-report acceptance: PASS. See `2026-07-23-chapter44-retirement-and-external-v4-d1-report-acceptance.md`.
