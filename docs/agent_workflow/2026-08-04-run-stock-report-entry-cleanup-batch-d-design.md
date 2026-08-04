# Run Stock Report Entry Cleanup Batch D Design

## 1. Objective

Reduce the generic report entry `scripts/run_stock_report.py` without moving
the same code into another module. The batch makes one user-approved hard cut:
retire the unused stock-config bootstrap CLI. It also consolidates repeated
offline-smoke patching and cached-input loading while preserving formal report
generation, `--fast-test`, `--offline-smoke`, and PDF behavior.

Baseline: `e2fe945` on the current branch. Existing broker-note replacements,
old 20260705 reports, and plan-packet files are user-owned and out of scope.

## 2. Evidence And Selected Approach

`run_stock_report.py` currently has 680 lines:

- stock-config bootstrap: about 130 lines;
- offline-smoke setup: about 120 lines;
- cached Zhihu/Xueqiu and knowledge-post loading: about 145 lines;
- formal report orchestration and supporting entry logic: the remainder.

Repository search found no bootstrap caller outside this entry and its tests.
No wrapper, pipeline, README, tool, or configuration file invokes the three
bootstrap flags or helpers. The user explicitly approved retiring this surface.

Selected approach:

1. delete bootstrap behavior rather than relocate it;
2. retain offline smoke, but share environment clearing and function patching;
3. share the deterministic cache-file search/read loop;
4. keep bootstrap defaults out of a new utility module;
5. leave knowledge-post frontmatter parsing local because the existing shared
   parsers have different strictness and dependency contracts.

Rejected alternatives:

- Splitting the entry into several new modules: improves the visible entry
  length but does not reduce repository runtime.
- Deleting offline smoke: removes a useful deterministic engineering path.
- Reusing `claim_verification.parse_frontmatter`: couples the entry to a large
  verification module and changes malformed-frontmatter behavior.
- Compacting literal dictionaries or expressions solely to win line count:
  harms readability without removing responsibility.

## 3. Locked Behavior

### 3.1 Bootstrap hard cut

Remove these CLI options:

- `--bootstrap-config`
- `--write-config`
- `--bootstrap-output`
- bootstrap-only `--code`, `--xueqiu-code`, and `--gid`

Remove the bootstrap-only helpers and default source-intake literal:

- `_write_stocks_config`
- `_default_bootstrap_output`
- `_build_default_a_stock_source_intake`
- `_build_bootstrap_stock`
- `_handle_bootstrap`

An unknown stock still returns exit code 2. Its message must say that the stock
is absent and show the actual `--config` path to review; it must not offer a
removed flag. Existing configured-stock lookup by name, code, Xueqiu code, and
gid remains unchanged.

### 3.2 Offline-smoke consolidation

Keep `--offline-smoke` semantics exactly:

- implies `--fast-test` and `--no-pdf`;
- redirects default raw/report outputs to `/tmp`;
- clears LLM credentials before and after importing the quality gate;
- disables quality-gate LLM, consolidator LLM, synthesizer LLM, lazy financial
  fetching, execution-summary LLM, technical collection, and charts;
- remains process-local and does not modify configuration.

Use small private helpers/constants for repeated API-key clearing and repeated
`return None` function assignments. Preserve separate warning boundaries so an
optional import failure does not prevent later patches. Do not introduce a
general monkeypatch framework or change production dependency injection.

### 3.3 Cache loading consolidation

Use one private cache reader for the common behavior:

1. exact requested-date filename has first priority even if an older file has
   a newer mtime;
2. remaining matching files are tried by descending mtime;
3. malformed or unreadable candidates log a warning and fall through;
4. the reader validates the projected value type before returning;
5. no network request is introduced.

Zhihu projection remains
`payload["raw_data"][stock_name]["zhihu"]` as a dictionary. Xueqiu projection
remains `payload["posts"]` as a list filtered to dictionary entries. Existing
success and missing-cache log meaning remains intact.

### 3.4 Explicitly unchanged

- stock-specific compatibility wrappers and all entry filenames;
- config JSON schema and existing stock entries;
- source-intake, Agent Reach, annual, broker, and external producer behavior;
- `PerStockReporter`, report-skill order, renderer behavior, citations, PDF;
- data providers, LLM prompts, scoring, technical algorithms, targets, risk,
  recommendations, data, knowledge, and reports;
- fast-test fallback order: Xueqiu cache, then knowledge posts, then empty;
- formal fallback to `fetch_all_stocks(..., use_xueqiu=False)`.

