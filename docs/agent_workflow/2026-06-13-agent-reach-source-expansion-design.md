# Agent-Reach Single-Stock Source Expansion Design

> Date: 2026-06-13  
> Owner: Codex  
> Status: Draft for Claude Review

## Goal

Expand Agent-Reach from a narrow official-web experiment into a controlled, auditable **single-stock deep-research source layer**.

The next implementation slice should expand information-source coverage for one target stock report at a time, while preserving the current safety boundary:

- Agent-Reach evidence may appear in the dedicated `Agent-Reach 外部证据观察` section.
- Agent-Reach evidence must not change scores, technical conclusions, risk scoring, LLM synthesis prompts, or citation numbering.
- All new sources must remain explicit, config-driven, stock-specific, and reviewable.

## Scope

This phase is about expanding **single-stock source coverage**, not changing downstream reasoning.

In scope:

- Build an Agent-Reach source inventory for one target stock, with Black Sesame as the pilot unless the user names another stock.
- Add explicit `agent_reach` config only for the target stock after source inventory review.
- Support existing source knobs:
  - `web_urls`
  - `official_domains`
  - `rss_feeds`
  - `rss_filter_terms`
- Add a lightweight local validation script or test helper that runs Agent-Reach query/fetch/quality for one stock and writes/prints compact status.
- Keep audit sidecar JSON as the primary runtime artifact.

Out of scope:

- Automatic whole-web search.
- Exa/Search API integration.
- WeChat scraping.
- YouTube/Bilibili transcript fetching.
- Xueqiu detail-page collection.
- KnowledgeSynthesizer prompt changes.
- Scoring engine or technical-analysis changes.
- Feeding Agent-Reach content into LLM synthesis.

## Current State

Black Sesame currently has:

- `agent_reach.enabled = true`
- six official `web_urls`
- `official_domains = ["blacksesame.com"]`
- sidecar audit JSON persistence
- official seed URL quality calibration

Other configured stocks currently have no Agent-Reach source config. That is intentional: this workflow should not batch-enable Agent-Reach across all stocks.

Existing code already supports per-stock config pass-through for `web_urls`, `rss_feeds`, `rss_filter_terms`, and `official_domains`. That means the next phase should avoid new schema unless review finds a real need.

## Proposed Approach

### Phase 6A: Single-Stock Source Inventory

Claude Code should create a source inventory document, not code, for the target stock:

```text
docs/agent_workflow/2026-06-13-agent-reach-source-inventory.md
```

For the target stock, record candidate sources in this shape:

| Stock | Source type | URL/feed | Domain | Why useful for this stock report | Risk | Recommendation |
|-------|-------------|----------|--------|----------------------------------|------|----------------|

Allowed candidate types:

- Official company news / IR / investor pages.
- Official exchange disclosure pages if stable and directly stock-specific.
- Stable RSS feeds from established finance/news sites, only when filter terms can keep them stock-specific. RSS is opt-in for this phase; official/company/exchange pages remain the default priority.
- Already-known explicit article URLs if they are primary/official or strong supporting context.

Example inventory row:

| Stock | Source type | URL/feed | Domain | Why useful for this stock report | Risk | Recommendation |
|-------|-------------|----------|--------|----------------------------------|------|----------------|
| 黑芝麻智能 | Official news article | `https://www.blacksesame.com/zh/list_10/972.html` | `blacksesame.com` | Primary-source product/safety certification evidence for the Agent-Reach evidence section | Jina Reader may include navigation noise | Keep; official seed URL |

Rejected source types should also be documented briefly:

- Search result pages.
- Login/paywall pages.
- Social feeds that require scraping.
- Xueqiu detail pages.
- Pages whose content is mostly navigation, unless they are official article pages and have passed local Jina fetch.

### Phase 6B: Single-Stock Config Expansion

After inventory review, add `agent_reach` config entries only for sources that meet these gates:

