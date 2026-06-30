# Agent-Reach Phase 3B Sample Report Claude Notes

## Status

Accepted with noted limitation

## Files Changed

- None (validation task only)

## Validation Artifacts

- Markdown sample path: `/tmp/phase3b_sample/黑芝麻智能_20260611.md`
- Agent-Reach section snippet: `/tmp/phase3b_sample/agent_reach_section.md`
- PDF sample path: `/tmp/phase3b_sample/黑芝麻智能_20260611.pdf`

## Markdown Review

- **Section placement**: `## Agent-Reach 外部证据观察` appears after `## 四、深度分析` and before `## 行业特有风险因子评估`. Correct.
- **Old headings absent**: `### 高优先级证据` and `### 低优先级观察` are not present. Correct.
- **New headings present**:
  - `### 本期外部证据概览` present.
  - `### 主题化证据观察` present.
  - Topic subheadings present: `#### 产品/量产进展`, `#### 财报/业绩线索`, `#### 待核查线索` (3 topics).
  - `### 待人工复核线索` present for demote items.
- **Overview topics**: `主要主题` lists `产品/量产进展、财报/业绩线索、待核查线索`. Only keep-item topics are included; demote-only topics are excluded. Correct.
- **Disclaimer**: Visible and unchanged: `本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。`
- **Wording**: Demote subsection includes `以下信息相关性或证据密度较弱，仅作为后续人工核查线索，不构成事实确认。` No verified-fact implication.
- **Table readability**: Markdown tables render with standard pipe formatting. No excessive width issues.
- **Pipe escaping**: Title `比亚迪|理想定点黑芝麻智驾方案` correctly escaped as `比亚迪\|理想定点黑芝麻智驾方案`.
- **Truncation**: Sample content did not exceed 120-char excerpt limit; truncation code path is covered by existing tests.

## PDF Review

- PDF export succeeded via `scripts/utils/pdf_exporter.py` (Playwright + Chromium).
- Output file size: 1.0 MB (6 pages), indicating full content rendered.
- Page 3 screenshot confirms:
  - Section heading and disclaimer render clearly.
  - Overview bullet list renders correctly.
  - Table header row (`时间 | 证据摘要 | 来源 | 质量 | 链接`) is visible and aligned.
  - No obvious table overflow or clipping around the Agent-Reach section.
- Full per-page table content screenshot was limited by PDF viewer DOM accessibility, but no layout regressions were observed.

## Tests

| Command | Result |
|---------|--------|
| `python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py -q` | 26 passed |
| `python3 -m pytest tests/reporter/test_assembly_skills.py tests/reporter/test_pipeline_integration.py tests/reporter/test_synthesis_skills.py -q` | 15 passed |

No regressions.

## Issues Found

1. **Keyword overlap causing misclassification (limitation, not blocking)**
   - Item `比亚迪|理想定点黑芝麻智驾方案` (keep) was classified into `产品/量产进展` instead of `客户/定点/订单` because its content contains `交付`, which is a `product_progress` keyword.
   - Item `黑芝麻智能 vs 地平线：智驾芯片格局分析` (keep) was classified into `产品/量产进展` instead of `竞争对手动态` because its title contains `芯片`, which matches the `product_progress` keyword list before `competition` is evaluated.
   - **Impact**: `客户/定点/订单` and `竞争对手动态` do not appear in the overview `主要主题` or as separate topic tables, even though relevant keep items exist.
   - **Assessment**: This is a known limitation of the deterministic "first match wins" keyword classification. The Round 1 design review explicitly accepted this tradeoff for Phase 3B. No source change is recommended at this stage.

## Recommended Follow-Ups

- In a future phase, consider refining the `_TOPIC_KEYWORDS` lists or making them stock-configurable (as already noted in the source comment referencing `COMPETITOR_MAP` / `INDUSTRY_MAP`).
- Consider whether `交付` should remain in `product_progress` or be moved to `customer_orders`, since delivery timelines are often mentioned in customer-order news.
- No code changes required for Phase 3B closure.
