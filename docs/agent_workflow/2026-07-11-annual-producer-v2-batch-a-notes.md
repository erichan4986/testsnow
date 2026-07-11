# Annual Producer v2 Batch A Notes

## Result

Batch A implementation is complete on `codex/annual-producer-v2`.

Commits:

- `f86198f refactor: propagate annual argument families`
- `0abc84a refactor: carry annual completeness into chapter four`

## Implemented

- Annual memo rows retain all admitted v2 narrative cards without the old `[:8]` cap.
- Canonical `argument_family` and `argument_complete` are copied into annual memo rows.
- Financial fact and explanation rows use `financial_quality_explanation` and `argument_complete=false`.
- `MaterialRow` carries `argument_complete`; annual rows use the producer family directly.
- Formal-medium 4.4 admits only complete annual rows; incomplete atomic rows remain visible in 4.1.
- Annual renderer projection no longer uses title-based role inference or annual row limits.
- Formal-rich and formal-thin routing boundaries remain unchanged.

## Verification

- Focused and downstream suite: `390 passed`.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- Runtime delta against `33be46f`: `+1570/-1848`, net `-278` lines.
- Local material-pack check succeeded for five existing stock note directories.

The full repository pytest run was attempted but is not a Batch A blocker: it hit an unrelated
`scoring_engine.py` relative-import failure in `test_claim_risk_signal_skill.py` after 224
passed tests, then entered a slow tdxpy test and was interrupted.

## Batch B Gate

`Batch B allowed: no`.

The local active note directories still contain unshadowed legacy notes. The pack reported
non-zero `v1_adapter_use_count` (中际旭创: 9; other sampled stocks also non-zero). Do not
delete the v1 adapter or archive legacy notes until the report flow refreshes all active notes
to the v2 selection version and every refreshed sample reports adapter use `0`.

