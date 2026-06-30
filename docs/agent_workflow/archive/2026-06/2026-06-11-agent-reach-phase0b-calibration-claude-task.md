# Claude Code Task: Agent-Reach Phase 0B RSS/Web Calibration

> **Design**: `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-design.md`
> **Review Notes**: `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-claude-notes.md`
> **Notes Output**: `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-implementation-claude-notes.md`
> **Local Runner**: user runs this prompt from the local trusted terminal

You are implementing the locked Phase 0B task. Stay within scope.

## 1. Objective

Calibrate Agent-Reach Phase 0 RSS/Web behavior after runtime validation showed:

- default RSS feeds are broken,
- RSS filter terms are too broad,
- RSS/Web quality scoring is unfairly social-post-oriented,
- Web portal/navigation pages should be detected explicitly by the quality gate.

Do not add new platforms. Do not change report synthesis, scoring engine, renderer behavior, or entry scripts.

## 2. Allowed Changes

You may modify only:

- `scripts/utils/report_skills/agent_reach_query_skill.py`
  - set default RSS feeds to empty,
  - tighten RSS filter-term generation,
  - add optional `agent_reach_rss_filter_terms` override support,
  - keep explicit Web URL behavior unchanged.
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
  - add source-type detection,
  - add source-specific scoring profiles and thresholds,
  - keep social/default scoring behavior unchanged,
  - add Web portal/navigation page detection in the quality layer.
- `tests/reporter/test_agent_reach_skills.py`
  - add/update query generation tests.
- `tests/reporter/test_agent_reach_quality_skill.py`
  - add/update RSS/Web scoring and portal guard tests.
- `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-implementation-claude-notes.md`
  - write implementation notes.

## 3. Do Not Modify

Do not modify:

- `scripts/utils/report_skills/agent_reach_skill.py`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `scripts/xueqiu_monitor_v2.py`
- `scripts/run_*.py`
- Xueqiu, Playwright, Chrome CDP, or browser-related code
- generated reports, PDFs, images, caches, or raw data

If implementation appears to require any forbidden file, stop and write a blocker into the notes file.

## 4. Required Implementation Details

### 4.1 Query Skill

In `agent_reach_query_skill.py`:

1. Set `_DEFAULT_RSS_FEEDS = []`.
2. Remove `_INDUSTRY_KEYWORDS` automatic injection from RSS filter terms.
3. Build default RSS filter terms from identity terms only:
   - `stock_name`
   - stock `code`
   - explicitly supplied `competitors`
   - safe short-name variant if derivable
4. Add optional ctx override:
   - `agent_reach_rss_filter_terms`
   - If provided and non-empty, use those explicit terms instead of auto-generated terms.
5. Do not generate an RSS query if:
   - `rss_feeds` is empty, or
   - filter terms are empty.
6. Preserve Web behavior:
   - Web query is generated only when `agent_reach_urls` or `agent_reach_web_urls` is provided.
   - Web can still be generated when no RSS query exists.

Short-name derivation should be conservative. It may strip common suffixes such as `智能`, `科技`, `股份`, `集团`, but must avoid adding an empty or 1-character term.

### 4.2 Quality Skill

In `agent_reach_quality_skill.py`:

1. Add `_detect_source_type(item)`:
   - `"rss"` if `item.source_platform` contains `rss`,
   - `"web"` if it contains `web`,
   - otherwise `"social"`.
2. Add source-specific profiles:
   - social/default keeps existing behavior and thresholds:
     - keep >= 60
     - demote >= 35
   - rss/web:
     - keep >= 50
     - demote >= 30
     - interaction weight = 0
     - shorter content thresholds suitable for RSS/Web
     - stronger evidence/data pattern bonus is acceptable if tests justify it
3. Preserve output shape from `score_agent_reach_item()`:
   - `score`
   - `action`
   - `reasons`
4. Add Web-only portal/navigation detection in the quality gate:
   - multiple signals should be required,
   - one word such as `链接` should not be enough,
   - obvious portal/navigation pages should be `discard`.
5. Do not change `agent_reach_quality_skill()` ctx output keys.
6. Do not pass Agent-Reach data to synthesis or scoring engine.

## 5. Required Tests

Use TDD: add tests that fail against the current implementation before changing production code.

### Query Tests

Add/update tests proving:

- `generate_agent_reach_queries("黑芝麻智能", "02533")` returns no RSS query when no `agent_reach_rss_feeds` are provided.
- Providing `ctx.agent_reach_rss_feeds` generates an RSS query.
- `generate_agent_reach_queries("澜起科技", "688008", ctx=ctx_with_feeds)` includes `澜起科技` and `688008`, but not standalone `科技`.
- Explicit `agent_reach_rss_filter_terms` override is honored.
- Explicit Web URLs still generate a Web query even when RSS is absent.
- Empty stock/code with no URLs still returns no queries.

### Quality Tests

Add/update tests proving:

- A data-rich `AgentReach(rss)` item with stock/query relevance can reach `keep` with `interaction_score=0`.
- A data-rich `AgentReach(web)` article can reach `keep` with `interaction_score=0` if it is article-like.
- A social/default item that scored below 60 before does not become keep due to RSS/Web calibration.
- A generic unrelated RSS item does not reach keep merely because it contains a broad term.
- A Web portal/navigation page is discard and includes a portal/navigation reason.
- A legitimate Web article containing one `链接` or one source-link phrase is not automatically discarded.
- Existing missing `extra.raw` tolerance still passes.

## 6. Required Verification

Run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_quality_skill.py -q
python3 -m pytest tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

Optional after tests pass:

- Run a tiny local smoke check using explicit `agent_reach_rss_feeds` only if network is available and bounded.
- If live network is flaky, skip and record the reason. Do not retry repeatedly.

Do not run broad full `pytest` unless you can complete it quickly with a timeout.

## 7. Stop Conditions

Stop and write a blocker if:

- Any forbidden file must be modified.
- A change would alter default pipeline skill count or existing entry scripts.
- A change would feed Agent-Reach data into `KnowledgeSynthesizer`, report scoring, or LLM prompt context.
- Tests require real network access.
- Xueqiu/Chrome/CDP/account-based access appears necessary.

## 8. Required Notes Format

Write `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-implementation-claude-notes.md`:

```markdown
# Claude Notes: Agent-Reach Phase 0B RSS/Web Calibration

## Summary

- 

## Files Changed

- 

## Tests Added Or Updated

- 

## Tests Run

| Command | Result | Notes |
| --- | --- | --- |

## Local Command Used

```bash

```

## Deviations From Task

- None.

## Blockers Or Follow-Ups

- None.
```
