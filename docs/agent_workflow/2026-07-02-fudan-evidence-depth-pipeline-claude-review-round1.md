# Claude Review Round 1 — 复旦微电 Evidence Depth Pipeline

请在 `/Users/erichan/testsnow` 仓库中做一次只读设计审查，不要改代码、不要运行外部采集、不要启动 Chrome/CDP/Playwright。

## 需要阅读

1. `docs/agent_workflow/2026-07-02-fudan-evidence-depth-pipeline-design.md`
2. `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design.md`
3. `scripts/utils/knowledge_synthesizer.py`
4. `scripts/utils/report_skills/synthesis_skills.py`
5. `scripts/utils/reporter/sections/deep_analysis_renderer.py`
6. `scripts/utils/curated_external_full_body_viewpoint_claims.py`
7. `scripts/utils/social_viewpoint_source_packets.py`
8. `scripts/utils/report_quality.py`
9. 视需要抽读相关 tests，但不要运行完整报告入口。

## 审查目标

这不是审查单份报告怎么改，而是审查 pipeline 设计是否能防止下一只股票复发同类问题：

- 4.1 有材料但空泛，产品/同行/供应链分析没有硬证据；
- 4.2 重复核心事实数字，缺少年报/季报解释；
- 4.3 没有真实资金面信息；
- 4.4 过度压缩外部好文，丢掉数字、假设、推理链；
- LLM 可能把多跳行业逻辑编造成公司直接受益；
- 社媒/知乎/微信材料可能越界进入 4.1-4.3。

## 重点问题

请重点回答：

1. `formal_financial_explanation_pack` 是否与现有年报全文/结构化事实链路兼容？是否会误把风险提示、模板化文字当成业绩变化原因？
2. `peer_business_comparison_pack` 是否能补足 4.1 的产品/同行基本面对比？confidence、source_refs、usage 设计是否足够防止无支撑“优于/劣于/领先/落后”？
3. 4.4 保真展示是否会违反版权/过度引用风险？`source_excerpt`、`reasoning_steps`、`numbers_used` 的边界是否够清楚？
4. 多跳产业链逻辑的处理是否足够安全？有没有路径会让 “存储涨价 -> 晶圆产能紧张 -> CIS 排产减少 -> CIS 涨价” 这类链条进入 canonical 4.1-4.3？
5. `fundflow_material_pack` 是否应该先做成 deterministic summary，还是让 LLM 直接消费 `资金流向` items 就足够？
6. 新增空泛度 quality warnings 是否可测试？会不会误杀正常研报表达？
7. 实施顺序 D → A → B → C → E 是否合理？哪些批次需要再拆？
8. 哪些文件/测试必须纳入实现任务，避免实现时只改 prompt、不改材料生产者？

## 输出格式

请写入：

`docs/agent_workflow/2026-07-02-fudan-evidence-depth-pipeline-claude-review-round1-notes.md`

按以下结构输出：

```markdown
# Evidence Depth Pipeline Review Round 1

## Verdict

verdict: ok | needs_revision | blocked

一句话总结。

## Findings

### Blocker

- B1: ...
  - Evidence:
  - Why it matters:
  - Required change:

### Must-Fix

- MF1: ...
  - Evidence:
  - Why it matters:
  - Required change:

### Nice-to-have

- N1: ...

## Batch Split Recommendation

- Batch D:
- Batch A:
- Batch B:
- Batch C:
- Batch E:

## LLM Hallucination Risk

- Highest-risk path:
- Existing guard:
- Missing guard:

## Test Coverage Gaps

- ...

## Implementation Readiness

recommend_implementation: yes | no | partial

If partial, list exactly which batches can start.

## Git Status

Report `git status --short` and confirm no code/report files were modified.
```

## 禁止事项

- 不要修改任何代码、配置、报告、测试。
- 不要运行主报告入口。
- 不要访问外部网站。
- 不要抓雪球/知乎/微信。
- 不要启动 Chrome/CDP/Playwright。