## 4. Allowed Files

Runtime and tests:

- `scripts/run_stock_report.py`
- `tests/reporter/test_run_stock_report_entry.py`
- `tests/test_runtime_hygiene.py`

Workflow records:

- this design;
- its review prompt/notes;
- the later implementation plan and implementation notes.

No new runtime module is allowed. Do not touch existing dirty files.

## 5. TDD Plan

### Task 1: RED bootstrap retirement

Update entry tests to require:

1. unknown configured stock returns 2 and names the actual config path without
   mentioning `--bootstrap-config`;
2. removed bootstrap flags are rejected by argument parsing;
3. runtime hygiene asserts the five bootstrap helpers are absent and all six
   bootstrap-only option strings are absent.

Delete only bootstrap-specific tests. Keep configured-stock and canonical
source-intake configuration tests because they protect active behavior.

### Task 2: GREEN hard cut

Remove the six bootstrap CLI arguments, five helpers, bootstrap literal, and
the bootstrap branches in `main()`. Preserve `_dedupe_keep_order` because it is
still used by live Zhihu keyword construction.

### Task 3: RED/GREEN cache consolidation

Add focused fixtures proving:

- requested-date cache wins over a newer fallback;
- malformed requested-date cache falls through to the newest valid fallback;
- Zhihu and Xueqiu projected types are enforced;
- Xueqiu non-dictionary entries remain filtered;
- fast-test still never invokes network fallback.

Implement one common candidate/read loop. Do not merge Zhihu and Xueqiu
payload schemas or logging into an opaque adapter registry.

### Task 4: RED/GREEN offline-smoke consolidation

Retain existing offline-smoke tests and add a narrow assertion that both the
renderer data-fetcher module and report-skill data module receive the same five
disabled fetch callables. Add a regression fixture in which importing the
quality gate restores an API key, then assert the second clear removes it
before the remaining modules initialize.

Then consolidate repeated assignments with readable private helpers.

### Task 5: Verification

Run:

- `tests/reporter/test_run_stock_report_entry.py`
- `tests/reporter/test_report_run_plan.py`
- `tests/reporter/test_stock_reporter_run_plan.py`
- `tests/reporter/test_pipeline_integration.py`
- `tests/test_runtime_hygiene.py`
- full `pytest`
- `bash tools/ci_grep_gates.sh`
- `git diff --check`
- `python3 scripts/run_stock_report.py --stock 黑芝麻智能 --offline-smoke`

The smoke output must stay under `/tmp` and must not alter repository data,
knowledge, or reports.

## 6. Runtime Budget

- Baseline `scripts/run_stock_report.py`: 680 lines.
- Target: at most 525 lines.
- Expected runtime deletion: 155-180 lines.
- Hard stop: fewer than 140 net runtime lines deleted.

Test deletion does not count toward the runtime budget. Do not meet the budget
by dense formatting, deleting active diagnostics, moving code, or weakening
tests unrelated to bootstrap retirement.

## 7. Failure Modes

| Failure | Symptom | Detection |
|---|---|---|
| Removed bootstrap still partially parses | stale flag accepted or dangling helper | argparse + runtime-hygiene tests |
| Unknown-stock path becomes opaque | traceback or no remediation | entry test |
| Exact-date cache loses priority | report silently uses older material | cache-priority test |
| Malformed cache blocks fallback | empty report despite valid older cache | malformed-fallback test |
| Cache schemas are conflated | list/dict accepted in wrong path | projected-type tests |
| Fast test makes network calls | external fetch runs without cache | existing network-fail test |
| Offline smoke leaves one fetch owner live | network attempted in smoke | dual-module patch test + smoke run |
| `.env` reload restores LLM use | smoke initializes an LLM client | existing quality/consolidator tests |
| Refactor changes formal pipeline | run-plan or integration regression | downstream suites |
| Code is merely relocated | runtime line count unchanged | no-new-module rule + numstat |

## 8. Stop Conditions

Stop and return to design if implementation requires:

- changing any configured stock or source-intake schema;
- changing report-skill order, producer behavior, renderer output, citation,
  scoring, technical, target, risk, recommendation, or LLM prompt;
- adding a replacement bootstrap utility or compatibility adapter;
- touching files outside the allowlist;
- making fast-test or offline-smoke less deterministic;
- deleting fewer than 140 net runtime lines without an evidence-backed revised
  ledger.
