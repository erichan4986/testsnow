# Claude Review Round 1: Structured Risk Signals

Review target:

- `docs/agent_workflow/2026-06-14-structured-risk-signals-design.md`

Relevant code:

- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `tests/reporter/test_risk_renderer.py`

## Review Goal

Evaluate whether the design safely stabilizes qualitative risk scoring without hiding risk observations or accidentally changing unrelated scoring behavior.

## Questions To Answer

1. Does separating structured scored signals from free-text LLM observations solve the observed risk-score drift?
2. Is defaulting `score_llm_keyword_risks=False` safe for existing reports?
3. Is the structured signal schema too broad or too narrow for this phase?
4. Are the scoring rules for `verified/supported/unverified` reasonable?
5. Are there hidden paths where Agent-Reach, claim verification, or core-fact provenance could accidentally affect risk scoring in this phase?
6. Are the proposed tests enough?
7. Does this require R2 before implementation?

## Output Format

Append review directly to `docs/agent_workflow/2026-06-14-structured-risk-signals-design.md` under:

```markdown
## Round 1 Feedback

### Status

Ready to implement / Must-fix before task / Blocked

### Findings

- [severity] finding...

### Recommendations

- ...

### Open Questions

- ...

### R2 Needed

Yes / No
```

Do not modify source code.
Do not create implementation task.
Do not run report generation.
Do not use network, browser, CDP, Xueqiu, Zhihu, or LLM calls.
