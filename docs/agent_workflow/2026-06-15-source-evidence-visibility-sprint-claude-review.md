# Claude Review Prompt: Source Evidence Visibility Sprint

Use this prompt for a fast design review. Do not write code.

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做设计快审，不要修改源码。

请阅读：
- docs/agent_workflow/2026-06-15-source-evidence-visibility-sprint-design.md
- scripts/utils/report_skills/source_intake_merge_skill.py
- scripts/utils/report_skills/assembly_skills.py
- scripts/utils/reporter/sections/agent_reach_evidence_renderer.py
- scripts/utils/reporter/sections/deep_analysis_renderer.py

目标：
审查 Source Evidence Visibility Sprint 设计是否足够安全，可以作为一个合并 implementation task 推进。

重点检查：
1. 新 Source Intake 展示层是否可能污染评分、风险、EV、技术面、LLM synthesis 或最终建议。
2. 是否会把 Eastmoney 新闻/券商研报错误渲染成 confirmed_fact 或官方事实。
3. renderer placement 是否合理：deep analysis 后、Agent-Reach/risk 前。
4. 是否已有 ctx 字段足够支撑，不需要改 pipeline 数据流。
5. 是否需要复用 AgentReachEvidenceRenderer，还是应新增独立 SourceIntakeEvidenceRenderer。
6. Verified Claim Summary 是否真的已经存在，只需验收，不需要重做。
7. 缺失的测试、失败模式和 runtime 验收清单。

请把反馈追加到 design 文件末尾，标题为：
## Round 1 Feedback

反馈格式：
- Status: Ready to implement / Must-fix before task
- R2 Needed: Yes/No
- Findings: 按 severity 排序
- Required task adjustments
- Missing tests
- Blocker

禁止事项：
- 不要修改源码。
- 不要运行外部网络、报告生成、Chrome/CDP、雪球详情页。
- 不要改 config/knowledge/reports/data/raw。
```
```
