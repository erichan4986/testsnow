# Recommendation / EV / Entry / Risk Consistency Implementation Task

Date: 2026-07-01

Task type: Level 3 implementation after design review

Design:

- `docs/agent_workflow/2026-06-30-recommendation-risk-consistency-design.md`

Review notes:

- `docs/agent_workflow/2026-07-01-recommendation-risk-consistency-claude-review-round1.md`

## Goal

Implement a central `RecommendationDecision` so the report uses one source of
truth for score, EV display, recommendation label, entry constraint, and risk
position advice.

The first release gate is Markdown consistency:

- no `EV: N/A%`;
- execution summary and section 1 show the same score / EV / recommendation;
- any technical `关注/不操作` state prevents bare `强烈看多` / bare `看多`;
- risk position advice uses the same `EntryConstraint` as the final
  recommendation label;
- 4.4 display-only risk observations may add explanatory notes but must not
  change formal score, EV, recommendation, or risk score.

## Allowed Files

Implementation:

- `scripts/utils/reporter/recommendation_decision.py` (new)
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/reporter/sections/composite_score_renderer.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/check_report_quality.py`
- `scripts/utils/report_quality.py` or existing report-quality helper, if the
  current quality checks live there

Tests:

- `tests/reporter/test_recommendation_decision.py` (new)
- `tests/reporter/test_scoring_engine_risk.py`
- `tests/reporter/test_report_quality.py`
- `tests/reporter/test_deep_analysis_renderer.py` only if needed for structured
  4.4 metadata plumbing
- `tests/reporter/test_pipeline_integration.py` only if a focused pipeline test
  is already using the touched paths and needs update

Docs / notes:

- `docs/agent_workflow/2026-07-01-recommendation-risk-consistency-claude-notes.md`

## Forbidden Changes

- Do not change EV formula weights.
- Do not change pillar score weights.
- Do not change risk-factor score weights.
- Do not change technical indicator algorithms.
- Do not make 4.4 external viewpoints scoring-eligible.
- Do not scan rendered 4.4 Markdown to compute formal decision state.
- Do not remove or rename public functions:
  - `ev_expectation(...)`
  - `composite_score_section(...)`
  - `risk_score_section(...)`
- Do not remove or rename report entrypoints.
- Do not run live report generation until unit/focused tests pass.
- Do not access external websites, do not refresh Zhihu, do not scrape Xueqiu
  detail pages, do not launch logged-in Chrome/CDP.
- Do not edit `data/raw`, `knowledge`, or committed historical reports.

## Required Implementation Shape

### 1. New decision module

Create `scripts/utils/reporter/recommendation_decision.py`.

It must be pure and deterministic: no I/O, no network, no LLM, no file writes.

Required public shapes:

- `EvDecision`
- `EntryConstraint`
- `RiskAssessment`
- `DisplayOnlyExternalRiskSignal`
- `RecommendationDecision`
- `build_recommendation_decision(...)`

Use dataclasses unless the local style strongly suggests otherwise.

Required behavior:

- `EvDecision.ev_display` is `"+49.83%"` when EV exists and `"N/A"` when EV is
  missing. It must never be `"N/A%"`.
- `EntryConstraint` classifies any
  `stock_raw["technical"]["price_target"]["error"] == "关注/不操作"` as
  `wait_for_entry`, regardless of reason text.
- `BIAS` extreme-high flags classify as `overheated`.
- severe technical breakdown classifies as `severe_technical`.
- positive raw recommendation + `wait_for_entry` displays
  `看多但等待入场`.
- positive raw recommendation + `overheated` displays `看多但避免追高`.
- positive raw recommendation + `severe_technical` displays `风险控制优先`.
- non-positive recommendation labels must not be upgraded by entry logic.

### 2. Risk assessment split

Extract risk construction so both old and new callers can coexist.

Required shape:

- `build_risk_assessment(...) -> RiskAssessment`
- `render_risk_assessment(...) -> str`
- `risk_score_section(...)` remains as a compatibility wrapper.

Compatibility requirements:

- Existing markers in `tests/reporter/test_scoring_engine_risk.py` must remain
  unchanged:
  - `风险等级: X/10`
  - `> **仓位建议**: ...`
  - `> **仓位约束**: ...`
  - `> **入场约束**: ...`
  - `结构化风险观察（不计分）`
  - `LLM文本风险观察（不计分）`
- `EntryConstraint` must feed risk position advice. A `wait_for_entry`
  constraint cannot leave the risk section saying `积极配置，最大仓位 20%`.
- 4.4 display-only risk metadata may add an explanatory note, but must not add
  risk points or alter `total_risk`.

### 3. Assembly-level decision creation

Build `ctx["recommendation_decision"]` at the start of
`ReportAssemblySkill._assemble_markdown(...)`.

Do not add a new pipeline skill in this patch.

Use structured metadata only for display-only external risk:

- allowed: curated external narrative/digest metadata loaded in ctx before
  rendering;
- forbidden: scanning final Markdown or rendered 4.4 body.

If metadata is absent, do not infer risk notes from prose.

### 4. Renderer wiring

`ExecutiveSummaryRenderer`:

- must read `ctx["recommendation_decision"]`;
- must stop calling `ev_expectation(...)`;
- must stop reading `ev.get("signal")`;
- must render the constrained label, not the raw EV label.

`CompositeScoreRenderer` / `composite_score_section(...)`:

- section 1 header must use the same decision object as the summary;
- existing EV tables, target ranges, and reasons can remain, but must not
  recompute a different score / EV label / recommendation header.

`RiskRenderer`:

- use `RecommendationDecision.risk` where available;
- preserve the compatibility wrapper path for existing callers.

## Required Tests

Use TDD. Write failing tests before implementation.

### Unit tests for decision model

Create `tests/reporter/test_recommendation_decision.py`.

Required cases:

1. Missing EV:
   - `ev_display == "N/A"`;
   - rendered header text does not contain `EV: N/A%`.
2. Normal EV:
   - positive EV renders `+xx.xx%`.
3. MACD blocked entry:
   - `price_target.error == "关注/不操作"`;
   - reason does not contain `盈亏比不足`;
   - `EntryConstraint.state == "wait_for_entry"`;
   - final label is `看多但等待入场`.
4. Overheated entry:
   - BIAS extreme-high flag yields `看多但避免追高`.
5. Non-positive raw label:
   - entry logic does not upgrade it.
6. Display-only metadata:
   - metadata present adds only a display note;
   - formal risk score remains unchanged.

### Renderer / report-quality tests

Add or update focused tests to assert:

1. Summary and section 1 headers match score / EV / label.
2. Summary blocked-entry positive case renders `看多但等待入场`.
3. `EV: N/A%` is caught by quality checks.
4. `ev.get("signal")` is no longer referenced in
   `executive_summary_renderer.py`.
5. If final label says `等待入场`, risk section does not render
   `积极配置，最大仓位 20%`.
6. Structured display-only risk flag produces explanation without changing risk
   score.
7. Risk section does not infer display-only note by scanning 4.4 prose.

Existing tests that must stay green:

- `tests/reporter/test_scoring_engine_risk.py`
- `tests/reporter/test_report_quality.py`

## Required Verification Commands

Run focused tests first:

```bash
python3 -m pytest \
  tests/reporter/test_recommendation_decision.py \
  tests/reporter/test_scoring_engine_risk.py \
  tests/reporter/test_report_quality.py \
  -q
