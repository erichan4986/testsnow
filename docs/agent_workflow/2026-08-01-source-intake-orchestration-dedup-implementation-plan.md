# Source Intake Orchestration Deduplication Implementation Plan

**Goal:** Make `ReportRunPlan` the sole Agent-Reach enablement owner and remove
repetitive quality/merge output plumbing without changing source semantics.

**Architecture:** The compiler receives an explicit environment mapping and
emits the existing pipeline/context plan. Downstream skills consume that plan.
Quality and merge retain separate decisions but use compact local writers.

**Tech Stack:** Python, pytest, existing `SkillContext` pipeline.

## Task 1: Single enablement owner

**Files:**

- Modify `tests/reporter/test_report_run_plan.py`
- Modify `tests/reporter/test_stock_reporter_run_plan.py`
- Modify `tests/reporter/test_agent_reach_skills.py`
- Modify `scripts/utils/report_run_plan.py`
- Modify `scripts/utils/stock_reporter.py`
- Modify `scripts/utils/report_skills/agent_reach_query_skill.py`

1. Add compiler tests for accepted/false/omitted environment mappings.
2. Add a query test proving process environment cannot override false context.
3. Add a mocked reporter test proving environment-only enablement assembles the
   Agent-Reach branch without running a connector.
4. Run only those tests and confirm failures are caused by the missing compiler
   parameter and the query's second owner.
5. Add `environment: Mapping[str, str] | None = None` to the compiler, pass
   `os.environ` from the reporter, and remove environment access from query.
6. Re-run the tests to green.

## Task 2: Quality terminal-state writer

**Files:**

- Modify `tests/reporter/test_agent_reach_quality_skill.py`
- Modify `scripts/utils/report_skills/agent_reach_quality_skill.py`

1. Add an exact parameterized characterization for disabled/skipped/empty
   output shapes and retain the existing partial-timeout test.
2. Run the quality suite to establish the green characterization baseline.
3. Replace repeated terminal output writes with one local helper. Keep
   `score_agent_reach_item()` and all threshold code byte-for-byte unchanged.
4. Re-run the quality suite.

## Task 3: Merge bucket writer

**Files:**

- Modify `tests/reporter/test_source_intake_merge_skill.py`
- Modify `scripts/utils/report_skills/source_intake_merge_skill.py`

1. Add an ordered replacement characterization if the existing suite does not
   explicitly prove preferred duplicate replacement retains first-seen order.
2. Run the merge suite to establish the green characterization baseline.
3. Replace branch-based bucket assembly with a three-key mapping and one local
   output writer. Do not move or alter URL/dedupe/preference helpers.
4. Re-run the merge suite.

## Task 4: Verification and notes

1. Run focused run-plan/reporter/query/quality/merge/pipeline tests.
2. Run full pytest, CI grep gates, and `git diff --check`.
3. Run `scripts/run_黑芝麻智能.py --offline-smoke` with
   `ENABLE_AGENT_REACH` removed and a `/tmp` configuration copy that disables
   the stock-level Agent-Reach branch.
4. Compare `scripts/**/*.py` and `tests/**/*.py` line counts with the locked
   `67,052` / `62,300` baselines. Stop if runtime grows.
5. Write results to
   `docs/agent_workflow/2026-08-01-source-intake-orchestration-dedup-implementation-notes.md`.

No commit or push is part of this plan.
