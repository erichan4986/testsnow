# Claude Code Task: Agent-Reach Phase 0B Runtime Revalidation

> **Notes Output**: `docs/agent_workflow/2026-06-11-agent-reach-phase0b-runtime-revalidation-claude-notes.md`
> **Local Runner**: user runs this prompt from the local trusted terminal.
> **Validation Only**: do not modify source code.

## Goal

Revalidate Agent-Reach Phase 0B after RSS/Web calibration.

Answer:

1. With empty default RSS feeds, does Agent-Reach safely return `empty` when no explicit feeds or URLs are provided?
2. With explicit `agent_reach_rss_feeds`, does RSS still work?
3. Do identity-only filter terms avoid broad false positives such as standalone `科技`?
4. Do RSS/Web source-aware quality thresholds produce better keep/demote/discard behavior?
5. Are obvious Web portal/navigation pages now forced to discard?
6. Does the Agent-Reach evidence renderer produce readable output from the calibrated results?

## Hard Scope

Do not modify source code, tests, reports, generated images, caches, raw data, or entry scripts.

Do not use:

- Xueqiu cookies
- logged-in accounts
- Playwright/Chrome/CDP
- browser automation
- Twitter/X, Reddit, Bilibili, Xiaohongshu, Douyin, LinkedIn, or other non-Phase-0 connectors
- LLM synthesis or paid APIs

Allowed outputs:

- notes file listed above
- temporary artifacts under `/tmp/agent_reach_phase0b_revalidation/`

## Context Files

Read:

- `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-codex-review.md`
- `docs/agent_workflow/2026-06-11-agent-reach-phase0b-calibration-implementation-claude-notes.md`
- `scripts/utils/report_skills/agent_reach_query_skill.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/report_skills/agent_reach_skill.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`

## Required Steps

### 1. Focused Tests

Run and record:

```bash
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_quality_skill.py -q
python3 -m pytest tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

Do not run full `pytest`.

### 2. No-Input Behavior

Run the Agent-Reach query/fetch/quality path with:

- `enable_agent_reach=True`
- stock name and code provided
- no `agent_reach_rss_feeds`
- no `agent_reach_urls`

Record:

- generated `search_queries`
- fetch status
- quality status
- warnings

Expected: no RSS query, fetch status `empty`, no crash.

### 3. Explicit RSS Feed Smoke Test

Use at most 1-2 explicit RSS feeds. Prefer a feed that was known to work during prior validation, such as 36kr, if available locally.

Use specific identity filters, not broad terms:

- stock context: `黑芝麻智能`, `02533`
- optional explicit filter terms: `["黑芝麻智能", "黑芝麻", "02533"]`

Record:

- query specs
- fetch status
- item count
- quality status
- keep/demote/discard counts
- representative item titles/actions/scores/reasons
- whether any false positives were caused by broad terms

If no RSS items match, record whether this is due to strict identity filters, feed availability, or parser/network errors.

### 4. Web/Jina Smoke Test

Use 1 article-like public URL and 1 portal/homepage URL if available without login.

Record:

- fetch status
- quality action
- score and reasons
- whether portal/homepage is discarded with portal/navigation reason
- whether article-like URL avoids false portal discard

If Jina/SSL/network is flaky, skip after one bounded attempt and record the reason.

### 5. Renderer Sample

Render `AgentReachEvidenceRenderer` directly from the real keep/demote items gathered above.

Write:

`/tmp/agent_reach_phase0b_revalidation/agent_reach_live_section.md`

Record:

- whether section renders,
- keep/demote/discard counts shown,
- whether table is readable,
- whether themed grouping makes sense.

## Notes Format

Write `docs/agent_workflow/2026-06-11-agent-reach-phase0b-runtime-revalidation-claude-notes.md`:

```markdown
# Agent-Reach Phase 0B Runtime Revalidation Notes

## Status

Accepted / Accepted with issues / Blocked

## Tests

| Command | Result |
| --- | --- |

## No-Input Behavior

- search_queries:
- fetch status:
- quality status:
- warnings:

## Explicit RSS Results

| Feed | Stock/filter | Fetch status | Items | Keep | Demote | Discard | Key warnings |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |

### Representative RSS Items

- title / action / score / reasons / url

## Web/Jina Results

| URL | Page type | Fetch status | Action | Score | Key reasons |
| --- | --- | --- | --- | ---: | --- |

## Renderer Sample

- path:
- readable:
- topic grouping:

## Assessment

- Did Phase 0B fix the default-feed issue?
- Did identity-only filters reduce false positives?
- Did RSS/Web scoring improve useful evidence retention?
- Did portal detection work?

## Follow-Ups

- Concrete next steps only.
```

## Completion Criteria

- Notes file exists.
- No source files are modified.
- Focused tests are recorded.
- No-input behavior is tested.
- At least one of RSS or Web live smoke tests is attempted.
- Renderer sample is attempted if any keep/demote item exists.
