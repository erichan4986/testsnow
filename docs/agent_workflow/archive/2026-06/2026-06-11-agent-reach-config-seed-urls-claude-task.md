# Agent-Reach Config Seed URLs — Claude Task

You are Claude Code working in `/Users/erichan/testsnow`.

## Context

Agent-Reach Phase 0B now supports explicit Web URLs through:

- `agent_reach_urls` / `agent_reach_web_urls` in `SkillContext`
- `WebConnector`
- source-aware quality gate
- `AgentReachEvidenceRenderer`

The official Black Sesame URL smoke test now works:

`https://www.blacksesame.com/zh/list_10/972.html`

Current problem: this only works in manual smoke tests. Normal report generation does not pass per-stock Agent-Reach seed URLs into the pipeline, and `PerStockReporter.generate_stock_report()` still builds the default 11-skill pipeline.

## Goal

Make Agent-Reach explicit URL evidence usable from normal report generation, behind explicit opt-in config, without changing default behavior.

## Desired Behavior

1. Default behavior remains unchanged:
   - `build_stock_report_pipeline()` default still returns 11 skills.
   - `PerStockReporter(...)` without Agent-Reach options does not include Agent-Reach skills.
   - No network/subprocess calls happen by default.

2. When a stock has explicit Agent-Reach config enabled:
   - `PerStockReporter.generate_stock_report(stock_name, ...)` builds the optional Agent-Reach pipeline.
   - Initial pipeline input includes:
     - `enable_agent_reach: True`
     - `agent_reach_urls` or `agent_reach_web_urls`
     - optional `agent_reach_rss_feeds`
     - optional `agent_reach_rss_filter_terms`

3. Add one known-good seed URL for 黑芝麻智能:

```json
"agent_reach": {
  "enabled": true,
  "web_urls": [
    "https://www.blacksesame.com/zh/list_10/972.html"
  ]
}
```

Use `web_urls` in config, but map it to existing `agent_reach_urls` or `agent_reach_web_urls` ctx keys.

## Scope

Prefer narrow changes:

- `scripts/utils/stock_reporter.py`
- `scripts/xueqiu_monitor_v2.py` only if needed to pass stock config into `PerStockReporter`
- `config/stocks.json`
- focused tests under `tests/reporter/`

Do not modify:

- `KnowledgeSynthesizer`
- `SynthesisSkill`
- `source_adapter.py`
- `agent_reach_skill.py`
- `agent_reach_quality_skill.py`
- `agent_reach_evidence_renderer.py`
- scoring engine
- technical analysis modules
- Xueqiu/CDP/Playwright code

## Implementation Guidance

### 1. Add optional reporter config plumbing

Extend `PerStockReporter.__init__` conservatively, for example:

```python
def __init__(
    self,
    stocks_data=None,
    data_path=None,
    stock_codes=None,
    raw_data=None,
    agent_reach_configs=None,
    enable_agent_reach=False,
):
    ...
    self.agent_reach_configs = agent_reach_configs or {}
    self.enable_agent_reach = enable_agent_reach
```

Keep existing call sites valid.

### 2. Map per-stock config to pipeline input

Inside `generate_stock_report()`:

- Look up `ar_cfg = self.agent_reach_configs.get(stock_name, {})`.
- Enable Agent-Reach if `self.enable_agent_reach` is true or `ar_cfg.get("enabled") is True`.
- Build pipeline with `build_stock_report_pipeline(enable_agent_reach=agent_reach_enabled)`.
- Add ctx input keys only when present:
  - `enable_agent_reach`
  - `agent_reach_urls` from `ar_cfg.get("web_urls", [])` or `ar_cfg.get("urls", [])`
  - `agent_reach_rss_feeds` from `ar_cfg.get("rss_feeds", [])`
  - `agent_reach_rss_filter_terms` from `ar_cfg.get("rss_filter_terms", [])`

Do not pass empty lists unnecessarily unless existing tests prefer that.

### 3. Pass config from main monitor

In `scripts/xueqiu_monitor_v2.py`, when creating `PerStockReporter`, derive:

```python
agent_reach_configs = {
    s["name"]: s.get("agent_reach", {})
    for s in stocks
    if s.get("agent_reach")
}
```

Pass it into `PerStockReporter`.

Do not add new CLI flags in this task.

### 4. Update `config/stocks.json`

Add the `agent_reach` block only to 黑芝麻智能 with the official URL above.

## Tests

Add focused tests. Suggested file:

`tests/reporter/test_stock_reporter_agent_reach_config.py`

Use mocks so tests do not perform network/API calls.

Test cases:

1. Default reporter does not enable Agent-Reach:
   - mock `build_stock_report_pipeline`
   - call `generate_stock_report()`
   - assert `build_stock_report_pipeline()` called with no Agent-Reach enabled, or with `enable_agent_reach=False`
   - assert pipeline input does not contain `agent_reach_urls`

2. Per-stock config enables Agent-Reach and passes URL:
   - `agent_reach_configs={"黑芝麻智能": {"enabled": True, "web_urls": ["https://example.com/article"]}}`
   - assert `build_stock_report_pipeline(enable_agent_reach=True)`
   - assert pipeline input contains `enable_agent_reach=True`
   - assert pipeline input contains `agent_reach_urls=["https://example.com/article"]`

3. Disabled per-stock config does not enable Agent-Reach:
   - `{"enabled": False, "web_urls": ["https://example.com/article"]}`
   - assert optional pipeline is not enabled
   - assert URLs are not passed

4. RSS config mapping if present:
   - config includes `rss_feeds` and `rss_filter_terms`
   - assert those keys appear in initial pipeline input only when enabled

Existing integration tests must keep passing:

```bash
python3 -m pytest tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_pipeline_integration.py tests/reporter/test_agent_reach_skills.py -q
```

Also run the focused Agent-Reach suite:

```bash
python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_evidence_renderer.py -q
```

## Optional Runtime Smoke

If local network/Jina access works, run a single 黑芝麻智能 report generation with Agent-Reach enabled and confirm:

- Agent-Reach section is present.
- The official URL appears or its evidence row appears.
- No Xueqiu detail-page automation, Chrome/CDP, Playwright, or login-dependent fetch is used for this validation.

If runtime report generation is too slow or blocked, document that and rely on focused tests.

## Notes Output

Write implementation notes to:

`docs/agent_workflow/2026-06-11-agent-reach-config-seed-urls-claude-notes.md`

Include:

- Files changed
- Tests run and results
- Whether runtime smoke was run
- Any deviations or blockers
