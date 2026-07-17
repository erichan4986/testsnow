# External Producer v3 Peer Group Reliability Notes

## Result

- Added deterministic downgrade of non-consecutive, otherwise safe peer groups to standalone units.
- Preserved LLM keep/skip decisions, reasons, evidence, prompt, schemas, and existing retry policy.
- Continuous groups remain grouped; oversized groups remain fail-closed.

## TDD

- RED: ordinal-gap `[1, 3]` returned `selector_incomplete`.
- GREEN: the same response becomes two singleton peer cards with one selector request.
- Identity guards: consecutive `[1, 2]` remains one card; four-member group still fails after two attempts.

## Verification

- Related tests: `420 passed`.
- `tools/ci_grep_gates.sh`: passed.
- `git diff --check`: clean.
- No live LLM call, report generation, config change, or pack promotion was performed.
