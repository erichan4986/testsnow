# Claude Review Round 1: Agent-Reach Claim/Risk Bridge

You are Claude Code reviewing a combined design in `/Users/erichan/testsnow`.

Read:

- `AGENTS.md`
- `docs/agent_workflow/2026-06-14-agent-reach-claim-risk-bridge-design.md`
- `scripts/utils/source_credit.py`
- `scripts/utils/evidence_note_writer.py`
- `scripts/utils/claim_verification.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/report_skills/evidence_note_skill.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/stock_reporter.py`
- `tests/reporter/test_pipeline_integration.py`
- `tests/reporter/test_stock_reporter_agent_reach_config.py`
- `tests/reporter/test_scoring_engine_risk.py`

## Goal

Review the design for one combined implementation phase:

```text
Agent-Reach source_credit
  -> evidence notes
  -> claim verification
  -> structured_risk_signals
  -> risk_score_section()
```

The goal is speed with quality: one implementation task after this review if there is no blocker.

## Review Instructions

Do not implement.
Do not modify source or tests.
Do not run report generation.
Do not access network, LLM, browser, Chrome/CDP, Xueqiu, or Zhihu.

Append feedback directly to:

`docs/agent_workflow/2026-06-14-agent-reach-claim-risk-bridge-design.md`

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

- Does the design correctly reuse existing source_credit, evidence note writer, and claim verification logic?
- Is adding a new pure `claim_risk_signals.py` helper preferable to changing `claim_verification.py` or `scoring_engine.py`?
- Is inserting a new skill after `SynthesisSkill` and before `scoring_skill` safe?
- Could `structured_risk_signals` be produced too aggressively from company official product news?
- Are verified/supported/unverified mappings conservative enough?
- Does the design avoid Agent-Reach becoming numbered citations or LLM synthesis input?
- Is config gating clear enough, especially around writing `knowledge/` evidence notes?
- Should implementation modify `config/stocks.json` now, or leave config changes to runtime validation?
- Are tests sufficient to prove default behavior unchanged?

Stop after writing review feedback. Do not implement.
