# Agent-Reach Evidence Renderer Jina Cleanup — Claude Task

You are Claude Code working in `/Users/erichan/testsnow`.

## Context

Runtime validation generated:

- `reports/黑芝麻智能_20260612.md`
- `reports/黑芝麻智能_20260612.pdf`

Agent-Reach config works: the Black Sesame official URL is fetched, quality-gated as `keep` with score `51`, and rendered into the report.

Current report-quality issue:

The Agent-Reach evidence table includes raw Jina Reader prefixes and newlines inside one Markdown table cell:

- `Title:`
- `URL Source:`
- `Markdown Content:`

Example from `reports/黑芝麻智能_20260612.md`:

```markdown
| — | Title: 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最高功能安全认证-黑芝麻智能科技有限公司 — 
URL Source: https://www.blacksesame.com/zh/list_10/972.html

Markdown Content:
# 黑芝麻智能华山A2000U、A2000X获ISO 26262 ASIL-D最... | AgentReach(web) | 51 / ... |
```

This breaks Markdown table shape and causes PDF table-cell overflow.

## Goal

Clean Agent-Reach evidence table display so Web/Jina records render as compact, single-line, readable evidence rows.

## Constraints

- Do not modify `WebConnector`, `agent_reach_quality_skill.py`, pipeline order, report scoring, `KnowledgeSynthesizer`, technical analysis, Xueqiu/CDP/Playwright, or entry scripts.
- Keep the fix in `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` and focused renderer tests.
- Do not change quality scoring or Agent-Reach item retention.
- Do not add domain whitelists.

## Required Behavior

1. `_make_excerpt()` or a new renderer-only helper should remove Jina metadata prefixes from display excerpts:
   - leading `Title: ...`
   - `URL Source: ...`
   - `Markdown Content:`

2. Markdown table cells must be single-line:
   - collapse `\r`, `\n`, tabs, and repeated spaces to one space
   - no raw newline should appear inside the generated table row

3. Avoid title duplication:
   - if content begins with the same title or a Markdown H1 version of the title, do not render `title — title...`

4. Keep useful article body text:
   - for the Black Sesame Jina shape, the evidence summary should mention the ASIL-D certification / A2000U / A2000X content, not just metadata.

5. Keep existing pipe escaping behavior.

6. Keep existing renderer section order and topic classification unchanged.

## Suggested Tests

Modify `tests/reporter/test_agent_reach_evidence_renderer.py`.

Add tests for:

1. Jina metadata cleanup:
   - input content includes:
     - `Title: ...`
     - `URL Source: https://...`
     - `Markdown Content:`
     - `# same title`
     - article body text
   - rendered output does not contain `URL Source:` or `Markdown Content:`
   - rendered table row contains no raw newline inside the row
   - rendered output contains article body text

2. Title duplication:
   - title and first content heading are the same
   - rendered cell does not show duplicated `title — title`

3. Pipe escaping still works:
   - content contains `A|B`
   - output contains `A\\|B`

4. Existing tests still pass.

## Verification

Run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
```

If practical, regenerate or re-render the Agent-Reach section for the existing Black Sesame sample and confirm:

- no `URL Source:` / `Markdown Content:` in the Agent-Reach evidence table
- table row remains one Markdown line
- evidence summary is readable

## Notes Output

Write notes to:

`docs/agent_workflow/2026-06-12-agent-reach-evidence-renderer-jina-cleanup-claude-notes.md`

Include:

- files changed
- tests run
- before/after excerpt from the Agent-Reach table if available
- any blocker or deviation
