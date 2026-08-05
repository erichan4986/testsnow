# Claude Code Review: Chapter 4 Read-Model Consolidation Batch G1

> **Design**: `docs/agent_workflow/2026-08-05-chapter4-read-model-consolidation-batch-g1-design.md`
> **Audit**: `docs/agent_workflow/2026-08-05-chapter4-read-model-consolidation-batch-g-audit.md`
> **Expected Output**: `docs/agent_workflow/2026-08-05-chapter4-read-model-consolidation-batch-g1-claude-review-round1-notes.md`

You are reviewing the design only. Do not implement code in this round.

## Review Objective

Verify that the proposed consolidation removes duplicate renderer ownership
without changing Chapter 4 content, profile behavior, or citation identity.

## Files To Inspect

- `docs/agent_workflow/2026-08-05-chapter4-read-model-consolidation-batch-g1-design.md`
- `docs/agent_workflow/2026-08-05-chapter4-read-model-consolidation-batch-g-audit.md`
- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/test_runtime_hygiene.py`

## Required Review Questions

1. Does direct annual `MaterialRow` rendering preserve all current visible
   behavior while removing renderer-side admission and portrait scoring?
2. Is the suspicious-zero boundary exact: reject only formal facts, retain
   explanation rows, and avoid broad numeric filtering?
3. Is deferring formal-thin broker unification necessary because the current
   path renders sections, forecast ranges, and risks while `MaterialRow` loses
   the separate forecast metric/period boundary?
4. Does the revised design correctly preserve the existing annual, broker, and
   external offset formulas rather than collapsing them?
5. Do the existing `[^5]`/`[^6]` fixtures plus the proposed broker parity test
   fully guard formal-thin citation regression?
6. Are forecast, risk, single-institution, and empty-broker behaviors explicitly
   preserved?
7. Could formal-medium or formal-rich behavior change through shared helpers?
8. Are any named deletion candidates used by runtime, previews, tools, dynamic
   registries, or public package imports not covered by the audit?
9. Is the 80-130 net deletion target credible without compressing code at the
   expense of readability or adding a new adapter path?
10. Are any requirement-test gaps or hidden scope expansions missing from the
    design?

## Constraints

- Do not modify runtime, tests, configuration, prompts, data, knowledge, or
  reports.
- Do not access the network, start browsers, run LLMs, or generate reports.
- Write only the required review notes file.
- Inspect the real code and tests; do not rely only on the audit summary.
- Keep findings concise and classify each as `blocker`, `must-fix`, or
  `nice-to-have`.

## Required Notes Format

```markdown
# Chapter 4 Read-Model Consolidation Batch G1 Claude Review Round 1 Notes

verdict: ok | needs_revision
implementation_ready: yes | no

## Blockers
- ...

## Must-Fix
- ...

## Nice-To-Have
- ...

## Requirement-Test Gaps
- ...

## Runtime Budget Assessment
- ...

## Scope And Citation Audit
- ...

## Recommendation
- R2 required: yes | no
- Reason: ...
```

Stop after writing the notes. Do not implement or repair the design.
