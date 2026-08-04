# Source Intake Orchestration Deduplication Design

## 1. Goal

Reduce duplicated orchestration code in the early report pipeline without
changing source collection implementations, quality scoring, evidence
eligibility, URL dedupe, source precedence, or skill order.

The target path is:

```text
ReportRunPlan
  -> Agent-Reach query / fetch / quality
  -> A-share Source Intake
  -> source_intake_merge
```

The preceding run-plan task established one per-stock compiler. This task makes
that compiler the sole owner of Agent-Reach enablement and removes repetitive
terminal-state and bucket-writing code downstream.

The only intentional behaviour correction is that the documented
`ENABLE_AGENT_REACH=1` standard-entry override becomes effective before skill
assembly. Today it is read too late to insert Agent-Reach skills.

## 2. Current Problems

### 2.1 Agent-Reach has two enablement decisions

`compile_report_run_plan()` decides whether the pipeline includes Agent-Reach
skills, while `agent_reach_query_skill()` independently reads
`ENABLE_AGENT_REACH`. In the standard reporter path, the second decision cannot
insert omitted skills, so the environment override is ineffective unless the
pipeline was already built with Agent-Reach enabled.

### 2.2 Quality terminal states repeat the same output protocol

`agent_reach_quality_skill()` separately writes the same bucket/result/summary
keys for `disabled`, `skipped`, `empty`, and `ok`. The repetition makes shape
drift likely and obscures the actual scoring loop.

### 2.3 Merge bucket assembly is verbose

`source_intake_merge_skill()` creates and dispatches to three lists with a
branch chain, then writes the same three output keys in disabled and successful
paths. The merge decision itself is valid and must remain distinct from the
Agent-Reach quality decision.

## 3. Chosen Approach

Use a narrow orchestration-only refactor:

1. `compile_report_run_plan()` receives
   `environment: Mapping[str, str] | None = None`, treats `None` as an empty
   mapping, and
   combines `ENABLE_AGENT_REACH`, the global constructor flag, and per-stock
   configuration into one `agent_enabled` decision.
2. `PerStockReporter` passes `os.environ` to the compiler. The compiler reads
   only `ENABLE_AGENT_REACH` during the call. Direct compiler calls that omit
   the mapping remain deterministic and do not inspect process state.
3. `agent_reach_query_skill()` consumes only `enable_agent_reach` from context;
   it no longer imports or reads `os.environ`.
4. `agent_reach_quality_skill()` uses one local terminal-output helper for all
   statuses while preserving every existing output key and summary field.
5. `source_intake_merge_skill()` uses one bucket mapping and one output writer.
   It retains the existing dedupe key, preference rule, item order, and bucket
   predicate.

This is preferred over a shared generic source protocol because the quality
gate and merge stage have different semantic responsibilities. A new cross-file
abstraction would add coupling and is not needed to remove the current
duplication.

## 4. Locked Behaviour Contracts

### 4.1 Enablement precedence

Agent-Reach is enabled when any of these are true:

1. `ENABLE_AGENT_REACH` is one of `1`, `true`, or `True`;
2. `global_agent_reach_enabled` is true;
3. the stock's `agent_reach.enabled` value is true.

Environment parsing preserves those accepted values exactly. This task does
not broaden whitespace or case handling.

The compiler always emits the pipeline constructor flag. When enabled, it also
emits the existing true context flag; when disabled, it preserves the current
context-key omission. Both behaviours come from the same decision. The query
skill must not inspect environment or configuration.

Direct/manual query-skill invocation no longer treats process environment as an
independent enablement path. Such callers must provide `enable_agent_reach` in
context. The supported `PerStockReporter` entry remains environment-compatible
because it forwards the environment to the compiler before pipeline assembly.
This repairs the archived standard-entry contract; collection can become active
only when a caller deliberately sets one of the accepted environment values.

### 4.2 Quality states

The following states and shapes are unchanged:

- `disabled`: empty buckets/results, blank fetch status, disabled summary;
- `skipped`: empty buckets/results when fetch is missing/error or timeout has no
  items, with the original fetch status and warnings;
- `empty`: enabled fetch completed with no items;
- `ok`: scored items partitioned into keep/demote/discard, including partial
  timeout items.

`agent_reach_run_summary` must retain stock/date/enabled/fetch/quality/query,
counts, warnings, and compact results. Full source content must never enter the
summary.

### 4.3 Merge semantics

The refactor must preserve:

- canonical URL and periodic-excerpt identity rules;
- stable first-seen order for distinct items;
- higher source credit wins;
- equal-credit official exchange announcement beats web evidence;
- ineligible items become discard;
- Agent-Reach quality action controls demote/discard;
- discard input from Agent-Reach is not reintroduced;
- input lists and helper outputs are not mutated.

## 5. Scope

### Allowed runtime files

- `scripts/utils/report_run_plan.py`
- `scripts/utils/stock_reporter.py`
- `scripts/utils/report_skills/agent_reach_query_skill.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/report_skills/source_intake_merge_skill.py`

