# Claude Notes: Agent-Reach Phase 0B RSS/Web Calibration

## Summary

Calibrated Agent-Reach Phase 0 RSS/Web behavior after runtime validation:

- Default RSS feeds cleared (were all broken).
- RSS filter terms tightened to identity-only (stock_name, code, competitors, short-name).
- Removed broad industry keyword injection.
- Added `agent_reach_rss_filter_terms` ctx override.
- Added source-aware quality scoring: RSS/Web use lower thresholds (KEEP=50/DEMOTE=30), no interaction-score penalty, adjusted content-length thresholds.
- Added Web portal/navigation page detection in quality gate.
- Preserved all social/default scoring behavior unchanged.

## Files Changed

- `scripts/utils/report_skills/agent_reach_query_skill.py`
  - `_DEFAULT_RSS_FEEDS = []`
  - Removed `_INDUSTRY_KEYWORDS` and auto-injection
  - Added `_derive_short_name()` with suffix stripping
  - Added `agent_reach_rss_filter_terms` ctx override support
  - RSS query only generated when feeds and filter_terms are both non-empty
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
  - Added `_detect_source_type()`, `_SCORING_PROFILES`, `_is_portal_page()`
  - `_score_credibility()`, `_score_evidence()`, `_score_substance()`, `_score_engagement()` now accept `profile` dict
  - `score_agent_reach_item()` uses source-specific thresholds and portal penalty
- `tests/reporter/test_agent_reach_skills.py`
  - Updated 2 existing tests for empty default feeds
  - Added 6 new Phase 0B query calibration tests
- `tests/reporter/test_agent_reach_quality_skill.py`
  - Added 6 new Phase 0B quality calibration tests

## Tests Added Or Updated

### Query skill (test_agent_reach_skills.py)
- `test_generate_no_rss_query_without_feeds` — no feeds → no RSS query
- `test_generate_rss_query_with_feed_override` — ctx feeds generates query
- `test_filter_terms_no_industry_keywords` — "科技" not in filter terms for "澜起科技"
- `test_filter_terms_explicit_override` — `agent_reach_rss_filter_terms` honored
- `test_web_query_without_rss` — Web query works even when RSS absent
- `test_empty_stock_no_feeds_no_urls_returns_empty` — complete empty case
- Updated `test_query_skill_enabled_generates_rss_query` — added feed override
- Updated `test_generate_agent_reach_queries_backward_compatible_without_ctx` — adjusted for empty defaults

### Quality skill (test_agent_reach_quality_skill.py)
- `test_rss_data_rich_item_can_keep_with_zero_interaction` — RSS keep at 50+ with interaction=0
- `test_web_article_can_keep_with_zero_interaction` — Web keep at 50+ with interaction=0
- `test_social_item_below_threshold_stays_not_keep` — social threshold unchanged (60)
- `test_generic_unrelated_rss_item_not_keep` — unrelated content stays not-keep
- `test_web_portal_page_discarded` — portal detection + discard reason
- `test_web_article_with_one_link_not_discarded` — single 链接 does not auto-discard

## Tests Run

| Command | Result | Notes |
| --- | --- | --- |
| `pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_quality_skill.py -q` | 51 passed | Includes 12 new Phase 0B tests |
| `pytest tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_evidence_renderer.py -q` | 54 passed | No regressions |
| `pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q` | 8 passed | No regressions |

## Local Command Used

```bash
cd /Users/erichan/testsnow
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_quality_skill.py -q
python3 -m pytest tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

## Deviations From Task

- None.

## Blockers Or Follow-Ups

- None.
