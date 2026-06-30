# Claude Review Round 1: Position Advice Guardrail

You are Claude Code reviewing a design in `/Users/erichan/testsnow`.

Read:

- `AGENTS.md`
- `docs/agent_workflow/2026-06-14-position-advice-guardrail-design.md`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `scripts/utils/report_quality.py`
- `tests/reporter/test_scoring_engine_risk.py`
- `tests/reporter/test_risk_renderer.py`

## Goal

Review the design for adding a technical-regime guardrail to risk-section position advice.

The intended behavior is:

- Keep risk score unchanged.
- Keep technical scoring unchanged.
- Cap only the rendered `仓位建议` when technical regime is weak.
- Remove the misleading `积极配置，最大仓位 20%` style advice when the report says `下降趋势 / 破坏期 / 趋势失效`.

## Review Instructions

Do not write implementation code.
Do not modify tests.
Do not run report generation.
Do not access network, LLM, browser, Chrome/CDP, Xueqiu, or Zhihu.

Please append your feedback directly to:

`docs/agent_workflow/2026-06-14-position-advice-guardrail-design.md`

Use this structure:

```markdown
## Round 1 Feedback

### Status

Ready to implement / Must-fix before task / Blocked

### Findings

1. [severity] ...

### Recommended Design Deltas

- ...

### Missing Tests

- ...

### Open Questions

- ...

### R2 Needed?

Yes/No, with reason.
```

## Specific Things To Check

- Is it correct to cap `position_advice` without changing `total_risk`?
- Is `_resonance` available at the location proposed by the design?
- Are the severe and moderate thresholds consistent with the technical-analysis design already in the repo?
- Could the new advice still trigger `STRONG_RECOMMENDATION_PATTERNS`?
- Could this accidentally hide real high-risk advice or make high-risk names look less risky?
- Are tests sufficient to prevent future drift?
- Does the design avoid touching LLM synthesis, Agent-Reach, claim verification, EV, final recommendation, and technical algorithms?

Stop after writing the review. Do not implement.
