# Agent-Reach Phase 3B Themed Evidence Design

> **Date**: 2026-06-11
> **Owner**: Codex
> **Status**: Ready to implement

---

## 1. Goal

Improve the Agent-Reach evidence section so it feels like a report-native evidence review
area instead of a raw external-search table pasted into the middle of the report.

Phase 3B should keep the current safety boundary:

- No LLM synthesis.
- No scoring impact.
- No change to `SynthesisSkill` or `KnowledgeSynthesizer`.
- No real Agent-Reach searches in tests.
- No changes to Xueqiu / CDP / browser collection.

The user-visible outcome should be a themed "外部证据观察" section that groups keep/demote
items by business topic and starts with a compact summary of what was found.

---

## 2. Non-Goals

- Do not summarize evidence with an LLM.
- Do not rewrite the deep-analysis section.
- Do not place Agent-Reach evidence inside LLM narrative paragraphs.
- Do not change Agent-Reach fetch, adapter, or quality scoring logic.
- Do not modify `scoring_engine.py`, technical analysis, price target logic, risk scoring,
  or entry scripts.
- Do not add images, charts, dashboard UI, or PDF-specific layout changes.
- Do not render discarded items.

---

## 3. Current Behavior

`AgentReachEvidenceRenderer` currently renders:

```markdown
## Agent-Reach 外部证据观察

> 本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。

**检索状态**: ok | **质量门**: keep 2 / demote 1 / discard 3

### 高优先级证据

| # | 时间 | 来源 | 标题/摘要 | 质量分 | 依据 | 链接 |

### 低优先级观察

| # | 时间 | 来源 | 标题/摘要 | 质量分 | 依据 | 链接 |
```

This is safe, but visually and narratively abrupt. It does not explain the evidence shape
before listing individual rows.

Relevant files:

- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- `tests/reporter/test_agent_reach_evidence_renderer.py`
- `scripts/utils/report_skills/assembly_skills.py`
- `tests/reporter/test_assembly_skills.py`

---

## 4. Recommended Approach

Upgrade the existing `AgentReachEvidenceRenderer` rather than adding a new renderer.

The renderer should classify each keep/demote item into deterministic topics, then render:

1. The same safety disclaimer.
2. A compact "本期外部证据概览" summary.
3. A topic-grouped evidence table.
4. A small "待人工复核" subsection for demote items or unmatched/weak evidence.

### Alternatives Considered

1. **Recommended: deterministic thematic grouping inside the existing renderer**
   - Lowest risk.
   - Keeps Phase 3 evidence section boundary intact.
   - Makes the report easier to read without LLM.

2. **Fold Agent-Reach items into `DeepAnalysisRenderer` subsections**
   - Smoother narrative, but higher coupling with LLM synthesis and citations.
   - Easy to confuse external evidence with synthesized conclusions.

3. **LLM summary of keep items**
   - Most readable, but premature.
   - Requires new anti-fabrication prompt design and user sample-output review.

---

## 5. Topic Classification

Add deterministic classification helpers inside
`scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`.

Recommended public-ish pure helper:

```python
def classify_agent_reach_topic(item, quality_result=None) -> str:
    ...
```

Topic labels:

| Topic Key | Display Label | Keyword Signals |
|-----------|---------------|-----------------|
| `product_progress` | 产品/量产进展 | 产品, 芯片, 量产, 交付, 出货, 良率, 产能, 版本, 发布 |
| `customer_orders` | 客户/定点/订单 | 客户, 定点, 订单, 合作, 供应商, 主机厂, 比亚迪, 理想, 蔚来, 小鹏 |
| `competition` | 竞争对手动态 | 竞争, 对手, 同业, 替代, 英伟达, 高通, 地平线, Mobileye |
| `earnings_business` | 财报/业绩线索 | 财报, 营收, 收入, 利润, 毛利率, 指引, 同比, 环比, 亏损 |
| `market_sentiment` | 市场反馈/舆情变化 | 热度, 讨论, 舆情, 关注, 投资者, 机构, 评级, 观点 |
| `to_verify` | 待核查线索 | fallback topic |

Rules:

- Use title + content + quality reasons text.
- First matching topic wins in the order above.
- Classification must be pure and deterministic.
- Missing title/content/reasons must not raise.
- Do not infer facts beyond keyword matching.
- Some company names in the first keyword pass are stock-centric for 黑芝麻智能 and
  automotive semiconductor research. Keep a code comment near the keyword list noting that
  future phases should derive competitor/customer names from `COMPETITOR_MAP` /
  `INDUSTRY_MAP` or stock-specific config.
- Multi-topic conflicts are resolved by the fixed topic order. For example, an item
  containing both `量产` and `营收` must classify as `product_progress`.

---

## 6. Output Design

Keep the top-level heading:

```markdown
## Agent-Reach 外部证据观察
```

Keep the disclaimer exactly:

```markdown
> 本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。
```

Replace the abrupt tables with this shape:

