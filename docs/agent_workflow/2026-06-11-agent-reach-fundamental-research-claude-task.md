# Claude Code Task: Agent-Reach Fundamental Research Phase 1

> **Design**: `docs/agent_workflow/2026-06-11-agent-reach-fundamental-research-design.md`
> **Notes Output**: `docs/agent_workflow/2026-06-11-agent-reach-fundamental-research-claude-notes.md`
> **Local Runner**: user runs this prompt from their local trusted terminal

You are implementing the locked Phase 1 task from the design. Stay within scope.

---

## 1. Objective

Implement the optional Agent-Reach Phase 1 data-ingestion skeleton:

- deterministic query generation,
- optional CLI fetching with safe subprocess handling,
- Agent-Reach platform adapters to `SynthesisItem`,
- optional pipeline integration behind `enable_agent_reach`,
- focused tests proving disabled/default behavior, enabled mocked behavior, timeout/failure behavior, dedupe, and malformed adapter records.

This phase must not change report conclusions, scoring, synthesis prompts, or report renderers.

---

## 2. Allowed Changes

You may modify or add only:

- `scripts/utils/report_skills/agent_reach_query_skill.py` — new deterministic query skill and pure query helper.
- `scripts/utils/report_skills/agent_reach_skill.py` — new optional CLI fetch skill, parser, dedupe/status handling.
- `scripts/utils/source_adapter.py` — add Agent-Reach platform adapters and optional `agent_reach_items` support in `adapt_all()`.
- `scripts/utils/report_skills/__init__.py` — add `enable_agent_reach: bool = False` builder flag and insert optional skills after `quality_gate_skill` only when enabled.
- `tests/reporter/test_agent_reach_skills.py` — focused unit tests for new skills.
- `tests/utils/test_source_adapter.py` — adapter tests for Agent-Reach records and malformed/missing fields.
- `tests/reporter/test_pipeline_integration.py` or a focused equivalent — verify default 11-skill pipeline and enabled Agent-Reach pipeline.
- `docs/agent_workflow/2026-06-11-agent-reach-fundamental-research-claude-notes.md` — append implementation notes.

---

## 3. Do Not Modify

Do not modify:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/technical_analyzer.py`
- any technical-analysis module
- entry points: `scripts/xueqiu_monitor_v2.py`, `scripts/run_*.py`, `scripts/run_technical_analysis.py`
- `data/raw`, `reports`, `knowledge`, or generated cache/report files
- Xueqiu fetchers, Playwright, Chrome, or CDP code

Do not run real Agent-Reach searches. Use mocks only.

---

## 4. Required Design Decisions

Implement these decisions exactly:

1. `build_stock_report_pipeline()` without arguments must keep the existing 11-skill default pipeline.
2. Add `build_stock_report_pipeline(llm_client=None, enable_agent_reach: bool = False)`.
3. When `enable_agent_reach=True`, insert the Agent-Reach query/fetch skills after `quality_gate_skill` and before `cross_source_consolidation_skill`.
4. Agent-Reach disabled/default mode must not run subprocess, network, browser, or LLM calls.
5. Agent-Reach output must be stored only on `ctx`:
   - `agent_reach_enabled`
   - `agent_reach_status`
   - `agent_reach_warnings`
   - `search_queries`
   - `agent_reach_items`
6. Do not mutate `stock_raw`, `raw_data`, or caller input dictionaries.
7. Do not pass `agent_reach_items` to `adapt_all()` from `SynthesisSkill`.
8. Do not modify `SynthesisSkill._build_synthesis_items()`.
9. Status values:
   - `"disabled"`: feature off.
   - `"missing_binary"`: enabled but CLI binary unavailable.
   - `"timeout"`: per-command or per-stock deadline hit.
   - `"error"`: non-zero command, parse failure, or unexpected safe failure.
   - `"ok"`: enabled and items collected.
   - `"empty"`: enabled and commands succeeded but no usable items.

---

## 5. Implementation Guidance

### Query Skill

Create `scripts/utils/report_skills/agent_reach_query_skill.py`.

Expose:

```python
def generate_agent_reach_queries(stock_name: str, code: str = "", competitors: list[str] = None) -> list[dict]:
    ...
