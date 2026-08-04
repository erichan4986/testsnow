# Scripts 全栈审计 Batch A — Implementation Task

## 输入

完整阅读：

- `docs/agent_workflow/2026-08-04-scripts-full-stack-audit-batch-a-design.md`
- `docs/agent_workflow/2026-08-04-scripts-full-stack-audit-batch-a-claude-review-round1-notes.md`
- `docs/agent_workflow/2026-08-04-scripts-full-stack-audit-batch-a-implementation-plan.md`
- `AGENTS.md`

## 目标

按 implementation plan 的 Task 1 -> Task 2 -> Task 3 严格 TDD，实现 A1-A5 的确定性死代码删除。

## 允许修改

- `scripts/utils/reporter/sections/price_target_renderer.py`（删除）
- `scripts/utils/reporter/sections/__init__.py`
- `scripts/utils/reporter/data_fetcher.py`
- `scripts/utils/periodic_report_narrative_pack_store.py`
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- `scripts/utils/external_source_document.py`
- `scripts/utils/periodic_report_required_metrics.py`
- `tests/test_runtime_hygiene.py`
- `README.md`
- 本任务的 implementation notes

现有 design/review/plan/task 文档只读，不再重写。

## 禁止事项

- 不修改任何 active owner 的行为；保留 `Iterable` import。
- 不修改评分、风险、技术算法、目标价引擎、引用、LLM prompt 或采集逻辑。
- 不修改其他 tests，不删除 test case。
- 不修改 data、knowledge、reports，不联网，不启动 Chrome/CDP。
- 不处理主仓库 `/Users/erichan/testsnow` 的脏分支。
- 不提交、不推送。

## 停止条件

- 候选出现新的 runtime/test/preview/tool 调用证据；
- 需要改白名单之外的源码或测试；
- runtime 净减不足 185 行或出现 runtime 新增；
- focused/full suite 出现无法由本批删除直接解释的失败；
- 离线 smoke 写入 `/tmp` 之外或尝试外部采集。

## 输出

写入：

`docs/agent_workflow/2026-08-04-scripts-full-stack-audit-batch-a-implementation-notes.md`

最终仅汇报：修改/删除文件、RED/GREEN、focused/full/CI/smoke、runtime numstat、
active owner 审计、blocker/warning/deviation、`Batch A accepted: yes|no`、notes 路径。
