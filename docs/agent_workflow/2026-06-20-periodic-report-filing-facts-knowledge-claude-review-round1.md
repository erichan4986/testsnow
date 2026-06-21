# Periodic Report Filing Facts Knowledge — Claude Review Round 1

> **Date**: 2026-06-20
> **Owner**: Codex
> **Status**: Ready for Round 1 review

---

## Prompt For Claude Code

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做只读设计审查。不要实现代码，不要修改源码、测试、配置、prompt、data/raw、reports、knowledge；只允许把反馈追加到设计文档指定位置。

目标：
审查 Phase B 设计：把 exact `periodic_report_filing_fact` 作为结构化年报事实写入 Knowledge，同时继续隔离 `periodic_report_fulltext_analysis`、derived facts、risk signals、scoring/risk。

必须阅读：
- docs/agent_workflow/2026-06-20-periodic-report-filing-facts-knowledge-design.md
- docs/agent_workflow/2026-06-20-periodic-report-structured-facts-design.md
- scripts/utils/periodic_report_structured_facts.py
- scripts/utils/evidence_note_writer.py
- scripts/utils/report_skills/evidence_note_skill.py
- scripts/utils/report_skills/knowledge_skills.py
- tests/reporter/test_fulltext_material_isolation.py
- tools/ci_grep_gates.sh

重点检查：
1. Source-type split 是否安全：
   - `periodic_report_fulltext_analysis` 仍不得进入 Knowledge。
   - `periodic_report_filing_fact` 只能通过结构化 writer 进入。
   - `periodic_report_derived_fact` / `periodic_report_risk_signal` Phase B 不持久化。
2. Writer-only first 是否合理：
   - 是否应该先不做 pipeline registration？
   - 如果必须做 pipeline wrapper，哪些额外 tests 是 must-fix？
3. 是否应该复用 `evidence_note_writer.py`：
   - 设计倾向不复用，因为 generic claim-status 与 filing fact schema 语义不同。
   - 检查这个判断是否正确，是否有更小安全方案。
4. Knowledge 持久化边界是否明确：
   - 不改 `KnowledgePersistenceSkill` deep-analysis writer。
   - 不写真实 `knowledge/`，只在 tests 用 tmp_path。
   - 不让 fulltext summary 间接进入 `ctx["synthesis"]` 或 evidence notes。
5. 文件范围是否合理：
   - writer-only 允许新增 `periodic_report_filing_fact_note_writer.py` 和对应测试。
   - 不允许改 scoring/risk/synthesis/KnowledgeSynthesizer/fetchers。
6. 测试计划是否足够证明：
   - 只写 filing facts。
   - 缺 evidence 的 fact 被 skip。
   - fulltext/derived/risk 被 filter。
   - duplicate deterministic。
   - hostile stock/fact fields 不能 path traversal。
   - existing fulltext material isolation tests 仍通过。

可运行只读检查：
- rg -n "periodic_report_filing_fact|periodic_report_fulltext_analysis|knowledge_eligible|fact_candidate|synthesis_text|Knowledge" docs/agent_workflow/2026-06-20-periodic-report-filing-facts-knowledge-design.md scripts/utils tests/reporter/test_fulltext_material_isolation.py tools/ci_grep_gates.sh
- python3 -m pytest tests/utils/test_agent_workflow_docs.py tests/utils/test_ci_grep_gates.py tests/reporter/test_fulltext_material_isolation.py -q
- bash tools/ci_grep_gates.sh
- git diff --check

禁止事项：
- 不要实现代码。
- 不要访问外部网络。
- 不要启动 Chrome/CDP。
- 不要运行报告入口。
- 不要写 data/raw、reports、knowledge。
- 不要修改源码、测试、配置、prompt。

输出位置：
把反馈追加到 `docs/agent_workflow/2026-06-20-periodic-report-filing-facts-knowledge-design.md` 的 `## 11. Claude Review Log` 末尾，标题用：

`### Round 1 Feedback (Claude, 2026-06-20)`

反馈格式：
- Status: Ready / Needs minor fixes / Must-fix before task
- R2 Needed: Yes/No
- Blockers
- Must-fix
- Nice-to-have
- Phase B implementation allowed: Yes/No
- 是否建议 writer-only or pipeline wrapper
- 测试结果
- 是否改动了除设计文档外的文件

停止条件：
- 如果发现必须改 KnowledgeSynthesizer/synthesis/scoring/risk 才能实现 Phase B，请标为 blocker。
- 如果发现设计仍会让 `periodic_report_fulltext_analysis` 进入 Knowledge，请标为 blocker。
- 如果发现 filing facts 需要 source_credit>75 或 confirmed source type 才能写 Knowledge，请标为 blocker 或 must-fix，并解释替代方案。
```

---

## Expected Outcome

Round 1 should decide whether Phase B should start writer-only or include a default-off
pipeline wrapper. It should not reopen Phase C scoring or fulltext material-layer rules.

