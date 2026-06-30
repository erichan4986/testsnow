# Claude Review Round 1 Prompt: Agent-Reach Phase 3B Themed Evidence

Please review the Phase 3B design only. Do not write code.

Design file:

`docs/agent_workflow/2026-06-11-agent-reach-themed-evidence-design.md`

Context:

- Phase 3 added a safe Markdown-only `AgentReachEvidenceRenderer`.
- The current section is safe but too abrupt: it renders keep/demote tables directly.
- The user wants the Agent-Reach evidence to feel less pasted-on.
- Phase 3B should improve presentation through deterministic topic grouping only.
- Do not use LLM synthesis, do not affect scoring, and do not change pipeline behavior.

Review goals:

1. Check whether upgrading the existing renderer is the right boundary.
2. Check whether deterministic topic classification is enough for this phase.
3. Review topic labels, topic order, and keyword signals.
4. Check whether demote items should remain under `待人工复核线索` or be grouped by topic.
5. Identify missing tests, especially classification priority, Markdown escaping regression,
   truncation regression, out-of-sync quality results, and disabled/empty behavior.
6. Confirm the design keeps Agent-Reach out of `SynthesisSkill`,
   `KnowledgeSynthesizer`, `scoring_engine.py`, entry scripts, and Xueqiu/CDP fetchers.

Please write feedback to:

`docs/agent_workflow/2026-06-11-agent-reach-themed-evidence-claude-notes.md`

Use this structure:

```markdown
# Agent-Reach Phase 3B Themed Evidence Claude Notes

## Status

Ready to implement / Ready with changes / Blocked

## Findings

- High: ...
- Medium: ...
- Low: ...

## Required Design Changes

- ...

## Test Gaps

- ...

## Scope Guardrails

- ...
```

Important guardrails:

- Do not write implementation code.
- Do not run real Agent-Reach searches.
- Do not modify files outside `docs/agent_workflow/`.
- Do not suggest LLM synthesis in this phase unless explicitly framed as a later phase.
