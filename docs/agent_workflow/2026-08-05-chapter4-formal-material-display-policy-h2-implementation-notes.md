# Chapter 4 Formal Material Display Policy H2 Implementation Notes

## Result

`implemented`

The user-approved Claude review waiver was used. Codex retained two self-review
rounds, TDD, focused/full tests, CI gates, and report verification.

## Modified Runtime

- `scripts/utils/deep_analysis_material_snapshot.py`
  - annual cleaner is normalization-only; no 300-character snapshot cut;
  - admitted broker projection retains all guarded, deduplicated loader items;
  - a non-empty guarded broker selection is admitted as the existing
    `single_institution` state.
- `scripts/utils/report_skills/synthesis_skills.py`
  - coverage `memo_row_count` follows the admitted broker count instead of the
    compatibility-era `min(6, usable)` cap.

No producer, renderer, profile branch, scoring, target price, risk,
technical-analysis, recommendation, or LLM prompt code was changed.

## TDD Evidence

RED focused run:

- four new H2 tests failed as expected: annual body was still cut to 288
  characters, broker rows/citations remained at 6, one broker card remained
  absent, and coverage remained at 6.

GREEN focused run:

- H2 behavior tests: `4 passed`;
- sparse broker duplicate-versus-new-anchor regression: `1 passed`;
- affected focused suites: `270 passed`.

## Full Verification

- Full pytest: `2860 passed, 10 skipped`;
- `bash tools/ci_grep_gates.sh`: all gates passed;
- `git diff --check`: clean.

## Runtime Delta

Against `e504cb9`:

| File | Added | Removed | Net |
|---|---:|---:|---:|
| `deep_analysis_material_snapshot.py` | 326 | 91 | +235 |
| `synthesis_skills.py` | 34 | 392 | -358 |
| Combined | 360 | 483 | **-123** |

H2 itself reduces the H1 runtime baseline by another 12 lines. No third
formal-material projection path was introduced.

## Report Verification

Local-cache `--fast-test --no-pdf` entries completed with exit code 0:

- `reports/中际旭创_20260805.md` and `.html`;
- `reports/复旦微电_20260805.md` and `.html`;
- `reports/黑芝麻智能_20260805.md` and `.html`.

Source-boundary checks: all three PASS.

Prose checks: all three PASS with existing warnings only.

`check_report_quality.py` failed for all three because the current environment
could not reach the market-data providers, leaving daily/weekly/volume fields
missing. The report commands fell back and completed; this is an environment
warning, not a Chapter4 H2 failure. No code was changed to mask it.

The sparse broker behavior and full eight-item projection are covered by
synthetic snapshot/ViewModel tests because the current local report run had no
usable broker manifest to exercise that path naturally.

## Scope / Workspace

- Existing user dirty files were preserved.
- Report/data outputs are natural ignored artifacts.
- No commit or push was performed.
- No network data was edited or fabricated.

## Blocker / Warning / Deviation

- Blocker: none for H2 runtime/tests.
- Warning: report quality gate is environment-blocked by missing market data;
  rerun with reachable providers before final production acceptance.
- Deviation: no Claude review, explicitly waived by the user.