```markdown
### 本期外部证据概览

- 高优先级证据：3 条；低优先级观察：2 条；已过滤：4 条
- 主要主题：产品/量产进展、客户/定点/订单、竞争对手动态
- 检索状态：ok；质量门：ok

### 主题化证据观察

#### 产品/量产进展

| 时间 | 证据摘要 | 来源 | 质量 | 链接 |
|------|----------|------|------|------|
| 2026-06-10 | 黑芝麻智能量产... | AgentReach(twitter) | 72 / 包含股票名称; 有URL | 原文 |

#### 客户/定点/订单

...

### 待人工复核线索

> 以下信息相关性或证据密度较弱，仅作为后续人工核查线索，不构成事实确认。
```

Rendering rules:

- Keep items render under their detected topic.
- Demote items render under `待人工复核线索`, optionally with a topic label column.
- The overview `主要主题` bullet should list only non-empty keep-item topics. Do not include
  demote-only topics there, to avoid overstating weak signals.
- Discard items never render.
- If all items classify as `to_verify`, still render a readable `待核查线索` topic.
- Preserve caps: max 6 keep items, max 4 demote items.
- Keep markdown escaping, 120-character truncation, URL behavior, and missing-quality
  metadata fallback from Phase 3.
- Do not show "高优先级证据" and "低优先级观察" as raw table headings anymore unless Claude
  finds a compelling reason to keep them.

---

## 7. Data Contract

Inputs remain unchanged:

- `agent_reach_enabled`
- `agent_reach_status`
- `agent_reach_quality_status`
- `agent_reach_quality_summary`
- `agent_reach_keep_items`
- `agent_reach_demote_items`
- `agent_reach_quality_results`

No new pipeline keys should be required.

The existing `(title, source, url)` quality-result lookup must be preserved. If a result is
missing:

- score renders as `—`
- reasons render as `未评分`

---

## 8. Files Expected To Change

| File | Change Type | Reason |
|------|-------------|--------|
| `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py` | Modify | Add deterministic topic classification and grouped rendering |
| `tests/reporter/test_agent_reach_evidence_renderer.py` | Modify | Add classification and grouped-output tests |

Optional only if needed:

| File | Change Type | Reason |
|------|-------------|--------|
| `docs/agent_workflow/2026-06-11-agent-reach-themed-evidence-claude-notes.md` | Add | Implementation notes |

Files that should not need changes:

- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/utils/reporter/sections/__init__.py`
- `tests/reporter/test_assembly_skills.py`

If Claude finds these need changes, it must explain why in notes before/while implementing.

---

## 9. Files That Must Not Change

| File/Area | Reason |
|-----------|--------|
| `scripts/utils/report_skills/synthesis_skills.py` | Agent-Reach must not enter synthesis |
| `scripts/utils/knowledge_synthesizer.py` | LLM integration is reserved for a later user-reviewed phase |
| `scripts/utils/source_adapter.py` | Adapter contract is unchanged |
| `scripts/utils/report_skills/agent_reach_quality_skill.py` | Quality scoring is unchanged in this phase |
| `scripts/utils/reporter/scoring_engine.py` | Evidence display must not affect scoring |
| Entry scripts | Existing usage remains unchanged |
| Xueqiu / Playwright / CDP fetchers | Out of scope |

---

## 10. Acceptance Gates

Focused tests:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_assembly_skills.py tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

Required behaviors:

- Default/disabled reports still render no Agent-Reach section.
- `empty` status still renders the existing empty note.
- Keep item with `量产` renders under `产品/量产进展`.
- Keep item with `客户` / `定点` / `订单` renders under `客户/定点/订单`.
- Keep item with competitor keywords renders under `竞争对手动态`.
- Keep item with `营收` / `财报` / `利润` renders under `财报/业绩线索`.
- Item containing both `量产` and `营收` classifies as `产品/量产进展`.
- `quality_result["reasons"]` contributes to classification when title/content lack topic
  keywords.
- Item with no topic keywords renders under `待核查线索`.
- Overview `主要主题` lists keep-item topics only, not demote-only topics.
- Weak/demote item renders under `待人工复核线索`.
- Discard item does not render.
- Quality metadata lookup still works when results are out of sync.
- Markdown `|` escaping and 120-character truncation still work.
- No protected files are modified.

Manual review:

- Read the rendered Markdown and confirm the section reads like evidence review, not an
  investment conclusion.
- Confirm it does not imply the evidence has been verified as fact.

---

## 11. Claude Review Log

### Round 1 Feedback

- Claude status: Ready to implement.
- Resolved: upgrading the existing `AgentReachEvidenceRenderer` is the correct boundary.
- Resolved: deterministic topic classification is sufficient for this display-only phase.
- Resolved: topic order is appropriate for automotive-semiconductor research because
  operational evidence comes before financial and market signals.
- Resolved: demote items should stay in one `待人工复核线索` bucket rather than being promoted
  into theme sections.
- Low: some keywords are 黑芝麻智能-centric and should be documented as a first pass.
- Low: add explicit classification-order tests.
- Low: overview `主要主题` should include only keep-item topics.

### Codex Response To Round 1

- Accepted. Added stock-centric keyword limitation and future config note to Section 5.
- Accepted. Added multi-topic conflict behavior and tests to Sections 5 and 10.
- Accepted. Locked `主要主题` to keep-item topics only.
- Accepted. Added quality-reason classification and `to_verify` fallback test requirements.

### Final Implementation Readiness

Ready to implement Phase 3B.
