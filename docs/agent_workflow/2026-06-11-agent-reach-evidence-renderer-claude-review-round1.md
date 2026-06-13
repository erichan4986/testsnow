# Claude Review Round 1 Prompt: Agent-Reach Phase 3 Evidence Renderer

Please review the Phase 3 design only. Do not write code.

Design file:

`docs/agent_workflow/2026-06-11-agent-reach-evidence-renderer-design.md`

Context:

- Phase 1 added optional Agent-Reach query/fetch plumbing behind
  `build_stock_report_pipeline(enable_agent_reach=True)`.
- Phase 2 added deterministic quality filtering:
  `agent_reach_keep_items`, `agent_reach_demote_items`,
  `agent_reach_discard_items`, `agent_reach_quality_results`,
  `agent_reach_quality_status`, and `agent_reach_quality_summary`.
- Agent-Reach data still must not enter `KnowledgeSynthesizer`, scoring, or LLM prompts.
- Phase 3 should only render filtered evidence for human review.

Review goals:

1. Check whether a standalone `AgentReachEvidenceRenderer` is the right boundary.
2. Check whether placing it after `deep_analysis` and before `risk` is safe for report
   readability and numbering.
3. Check whether the renderer contract is sufficiently defensive for malformed
   `SynthesisItem` records.
4. Check whether `_data_sources()` should include Agent-Reach only when keep/demote items
   exist.
5. Identify any missing tests, especially around Markdown escaping, disabled/empty states,
   item limits, and accidental rendering of discarded items.
6. Confirm the design keeps Agent-Reach out of `SynthesisSkill`,
   `KnowledgeSynthesizer`, `scoring_engine.py`, entry scripts, and Xueqiu/CDP fetchers.

Please write your feedback to:

`docs/agent_workflow/2026-06-11-agent-reach-evidence-renderer-claude-notes.md`

Use this structure:

```markdown
# Agent-Reach Phase 3 Evidence Renderer Claude Notes

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
- Do not suggest LLM synthesis in Phase 3 unless explicitly framed as a later phase.
