# Source Intake v2 Claude Implementation Task

Date: 2026-06-14

## Context

Read first:

- `docs/agent_workflow/2026-06-14-source-intake-v2-design.md`
- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/report_skills/evidence_note_skill.py`
- `scripts/utils/stock_reporter.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/evidence_note_writer.py`

Round 1 design review is complete. Status is **Ready to implement**, with two required implementation constraints:

1. `evidence_note_writer_skill` currently has a hard Agent-Reach gate. Remove or relax it so evidence notes can be written from Source Intake items even when Agent-Reach is disabled.
2. A-stock / akshare dependencies must be lazy-imported. Disabled Source Intake must not import or call akshare.

## Goal

Implement Source Intake v2 Phase 1 as a structured A-share intake path beside Agent-Reach:

```text
a_stock_source_intake
  -> source_intake_merge
  -> evidence_note_writer
  -> existing claim verification / official fact summary / risk bridge
```

This phase must make cninfo announcements, Eastmoney stock news, and Eastmoney research report rows available as source-credit tagged evidence notes. It must not add a new report renderer or modify LLM prompts.

## Allowed Files

You may create:

- `scripts/utils/a_stock_source_intake.py`
- `scripts/utils/report_skills/a_stock_source_intake_skill.py`
- `scripts/utils/report_skills/source_intake_merge_skill.py`
- `scripts/smoke_source_intake.py`
- `tests/utils/test_a_stock_source_intake.py`
- `tests/reporter/test_a_stock_source_intake_skill.py`
- `tests/reporter/test_source_intake_merge_skill.py`
- `tests/reporter/test_source_intake_smoke_script.py`
- `tests/reporter/test_stock_reporter_source_intake_config.py`
- `docs/agent_workflow/2026-06-14-source-intake-v2-claude-notes.md`

You may modify:

- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/report_skills/evidence_note_skill.py`
- `scripts/utils/stock_reporter.py`
- `tests/reporter/test_pipeline_integration.py`
- `tests/reporter/test_evidence_note_skill.py`
- `tests/reporter/test_stock_reporter_agent_reach_config.py`
- related focused tests if existing expectations need updating for the new feature flags

Do not modify unless Codex explicitly approves:

