# Claude Code Review: Chapter 4 Broker Read-Model Consolidation G2

You are the read-only reviewer in `/Users/erichan/testsnow`.

Read:

- `AGENTS.md`
- `docs/agent_workflow/2026-08-05-chapter4-broker-read-model-consolidation-g2-design.md`
- `docs/agent_workflow/2026-08-05-chapter4-read-model-consolidation-batch-g1-implementation-notes.md`
- the actual current implementations and tests named in the design scope

Do not modify runtime, tests, configuration, prompts, data, knowledge, reports,
or existing workflow files. Do not run network, browser, LLM, report generation,
or destructive commands.

Review the design against the real code, focusing on:

1. whether three optional broker fields are sufficient to reproduce section,
   forecast, risk, attribution, and single-institution output losslessly;
2. whether rendering full snapshot broker rows preserves formal-thin behavior
   without accidentally applying formal-medium selection budgets;
3. whether the single formula `baseline offset + snapshot-global ref` is valid
   for annual, broker, and external rows in every formal-thin path;
4. whether deleting `_max_snapshot_ref`, `_broker_row_author`, raw memo reads,
   and `broker_citation_offset` leaves any hidden caller or citation merge gap;
5. whether source order, absent fallback, attribution normalization, and
   prebuilt-snapshot behavior are fully testable, including generic
   `attribution="研报"` and accepted-but-empty memo behavior;
6. whether the 20-40 line runtime reduction is credible without opaque
   compression or another adapter;
7. whether any requirement-test gap, compatibility risk, or scope omission
   remains.

Write findings to:

`docs/agent_workflow/2026-08-05-chapter4-broker-read-model-consolidation-g2-claude-review-round1-notes.md`

Required output structure:

- `verdict: ok | needs_revision`
- `blockers`
- `must_fix`
- `nice_to_have`
- `requirement_test_gaps`
- `scope_and_budget_assessment`
- `implementation_ready: yes | no`

Each finding must cite concrete file/function evidence. If there are no
blockers or must-fix items, say so explicitly. Stop after writing the notes.
