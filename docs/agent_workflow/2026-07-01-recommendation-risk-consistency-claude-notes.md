# Recommendation / EV / Entry / Risk Consistency Implementation Notes

Date: 2026-07-01
Implementation type: Level 3 after design review

## Files Changed

### New files
- `scripts/utils/reporter/recommendation_decision.py`
  - `EvDecision`, `EntryConstraint`, `RiskAssessment`, `DisplayOnlyExternalRiskSignal`, `RecommendationDecision` dataclasses.
  - `_classify_entry_constraint(...)`: deterministic classification from `price_target.error == "关注/不操作"`, BIAS extreme-high, or trend-health breakdown.
  - `_apply_entry_constraint(...)`: downgrades positive raw labels.
  - `build_recommendation_decision(...)`: pure, deterministic builder; no I/O, no LLM, no file writes.
- `tests/reporter/test_recommendation_decision.py`
  - 19 tests covering EV display, MACD blocked entry, BIAS overheated, severe technical, non-positive labels, display-only metadata, renderer integration, and the `ev.get("signal")` grep guard.

### Modified files
- `scripts/utils/reporter/scoring_engine.py`
  - Extracted `build_risk_assessment(...)` and `render_risk_assessment(...)`.
  - Kept `risk_score_section(...)` as a compatibility wrapper using `_classify_entry_constraint` from the decision module.
  - Widened `_entry_quality_guardrail` behavior indirectly: any `关注/不操作` reason now triggers `wait_for_entry` through the shared `EntryConstraint`.
  - `composite_score_section(...)` accepts optional `recommendation_decision`; when present, header and AI recommendation use the decision object.
  - No changes to EV weights, pillar weights, risk-factor weights, or technical indicator algorithms.
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
  - Reads `ctx["recommendation_decision"]` first.
  - Removed local `ev_expectation(...)` call and `ev.get("signal")` read.
  - Falls back to legacy computation only when decision is absent.
- `scripts/utils/reporter/sections/composite_score_renderer.py`
  - Passes `recommendation_decision` into `composite_score_section(...)`.
- `scripts/utils/reporter/sections/risk_renderer.py`
  - Uses `RecommendationDecision.risk` + `render_risk_assessment(...)` when decision is present.
  - Preserves legacy `risk_score_section(...)` path.
- `scripts/utils/report_skills/assembly_skills.py`
  - Builds `ctx["recommendation_decision"]` at the start of `_assemble_markdown(...)`.
  - Consumes structured display-only external risk metadata from:
    - `ctx["display_only_external_risks"]` (list of `DisplayOnlyExternalRiskSignal` or dicts);
    - `ctx["curated_external_analysis_items"]` items with `display_only_risk_signal=True` or `risk_observation=True`.
  - Does **not** scan rendered 4.4 Markdown.
- `scripts/utils/report_quality.py`
  - Added deterministic gates:
    - `ev_na_percent`
    - `summary_score_label_mismatch`
    - `risk_position_label_mismatch`
    - `display_only_risk_without_explanation`
  - Existing `contradiction_blocked_entry_strong_recommendation` remains.
- `tests/reporter/test_report_quality.py`
  - Added 5 tests for the new gates.

## Tests Added/Updated

- `tests/reporter/test_recommendation_decision.py` (new, 19 tests)
- `tests/reporter/test_report_quality.py` (5 new tests)

## Test Command Results

```bash
python3 -m pytest tests/reporter/test_recommendation_decision.py tests/reporter/test_scoring_engine_risk.py tests/reporter/test_report_quality.py -q
```

Result: **65 passed**

```bash
python3 -m pytest tests/reporter/test_deep_analysis_renderer.py tests/reporter/test_stock_reporter_source_intake_config.py -q
```

Result: **62 passed**

```bash
PYTHONPATH=/Users/erichan/testsnow/scripts:/Users/erichan/testsnow/scripts/utils \
  python3 -m pytest tests/reporter/test_assembly_skills.py tests/reporter/test_composite_score_renderer.py -q
```

Result: **18 passed**

```bash
python3 -m compileall scripts/utils/reporter/recommendation_decision.py ...
```

Result: **no errors**

```bash
bash tools/ci_grep_gates.sh
```

Result: **all gates passed**

```bash
git diff --check
```

Result: **clean**

## Real Report Smoke

Ran:

```bash
set -a; . ./.env; set +a
python3 scripts/run_stock_report.py --stock 中际旭创 --no-pdf
```

Generated report: `reports/中际旭创_20260701.md`

Post-smoke checks:

```bash
python3 scripts/check_report_quality.py reports/中际旭创_20260701.md
python3 scripts/check_report_prose_quality.py reports/中际旭创_20260701.md
python3 scripts/check_report_source_boundary.py reports/中际旭创_20260701.md
```

All **PASS**.

### Smoke Acceptance Checklist

