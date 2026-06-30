# Claude Implementation Task: Agent-Reach Phase 0 Connector Refactor

Implement the revised design in:

`docs/agent_workflow/2026-06-11-agent-reach-connector-refactor-design.md`

## Goal

Replace the invalid `agent-reach search <platform>` fetch layer with a connector registry.
Phase 0 must only implement low-risk real connectors for RSS and Web/Jina Reader while
preserving all downstream Agent-Reach contracts.

## Scope

Allowed files:

- Modify `scripts/utils/report_skills/agent_reach_skill.py`
- Modify `scripts/utils/report_skills/agent_reach_query_skill.py`
- Modify or replace `tests/reporter/test_agent_reach_skills.py`
- Add `tests/reporter/test_agent_reach_connector.py` if cleaner
- Update `tests/reporter/test_pipeline_integration.py` only if needed because `_run_command`
  is removed
- Write notes to:
  `docs/agent_workflow/2026-06-11-agent-reach-connector-refactor-claude-notes.md`

Do not modify:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- Entry scripts such as `scripts/xueqiu_monitor_v2.py` or `scripts/run_*.py`
- Xueqiu / Playwright / CDP fetchers
- Generated reports, caches, PDFs, images, or raw data

## Required Architecture

### Connector Registry

In `scripts/utils/report_skills/agent_reach_skill.py`, remove the old fake command mapping:

```python
_AGENT_REACH_COMMANDS = {
    "twitter": ["agent-reach", "search", "twitter"],
    ...
}
```

Replace it with:

- `Connector` base class or protocol
- `RSSConnector`
- `WebConnector`
- detection-only helper/classes for `youtube`, `exa_search`, `wechat`
- `CONNECTOR_REGISTRY` containing only:
  - `rss`
  - `web`

Do not register `youtube`, `exa_search`, or `wechat` by default. If explicitly targeted,
they should produce detection-only warnings and no records.

Do not implement or register:

- `twitter`
- `xueqiu`
- `xiaohongshu`
- `douyin`
- `linkedin`
- `reddit`
- `bilibili`
- `v2ex`

Unknown platforms should warn and skip.

### Public Skill Contract

Keep `agent_reach_fetch_skill(ctx)` behavior compatible:

Inputs:

- `agent_reach_enabled`
- `search_queries`

Outputs:

- `agent_reach_status`
- `agent_reach_items`
- `agent_reach_warnings`

No downstream keys or consumers should change.

### Status Mapping

Implement deterministic status mapping:

- disabled when `agent_reach_enabled` is false
- empty when `search_queries` is empty
- missing_binary when every attempted connector is unavailable due dependencies/config
- empty when at least one connector is available but no records match and there is no runtime error
- error when at least one connector is available, no records are returned, and runtime/parse errors occurred
- ok when at least one record is returned and no timeout/budget was hit
- timeout when records exist and a timeout/budget warning occurred

Warnings must use `[platform] message` format.

### Dependency Checks

`check_deps()` must only check local prerequisites. It must not make network calls.

Cache dependency results per `agent_reach_fetch_skill()` run so each connector is checked
only once per run.

### RSSConnector

Dependency check:

- import `feedparser`
- no network calls in `check_deps()`

Input query spec:

```python
{
    "query": "rss_poll",
    "target_platforms": ["rss"],
    "rationale": "行业 RSS 订阅",
    "rss_feeds": [...],
    "rss_limit": 5,
    "rss_filter_terms": [...],
}
```

Runtime behavior:

- if `rss_filter_terms` is empty, return no records and warning:
  `[rss] no filter terms, skipping to avoid noise`
- parse each feed with `feedparser.parse(url)`
- keep only entries whose title/summary/description contains at least one filter term
- enforce `rss_limit`
- return raw dict records with:
  - `_platform = "rss"`
  - `title`
  - `content`
  - `url`
  - `author`
  - `publish_time`
  - `source_feed`
  - `tags`