- `config/stocks.json`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/*`
- `scripts/xueqiu_monitor_v2.py`
- `knowledge/**`
- `data/raw/**`
- `reports/**`

## Required Behavior

### 1. New A-Stock Source Intake Helper

Create a pure helper module that exposes deterministic, testable functions. Suggested API:

```python
def collect_a_stock_source_items(
    *,
    stock_name: str,
    stock_code: str,
    config: dict,
    today: date | None = None,
) -> dict:
    ...
```

The return value should be a structured dict, for example:

```python
{
    "status": "ok",
    "items": [SynthesisItem(...), ...],
    "source_statuses": {
        "cninfo_announcements": {"status": "ok", "count": 3, "error": ""},
        "eastmoney_stock_news": {"status": "empty", "count": 0, "error": ""},
        "eastmoney_research_reports": {"status": "error", "count": 0, "error": "..."},
    },
    "warnings": [],
}
```

Requirements:

- No module-level `import akshare`.
- Lazy-import akshare inside the functions that actually call it.
- If akshare is missing, a function is missing, or an adapter raises, return a structured per-source `error` or `unsupported_function`; do not raise out of the helper.
- Disabled sources return status `disabled`.
- Empty sources return status `empty`.
- Adapter failures for one source must not block other sources.

### 2. Source-Specific Rules

#### cninfo announcements

Use akshare with the current compatible market:

```python
ak.stock_zh_a_disclosure_report_cninfo(
    symbol=stock_code,
    market="沪深京",
    start_date="YYYYMMDD",
    end_date="YYYYMMDD",
)
```

Rules:

- Test must prove `market="沪深京"` is passed.
- Filter by stock code/name when columns allow it.
- Use title/date/url columns defensively. Common column names include `公告标题`, `公告时间`, `公告链接`, but code must tolerate alternatives.
- Keep configured categories when provided.
- Cap to `max_items`.
- Convert to `SynthesisItem` with:
  - `source_platform="公告"` or a stable equivalent
  - `extra.source_credit=95`
  - `extra.source_type="exchange_announcement"`
  - `extra.source_domain="cninfo.com.cn"`
  - `extra.verification_status="confirmed_fact"`
  - `extra.knowledge_eligible=True`
  - `extra.report_eligible=True`
  - raw metadata preserved under `extra.raw_metadata` or `extra.raw`
- Do not fetch or parse full PDFs in this phase.

#### Eastmoney stock news

Use `ak.stock_news_em(symbol=stock_code)` if available.

Rules:

- Require a strong stock-name or stock-code match when content/title is available.
- Cap to `max_items`.
- Convert to `SynthesisItem` with:
  - `extra.source_credit=60`
  - `extra.source_type="news"`
  - `extra.source_domain` set to a stable Eastmoney domain label
  - `extra.verification_status="professional_observation"`
  - `extra.knowledge_eligible=True`
  - `extra.report_eligible=True`
- It must not be marked as official/confirmed.

#### Eastmoney research reports

Use an existing stable akshare/report API path if already available in the repo, or wrap the known a-stock-data compatible path behind a lazy function. Do not add a new heavy dependency.

Rules:

- Cap to `max_items`.
- Convert to `SynthesisItem` with:
  - `extra.source_credit=65`
  - `extra.source_type="research_report"`
  - `extra.verification_status="professional_observation"`
  - `extra.knowledge_eligible=True`
  - `extra.report_eligible=True`
- Preserve rating, EPS, target-price, institution and report date as metadata if present.
- Do not download research PDFs by default.

#### Eastmoney global news

Default disabled. If implemented, require strict stock name/code filtering and cap to 5. It may return `disabled` in Phase 1 if no stable path is implemented.

### 3. Source Intake Skill

Create `a_stock_source_intake_skill`.

It should:

- Read:
  - `source_intake_enabled`
  - `source_intake_config`
  - `stock_name`
  - `stock_codes`
- If disabled, set:
  - `source_intake_status="disabled"`
  - `source_intake_items=[]`
  - `source_intake_summary={"status": "disabled", ...}`
- If enabled, call the helper and set:
  - `source_intake_status`
  - `source_intake_items`
  - `source_intake_summary`
  - `source_intake_error` if applicable
- Never call LLM, browser, CDP, Xueqiu, or Zhihu.

### 4. Source Intake Merge Skill

Create `source_intake_merge_skill`.

It should normalize available external evidence into merged buckets:

- `external_evidence_keep_items`
- `external_evidence_demote_items`
- `external_evidence_discard_items`
- `source_intake_summary`

Inputs:

- Existing Agent-Reach buckets:
  - `agent_reach_keep_items`
  - `agent_reach_demote_items`
  - `agent_reach_discard_items`
- New Source Intake items:
  - `source_intake_items`

Rules:

- URL-dedupe across Agent-Reach and Source Intake.
- Prefer the item with higher `extra.source_credit`.
- If credits tie, prefer Source Intake for structured official cninfo rows.
- Keep high-credit and medium-credit Source Intake items in `external_evidence_keep_items` if `extra.report_eligible` or `extra.knowledge_eligible` is true.
- Preserve Agent-Reach backward compatibility.
- The skill should be cheap and deterministic.

### 5. Evidence Note Writer Gate

Update `evidence_note_writer_skill`.

New rule:

- If `enable_evidence_notes` is false: `disabled`.
- If merged `external_evidence_keep_items` / `external_evidence_demote_items` exist or merged keys are present, use them.
- Else fall back to existing Agent-Reach buckets and existing `agent_reach_quality_status` behavior.
- Do not require `agent_reach_enabled=True` when merged external evidence exists.
- Do not mutate input lists.

This is required for:

```text
Agent-Reach disabled + Source Intake enabled + evidence notes enabled
```

### 6. Pipeline Wiring

Update `build_stock_report_pipeline` with a new flag:

```python
enable_source_intake: bool = False
```

Required deterministic order:

```text
data_loading
quality_gate
agent_reach_query/fetch/quality          # only if enable_agent_reach
a_stock_source_intake                    # only if enable_source_intake
source_intake_merge                      # if enable_agent_reach or enable_source_intake
evidence_note_writer                     # if enable_evidence_notes and (enable_agent_reach or enable_source_intake)
cross_source_consolidation
quote_fetching
competitor_fetching
technical_fetching
technical_analysis
synthesis
claim_risk_signal                        # if enabled
scoring
charts
assembly
```

Expected skill counts:

- default: 11
- Agent-Reach only: 15 if merge is included, or keep existing count only if merge is intentionally skipped for AR-only compatibility. State the final decision in notes and tests.
- Source Intake only: base + `a_stock_source_intake` + `source_intake_merge` = 13, plus evidence note writer if enabled = 14
- Agent-Reach + Source Intake + evidence notes + claim risk signals: deterministic and covered by tests

Prefer including `source_intake_merge` whenever either external source path is enabled, because it gives one stable evidence writer surface.

### 7. PerStockReporter Config Wiring

Add per-stock `source_intake` config support.

Rules:

- Source Intake config is separate from `agent_reach`.
- Keep existing `agent_reach` config unchanged.
- Existing constructor can either:
  - continue using `agent_reach_configs` as the per-stock external-source config container, reading `source_intake` from the same per-stock dict; or
  - add a clearly named optional `source_intake_configs` parameter if that is cleaner.
- Do not change existing public callers unless tests require it.
- `source_intake.enabled=True` should pass `enable_source_intake=True` into pipeline builder.
- `evidence_notes.enabled=True` should enable evidence notes if either Agent-Reach or Source Intake is enabled.
- `source_intake` config should be passed to ctx as `source_intake_config`.
- Claim verification remains separately controlled by `claim_verification.enabled`.

### 8. Smoke Script

Add:

```text
scripts/smoke_source_intake.py --stock 中简科技 --json
```

Requirements:

- Does not run full report.
- Does not call LLM.
- Does not start Chrome/CDP.
- Does not fetch Xueqiu detail pages.
- Runs only Source Intake helper/skill and merge.
- Prints JSON when `--json` is set.
- Optional `--write-audit --output-dir reports` may write a compact audit JSON without full content.
- If network is unavailable, return source statuses/errors instead of crashing.

### 9. Tests

Use TDD. Write failing tests before implementation.

Required focused tests:

- Source Intake disabled pipeline does not contain source intake skills.
- Source Intake disabled does not import/call akshare.
- Source Intake enabled imports/calls akshare only inside helper execution.
- cninfo adapter calls `market="沪深京"`.
- cninfo rows become high-credit official/exchange `SynthesisItem`.
- Eastmoney stock news rows become medium-credit `professional_observation`.
- Eastmoney research rows become medium-credit `professional_observation`.
- Adapter error for one source does not block other source outputs.
- `source_intake_summary` includes per-source statuses/counts/errors.
- Source Intake only + evidence notes enabled calls `write_evidence_notes` without Agent-Reach.
- Evidence note writer prefers `external_evidence_*` when present.
- Evidence note writer falls back to existing Agent-Reach buckets.
- Merge URL-dedupes Agent-Reach and Source Intake, preferring higher `source_credit`.
- Medium-credit news/research is not marked `confirmed_fact` and has `source_credit < 80`.
- `PerStockReporter` passes `enable_source_intake=True` and `source_intake_config`.
- Default reporter keeps Source Intake disabled.
- Pipeline skill order is deterministic for default, Source Intake only, Agent-Reach only, both enabled, and all enabled with evidence notes / claim risk signals.
- Smoke script AST/import test proves it does not import `PerStockReporter`, `KnowledgeSynthesizer`, `ZhihuCollector`, Playwright, or CDP helpers.

Suggested commands:

```bash
python3 -m pytest \
  tests/utils/test_a_stock_source_intake.py \
  tests/reporter/test_a_stock_source_intake_skill.py \
  tests/reporter/test_source_intake_merge_skill.py \
  tests/reporter/test_evidence_note_skill.py \
  tests/reporter/test_pipeline_integration.py \
  tests/reporter/test_stock_reporter_source_intake_config.py \
  tests/reporter/test_source_intake_smoke_script.py -q
```

Regression commands:

```bash
python3 -m pytest \
  tests/reporter/test_agent_reach_skills.py \
  tests/reporter/test_agent_reach_quality_skill.py \
  tests/reporter/test_claim_risk_signal_skill.py \
  tests/utils/test_claim_verification.py \
  tests/utils/test_evidence_note_writer.py -q
```

Do not run a full report unless Codex or the user asks after implementation review.

## Stop Conditions

Stop and report instead of continuing if:

- You need to modify `config/stocks.json`.
- You need to modify LLM prompts, `KnowledgeSynthesizer`, scoring, EV, technical algorithms, or report renderers.
- You need to fetch Xueqiu detail pages, launch Chrome/CDP, or refresh Zhihu.
- Tests require real network to pass.
- akshare current API shape is incompatible with the design and cannot be isolated behind tests.
- You need to write full PDF body extraction.

## Notes Output

Write:

```text
docs/agent_workflow/2026-06-14-source-intake-v2-claude-notes.md
```

Include:

- Files changed
- Final public API / ctx keys
- Pipeline skill order and counts
- Source-credit mapping table
- Lazy import proof
- Focused test results
- Regression test results
- Any smoke result, if run
- Deviations from this task
- Blockers

## Completion Summary Format

When done, reply with:

- Files changed
- Tests run and results
- Whether akshare is lazy-imported
- Whether Agent-Reach disabled + Source Intake enabled can write evidence notes
- Whether config/knowledge/reports/data/raw were untouched
- Deviations
- Blockers
