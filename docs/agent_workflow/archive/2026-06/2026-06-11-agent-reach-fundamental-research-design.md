# Agent-Reach Fundamental Research Integration Design

> **Date**: 2026-06-11
> **Owner**: Codex
> **Status**: Under Claude Review

---

## 1. Goal

Integrate Agent-Reach as an optional fundamental-research enrichment layer for the A/H stock report pipeline. The first implementation slice should collect and normalize project/product/competitor intelligence from external search tools, but it must not change final investment conclusions, scoring, or LLM synthesis prompts until the collected data is proven reliable.

The user-visible outcome for phase 1 is:

- Existing report entry points still work when Agent-Reach is not installed.
- When explicitly enabled, the pipeline can generate search queries, call local Agent-Reach-like CLIs with strict timeouts, normalize results into `SynthesisItem`, and store those results in `SkillContext` for later review/synthesis phases.
- Reports can show a clear data-availability note, but do not yet add fabricated project-intelligence narrative.

---

## 2. Non-Goals

- Do not modify `KnowledgeSynthesizer` prompts in phase 1.
- Do not add a sixth synthesis theme in phase 1.
- Do not modify `scoring_engine.py`, technical-analysis algorithms, or risk scoring.
- Do not fetch Xueqiu detail pages or control logged-in Chrome/CDP.
- Do not make Agent-Reach mandatory for report generation.
- Do not rewrite the report pipeline or remove existing entry points.
- Do not commit generated reports, cache files, or raw search outputs unless a test fixture explicitly needs them.

---

## 3. Current Context

| Area | Current Behavior | Relevant Files |
|------|------------------|----------------|
| Pipeline assembly | Fixed skill order: data loading -> quality gate -> consolidation -> quote/competitor/technical -> synthesis -> scoring -> charts -> assembly | `scripts/utils/report_skills/__init__.py` |
| Source normalization | `adapt_all()` converts Xueqiu/Zhihu/reports/announcements/fundflow/news/wechat to `SynthesisItem` | `scripts/utils/source_adapter.py` |
| Quality gate | `quality_gate_skill()` calls `ContentQualityGate.process_xueqiu_posts(all_posts)` and returns `keep_posts`/`demote_posts`/`discard_posts` as raw Xueqiu dicts | `scripts/utils/report_skills/data_skills.py`, `scripts/utils/content_quality_gate.py` |
| Synthesis | `SynthesisSkill` adapts current sources and calls `KnowledgeSynthesizer.synthesize()` for five existing themes | `scripts/utils/report_skills/synthesis_skills.py`, `scripts/utils/knowledge_synthesizer.py` |
| Deep analysis rendering | Renders core facts, 4.1 industry logic, 4.2 earnings/valuation, 4.3 funding/catalysts, citations | `scripts/utils/reporter/sections/deep_analysis_renderer.py` |
| Prior spec | Full Agent-Reach design proposes query generation, CLI fetching, new adapters, quality gate expansion, sixth theme, renderer additions | `docs/superpowers/specs/2026-06-10-agent-reach-fundamental-research-design.md` |

---

## 4. Proposed Design

### 4.1 Implementation Strategy

Implement in four small phases. Phase 1 is the only phase to implement after this design review; later phases need separate review because they touch prompts/report narrative.

| Phase | Scope | Risk | Acceptance |
|-------|-------|------|------------|
| 1 | Optional query generation + CLI fetching + `SynthesisItem` adapters + context plumbing | Low/medium | No Agent-Reach installed = no failure; enabled mock CLI returns normalized items |
| 2 | Generic quality gate for `SynthesisItem` and Agent-Reach result filtering | Medium | Noise is filtered without breaking Xueqiu quality behavior |
| 3 | Report-visible project-intelligence summary section without changing `KnowledgeSynthesizer` prompt | Medium/high | Section lists sourced items/timeline only; no unsupported LLM claims |
| 4 | Optional LLM synthesis prompt/theme integration | High | Requires user sample-output review and citation traceability |

