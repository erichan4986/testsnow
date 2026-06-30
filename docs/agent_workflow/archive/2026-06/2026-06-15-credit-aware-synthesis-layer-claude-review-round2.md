# Claude Review Round 2 Prompt — Credit-Aware Synthesis Layer

请把下面 prompt 交给 Claude Code，在 `/Users/erichan/testsnow` 仓库中执行第二轮设计审查。

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库中做 Round 2 设计审查，不要修改源码。

目标：
审查 docs/agent_workflow/2026-06-15-credit-aware-synthesis-layer-design.md，重点确认 Round 1 的两个 blocker 是否已被设计层面解决：

1. 新闻/研报/社区来源不能再通过 provenance enrichment 被标为 supported core fact。
2. corroborated_discussion 不再被 Phase 1 当成现有 claim verification schema 的可用 bucket。

请重点检查：
- Phase 1 是否明确包含 deterministic core fact provenance hard filter。
- hard filter 的允许/拒绝来源家族是否足够清晰。
- `derive_synthesis_usage()` fallback mapping 是否覆盖现有 SynthesisItem adapter 来源。
- legacy `.chat(prompt)` 路径是否被纳入同样信用规则。
- verified discussion 是否强制显式写成“社区讨论线索已与...相互印证”等字样。
- 中信用新闻/研报是否只允许进入风险观察文字，不允许影响风险评分或结构化风险信号。
- corroborated_discussion 是否只作为 Phase 1 禁用规则/术语存在，真正 schema 扩展是否被推迟到 Phase 2。
- 测试计划是否足以防止 core facts / citation / risk scoring 污染。

禁止事项：
- 不要修改源码。
- 不要运行 LLM。
- 不要访问外部网络。
- 不要生成报告。
- 不要修改 knowledge/、reports/、data/raw/。

输出要求：
把反馈追加到 docs/agent_workflow/2026-06-15-credit-aware-synthesis-layer-design.md 的 `## Round 2 Feedback` 小节。

反馈格式：
- Status: Ready to implement / Must-fix before task / Blocked
- Remaining blockers
- Required task adjustments
- Missing tests
- Final recommendation

停止条件：
- 如果 hard filter 仍不充分，标为 Must-fix before task。
- 如果设计仍要求 Phase 1 使用不存在的 `corroborated` schema，标为 Must-fix before task。
- 如果实现必须修改 scoring_engine.py、技术算法或采集逻辑才能成立，标为 Blocked。
```
