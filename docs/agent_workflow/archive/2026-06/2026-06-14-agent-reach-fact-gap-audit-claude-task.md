# Claude Implementation Task: Agent-Reach Fact Gap Audit

Read first:

- `docs/agent_workflow/2026-06-14-agent-reach-fact-gap-audit-design.md`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `tests/reporter/test_agent_reach_evidence_renderer.py`

## Goal

Add a display-only "核心事实缺口观察" subsection to the Agent-Reach evidence section.

The subsection should compare kept Agent-Reach evidence topics against the existing `core_facts` table and highlight possible coverage gaps for human review.

## Allowed Files

Modify:

- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `tests/reporter/test_agent_reach_evidence_renderer.py`

Add:

- `docs/agent_workflow/2026-06-14-agent-reach-fact-gap-audit-claude-notes.md`

Do not modify other files unless a focused test proves it is unavoidable. Stop and report before expanding scope.

## Forbidden

- Do not modify `KnowledgeSynthesizer`, synthesis prompts, or citation parsing.
- Do not modify scoring, risk, technical analysis, EV, position sizing, or final recommendation logic.
- Do not mutate `core_facts`.
- Do not write `knowledge/`, `data/raw/`, or generated reports from tests.
- Do not fetch external websites.
- Do not start Chrome/CDP or touch Xueqiu details.

## Required Behavior

1. Reuse the existing deterministic topic classification in `agent_reach_evidence_renderer.py`.
2. Build topic coverage from `core_facts` by scanning each fact's `fact` and `data` fields.
3. Only kept Agent-Reach items may create gap observations.
4. Demoted items must not create gap observations.
5. If an Agent-Reach keep item's topic is not covered by `core_facts`, render it in a "核心事实缺口观察" subsection.
6. Cap gap observations at 4.
7. Use conservative wording:
   - "外部证据提示"
   - "核心事实基座未覆盖该主题"
   - "人工复核是否需要补充事实基座"
8. Include a disclaimer that this subsection:
   - is read-only,
   - does not confirm facts,
   - does not affect scoring or conclusions.
9. Do not emit numbered citation markers like `[^1]` from this subsection.

## Test Requirements

Write failing tests first in `tests/reporter/test_agent_reach_evidence_renderer.py`, then implement.

Required tests:

- Gap subsection renders when a keep item topic is absent from `core_facts`.
- Gap subsection does not render when `core_facts` already cover that topic.
- Demote-only items do not create fact gap rows.
- Output contains the non-impact disclaimer.
- Output contains no numbered citation markers from the gap subsection.
- Gap rows are capped at 4.

Run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py -q
```

Optional, if quick:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
```

## Notes Output

Write:

`docs/agent_workflow/2026-06-14-agent-reach-fact-gap-audit-claude-notes.md`

Include:

- Files changed.
- Tests run and results.
- A short sample of the rendered subsection.
- Any deviations from the task.
- Any blocker.

## Stop Conditions

Stop and report if:

- You need to change files outside the allowed list.
- You need to modify synthesis prompts, citations, scoring, technical analysis, or report pipeline order.
- Tests require network, browser, CDP, or external data.
- Existing renderer contracts appear incompatible with the design.
