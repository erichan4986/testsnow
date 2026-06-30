# Agent-Reach Phase 3B Themed Evidence Codex Review

Date: 2026-06-11

## Status

Accepted after Codex validation and one small ordering fix.

Phase 3B upgrades the existing `AgentReachEvidenceRenderer` from raw keep/demote tables to
a themed evidence-review section. It remains display-only: no LLM synthesis, no scoring
impact, and no pipeline contract change.

## Reviewed Scope

- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `tests/reporter/test_agent_reach_evidence_renderer.py`
- `docs/agent_workflow/2026-06-11-agent-reach-themed-evidence-claude-notes.md`

No Phase 3B changes were needed in:

- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/utils/reporter/sections/__init__.py`
- `tests/reporter/test_assembly_skills.py`

Those files still show as modified in the working tree from earlier phases, but Phase 3B
did not require additional edits there.

## Codex Fix

Claude's implementation rendered overview `主要主题` in the order keep items appeared in
the input. That could make the summary unstable, for example showing `客户/定点/订单` before
`产品/量产进展` when item order changed.

Codex added a failing test and changed the overview topic list to iterate the fixed topic
order from `_TOPIC_LABELS`.

Codex also added a direct long-excerpt truncation regression test, because the Phase 3B task
required truncation behavior to remain locked.

## Verification

Commands run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_assembly_skills.py tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

Results:

- `26 passed`
- `15 passed`

## Boundary Checks

Search confirmed the Phase 3B renderer/classifier is not referenced from:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/xueqiu_monitor_v2.py`
- `scripts/run_*.py`

The only expected Agent-Reach keep/demote references in protected areas are the Phase 2
quality skill outputs.

## Resulting Behavior

- `classify_agent_reach_topic()` classifies items into six deterministic topics.
- First matching topic wins, so `量产` + `营收` classifies as `product_progress`.
- `quality_result["reasons"]` participates in classification.
- Overview includes only keep-item topics and now follows fixed topic order.
- Keep items render under themed evidence subsections.
- Demote items render only under `待人工复核线索`.
- Discard items remain hidden.
- Markdown escaping, URL handling, missing-quality fallback, caps, disabled/skipped/error
  silence, and empty-state note are preserved.

## Follow-Up

The next useful validation is generating a sample report with mocked or real local
Agent-Reach keep/demote items and reviewing the Markdown/PDF readability. If the evidence
quality looks useful, the later LLM phase should still be designed separately with
anti-fabrication and citation requirements.