### Allowed tests

- `tests/reporter/test_report_run_plan.py`
- `tests/reporter/test_stock_reporter_run_plan.py`
- `tests/reporter/test_agent_reach_skills.py`
- `tests/reporter/test_agent_reach_quality_skill.py`
- `tests/reporter/test_source_intake_merge_skill.py`
- `tests/reporter/test_pipeline_integration.py`

### Explicitly excluded

- connector implementations and network calls;
- A-share intake collection logic;
- quality scoring weights or thresholds;
- URL normalization/dedupe semantics;
- evidence-note, synthesis, renderer, scoring, risk, target, or technical code;
- pipeline skill order;
- LLM prompts, report generation, data, knowledge, and reports.

Detection-only connectors remain present. Global URL-normalization consolidation
is deferred because existing modules intentionally use different identity
semantics.

## 6. TDD Plan

### Batch A: single enablement owner

Add failing tests proving:

- environment-only enablement includes Agent-Reach pipeline/context flags;
- false environment values do not enable it;
- omitted compiler environment remains disabled even when the process variable
  is set, proving compiler tests and helper calls are deterministic;
- config/global/environment precedence is additive;
- query skill ignores the process environment and consumes context only;
- standard reporter passes an environment mapping to the compiler.
- standard reporter with environment-only enablement builds the Agent-Reach
  branch under mocks, without invoking connectors.

Then move environment parsing into the compiler and remove it from query skill.

### Batch B: quality-state writer

Add a parameterized terminal-state contract covering disabled, skipped, empty,
and partial-timeout success. Assert exact bucket/result/summary keys and warning
propagation. Replace repeated writes with one local helper and retain the scorer
unchanged.

### Batch C: merge bucket writer

Add or tighten tests for output shape, stable order, official tie preference,
demote/discard behaviour, and input immutability. Replace list dispatch and
output repetition with a local bucket mapping/writer.

### Batch D: regression and accounting

Run focused suites, the full suite, CI grep gates, `git diff --check`, and the
offline smoke entry with `ENABLE_AGENT_REACH` removed and a `/tmp` config copy
whose stock-level Agent-Reach flag is disabled. Do not generate a formal report
or access the network.

## 7. Requirement-Test Matrix

| Requirement | Test owner |
|---|---|
| Environment/config/global compile to one decision | `test_report_run_plan.py` |
| Omitted compiler environment never reads process state | `test_report_run_plan.py` |
| Query skill cannot independently enable itself | `test_agent_reach_skills.py` |
| Reporter forwards environment to compiler | `test_stock_reporter_run_plan.py` |
| Environment-only reporter plan includes Agent-Reach without network | `test_stock_reporter_run_plan.py` |
| Disabled/skipped/empty/partial-timeout shapes remain stable | `test_agent_reach_quality_skill.py` |
| Run summary excludes full content | `test_agent_reach_quality_skill.py` |
| Merge order, preference, eligibility, and action remain stable | `test_source_intake_merge_skill.py` |
| Skill order remains unchanged | `test_pipeline_integration.py` |

## 8. Failure Modes and Guards

| Failure mode | Observable symptom | Guard |
|---|---|---|
| Env enables context but not pipeline construction | Agent-Reach keys exist but skills never run | compiler pipeline/context equality test |
| Ambient enablement triggers acceptance traffic | offline smoke unexpectedly runs connectors | smoke removes env and disables Agent-Reach in a `/tmp` config; reporter test uses mocks |
| Query skill remains a second owner | env-only direct query invocation enables itself | query context-only negative test |
| Empty-state helper changes summary shape | smoke/audit writer misses keys | exact terminal-state assertions |
| Timeout drops partial evidence | timeout with items becomes skipped | partial-timeout success test |
| Merge refactor changes order | citations/material ordering changes | ordered item identity assertion |
| Official tie preference is lost | lower-value web item shadows announcement | equal-credit preference test |
| Generic abstraction changes URL identity | unexpected dedupe or source loss | no URL helper movement; existing dedupe suite |

## 9. Line Budget and Stop Conditions

Locked pre-task runtime baseline: `67,052` lines under `scripts/**/*.py`.

- Target: at least `50` net runtime lines removed.
- Acceptable: any net reduction if all contracts pass and no artificial
  abstraction is introduced.
- Hard stop: runtime grows, a quality threshold/source rule must change, a new
  cross-file source protocol is required, or an allowed-file boundary must be
  expanded.

No test module deletion is planned for this batch. Individual duplicate tests
may be removed only when their exact contract is mapped to a surviving test;
no deletion target is imposed.

## 10. Acceptance

- focused tests pass;
- full `pytest` passes with only existing skips;
- `tools/ci_grep_gates.sh` passes;
- `git diff --check` is clean;
- offline smoke generates only temporary outputs;
- no network, Chrome/CDP, formal report, data, knowledge, or report mutation;
- final notes report before/after runtime and test line counts plus any deleted
  test mapping.
