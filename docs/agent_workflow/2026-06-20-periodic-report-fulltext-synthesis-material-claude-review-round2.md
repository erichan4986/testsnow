# Claude Review Round 2 — Periodic Report Fulltext Synthesis Material

你是 Claude Code，在 `/Users/erichan/testsnow` 仓库里做只读 R2 设计审查。

## 目标

审查 Round 1 后新增的设计 delta 是否解决 blocker：

`docs/agent_workflow/2026-06-19-periodic-report-fulltext-synthesis-material-design.md`

重点看文档末尾：

`## Design Delta After Round 1`

## 禁止事项

- 不要修改源码、测试、配置、prompt。
- 不要运行真实 LLM。
- 不要访问外部网络。
- 不要启动 Chrome/CDP。
- 不要抓雪球详情页。
- 不要写 reports、knowledge、data/raw。

## R2 重点问题

1. 双结果策略是否能阻断 `synthesis_text → risk_score_section` 的间接泄漏？
   - `ctx["synthesis"]` 使用 enhanced synthesis。
   - `ctx["core_facts"]` 使用 baseline core facts。
   - `ctx["synthesis_text"]` 使用 baseline flatten。
   - enhanced flatten 只写到 `ctx["synthesis_text_with_periodic_report_fulltext"]`。
2. 这个方案是否可以不修改 `risk_renderer.py` 和 `scoring_engine.py`？
3. 是否接受 opt-in 时多一次 synthesis 调用的成本？
4. `derive_synthesis_usage()` 的 fulltext 分支和 source line 截断策略是否足够明确？
5. 测试计划是否足以捕获：
   - core facts 被 fulltext 支撑；
   - risk score / keyword observations 被 fulltext 影响；
   - 普通 source excerpt 被误放宽；
   - citation 编号重排。

## 输出格式

请把反馈追加到同一设计文档末尾，标题：

`## Round 2 Feedback`

包含：

- Status: Ready / Needs minor fixes / Needs major changes
- Blockers
- Must-fix before implementation
- Nice-to-have
- Final recommendation

## 停止条件

如果你认为必须修改以下文件才能安全实现，请停止并说明原因，不要提出直接实现：

- `scripts/utils/reporter/scoring_engine.py`
- technical modules
- `claim_risk_signal_skill.py`
- `source_intake_merge_skill.py`
- `KnowledgeSynthesizer.extract_core_facts()` prompt
