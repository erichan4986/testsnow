# Report `--no-llm` Mode Implementation Notes

## Modified Files

Runtime:

- `scripts/run_stock_report.py`
- `scripts/utils/stock_reporter.py`
- `scripts/utils/content_quality_gate.py`
- `scripts/utils/report_skills/data_skills.py`
- `scripts/utils/report_skills/analysis_skills.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/reporter/sections/html_dashboard_renderer.py`

Tests:

- `tests/reporter/test_run_stock_report_entry.py`
- `tests/reporter/test_stock_reporter_run_plan.py`
- `tests/reporter/test_data_skills.py`
- `tests/reporter/test_analysis_skills.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_executive_summary_renderer.py`
- `tests/reporter/test_html_dashboard_renderer.py`

Notes:

- `docs/agent_workflow/2026-08-05-report-no-llm-mode-claude-notes.md`

No other files were intentionally modified for this batch. Existing dirty
worktree changes were preserved.

## RED/GREEN

1. Entry/intake: 3 tests failed before implementation, then passed. The new
   flag, offline-smoke policy, and non-fast `use_curator=False` contract are
   covered.
2. Reporter/quality/consolidation: 3 tests failed before implementation, then
   passed. `report_llm_enabled` defaults to `True` and is explicitly forwarded
   through the existing context; quality and topic consolidation receive the
   existing deterministic fallback switch.
3. Synthesis: 1 strict no-call test failed before implementation, then passed.
   No-LLM synthesis retains `SynthesisItem` construction and returns the
   existing template envelope without calling an injected synthesizer or
   constructing `KnowledgeSynthesizer`.
4. Executive summary: 1 strict no-call test failed before implementation,
   then passed. The legacy path enters the existing heuristic extraction
   directly when disabled; the view-model path is unchanged.
5. The first report acceptance found an unlisted HTML Dashboard call site
   making two requests. Its regression test reproduced exactly two calls
   before the narrow fix and zero calls after it.

New contract tests: `7 passed` after GREEN. The entry wiring test and the
existing compatibility tests also pass.

## Verification

- Focused report suites: `163 passed`.
- H1/H2 snapshot and renderer regression suites: `165 passed`.
- Dashboard/executive/assembly regression: `69 passed`.
- Full suite after the Dashboard fix: `2868 passed, 10 skipped`.
- `bash tools/ci_grep_gates.sh`: passed all gates.
- `git diff --check`: clean.
- No live LLM request was made to prove the no-call behavior.

## Runtime Numstat

The task-local hunk ledger is `+44` net runtime lines, four lines above the
target and below the `+80` hard stop:

| Runtime owner | Net |
| --- | ---: |
| entry flag/collector/reporter wiring | +12 |
| reporter context field | +3 |
| quality-gate forwarding | +0 |
| consolidation forwarding | +2 |
| data skill forwarding | +3 |
| synthesis short-circuit | +9 |
| executive-summary switch | +11 |
| HTML Dashboard switch | +4 |
| **Total** | **+44** |

For transparency, the current mixed dirty-worktree diff against `HEAD` is:

| File | Added | Removed | Net |
| --- | ---: | ---: | ---: |
| `run_stock_report.py` | 13 | 1 | +12 |
| `stock_reporter.py` | 3 | 0 | +3 |
| `content_quality_gate.py` | 2 | 2 | 0 |
| `data_skills.py` | 4 | 1 | +3 |
| `analysis_skills.py` | 3 | 1 | +2 |
| `synthesis_skills.py` | 44 | 393 | -349 |
| `executive_summary_renderer.py` | 29 | 18 | +11 |

The `synthesis_skills.py` deletion-heavy row predates this batch and belongs
to the existing H1/H2 dirty work. It is not attributed to `--no-llm`.

## Six-Owner No-Request Evidence

- Zhihu intake spy observed `use_curator=False` for non-fast `--no-llm`.
- Quality-gate spy observed `use_llm=False`.
- Consolidator spy observed `use_llm_topics=False`.
- Strict injected synthesis fake was not called; the deterministic template
  path returned synthesis output.
- Strict `_llm_extract_thesis` spy was not called; the legacy renderer still
  produced output through heuristics.
- The HTML Dashboard regression reproduced the two-request leak and then
  verified that its helper calls use `use_llm=False`.

The tests verify request-boundary selection without making a real request.
SDK client construction remains outside the zero-request contract.

## Preservation / Scope

- `--fast-test` remains independently defined and still allows normal
  synthesis unless `--no-llm` is also selected.
- `--no-llm` does not imply `--fast-test`, `--no-pdf`, offline market data, or
  environment-key deletion.
- `--offline-smoke` keeps its existing patches and now explicitly carries
  `no_llm=True`.
- Annual, broker, and curated external material paths are not removed or
  re-read through a second pipeline. H1/H2 snapshot and renderer regressions
  passed.
- No scoring, target price, risk, recommendation, technical algorithm,
  market provider, prompt, canonical pack, data, knowledge, or report change
  was made by this batch.

## Blocker / Warning / Deviation

- Blocker: the first live acceptance failed on two HTML Dashboard requests;
  the code-level blocker is fixed and awaits one narrow live rerun.
- Warning: a full live report run was intentionally not performed; the task
  prohibits using a live LLM request as proof of zero requests. Market,
  technical, chart, and PDF preservation are covered by unchanged code paths
  and regression tests, not by a new report artifact in this batch.
- Deviation: none.

## Batch Acceptance

`--no-llm` implementation is code-complete and awaits the narrow live rerun
that verifies the corrected HTML Dashboard path makes zero requests.
