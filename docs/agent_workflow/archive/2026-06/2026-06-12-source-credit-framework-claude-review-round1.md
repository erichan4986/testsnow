# Claude Review Round 1: Source Credit Framework

You are Claude Code reviewing a design. Do **not** write implementation code.

Read:

- `docs/agent_workflow/2026-06-12-source-credit-framework-design.md`
- `scripts/utils/source_adapter.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/report_skills/agent_reach_skill.py`
- `tests/utils/test_source_adapter.py`

## Review Goal

Assess whether the proposed Phase 1 source-credit framework is the right boundary for moving Agent-Reach toward a knowledge-base-first architecture.

## Questions To Answer

1. Is a separate `scripts/utils/source_credit.py` module the right boundary, or should source credit initially live inside `source_adapter.py`?
2. Does the proposed `SourceCreditResult` schema contain enough metadata for a future evidence-note writer and claim verification layer?
3. Are the proposed credit tiers sensible for A/H stock research?
4. Are any source classes too high or too low risk?
5. Does attaching source-credit metadata in `AgentReachAdapter.to_synthesis_item()` risk breaking existing tests or downstream code?
6. Are the guardrails strong enough to prevent this phase from accidentally changing report conclusions or LLM synthesis?
7. Are the acceptance tests sufficient?
8. What edge cases are missing?

## Constraints

Do not suggest implementation beyond Phase 1 unless clearly marked as future work.

Do not propose:

- changing `KnowledgeSynthesizer`
- writing knowledge-base evidence notes in this phase
- changing report renderer output
- changing Agent-Reach connector behavior
- changing Agent-Reach quality thresholds
- adding network, browser, subprocess, or LLM calls

## Output

Write review notes to:

`docs/agent_workflow/2026-06-12-source-credit-framework-claude-notes.md`

Use this format:

```markdown
# Source Credit Framework Review Round 1

## Status

Ready to implement / Ready with changes / Blocked

## Findings

### High
- ...

### Medium
- ...

### Low
- ...

## Recommendations

- ...

## Test Gaps

- ...

## Final Recommendation

...
```
