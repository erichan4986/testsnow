# Annual Producer v2 Claude Review Round 2

## Goal

Perform a read-only verification of the revised Annual Producer v2 design. Do
not broaden the review into implementation style preferences or deferred
External Producer work.

## Read First

- `docs/agent_workflow/2026-07-11-annual-producer-v2-design.md`
- `docs/agent_workflow/2026-07-11-annual-producer-v2-claude-review-round1-notes.md`
- the current producer, note writer/loader, material pack, annual memo,
  MaterialSnapshot, renderer, and focused tests referenced by those documents

## Round 2 Questions

1. Does one canonical family now flow directly through v2 note,
   `annual_report_memo.display_group`, and `MaterialRow.render_role`, with the
   five old intermediate annual roles and title inference scheduled for deletion?
2. Is the 4.4 boundary exact and enforceable: only annual rows with
   `argument_complete=true` enter `price_path_rows`, while atomic and adapted-v1
   rows remain 4.1-only and cannot return through a renderer fallback?
3. Is the SourceUnit model sufficient to prove source substring, monotonic
   order, contiguous assembly, and non-overlapping ownership? Is the temporary
   v1 proxy-unit behavior safe and unmistakably non-current?
4. Is there still exactly one candidate/selection path, including sparse
   material? Confirm that `admission_invariant_violation` is not a second
   fallback selector.
5. Is single-family resolution deterministic for ambiguous units, with secondary
   signals recorded instead of duplicate cards?
6. Are all canonical annual count caps identified through producer, pack, memo,
   snapshot, and formal-medium/formal-thin renderer? Confirm that retaining the
   optional LLM display `max_display_items` budget cannot cap Chapter 4.
7. Is v1/v2 coexistence deterministic, v2-preferred, refreshable, and removable
   in Batch B without a permanent compatibility layer?
8. Are the diagnostics keys, concrete schema/selection versions, real samples,
   requirement-test matrix, and failure behavior complete enough to implement?
9. Is the runtime budget credible given the named same-batch deletions? Identify
   any old helper or mapping that the design still fails to schedule for removal.

## Boundaries

- Do not implement code or modify the design.
- Do not generate reports.
- Do not modify config, reports, knowledge, data, prompts, or existing dirty
  worktree files.
- The only allowed output file is the Round 2 notes below.
- Scoring, target price, risk scoring, technical analysis, recommendation, LLM
  prompts, collection, browser, and External Producer remain out of scope.

## Output

Write:

`docs/agent_workflow/2026-07-11-annual-producer-v2-claude-review-round2-notes.md`

Use this structure:

- `verdict: ok | needs_revision | blocked`
- `round1_findings`: F-01 through F-06, each `closed | open | partially_closed`
  with code/design evidence
- `remaining_blocker`
- `remaining_must_fix`
- `nice_to_have`
- `requirement_test_gaps`
- `batch_a_budget`
- `batch_b_budget`
- `implementation_plan_ready: yes | no`
- `recommended_next_step`

Do not reopen an accepted design decision merely as a stylistic preference. A
remaining blocker or must-fix must name the exact contract that is ambiguous or
unimplementable and point to the relevant current code.

## Stop Conditions

Stop and report rather than editing another file if review would require:

- changing any out-of-scope business path;
- implementing code to determine correctness;
- running network, browser, Chrome/CDP, or Xueqiu operations;
- modifying anything except the Round 2 notes file.
