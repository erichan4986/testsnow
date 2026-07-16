# Evidence Freshness Adaptation - Codex Implementation Notes

日期：2026-07-15
分支：`codex/annual-producer-v2`

## 修改文件

Runtime：

- `scripts/utils/evidence_freshness.py`
- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/curated_external_viewpoint_narrative.py`
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/report_quality.py`

Tests：

- `tests/utils/test_evidence_freshness.py`
- `tests/utils/test_curated_external_viewpoint_narrative.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_executive_summary_renderer.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_report_quality.py`

## 实现摘要

- 新增纯 freshness policy：只解析显式日期，120 天阈值，正式层/券商层混合日期 fail-closed。
- 外部候选只来自既有 `_curated_external_narrative_paragraphs`，只读取 topic/primary_topic 元数据，要求完整 display-only 边界、source credit >=55、每个 supporting citation 均为新鲜显式日期，并拒绝未否定的强确认语气。
- 同一 URL/来源元数据先逐条完成边界校验，再做 identity 去重；候选最多一条，带确定性排序和 reason code。
- SynthesisSkill 仅向 baseline citation map 预约候选引用，不写入 baseline 文本、sources、core facts 或评分输入。
- 执行摘要只在严格候选存在时追加一条完整 disclaimer；Chapter 4 继续使用 full snapshot offset，候选引用在 offset 后按既有 identity 做精确 alias。
- formal-rich 无候选、无 preface；formal-medium / formal-thin 才启用 overlay。

## TDD / 测试结果

- 纯策略 RED：新增模块不存在时 ImportError；GREEN：`13 passed`。
- Batch 4 focused：`361 passed`。
- 下游 material/synthesis/source-intake 套件：`110 passed`。
- source boundary / fulltext intake 相关套件：`80 passed`。
- `bash tools/ci_grep_gates.sh`：all gates passed。
- `git diff --check`：clean。
- 相关 runtime `py_compile`：通过。

全仓 `pytest` 未作为本批通过门：已运行到 `224 passed, 6 skipped` 后，暴露既有 `test_claim_risk_signal_skill` 顶层导入 `scoring_engine` 时的相对导入错误，随后环境数据测试触发 akshare 请求并被中断。该失败不触及本批允许文件，未对其做越界修复。

## Runtime 审计

新增 freshness policy 文件当前为 121 行。当前 worktree 在 Batch 4 开始前已经存在 Chapter 4、executive summary、report quality 等脏改动，因此 `git diff --numstat HEAD` 不能作为 Batch 4 独立增量：它包含前序 Batch 3/技术分析/报告布局改动。

当前相关 tracked runtime diff（含前序脏改动）为：

```text
curated_external_viewpoint_narrative.py  22  1
report_quality.py                        52 10
synthesis_skills.py                      54  0
deep_analysis_renderer.py               144 142
executive_summary_renderer.py            25  0
```

因此不能把上述总量误报为本批净增，也不能在缺少 Batch 4 起始快照的情况下声称精确的独立 `+190`。本批未继续扩大允许文件；新增逻辑集中在 6 个既定 runtime 文件和一个纯策略模块，未引入第二 selector 或新的数据路径。

## Blocker / Warning / Deviation

- Blocker：无发现 Batch 4 功能 blocker；聚焦、下游、source boundary、CI 均通过。
- Warning：全仓测试仍有既有顶层模块导入/akshare 环境失败；runtime 独立增量因起始 worktree 已脏无法从当前 HEAD 精确核算。
- Deviation：未生成正式报告；未联网；未修改 data、knowledge、reports、config、prompt、采集、profile、评分、目标价、风险、技术面或推荐逻辑；未提交、未推送。

## Stop-condition audit

- 未从标题、路径、mtime、报告年份或正文推断日期/动态 topic。
- 未让外部材料进入 4.1、core facts、baseline synthesis text、评分、风险、目标价、推荐或技术判断。
- formal-thin 的 full-snapshot citation offset 公式未改变；alias 只处理与已预约 baseline identity 相同的精确 citation marker。
- 外部候选缺日期、混合日期、边界字段、信用不足、topic 未映射或强确认语气时均保持普通 Preview，不晋升。

## Follow-up fixes

- `report_as_of_date` 未注入时，freshness overlay 现在只回退到运行日；不再使用历史 `collected_at`。
- `近期待验证变量` 必须出现在 `执行摘要` 内；同样文本重复到其他章节也会触发 `freshness_summary_outside_executive_summary`。
- 新增 formal-thin 组装回归：摘要候选与 full-snapshot offset 后的 4.3 使用同一 citation identity，全局引用表不出现重复 URL、missing 或 unused ref。
- 验证：相关 focused suite `375 passed`，`tools/ci_grep_gates.sh` 与 `git diff --check` 通过。
- Runtime 独立增量仍无法由当前脏 worktree 可靠重建；在没有 Batch 4 起始快照时，不将当前总 diff 误报为本批精确行数。
