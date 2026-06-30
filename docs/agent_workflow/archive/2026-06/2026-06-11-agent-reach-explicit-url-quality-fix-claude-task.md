# Agent-Reach Explicit URL Quality Fix — Claude Task

You are Claude Code working in `/Users/erichan/testsnow`.

## Context

Phase 0B Web/Jina smoke test used this explicit official Black Sesame URL:

`https://www.blacksesame.com/zh/list_10/972.html`

Fetch succeeded (`agent_reach_status=ok`, 25,924 chars), but the quality gate discarded it with score 29 because `_is_portal_page()` fired on Jina Reader output. Jina included corporate-site navigation, footer, and site-map links around the article body. The raw content score before portal cap was about 66 and should survive.

This is a false positive for explicit user-provided URLs. It should not weaken portal filtering for generic/non-explicit Web pages.

## Goal

Fix Agent-Reach Web quality handling so:

1. Generic portal/navigation Web pages are still discarded.
2. Data-rich article pages loaded from explicit user-provided URLs are not capped below demote solely because Jina included nav/footer chrome.
3. Existing ctx/output contracts remain unchanged.

## Constraints

- Do not modify `KnowledgeSynthesizer`, `SynthesisSkill`, report assembly order, scoring engine, technical analysis code, Xueqiu/CDP/Playwright, or entry scripts.
- Do not add domain whitelists such as `blacksesame.com`.
- Do not globally relax `_is_portal_page()` for all Web records.
- Keep Agent-Reach outputs on `ctx` only; do not mutate `stock_raw` or `raw_data`.
- Keep all changes narrow and test-driven.

## Suggested Implementation

1. In `scripts/utils/report_skills/agent_reach_skill.py`, have `WebConnector.run()` mark records created from explicit URL reads with raw provenance metadata, for example:
   - `user_provided_url: True`
   - `query_type: "web_read"`

   Use simple scalar fields in the raw record so `AgentReachAdapter` preserves them under `item.extra["raw"]`.

2. In `scripts/utils/report_skills/agent_reach_quality_skill.py`, adjust Web portal handling:
   - Keep the existing portal cap for non-explicit Web records.
   - For explicit user-provided URL records, apply the portal penalty and add a reason, but do not cap to `demote_threshold - 1` when the raw score otherwise meets the Web keep threshold.
   - Low-substance explicit URL pages should still be discarded by their low score after penalty.

   Preferred behavior for the smoke-test shape:
   - raw score around 66
   - portal penalty -15
   - final score around 51
   - action `keep` under Web threshold 50, or at minimum `demote` if your exact fixture scores slightly lower

3. Add tests before/with the implementation:
   - `WebConnector.run()` records explicit URL provenance.
   - A data-rich explicit Web article with many nav/footer links and portal keywords is not discarded.
   - A non-explicit data-rich portal page remains discarded; keep the existing regression test passing.
   - A low-substance explicit homepage/navigation page still does not become `keep`.
   - Existing `test_web_portal_page_discarded` and `test_data_rich_web_portal_page_still_discarded` still pass.

## Verification

Run focused tests:

```bash
python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py -q
```

If practical in your local environment, rerun the explicit URL smoke test with:

`https://www.blacksesame.com/zh/list_10/972.html`

Expected outcome:

- Fetch: `ok`
- Quality: item is `keep` or at least `demote`, not `discard`
- Renderer: Agent-Reach section is non-empty and readable

## Notes Output

Write implementation notes to:

`docs/agent_workflow/2026-06-11-agent-reach-explicit-url-quality-fix-claude-notes.md`

Include:

- Files changed
- Tests run and results
- Smoke-test result if run
- Any deviations from this task
