# External Producer v4 Architecture Refactor - Claude Review Round 1

Worktree: `/Users/erichan/testsnow/.worktrees/annual-producer-v2`

Review only:

- `docs/agent_workflow/2026-07-22-external-producer-v4-architecture-refactor-design.md`

Read the current runtime and tests needed to verify the design, especially:

- `scripts/utils/curated_external_full_body_viewpoint_claims.py`
- `scripts/utils/curated_external_argument_cards.py`
- `scripts/utils/curated_external_display_projection.py`
- `scripts/utils/curated_external_topic_narrative.py`
- `scripts/utils/curated_external_display.py`
- `scripts/utils/deep_analysis_material_snapshot.py`

## Review questions

1. Does the v4 design fix the actual information-loss root cause rather than moving scope heuristics?
2. Can SourceDocument preserve paragraph boundaries and exact offsets without rewriting source evidence?
3. Is document/block/unit scope resolution deterministic, symmetric and reconstructable for target, peer and
   comparative articles?
4. Can explicit peer entities without company suffixes still terminate target ownership without a stock-specific
   dictionary?
5. Are card ownership, multi-family handling and no-cap behavior unambiguous?
6. Is the ID-only peer selector plus ID-only narrative plan sufficient for readability without allowing new facts?
7. Can `MaterialSnapshot` remain stable while v3/v3.1 readers and display projection are removed?
8. Which preview/acquisition modules are genuinely obsolete, and which still have live callers?
9. Are the four migration batches independently testable and rollback-safe?
10. Is the target of at least 250 net runtime lines removed credible? Name concrete functions/files that should be
    deleted or replaced.

## Required output

Write review notes to:

`docs/agent_workflow/2026-07-22-external-producer-v4-architecture-refactor-claude-review-round1-notes.md`

Use this structure:

- `verdict: ok | needs_revision`
- blockers
- must-fix
- nice-to-have
- requirement-test gaps
- ownership/call-graph audit
- deletion and runtime-budget audit
- whether Batch A is implementation-ready

Do not modify runtime, tests, configuration, source data, canonical packs, knowledge notes or reports. Do not use
the network and do not generate a report.
