# Agent-Reach Phase 3 Evidence Renderer Codex Review

Date: 2026-06-11

## Status

Accepted after Codex validation and one small fix.

Phase 3 adds a Markdown-only evidence section for filtered Agent-Reach results. It remains a
display layer and does not feed Agent-Reach content into synthesis, scoring, or entry
scripts.

## Reviewed Scope

- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `scripts/utils/reporter/sections/__init__.py`
- `scripts/utils/report_skills/assembly_skills.py`
- `tests/reporter/test_agent_reach_evidence_renderer.py`
- `tests/reporter/test_assembly_skills.py`

## Codex Fix

Claude implemented `AgentReachEvidenceRenderer.required_keys()` as
`["agent_reach_enabled", "agent_reach_quality_status"]`. In this codebase,
`ReportAssemblySkill._render_section()` checks `required_keys()` before calling
`render()`, so default reports with Agent-Reach disabled by omission produced this markdown
comment:

```markdown
<!-- agent_reach_evidence: skipped (missing keys: agent_reach_enabled, agent_reach_quality_status) -->
```

That violated the Phase 3 requirement that default reports stay silent. Codex added a
failing regression assertion and changed `required_keys()` to return `[]`, letting the
renderer handle disabled/missing context by returning an empty string.

## Verification

Commands run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

Results:

- `19 passed`
- `8 passed`

## Boundary Checks

Search confirmed the new evidence renderer is not referenced from:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/content_quality_gate.py`
- `scripts/xueqiu_monitor_v2.py`
- `scripts/run_*.py`

The only expected references to `agent_reach_keep_items` and `agent_reach_demote_items` in
protected areas are the Phase 2 quality skill outputs.

## Notes

- The renderer uses `(title, source_platform, url)` to look up quality metadata.
- Missing quality metadata renders as `—` / `未评分`.
- `keep` is capped at 6 items; `demote` is capped at 4 items.
- `discard` items are not rendered.
- Markdown table pipes are escaped.
- Header data source includes `Agent-Reach外部检索` only for enabled + ok +
  keep/demote non-empty.

## Follow-Up

The next useful step is a sample report run with mocked or real local Agent-Reach output, then
manual review of the evidence section wording and PDF readability. That validation should
still avoid changing LLM synthesis or scoring.