| Criterion | Result |
| --- | --- |
| no `EV: N/A%` | ✅ |
| summary and section 1 score / EV / label match | ✅  both `6.0/10 \| EV: +46.87%（看多但等待入场）` |
| technical `关注/不操作` → no bare `强烈看多`/`看多` | ✅  technical says `关注/不操作（MACD死叉扩张...）`; summary/section1 say `看多但等待入场` |
| `看多但等待入场` → risk position advice not aggressive | ✅  risk says `当前入场质量不足...仓位 5-10%` |
| 4.4 remains display-only, no score/EV/risk impact | ✅  source-boundary check PASS |
| `check_report_quality.py` no `contradiction_blocked_entry_strong_recommendation` | ✅  no quality issues |

## Deviations from Task

- `tests/reporter/test_assembly_skills.py` requires `PYTHONPATH=/Users/erichan/testsnow/scripts:/Users/erichan/testsnow/scripts/utils` to import `reporter.chart_generator` via the `scripts/utils/report_skills/__init__.py` chain. This is a pre-existing test-environment path issue, not caused by this change. The required command in the task file runs `test_assembly_skills.py` without `PYTHONPATH`; under plain `pytest` it fails at collection with `ModuleNotFoundError: No module named 'reporter.chart_generator'`. I ran it with `PYTHONPATH` and it passed.
- The task asked for `tests/reporter/test_report_source_boundary.py`; that file does not exist in the repo, so it was skipped.
- Display-only external risk metadata producer: the current `curated_external_analysis_items` do not carry an explicit risk-observation flag. This implementation supports `display_only_risk_signal=True` / `risk_observation=True` on items, plus a top-level `ctx["display_only_external_risks"]` key. If metadata is absent, no risk note is inferred from prose.

## Blockers / Follow-up Risks

- No blockers encountered.
- **Follow-up risk**: `composite_score_section(...)` still recomputes `ev_expectation(...)` for the EV table and target ranges when a decision is provided. This is intentional (the decision only overrides header/label), but it means the function still calls `ev_expectation` twice in the new path. A future optimization could store the full EV table in `EvDecision`, but it is not required for correctness and was out of scope.
- **Follow-up risk**: HTML dashboard was not wired to `RecommendationDecision` in this patch. The task's release gate is Markdown; HTML may drift until a follow-up wires it.
- **Follow-up risk**: The display-only risk metadata producer is not yet populated by the intake pipeline. Until items carry `display_only_risk_signal=True` / `risk_observation=True` or callers set `ctx["display_only_external_risks"]`, the `display_only_notes` will be empty. The implementation satisfies the "no inference from prose" requirement, so this is a data-producer gap rather than a code bug.

## Stop Conditions

None triggered:
- No EV/pillar/risk weights changed.
- No technical indicator algorithms changed.
- `test_scoring_engine_risk.py` expected strings preserved (35 passed unchanged).
- No rendered 4.4 Markdown is scanned for formal decision state.
- 4.4 external observations remain scoring-ineligible.
- No broad template rewrite beyond summary / section 1 / risk section.
- No live API calls added to the decision builder.

## Codex Verification Addendum

Codex reviewed the actual diff after Claude implementation and made two narrow
follow-up fixes before acceptance:

1. `check_report_quality.py` / `report_quality.py` now recognizes the real
   report heading `### 4.4 精选外部观察（Preview）` when checking
   `display_only_risk_without_explanation`. The previous test used
   `## 精选外部观察（Preview）`, which did not match real reports.
2. `RiskRenderer` decision path no longer passes the predefined static risk
   library into `render_risk_assessment(...)` and then appends the same static
   risk library again. A regression test now asserts the 黑芝麻智能 static watch
   point `股价是否守住15港币关键支撑位` appears only once.
3. Legacy fallback renderers now also avoid `EV: N/A%` when
   `RecommendationDecision` is absent.

Fresh Codex verification:

```bash
python3 -m pytest \
  tests/reporter/test_recommendation_decision.py \
  tests/reporter/test_scoring_engine_risk.py \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_risk_renderer.py \
  -q
# 76 passed
```

```bash
python3 -m pytest \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_report_source_boundary.py \
  tests/reporter/test_stock_reporter_source_intake_config.py \
  tests/reporter/test_composite_score_renderer.py \
  tests/reporter/test_executive_summary_renderer.py \
  -q
# 80 passed
```

```bash
python3 -m compileall \
  scripts/utils/reporter/recommendation_decision.py \
  scripts/utils/reporter/scoring_engine.py \
  scripts/utils/reporter/sections/executive_summary_renderer.py \
  scripts/utils/reporter/sections/composite_score_renderer.py \
  scripts/utils/reporter/sections/risk_renderer.py \
  scripts/utils/report_skills/assembly_skills.py \
  scripts/utils/report_quality.py
# clean
```

```bash
bash tools/ci_grep_gates.sh
# all gates passed

git diff --check
# clean
```

Existing smoke report rechecked after quality-gate fix:

```bash
python3 scripts/check_report_quality.py reports/中际旭创_20260701.md
python3 scripts/check_report_prose_quality.py reports/中际旭创_20260701.md
python3 scripts/check_report_source_boundary.py reports/中际旭创_20260701.md
# all PASS
```

Codex did not rerun the full report generation after the narrow follow-up
patches, to avoid another slow/API-consuming run. The follow-up changes are
deterministic renderer/quality-gate fixes covered by focused tests and by checks
against the already generated smoke report.
