# Report `--no-llm` Mode Implementation Task

Worktree: `/Users/erichan/testsnow`

Read before editing:

- `AGENTS.md`
- `docs/agent_workflow/2026-08-05-report-no-llm-mode-design.md`
- `docs/agent_workflow/2026-08-05-report-no-llm-mode-claude-review-round1-notes.md`

## Goal

Implement the locked `--no-llm` report-run option. It must produce zero LLM
requests while preserving local materials, market data, technical analysis,
charts, and normal report output. Keep existing `--fast-test` and
`--offline-smoke` semantics.

## Allowed runtime files

- `scripts/run_stock_report.py`
- `scripts/utils/stock_reporter.py`
- `scripts/utils/content_quality_gate.py`
- `scripts/utils/report_skills/data_skills.py`
- `scripts/utils/report_skills/analysis_skills.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/reporter/sections/html_dashboard_renderer.py`

Allowed test files are the directly corresponding existing test files:

- `tests/reporter/test_run_stock_report_entry.py`
- `tests/reporter/test_stock_reporter_run_plan.py`
- `tests/reporter/test_data_skills.py`
- `tests/reporter/test_analysis_skills.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_executive_summary_renderer.py`
- `tests/reporter/test_html_dashboard_renderer.py`

Only add workflow notes at:

`docs/agent_workflow/2026-08-05-report-no-llm-mode-claude-notes.md`

## Required behavior

1. Add `--no-llm` with default enabled behavior unchanged.
2. Propagate `report_llm_enabled=False` explicitly through the reporter context.
3. With non-fast `--no-llm`, allow existing Zhihu network search but call
   `use_curator=False`.
4. With no-LLM context, use existing deterministic fallbacks for:
   - ContentQualityGate;
   - ContentConsolidator;
   - baseline/display SynthesisSkill;
   - legacy executive-summary thesis extraction.
   - HTML Dashboard thesis extraction.
5. Do not mutate API-key environment variables.
6. `--offline-smoke` must set the policy true/false consistently while keeping
   its existing broader offline patches.
7. Preserve annual/broker/external MaterialSnapshot and H1/H2 display behavior.

## TDD order

1. Entry flag/default/offline-smoke and collector `use_curator` tests: RED then
   GREEN.
2. Reporter and quality/consolidation propagation tests: RED then GREEN.
3. Synthesis no-call and deterministic fallback tests: RED then GREEN.
4. Executive-summary legacy fallback no-call test: RED then GREEN.
5. Run H1/H2 snapshot and renderer regression tests.

Strict no-call tests must fail if any of these request boundaries execute:

- `ContentQualityGate` LLM assessment;
- `ContentConsolidator` topic LLM;
- `KnowledgeSynthesizer` or injected legacy synthesis client;
- executive-summary `_llm_extract_thesis`;
- HTML Dashboard calls to the same thesis helper;
- Zhihu ContentQualityGate/Curator when non-fast collection is selected.

Client construction alone is not a request; do not add process-wide environment
deletion or monkeypatch-only runtime behavior.

## Prohibited changes

- No prompt changes.
- No scoring, target price, risk, recommendation, technical algorithm, market
  provider, canonical pack, data/raw, knowledge, or report changes.
- No redefinition of `--fast-test`.
- No second report pipeline, policy registry, or broad refactor.
- Do not revert or format unrelated dirty-worktree changes.

## Verification and stop conditions

Run focused tests, then full `pytest`, `bash tools/ci_grep_gates.sh`, and
`git diff --check`. Measure runtime numstat against the pre-task HEAD. Stop
immediately if runtime net growth exceeds `+80` lines, an allowed file is
insufficient, a prompt/algorithm change is needed, or a non-LLM behavior changes.

Do not make a live LLM request to prove zero requests. A local request-spy
acceptance may run `--fast-test --no-llm --no-pdf` with ordinary market/technical
paths enabled.

After implementation, write the notes file with:

- modified files;
- RED/GREEN results in the required order;
- focused/full/CI/diff-check results;
- runtime numstat;
- five-owner zero-request evidence;
- report/technical preservation evidence;
- blocker/warning/deviation;
- whether the batch is accepted.

Write notes and stop for Codex acceptance.