```

Each query dict should include:

- `query`
- `target_platforms`
- `rationale`

Keep it deterministic and free of env/LLM/subprocess calls.

The skill should populate `search_queries` when enabled and set sane disabled defaults when not enabled.

### Fetch Skill

Create `scripts/utils/report_skills/agent_reach_skill.py`.

Use list-argument subprocess calls only. Do not use shell strings.

The implementation should be mock-friendly:

- Accept injectable command runner or isolate `_run_command()` so tests can patch it.
- Parse JSON lines and JSON arrays.
- Deduplicate by canonical URL; if URL is absent, dedupe by `(platform, title, publish_time)`.
- Enforce:
  - per-command timeout: 30 seconds,
  - per-stock budget: 60 seconds,
  - per-query/platform cap: 10 items,
  - total cap: 100 items.
- If binaries are unavailable, set `agent_reach_status = "missing_binary"` and return without raising.

Because actual installed CLI names are not confirmed, keep the platform command mapping small/configurable and fully mocked in tests. It is acceptable if real CLI support is skeletal in phase 1 as long as the safe interface and tests are in place.

### Source Adapter

Add Agent-Reach adapters for likely platform records. Normalize to `SynthesisItem` while preserving raw data in `extra`.

Required behavior:

- Missing string fields default to `""`.
- Missing interaction fields default to `0`.
- Missing URL and publish time must not raise.
- Empty content should either use title/summary text or return an item with empty content, as long as no field is fabricated.

Add `agent_reach_items: List[Dict] = None` to `adapt_all()`, but do not call it from synthesis in phase 1.

---

## 6. Required Tests

Add/update focused tests covering:

1. `generate_agent_reach_queries()` returns deterministic project/product/competitor queries.
2. Default pipeline still has 11 skills:

```python
pipeline = build_stock_report_pipeline()
assert len(pipeline.skills) == 11
```

3. Enabled pipeline has the two additional Agent-Reach skills in the correct position after `quality_gate_skill`.
4. Disabled Agent-Reach behavior:
   - `agent_reach_items == []`
   - `agent_reach_status == "disabled"`
   - no subprocess/runner called.
5. Enabled mocked CLI returns normalized `SynthesisItem` objects and `agent_reach_status == "ok"`.
6. Missing binary sets `agent_reach_status == "missing_binary"` and does not raise.
7. Timeout/deadline sets `agent_reach_status == "timeout"` and returns partial results if any.
8. Duplicate URL records dedupe to one item.
9. `adapt_all(agent_reach_items=[...])` handles missing URL, missing publish time, missing interaction score, unknown author, and empty content without raising.
10. Existing synthesis behavior does not include Agent-Reach items in phase 1. This can be a focused assertion that `SynthesisSkill._build_synthesis_items()` remains unchanged by behavior, not by brittle source text.

---

## 7. Required Verification

Run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/utils/test_source_adapter.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py -q
```

If feasible, also run:

```bash
python3 -m pytest tests/reporter/test_synthesis_skills.py -q
```

Do not run real Agent-Reach searches.

---

## 8. Stop Conditions

Stop and write the blocker into the notes file if:

- You need to modify files outside the allowed list.
- You need to modify `SynthesisSkill`, `KnowledgeSynthesizer`, scoring, report renderers, technical analysis, or entry scripts.
- Real Agent-Reach CLI behavior is required to proceed.
- Tests require network, browser, Chrome/CDP, or Xueqiu detail fetching.
- The design contradicts current code.

---

## 9. Required Notes Format

Append to `docs/agent_workflow/2026-06-11-agent-reach-fundamental-research-claude-notes.md`:

```markdown
## Implementation Notes

### Summary

- 

### Files Changed

- 

### Tests Run

| Command | Result | Notes |
|---------|--------|-------|
|  |  |  |

### Local Command Used

```bash

```

### Deviations From Task

- None.

### Blockers Or Follow-Ups

- None.
```