```

Then run renderer / source-boundary related focused tests:

```bash
python3 -m pytest \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_source_boundary.py \
  tests/reporter/test_stock_reporter_source_intake_config.py \
  -q
```

Then run compile/gates:

```bash
python3 -m compileall \
  scripts/utils/reporter/recommendation_decision.py \
  scripts/utils/reporter/scoring_engine.py \
  scripts/utils/reporter/sections/executive_summary_renderer.py \
  scripts/utils/reporter/sections/composite_score_renderer.py \
  scripts/utils/reporter/sections/risk_renderer.py \
  scripts/utils/report_skills/assembly_skills.py

bash tools/ci_grep_gates.sh
git diff --check
```

Only after all focused tests pass, run one real report smoke:

```bash
set -a; . ./.env; set +a
python3 scripts/run_stock_report.py --stock 中际旭创 --no-pdf
python3 scripts/check_report_quality.py reports/中际旭创_20260701.md
python3 scripts/check_report_prose_quality.py reports/中际旭创_20260701.md
python3 scripts/check_report_source_boundary.py reports/中际旭创_20260701.md
```

If date-based output path differs, use the generated Markdown path.

Do not run additional stock reports unless the first smoke passes and the user
explicitly asks for more. Report generation is slow and can consume API budget.

## Smoke Acceptance Criteria

For the 中际旭创 smoke:

- no `EV: N/A%`;
- summary and section 1 score / EV / label match;
- if technical section says `关注/不操作`, summary and section 1 do not show bare
  `强烈看多` or bare `看多`;
- if label is `看多但等待入场`, risk section does not say
  `积极配置，最大仓位 20%`;
- 4.4 remains display-only and does not affect score / EV / formal risk score;
- `check_report_quality.py` does not emit
  `contradiction_blocked_entry_strong_recommendation`;
- source-boundary check remains PASS.

## Stop Conditions

Stop and write notes instead of continuing if:

- implementation requires changing EV formula weights, pillar weights, or
  risk-factor additive weights;
- implementation requires changing technical indicator calculations;
- `test_scoring_engine_risk.py` failures require changing expected public
  strings rather than preserving them;
- the only way to compute display-only external risk notes is scanning rendered
  4.4 Markdown;
- implementation would make 4.4 external observations scoring-eligible;
- a focused test exposes broad unrelated failures;
- report smoke attempts to access Xueqiu detail pages, logged-in Chrome/CDP, or
  other unsafe collection.

## Required Notes Output

Write:

```text
docs/agent_workflow/2026-07-01-recommendation-risk-consistency-claude-notes.md
```

Include:

- files changed;
- tests added/updated;
- exact test command results;
- whether a real report smoke was run;
- generated report path if smoke was run;
- acceptance checklist results;
- any deviations from this task;
- blockers or follow-up risks.

