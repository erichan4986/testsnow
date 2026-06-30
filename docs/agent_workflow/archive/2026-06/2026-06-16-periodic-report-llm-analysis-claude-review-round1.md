# Claude Review Round 1 Prompt: Periodic Report LLM Analysis

Please give this prompt to Claude Code.

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做一次设计审查，不要写代码。

目标：
审查 docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-design.md，判断“年报/半年报 deterministic extractor 后接一个 bounded LLM analysis 层”的设计是否安全、可实现、测试充分。

背景：
- 已有 scripts/utils/periodic_report_extractor.py 负责规则摘录年报/半年报。
- 已有 Source Intake 集成将摘录作为 periodic_report_excerpt，source_credit 75，不进核心事实、评分、风险或合成。
- 用户希望年报内部也能用 LLM 做总结提炼，但不希望 LLM 直接读完整年报后编造或把管理层观点升级成确认事实。
- 本设计只讨论 Phase 1：LLM 只总结 extractor 已选摘录，输出 periodic_report_analysis，credit <=75，professional_analysis。

审查范围：
1. 读取设计文档：
   docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-design.md
2. 可按需查看现有实现，但不要修改：
   - scripts/utils/periodic_report_extractor.py
   - scripts/utils/a_stock_source_intake.py
   - scripts/utils/evidence_note_writer.py
   - scripts/utils/report_skills/source_intake_merge_skill.py
   - scripts/utils/reporter/sections/source_intake_evidence_renderer.py
   - tests/utils/test_periodic_report_extractor.py
   - tests/utils/test_a_stock_source_intake.py
   - tests/utils/test_evidence_note_writer.py
   - tests/reporter/test_source_intake_evidence_renderer.py

重点审查：
- LLM 输入是否被足够约束为 extractor items，而不是全文。
- 输出 schema 是否足以防止 confirmed_fact / fact_candidate / core_fact 泄漏。
- source_credit 75 + professional_analysis 的语义是否一致。
- validator 是否覆盖了非法引用、无效 refs、schema mismatch、过长摘要、未知 usage。
- 是否还需要“新数字/新实体”检测，若需要，是 blocker 还是可作为 Phase 1.1。
- 是否应先只做 helper + tests，还是可以加 opt-in CLI --llm-summary。
- 是否存在绕过路径导致 periodic_report_analysis 进入 KnowledgeSynthesizer、risk_score、core_facts、final recommendation。
- 测试计划是否缺漏关键 case。
- allowed files 是否过宽或过窄。

禁止事项：
- 不要修改任何源码、测试、配置、报告、knowledge 或 data/raw。
- 不要访问外部网站。
- 不要运行 LLM。
- 不要跑完整报告。
- 不要启动 Chrome/CDP，不要抓雪球详情页。

请把审查结果追加写入同一个设计文档末尾：
docs/agent_workflow/2026-06-16-periodic-report-llm-analysis-design.md

追加标题：
## Round 1 Feedback

输出格式：
- Status: Ready to implement / Needs minor fixes / Must-fix before task
- R2 Needed: Yes/No
- Findings: 按 severity 排序，给出具体原因和文件/设计章节引用
- Required Deltas: 如果需要设计修正，列出必须改哪些点
- Missing Tests: 列出实现前必须补的 focused tests
- Open Questions: 只列真正会影响实现边界的问题
- 是否建议 Phase 1 加 CLI，还是 helper-only

停止条件：
- 如果你发现必须修改 KnowledgeSynthesizer、scoring_engine.py、risk scoring、technical analysis 或 pipeline 顺序才能成立，请标为 blocker。
- 如果你发现设计会把 LLM 产物升级为核心事实或评分输入，请标为 blocker。
```
