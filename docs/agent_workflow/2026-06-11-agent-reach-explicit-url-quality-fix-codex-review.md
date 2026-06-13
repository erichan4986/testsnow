# Agent-Reach Explicit URL Quality Fix — Codex Review

## Verdict

Accepted.

The implementation matches the task: explicit user-provided Web URLs now receive a portal penalty without being capped below demote, while generic Web records without provenance are still force-discarded when portal detection fires.

## Verified Files

- `scripts/utils/report_skills/agent_reach_skill.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `tests/reporter/test_agent_reach_connector.py`
- `tests/reporter/test_agent_reach_quality_skill.py`
- `docs/agent_workflow/2026-06-11-agent-reach-explicit-url-quality-fix-claude-notes.md`

## Requirement Check

- No domain whitelist was added.
- `_is_portal_page()` was not globally relaxed.
- Generic portal pages still cap below demote and discard.
- Explicit `web_read` URL pages keep the penalized score, so data-rich articles can survive.
- Low-substance explicit URL pages still discard on low score after penalty.
- No changes were made to `KnowledgeSynthesizer`, `SynthesisSkill`, report assembly order, scoring engine, technical analysis code, Xueqiu/CDP/Playwright, or entry scripts.

## Verification

Fresh command run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py -q
```

Result:

```text
83 passed in 1.40s
```

## Notes

`WebConnector` currently only reads explicit URL lists, so marking its records with `user_provided_url: True` is consistent with the current connector contract. If a future Web search connector is added, provenance must stay separated so search-discovered Web pages do not inherit explicit-URL trust.
