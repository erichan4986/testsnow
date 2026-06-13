# Agent-Reach Phase 0 Connector Refactor — Implementation Notes

Date: 2026-06-11

## Files Changed

- `scripts/utils/report_skills/agent_reach_skill.py` — rewritten (connector registry, RSSConnector, WebConnector)
- `scripts/utils/report_skills/agent_reach_query_skill.py` — rewritten (Phase 0 RSS + conditional Web queries)
- `tests/reporter/test_agent_reach_skills.py` — rewritten (52 tests, no `_run_command` patches)
- `tests/reporter/test_agent_reach_connector.py` — new (connector-level focused tests)
- `tests/reporter/test_pipeline_integration.py` — updated (replaced `_run_command` patch with `RSSConnector.run` patch)

## Tests Run and Results

```bash
$ python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py -q
52 passed in 1.21s

$ python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_evidence_renderer.py -q
39 passed in 1.10s

$ python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
8 passed in 27.92s

# Combined run
$ python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
99 passed in 27.18s
```

## `_AGENT_REACH_COMMANDS` and Fake `agent-reach search` Paths

**Fully removed.**

- `_AGENT_REACH_COMMANDS` dict deleted.
- `_run_command()` helper deleted.
- `_parse_records()` deleted (no longer needed; connectors produce dicts directly).
- All fake `agent-reach search <platform>` invocation paths eliminated.

## Registered Connectors

**Default registry (`CONNECTOR_REGISTRY`):**
- `rss` → `RSSConnector()`
- `web` → `WebConnector()`

**Detection-only (not registered by default):**
- `youtube` → `YouTubeConnector()`
- `exa_search` → `ExaSearchConnector()`
- `wechat` → `WechatConnector()`

**Explicitly unsupported:**
- `twitter`, `xueqiu`, `xiaohongshu`, `douyin`, `linkedin`, `reddit`, `bilibili`, `v2ex`

## Deviations from Design

1. **RSS default feeds:** The design suggested a "tiny, conservative default list." The constants module uses 3 mainstream Chinese finance RSS feeds. All are overridable via `ctx.agent_reach_rss_feeds`.

2. **Industry keyword heuristic:** `_build_rss_filter_terms()` adds industry keywords only if they appear in `stock_name` (to avoid over-broad filtering for unrelated stocks). This is slightly stricter than the design's "include conservative industry keywords if available."

3. **`_parse_records` removed:** The design did not explicitly require keeping `_parse_records`. Since connectors now produce structured dicts directly, JSON parsing is no longer needed at the skill layer.

4. **Test file split:** Created `test_agent_reach_connector.py` for low-level connector tests and kept `test_agent_reach_skills.py` for skill-level integration tests. This is cleaner than a single monolithic test file.

## Forbidden Files Not Modified

Confirmed no changes to:
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- Entry scripts (`scripts/xueqiu_monitor_v2.py`, `scripts/run_*.py`)
- Xueqiu / Playwright / CDP fetchers

## Blockers

None. All 99 targeted tests pass.