### 4.2 Phase 1 Components

| Component | Responsibility | Inputs | Outputs |
|-----------|----------------|--------|---------|
| `agent_reach_query_skill.py` | Produce deterministic search queries with optional LLM/cache later | `stock_name`, `code`, industry/competitors if available | `search_queries`, `agent_reach_status` |
| `agent_reach_skill.py` | Check enablement, run local CLI commands safely, parse JSON/JSONL, dedupe by URL | `search_queries`, env/config | `agent_reach_items`, status/warnings |
| Agent-Reach adapters | Normalize Twitter/Reddit/Bilibili/Wechat/Xiaohongshu raw records | raw dicts | `SynthesisItem` |
| Pipeline integration | Insert optional skills after the existing Xueqiu quality gate and before cross-source consolidation | `SkillContext` | context values available downstream |

### 4.3 Feature Flag

Agent-Reach must be disabled by default.

Suggested config:

- Env var: `ENABLE_AGENT_REACH=1`
- Builder flag: `build_stock_report_pipeline(enable_agent_reach: bool = False)`
- Optional runtime/context override inside the skill is allowed only for focused tests; normal entry points should rely on the builder flag or env var.

If neither is set, the new skills should:

- set `agent_reach_enabled = False`
- set `agent_reach_items = []`
- set `agent_reach_status = "disabled"`
- return quickly without subprocess calls

Default compatibility requirement:

- `build_stock_report_pipeline()` must keep the existing 11-skill default pipeline.
- `build_stock_report_pipeline(enable_agent_reach=True)` may return the optional 13-skill pipeline with Agent-Reach query/fetch skills inserted after `quality_gate_skill`.
- Existing entry points do not need to pass `enable_agent_reach` in phase 1.

### 4.4 Data Flow

```text
data_loading_skill
  -> quality_gate_skill
  -> agent_reach_query_skill
      -> search_queries
  -> agent_reach_fetching_skill
      -> raw platform records
      -> platform adapters
      -> agent_reach_items: list[SynthesisItem]
  -> existing quality/synthesis/report pipeline
```

Phase 1 must not feed `agent_reach_items` into `KnowledgeSynthesizer` by default. Store them only on `ctx` as output values. Do not write them into `stock_raw` and do not mutate caller-provided `raw_data`.

### 4.5 CLI Execution Rules

- Use `subprocess.run()` with list arguments, never shell strings.
- Per command timeout: 30 seconds.
- Per stock total wall-clock budget: 60 seconds. Stop launching new CLI calls after the deadline and return items collected so far.
- Global result cap per stock: 100 items.
- Per query/platform cap: 10 items.
- Deduplicate by canonical URL; if URL is missing, dedupe by `(platform, title, publish_time)`.
- Parse both JSON lines and JSON array output.
- Never call external CLI when disabled.
- Missing CLI, timeout, or non-zero exit should produce warnings/status but not fail the report.
- Status values should be explicit: `"disabled"` when the feature is off, `"missing_binary"` when enabled but no CLI command is available, `"timeout"` for deadline/timeouts, `"error"` for parse/non-zero failures, and `"ok"` when items are collected successfully.
- Phase 1 should serialize CLI calls or use explicitly bounded concurrency. Do not spawn unbounded platform/query subprocesses.

### 4.6 Query Generation Rules

Phase 1 should avoid adding a new LLM dependency if possible. Start with deterministic templates:

- `{stock_name} 产品进展`
- `{stock_name} 量产`
- `{stock_name} 客户 定点`
- `{stock_name} 竞争对手`
- `{stock_name} 财报 业绩`
- competitor-aware queries when `COMPETITOR_MAP` has entries

LLM query generation and 7-day query cache can be implemented in a later phase after CLI integration is proven. If Claude strongly recommends including cache now, it must remain deterministic-testable and not require an LLM in tests.

