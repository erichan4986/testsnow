# Agent-Reach Phase 0B RSS/Web Calibration Design

> **Date**: 2026-06-11
> **Owner**: Codex
> **Status**: Locked for Implementation

## 1. Goal

Calibrate the Phase 0 Agent-Reach RSS/Web path after runtime validation showed that the connector architecture works but the default data and quality rules are not yet useful enough for stock reports.

This phase should keep the current safety boundary:

- Agent-Reach remains optional behind `enable_agent_reach=True`.
- Agent-Reach evidence remains separate from `KnowledgeSynthesizer`, report scoring, technical analysis, and LLM conclusions.
- No new social/login platforms are added.
- No Xueqiu, Playwright, CDP, browser, cookie, or account-based collection is introduced.

The desired outcome is a more usable Phase 0 path:

1. Default RSS behavior does not rely on broken feeds.
2. Query/filter terms are specific enough to avoid broad matches like `科技` or `UK`.
3. RSS/Web items are scored fairly despite having no engagement metrics.
4. Portal/navigation Web pages are filtered more reliably.

## 2. Evidence From Runtime Validation

Reference:

- `docs/agent_workflow/2026-06-11-agent-reach-phase0-runtime-validation-claude-notes.md`

Findings:

- `rss` and `web` connectors are locally available.
- Default RSS feeds are not reliable:
  - `chinastock.com.cn`: SSL certificate error
  - Sina RSS URL: invalid XML
  - CNInfo RSS URL: empty/no entries
- RSSConnector works with valid feeds such as 36kr and BBC.
- Quality gate is too social-post-oriented:
  - RSS/Web items have `interaction_score=0`.
  - A data-rich 36kr item scored 56 and was demoted.
- Validation also exposed false positives:
  - Generic filter terms such as `科技` and `UK` matched unrelated RSS content.
  - Portal pages fetched through Jina Reader were correctly discarded, but only after spam penalties.

## 3. Non-Goals

- Do not add YouTube, Exa, WeChat, Twitter/X, Reddit, Bilibili, Xueqiu, Xiaohongshu, Douyin, LinkedIn, or V2EX.
- Do not modify `KnowledgeSynthesizer`, LLM prompts, synthesis item assembly, scoring engine, technical analysis, risk scoring, or entry scripts.
- Do not render discarded items.
- Do not run broad live crawling in tests.
- Do not introduce a new dependency.
- Do not add a persistent config file unless absolutely necessary.

## 4. Proposed Changes

### 4.1 RSS Feed Defaults

Current defaults should be revised because all three failed during validation.

Locked Phase 0B behavior:

- Set `_DEFAULT_RSS_FEEDS = []`.
- Keep `agent_reach_rss_feeds` ctx override as the primary control.
- If no RSS feeds are provided and there are no Web URLs, query generation may return an empty list.
- Do not replace broken defaults with another hard-coded public feed list in this phase.

Rationale:

- The validation showed all three hard-coded feeds failed.
- 36kr worked but is broad technology/startup news, not stock-specific research.
- An empty default is less convenient, but safer and easier to reason about than a decaying hard-coded feed list.

### 4.2 Specific RSS Filter Terms

Do not add generic market or language terms that can match broad unrelated content.

Update `_build_rss_filter_terms()` rules:

- Always include non-empty `stock_name`.
- Include stock code only when non-empty.
- Include competitors only when explicitly supplied.
- Add short-name variants only when derivable from the stock name and not dangerously generic.
- Do not automatically add generic industry keywords based on stock name substring.
- Never include one-word generic terms such as `科技`, `AI`, `UK`, `China`, `市场`, `投资`, or `新闻` as standalone filters.
- Allow an optional explicit override key `agent_reach_rss_filter_terms` for users who knowingly want broader or custom filters.

For Phase 0B, prefer false negatives over false positives. RSS is an external-evidence supplement, not the primary research source.

Test expectations:

- `generate_agent_reach_queries("澜起科技", "688008")` includes `澜起科技` and `688008`.
- It must not include standalone `科技`.
- `generate_agent_reach_queries("", "")` still generates no RSS query.
- Explicit Web URLs still work without RSS filter terms.

### 4.3 Source-Aware Quality Scoring

Do not globally lower `_KEEP_THRESHOLD`.

Instead, make `score_agent_reach_item()` source-aware while keeping the public API and output shape unchanged.

Detect source type from `item.source_platform`:

- `AgentReach(rss)` -> RSS profile
- `AgentReach(web)` -> Web profile
- anything else -> existing social/default profile

RSS/Web profile changes:

- Engagement score should be ignored, not punished or artificially granted.
  - Set RSS/Web `interaction_weight = 0`.
  - Add an audit reason such as `非社交来源，不按互动评分`.
- Reward concrete evidence patterns more strongly for RSS/Web:
  - monetary amounts
  - percentages
  - dates
  - technical metrics
  - company/customer names
