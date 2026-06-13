# Claude Implementation Task: Agent-Reach Single-Stock Source Expansion

## Status

Ready for local Claude Code implementation. Round 1 design review found no blockers and no medium+ must-fix items. R2 is not needed.

## Read First

Read and follow:

```text
docs/agent_workflow/2026-06-13-agent-reach-source-expansion-design.md
```

This is a single-stock deep research expansion task. It is not a batch/multi-stock rollout.

## Goal

Expand Agent-Reach information-source coverage for one target stock report, with 黑芝麻智能 as the pilot, while keeping Agent-Reach isolated from scoring, LLM synthesis, technical analysis, and final recommendations.

## Scope

Implement three narrow pieces:

1. Create a target-stock source inventory document.
2. Add a lightweight single-stock Agent-Reach smoke script.
3. If the inventory and smoke validation support it, update only 黑芝麻智能's `agent_reach` config with validated explicit sources.

Do not change report conclusions, scoring, synthesis prompts, Xueqiu collection, or technical analysis.

## Target Stock

Default target:

```text
黑芝麻智能 / HK02533
```

Do not add Agent-Reach config to other stocks in this task.

## Allowed Files

Prefer keeping changes within:

- `docs/agent_workflow/2026-06-13-agent-reach-source-inventory.md`
- `docs/agent_workflow/2026-06-13-agent-reach-source-expansion-claude-notes.md`
- `scripts/smoke_agent_reach.py`
- `tests/reporter/test_agent_reach_smoke_script.py`
- `tests/reporter/test_agent_reach_source_config.py`
- `tests/reporter/test_stock_reporter_agent_reach_config.py`
- `config/stocks.json`

Only touch the existing Agent-Reach query/fetch/quality implementation if tests expose a clear bug. If that happens, stop and explain before changing it unless the fix is a narrow, directly tested bugfix.

## Forbidden Changes

- Do not modify `scripts/utils/knowledge_synthesizer.py`.
- Do not modify `scripts/utils/report_skills/synthesis_skills.py`.
- Do not modify `scripts/utils/reporter/scoring_engine.py`.
- Do not modify technical-analysis modules.
- Do not modify Xueqiu fetchers, CDP scripts, or Playwright scraping logic.
- Do not add automatic whole-web search.
- Do not add Exa/Search API, WeChat, YouTube, Bilibili, or social scraping.
- Do not run full reports before smoke tests pass.
- Do not feed Agent-Reach evidence into LLM synthesis, scoring, final recommendation, or numbered citations.
- Do not persist full fetched page content in audit JSON.

## Implementation Requirements

### Task 1: Source Inventory

Create:

```text
docs/agent_workflow/2026-06-13-agent-reach-source-inventory.md
```

The inventory must focus only on 黑芝麻智能.

Include:

- Current configured sources.
- Candidate official/company/exchange/public primary-source URLs.
- Optional RSS candidates only if stable and stock-specific filtering is realistic.
- Rejected sources and reasons.
- Access risk notes, including 403/anti-scraping risk if observed.

Use this table shape:

```markdown
| Stock | Source type | URL/feed | Domain | Why useful for this stock report | Risk | Recommendation |
|-------|-------------|----------|--------|----------------------------------|------|----------------|
| 黑芝麻智能 | Official news article | https://www.blacksesame.com/zh/list_10/972.html | blacksesame.com | Primary-source product/safety certification evidence | Jina Reader may include navigation noise | Keep; official seed URL |
```

Recommendation values should be one of:

- `keep`
- `reject`
- `needs-test`

Do not include:

- Search result pages.
- Login/paywall pages.
- Social feeds requiring scraping.
- Xueqiu detail pages.
- Generic portals unless they resolve to stable official article pages.

If you use local public-web research, record the accessed URLs in the inventory. Do not use logged-in browser state.

### Task 2: Smoke Script

Create:

```text
scripts/smoke_agent_reach.py
```

Expected behavior:

- CLI shape:

```text
python3 scripts/smoke_agent_reach.py --stock 黑芝麻智能
python3 scripts/smoke_agent_reach.py --stock 黑芝麻智能 --write-audit
python3 scripts/smoke_agent_reach.py --stock 黑芝麻智能 --json
```

