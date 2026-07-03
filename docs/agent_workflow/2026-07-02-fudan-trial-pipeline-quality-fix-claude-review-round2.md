# Claude Round 2 Review Prompt — Fudan Trial Pipeline Quality Fix

You are Claude Code reviewing a revised design in `/Users/erichan/testsnow`.

This is a **read-only design review**. Do not modify code, config, tests, reports, or generated files.

## Read First

1. `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design.md`
2. `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design-delta.md`
3. `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-claude-review-notes.md`

Only inspect code if needed to verify whether the revised design matches the actual repo shape.

## Review Scope

Do **not** re-review the entire original problem. Focus only on whether Round 1 findings are closed:

- B1: `stock_config.industry/competitors/product_exposure_terms` availability and regression safety.
- B2: 4.3 missing root cause in `deep_analysis_renderer.py` and renderer fallback priority.
- B3: missing `product_exposure_terms` fallback and no false killing of existing formal industry reports.
- MF1: header uses `stock_config` first and falls back to `INDUSTRY_MAP/COMPETITOR_MAP`.
- MF2: financial unit issue is assigned to upstream table/cell parser, not only `_filing_fact`.
- MF3: financial missing-data gate is metric-specific.
- MF4: renderer-layer tests are included.
- MF5: Direct-Only underfilled items stop/warning condition is included.

Also check whether the revised batch order is implementable:

1. Batch 1.5 config completion.
2. Batch D header + renderer fallback.
3. Batch A quality gates.
4. Batch B Direct-Only source relevance.
5. Batch C financial fact pack + unit normalization.
6. Batch E smoke/regression.

## Constraints To Enforce

- No hand-editing generated report content.
- Fix pipeline behavior, not this one report.
- 4.1/4.2/4.3 canonical synthesis must not consume social/雪球/知乎/微信 raw content.
- 4.4 remains display-only.
- Multi-hop industry chains remain out of canonical sections unless a future deterministic chain validator exists.
- Do not recommend changing Xueqiu/CDP/Playwright/external crawling in this task.

## Output File

Write your review to:

`docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-claude-review-round2-notes.md`

## Required Output Structure

```yaml
verdict: ok | needs_revision
summary: "<one paragraph>"
round1_closure:
  B1: closed | still_open
  B2: closed | still_open
  B3: closed | still_open
  MF1: closed | still_open
  MF2: closed | still_open
  MF3: closed | still_open
  MF4: closed | still_open
  MF5: closed | still_open
blockers:
  - id: Bx
    title: ""
    evidence: ""
    required_fix: ""
must_fix:
  - id: MFx
    title: ""
    evidence: ""
    required_fix: ""
nice_to_have:
  - id: Nx
    title: ""
    evidence: ""
    suggestion: ""
implementation_readiness:
  recommended_next_step: "proceed_to_task | revise_design_again"
  batch_order_ok: true | false
  notes: ""
git_status:
  changed_files_observed: []
  unexpected_changes: []
```

If all Round 1 items are closed, set `verdict: ok` and do not invent new scope unless it is a direct blocker to implementing this design.
