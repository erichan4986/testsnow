# Agent-Reach Quality Gate Phase 2 Design

> **Date**: 2026-06-11
> **Owner**: Codex
> **Status**: Under Claude Review

---

## 1. Goal

Add a dedicated, deterministic quality gate for Agent-Reach `SynthesisItem` records. Phase 2 should filter noisy social/web results into keep/demote/discard buckets and produce auditable quality metadata, but it must still not feed Agent-Reach data into `KnowledgeSynthesizer`, report renderers, scoring, or investment conclusions.

The user-visible outcome is still mostly invisible in reports: Agent-Reach can be enabled, fetched records can be quality-filtered, and later phases can safely render only the filtered factual candidates.

---

## 2. Non-Goals

- Do not modify `KnowledgeSynthesizer` or any LLM prompt.
- Do not modify `SynthesisSkill._build_synthesis_items()` to pass `agent_reach_items` into `adapt_all()`.
- Do not modify `DeepAnalysisRenderer` or any report section in Phase 2.
- Do not modify `scoring_engine.py`, technical analysis, risk scoring, or entry scripts.
- Do not run real Agent-Reach searches.
- Do not use LLM quality assessment for Agent-Reach in Phase 2.
- Do not change the existing Xueqiu quality gate behavior.

---

## 3. Current Context

| Area | Current Behavior | Relevant Files |
|------|------------------|----------------|
| Agent-Reach fetch | Optional Phase 1 skills produce `ctx.agent_reach_items`, status, warnings. Default pipeline remains 11 skills; enabled pipeline has 13 skills. | `scripts/utils/report_skills/agent_reach_query_skill.py`, `scripts/utils/report_skills/agent_reach_skill.py`, `scripts/utils/report_skills/__init__.py` |
| Agent-Reach normalization | `AgentReachAdapter` converts raw platform records to `SynthesisItem`. | `scripts/utils/source_adapter.py` |
| Existing quality gate | `ContentQualityGate` filters Xueqiu posts and has LLM fallback logic. It is not designed for Agent-Reach social data. | `scripts/utils/content_quality_gate.py`, `scripts/utils/report_skills/data_skills.py` |
| Synthesis | Does not receive Agent-Reach data in Phase 1. This must remain true in Phase 2. | `scripts/utils/report_skills/synthesis_skills.py` |

---

## 4. Proposed Design

### 4.1 Implementation Strategy

Create a new Agent-Reach-specific quality skill:

`scripts/utils/report_skills/agent_reach_quality_skill.py`

It should be inserted only when `enable_agent_reach=True`, after `agent_reach_fetch_skill` and before `cross_source_consolidation_skill`.

Pipeline shape:

```text
Default:
data_loading -> quality_gate -> cross_source_consolidation -> ... -> assembly
11 skills

Agent-Reach enabled:
data_loading
  -> quality_gate
  -> agent_reach_query
  -> agent_reach_fetch
  -> agent_reach_quality
  -> cross_source_consolidation
  -> ...
14 skills
```

Default `build_stock_report_pipeline()` must remain 11 skills.

### 4.2 Components

| Component | Responsibility | Inputs | Outputs |
|-----------|----------------|--------|---------|
| `AgentReachQualityDecision` | Small dataclass/dict-like result for each item | `SynthesisItem`, score, action, reasons | auditable quality metadata |
| `score_agent_reach_item()` | Pure deterministic scoring function | `SynthesisItem`, optional `stock_name`, optional `search_queries` | score/action/reasons |
| `agent_reach_quality_skill` | Classify all `ctx.agent_reach_items` | `agent_reach_items`, `stock_name`, status | keep/demote/discard lists + stats |

### 4.3 Output Contract

The skill should write only to `ctx`:

- `agent_reach_keep_items`: list of `SynthesisItem`
- `agent_reach_demote_items`: list of `SynthesisItem`
- `agent_reach_discard_items`: list of `SynthesisItem`
- `agent_reach_quality_results`: list of serializable dicts with title/source/action/score/reasons/url/fetch_status/quality_status
- `agent_reach_quality_status`: `"disabled" | "skipped" | "ok" | "empty"`
- `agent_reach_quality_summary`: dict with counts

Do not mutate `agent_reach_items`, `stock_raw`, or `raw_data`.

### 4.4 Status Rules

- If Agent-Reach is disabled or no fetch skill ran: `agent_reach_quality_status = "disabled"`.
- If fetch status is `missing_binary`, `error`, or `timeout` with zero items: `agent_reach_quality_status = "skipped"` and all output lists empty.
- If fetch status is `timeout` but partial items exist: score those items and set quality status based on results.
- If `agent_reach_items` is empty: `agent_reach_quality_status = "empty"`.
- If items are scored: `agent_reach_quality_status = "ok"`.

### 4.5 Deterministic Scoring Heuristics

Start with a transparent 0-100 rule score. Suggested weights:

- Relevance to stock/query/product context: 0-25
- Source credibility: 0-25
- Evidence/detail density: 0-20
- Content substance/length: 0-20
- Engagement signal: 0-10

Suggested action thresholds:

- `keep`: score >= 60
- `demote`: score >= 35 and < 60
- `discard`: score < 35

Suggested positive signals:

- Text contains stock name, code, or product/industry terms from generated queries. The skill wrapper should pass `ctx.search_queries` into the pure scorer so query-term relevance stays deterministic and testable.
- Source appears official/verified/primary (`extra.raw.is_official`, `verified`, `account_type == "official"`, `source_type == "official"`).
- Contains dates, percentages, amounts, product keywords, customer/order/launch/mass-production terms.
- Has enough title/content length to inspect.
- Has non-trivial engagement.