- Load `config/stocks.json`.
- Find the target stock by `name`.
- Build a minimal `SkillContext` containing:
  - `stock_name`
  - `stock_codes`
  - `date_str`
  - `enable_agent_reach`
  - `agent_reach_urls` when configured
  - `agent_reach_official_domains` when configured
  - `agent_reach_rss_feeds` when configured
  - `agent_reach_rss_filter_terms` when configured
- Run only:
  - `agent_reach_query_skill`
  - `agent_reach_fetch_skill`
  - `agent_reach_quality_skill`
- Print compact status by default:
  - stock
  - enabled
  - query count
  - fetch status
  - quality status
  - keep/demote/discard/total
  - warnings
  - top result URLs and actions
- `--json` prints compact JSON to stdout.
- `--write-audit` writes the existing `agent_reach_run_summary` to:

```text
reports/<stock_name>_<date_str>_agent_reach_smoke.json
```

- The script must not import or instantiate:
  - `PerStockReporter`
  - `ZhihuCollector`
  - `KnowledgeSynthesizer`
  - PDF export
  - full report assembly

Use only standard library plus existing project modules.

### Task 3: Tests

Write failing tests first.

Add or update tests proving:

1. Smoke script config loading:
   - finds 黑芝麻智能
   - maps `web_urls` to `agent_reach_urls`
   - maps `official_domains` to `agent_reach_official_domains`
   - does not enable Agent-Reach for unrelated stocks

2. Smoke script isolation:
   - does not import/instantiate `PerStockReporter`
   - does not import/instantiate `ZhihuCollector`
   - does not import/instantiate `KnowledgeSynthesizer`
   - does not import PDF export or full report assembly

3. Smoke script output:
   - mocked Agent-Reach skills produce compact text or JSON status
   - `--write-audit` writes compact audit JSON with no full `content`

4. Config scope:
   - any new `agent_reach` changes remain scoped to 黑芝麻智能
   - no other configured stock gains `agent_reach.enabled=true`

5. Failure handling:
   - mocked web failure or fetch `error` still produces status output and does not crash

Recommended test files:

```text
tests/reporter/test_agent_reach_smoke_script.py
tests/reporter/test_agent_reach_source_config.py
```

### Task 4: Optional Config Update

Only after source inventory and smoke tests:

- Keep existing 黑芝麻智能 `agent_reach` config.
- Add new URLs only if they are recommended `keep` and pass smoke validation.
- Do not add config for any other stock.
- RSS should remain opt-in. Add RSS only if the inventory explicitly recommends it and filtering terms are stock-specific.

If newly discovered URLs have not been smoke-tested successfully, leave them in the inventory as `needs-test` rather than adding them to `config/stocks.json`.

## Required Test Commands

Run focused tests:

```bash
python3 -m pytest tests/reporter/test_agent_reach_smoke_script.py tests/reporter/test_agent_reach_source_config.py -q
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/reporter/test_agent_reach_connector.py tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_stock_reporter_agent_reach_config.py -q
```

If those pass, run the smoke script locally:

```bash
python3 scripts/smoke_agent_reach.py --stock 黑芝麻智能 --json
python3 scripts/smoke_agent_reach.py --stock 黑芝麻智能 --write-audit
```

Do not run a full report unless the smoke validation passes.

If you do run a full report, use the single-stock fast-test entry:

```bash
cd scripts && python3 run_黑芝麻智能.py --fast-test
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260613.md
```

## Notes Output

Write:

```text
docs/agent_workflow/2026-06-13-agent-reach-source-expansion-claude-notes.md
```

Include:

- Files changed.
- Source inventory summary.
- Whether any new URL/feed was added to config and why.
- Smoke script output summary.
- Tests run with exact results.
- Whether full report was run.
- Generated audit paths.
- Deviations from task.
- Blockers.

## Stop Conditions

Stop and report if:

- You need to touch synthesis, scoring, technical analysis, or Xueqiu/CDP code.
- You need automatic search or social scraping.
- Source inventory cannot find any stable official/public source beyond existing URLs.
- Smoke validation fails for all candidate sources.
- Focused tests expose broad unrelated failures.