- Keep relevance strict:
  - Stock name/code/query term match remains important.
  - A generic filter term match alone must not make an item relevant.

Use source-specific thresholds:

- social/default:
  - keep >= 60
  - demote >= 35
  - discard < 35
- rss/web:
  - keep >= 50
  - demote >= 30
  - discard < 30

This is not a global threshold reduction. Social/default scoring must remain unchanged.

Recommendation:

- Use scoring profiles by source type.
- For RSS/Web, set interaction weight to 0 rather than granting artificial interaction points.
- Tune evidence/content thresholds for RSS/Web summaries.

Expected behavior:

- A data-rich RSS/Web item with stock/query relevance and URL can reach keep without interaction metrics.
- Unrelated BBC-style false positives should remain demote or discard unless they actually match specific stock/code/query terms.
- Portal pages should remain discard.

### 4.4 Portal/Page-Shape Guard

Add a deterministic page-shape guard in the quality gate rather than in `WebConnector`.

Reason:

- `WebConnector` should stay a reader/normalizer.
- Quality gate is the right place to decide whether a page is evidence.

Possible helper:

```python
def _looks_like_portal_page(item: SynthesisItem) -> tuple[bool, list[str]]:
    ...
```

Signals:

- very high link/navigation word density (`链接`, `首页`, `登录`, `注册`, `频道`, `导航`, `更多`)
- very long content with many short navigation fragments and few evidence/data patterns
- title looks like a homepage/portal title rather than an article

Behavior:

- Apply a Web-only `portal_penalty` when multiple portal signals are present.
- Do not discard a legitimate article merely because it contains one word like `链接`.
- The implementation may force discard only if tests show the soft penalty is insufficient for obvious portal pages.

Tests should include:

- Sina/Baidu-like portal content is discard.
- Article content containing one source link is not automatically penalized to discard.

## 5. Files Expected To Change

| File | Change Type | Reason |
| --- | --- | --- |
| `scripts/utils/report_skills/agent_reach_query_skill.py` | Modify | Replace broken RSS defaults and tighten filter terms |
| `scripts/utils/report_skills/agent_reach_quality_skill.py` | Modify | Source-aware scoring for RSS/Web and portal guard |
| `tests/reporter/test_agent_reach_skills.py` | Modify | Query/filter/default RSS tests |
| `tests/reporter/test_agent_reach_quality_skill.py` | Modify | RSS/Web scoring and portal guard tests |
| `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-claude-notes.md` | Add | Implementation/review notes later |

## 6. Files That Must Not Change

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `scripts/xueqiu_monitor_v2.py`
- `scripts/run_*.py`
- Xueqiu/Playwright/CDP fetchers
- generated reports, images, raw data, cache files

## 7. Testing Plan

Unit tests:

- Query generation:
  - no empty RSS filters
  - no default RSS query when no `agent_reach_rss_feeds` override is provided
  - RSS query generated when explicit feeds are provided
  - no standalone generic `科技`
  - optional explicit `agent_reach_rss_filter_terms` override works
  - explicit competitors included
  - explicit Web URLs still generate Web query
- RSS/Web scoring:
  - data-rich RSS item reaches keep without interaction score
  - unrelated RSS item with generic term does not reach keep
  - social item scoring remains unchanged
  - source-specific thresholds do not lower social keep/demote thresholds
  - official/verified metadata handling still tolerates missing `extra.raw`
- Portal guard:
  - portal/navigation page is discard
  - article with one link/spam-like term is not automatically discard

Regression tests:

```bash
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_quality_skill.py -q
python3 -m pytest tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

No live network calls in automated tests.

## 8. Acceptance Criteria

- Default RSS query generation intentionally has no default feeds and requires `agent_reach_rss_feeds` for RSS activation.
- Query filters do not contain standalone broad terms such as `科技`.
- RSS/Web items are not penalized solely for lacking interaction metrics.
- A data-rich RSS/Web item can pass `keep` while unrelated/generic matches do not.
- Portal/navigation Web pages remain filtered.
- Default pipeline remains unchanged when `enable_agent_reach=False`.
- Agent-Reach still does not enter `KnowledgeSynthesizer`, report scoring, or LLM prompt context.

## 9. Claude Round 1 Review Response

Claude review notes:

- `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-claude-notes.md`

Accepted decisions:

1. Default RSS feeds are empty. RSS requires explicit `ctx.agent_reach_rss_feeds`.
2. RSS filter terms are identity-only: stock name, code, competitors, short-name variants, or explicit user override.
3. RSS/Web scoring is source-aware. Social thresholds remain 60/35; RSS/Web thresholds are 50/30.
4. Portal detection belongs in `agent_reach_quality_skill.py`, not in `WebConnector`.
5. Implementation order: query skill first, then source-aware scoring, then portal guard, then focused tests and optional live smoke validation.
