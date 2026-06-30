# Position Advice Guardrail Design

Date: 2026-06-14

## Goal

Prevent the risk section from giving aggressive position advice when the technical regime is weak.

Observed runtime after Structured Risk Signals:

- `综合风险评分` fell to `2.0/10`, which is correct because LLM keyword risks no longer score.
- The risk section then rendered `仓位建议: 积极配置，最大仓位 20%`.
- The same report also says the technical regime is `下降趋势 / 破坏期`, with `趋势健康度 26/100，趋势失效`.
- `scripts/check_report_quality.py` therefore emits `contradiction_weak_trend_strong_recommendation`.

This phase should remove the misleading aggressive position wording without changing risk score, technical score, EV, synthesis, Agent-Reach, or final recommendation logic.

## Current Behavior

`risk_score_section()` maps only `total_risk` to position advice:

```python
if total_risk <= 2:
    position_advice = "积极配置，最大仓位 20%"
elif total_risk <= 5:
    position_advice = "谨慎持有，仓位 10-15%"
elif total_risk <= 7:
    position_advice = "控制仓位，5-10%"
else:
    position_advice = "建议减仓或不买入"
```

Problem:

- This treats a low risk score as permission for positive position advice.
- After Structured Risk Signals, qualitative LLM wording no longer inflates risk score, so the position advice can become too positive while trend structure is broken.

## Design Options

### Option A: Add risk points for weak technical state

Increase `total_risk` when the technical regime is weak.

Rejected for this phase:

- It mixes technical trend regime into risk score after we just stabilized the scoring model.
- It may create double counting because `技术破位` already adds risk.
- It changes historical risk numbers rather than only fixing the advice wording.

### Option B: Change report quality checker only

Adjust `STRONG_RECOMMENDATION_PATTERNS` so this warning no longer fires.

Rejected:

- The report text would still be misleading.
- The quality checker is correctly flagging a real product issue.

### Option C: Cap position advice by technical regime

Keep `total_risk` unchanged, but pass the technical regime into the position-advice mapping and cap aggressive advice when trend state is weak.

Chosen approach:

- It fixes the visible contradiction.
- It preserves risk-score explainability.
- It is small and testable.

## Proposed Behavior

Add a helper near `risk_score_section()`:

```python
def _technical_position_guardrail(stock_raw: Dict) -> Optional[Dict]:
    ...
```

It reads:

```python
resonance = stock_raw.get("technical", {}).get("indicators", {}).get("_resonance", {})
trend_state = resonance.get("trend_state", {})
trend_health = resonance.get("trend_health", {})
```

It should classify the technical regime as:

### Severe Guardrail

Trigger if any of:

- `trend_state.stage == "破坏期"`
- `trend_state.primary_state == "下降趋势"`
- `trend_health.grade == "趋势失效"`
- numeric `trend_health.score < 30`

Effect:

- Do not alter `total_risk` or `risk_level`.
- Override only `position_advice` to:

```text
趋势破坏期，以观望或防守仓位为主，建议 0-5%
```

This wording intentionally avoids quality-check strong terms such as `积极配置`, `建议加仓`, and `趋势仍可跟踪`.

### Moderate Guardrail

Trigger if no severe guardrail and any of:

- `trend_state.stage == "转弱期"`
- `trend_health.grade == "破坏风险高"`
- numeric `30 <= trend_health.score < 45`

Effect:

- Do not alter `total_risk` or `risk_level`.
- If the original position advice is more aggressive than this, cap it to:

```text
趋势转弱，控制仓位，建议 5-10%
```

If the original risk-based advice is already more conservative, keep the original.

### No Guardrail

If no weak technical signal is available, keep the existing risk-based mapping exactly.

## Renderer Flow

No new renderer API is required if `risk_score_section()` can read `stock_raw`.

`RiskRenderer` already passes `stock_raw` into:

```python
risk_score_section(stock_raw=stock_raw, ...)
```

So the guardrail can be implemented inside `risk_score_section()` after `risk_level` and initial `position_advice` are computed.

Add a short explanatory note when the guardrail applies:

```markdown
> **仓位建议**: 趋势破坏期，以观望或防守仓位为主，建议 0-5%
> **仓位约束**: 技术状态为 下降趋势 / 破坏期，风险分不低估趋势破坏带来的仓位限制。
```

