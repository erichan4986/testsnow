# Claude Review Round 1: Periodic Report LLM Analysis v2

Date: 2026-06-16

## Prompt For Claude Code

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做一次只读设计审查，不要修改源码。

目标：
审查 docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-v2-design.md。

背景：
当前 periodic_report_extractor 依赖较多规则/关键词，面对中简科技年报时能抓到部分产品、客户、研发和财务风险，但用户指出这种方式不适合通用到其他行业。新设计改为：
- 规则只做通用章节/表格 evidence pack
- LLM 负责公司/行业特定分析
- deterministic validator 防止编造数字、实体和事实晋级

请重点审查：
1. 这个 v2 架构是否比继续堆关键词更通用。
2. evidence pack 的 usage 列表是否覆盖 A 股年报/半年报的重要章节和表格。
3. LLM 输出 schema 是否足够支持“市场前景、经营情况、财务风险、研发、客户、capex”等分析。
4. number/entity fidelity validator 是否可实现，是否存在误杀/漏杀风险。
5. 是否应该一通大 prompt，还是拆成 2-3 个 themed LLM calls。
6. Phase A helper-only 的允许文件和禁止事项是否足够安全。
7. 是否有遗漏测试，尤其是发明数字、发明产品/客户名、表格截断、跨证据引用、输出误入核心事实。

禁止事项：
- 不要修改任何源码、测试、配置、报告或 knowledge/data 文件。
- 不要访问外部网络。
- 不要运行 LLM。
- 不要生成报告。
- 不要启动 Chrome/CDP，不要抓雪球详情页。

输出要求：
把反馈追加到 docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-v2-design.md 末尾，标题为：

## Round 1 Feedback

反馈结构：
- Status: Ready to implement / Needs minor fixes / Must-fix before task
- R2 Needed: Yes/No
- Findings by severity
- Required design deltas
- Missing tests
- Open questions
- Final recommendation

如果你认为可以实现，请明确哪些点必须在 implementation task 中落实。
如果你认为不能实现，请列 blocker 和最小修正方案。
```
