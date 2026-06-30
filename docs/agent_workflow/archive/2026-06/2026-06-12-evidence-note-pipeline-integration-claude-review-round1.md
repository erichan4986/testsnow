# Claude Review Round 1: Evidence Note Pipeline Integration Phase 3

请审查以下设计，不要写代码，不要修改源码。

Design file:

`docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-design.md`

背景：

我们已经完成：

1. Source Credit Framework Phase 1
   - `scripts/utils/source_credit.py`
   - `AgentReachAdapter` 给 Agent-Reach `SynthesisItem.extra` 附加 `source_credit`, `source_type`, `knowledge_eligible` 等字段。

2. Evidence Note Writer Phase 2
   - `scripts/utils/evidence_note_writer.py`
   - `write_evidence_notes(...)`
   - 纯模块，不调用网络/LLM/浏览器/subprocess。
   - 单元测试已覆盖 dry-run、真实写入到 `tmp_path`、去重、无 PyYAML fallback。

现在 Phase 3 目标：

把 evidence note writer 以显式开关接入单股深度报告 pipeline，但不进入 `KnowledgeSynthesizer`，不影响报告结论。

请重点审查：

1. Pipeline 插入点是否正确：
   - 设计建议放在 `agent_reach_quality_skill` 之后、`cross_source_consolidation_skill` 之前。

2. 默认行为是否足够安全：
   - 默认 11 skills 不变。
   - `enable_agent_reach=True` 仍为 14 skills。
   - 只有 `enable_agent_reach=True and enable_evidence_notes=True` 时变 15 skills。

3. `PerStockReporter` 配置接入是否合理：
   - 从 `agent_reach_configs[stock]["evidence_notes"]` 读取。
   - 默认 `dry_run=True`。
   - 不强制修改 `config/stocks.json`。

4. ctx 输出字段是否清晰、可测试、可序列化：
   - `evidence_note_status`
   - `evidence_note_write_plan`
   - `evidence_note_summary`
   - `evidence_note_error`

5. writer 出错时是否应该中断 pipeline：
   - 设计建议不阻断，写 `status=error`。
   - 请判断这个策略是否合理，尤其是在 `dry_run=False` 时。

6. 是否有越界风险：
   - 不应修改 `KnowledgeSynthesizer`
   - 不应修改 `SynthesisSkill._build_synthesis_items()`
   - 不应把 evidence notes 传给 LLM
   - 不应修改 scoring/technical/report renderer
   - 不应运行 `xueqiu_monitor_v2.py`

7. 测试计划是否覆盖关键回归：
   - disabled/skipped/empty/dry_run/written/error
   - pipeline 11/14/15 skills
   - `PerStockReporter` config pass-through
   - `tmp_path` 写入，不碰真实 `knowledge/`

请把审查结果写入：

`docs/agent_workflow/2026-06-12-evidence-note-pipeline-integration-claude-notes.md`

输出格式：

```markdown
# Evidence Note Pipeline Integration Review Round 1

## Status

Ready to implement / Ready with changes / Blocked

## Findings

### High
- None if no high-severity findings.

### Medium
- None if no medium-severity findings.

### Low
- None if no low-severity findings.

## Required Changes Before Implementation

- None if no required changes.

## Nice To Have

- None if no nice-to-have suggestions.

## Files Reviewed

- List reviewed files.
```

约束：

- 不写代码。
- 不修改任何 `.py` 文件。
- 不运行报告生成。
- 不运行网络/浏览器/LLM。
- 可以读取相关代码和测试。
