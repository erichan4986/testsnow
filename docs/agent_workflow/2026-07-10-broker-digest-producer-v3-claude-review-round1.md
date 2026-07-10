# Broker Digest Producer V3 - Claude Review Round 1

Review this design only. Do not modify code:

- `docs/agent_workflow/2026-07-10-broker-digest-producer-v3-design.md`

Write the completed review to:

- `docs/agent_workflow/2026-07-10-broker-digest-producer-v3-claude-review-round1-notes.md`

Inspect these files to verify the design against the current implementation:

- `scripts/utils/broker_research_digest.py`
- `scripts/utils/broker_research_digest_note_writer.py`
- `tests/utils/test_broker_research_digest.py`
- `tests/utils/test_broker_research_digest_note_writer.py`

Focus on:

1. Whether complete source-unit selection can preserve claim/evidence without
   synthesizing new claims.
2. Whether the proposed score parts distinguish OCR damage, incomplete numbers,
   boilerplate, weak evidence, and semantic redundancy.
3. Whether `selection_version` is sufficient to refresh stale notes without
   changing the existing source-boundary contract.
4. Missing failure cases for forecasts, risk notes, no-heading fallbacks, long
   reports, and multiple heading occurrences.
5. Whether the implementation can remain within the stated code budget and two
   runtime files.

Write findings in this format:

```text
verdict: ok | needs_revision | blocked

summary:

blockers:
  - id:
    issue:
    evidence:
    suggested_fix:

must_fix:
  - id:
    issue:
    evidence:
    suggested_fix:

nice_to_have:
  - id:
    issue:
    suggested_fix:

requirement_test_gaps:
  - requirement:
    missing_test:

recommended_next_step:
```

Do not implement changes, run a formal report, access external sites, start
Chrome/CDP, or modify reports/data/knowledge.
