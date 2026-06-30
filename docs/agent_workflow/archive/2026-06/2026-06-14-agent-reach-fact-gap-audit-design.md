# Agent-Reach Fact Gap Audit Design

## Goal

Add a read-only audit inside the single-stock report that compares kept Agent-Reach evidence against the existing core fact base and highlights possible fact-base gaps for human review.

This is not a scoring feature, not LLM synthesis input, and not a new citation source.

## Scope

Target report path: single-stock deep report pipeline.

Primary example stock: 黑芝麻智能 / HK02533.

Allowed behavior:

- Read `agent_reach_keep_items`, `agent_reach_quality_results`, and `core_facts` from the report context.
- Use the existing deterministic Agent-Reach topic classifier.
- Render a small "核心事实缺口观察" subsection inside `## Agent-Reach 外部证据观察`.
- Phrase every row as an audit prompt, not as a confirmed missing fact.

Forbidden behavior:

- Do not mutate `core_facts`.
- Do not add Agent-Reach items to `synthesis`, `citations`, numbered refs, or LLM prompts.
- Do not affect composite score, risk score, technical analysis, EV, position sizing, or final recommendation.
- Do not fetch new external data in tests.
- Do not write `knowledge/`, `data/raw/`, or report outputs from unit tests.

## Recommended Approach

Use a display-only comparator in `agent_reach_evidence_renderer.py`.

Data flow:

1. Build topic coverage from `core_facts` by scanning `fact` and `data` text with the same topic keyword groups used for Agent-Reach evidence.
2. Classify each keep item using `classify_agent_reach_topic()`.
3. If a keep item's topic is not represented in the core fact base, include it as a "possible gap" observation.
4. Limit output to 4 observations.
5. Render the audit before "主题化证据观察" so the reader sees the gap cue before the detailed evidence table.

The output should use conservative wording:

```markdown
### 核心事实缺口观察

> 以下仅提示外部证据与核心事实基座之间的覆盖差异，不构成事实确认，也不影响评分或结论。

| 主题 | 外部证据提示 | 当前状态 | 建议动作 |
|------|--------------|----------|----------|
| 产品/量产进展 | 黑芝麻智能发布新芯片... | 核心事实基座未覆盖该主题 | 人工复核是否需要补充事实基座 |
```

## Failure Modes

- False positive gap: keyword matching misses a semantically related core fact. Mitigation: use "可能/提示/人工复核" wording.
- Official page with navigation noise: rely on existing quality scoring and excerpt cleanup; do not infer beyond title/excerpt.
- Demoted low-quality evidence creating noise: exclude demote items from gap audit for this phase.
- Empty or absent `core_facts`: render at most 4 keep-item gap observations and state this is a coverage prompt, not confirmation.

## Tests

Add focused tests in `tests/reporter/test_agent_reach_evidence_renderer.py`:

- Gap subsection renders when a keep item topic is absent from `core_facts`.
- Gap subsection does not render when `core_facts` already cover that topic.
- Demote-only items do not create fact gap rows.
- The output contains the non-impact disclaimer and does not contain numbered citation markers.
- Gap rows are capped at 4.

## Acceptance

- Focused renderer tests pass.
- Existing Agent-Reach renderer tests pass.
- The generated report still keeps Agent-Reach separate from scoring, synthesis, and numbered citations.
