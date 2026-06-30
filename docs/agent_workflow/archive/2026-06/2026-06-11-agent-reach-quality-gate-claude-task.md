# Claude Code Task: Agent-Reach Quality Gate Phase 2

> **Design**: `docs/agent_workflow/2026-06-11-agent-reach-quality-gate-design.md`
> **Notes Output**: `docs/agent_workflow/2026-06-11-agent-reach-quality-gate-claude-notes.md`
> **Local Runner**: user runs this prompt from their local trusted terminal

You are implementing the locked Phase 2 task from the design. Stay within scope.

---

## 1. Objective

Implement a dedicated deterministic quality gate for Agent-Reach `SynthesisItem` records:

- score Agent-Reach items with transparent rules,
- split items into keep/demote/discard buckets,
- write compact audit metadata to `ctx`,
- insert the skill only when `enable_agent_reach=True`,
- keep Agent-Reach data out of synthesis, report renderers, scoring, and investment conclusions.

---

## 2. Allowed Changes

You may modify or add only:

- `scripts/utils/report_skills/agent_reach_quality_skill.py` — new deterministic quality scorer and skill.
- `scripts/utils/report_skills/__init__.py` — import and insert quality skill only in enabled Agent-Reach pipeline.
- `tests/reporter/test_agent_reach_quality_skill.py` — focused tests for scoring/status/output contract.
- `tests/reporter/test_pipeline_integration.py` — update enabled pipeline skill count and quality skill position.
- `docs/agent_workflow/2026-06-11-agent-reach-quality-gate-claude-notes.md` — implementation notes.

---

## 3. Do Not Modify

Do not modify:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/technical_analyzer.py`
- any technical-analysis module
- `scripts/utils/content_quality_gate.py`
- entry points: `scripts/xueqiu_monitor_v2.py`, `scripts/run_*.py`, `scripts/run_technical_analysis.py`
- `data/raw`, `reports`, `knowledge`, or generated cache/report files
- Xueqiu fetchers, Playwright, Chrome, or CDP code

Do not run real Agent-Reach searches. Use mocks/constructed `SynthesisItem` objects only.

---

## 4. Required Design Decisions

Implement these decisions exactly:

1. Default `build_stock_report_pipeline()` remains 11 skills.
2. `build_stock_report_pipeline(enable_agent_reach=True)` becomes 14 skills.
3. Insert `agent_reach_quality_skill` after `agent_reach_fetch_skill` and before `cross_source_consolidation_skill`.
4. All Phase 2 output stays on `ctx`; do not mutate `agent_reach_items`, `stock_raw`, `raw_data`, or caller input dictionaries.
5. Do not pass Agent-Reach items into `SynthesisSkill`, `adapt_all()` from synthesis, `KnowledgeSynthesizer`, renderers, or scoring.
6. Do not call LLMs, external websites, browsers, real CLI searches, or subprocesses in the quality skill.
7. The quality scorer is deterministic and pure.

---

## 5. Implementation Guidance

Create `scripts/utils/report_skills/agent_reach_quality_skill.py`.

Expose:

```python
def score_agent_reach_item(item, stock_name: str = "", search_queries: list[dict] = None) -> dict:
    ...
```

The return dict should include:

- `score`
- `action`: `"keep" | "demote" | "discard"`
- `reasons`

Suggested constants:

- keep: score >= 60
- demote: 35 <= score < 60
- discard: score < 35

Use a transparent 0-100 scoring split:

- relevance: 0-25
- source credibility: 0-25
- evidence/detail density: 0-20
- substance/length: 0-20
- engagement: 0-10

The scorer may inspect:

- `item.title`
- `item.content`
- `item.source_platform`
- `item.interaction_score`
- `item.extra.get("raw", {})`
- `stock_name`
- terms from `search_queries`

Use `.get()` for all nested raw metadata. Do not assume keys exist.

### Quality Skill Outputs

`agent_reach_quality_skill(ctx)` must write:

- `agent_reach_keep_items`
- `agent_reach_demote_items`
- `agent_reach_discard_items`
- `agent_reach_quality_results`
- `agent_reach_quality_status`
- `agent_reach_quality_summary`

`agent_reach_quality_results` must be compact metadata only. Include:

- title
- source
- action
- score
- reasons
- url
- fetch_status
- quality_status

Do not duplicate full content in `agent_reach_quality_results`.

### Status Rules

- If Agent-Reach is disabled or no fetch status exists: `agent_reach_quality_status = "disabled"`.
- If fetch status is `missing_binary`, `error`, or `timeout` with zero items: `agent_reach_quality_status = "skipped"` and lists empty.
- If fetch status is `timeout` but partial items exist: score those items and set `agent_reach_quality_status = "ok"`.
- If `agent_reach_items` is empty: `agent_reach_quality_status = "empty"`.
- If items are scored: `agent_reach_quality_status = "ok"`.

### Summary Shape

`agent_reach_quality_summary` should be a small dict:

```python
{
    "keep": 0,
    "demote": 0,
    "discard": 0,
    "total": 0,
    "fetch_status": "...",
    "quality_status": "...",
}
```

---

## 6. Required Tests

Add/update focused tests covering:

1. Official, relevant, evidence-rich item scores `keep`.
2. Short but somewhat relevant item scores `demote`.
3. Off-topic or spam/pumping item scores `discard`.
4. Scorer accepts `search_queries` and uses query terms deterministically.
5. Scorer tolerates missing `item.extra["raw"]` and missing raw metadata keys.
6. Disabled/no fetch status writes empty lists and `agent_reach_quality_status == "disabled"`.
7. `missing_binary`, `error`, or `timeout` with no items writes `agent_reach_quality_status == "skipped"`.
8. `timeout` with partial items scores those items and writes `agent_reach_quality_status == "ok"`, with `fetch_status == "timeout"` in results/summary.
9. `empty` fetch status with empty items writes `agent_reach_quality_status == "empty"`.
10. Quality results do not include full content.
11. Default pipeline still has 11 skills.
12. Enabled pipeline has 14 skills and ordering:

```text
quality_gate_skill
agent_reach_query_skill
agent_reach_fetch_skill
agent_reach_quality_skill
cross_source_consolidation_skill
```

13. `SynthesisSkill` behavior remains unchanged and does not consume `agent_reach_keep_items`.

---

## 7. Required Verification

Run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_skills.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py -q
python3 -m pytest tests/reporter/test_synthesis_skills.py -q
```

Do not run real Agent-Reach searches.

---

## 8. Stop Conditions

Stop and write the blocker into the notes file if:

- You need to modify files outside the allowed list.
- You need to modify `SynthesisSkill`, `KnowledgeSynthesizer`, scoring, report renderers, technical analysis, `ContentQualityGate`, or entry scripts.
- Real Agent-Reach CLI behavior is required to proceed.
- Tests require network, browser, Chrome/CDP, or Xueqiu detail fetching.
- The design contradicts current code.

---

## 9. Required Notes Format

Write `docs/agent_workflow/2026-06-11-agent-reach-quality-gate-claude-notes.md` with:

```markdown
# Claude Notes: Agent-Reach Quality Gate Phase 2

## Summary

- 

## Files Changed

- 

## Tests Run

| Command | Result | Notes |
|---------|--------|-------|
|  |  |  |

## Local Command Used

```bash

```

## Deviations From Task

- None.

## Blockers Or Follow-Ups

- None.
```
