# Agent-Reach Config Seed URLs — Codex Review

## Verdict

Accepted for Agent-Reach scope.

The implementation wires explicit per-stock Agent-Reach seed URLs from config into normal report generation while preserving the default `PerStockReporter` behavior when no Agent-Reach config is supplied.

## Files Reviewed

- `config/stocks.json`
- `scripts/utils/stock_reporter.py`
- `scripts/xueqiu_monitor_v2.py`
- `tests/reporter/test_stock_reporter_agent_reach_config.py`
- `docs/agent_workflow/2026-06-11-agent-reach-config-seed-urls-claude-notes.md`

## Requirement Check

- `PerStockReporter(...)` without Agent-Reach options still builds `build_stock_report_pipeline(enable_agent_reach=False)`.
- Per-stock `agent_reach.enabled=true` builds the optional Agent-Reach pipeline and passes `agent_reach_urls`.
- `web_urls` and `urls` aliases are supported.
- RSS feed/filter config is passed only when Agent-Reach is enabled.
- `config/stocks.json` adds the verified Black Sesame official URL only under explicit `agent_reach.enabled=true`.
- No changes were made to `KnowledgeSynthesizer`, `SynthesisSkill`, Agent-Reach connector/quality/renderer internals, scoring engine, technical analysis, Xueqiu/CDP, or Playwright code.

## Verification Run By Codex

Fresh focused tests:

```bash
python3 -m pytest tests/reporter/test_stock_reporter_agent_reach_config.py tests/reporter/test_pipeline_integration.py tests/reporter/test_agent_reach_skills.py -q
```

Result:

```text
43 passed in 18.77s
```

Fresh Agent-Reach regression tests:

```bash
python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_evidence_renderer.py -q
```

Result:

```text
77 passed in 2.41s
```

Full-suite status reported by Claude:

```text
412 passed, 6 skipped, 1 pre-existing failure
```

Codex reproduced the remaining failure:

```bash
python3 -m pytest tests/reporter/test_lexin_phase3_report.py::test_negative_bias_advisor_no_chasing -q
```

Result:

```text
FAILED tests/reporter/test_lexin_phase3_report.py::test_negative_bias_advisor_no_chasing
AssertionError: assert '负偏离' in '正常'
```

That failure is in `scripts/utils/reporter/technical_analyzer.py::_build_advisors()` and is outside the Agent-Reach config path.

## Important Boundary Note

`PerStockReporter` still defaults to no Agent-Reach. However, `scripts/xueqiu_monitor_v2.py` now passes `agent_reach_configs` from `config/stocks.json`, and 黑芝麻智能 has `agent_reach.enabled=true`. Therefore, the normal main monitor run will attempt Agent-Reach Web/Jina for 黑芝麻智能 by configuration. This is intentional explicit opt-in, but it means "no network by default" only remains true for reporter instances without config, not for the repo's current configured Black Sesame run.

## Follow-Up

The remaining technical analyzer failure should be handled as a separate task if desired:

- File: `scripts/utils/reporter/technical_analyzer.py`
- Test: `tests/reporter/test_lexin_phase3_report.py::test_negative_bias_advisor_no_chasing`
- Symptom: `bias_5=-2.5` returns state `正常` instead of a state containing `负偏离`.
