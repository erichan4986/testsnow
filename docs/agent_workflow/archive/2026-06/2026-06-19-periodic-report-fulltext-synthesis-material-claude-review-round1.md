# Claude Review Round 1 — Periodic Report Fulltext Synthesis Material

你是 Claude Code，在 `/Users/erichan/testsnow` 仓库里做只读设计审查。

## 目标

审查以下设计是否足够安全、可实现：

`docs/agent_workflow/2026-06-19-periodic-report-fulltext-synthesis-material-design.md`

核心意图：让年报/半年报 fulltext material 可选进入最终 LLM 主题叙事 synthesis，但仍不得进入核心事实、评分、风险评分或 Knowledge 写入。

## 禁止事项

- 不要修改源码、测试、配置、prompt。
- 不要运行真实 LLM。
- 不要访问外部网络。
- 不要启动 Chrome/CDP。
- 不要抓雪球详情页。
- 不要写 reports、knowledge、data/raw。

## 请重点审查

1. 设计是否会让 `periodic_report_fulltext_analysis` 被核心事实抽取误升格。
2. `SynthesisSkill` 追加 fulltext item 的位置是否合理。
3. `synthesis_credit` 对 fulltext 的 `credit_tier/usage/display_label` 是否足够清楚。
4. `format_synthesis_source_line()` 为 fulltext 放宽 excerpt 到 1200-1600 字符是否有 prompt 长度风险。
5. 是否需要 Phase A 就做 `PerStockReporter` 配置透传，还是先 ctx-only。
6. 是否还有 no-leak 测试缺口：scoring、risk scoring、Knowledge、evidence notes、source intake merge。
7. 是否需要改 `KnowledgeSynthesizer.extract_core_facts()` prompt，还是只靠 deterministic provenance filter 足够。

## 建议阅读文件

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/knowledge_synthesizer.py`
- `scripts/utils/synthesis_credit.py`
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_pipeline_integration.py`

## 输出格式

请把反馈追加到设计文档末尾，标题：

`## Round 1 Feedback`

包含：

- Status: Ready / Needs minor fixes / Needs major changes
- R2 Needed: Yes / No
- Blockers
- Must-fix before implementation
- Nice-to-have
- Suggested test additions
- Final recommendation

## 停止条件

如果你发现实现必须修改以下文件，请停止并说明原因，不要提出直接实现：

- `scoring_engine.py`
- technical modules
- `claim_risk_signal_skill.py`
- `source_intake_merge_skill.py`
- `KnowledgeSynthesizer.extract_core_facts()` prompt
