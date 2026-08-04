# Report Run Plan Deduplication: Codex Review Round 1

## Verdict

`ok`

## Review passes

### Pass 1: ownership and behavior

- Closed a placeholder in the base-context example by making
  `enable_claim_risk_signals` an always-present compiled context value.
- Locked the current evidence-note payload precedence, including the unusual
  edge where an enabled Agent-Reach evidence block can supply payload values
  while Source Intake is the active parent that makes notes eligible.
- Confirmed claim-verification precedence is independent from parent source
  enablement and must remain unchanged.
- Confirmed child annual, broker and external display gates remain dependent on
  Source Intake.

### Pass 2: scope, tests and budget

- Confirmed `data_path` is used only by the old `stock_reporter.py` CLI and can
  be removed with that CLI.
- Confirmed `generate_all_reports()` is used only by `xueqiu_monitor_v2.py` and
  the old module CLI.
- Required a narrow batch-report helper so batch behavior can be tested without
  running collection or browser paths.
- Confirmed existing pipeline integration tests already cover skill counts and
  order; no runtime change to `report_skills/__init__.py` is needed.
- The line budget remains credible: removing reporter config plumbing,
  batch/summary/CLI code and duplicated test scaffolding should exceed the
  `-100 runtime / -400 tests` targets after adding the compiler and matrix.

## Blockers

None.

## Must-fix

None remaining.

## Implementation ready

`yes`, after user review of the written design.
