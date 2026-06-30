# Agent-Reach Phase 3 Evidence Renderer Design

> **Date**: 2026-06-11
> **Owner**: Codex
> **Status**: Ready to implement

---

## 1. Goal

Add a small report-visible evidence section for vetted Agent-Reach results. Phase 3 should
make filtered external research visible to the user so the user can judge whether the
sources are useful enough for later LLM synthesis.

This phase is intentionally a display layer only:

- Render `agent_reach_keep_items` and selected `agent_reach_demote_items`.
- Show traceable metadata: source platform, publish time, title, short excerpt, quality
  score/reasons, URL.
- Do not generate new analytical conclusions.
- Do not feed Agent-Reach content into `KnowledgeSynthesizer`.
- Do not affect stock scoring, risk scoring, technical conclusions, or existing entries.

---

## 2. Non-Goals

- Do not modify `KnowledgeSynthesizer`, its prompts, citation generation, or theme list.
- Do not modify `SynthesisSkill._build_synthesis_items()`.
- Do not pass Agent-Reach records into `adapt_all()` from synthesis.
- Do not modify `scoring_engine.py`, technical analysis, price target logic, or risk scoring.
- Do not run real Agent-Reach searches in tests.
- Do not render discarded items in the report.
- Do not add chart generation, images, or PDF-specific layout logic in this phase.
- Do not modify Xueqiu Playwright/CDP collection.

---

## 3. Current Context

| Area | Current Behavior | Relevant Files |
|------|------------------|----------------|
| Phase 1 fetch | Optional Agent-Reach query/fetch skills produce `agent_reach_items`, status, warnings. | `scripts/utils/report_skills/agent_reach_query_skill.py`, `scripts/utils/report_skills/agent_reach_skill.py` |
| Phase 2 quality | Deterministic quality gate produces keep/demote/discard lists and compact audit results. | `scripts/utils/report_skills/agent_reach_quality_skill.py` |
| Report assembly | Markdown sections are assembled from `ReportAssemblySkill.RENDERERS`. HTML dashboard is separate. | `scripts/utils/report_skills/assembly_skills.py` |
| Existing deep analysis | LLM synthesis and citations are rendered by `DeepAnalysisRenderer`. | `scripts/utils/reporter/sections/deep_analysis_renderer.py` |

---

## 4. Recommended Approach

Use a new standalone Markdown section renderer:

`scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`

Insert it into `ReportAssemblySkill.RENDERERS` after `deep_analysis` and before `risk`.
This keeps the external evidence near the fundamental narrative but visually separate from
the risk section and final warnings.

Do not modify the HTML dashboard in Phase 3. The Markdown output is the source that matters
for PDF and detailed review; adding dashboard cards would be a separate UI pass.

### Alternatives Considered

1. **Recommended: separate evidence section**
   - Lowest coupling.
   - Clear to users that Agent-Reach is raw external evidence, not a synthesized conclusion.
   - Easy to test with a small renderer contract.

2. **Fold bullets into `DeepAnalysisRenderer`**
   - Looks integrated, but risks confusing raw evidence with LLM narrative.
   - Increases chance future prompt changes accidentally consume Agent-Reach content.

3. **Append only to citation list**
   - Traceable, but too hidden; user cannot judge content quality from citations alone.

---

## 5. Output Design

Renderer heading:

```markdown
## Agent-Reach 外部证据观察
```

Intro note:

```markdown
> 本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。
```

When quality status is usable:

```markdown
**检索状态**: ok | **质量门**: keep 2 / demote 1 / discard 3
```

Keep table:

```markdown
### 高优先级证据

| # | 时间 | 来源 | 标题/摘要 | 质量分 | 依据 | 链接 |
|---|------|------|-----------|--------|------|------|
| 1 | 2026-06-10 | AgentReach(twitter) | 黑芝麻智能量产进展... | 72 | 包含股票名称；有URL | 原文 |
```

Demote table:

```markdown
### 低优先级观察

> 以下信息相关性或证据密度较弱，仅作后续人工复核线索。
```

Only render:

- up to 6 keep items
- up to 4 demote items
- no discard items

When Agent-Reach is enabled but has no usable result, render a short status note. When
Agent-Reach is disabled or no quality skill ran, return an empty string so default reports
do not gain noise.

Implementation decision after Round 1 review:

- Disabled, skipped, missing-binary, and error-only states return `""`.
- Enabled with `agent_reach_quality_status == "empty"` renders a short note:
  `> Agent-Reach 未检索到可用外部证据。`
- Caps stay as module constants: `MAX_KEEP_ITEMS = 6`, `MAX_DEMOTE_ITEMS = 4`.

---

## 6. Data Contract

Inputs from `SkillContext`:

- `agent_reach_enabled`
- `agent_reach_status`
- `agent_reach_quality_status`
- `agent_reach_quality_summary`
- `agent_reach_keep_items`
- `agent_reach_demote_items`
- `agent_reach_quality_results`
- `agent_reach_warnings`

Renderer rules:

