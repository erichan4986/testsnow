# Technical Analysis v2 Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development and verification-before-completion. Execute inline because the user explicitly waived Claude review and requested direct implementation.

**Goal:** Make `technical_judgment.v1` the sole owner of technical interpretation and render one readable, internally consistent technical chapter without changing calculations or recommendation semantics.

**Architecture:** Add a deterministic `interpretation` projection to the existing judgment in `technical_state_machine.py`. Replace the renderer's raw-signal conclusion/ranking paths with ordered formatting of that projection while retaining legacy rendering only when neither structural inputs nor a valid core judgment exist.

**Tech Stack:** Python, pytest, Markdown renderer output.

---

### Task 1: Lock Interpretation and Cache Contracts

**Files:**
- Modify: `tests/reporter/test_technical_state_machine.py`
- Modify: `scripts/utils/reporter/technical_state_machine.py`

- [x] Add failing tests for down-regime counter-evidence, weekly-range/daily-break alignment, generic/concrete priority observations, market-context readiness, target status/reason normalization, additive projection validation, and core-cache upgrade boundaries.
- [x] Run the named state-machine tests and confirm failures are caused by the missing `interpretation` contract.
- [x] Implement a single interpretation builder plus narrow normalization/validation helpers. Reuse only existing categorical fields and trigger checks; do not add numerical thresholds.
- [x] Run all state-machine tests and refactor only after green.

### Task 2: Replace Renderer Decision Ownership

**Files:**
- Modify: `tests/reporter/test_technical_renderer.py`
- Modify: `tests/reporter/test_market_resonance_integration.py`
- Modify: `scripts/utils/reporter/sections/technical_renderer.py`

- [x] Add failing tests proving full/compact semantic identity, localized target states, hidden unavailable market context, one sell assessment, concise levels, safe core-only cache rendering, and removal of `_build_conclusion`/`_pick_priority_signal`.
- [x] Run the named renderer tests and confirm expected RED failures.
- [x] Replace compact/full insertion assembly with shared ordered section composition driven by `judgment.interpretation`; keep detailed tables only as projection detail.
- [x] Delete the two renderer decision helpers, raw warning rank blocks, unavailable market placeholder, duplicated sell assessment, raw extrema diagnostics, and raw reason-code prose.
- [x] Run renderer and market-resonance tests and refactor only after green.

### Task 3: Regression and Scope Gates

**Files:**
- Test only: recommendation, dashboard, report quality, technical skill contract, and non-network technical suites.
- Create: `docs/agent_workflow/2026-07-17-technical-analysis-v2-phase2-codex-notes.md`

- [x] Run focused state-machine/renderer/market tests.
- [x] Run downstream recommendation, dashboard, report-quality, and technical-skill contract tests.
- [x] Run the non-network technical test suite, `bash tools/ci_grep_gates.sh`, and `git diff --check`.
- [x] Audit the diff: only two runtime files and three tests may change; no indicator, target, scoring, risk, recommendation, data, knowledge, report, or prompt file may change.
- [x] Measure the two runtime files against task-start `cb35b7b`; stop if combined net growth exceeds `+120`.
- [x] Record RED/GREEN evidence, test counts, runtime numstat, scope audit, warnings, and any deviations in the Codex notes file.
