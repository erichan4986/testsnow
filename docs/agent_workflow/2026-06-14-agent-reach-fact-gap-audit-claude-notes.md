# Claude Notes: Agent-Reach Fact Gap Audit

## Summary

Added a read-only "核心事实缺口观察" subsection to the Agent-Reach evidence renderer. It compares kept Agent-Reach evidence topics against the existing `core_facts` table and highlights possible coverage gaps for human review. It does not affect scoring, risk, technical analysis, LLM synthesis, numbered citations, or final recommendations.

## Files Changed

- `scripts/utils/reporter/sections/agent_reach_evidence_renderer.py`
  - Added `MAX_FACT_GAP_OBSERVATIONS = 4`.
  - Added `_build_core_fact_topic_coverage(core_facts)` to scan `fact` and `data` fields using the existing `_TOPIC_KEYWORDS`.
  - Added `_render_fact_gap_audit(gap_topics, keep_by_topic)` to render the new subsection.
  - Wired the gap audit into `render()` between the overview and themed evidence.
- `tests/reporter/test_agent_reach_evidence_renderer.py`
  - Extended `_make_ctx()` to accept `core_facts`.
  - Added 6 focused tests for the new gap audit behavior.
  - Updated existing six-item Black Sesame test to count themed evidence rows separately from gap rows.

## Files Not Changed

- No changes to `KnowledgeSynthesizer`, synthesis prompts, citation parsing, scoring, risk, technical analysis, EV, position sizing, or report pipeline order.
- No changes to `knowledge/`, `data/raw/`, or generated report outputs.
- No external network, browser, CDP, or Xueqiu detail fetching.

## Tests Run

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py -q
```

```text
37 passed in 0.15s
```

Optional broader run:

```bash
python3 -m pytest tests/reporter/test_agent_reach_evidence_renderer.py tests/reporter/test_assembly_skills.py -q
```

```text
46 passed in 32.90s
```

## New Tests Added

- `test_fact_gap_subsection_renders_for_uncovered_topic` — gap renders when a keep item topic is absent from `core_facts`.
- `test_fact_gap_subsection_absent_when_topic_covered` — no gap when `core_facts` covers the topic.
- `test_demote_items_do_not_create_fact_gaps` — demoted items never create gap rows.
- `test_fact_gap_disclaimer_present` — output contains the read-only, non-impact disclaimer.
- `test_fact_gap_has_no_numbered_citations` — gap subsection emits no `[^N]` markers.
- `test_fact_gap_rows_capped_at_four` — at most four gap observations are rendered, one per uncovered topic.

## Rendered Subsection Sample

Input: one kept Agent-Reach item about chip mass production, empty `core_facts`.

```markdown
## Agent-Reach 外部证据观察

> 本节仅展示外部检索证据，不参与综合评分、风险评分或 LLM 深度分析结论。

### 本期外部证据概览

- 高优先级证据：1 条；低优先级观察：0 条；已过滤：0 条
- 主要主题：产品/量产进展
- 检索状态：ok；质量门：ok

### 核心事实缺口观察

> 以下仅提示外部证据与核心事实基座之间的覆盖差异，不构成事实确认，也不影响评分或结论。

| 主题 | 外部证据提示 | 当前状态 | 建议动作 |
|------|--------------|----------|----------|
| 产品/量产进展 | 黑芝麻智能量产进展 — 芯片量产良率达到95% | 核心事实基座未覆盖该主题 | 人工复核是否需要补充事实基座 |

### 主题化证据观察

#### 产品/量产进展

| 时间 | 证据摘要 | 来源 | 质量 | 链接 |
|------|----------|------|------|------|
| 2026-06-10 | 黑芝麻智能量产进展 — 芯片量产良率达到95% | AgentReach(twitter) | 70 /  | [原文](http://a) |
```

## Deviations From Task

- None. The implementation stays within the allowed files and constraints.

## Blockers

- None.

## Notes

- The gap audit is intentionally topic-based rather than item-based: if multiple keep items share the same uncovered topic, only one observation is emitted. This avoids redundant rows and keeps the audit concise.
- The subsection is placed before "主题化证据观察" so readers see the coverage cue before the detailed evidence table.
- All wording uses conservative audit language ("提示", "未覆盖", "人工复核"), consistent with the design doc.
