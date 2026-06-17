# Position Advice Guardrail — Claude Implementation Notes

Date: 2026-06-14
Task: docs/agent_workflow/2026-06-14-position-advice-guardrail-claude-task.md

## Files Changed

- `scripts/utils/reporter/scoring_engine.py`
  - Added `_technical_position_guardrail(stock_raw)` helper near `risk_score_section()`.
  - Applied guardrail to `position_advice` only, after `total_risk` and `risk_level` are computed.
  - Added optional `> **仓位约束**: ...` blockquote line when the guardrail actually changes advice.
- `tests/reporter/test_scoring_engine_risk.py`
  - Added focused tests for severe guardrail, moderate guardrail, malformed score handling, missing `_resonance`, and conservative-advice preservation.
- `tests/reporter/test_risk_renderer.py`
  - Added end-to-end renderer test proving `_resonance` in `stock_raw` reaches `risk_score_section()` and renders guardrail note.
- `docs/agent_workflow/2026-06-14-position-advice-guardrail-claude-notes.md` (this file)

## Tests Run and Results

Focused tests:

```text
python3 -m pytest tests/reporter/test_risk_renderer.py tests/reporter/test_scoring_engine_risk.py -q
33 passed in 0.09s
```

Assembly regression:

```text
python3 -m pytest tests/reporter/test_assembly_skills.py -q
9 passed in 31.81s
```

Full suite (extra sanity check):

```text
python3 -m pytest -q
729 passed, 6 skipped in 169.50s
```

## Guardrail Rules Summary

`_technical_position_guardrail(stock_raw)` reads `stock_raw["technical"]["indicators"]["_resonance"]` defensively:

| Level | Trigger (any of) | Effect on `position_advice` |
|-------|------------------|------------------------------|
| Severe | `trend_state.stage == "破坏期"` or `primary_state == "下降趋势"` or `trend_health.grade == "趋势失效"` or numeric `score < 30` | If risk-based advice is not already `建议减仓或不买入`, override to `趋势破坏期，以观望或防守仓位为主，建议 0-5%` and append `仓位约束` note. |
| Moderate | `trend_state.stage == "转弱期"` or `trend_health.grade == "破坏风险高"` or numeric `30 <= score < 45` | If risk-based advice is `积极配置，最大仓位 20%` or `谨慎持有，仓位 10-15%`, cap to `趋势转弱，控制仓位，建议 5-10%` and append note. Already-conservative advice is kept unchanged. |
| None | None of the above | Keep existing risk-only position advice; no note. |

Numeric thresholds (`< 30`, `30 <= score < 45`) are heuristics tied to current technical analyzer output, not a formal cross-module contract.

## Risk Score Unchanged

All tests confirm that `total_risk`, `risk_level`, and the risk-factor table are computed exactly as before. Examples:

- Severe guardrail test with `破坏期 / 下降趋势 / score 26` plus technical breakdown + liquidity: `风险等级: 2.0/10` remains unchanged.
- Missing `_resonance` path: `风险等级: 0.0/10` and original advice `积极配置，最大仓位 20%` remain unchanged.
- High-risk + severe trend: `风险等级: 8.0/10` remains unchanged.

## Deviations

- No renderer code changes were required; `RiskRenderer` already passes `stock_raw` to `risk_score_section()`.
- Full pytest suite was run as an extra sanity check beyond the task's required focused tests + assembly regression.
- The guardrail note is emitted only when the guardrail actually changes the position advice, matching the design's preference for minimal output.

## Blocker

None. Implementation stayed within allowed files and did not touch scoring rules, `report_quality.py`, technical analyzers, synthesis, EV, final recommendation, or Agent-Reach.

## Verification Checklist

- [x] Failing tests written first and observed failing.
- [x] Minimal implementation added to `scoring_engine.py` only.
- [x] Focused tests pass.
- [x] Assembly regression passes.
- [x] Full suite passes (729 passed, 6 skipped).
- [x] No network, LLM, Chrome/CDP, Xueqiu, or Zhihu access used.
- [x] Notes file written.
