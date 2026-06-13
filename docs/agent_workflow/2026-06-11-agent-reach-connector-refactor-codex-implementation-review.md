# Agent-Reach Connector Refactor - Codex Implementation Review

Date: 2026-06-11

## Scope Reviewed

Reviewed Claude Code implementation against:

- `docs/agent_workflow/2026-06-11-agent-reach-connector-refactor-design.md`
- `docs/agent_workflow/2026-06-11-agent-reach-connector-refactor-claude-task.md`
- `docs/agent_workflow/2026-06-11-agent-reach-connector-refactor-claude-notes.md`

Files inspected:

- `scripts/utils/report_skills/agent_reach_skill.py`
- `scripts/utils/report_skills/agent_reach_query_skill.py`
- `tests/reporter/test_agent_reach_skills.py`
- `tests/reporter/test_agent_reach_connector.py`
- `tests/reporter/test_pipeline_integration.py`

## Findings

### Accepted

- The fake `agent-reach search ...` command layer was removed.
- `agent_reach_fetch_skill()` now routes through a connector registry.
- Default registry contains only `rss` and `web`.
- Detection-only connectors exist for `youtube`, `exa_search`, and `wechat`, but are not default targets.
- Unsupported platforms such as Twitter/X, Xueqiu, Xiaohongshu, Douyin, LinkedIn, Reddit, Bilibili, and V2EX are skipped with warnings.
- Downstream context keys remain compatible: `agent_reach_status`, `agent_reach_items`, `agent_reach_warnings`.
- Existing quality gate and renderer contracts remain unchanged.

### Codex Fix Applied

One edge case was missing from Claude's tests:

- When `stock_name` and `code` were both empty, `_build_rss_filter_terms()` returned `[""]`.
- RSS matching with an empty string would match every RSS entry, effectively turning the conservative RSS connector into an unfiltered feed poll.

Fix:

- Empty RSS filter terms are now removed.
- RSS query generation is skipped when there are no valid filter terms.
- Explicit Web URL reads still work even when no RSS filter terms exist.

Regression tests added:

- `test_generate_agent_reach_queries_skips_rss_without_filter_terms`
- `test_generate_agent_reach_queries_allows_web_without_filter_terms`

## Verification

Commands run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py -q
python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

Results:

- Agent-Reach connector + skill tests: 54 passed
- Agent-Reach quality + renderer tests: 39 passed
- Pipeline + synthesis regression tests: 8 passed

Total focused verification: 101 passed.

## Residual Risks

- `RSSConnector` relies on `feedparser.parse()` and currently treats malformed feeds with no entries as empty unless an exception is raised. This is acceptable for Phase 0 but should be revisited if RSS becomes a primary evidence source.
- Unknown-only or unsupported-only platform requests currently end as `missing_binary`/empty-style no-result states plus warnings. This is tolerable because default queries never target those platforms.
- RSS matching is still conservative and may miss relevant industry articles that do not mention the stock name, code, competitor, or configured keyword. This is safer than over-collection for Phase 0.

## Recommendation

Proceed with this refactor. The implementation is now aligned with Agent-Reach's actual scaffolding model and preserves the downstream report pipeline contracts.