### WebConnector

Dependency check:

- only check Python stdlib `urllib.request`
- no network calls in `check_deps()`

Input query spec:

```python
{
    "query": "web_read",
    "target_platforms": ["web"],
    "rationale": "读取已知网页",
    "urls": [...],
    "timeout": 15,
}
```

Runtime behavior:

- if URLs are empty, return no records and warning:
  `[web] no URLs provided`
- read each URL via Jina Reader:
  `https://r.jina.ai/{url}`
- use `urllib.request.Request`
- catch timeout, HTTP errors, empty content
- return raw dict records with:
  - `_platform = "web"`
  - `title`
  - `content`
  - `url`
  - `author = ""`
  - `publish_time = ""`

### Detection-Only Platforms

If explicitly targeted:

- `youtube`: check `yt-dlp` and `node` or `deno`; warn with dependency status; no records
- `exa_search`: check `mcporter`; optionally check config output if safe/local; no records
- `wechat`: share Exa dependency check; no records

Do not target these by default.

## Query Skill Requirements

Modify `generate_agent_reach_queries()` and/or `agent_reach_query_skill()` to Phase 0 behavior.

RSS:

- default target is `rss`
- add `rss_filter_terms`
- include stock name, code, competitors, and conservative industry keywords if available
- allow `agent_reach_rss_feeds` ctx override
- use a module constant for default feeds; do not add a config file

Web:

- only add `web` query when ctx has non-empty:
  - `agent_reach_urls`, or
  - `agent_reach_web_urls`
- do not generate empty `urls: []`

Default queries must not include:

- twitter
- reddit
- bilibili
- wechat
- xiaohongshu
- youtube
- exa_search

If adding an optional ctx parameter to `generate_agent_reach_queries()` is the cleanest way
to access URL/feed overrides, keep it backward-compatible for existing tests.

## Tests

Use TDD: write failing tests first, run them, then implement.

Required focused coverage:

- registry contains `rss` and `web`
- registry does not contain `twitter`
- registry does not contain `youtube`
- unknown platform creates warning and does not fail
- explicit detection-only `youtube` creates detection-only/unavailable warning and no records
- RSS dependency ok/missing
- RSS skips empty `rss_filter_terms`
- RSS filters matching entries
- RSS no-match returns empty behavior
- RSS parse/runtime failure returns warning
- RSS limit enforced
- Web dependency ok
- Web read success
- Web HTTP error / timeout / empty content warnings
- Web multiple URLs partial success
- query skill does not generate Web query without URLs
- query skill generates Web query with `agent_reach_urls`
- query skill default targets only Phase 0 platforms
- status mapping:
  - disabled
  - empty no queries
  - missing_binary all dependencies unavailable
  - empty available but no records
  - error available but runtime failure no records
  - ok with records
  - timeout with records and budget/timeout
- total cap
- dedupe by URL
- output items are `SynthesisItem`
- quality skill accepts produced items
- evidence renderer accepts produced items

Remove or rewrite tests that patch `_run_command`, because `_run_command` should no longer
exist as a fake `agent-reach search` execution path.

Run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py -q
python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

If you do not create `tests/reporter/test_agent_reach_connector.py`, omit that file from the
first command and explain the choice in notes.

## Notes File

After implementation, write:

`docs/agent_workflow/2026-06-11-agent-reach-connector-refactor-claude-notes.md`

Include:

- Files changed
- Tests run and exact results
- Whether `_AGENT_REACH_COMMANDS` and fake `agent-reach search` paths were removed
- Which connectors are registered by default
- Any deviations from the design
- Confirmation that forbidden files were not modified
- Any blockers

## Guardrails

- Do not run real RSS/Web network calls during tests; mock them.
- Do not run real Agent-Reach searches.
- Do not login to any platform.
- Do not configure cookies.
- Do not modify LLM prompts, synthesis, scoring, entry scripts, or Xueqiu/CDP code.
- Do not commit generated artifacts.