Suggested negative signals:

- Empty title/content.
- Stock-price pumping, pure emotion, ad/spam, referral language.
- No relation to stock name/code/query terms.
- Very short content with no metadata.

The score function must return reasons so future report rendering can explain why an item was included or excluded.

### 4.6 Data Shape

Use existing `SynthesisItem` as input. `AgentReachAdapter` stores raw platform data under `item.extra["raw"]`; the quality gate may inspect that metadata but must tolerate missing keys using chained `.get()` access such as `item.extra.get("raw", {}).get("verified", False)`.

`agent_reach_quality_results` should not duplicate full content. Store compact audit metadata and reasons only; full text remains in the original `SynthesisItem` objects in keep/demote/discard lists.

Do not introduce a new dependency.

---

## 5. Files Expected To Change

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/utils/report_skills/agent_reach_quality_skill.py` | Add | Dedicated Agent-Reach quality scoring and skill |
| `scripts/utils/report_skills/__init__.py` | Modify | Insert quality skill only in enabled Agent-Reach pipeline |
| `tests/reporter/test_agent_reach_quality_skill.py` | Add | Unit tests for scoring/status/output contract |
| `tests/reporter/test_pipeline_integration.py` | Modify | Enabled pipeline now has 14 skills and quality skill position |
| `docs/agent_workflow/2026-06-11-agent-reach-quality-gate-claude-notes.md` | Add/append | Implementation notes later |

---

## 6. Files That Must Not Change

| File/Area | Reason |
|-----------|--------|
| `scripts/utils/report_skills/synthesis_skills.py` | Agent-Reach must not enter synthesis in Phase 2 |
| `scripts/utils/knowledge_synthesizer.py` | Prompt changes reserved for Phase 4 |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | Report-visible rendering reserved for Phase 3 |
| `scripts/utils/reporter/scoring_engine.py` | Quality gate must not influence scores yet |
| Entry scripts | Existing user entry points remain stable |
| `data/raw`, `reports`, `knowledge` | No generated artifacts in Phase 2 |
| Xueqiu fetchers / Playwright / CDP | Out of scope |

---

## 7. Data And Reporting Constraints

- Agent-Reach quality filtering is a pre-report safety layer, not an analytical conclusion.
- Do not fabricate missing metadata.
- Do not call LLMs, external websites, browsers, or real CLI searches.
- Keep all output in `ctx`.
- Keep discarded items available in `agent_reach_discard_items` for audit/debugging, but never render them in Phase 2.

---

## 8. Acceptance Gates

### Focused Tests

```bash
python3 -m pytest tests/reporter/test_agent_reach_quality_skill.py tests/reporter/test_agent_reach_skills.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py -q
python3 -m pytest tests/reporter/test_synthesis_skills.py -q
```

### Required Behaviors

- Default pipeline remains 11 skills.
- `build_stock_report_pipeline(enable_agent_reach=True)` returns 14 skills.
- Quality skill appears after `agent_reach_fetch_skill` and before `cross_source_consolidation_skill`.
- Disabled/missing/empty statuses do not raise.
- Official, relevant, evidence-rich item is `keep`.
- Short but somewhat relevant item is `demote`.
- Off-topic or spam/pumping item is `discard`.
- Partial timeout with items still scores those items.
- Partial timeout quality results preserve `fetch_status = "timeout"` while quality status can still be `"ok"` if items were scored.
- `SynthesisSkill` behavior remains unchanged and does not consume `agent_reach_keep_items`.

---

## 9. Open Questions

| Question | Owner | Decision |
|----------|-------|----------|
| Should thresholds be configurable now? | Codex/Claude | Recommend hard-coded constants in Phase 2; config later after real data review |
| Should quality results keep full content? | Codex/Claude | Recommend no: store metadata/reasons only, keep full content in item lists |
| Should discarded Agent-Reach items be persisted? | User/Codex | No in Phase 2; context only |
| Should scorer receive `search_queries`? | Claude/Codex | Yes: skill wrapper passes queries into pure scorer for deterministic query-term relevance |
| Should quality results include fetch status? | Claude/Codex | Yes: include compact `fetch_status` and `quality_status` metadata |

---

## 10. Claude Review Log

### Round 1 Feedback

- Claude status: Ready to implement.
- Resolved: dedicated `agent_reach_quality_skill.py` is the correct boundary and should not pollute existing `ContentQualityGate`.
- Resolved: deterministic 0-100 scoring with explicit thresholds is transparent and testable.
- Resolved: default pipeline remains 11 skills; enabled pipeline becomes 14 skills.
- Resolved: Agent-Reach data remains isolated from `SynthesisSkill`.
- Low recommendations accepted:
  - Pass `search_queries` from the skill wrapper into the pure scorer for relevance matching.
  - Use `.get()` access for all `extra["raw"]` metadata.
  - Keep `agent_reach_quality_results` compact and avoid duplicating full content.
  - Update pipeline tests from 13 to 14 enabled skills.
  - Include fetch status in compact quality audit metadata.

### Codex Response To Round 1

- Accepted all low-severity recommendations and updated Sections 4.2, 4.3, 4.5, 4.6, 8, and 9.

### Round 2 Feedback

- Skipped. Round 1 status was Ready to implement and recommendations were small, non-blocking clarifications.

### Final Implementation Readiness

- Ready to implement Phase 2.
