# Claude Implementation Task: Position Advice Guardrail

Read first:

- `AGENTS.md`
- `docs/agent_workflow/2026-06-14-position-advice-guardrail-design.md`

## Goal

Fix the risk-section position advice contradiction:

- Keep `total_risk` and `risk_level` unchanged.
- Keep technical scoring unchanged.
- Cap only the rendered `仓位建议` when the technical regime is weak.
- Avoid output such as `积极配置，最大仓位 20%` when the report says `下降趋势 / 破坏期 / 趋势失效`.

This phase is a narrow guardrail. Do not connect Agent-Reach, source credit, claim verification, or structured risk signal generation.

## Allowed Files

Modify:

- `scripts/utils/reporter/scoring_engine.py`
- `tests/reporter/test_scoring_engine_risk.py`
- `tests/reporter/test_risk_renderer.py`

Create:

- `docs/agent_workflow/2026-06-14-position-advice-guardrail-claude-notes.md`

Only modify `scripts/utils/reporter/sections/risk_renderer.py` if a test proves it is required. The current design expects no renderer code change because `RiskRenderer` already passes `stock_raw`.

Stop before modifying any other file.

## Forbidden

- Do not change `total_risk` scoring rules.
- Do not add new risk factors.
- Do not modify `scripts/utils/report_quality.py`.
- Do not modify technical analysis algorithms.
- Do not modify `KnowledgeSynthesizer`, Agent-Reach, claim verification, synthesis skills, EV, scoring pillars, final recommendation, config, knowledge, data/raw, or generated reports.
- Do not run full report generation in the implementation round.
- Do not access external websites, LLM, browser, CDP, Xueqiu, or Zhihu.

## Required Implementation

### 1. Add a technical position guardrail helper

Add a small helper near `risk_score_section()` in `scoring_engine.py`.

It should read, defensively:

```python
resonance = stock_raw.get("technical", {}).get("indicators", {}).get("_resonance", {})
trend_state = resonance.get("trend_state", {})
trend_health = resonance.get("trend_health", {})
```

It should return guardrail metadata or `None`.

Severe guardrail triggers if any of:

- `trend_state.stage == "破坏期"`
- `trend_state.primary_state == "下降趋势"`
- `trend_health.grade == "趋势失效"`
- numeric `trend_health.score < 30`

Moderate guardrail triggers if no severe trigger and any of:

- `trend_state.stage == "转弱期"`
- `trend_health.grade == "破坏风险高"`
- numeric `30 <= trend_health.score < 45`

Numeric thresholds are heuristics tied to current technical analyzer output. Treat malformed score values (`str`, `None`, bool, non-number) as missing numeric scores; string fields can still trigger guardrails.

### 2. Apply guardrail only to position advice

After `total_risk`, `risk_level`, and initial `position_advice` are computed:

- Do not alter `total_risk`.
- Do not alter `risk_level`.
- Do not add risk factors.

Severe guardrail:

- If the risk-based advice is already `建议减仓或不买入`, keep it.
- Otherwise override `position_advice` to:

```text
趋势破坏期，以观望或防守仓位为主，建议 0-5%
```

Moderate guardrail:

- If the risk-based advice is `积极配置，最大仓位 20%` or `谨慎持有，仓位 10-15%`, cap to:

```text
趋势转弱，控制仓位，建议 5-10%
```

- If the risk-based advice is already `控制仓位，5-10%` or `建议减仓或不买入`, keep it.

### 3. Render guardrail note when applied

If a guardrail actually changes the position advice, add a second blockquote line below `仓位建议`:

Severe:

```markdown
> **仓位约束**: 技术状态为 下降趋势 / 破坏期，风险分不低估趋势破坏带来的仓位限制。
```

Moderate:

```markdown
> **仓位约束**: 技术健康度偏弱，仓位建议已按技术状态降级。
```

If the guardrail did not change advice because the risk-based advice was already conservative, do not add the note unless the implementation can explain it without implying a change. Prefer minimal output.

## Required Tests

Write failing tests first.

### `tests/reporter/test_scoring_engine_risk.py`

Add focused tests:

1. Severe guardrail with `下降趋势 / 破坏期 / score 26` changes position advice to `0-5%` while risk score remains unchanged.
2. Severe guardrail output does not match any pattern in `scripts.utils.report_quality.STRONG_RECOMMENDATION_PATTERNS`.
3. Severe guardrail still triggers when `trend_health.score` is malformed (`"26"` or `None`) but `stage`, `primary_state`, or `grade` is severe.
4. Missing `_resonance` preserves the existing risk-only advice.
5. High total risk plus severe weak trend keeps `建议减仓或不买入`, not a less conservative guardrail advice.
6. Moderate guardrail caps low-risk advice to `5-10%`.
7. Moderate guardrail does not override already-conservative risk-based advice.

### `tests/reporter/test_risk_renderer.py`

Add one end-to-end renderer test:

- Context includes `stock_raw` with `_resonance` severe trend state.
- Rendered output contains the guardrail position advice and `仓位约束`.

## Verification Commands

Run:

```bash
python3 -m pytest tests/reporter/test_risk_renderer.py tests/reporter/test_scoring_engine_risk.py -q
```

Run assembly regression:

```bash
python3 -m pytest tests/reporter/test_assembly_skills.py -q
```

Do not run full report generation in this implementation round. Runtime validation will be a separate local step after Codex review.

## Notes Output

Write:

`docs/agent_workflow/2026-06-14-position-advice-guardrail-claude-notes.md`

Include:

- Files changed.
- Tests run and results.
- Summary of the guardrail rules.
- Whether `risk_score_section()` risk score stayed unchanged in tests.
- Any deviations.
- Any blocker.

## Stop Conditions

Stop and report before proceeding if:

- You need to modify files outside the allowed list.
- You find that `_resonance` is not available through `stock_raw` in the tested path.
- Tests require changing `report_quality.py`.
- Fixing the warning requires changing final recommendation, EV, technical analyzer, or synthesis logic.
