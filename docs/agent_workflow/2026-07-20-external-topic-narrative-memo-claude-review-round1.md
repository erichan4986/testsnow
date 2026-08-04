# External Topic Narrative Memo Round 1 Review

## Role

Perform a read-only design review. Do not modify runtime code, tests, config, data, Knowledge notes, packs, or reports. Do not access the network or run a live LLM.

## Read

- `docs/agent_workflow/2026-07-20-external-topic-narrative-memo-design.md`
- `scripts/utils/curated_external_argument_cards.py`
- `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- `scripts/previews/curated_external_full_body_viewpoint_preview.py`
- `scripts/utils/curated_external_display.py`
- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/report_quality.py`
- relevant tests for those modules

## Review Questions

1. Does requiring one complete-prefix quote for every evidence unit materially improve fluency without creating a second evidence owner or silently hiding evidence?
2. Can an optional `topic_narratives` envelope safely remain inside `curated_external_argument_pack.v3`, or must the top-level pack schema/version change?
3. Is the source-pack fingerprint complete and stable enough to prevent stale narratives?
4. Are exact-prefix and terminal-boundary checks sufficient to prevent subject loss, truncation, unsupported entities, unsupported numbers, or causal additions?
5. Does filtering narrative parts to selected visible cards, followed by full visible-card coverage validation, prevent a memo from restoring a card removed by annual/broker owner selection without causing unnecessary fallback?
6. Does the proposed `MaterialSnapshot`/`Chapter4Section` structure preserve formal-thin full-snapshot citation offsets and formal-medium visible-citation filtering?
7. Does private-key-only display projection prove that memo text cannot affect exact-card synthesis text, profile routing, freshness, executive summary, or recommendation?
8. Can the existing report source-boundary and quality gates safely recognize the new target/peer lead phrases without weakening confirmation checks or moving refs after punctuation?
9. Is one additional stock-level LLM request realistic for response size and JSON completeness with no topic/card cap, one HTTP attempt, and a 60-second timeout?
10. Are Chapter 4.4, profile routing, scoring, target, risk, technical analysis, recommendation, and `KnowledgeSynthesizer` sufficiently isolated?
11. Are the two batch budgets (+220/+170), combined +380 stop, tests, and live acceptance gate credible?

## Required Output

Write findings to:

`docs/agent_workflow/2026-07-20-external-topic-narrative-memo-claude-review-round1-notes.md`

Use:

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

scope_and_budget:
  assessment:

implementation_ready: yes | no
```

Every finding must cite a concrete design section and, where relevant, a current code path or test. Do not write implementation code. If there are no blockers or must-fix findings, say so explicitly.
