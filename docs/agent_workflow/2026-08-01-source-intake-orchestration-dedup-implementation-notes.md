# Source Intake Orchestration Deduplication Implementation Notes

## Result

Implementation completed under the user-approved independent-review skip.
`ReportRunPlan` is now the only runtime reader of `ENABLE_AGENT_REACH`, quality
terminal-state output is written through one local path, and merged evidence is
partitioned through one bucket mapping.

## Modified files

Runtime:

- `scripts/utils/report_run_plan.py`
- `scripts/utils/stock_reporter.py`
- `scripts/utils/report_skills/agent_reach_query_skill.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/report_skills/source_intake_merge_skill.py`

Tests:

- `tests/reporter/test_report_run_plan.py`
- `tests/reporter/test_stock_reporter_run_plan.py`
- `tests/reporter/test_agent_reach_skills.py`
- `tests/reporter/test_agent_reach_quality_skill.py`
- `tests/reporter/test_source_intake_merge_skill.py`

Workflow documentation was added or updated under the matching `2026-08-01`
prefix. No runtime file outside the locked scope was modified.

## TDD evidence

### Batch A: enablement owner

- RED: `8 failed, 1 passed`.
  - compiler rejected the new environment parameter;
  - query skill independently enabled itself from process environment;
  - the standard reporter skipped before assembling the Agent-Reach branch.
- GREEN: `9 passed` after the compiler accepted an explicit mapping, the facade
  forwarded `os.environ`, and query consumed context only.

### Batch B: quality terminal states

- Characterization baseline: `32 passed` for exact disabled/skipped/empty
  shapes plus existing partial-timeout behaviour.
- Refactor regression: quality and Agent-Reach suites `67 passed`.
- Final self-review found that dictionary dispatch no longer fail-closed for an
  unexpected action. A new test failed with `KeyError: unexpected`; the old
  fallback-to-discard behaviour was restored and the quality suite finished at
  `33 passed`.

### Batch C: merge buckets

- Added first-seen order characterization for preferred duplicate replacement.
- Baseline and refactored merge suite: `13 passed` both times.

## Final verification

- Focused compiler/facade/query/quality/merge/pipeline/evidence/assembly suite:
  `203 passed in 8.03s`.
- Full suite: `2819 passed, 10 skipped in 57.46s`.
- `bash tools/ci_grep_gates.sh`: all gates passed.
- `git diff --check`: clean.
- Runtime search: `ENABLE_AGENT_REACH` has one Python owner,
  `scripts/utils/report_run_plan.py`.
- Offline smoke: exit `0`; outputs were confined to
  `/tmp/testsnow_offline_smoke`.

The first smoke invocation exposed a pre-existing acceptance hazard: the
offline flag does not disable stock-configured Agent-Reach URLs and attempted
six DNS reads. That result was rejected. The accepted rerun used a `/tmp` config
copy with stock-level Agent-Reach disabled and an unset environment variable;
no Agent-Reach query/fetch/quality skill ran.

## Line accounting

- Runtime: `66,998`, from locked baseline `67,052`; net `-54`.
- Tests: `62,463`, from locked baseline `62,300`; net `+163`.
- No test module was deleted.

The runtime reduction comes from collapsing repeated quality terminal writes,
removing the query-level environment owner, and replacing merge list dispatch
with one bucket mapping. No shared source protocol was introduced.

## Scope and behaviour audit

- Environment acceptance remains exactly `1`, `true`, or `True`.
- Compiler calls without an environment mapping remain deterministic.
- The standard reporter now fulfils the documented environment-only enablement
  contract before skill assembly.
- Quality scores, thresholds, query generation, connectors, URL identity,
  source preference, item order, evidence eligibility, and pipeline order are
  unchanged.
- No LLM prompt, synthesis, renderer, scoring, target, risk, technical, data,
  knowledge, or repository report output was modified.

## Blocker / warning / deviation

- Blocker: none.
- Warning: `--offline-smoke` alone does not suppress stock-configured
  Agent-Reach URLs; use an isolated disabled config for genuinely offline
  acceptance until that separate entry issue is addressed.
- Deviation: independent Claude review was skipped by explicit user direction.
- No commit or push was made.
