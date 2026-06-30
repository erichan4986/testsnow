# Claude Review Round 1 Prompt — Credit-Aware Synthesis Layer

请把下面 prompt 交给 Claude Code，在 `/Users/erichan/testsnow` 仓库中执行设计审查。

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库中做设计审查，不要修改源码。

目标：
审查 docs/agent_workflow/2026-06-15-credit-aware-synthesis-layer-design.md。
重点判断该设计是否能安全地让 KnowledgeSynthesizer 按证据信用分层使用材料：
- 高信用事实可进核心事实
- 中信用来源可参与专业背景分析但不能写成公司确认
- verified/supported discussion 可参与分析观点但必须保留验证状态和推论边界
- 多个低信用来源重复出现的 claim 只能算 corroborated_discussion / 社区共振线索，不能升级为事实确认
- unverified social claim 不得污染核心事实、风险因子、最终建议或编号引用

请重点检查：
1. 是否会破坏现有 citation 机制或 source_refs / core_facts provenance。
2. 是否会让 claim_verification_context 被误当成新的引用来源。
3. 是否会让中信用新闻/研报被 LLM 写成“公司确认”。
4. 是否需要 prompt-only Phase 1 之外的 deterministic guard。
5. `derive_synthesis_usage()` 应放在 KnowledgeSynthesizer 内部还是独立 helper。
6. 是否需要先加 hard filter，避免 core_facts 提取新闻/研报/社区来源。
7. legacy `.chat(prompt)` 路径是否也必须同步相同约束。
8. 测试计划是否覆盖 prompt 顺序、previous narratives、claim verification appendix 和 core facts extraction。
9. corroborated_discussion 的定义是否足够防止“多个低信用来源互相验证”的误用。
10. 如果 claim verification 当前还没有 explicit corroborated 状态，Phase 1 是否应只在 prompt 规则中定义它，还是必须先扩展 plan/schema。

禁止事项：
- 不要修改源码。
- 不要运行 LLM。
- 不要访问外部网络。
- 不要生成报告。
- 不要修改 knowledge/、reports/、data/raw/。

输出要求：
把反馈追加到 docs/agent_workflow/2026-06-15-credit-aware-synthesis-layer-design.md 的 `## Round 1 Feedback` 小节。

反馈格式：
- Status: Ready to implement / Must-fix before task / Blocked
- R2 Needed: Yes/No
- Findings: 按 severity 排序，标注 blocker / medium / low
- Required design deltas
- Missing tests
- Open questions

停止条件：
- 如果你认为设计会导致 LLM 编造事实、引用污染、或评分/风险污染，请标为 Must-fix before task。
- 如果你发现必须修改 scoring_engine.py、技术算法或采集逻辑才能成立，请标为 Blocked。
```
