# Agent-Reach Connector Refactor Codex Review

Date: 2026-06-11

## Status

Ready with changes.

The core diagnosis is correct: `agent-reach search <platform>` does not exist, so the
current `agent_reach_skill.py` fetch layer is a mockable but invalid runtime interface.
The proposed connector registry is the right replacement boundary, and the existing
downstream layers can be preserved.

Do not implement the design as-is until the changes below are folded in.

## What Should Be Preserved

- Keep `agent_reach_fetch_skill(ctx)` as the public skill entry.
- Keep output keys unchanged:
  - `agent_reach_status`
  - `agent_reach_items`
  - `agent_reach_warnings`
- Keep downstream contracts unchanged:
  - `AgentReachAdapter`
  - `agent_reach_quality_skill`
  - `AgentReachEvidenceRenderer`
- Keep default pipeline disabled unless `enable_agent_reach=True`.

## Required Design Changes

### 1. Do Not Run Web/Jina Dependency Network Checks Per Stock

The design suggests `WebConnector.check_deps()` can send a HEAD request to Jina Reader.
That is too expensive and can turn dependency checking into network behavior before any
actual URL read.

Change:

- `check_deps()` should only check local prerequisites for Phase 0.
- For Web/Jina, local prerequisite is basically Python stdlib availability.
- Actual Jina reachability should be handled in `run()` per URL with timeout and warning.
- Cache each connector's `check_deps()` result for one `agent_reach_fetch_skill()` run.

### 2. Do Not Emit Web Queries With Empty URL Lists

Web is not a search connector; it reads known URLs. A default query like:

```python
{"query": "web_read", "target_platforms": ["web"], "urls": []}
```

will only create useless empty results or warnings.

Change:

- `agent_reach_query_skill` should include a Web query only when known URLs exist.
- Accept optional ctx input such as `agent_reach_urls` or `agent_reach_web_urls`.
- If no URLs are supplied, do not add `web` to `search_queries`.
- This is an input extension, not an output contract change.

### 3. Filter RSS Entries Before Creating Records

RSS feed polling without filtering can produce broad market/news noise for every stock.
The quality gate will discard some noise, but Phase 0 should avoid flooding it.

Change:

- RSS query specs should carry filter terms:
  - `stock_name`
  - code, if useful
  - competitors, if available
  - industry keywords if already available
- `RSSConnector` should keep entries whose title/content match at least one filter term.
- If no filter terms exist, either skip RSS or cap aggressively and warn.

### 4. Clarify Status Mapping For Dependency-Only Failure

The design says all connectors unavailable may be `"error"` or `"missing_binary"`.
This must be deterministic for tests and Phase 2 quality behavior.

Change:

- If every attempted connector is unavailable due dependency/config, status should be
  `"missing_binary"` and warnings should include `[platform] unavailable: ...`.
- If connectors were available but returned no records, status should be `"empty"`.
- If available connectors produced parse/runtime errors and no records, status should be
  `"error"`.
- If at least one connector returns records, status should be `"ok"` unless timeout/budget
  was hit, in which case `"timeout"`.

### 5. Detection-Only Connectors Should Not Be Targeted By Default

YouTube, Exa, and WeChat detection-only connectors are useful for future readiness, but if
default queries target them now, users will see repeated warnings with no data.

Change:

- Keep detection-only classes optional.
- Do not include `youtube`, `exa_search`, or `wechat` in default Phase 0 query targets.
- If a caller explicitly targets them, return a clear warning and no records.

### 6. Tests Must Stop Patching `_run_command`

Existing tests patch `_run_command` around fake `agent-reach search` behavior. Those tests
should be replaced with connector-level tests.

Required test updates:

- Remove direct import reliance on `_run_command` from tests.
- Add connector tests for `RSSConnector`, `WebConnector`, registry, unknown platform,
  status mapping, dedupe, caps, and ctx contract.
- Keep regression tests that verify downstream quality/render can consume produced
  `SynthesisItem` objects.

## Implementation Scope Recommendation

Phase 0 should implement only:

- `RSSConnector`
- `WebConnector`
- connector registry
- revised query generation for:
  - RSS with filter terms
  - Web only when URL list is supplied
- detection-only stubs only if they do not add runtime warning noise

Do not implement:

- Twitter/X
- Xueqiu
- Xiaohongshu
- Douyin
- LinkedIn
- Reddit
- Bilibili
- YouTube search/subtitles
- Exa/WeChat search

## Open Design Question

Where should default RSS feed URLs live?

Recommendation for Phase 0:

- Put a tiny, conservative default list in `agent_reach_query_skill.py` or a small constant in
  `agent_reach_skill.py`.
- Prefer allowing ctx override via `agent_reach_rss_feeds`.
- Do not add a new config file until real RSS value is proven.

## Next Step

Ask Claude to revise the design with the required changes above. If Claude agrees and no
new blockers appear, the next implementation task can be limited to:

- `scripts/utils/report_skills/agent_reach_skill.py`
- `scripts/utils/report_skills/agent_reach_query_skill.py`
- `tests/reporter/test_agent_reach_skills.py`
- optional new `tests/reporter/test_agent_reach_connector.py`

No changes should be made to synthesis, scoring, report rendering, entry scripts, or
Xueqiu/CDP code.
