# Report Run Plan Deduplication Design

## 1. Goal

Reduce configuration plumbing and duplicated tests along the real report call
path without changing pipeline order, report content, source behavior, scoring,
technical analysis, risk logic, citations, or LLM prompts.

The target flow is:

```text
stocks.json / explicit configs
    -> compile_report_run_plan()
    -> ReportRunPlan
    -> build_stock_report_pipeline(**plan.pipeline_kwargs)
    -> pipeline.run(base_input | plan.context_values)
```

The legacy batch entry `xueqiu_monitor_v2.py` remains, but the hard-coded
summary report is retired. Batch execution becomes a thin loop over the single
stock pipeline owner.

## 2. Current Problems

`PerStockReporter.generate_stock_report()` currently performs four jobs:

1. resolve Agent-Reach and Source Intake configuration;
2. derive pipeline construction flags;
3. repeat the same decisions while building pipeline context;
4. execute and handle the pipeline result.

The configuration branches occupy roughly half of the method. Two test files
use 1,327 lines and 45 test functions to exercise many combinations through a
mocked reporter instead of testing configuration compilation directly.

`PerStockReporter` also owns a legacy batch loop and a stock-specific summary
whose themes and risks are hard-coded. Only `xueqiu_monitor_v2.py` and the
module's old CLI use this path.

## 3. Ownership

### 3.1 `ReportRunPlan`

Add `scripts/utils/report_run_plan.py` with:

```python
@dataclass(frozen=True)
class ReportRunPlan:
    pipeline_kwargs: dict[str, Any]
    context_values: dict[str, Any]
    can_run_without_posts: bool
```

Add one pure function:

```python
compile_report_run_plan(
    *,
    repo_root: Path,
    agent_reach_config: Mapping[str, Any],
    source_intake_config: Mapping[str, Any],
    global_agent_reach_enabled: bool = False,
    global_periodic_fulltext_enabled: bool = False,
) -> ReportRunPlan
```

This function is the only owner of config precedence and optional pipeline
context. It performs no I/O; path resolution is deterministic `Path`
composition. It does not import pipeline skills.

### 3.2 `PerStockReporter`

`PerStockReporter` remains the single-stock facade. It owns:

- base inputs: stock name, date, output directory, posts, raw data, codes and
  complete stock config;
- the early no-material skip;
- pipeline creation and execution;
- exception logging and `(md_path, html_path)` return values.

It does not interpret child Source Intake or Agent-Reach options after this
change.

The legacy `data_path` constructor argument is removed together with the old
module CLI. Repository search shows no runtime or test caller outside that CLI;
all active callers pass `stocks_data` directly. The now-unused `json` import is
removed as well.

### 3.3 Pipeline builder

`build_stock_report_pipeline()` continues to own skill ordering. It consumes
the already-compiled `pipeline_kwargs`; it does not read raw stock config and
its ordering is unchanged.

### 3.4 Batch coordinator

`xueqiu_monitor_v2.py` owns batch iteration. It constructs one
`PerStockReporter`, calls `generate_stock_report()` for each configured stock,
and accumulates non-empty Markdown/HTML paths for its existing PDF loop.

The loop is exposed as one narrow private helper accepting already-collected
stocks, post data, raw data and output directory. This keeps collection outside
the helper and permits a no-network unit test. It preserves the current
reporter constructor inputs; the refactor does not newly enable Source Intake
for the legacy monitor.

`PerStockReporter.generate_all_reports()`, `_generate_summary_report()`, and the
module-level CLI are removed. No replacement hard-coded summary is generated.

## 4. Configuration Contract

The compiler must preserve these exact rules:

1. Agent-Reach is active when the global flag is true or the per-stock config
   has `enabled: true`.
2. Source Intake is active only when its per-stock config has `enabled: true`.
3. Periodic fulltext requires active Source Intake. An explicit nested
   `periodic_report_fulltext.enabled` overrides the global default; when the
   nested key is absent, the global default is used.
4. Periodic narrative, broker digest, and curated external display require
   active Source Intake and their own nested `enabled: true`.
5. Evidence notes require at least one active parent source with notes enabled.
   Once enabled, payload selection preserves the current expression exactly:
   choose Agent-Reach evidence config when its nested `enabled` is true,
   otherwise choose Source Intake evidence config. This means an enabled
   Agent-Reach evidence block can supply payload values even when Agent-Reach
   itself is inactive but Source Intake made notes eligible; the refactor must
   not silently correct this existing edge behavior.
6. Claim verification config retains the current
   `agent_reach.claim_verification or source_intake.claim_verification`
   precedence. `enabled` and `risk_signals` remain independent.
7. `canonical_synthesis_source_policy` is passed only when equal to
   `formal_first`.
8. Curated external pack paths are resolved against `repo_root` unless already
   absolute.
9. Optional values such as display limits, verification limits, cache paths,
   report type, URLs, RSS feeds, domains and evidence base directories are
   emitted only when currently emitted.
10. The legacy `urls` alias remains a fallback for `web_urls`.

`can_run_without_posts` is true when Agent-Reach or Source Intake is active.
It replaces the reporter's duplicate early-skip booleans.

## 5. Pipeline Input Contract

The reporter builds the invariant base input:

```python
{
    "stock_name": stock_name,
    "date_str": self.date_str,
    "output_dir": output_dir,
    "stocks_data": self.stocks_data,
    "raw_data": self.raw_data,
    "stock_codes": self.stock_codes,
    "stock_config": stock_cfg,
}
```

It then updates the base input with `plan.context_values`. The compiler must
not duplicate invariant inputs or include absent optional keys with `None`.
`context_values` always contains the boolean `enable_claim_risk_signals`,
matching the current reporter input even when false.

