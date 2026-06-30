# Claude Validation Task: Agent-Reach Phase 3B Sample Report Review

## Goal

Generate or assemble a sample report that includes mocked Agent-Reach keep/demote evidence,
then review whether the Phase 3B themed evidence section reads naturally in Markdown and,
if local permissions allow, PDF.

This is a validation task, not a feature implementation task.

## Context

Phase 3B changed:

- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `tests/reporter/test_agent_reach_evidence_renderer.py`

The renderer now shows:

- `本期外部证据概览`
- `主题化证据观察`
- topic groups for keep items
- `待人工复核线索` for demote items

Codex review:

`docs/agent_workflow/2026-06-11-agent-reach-themed-evidence-codex-review.md`

## Scope

Allowed:

- Run existing focused tests.
- Use mocked Agent-Reach data to assemble a temporary/sample Markdown report.
- If local Chromium/PDF permissions allow, export the sample report to PDF and visually inspect the Agent-Reach section.
- Write findings to:
  `docs/agent_workflow/2026-06-11-agent-reach-themed-evidence-sample-report-claude-notes.md`

Avoid source changes unless a clear bug is found.

If a bug is found:

- Make the smallest fix.
- Add or update a focused test.
- Explain the bug, fix, and test in the notes file.

Do not modify:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/reporter/scoring_engine.py`
- Entry scripts such as `scripts/xueqiu_monitor_v2.py` or `scripts/run_*.py`
- Xueqiu / Playwright / CDP fetchers

Do not run real Agent-Reach searches unless the user explicitly asks in a later task.

## Suggested Validation Approach

Use mocked `SynthesisItem` records and `SkillContext` data, not real web search.

Create a temporary local validation script only if needed, preferably under `/tmp` or another
non-repo temp path. Do not commit that script.

The mocked context should include:

- `agent_reach_enabled=True`
- `agent_reach_status="ok"`
- `agent_reach_quality_status="ok"`
- `agent_reach_quality_summary={"keep": 5, "demote": 2, "discard": 3, ...}`
- `agent_reach_keep_items` containing examples for:
  - 产品/量产进展
  - 客户/定点/订单
  - 竞争对手动态
  - 财报/业绩线索
  - 待核查线索
- `agent_reach_demote_items` containing two weak signals
- `agent_reach_quality_results` with matching scores and reasons

Then validate at least one of these paths:

1. Render `AgentReachEvidenceRenderer.render(ctx)` directly and save the section snippet for review.
2. Preferably assemble a full Markdown report through `ReportAssemblySkill` with a minimal valid context and verify the section placement after deep analysis and before risk.

If using `ReportAssemblySkill`, include enough baseline fields to avoid unrelated renderer failures:

- `stock_name`
- `date_str`
- `output_dir`
- `pillar_scores`
- `total_score`
- `quote`
- `consensus`
- `synthesis`
- `keep_posts`
- `all_posts`
- `cross_source_summary`

## Markdown Review Checklist

Check the generated Markdown for:

- Agent-Reach section appears after `## 四、深度分析` and before risk content.
- The section does not contain old headings:
  - `### 高优先级证据`
  - `### 低优先级观察`
- The section contains:
  - `### 本期外部证据概览`
  - `### 主题化证据观察`
  - at least two topic headings
  - `### 待人工复核线索`
- Overview `主要主题` includes only keep-item topics.
- Demote-only topics are not promoted into `主要主题`.
- The disclaimer is visible and unchanged:
  `本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。`
- Wording does not imply the external evidence is verified fact.
- Tables are readable and not too wide in Markdown.
- Long excerpts are truncated.
- Markdown pipes inside content are escaped.

## PDF Review Checklist

Only do this if local permissions allow PDF export.

Check:

- No table overflow or clipped content around the Agent-Reach section.
- Topic headings stay visually attached to their tables.
- The section does not consume excessive report length.
- The disclaimer remains visible.

If PDF export is blocked by Chromium/macOS sandbox permissions, record that in notes and do
not treat it as a code failure.

## Tests To Run

Run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_assembly_skills.py tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

If any source fix is made, run the relevant focused test again after the fix.

## Notes File

Write:

`docs/agent_workflow/2026-06-11-agent-reach-themed-evidence-sample-report-claude-notes.md`

Use this structure:

```markdown
# Agent-Reach Phase 3B Sample Report Claude Notes

## Status

Accepted / Accepted with small fix / Blocked

## Files Changed

- ...

## Validation Artifacts

- Markdown sample path:
- PDF sample path, if generated:

## Markdown Review

- ...

## PDF Review

- ...

## Tests

- ...

## Issues Found

- ...

## Recommended Follow-Ups

- ...
```

## Guardrails

- Do not run real Agent-Reach searches.
- Do not modify LLM prompts, synthesis, scoring, entry scripts, or data collectors.
- Do not commit generated reports or temp scripts.
- Keep the validation evidence-oriented; do not add investment conclusions.
