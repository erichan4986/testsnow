# Codex Review: Structured Risk Signals

Date: 2026-06-14

## Scope Reviewed

- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `tests/reporter/test_risk_renderer.py`
- `tests/reporter/test_scoring_engine_risk.py`
- `docs/agent_workflow/2026-06-14-structured-risk-signals-claude-notes.md`

## Review Result

Status: Accepted with narrow Codex fixes and runtime validation.

No blocker remains in the focused implementation.

## What Changed

The implementation moves qualitative risk scoring away from LLM free-text keyword matches by default.

- Quantitative risks still score as before.
- `synthesis_text` keyword hits now render under `### LLM文本风险观察（不计分）` and do not affect the risk score by default.
- `score_llm_keyword_risks=True` preserves the previous keyword-scoring behavior as an escape hatch.
- `structured_risk_signals` can affect the risk score only when the signal is known, has `verified` or `supported` status, and has confidence >= 60.
- Duplicate structured signals score once and render once.
- Rendered evidence strips `[n]` and `[^n]` citation markers.

## Codex Fixes Applied

1. Removed dead/duplicate structured-risk loop logic left in the first implementation pass.
2. Normalized unknown structured signal sources to `外部来源`, including non-empty unknown values such as `random_blog`.
3. Rejected boolean `score` and `confidence` values so `score: true` cannot become a numeric risk score through Python's `bool`/`int` inheritance.
4. Normalized string `matched_terms` as a single term instead of iterating it character by character.

## Added/Strengthened Tests

- Unknown non-empty source renders as `外部来源`.
- Boolean structured signal numbers do not score.
- String `matched_terms` renders as one sanitized term.

## Verification

Focused risk tests:

```text
python3 -m pytest tests/reporter/test_risk_renderer.py tests/reporter/test_scoring_engine_risk.py -q
24 passed in 0.12s
```

Assembly regression:

```text
python3 -m pytest tests/reporter/test_assembly_skills.py -q
9 passed in 22.49s
```

Combined verification:

```text
python3 -m pytest tests/reporter/test_risk_renderer.py tests/reporter/test_scoring_engine_risk.py tests/reporter/test_assembly_skills.py -q
33 passed in 24.00s
```

## Runtime Validation

Local Claude Code ran the single-stock fast report:

```text
cd scripts && python3 run_黑芝麻智能.py --fast-test
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260614.md
```

Codex independently checked the generated Markdown and quality gate output:

```text
PASS: reports/黑芝麻智能_20260614.md
- [WARNING] contradiction_weak_trend_strong_recommendation: 报告出现趋势走弱/破坏信号，同时包含偏积极建议，需人工复核。
```

Generated report risk section:

```markdown
### 风险等级: 2.0/10（低风险）

| 风险因子 | 状态 | 加分 |
|----------|------|------|
| 技术破位 | 当前价 14.02 < MA20 15.88 | +1.0 |
| 流动性差 | 近20日日均成交 0.95 亿 < 5 亿 | +1.0 |

### LLM文本风险观察（不计分）

| 风险信号 | 命中词 | 说明 |
|----------|--------|------|
| 竞争格局恶化 | 价格战 | 自由文本命中，仅提示人工复核 |
| 资金流出 | 净流出, 减持 | 自由文本命中，仅提示人工复核 |
| 技术路线风险 | 替代 | 自由文本命中，仅提示人工复核 |
```

Runtime result:

- The previous LLM-keyword-only risk jump is gone.
- Keyword hits remain visible under `### LLM文本风险观察（不计分）`.
- Risk factors now contain only deterministic quantitative triggers in this report: `技术破位` and `流动性差`.
- Comprehensive score, EV, final recommendation, and technical conclusion stayed stable.
- Agent-Reach remains isolated in its own evidence section and does not enter the risk factor table or numbered citations.

Residual product warning:

- The quality gate still warns about weak technical trend plus relatively positive position wording. This is not caused by LLM keyword scoring anymore. It suggests the next risk/reporting phase should align position advice with technical regime, not only risk score.

## Notes

This phase does not yet connect Agent-Reach to `source_credit -> evidence notes -> claim verification -> structured_risk_signals`. It only prepares the risk renderer/scoring side so that future verified structured signals can affect risk scores without relying on unstable LLM phrasing.