Pipeline construction receives only `plan.pipeline_kwargs`. This guarantees
that construction and context are produced from one decision pass.

## 6. Error Handling

- Missing or malformed optional nested config is treated as disabled, matching
  current `.get(..., {}) or {}` behavior.
- Relative pack paths are deterministic and do not require the file to exist at
  compile time; reader validation remains downstream.
- If there are no posts and `can_run_without_posts` is false, the reporter logs
  and returns `("", "")` as today.
- Pipeline exceptions remain caught by `PerStockReporter`, logged, and return
  `("", "")`.
- Batch execution retains the current outer error boundary. A raised reporter
  construction/execution error returns status 1; normal empty paths are simply
  omitted from the PDF list.
- No summary file is emitted as a fallback.

## 7. Test Design

### 7.1 Compiler contract matrix

Create `tests/reporter/test_report_run_plan.py`. Parameterize the existing
configuration combinations and assert exact `pipeline_kwargs`, exact relevant
`context_values`, and `can_run_without_posts`.

The matrix must cover:

- all defaults off;
- global and per-stock Agent-Reach enablement;
- disabled Agent-Reach config;
- URLs alias, RSS feeds/filter terms and official domains;
- Source Intake enabled/disabled;
- formal-first policy;
- explicit periodic fulltext enable/disable and global fallback;
- annual narrative, broker digest and external display parent gates and limits;
- relative/absolute curated pack paths;
- Agent-Reach and Source Intake evidence-note configurations;
- Source Intake-enabled notes with inactive Agent-Reach but an enabled
  Agent-Reach evidence block, preserving the current payload precedence;
- claim verification and risk-signal independence;
- verification limits and base directories;
- simultaneous Agent-Reach and Source Intake precedence.

### 7.2 Reporter integration

Keep focused integration tests for:

1. compiler output is passed unchanged to the pipeline builder and context;
2. no-post runs proceed when `can_run_without_posts` is true;
3. no-post runs skip when it is false;
4. pipeline exceptions return empty paths;
5. real chart/report integration remains unchanged.

The existing Agent-Reach and Source Intake reporter tests may be deleted or
collapsed only after every configuration assertion is mapped to either the
compiler matrix or one of these integration contracts.

### 7.3 Batch integration

Add a focused test for the batch report helper/path that verifies:

- configured stocks are processed in source order;
- each stock uses `generate_stock_report()` exactly once;
- Markdown and HTML paths are accumulated;
- no `xueqiu_summary_*.md` path is produced;
- the existing PDF loop can consume the returned path list.

### 7.4 Pipeline order regression

Existing `test_pipeline_integration.py` remains authoritative. Add an explicit
skill-name sequence assertion only if current tests do not already lock the
relevant order.

## 8. Implementation Batches

### Batch A: Pure compiler

- Add the compiler and contract matrix.
- Compare its output with current reporter behavior.
- Do not connect it to runtime yet.

### Batch B: Reporter cutover

- Replace reporter config branches with the compiler.
- Collapse superseded configuration tests.
- Run reporter, pipeline and chart integration tests.

### Batch C: Batch ownership

- Add the narrow batch-report helper and move explicit iteration into
  `xueqiu_monitor_v2.py`.
- Delete batch/summary/CLI code from `stock_reporter.py`.
- Add batch path tests without running collection.

### Batch D: Verification and accounting

- Run the full suite, CI grep gates and `git diff --check`.
- Run `python3 scripts/run_黑芝麻智能.py --offline-smoke`.
- Verify the pipeline skill order before and after.
- Record runtime and test line deltas against the post-dedup baseline of
  67,156 runtime lines and 63,045 test lines.

## 9. Failure Modes

| Failure | Observable effect | Required test |
|---|---|---|
| Pipeline/context decisions diverge | skill enabled without required context | exact plan matrix |
| Child display bypasses parent gate | stale materials appear unexpectedly | parent-off cases |
| Global fulltext overrides explicit off | unwanted annual intake | explicit-off case |
| Claim/evidence precedence changes | risk or notes differ | dual-config cases |
| Pack path changes | external cards disappear | relative/absolute cases |
| No-post source run is skipped | formal-only reports disappear | reporter no-post integration |
| Skill order changes | synthesis/scoring behavior changes | pipeline sequence assertion |
| Batch path includes removed summary | stale hard-coded report remains | batch path test |
| Tests are deleted before migration | silent contract loss | requirement-test mapping |

## 10. Scope

Allowed runtime files:

- new `scripts/utils/report_run_plan.py`;
- `scripts/utils/stock_reporter.py`;
- `scripts/xueqiu_monitor_v2.py`;

`scripts/utils/report_skills/__init__.py` is read-only in this task. Existing
pipeline integration tests already lock enabled-skill counts and ordering.

Allowed tests:

- new `tests/reporter/test_report_run_plan.py`;
- the two existing reporter config test files;
- focused reporter/pipeline integration tests;
- one new or existing batch coordinator test.

Out of scope:

- synthesis, renderer and material producers;
- scoring, technical analysis, targets and risk rules;
- source collection implementations;
- report structure, citations and LLM prompts;
- current Chapter 2 gross-margin changes;
- formal report generation or network access.

## 11. Budget and Stop Conditions

Targets:

- runtime net reduction at least 100 lines;
- tests net reduction at least 400 lines;
- no reduction in meaningful configuration case coverage;
- full suite zero failures;
- identical pipeline skill order.

Stop and return to design if:

- compiler output cannot exactly reproduce a current configuration case;
- implementation requires a source, synthesis, renderer, scoring, technical or
  risk change;
- batch cutover changes collection or browser behavior;
- runtime reduction is below 100 or test reduction below 400 after all batches;
- unrelated failures appear in the full suite.
