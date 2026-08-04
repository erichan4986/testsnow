# External Producer v3 Selection Stability and Efficiency - Claude Review Round 1

## Review Mode

Read-only design review. Do not modify runtime code, tests, config, caches, knowledge, reports, or `/tmp`
Gate artifacts. Do not call a live model or access the network.

## Inputs

Read:

- `docs/agent_workflow/2026-07-17-external-producer-v3-selection-stability-efficiency-design.md`
- `docs/agent_workflow/2026-07-17-external-producer-v2-evidence-unit-selector-design.md`
- `scripts/utils/curated_external_argument_cards.py`
- `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- the corresponding producer, reader, display, and profile tests
- `/Users/erichan/.codex/attachments/305c204b-5f6d-4d31-9c2c-21fee2548d4c/pasted-text.txt`

## Questions

1. Does deterministic target bundling fully prevent optional peer families from changing target coverage or
   profile routing?
2. Is the continuation rule narrow enough to avoid entity misbinding while retaining legitimate pronoun or
   product continuations?
3. Can one shared preparation helper keep the refresh wrapper and canonical pack builder aligned without a
   hidden second selector path?
4. Is optional-peer admission generic, deterministic, and no-cap, or can it silently discard useful material
   through vague predicates?
5. Are global exact dedupe and same-source containment dedupe safe for evidence/citation diversity?
6. Does selector versioning make old live packs fail stale without unnecessary schema churn?
7. Are the diagnostics sufficient to prove latency improvement and distinguish filtering from LLM skipping?
8. Are the tests adequate for source order, target coverage invariance, exact evidence identity, profile
   stability, retries, and no-cap behavior?
9. Is the net +140 runtime hard stop credible when existing mixed-pool code is replaced rather than retained?
10. Did the design accidentally broaden scope into prompt synthesis, report rendering, scoring, or production
    cutover?

## Output

Write findings to:

`docs/agent_workflow/2026-07-17-external-producer-v3-selection-stability-efficiency-claude-review-round1-notes.md`

Use:

```text
verdict: ok | needs_revision | blocked

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

scope_and_budget:
  status:
  evidence:

implementation_ready: yes | no
```

If there are no findings in a category, write `none`. Stop after writing the review notes.
