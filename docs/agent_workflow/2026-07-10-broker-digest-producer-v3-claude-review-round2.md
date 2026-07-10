# Broker Digest Producer V3 - Claude Review Round 2

Review the revised design only. Do not modify code:

- `docs/agent_workflow/2026-07-10-broker-digest-producer-v3-design.md`
- `docs/agent_workflow/2026-07-10-broker-digest-producer-v3-claude-review-round1-notes.md`

Write the completed review to:

- `docs/agent_workflow/2026-07-10-broker-digest-producer-v3-claude-review-round2-notes.md`

Confirm whether Round 1 B1/B2 and M1-M7 are now fully represented by explicit
ownership, replacement scope, tests, and per-batch line budgets. In particular:

1. Batch A must replace, not duplicate, boundary/scoring/diagnostic logic.
2. Batch B must replace, not duplicate, validators/fallback/complementarity.
3. A current-schema note missing `selection_version` must refresh in place;
   legacy archive behavior must remain intact.
4. No implementation requirement may depend on renderer, LLM, scoring, target,
   risk, technical, recommendation, collection, or a committed report artifact.
5. The design must prevent synthetic claims by preserving complete source units
   and original order.

Output:

```text
verdict: ok | needs_revision | blocked

summary:

round1_closure:
  - id:
    status: closed | partial | open
    evidence:

remaining_blockers:
  - id:
    issue:
    suggested_fix:

remaining_must_fix:
  - id:
    issue:
    suggested_fix:

budget_assessment:
  batch_a:
  batch_b:

recommended_next_step:
```

Do not implement, run reports, access external sites, start Chrome/CDP, or
modify reports/data/knowledge.
