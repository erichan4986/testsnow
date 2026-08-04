# Claude Read-Only Review Prompt: Scripts Audit Batch B

Worktree: `/Users/erichan/testsnow`

Read:

- `docs/agent_workflow/2026-08-04-scripts-full-stack-audit-batch-b-design.md`
- `AGENTS.md`
- the runtime and tests named by the design

Perform a read-only design review. Do not edit runtime, tests, configuration,
prompts, data, knowledge, or reports. Verify every deletion candidate with
actual repository references, imports, package exports, dynamic registries,
previews, tools, README contracts, and active replacement owners.

Pay particular attention to:

1. whether `stock_quote_eastmoney` or `fund_flow_daily` has a hidden public or
   dynamic caller;
2. whether removing the exported `valuation_industry_judgment` can affect any
   current package import path;
3. whether `_extract_conclusion` is truly outside render execution;
4. whether the replacement owners cover the same active report duties without
   changing behavior;
5. whether the TDD matrix and 80-line deletion gate are credible.

Write findings to:

`docs/agent_workflow/2026-08-04-scripts-full-stack-audit-batch-b-claude-review-round1-notes.md`

Use `blocker`, `must-fix`, and `nice-to-have`; include a requirement-test matrix,
scope audit, exact deletion estimate, and `implementation_ready: yes|no`.
Stop after writing notes. Do not implement or commit.