Expose deterministic query generation as a pure function:

```python
generate_agent_reach_queries(stock_name: str, code: str = "", competitors: list[str] = None) -> list[dict]
```

The function must not read environment variables, call LLMs, or run subprocesses.

---

## 5. Files Expected To Change In Phase 1

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/utils/report_skills/agent_reach_query_skill.py` | Add | Generate deterministic search query specs |
| `scripts/utils/report_skills/agent_reach_skill.py` | Add | Optional CLI runner, parser, dedupe, status handling |
| `scripts/utils/source_adapter.py` | Modify | Add Agent-Reach platform adapters and `agent_reach_items` support in `adapt_all()` |
| `scripts/utils/report_skills/__init__.py` | Modify | Insert optional query/fetch skills after `quality_gate_skill` |
| `tests/reporter/test_agent_reach_skills.py` | Add | Unit tests for disabled mode, CLI parsing, timeout/failure, dedupe |
| `tests/utils/test_source_adapter.py` | Modify/Add | Adapter contract tests for platform records, including missing-field records |
| `tests/reporter/test_pipeline_integration.py` or focused contract test | Modify/Add | Existing pipeline works with Agent-Reach disabled; optional pipeline has expected additional skills |

---

## 6. Files That Must Not Change In Phase 1

| File/Area | Reason |
|-----------|--------|
| `scripts/utils/knowledge_synthesizer.py` | Prompt changes require separate review and user sample confirmation |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | Narrative/report-structure changes belong to phase 3 |
| `scripts/utils/reporter/scoring_engine.py` | Agent-Reach should not alter scores before data is validated |
| `scripts/utils/reporter/technical_analyzer.py` and technical modules | Out of scope |
| Entry scripts such as `scripts/run_黑芝麻智能.py` and `scripts/xueqiu_monitor_v2.py` | Existing user entry points must remain stable |
| Xueqiu Playwright/CDP fetchers | No new Xueqiu detail-page collection |

---

## 7. Data And Reporting Constraints

- Agent-Reach output is external web/social content and must be treated as lower-confidence unless it comes from official accounts or primary sources.
- Every normalized item must preserve `source_platform`, `author`, `title`, `url`, `publish_time`, `interaction_score`, and raw metadata in `extra`.
- Do not invent dates, authors, URLs, or engagement metrics.
- If raw content is missing, skip the item unless a title/summary field has usable text; do not fabricate body text.
- Missing `url`, missing/unparseable `publish_time`, missing `interaction_score`, and unknown author must not raise adapter exceptions. Preserve blanks/defaults and raw metadata in `extra`.
- The report must continue when Agent-Reach is disabled, missing, times out, or returns invalid JSON.
- Any future LLM synthesis of Agent-Reach data must use explicit anti-fabrication instructions and citation traceability.

---

## 8. Acceptance Gates For Phase 1

### Focused Tests

```bash
python3 -m pytest tests/reporter/test_agent_reach_skills.py tests/utils/test_source_adapter.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py -q
```

### Behavioral Checks

- With Agent-Reach disabled/default, pipeline output has `agent_reach_items == []` and no subprocess calls.
- With Agent-Reach disabled/default, pipeline output has `agent_reach_status == "disabled"` so later renderers can distinguish disabled from failed/empty states.
- `build_stock_report_pipeline()` returns the existing 11-skill default pipeline; `build_stock_report_pipeline(enable_agent_reach=True)` returns the optional Agent-Reach pipeline.
- With `enable_agent_reach=True` and mocked CLI output, normalized `SynthesisItem` objects are produced.
- With `enable_agent_reach=True` and missing CLI binary, pipeline output has `agent_reach_status == "missing_binary"` and continues.
- CLI failures/timeouts do not fail the pipeline.
- A mocked slow/many-query run respects the 60-second per-stock deadline and returns partial results/status.
- `adapt_all(agent_reach_items=[...])` handles missing URL, missing publish time, missing interaction score, and empty content without raising.
- Existing report generation entry points remain import-compatible.

### Report Generation

Phase 1 does not require a real external Agent-Reach run. A normal sample report should still generate with Agent-Reach disabled. If local Claude Code can run a sample report cheaply, use:

```bash
cd scripts
python run_黑芝麻智能.py
```

Then run:

```bash
python3 scripts/check_report_quality.py reports/黑芝麻智能_20260611.md
```

### Manual Review

- Confirm no external network/browser/Xueqiu detail-page access was introduced.
- Confirm no prompt or scoring changes occurred.
- Confirm Agent-Reach status/warnings are visible in context/logs for later renderer use.

---

## 9. Open Questions

| Question | Owner | Decision |
|----------|-------|----------|
| Which exact local CLI names are installed for Agent-Reach on the user's machine? | User/Claude | Pending; phase 1 should make commands configurable/test-mocked |
| Should Agent-Reach real outputs be stored in `data/raw/` or kept only in memory for now? | User/Codex | Decided for phase 1: keep only in `ctx`; raw persistence later |
| Should the pipeline builder expose `enable_agent_reach`? | Codex/Claude | Decided: yes, add `build_stock_report_pipeline(enable_agent_reach: bool = False)` and preserve 11-skill default |
| Should missing CLI be distinct from disabled? | Codex/Claude | Decided: yes, use `agent_reach_status = "missing_binary"` when enabled but unavailable |
| Should Bilibili use `yt-dlp` immediately or wait until text extraction quality is understood? | Codex/Claude | Recommend optional platform, disabled if binary missing |
| Should phase 3 add a separate “项目动态” section or fold sourced bullets into existing “资金面与催化剂”? | User/Codex | Pending after phase 1 data review |

---

## 10. Claude Review Log

### Round 1 Feedback

- Claude status: Ready with changes.
- High: original insertion point after `data_loading_skill` could bypass existing Xueqiu-only quality gate if Agent-Reach items later flowed downstream.
- Medium: writing to `stock_raw["agent_reach"]` could mutate caller-provided `raw_data`.
- Medium: adapters need malformed/missing-field tests.
- Medium: per-command timeout alone does not bound total wall-clock time.
- Low: disabled status should be explicit; query skill name should be Agent-Reach-specific; pipeline skill count tests need updating.

### Codex Response To Round 1

- Accepted. Phase 1 now inserts after `quality_gate_skill`, stores only on `ctx`, does not feed Agent-Reach items into synthesis, and prohibits `stock_raw` mutation.
- Accepted. Added 60-second per-stock total budget and bounded/serialized subprocess requirement.
- Accepted. Renamed query module to `agent_reach_query_skill.py` and required a pure `generate_agent_reach_queries()` function.
- Accepted. Added adapter tests for missing URL, publish time, interaction score, and empty content.
- Accepted. Added explicit `agent_reach_status == "disabled"` acceptance and pipeline skill-count/update expectations.

### Round 2 Feedback

- Claude status: Ready to implement.
- Guardrails added by Claude:
  1. Do not modify `SynthesisSkill._build_synthesis_items()` in phase 1.
  2. Do not mutate `stock_raw` or `raw_data`; use `ctx.set()`/`ctx.get()` only.
  3. Preserve the existing 11-skill default pipeline.
  4. Agent-Reach adapters must use `.get("field", "")` or equivalent defaults for required string fields.
  5. Disabled skills must return quickly without subprocess, network, or LLM calls.
  6. Keep renderers, scoring, technical analyzer, and entry scripts untouched.
- Open decisions resolved by Codex:
  - Add `build_stock_report_pipeline(enable_agent_reach: bool = False)` and keep the default at 11 skills.
  - Use `agent_reach_status = "missing_binary"` when enabled but no CLI binary is available.

### Final Implementation Readiness

- Ready to implement phase 1.
