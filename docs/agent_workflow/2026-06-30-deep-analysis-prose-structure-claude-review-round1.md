# Claude Review Round 1 — Deep Analysis Prose Structure

You are Claude Code reviewing a design in `/Users/erichan/testsnow`.

Read:

- `docs/agent_workflow/2026-06-30-deep-analysis-prose-structure-design.md`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/report_prose_quality.py`
- `tests/reporter/test_report_prose_quality.py`
- `reports/中际旭创_20260630.md` if present

Goal:

Review whether the design is safe and sufficient to reduce 4.1-4.3 repetition, long paragraphs, long sentences, template-like wording, and duplicate 4.4 citations without breaking:

- formal_first source boundary,
- citation traceability,
- display-only isolation for 4.4,
- existing report quality checks,
- no-social-in-4.1-4.3 rule.

Do not modify code, docs, configs, data, reports, tests, or prompts. This is read-only review.

Focus your review on:

1. Whether changing `KnowledgeSynthesizer` prompts is enough, or whether deterministic post-processing is needed.
2. Whether table-first output risks breaking citation parsing/rendering.
3. Whether the proposed prose checker is too noisy, under-specified, or overfit to 中际旭创.
4. Whether 4.1 / 4.2 / 4.3 section contracts are too strict or still too overlapping.
5. Whether duplicate 4.4 citation merging should be implemented in renderer, narrative JSON production, or both.
6. Missing tests and exact files where those tests should live.

Output:

Write your review to:

`/tmp/deep_analysis_prose_structure_review_round1.md`

Use this format:

```markdown
# Deep Analysis Prose Structure Review Round 1

## Verdict

- Status: ready_to_implement / needs_design_revision / blocked
- Blocker: N
- Must-fix: N
- Nice-to-have: N

## Findings

### Blockers

- ...

### Must-fix

- ...

### Nice-to-have

- ...

## Answers To Open Questions

1. ...

## Recommended Implementation Scope

- Phase(s) safe to implement now:
- Phase(s) to defer:
- Required focused tests:

## Verification Notes

- Files inspected:
- Commands run, if any:
- Whether git status changed:
```

Constraints:

- Do not run LLM/API.
- Do not access external websites.
- Do not start Chrome/Playwright/CDP.
- Do not run full pytest unless you choose to run a tiny read-only focused command; review can be static.
- Stop and report if you believe implementation would require changing scoring, risk, technical analysis, source collection, or `xueqiu_monitor_v2.py`.
