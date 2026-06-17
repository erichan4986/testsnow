# Codex Review: Position Advice Guardrail

Date: 2026-06-14

## Scope Reviewed

- `scripts/utils/reporter/scoring_engine.py`
- `tests/reporter/test_scoring_engine_risk.py`
- `tests/reporter/test_risk_renderer.py`
- `docs/agent_workflow/2026-06-14-position-advice-guardrail-claude-notes.md`

## Review Result

Status: Accepted with runtime validation.

No blocker remains.

## What Changed

`risk_score_section()` now caps only rendered position advice when `_resonance` indicates a weak technical regime.

Severe guardrail:

- Triggers on `破坏期`, `下降趋势`, `趋势失效`, or numeric `trend_health.score < 30`.
- Keeps `total_risk`, risk factors, and `risk_level` unchanged.
- If the risk-based advice is not already `建议减仓或不买入`, changes advice to `趋势破坏期，以观望或防守仓位为主，建议 0-5%`.
- Adds a `仓位约束` note only when advice is changed.

Moderate guardrail:

- Triggers on `转弱期`, `破坏风险高`, or numeric `30 <= trend_health.score < 45`.
- Caps only aggressive or semi-aggressive advice to `趋势转弱，控制仓位，建议 5-10%`.
- Keeps already conservative advice unchanged.

## Boundaries Preserved

- No change to risk scoring rules.
- No change to risk factor table construction.
- No change to technical analysis algorithms.
- No change to `report_quality.py`.
- No change to `RiskRenderer` implementation.
- No change to KnowledgeSynthesizer, Agent-Reach, claim verification, EV, final recommendation, config, knowledge, data/raw, or reports.

## Tests Reviewed

The added tests cover:

- Severe guardrail changes only advice and keeps risk score unchanged.
- Severe guardrail output does not match `STRONG_RECOMMENDATION_PATTERNS`.
- Malformed numeric score values still allow string fields to trigger guardrails.
- Missing `_resonance` preserves old risk-only advice.
- High-risk plus severe weak trend keeps `建议减仓或不买入`.
- Moderate guardrail caps only more aggressive advice.
- Moderate guardrail keeps already conservative advice.
- `RiskRenderer` end-to-end path passes `stock_raw` through and renders the guardrail note.

## Verification

Focused tests:

```text
python3 -m pytest tests/reporter/test_risk_renderer.py tests/reporter/test_scoring_engine_risk.py -q
33 passed in 0.12s
```

Assembly regression:

```text
python3 -m pytest tests/reporter/test_assembly_skills.py -q
9 passed in 22.27s
```

Combined verification:

```text
python3 -m pytest tests/reporter/test_risk_renderer.py tests/reporter/test_scoring_engine_risk.py tests/reporter/test_assembly_skills.py -q
42 passed in 21.99s
```

Diff hygiene:

```text
git diff --check
<no output>
```

## Runtime Validation

Local Claude Code ran:

```text
cd scripts && python3 run_黑芝麻智能.py --fast-test
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260614.md
```

Codex independently checked the generated Markdown and quality result:

```text
PASS: reports/黑芝麻智能_20260614.md
No quality issues found.
```

Generated report excerpts:

```markdown
### 综合评分: 4.1/10 | EV: N/A%（N/A）
| 技术面强度(M) | 25% | 2.6 | 趋势健康度 26/100，等级 趋势失效，阶段 破坏期 |
> **AI 综合推荐**：**N/A** — 技术面偏弱。数据不足，无法计算 EV。

## 综合风险评分
### 风险等级: 2.0/10（低风险）
> **仓位建议**: 趋势破坏期，以观望或防守仓位为主，建议 0-5%
> **仓位约束**: 技术状态为 下降趋势 / 破坏期，风险分不低估趋势破坏带来的仓位限制。
```

Runtime outcome:

- `contradiction_weak_trend_strong_recommendation` no longer appears.
- Strong recommendation patterns (`强烈看多`, `积极配置`, `建议加仓`, `趋势仍可跟踪`) are not present in the generated report.
- `综合风险评分` remains `2.0/10`.
- Position advice is no longer `积极配置，最大仓位 20%`.
- `仓位约束` appears in the risk section.
- Comprehensive score, EV, AI final recommendation, and technical conclusion are consistent.
- Agent-Reach remains isolated in its own section and does not enter scoring, risk factors, or LLM deep-analysis citations.

Runtime notes:

- `akshare` had a non-blocking proxy error for `index_zh_a_hist`; fallback to `mootdx` succeeded.
- Generated report/cache/chart files are expected runtime artifacts.

## Notes

This phase fixes the position-advice contradiction created after stabilizing LLM keyword risk scoring. It does not yet implement the Agent-Reach source-credit to claim-verification to structured-risk-signals loop.
