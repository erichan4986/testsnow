# Claude Code Task: Agent-Reach Phase 0 Runtime Validation

> **Local Runner**: user runs this prompt from the local trusted terminal.
> **Notes Output**: `docs/agent_workflow/2026-06-11-agent-reach-phase0-runtime-validation-claude-notes.md`
> **Validation Only**: do not modify source code unless explicitly asked in a later task.

## Goal

Validate the newly refactored Agent-Reach Phase 0 connector layer under real local runtime conditions.

The previous task replaced the invalid fake `agent-reach search <platform>` path with a Connector Registry. This task should answer:

1. Do the default `rss` and `web` connectors actually run locally?
2. What kind of records do they produce for stock research?
3. Is the deterministic quality gate too strict, especially for useful but short external evidence?
4. Does the themed evidence renderer produce a readable report section with real connector output?

## Hard Scope

Do not modify source code in this task.

Allowed outputs:

- Write validation notes to:
  `docs/agent_workflow/2026-06-11-agent-reach-phase0-runtime-validation-claude-notes.md`
- Write temporary validation artifacts under:
  `/tmp/agent_reach_phase0_validation/`

Forbidden:

- Do not edit `scripts/utils/**`, tests, report templates, scoring, renderers, or pipeline code.
- Do not modify `KnowledgeSynthesizer`, prompts, scoring, technical indicators, or report assembly logic.
- Do not use Xueqiu cookies, logged-in social accounts, Playwright, Chrome CDP, or browser automation.
- Do not access Twitter/X, Xueqiu, Xiaohongshu, Douyin, Reddit, Bilibili, LinkedIn, or other non-Phase-0 connectors.
- Do not run broad crawling. Keep live network calls small and bounded.
- Do not invoke LLM synthesis or paid external APIs.

If you discover a code bug, stop after documenting the reproducible symptom and recommended fix. Do not patch it in this task.

## Context Files To Read

- `docs/agent_workflow/2026-06-11-agent-reach-connector-refactor-design.md`
- `docs/agent_workflow/2026-06-11-agent-reach-connector-refactor-codex-implementation-review.md`
- `scripts/utils/report_skills/agent_reach_query_skill.py`
- `scripts/utils/report_skills/agent_reach_skill.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`

## Required Validation Steps

### 1. Focused Regression Tests

Run the focused tests that prove the connector layer and downstream contracts still work.

Record exact pass/fail summaries for:

- `tests/reporter/test_agent_reach_skills.py`
- `tests/reporter/test_agent_reach_connector.py`
- `tests/reporter/test_agent_reach_quality_skill.py`
- `tests/reporter/test_agent_reach_evidence_renderer.py`
- `tests/reporter/test_pipeline_integration.py`
- `tests/reporter/test_synthesis_skills.py`

Do not run full `pytest` unless you have a clear timeout and can finish it quickly.

### 2. Dependency Probe

From local Python, check:

- `RSSConnector.check_deps()`
- `WebConnector.check_deps()`
- detection-only connectors for `youtube`, `exa_search`, and `wechat`

Record:

- connector name
- available/unavailable
- reason
- whether it is registered in `CONNECTOR_REGISTRY`

Expected default registry: only `rss` and `web`.

### 3. Live RSS Smoke Test

Run a small live RSS validation through the actual query/fetch/quality flow.

Use at most 2-3 RSS feeds and a small result cap. Prefer the module default feeds first. If a default feed fails, record the failure and try one conservative public finance/news RSS feed only if needed.

Suggested stock contexts:

- 黑芝麻智能 / `02533`
- 澜起科技 / `688008`

For each stock:

1. Generate queries with `generate_agent_reach_queries()`.
2. Confirm RSS queries have non-empty `rss_filter_terms`.
3. Run `agent_reach_fetch_skill(ctx)`.
4. Run `agent_reach_quality_skill(ctx)`.
5. Record:
   - `agent_reach_status`
   - number of raw normalized items
   - warnings
   - quality status
   - keep/demote/discard counts
   - top 3 items by quality score, with title/source/url/action/reasons
   - any discard item that looks useful to a human reader

If live RSS returns no records, do not treat that as failure automatically. Determine whether it is caused by:

- strict filter terms,
- dead/unavailable feed,
- no matching recent articles,
- parser/runtime error,
- missing dependency.

### 4. Live Web/Jina Smoke Test

Run a bounded WebConnector validation only with explicit URLs.

Use 1-2 known, public, low-risk URLs related to one target stock or its official/company/news pages. Do not scrape logged-in or social pages.

If you cannot identify a stable public URL without broad web search, skip this step and record why.

For each URL:

1. Run through `agent_reach_fetch_skill(ctx)` with `agent_reach_urls` or an equivalent web query.
2. Run `agent_reach_quality_skill(ctx)`.
3. Record:
   - success/failure
   - content length
   - title extraction quality
   - quality action
   - reasons
   - warnings

### 5. Quality Gate Strictness Review

Review the live RSS/Web outputs as a human.

Answer:

- Are any good stock-research items being discarded?
- Are demoted items actually useful enough to surface as "待人工复核线索"?
- Which scoring dimension caused most false negatives: relevance, credibility, evidence density, content richness, or interaction?
- Does RSS/Web content shape require different scoring from social posts?

Do not change thresholds in this task. Provide concrete examples and suggested follow-up tests if needed.

### 6. Renderer Sample

Create a small Markdown sample of the Agent-Reach evidence section using the real keep/demote items from this validation.

Use `AgentReachEvidenceRenderer.render(ctx)` directly; do not run the full LLM report pipeline unless it is already cheap and local.

Write the sample to:

`/tmp/agent_reach_phase0_validation/agent_reach_live_section.md`

Record:

- whether the section renders,
- whether topic grouping looks sensible,
- whether any item lands in an obviously wrong topic,
- whether tables are readable.

PDF export is optional. If PDF export requires browser/macOS permissions, skip it and record the reason instead of trying repeatedly.

## Notes File Format

Write `docs/agent_workflow/2026-06-11-agent-reach-phase0-runtime-validation-claude-notes.md` with:

```markdown
# Agent-Reach Phase 0 Runtime Validation Notes

## Status

Accepted / Accepted with issues / Blocked

## Environment

- Python:
- Working directory:
- Network available: yes/no/partial

## Test Results

| Command | Result |
| --- | --- |

## Dependency Probe

| Connector | Registered by default | Available | Reason |
| --- | --- | --- | --- |

## Live RSS Results

| Stock | Fetch status | Items | Keep | Demote | Discard | Key warnings |
| --- | --- | ---: | ---: | ---: | ---: | --- |

### Notable RSS Items

List title/source/url/action/score/reasons for representative items.

## Live Web Results

| URL | Fetch status | Items | Quality action | Warnings |
| --- | --- | ---: | --- | --- |

## Quality Gate Strictness Assessment

- Good items discarded:
- Demoted items useful:
- Main false-negative dimension:
- Suggested future scoring changes:

## Renderer Sample

- Markdown sample path:
- Placement/readability:
- Topic classification issues:

## Blockers Or Follow-Ups

List concrete follow-up tasks. Do not include broad platform expansion unless supported by this validation.
```

## Completion Criteria

This task is complete when:

- The notes file exists.
- Focused tests are recorded.
- At least dependency probe and one of live RSS or live Web validation has been attempted.
- Quality-gate strictness is assessed with concrete examples or a clear "no live items available" explanation.
- No source files are modified.