- Treat all keys as optional.
- Accept both dict-like ctx and `SkillContext`.
- Never mutate lists or item objects.
- Escape Markdown table separators (`|`) in title, excerpt, source, reasons.
- Truncate excerpts to a fixed length, suggested 120 Chinese characters.
- Convert missing `publish_time`, `url`, `author`, `interaction_score`, or `extra.raw` to display-safe blanks.
- If URL is present, render `[原文](url)`; otherwise render `—`.
- Reasons come from `agent_reach_quality_results` when available; if missing, render
  score as `—` and reasons as `未评分`.
- Do not rely on list-index alignment between `agent_reach_quality_results` and
  `agent_reach_keep_items` / `agent_reach_demote_items`. Build a lookup dictionary keyed
  by `(title, source, url)`, where `source` maps to `item.source_platform`.
- For reason lists, escape each reason and join with `; ` so Markdown table columns stay
  stable.
- `required_keys()` should be permissive: return
  `["agent_reach_enabled", "agent_reach_quality_status"]` or an empty list. The renderer
  itself must handle disabled/empty states explicitly.

---

## 7. Header Data Source

Update `ReportAssemblySkill._data_sources()` to append `Agent-Reach外部检索` only when:

- `agent_reach_enabled` is true, and
- `agent_reach_quality_status == "ok"`, and
- `agent_reach_keep_items` or `agent_reach_demote_items` is non-empty.

Do not list Agent-Reach as a data source when disabled, skipped, empty, missing binary, or
error-only.

---

## 8. Files Expected To Change

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` | Add | Render filtered Agent-Reach evidence as Markdown |
| `scripts/utils/reporter/sections/__init__.py` | Modify | Export renderer if this package already exports renderers |
| `scripts/utils/report_skills/assembly_skills.py` | Modify | Add renderer to `RENDERERS` and data-source header logic |
| `tests/reporter/test_agent_reach_evidence_renderer.py` | Add | Renderer contract tests |
| `tests/reporter/test_assembly_skills.py` | Modify | Ordering and data-source header tests |

---

## 9. Files That Must Not Change

| File/Area | Reason |
|-----------|--------|
| `scripts/utils/report_skills/synthesis_skills.py` | Agent-Reach must not enter synthesis in Phase 3 |
| `scripts/utils/knowledge_synthesizer.py` | LLM integration is reserved for a later user-reviewed phase |
| `scripts/utils/source_adapter.py` | Phase 1 adapter contract is enough |
| `scripts/utils/report_skills/agent_reach_quality_skill.py` | Phase 2 quality behavior should remain stable unless tests expose a bug |
| `scripts/utils/reporter/scoring_engine.py` | Evidence display must not affect scoring |
| Entry scripts | Existing usage remains unchanged |
| Xueqiu fetchers / Playwright / CDP | Out of scope |

---

## 10. Acceptance Gates

Focused tests:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

Required behaviors:

- Disabled/default reports do not show the Agent-Reach evidence section.
- Enabled reports with keep items show `Agent-Reach 外部证据观察`.
- Demote items render under `低优先级观察`, not mixed with keep items.
- Discard items never render.
- Section includes quality score and compact reasons.
- Section includes source, publish time, short excerpt, and URL when present.
- Markdown table pipes in text are escaped.
- Quality results can be out of sync with item lists; unmatched items render with
  placeholder score/reasons instead of raising.
- Long content is truncated.
- Empty `publish_time` renders as `—`.
- `agent_reach_quality_status == "skipped"` returns an empty string.
- `agent_reach_quality_status == "empty"` renders the short enabled-but-empty note.
- Header data source includes Agent-Reach only when usable items exist.
- `SynthesisSkill`, `KnowledgeSynthesizer`, and `scoring_engine.py` remain untouched by this phase.

Manual review:

- Read generated Markdown around the new section and confirm wording does not imply these
  items are confirmed facts or investment conclusions.
- If a sample report is generated locally, confirm PDF image/layout changes are not part of
  this phase.

---

## 11. Claude Review Log

### Round 1 Feedback

- Claude status: Ready to implement.
- Resolved: standalone `AgentReachEvidenceRenderer` is the correct boundary and avoids
  coupling raw external evidence with LLM narrative.
- Resolved: inserting after `deep_analysis` and before `risk` is appropriate.
- Medium: renderer must handle `agent_reach_quality_results` being out of sync with
  keep/demote item lists.
- Medium: `required_keys()` should be permissive, with disabled/empty behavior handled
  inside the renderer.
- Low: reason lists should be escaped item-by-item and joined with `; `.
- Low: `sections/__init__.py` must explicitly import/export the new renderer.

### Codex Response To Round 1

- Accepted. Section 6 now requires a `(title, source, url)` lookup and placeholder
  `—` / `未评分` when quality metadata is missing.
- Accepted. `required_keys()` is now specified as permissive.
- Accepted. Added tests for out-of-sync quality results, Markdown pipe escaping,
  empty publish time, skipped state, and empty state.
- Accepted. `sections/__init__.py` is already listed in expected file changes.
- Decision: keep caps hard-coded as `MAX_KEEP_ITEMS = 6` and `MAX_DEMOTE_ITEMS = 4`.
- Decision: disabled/skipped/error states are silent; enabled-empty state renders a short
  note.

### Final Implementation Readiness

Ready to implement Phase 3.
