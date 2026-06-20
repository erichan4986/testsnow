# HK Periodic Report Evidence Pack — Claude Review Round 2

> **Date**: 2026-06-20
> **Owner**: Codex
> **Status**: Ready for narrow R2 review

---

## Prompt For Claude Code

```text
你是 Claude Code，在 /Users/erichan/testsnow 仓库里做只读设计复核。不要修改源码、测试、配置、prompt、data/raw、reports、knowledge；只允许把反馈追加到设计文档指定位置。

目标：
复核 HK periodic report evidence-pack 设计在 Round 1 后的 scope correction 是否已经足够进入 Phase HK-A helper-only 实现。

必须阅读：
- docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-design.md
- scripts/utils/periodic_report_evidence_pack.py
- scripts/utils/periodic_report_structured_facts.py
- scripts/utils/periodic_report_required_financial_metrics.py
- tests/utils/test_periodic_report_evidence_pack.py
- tests/utils/test_periodic_report_structured_facts.py

重点检查：
1. R1 的 blocker 是否已解决：
   - Phase HK-A 是否明确允许 `periodic_report_structured_facts.py` 做 HK label variants。
   - `revenue` / `operating_cash_flow` 是否有 Traditional + Simplified HK 标签。
   - `年內虧損` / `經調整虧損淨額` 是否没有被错误映射成 `net_profit`。
2. `收入` 是否只允许在 dedicated HK statement block 内锚定，而不是 raw text 全文搜索。
3. 五年財務概要/五年财务概要是否 deterministic fail-closed：
   - 不得作为 primary `hk_income_statement_table` / `hk_cash_flow_table` anchor。
   - 若以后保留，只能作为独立 diagnostic usage。
4. 文件范围是否合理且仍 helper-only：
   - 允许 `periodic_report_evidence_pack.py`
   - 允许 `periodic_report_structured_facts.py` 仅做 HK label variants
   - 允许对应 tests
   - 不允许 fetcher、pipeline、Knowledge、synthesis、scoring、risk、reports/data/knowledge 写入
5. 测试计划是否能证明：
   - 黑芝麻式繁体 HK income statement + cash flow 能 anchor revenue 和 negative OCF。
   - 多个裸 `收入` 不会误锚到无关段落。
   - 只有 five-year summary 时不会造假 fact/ref。
   - A-share block ids/priorities 不回归。

可运行只读检查：
- rg -n "hk_income_statement|hk_cash_flow|五年|收入|經營活動所用|PHASE_A|_PHASE_A_METRICS" docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-design.md scripts/utils/periodic_report_evidence_pack.py scripts/utils/periodic_report_structured_facts.py
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
把反馈追加到 `docs/agent_workflow/2026-06-20-hk-periodic-report-evidence-pack-design.md` 的 `## 10. Claude Review Log` 末尾，标题用：

`### Round 2 Feedback (Claude, 2026-06-20)`

反馈格式：
- Status: Ready to implement / Needs minor fixes / Must-fix before task
- R3 Needed: Yes/No
- Blockers
- Must-fix
- Nice-to-have
- Phase HK-A implementation allowed: Yes/No
- 测试结果
- 是否改动了除设计文档外的文件

停止条件：
- 如果发现需要改 fetcher/pipeline/Knowledge/synthesis/scoring/risk 才能满足 Phase HK-A，请停止并标为 blocker。
- 如果发现 design 仍会让 Black Sesame revenue/OCF 无法 anchor，请停止并标为 blocker。
```

---

## Expected Outcome

R2 should be narrow. It should only decide whether the Round 1 scope correction is enough
for helper-only implementation. It should not reopen Source Intake, synthesis, Knowledge,
scoring, risk, or HKEX fetcher design.

