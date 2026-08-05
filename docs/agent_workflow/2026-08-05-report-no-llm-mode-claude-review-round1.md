# Claude Read-Only Review Prompt: Report `--no-llm` Mode

You are Claude Code. Perform a read-only design review in:

`/Users/erichan/testsnow`

Read:

- `AGENTS.md`
- `docs/agent_workflow/2026-08-05-report-no-llm-mode-design.md`
- the runtime and tests named by the design

Review goals:

1. Confirm the five listed LLM owners are complete for the single-stock report
   pipeline and identify any hidden report-owned LLM request path.
2. Verify that an explicit context boolean can disable LLM requests without
   disabling market data, technical analysis, charts, PDF, source intake, or
   canonical Chapter 4 packs.
3. Verify deterministic fallbacks preserve current behavior and do not create a
   second synthesis path.
4. Check the proposed CLI/default/offline-smoke compatibility contract.
5. Check TDD coverage, failure modes, allowed scope, and the `+40/+80` runtime
   budget.

Output one concise review notes file:

`docs/agent_workflow/2026-08-05-report-no-llm-mode-claude-review-round1-notes.md`

Use this structure:

- `verdict: ok | needs_revision`
- `blocker`
- `must_fix`
- `nice_to_have`
- `hidden_llm_owner_audit`
- `requirement_test_gaps`
- `scope_budget_assessment`
- `implementation_ready: yes | no`

Constraints:

- Read only. Do not modify runtime, tests, config, prompts, data, knowledge, or
  reports.
- Do not run a report or make any network/LLM request.
- Preserve the dirty worktree.
- Do not review or alter unrelated H1/H2, broker-note, old-report, or plan-packet
  changes.

After writing the single notes file, stop.