- URL/feed is stable.
- It can be fetched through existing `WebConnector` or `RSSConnector`.
- It is relevant to the stock, not a generic portal.
- It has an official domain or clearly documented source class.
- It is low risk for access/anti-scraping.

Recommended initial expansion for the target stock:

- Prefer up to 3-8 high-confidence official or primary-source URLs for the target stock. This is a ceiling, not a required floor.
- Do not enable broad RSS by default unless a feed is stable and filtering terms are stock-specific.
- If no high-confidence source exists for the target stock, leave config unchanged and document why.
- Newly discovered sources should be recorded in the source inventory first. Enable them only after smoke validation passes; otherwise leave them out of config or mark them as rejected/needs-test in the inventory.

### Phase 6C: Local Single-Stock Smoke Validation

Add a lightweight validation entry that can run the target stock's Agent-Reach path without full report generation.

Preferred implementation shape:

```text
scripts/smoke_agent_reach.py --stock 黑芝麻智能
```

Behavior:

- Load `config/stocks.json`.
- Build a minimal `SkillContext`.
- Run only:
  - `agent_reach_query_skill`
  - `agent_reach_fetch_skill`
  - `agent_reach_quality_skill`
- Print a compact table:
  - stock
  - enabled
  - query count
  - fetch status
  - quality status
  - keep/demote/discard
  - warnings
  - audit path if `--write-audit` is provided
- Default must not run full report, PDF, LLM, Zhihu, Chrome, or Xueqiu detail pages.

The smoke command is useful because a full report is too heavy when we only need to validate source reachability.

## Failure Modes

| Failure mode | Expected handling | Test/validation |
|--------------|-------------------|-----------------|
| URL DNS/network failure | Fetch status `error` or warnings; report continues | mocked connector failure |
| Generic portal URL added by mistake | quality gate discard or demote; inventory marks risk | existing portal tests plus new config review |
| RSS feed returns unrelated articles | filter terms required; unrelated entries not kept | RSS connector tests |
| Official page has navigation noise | official seed reason + reduced penalty, no "内容价值低" | existing official seed tests |
| Official page returns 403 or anti-scraping response | Fetch status `error` or warning; validation continues; inventory records access risk | mocked web failure + local smoke notes |
| Audit summary contains full content | forbidden; tests must assert no `content` | existing + smoke tests |
| Full report accidentally runs during smoke | forbidden; script imports only Agent-Reach skills | smoke test / code review |

## Files Expected To Change

Likely implementation files:

- `config/stocks.json`
- `scripts/smoke_agent_reach.py`
- `tests/reporter/test_agent_reach_source_config.py` or existing config tests
- `tests/reporter/test_agent_reach_smoke_script.py`
- `docs/agent_workflow/2026-06-13-agent-reach-source-inventory.md`
- `docs/agent_workflow/2026-06-13-agent-reach-source-expansion-claude-notes.md`

Only touch Agent-Reach query/fetch/quality code if the inventory exposes a clear bug or missing testable behavior.

## Files That Must Not Change

- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/reporter/scoring_engine.py`
- technical-analysis modules
- Xueqiu fetchers / CDP scripts
- report section conclusions outside `Agent-ReachEvidenceRenderer`

## Acceptance Gates

Focused tests:

```bash
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_stock_reporter_agent_reach_config.py -q
```

New smoke/config tests:

```bash
python3 -m pytest tests/reporter/test_agent_reach_source_config.py tests/reporter/test_agent_reach_smoke_script.py -q
```

Additional acceptance assertions:

- Smoke script tests must prove it does not import or instantiate `PerStockReporter`, `ZhihuCollector`, `KnowledgeSynthesizer`, PDF export, or full report assembly.
- Config tests must prove any new `agent_reach` config is scoped only to the target stock.
- Source inventory must be written before config expansion and must include each candidate's recommendation.

Local runtime validation:

- Run the smoke validation for the target stock that receives or already has `agent_reach.enabled=true`.
- Do not run full reports unless smoke passes.
- If full report is run for a sample stock, use the single-stock fast-test entry when available and run `scripts/check_report_quality.py`.

## Open Questions For Claude Review

1. Should this phase add only official/company/exchange URLs for the target stock, or also curated third-party RSS feeds?
2. Is a new smoke script worth adding now, or should validation remain a documented inline Python snippet?
3. For the target stock, should newly discovered sources be enabled immediately after smoke validation, or added disabled until a full report sample passes?
4. Should the source inventory include candidate URLs discovered via local browser/network research, or only URLs already present in repo docs/config?
5. Should the pilot target remain 黑芝麻智能, or should the user select the next single-stock report target?

## Round 1 Feedback

### Status

Ready — no blockers, no medium+ must-fix items. R2 is not needed; the design can move directly to task implementation.

### Findings

- [Severity: low] The "Allowed candidate types" list already includes stable RSS feeds and known explicit article URLs, while Open Question #1 asks whether to allow curated third-party RSS. The design should resolve this tension in Phase 6B: RSS is acceptable only when (a) the feed is stable, (b) filter terms are stock-specific, and (c) the publisher has established credibility. The default for this phase should remain official/company/exchange first, RSS second.
- [Severity: low] Phase 6B recommends 3-8 high-confidence URLs. This is a reasonable per-stock ceiling; making it explicit that it is a ceiling (not a per-source-type floor) would reduce misinterpretation.
- [Severity: low] The smoke script default behavior is well-scoped to query/fetch/quality only. Acceptance gates should add a test that verifies the smoke script does not import or instantiate `PerStockReporter`, `ZhihuCollector`, `KnowledgeSynthesizer`, or PDF export paths.
- [Severity: low] The source inventory document defines a table schema but contains no example row. Adding one example row for 黑芝麻智能 would reduce ambiguity for the implementer.
- [Severity: low] The failure-mode table is strong. Consider adding a row for "official page returns 403/anti-scraping" with handling: fetch status becomes `error`, validation continues, and the inventory risk column records the incident.
- [Severity: low] Acceptance tests list existing tests but do not explicitly assert that new config is added only for the target stock. Add a config-scope assertion in the new config tests.

### Recommendations

- Keep the pilot target as 黑芝麻智能 unless the user explicitly selects another stock. Do not expand to other stocks in this phase.
- Add newly discovered sources to config in a disabled or commented state first, then enable only after smoke validation passes.
- Prioritize official/company/exchange URLs; allow curated RSS only as an opt-in, stock-specific, filtered source.
- Add `scripts/smoke_agent_reach.py` — the cost is justified because full report generation is too heavy for simple source-reachability checks and would risk triggering Xueqiu/Zhihu/LLM/PDF paths.
- Include a `--dry-run` or `--print-only` mode in the smoke script so it can be used in CI/tests without writing audit files by default.
- The inventory document should be reviewed by the user before Phase 6B config changes are applied.

### Source Inventory Guidance

- Include only candidate URLs that are official/public or already-known primary sources.
- Do not include search result pages, login/paywall pages, social feeds, or Xueqiu detail pages.
- For each candidate, record: URL, domain, source type, why useful for this stock report, access risk, and recommendation (keep / reject / needs-test).
- For 黑芝麻智能, start with `blacksesame.com` IR/news pages and HKEX disclosure pages if stable URLs exist.

### Open Questions

- None that block the design. Resolve the RSS default stance and source enablement gating during implementation, per the recommendations above.

## Design Delta

- Clarify default RSS stance in Phase 6B (official first, RSS opt-in).
- Add a smoke-script anti-full-report test to the acceptance gates.
- Add one example inventory row for 黑芝麻智能.
- Add an official-page 403/anti-scraping failure mode to the failure-mode table.

## Final Implementation Readiness

Ready to write task. R2 is not needed.
