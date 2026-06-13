# Agent-Reach Config Seed URLs — Implementation Notes

## Status

Accepted

## Files Changed

1. `scripts/utils/stock_reporter.py`
   - `PerStockReporter.__init__` now accepts optional `agent_reach_configs` and `enable_agent_reach`.
   - `generate_stock_report()` looks up per-stock `agent_reach` config.
   - Enables Agent-Reach when `self.enable_agent_reach` is True OR per-stock `enabled` is True.
   - Passes `enable_agent_reach`, `agent_reach_urls` (with `urls` alias), `agent_reach_rss_feeds`, `agent_reach_rss_filter_terms` into pipeline input only when present.
   - Default behavior unchanged: 11-skill pipeline, no Agent-Reach.

2. `scripts/xueqiu_monitor_v2.py`
   - Derives `agent_reach_configs` from `stocks.json` entries that have `agent_reach` field.
   - Passes configs to `PerStockReporter` constructor.

3. `config/stocks.json`
   - Added `agent_reach` block to 黑芝麻智能 with the verified official URL.

4. `tests/reporter/test_stock_reporter_agent_reach_config.py` (new)
   - `test_default_reporter_does_not_enable_agent_reach` — default reporter calls `build_stock_report_pipeline(enable_agent_reach=False)`, no AR keys in input.
   - `test_per_stock_config_enables_agent_reach_and_passes_url` — per-stock `enabled=True` calls `enable_agent_reach=True` and passes `agent_reach_urls`.
   - `test_disabled_per_stock_config_does_not_enable_agent_reach` — `enabled=False` ignores URLs, calls `enable_agent_reach=False`.
   - `test_global_enable_overrides_per_stock` — `enable_agent_reach=True` in reporter constructor enables for all stocks.
   - `test_rss_config_mapping_when_enabled` — `rss_feeds` and `rss_filter_terms` mapped correctly.
   - `test_urls_alias_backward_compatible` — config key `urls` maps to `agent_reach_urls`.

## Tests Run

| Command | Result |
| --- | --- |
| `pytest tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_pipeline_integration.py tests/reporter/test_agent_reach_skills.py -q` | **43 passed** |
| `pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_evidence_renderer.py -q` | **77 passed** |
| `pytest tests/reporter/ -q` (full suite) | **412 passed, 6 skipped, 1 pre-existing failure** |

The single failure (`test_lexin_phase3_report.py::test_negative_bias_advisor_no_chasing`) is a pre-existing technical analyzer issue unrelated to Agent-Reach changes. All Agent-Reach and stock reporter tests pass.

## Runtime Smoke

Not run. Full report generation requires LLM client, chart rendering (Kaleido/Plotly), and quote fetching — dependencies that are not practical to exercise in this test context. Focused unit + integration tests provide sufficient coverage of the config plumbing.

## Deviations From Task

None.

## Assessment

- Default pipeline remains 11 skills with no network calls.
- Only stocks with explicit `agent_reach.enabled=true` in `config/stocks.json` trigger the 14-skill pipeline.
- No domain whitelists, no global relaxation of portal detection.
- Existing call sites remain valid (backward-compatible constructor).
