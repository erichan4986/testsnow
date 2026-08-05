# H2 Codex Self-Review Round 1

## Verdict

`needs_revision`

## Finding

### M1: Coverage retained the hidden six-row cap

The initial design limited runtime scope to
`deep_analysis_material_snapshot.py`, but
`SynthesisSkill._build_material_coverage_diagnostics()` still calculated
`memo_row_count` as `min(6, broker_usable_card_count)`. Removing only
`selected[:6]` would create two contradictory row counts.

## Resolution

- add `synthesis_skills.py` to the narrow runtime scope;
- replace the old capped coverage count with the admitted projected count;
- add an eight-item coverage regression;
- document the expected one-card diagnostic changes separately from the
  evidence-profile branch, which must remain unchanged.

## Remaining Findings

No blocker. Round 2 is required because M1 changes the allowed runtime scope.
