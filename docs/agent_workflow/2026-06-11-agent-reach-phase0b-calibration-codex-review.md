# Agent-Reach Phase 0B Calibration - Codex Review

Date: 2026-06-11

## Scope Reviewed

Reviewed Claude Code implementation notes:

- `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-implementation-claude-notes.md`

Reviewed implementation files:

- `scripts/utils/report_skills/agent_reach_query_skill.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `tests/reporter/test_agent_reach_skills.py`
- `tests/reporter/test_agent_reach_quality_skill.py`

The implementation stayed within the allowed Phase 0B files for this review scope.

## Accepted Changes

- `_DEFAULT_RSS_FEEDS` is now empty.
- RSS query generation requires both explicit RSS feeds and non-empty filter terms.
- Broad `_INDUSTRY_KEYWORDS` injection was removed.
- RSS filter terms are identity-oriented: stock name, code, competitors, and conservative short-name variants.
- Optional `agent_reach_rss_filter_terms` override is supported.
- Web query generation still works independently when explicit URLs are provided.
- Quality scoring now detects source type: `rss`, `web`, or `social`.
- Social/default thresholds remain unchanged at keep 60 / demote 35.
- RSS/Web thresholds are source-specific at keep 50 / demote 30.
- RSS/Web interaction scoring is ignored rather than treated as a missing social signal.
- Web portal/navigation detection was added in the quality gate, not in the connector.

## Codex Fix Applied

During review, Codex found one gap:

- A Web page that is both portal-like and full of repeated stock/data terms could still score `keep`.
- Root cause: portal detection applied only a soft `-15` penalty, which could be outweighed by relevance, evidence, URL, and content-length bonuses.

Fix:

- Added `test_data_rich_web_portal_page_still_discarded`.
- Changed portal handling so a detected Web portal page is capped below the demote threshold, forcing `discard`.
- Existing article-like Web content with a single `链接` mention remains not automatically discarded.

## Verification

Commands run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_quality_skill.py -q
python3 -m pytest tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

Results:

- Query + quality tests: 52 passed
- Connector + evidence renderer tests: 54 passed
- Pipeline + synthesis tests: 8 passed

Total focused verification: 114 passed.

## Residual Notes

- RSS is now inactive by default unless `agent_reach_rss_feeds` is supplied. This is intentional.
- The current query scorer still primarily uses `query` text, stock name, and item text. Future calibration may want to consider `rss_filter_terms` directly in scoring, but that is not required for Phase 0B acceptance.
- Live RSS/Web smoke validation should be repeated later with explicit user-provided feeds.

## Recommendation

Accept Phase 0B after Codex's portal discard fix. The changes keep Agent-Reach isolated from synthesis, scoring engine, report conclusions, and entry scripts while making RSS/Web evidence handling more conservative and auditable.
