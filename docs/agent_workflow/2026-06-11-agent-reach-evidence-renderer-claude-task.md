# Claude Implementation Task: Agent-Reach Phase 3 Evidence Renderer

Implement Phase 3 exactly as specified in:

`docs/agent_workflow/2026-06-11-agent-reach-evidence-renderer-design.md`

## Goal

Add a Markdown-only Agent-Reach evidence section that displays filtered external evidence
for human review. This is a display layer only.

## Scope

Allowed files:

- Create `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- Modify `scripts/utils/reporter/sections/__init__.py`
- Modify `scripts/utils/report_skills/assembly_skills.py`
- Create `tests/reporter/test_agent_reach_evidence_renderer.py`
- Modify `tests/reporter/test_assembly_skills.py`
- Write notes to `docs/agent_workflow/2026-06-11-agent-reach-evidence-renderer-claude-notes.md`

Do not modify:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/reporter/scoring_engine.py`
- Any entry script such as `scripts/xueqiu_monitor_v2.py` or `scripts/run_*.py`
- Xueqiu / Playwright / CDP fetchers
- Generated reports, caches, PDFs, images, or raw data

## Required Behavior

### Renderer

Create `AgentReachEvidenceRenderer`.

Recommended contract:

```python
class AgentReachEvidenceRenderer:
    MAX_KEEP_ITEMS = 6
    MAX_DEMOTE_ITEMS = 4

    @staticmethod
    def required_keys() -> list[str]:
        return ["agent_reach_enabled", "agent_reach_quality_status"]

    def render(self, ctx) -> str:
        ...
```

Behavior:

- If `agent_reach_enabled` is false or missing, return `""`.
- If `agent_reach_quality_status` is `"disabled"`, `"skipped"`, `"error"`, or missing,
  return `""`.
- If `agent_reach_quality_status == "empty"`, return a short section or note containing:
  `Agent-Reach 未检索到可用外部证据。`
- If usable keep/demote items exist, render:
  - `## Agent-Reach 外部证据观察`
  - intro note exactly:
    `> 本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。`
  - status line with fetch status and quality summary counts
  - `### 高优先级证据` table for up to 6 keep items
  - `### 低优先级观察` table for up to 4 demote items
- Never render discard items.
- Never generate analytical conclusions.

### Defensive Quality Metadata Lookup

Do not align `agent_reach_quality_results` and item lists by index.

Build a lookup keyed by:

```python
(title, source, url)
```

where item fields are:

- `title = item.title`
- `source = item.source_platform`
- `url = item.url`

If no matching quality result exists:

- quality score renders as `—`
- reasons render as `未评分`

### Markdown Safety

- Escape `|` as `\|` in title, excerpt, source, and reasons.
- For reasons lists, escape each reason and join with `; `.
- Missing publish time renders as `—`.
- Missing URL renders as `—`.
- Existing URL renders as `[原文](url)`.
- Excerpt should prefer `item.content`; if content is empty, use `item.title`.
- Truncate excerpt to 120 characters and append `...` only when truncated.

### Assembly

Modify `ReportAssemblySkill.RENDERERS` to insert the new renderer after
`deep_analysis` and before `risk`.

Modify `_data_sources()` so it appends `Agent-Reach外部检索` only when:

- `agent_reach_enabled` is true
- `agent_reach_quality_status == "ok"`
- `agent_reach_keep_items` or `agent_reach_demote_items` is non-empty

Do not add Agent-Reach to the header for disabled, skipped, empty, missing binary, or
error-only states.

### Package Export

Update `scripts/utils/reporter/sections/__init__.py` to import/export
`AgentReachEvidenceRenderer`.

## Tests

Use TDD: write failing tests first, run them, then implement.

Add `tests/reporter/test_agent_reach_evidence_renderer.py` with tests for:

1. Disabled/default state returns `""`.
2. `agent_reach_quality_status == "skipped"` returns `""`.
3. `agent_reach_quality_status == "empty"` renders the empty-note text.
4. Keep item renders under `高优先级证据`.
5. Demote item renders under `低优先级观察`.
6. Discard item from `agent_reach_discard_items` does not render.
7. Quality score and reasons render from matching quality result.
8. Out-of-sync quality results do not raise; unmatched item shows `—` and `未评分`.
9. Markdown `|` characters are escaped.
10. Empty publish time renders `—`.
11. More than 6 keep items and 4 demote items are capped.

Modify `tests/reporter/test_assembly_skills.py` with tests for:

1. New renderer appears after `deep_analysis` and before `risk` in
   `ReportAssemblySkill.RENDERERS`.
2. Header data source includes `Agent-Reach外部检索` only for enabled + ok +
   keep/demote non-empty.
3. Header data source does not include Agent-Reach for disabled/skipped/empty.

Run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

## Notes File

After implementation, write:

`docs/agent_workflow/2026-06-11-agent-reach-evidence-renderer-claude-notes.md`

Include:

- Files changed
- Tests run and exact results
- Any deviations from the design
- Confirmation that forbidden files were not modified
- Any blockers

## Guardrails

- Do not run real Agent-Reach searches.
- Do not run browser, PDF export, Playwright, or CDP.
- Do not alter LLM prompts or scoring.
- Do not commit generated artifacts.
- Keep the section wording evidence-oriented; it must not imply confirmed facts or
  investment conclusions.
