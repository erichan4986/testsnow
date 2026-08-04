# Chapter 2 Gross-Margin Trend — Claude Review Round 1

## Review Target

Read only:

- `docs/agent_workflow/2026-07-31-chapter2-gross-margin-trend-design.md`
- the current implementations named in its Allowed Runtime Scope
- corresponding tests

Do not modify code, tests, config, caches, reports or prompts.

## Questions

1. Does the optional cache metric preserve existing v1 cache and amount-history
   behavior?
2. Are direct A/H gross-margin source contracts exact enough to prevent quarter,
   currency or field-identity leakage?
3. Can either derived formula combine different source rows or accidentally use
   `TOTAL_OPERATE_COST`?
4. Is direct-conflict precedence deterministic and fail-closed?
5. Does the proposed reader/intake split keep gross margin out of MetricSeries,
   FinancialScan and scoring without creating a second calculation owner?
6. Are `*` provenance and percentage-point change semantics sufficient and testable?
7. Are the allowed files, runtime budget and stop conditions credible?
8. Which required tests or negative fixtures are still missing?

## Output

Write findings to:

`docs/agent_workflow/2026-07-31-chapter2-gross-margin-trend-claude-review-round1-notes.md`

Use this structure:

- `verdict: ok | needs_revision`
- blockers
- must-fix
- nice-to-have
- requirement-test gaps
- scope/budget assessment
- implementation_ready: yes | no

Do not implement fixes.