For moderate:

```markdown
> **仓位建议**: 趋势转弱，控制仓位，建议 5-10%
> **仓位约束**: 技术健康度偏弱，仓位建议已按技术状态降级。
```

## Non-Goals

- Do not change `total_risk`.
- Do not add new risk factors.
- Do not change technical-analysis algorithms.
- Do not change `check_report_quality.py`.
- Do not change `KnowledgeSynthesizer`, Agent-Reach, claim verification, scoring pillars, EV, or final AI recommendation.
- Do not run external network, Xueqiu detail fetch, Chrome/CDP, or Zhihu refresh during implementation tests.

## Failure Modes

- Missing `_resonance`: keep old behavior.
- Malformed `trend_health.score`: ignore numeric score and rely on string fields if available.
- Unknown `stage` or `primary_state`: keep old behavior unless another guardrail trigger is present.
- Severe and moderate both match: severe wins.
- Risk-based advice is already more conservative than the moderate cap: keep the more conservative advice.
- Report quality still warns because another section contains a strong recommendation phrase: implementation notes should identify the source text rather than changing unrelated sections.

## Tests

Add focused tests in `tests/reporter/test_scoring_engine_risk.py`:

1. Severe guardrail: `下降趋势 / 破坏期 / 趋势健康度 26` changes only position advice to `0-5%`; risk score remains `2.0/10` for technical breakdown + liquidity.
2. Severe guardrail avoids strong recommendation words: no `积极配置`, no `建议加仓`, no `趋势仍可跟踪`.
3. Moderate guardrail: `转弱期` or health score `35` caps low-risk advice to `5-10%`.
4. Moderate guardrail does not make already conservative high-risk advice more aggressive.
5. Missing `_resonance` preserves existing risk-only advice.

Add renderer test in `tests/reporter/test_risk_renderer.py` if needed:

- `RiskRenderer` passes `stock_raw` with `_resonance` through and rendered output includes the guardrail note.

Runtime validation:

1. Run focused tests:

```text
python3 -m pytest tests/reporter/test_risk_renderer.py tests/reporter/test_scoring_engine_risk.py -q
```

2. Run assembly regression:

```text
python3 -m pytest tests/reporter/test_assembly_skills.py -q
```

3. Run local fast report:

```text
cd scripts && python3 run_黑芝麻智能.py --fast-test
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260614.md
```

Expected runtime outcome:

- `综合风险评分` risk score remains `2.0/10` unless market data changes.
- The position advice is no longer `积极配置，最大仓位 20%`.
- `contradiction_weak_trend_strong_recommendation` no longer appears unless another section contains strong recommendation wording.
- Comprehensive score, EV, final recommendation, technical analysis, Agent-Reach, and core facts remain unchanged except for natural LLM/runtime variance.

## Round 1 Feedback

### Status

**Ready to implement** — minor design deltas and additional tests recommended.

The design correctly identifies the product contradiction and proposes a small, localized fix that does not alter risk score, technical scoring, EV, synthesis, or final recommendation. The chosen Option C is appropriate.

### Findings

#### [medium] Guardrail advice wording may still partially overlap with `STRONG_RECOMMENDATION_PATTERNS`
The quality checker matches `积极配置`, `建议加仓`, and `趋势仍可跟踪`. The proposed severe advice `趋势破坏期，以观望或防守仓位为主，建议 0-5%` does not contain those strings, so the warning should disappear. However, the moderate advice `趋势转弱，控制仓位，建议 5-10%` is also safe. Verify in tests by scanning rendered output against the exact patterns in `report_quality.py` rather than ad-hoc substrings.

#### [medium] Numeric threshold consistency with technical analyzer
The design uses `trend_health.score < 30` for severe and `30 <= score < 45` for moderate. These thresholds are close to the `technical_score <= 3` boundary in `_technical_score_from_indicators()` (which caps scores when `下降趋势` or `破坏期` is present). There is no formal contract that trend_health score maps linearly to the 0-10 technical pillar, so the thresholds are reasonable but should be documented as heuristic. Consider aligning the severe threshold with the existing `technical_score <= 3` semantic if practical, but this is optional.

