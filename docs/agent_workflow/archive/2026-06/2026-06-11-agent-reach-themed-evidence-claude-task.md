# Claude Implementation Task: Agent-Reach Phase 3B Themed Evidence

Implement Phase 3B exactly as specified in:

`docs/agent_workflow/2026-06-11-agent-reach-themed-evidence-design.md`

## Goal

Upgrade the existing Agent-Reach evidence section from raw keep/demote tables into a
theme-grouped, report-native evidence review section. This remains display-only.

## Scope

Allowed files:

- Modify `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
- Modify `tests/reporter/test_agent_reach_evidence_renderer.py`
- Write notes to `docs/agent_workflow/2026-06-11-agent-reach-themed-evidence-claude-notes.md`

Avoid modifying unless a test proves it is necessary:

- `scripts/utils/report_skills/assembly_skills.py`
- `scripts/utils/reporter/sections/__init__.py`
- `tests/reporter/test_assembly_skills.py`

Do not modify:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/source_adapter.py`
- `scripts/utils/report_skills/agent_reach_quality_skill.py`
- `scripts/utils/reporter/scoring_engine.py`
- Any entry script such as `scripts/xueqiu_monitor_v2.py` or `scripts/run_*.py`
- Xueqiu / Playwright / CDP fetchers
- Generated reports, caches, PDFs, images, or raw data

## Required Behavior

### Topic Classification

Add a pure standalone helper in
`scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`:

```python
def classify_agent_reach_topic(item, quality_result=None) -> str:
    ...
```

Return topic keys:

- `product_progress`
- `customer_orders`
- `competition`
- `earnings_business`
- `market_sentiment`
- `to_verify`

Use title + content + quality reasons text.

Topic order must be fixed:

1. `product_progress`
2. `customer_orders`
3. `competition`
4. `earnings_business`
5. `market_sentiment`
6. `to_verify`

First matching topic wins. Example: an item containing both `量产` and `营收` must return
`product_progress`.

Keyword signals:

- `product_progress`: 产品, 芯片, 量产, 交付, 出货, 良率, 产能, 版本, 发布
- `customer_orders`: 客户, 定点, 订单, 合作, 供应商, 主机厂, 比亚迪, 理想, 蔚来, 小鹏
- `competition`: 竞争, 对手, 同业, 替代, 英伟达, 高通, 地平线, Mobileye
- `earnings_business`: 财报, 营收, 收入, 利润, 毛利率, 指引, 同比, 环比, 亏损
- `market_sentiment`: 热度, 讨论, 舆情, 关注, 投资者, 机构, 评级, 观点

Add a short code comment near these keyword lists:

```python
# Some customer/competitor names are stock-centric for the first pass.
# Future phases can derive them from COMPETITOR_MAP / INDUSTRY_MAP or stock config.
```

### Render Shape

Keep:

```markdown
## Agent-Reach 外部证据观察

> 本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。
```

Replace raw `高优先级证据` and `低优先级观察` tables with:

```markdown
### 本期外部证据概览

- 高优先级证据：N 条；低优先级观察：M 条；已过滤：K 条
- 主要主题：产品/量产进展、客户/定点/订单
- 检索状态：ok；质量门：ok

### 主题化证据观察

#### 产品/量产进展

| 时间 | 证据摘要 | 来源 | 质量 | 链接 |
|------|----------|------|------|------|
...

### 待人工复核线索

> 以下信息相关性或证据密度较弱，仅作为后续人工核查线索，不构成事实确认。
```

Rules:

- Keep items render under detected topic headings.
- Demote items render only under `待人工复核线索`.
- Discard items never render.
- Overview `主要主题` includes only non-empty keep-item topics.
- If no keep topics match, keep fallback items render under `#### 待核查线索`.
- Preserve caps: max 6 keep items, max 4 demote items.
- Preserve disabled/skipped/error default silence.
- Preserve `empty` status note.
- Preserve `(title, source, url)` quality-result lookup.
- Preserve missing quality fallback: score `—`, reasons `未评分`.
- Preserve Markdown `|` escaping.
- Preserve 120-character truncation and URL rendering.

## Tests

Use TDD: add failing tests first, run them, then implement.

Add or update tests in `tests/reporter/test_agent_reach_evidence_renderer.py` for:

1. `classify_agent_reach_topic()` returns `product_progress` for `量产`.
2. It returns `customer_orders` for `客户` / `定点` / `订单`.
3. It returns `competition` for competitor keywords.
4. It returns `earnings_business` for `营收` / `财报` / `利润`.
5. It returns `market_sentiment` for `舆情` / `关注`.
6. It returns `to_verify` for no keyword match.
7. Classification priority: item containing both `量产` and `营收` returns
   `product_progress`.
8. `quality_result["reasons"]` contributes to classification when title/content do not.
9. Rendered output contains `本期外部证据概览`.
10. Rendered output contains `主题化证据观察`.
11. Keep item with `量产` appears under `产品/量产进展`.
12. Keep fallback item appears under `待核查线索`.
13. Demote item appears under `待人工复核线索`, not under keep topic headings.
14. Overview `主要主题` excludes demote-only topics.
15. Old raw headings `### 高优先级证据` and `### 低优先级观察` are not rendered.
16. Existing regressions still pass: disabled/skipped/error empty output, empty note,
   discard hidden, out-of-sync quality result fallback, Markdown pipe escaping, empty
   publish time, caps, and truncation.

Run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py -q
python3 -m pytest tests/reporter/test_assembly_skills.py tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q
```

## Notes File

After implementation, write:

`docs/agent_workflow/2026-06-11-agent-reach-themed-evidence-claude-notes.md`

Include:

- Files changed
- Tests run and exact results
- Any deviations from the design
- Confirmation that forbidden files were not modified
- Any blockers

## Guardrails

- Do not run real Agent-Reach searches.
- Do not run browser, PDF export, Playwright, or CDP.
- Do not alter LLM prompts, synthesis, or scoring.
- Do not commit generated artifacts.
- Keep wording evidence-oriented; the section must not imply verified facts or investment
  conclusions.