#### [low] `_resonance` shape is not guaranteed in all report inputs
`stock_raw` is passed through, but some cached or test payloads may use legacy indicator shapes. The proposed helper handles missing `_resonance`, missing `trend_state`, and missing `trend_health`, which is sufficient. Ensure malformed `trend_health.score` (e.g., string or `None`) is also ignored for numeric comparisons.

#### [low] Position advice override could hide high-risk cases
If `total_risk` is high (e.g., `>= 8`) and the technical regime is also weak, the severe guardrail would replace `建议减仓或不买入` with `趋势破坏期...建议 0-5%`. This is not more aggressive, so it does not hide risk. The moderate guardrail explicitly keeps the more conservative advice when risk-based advice is already conservative. The design is safe, but a test should assert that a high-risk + weak-trend case still results in conservative wording.

#### [low] The guardrail note is rendered as a second blockquote line
The proposed rendering uses two consecutive blockquote lines:

```markdown
> **仓位建议**: ...
> **仓位约束**: ...
```

This is readable but slightly unusual. Consider whether the note should be a single `>` line or a separate `> **说明**:` block. Either is acceptable; the test should assert the note appears and contains the expected reason.

#### [low] No test for moderate-guardrail "keep more conservative" branch
The test list covers moderate capping aggressive advice but does not explicitly cover the branch where risk-based advice is already more conservative than the moderate cap. Add it.

### Recommended Design Deltas

1. Keep the overall approach (Option C) unchanged.
2. Add an explicit test that scans rendered output against `STRONG_RECOMMENDATION_PATTERNS` from `report_quality.py` to ensure the guardrail removes the warning.
3. Add a test for malformed/missing `trend_health.score` preserving old behavior.
4. Add a test for high-risk + weak-trend to confirm advice remains conservative.
5. Add a test for moderate guardrail preserving already-conservative advice.
6. Document the numeric thresholds (`score < 30`, `30 <= score < 45`) as heuristics tied to the current technical analyzer output.

### Missing Tests

- Scan rendered Markdown against `report_quality.STRONG_RECOMMENDATION_PATTERNS` after severe guardrail.
- Malformed `trend_health.score` (string, None) + weak string fields still triggers guardrail.
- Missing `_resonance` entirely preserves risk-only advice.
- High total risk + severe weak regime still yields conservative advice (not more aggressive).
- Moderate guardrail does not override already-conservative risk-based advice.
- `RiskRenderer` end-to-end: `stock_raw` with `_resonance` leads to guardrail note in output.

### Open Questions

1. Should the guardrail also cap `position_advice` when the technical analyzer output is `legacy_indicators` rather than `trend_health`? The design focuses on `_resonance`, which is the modern path; legacy payloads will simply keep risk-based advice. This is acceptable for this phase but may be worth noting.
2. Is the moderate cap `5-10%` intentionally the same upper bound as the `total_risk <= 7` risk-based advice? It creates a small overlap; if the design intends moderate to be a cap, this is fine.
3. Should the guardrail note be included in the Markdown even when no guardrail applies (e.g., `**仓位约束**: 无`) for consistency? Not required.

### R2 Needed?

**No.** The design is ready to implement after adding the recommended tests. No fundamental rework is required.

## Design Delta After Round 1

Accepted deltas:

1. Keep Option C unchanged: cap only rendered position advice, not `total_risk`.
2. Treat `trend_health.score < 30` and `30 <= score < 45` as implementation heuristics derived from current technical analyzer output, not as a formal cross-module scoring contract.
3. Severe guardrail must not make an already conservative high-risk recommendation less conservative. If risk-based advice is already `建议减仓或不买入`, keep it.
4. Moderate guardrail must cap only more aggressive advice. If risk-based advice is already `控制仓位，5-10%` or more conservative, keep it.
5. Tests must scan rendered output against `scripts.utils.report_quality.STRONG_RECOMMENDATION_PATTERNS`, not just hand-picked substrings.
6. Tests must cover malformed `trend_health.score` values (`str`, `None`) while string fields such as `stage` or `grade` still trigger the guardrail.
7. `RiskRenderer` should have an end-to-end test proving `_resonance` in `stock_raw` reaches `risk_score_section()` and produces the guardrail note.

Implementation-ready status: Ready to implement. R2 is not required.
