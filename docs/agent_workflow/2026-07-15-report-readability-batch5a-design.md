# Report Readability Batch 5A Design

日期：2026-07-15
范围：执行摘要口径一致性与 curated external 全局 URL 引用去重

## 目标

解决 20260715 正式报告中两个彼此独立、但都影响成稿可信度的问题：

1. 执行摘要把结构化基本面评分和高信用核心事实基座写成互相冲突的判断；
2. 同一外部 URL 被不同 claim 分配为多个 footnote，导致全局来源表重复。

本批不处理 4.3 长段落、主题跨节重复或外部材料 freshness 的正向触发；这些进入 Batch 5B。

## 边界

允许修改：

- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/curated_external_viewpoint_narrative.py`
- `tests/reporter/test_executive_summary_renderer.py`
- `tests/utils/test_curated_external_viewpoint_narrative.py`
- `tests/reporter/test_deep_analysis_renderer.py`（仅增加 formal-thin 引用 offset 回归）
- 本设计、implementation task 与实现 notes

禁止修改：

- `scoring_engine.py`、技术指标、目标价、风险分数、推荐阈值；
- producer、采集、LLM prompt、MaterialSnapshot 的 offset 公式；
- `report_quality.py`、`synthesis_skills.py`、profile 选择；
- data、knowledge、reports、config。

## 设计

### A. 执行摘要的口径边界

`_fundamental_summary()` 保持优先展示带 `verified` / `supported` provenance 的核心事实。

若没有可展示的高信用事实但存在 `pillar.fundamental`，文案改为两层事实：

> 模型基本面评分为 X/10，反映结构化基本面输入；证据状态为高信用核心事实基座尚未完整形成，因此该评分不构成正式材料确认。

这里不改变分数、输入、推荐或任何风险处理；只明确它们衡量的对象不同。没有评分时继续输出“尚未形成可由高信用来源支撑的核心事实基座”。

### B. curated narrative 的 URL-first citation allocation

`_validate_paragraphs()` 当前用 `claim_id -> ref_id` 分配引用，导致同一页面的多条 claim 即使 URL 相同也会在全局来源表生成多个 ref。

改为单一分配表：

- claim 有精确非空 URL 时，citation identity 为该 URL；
- claim 无 URL 时始终回退 `claim_id`，不使用 `_citation_from_claim()` 生成的默认 source/title 做 identity，避免把多个“外部精选观察 / 外部观点”占位来源错合并；
- 每个 resolved claim 先保留在 paragraph 的 `claim_refs`，只有 `citation_refs` 按 identity 去重；
- 同一 URL 的所有段落均引用同一个 ref，citation metadata 采用最先出现的安全 claim 元数据；不合并、重写或丢弃正文论点。

该 allocator 与现有 `deep_analysis_material_snapshot.citation_identity()` 在 URL-first 路径保持一致，但对无 URL 来源更保守：narrative allocation 按 claim-id 分开，后续 snapshot 仍可执行自己的 row-level exact identity 去重。narrative composer 不导入 snapshot，避免形成渲染/read-model 依赖反向。测试必须断言 URL 路径与 snapshot identity 一致，并单独锁定无 URL claim 不合并。

### C. Citation 与边界不变量

- 不变更 formal-thin 的 annual / broker / external offset 公式；
- 只减少重复外部 ref，不能新增或改写正文外部论点；
- 每个可见外部段落仍至少保留一个完整 inline footnote；
- 引用表不得出现 missing、unused、未知或重复的相同 URL；
- 外部 metadata 的 `preview_only`、`scoring_eligible=False` 和 `risk_score_eligible=False` 原样保留。

## 失败模式与测试

| 失败模式 | 安全结果 | 测试 |
|---|---|---|
| 评分与事实基座混为同一证据 | 文案明确两者口径不同 | 无核心事实 + fundamental score fixture |
| 已有高信用事实仍降级成评分说明 | 优先渲染高信用事实 | supported fact fixture |
| 同 URL 的多个 claim 仍生成多个 ref | 共享一个 citation ref，正文均引用它 | 两段、两 claim、同 URL fixture |
| 同标题但不同 URL 错合并 | 保留两个 ref | different-URL fixture |
| 无 URL 的 claim 被默认 metadata 错合并 | 按 claim id 分开 | no-URL fallback fixture |
| narrative 与 snapshot 的 URL identity 语义漂移 | URL 路径输出相同 | URL identity parity fixture |
| URL 去重后丢失 preview 边界 | citation metadata 保持最先出现的安全来源 | boundary-field assertion |
| local ref 去重改变 formal-thin offset | 正文可见 refs 与全局表完全一致 | formal-thin annual/broker/external assembly fixture |

## 验收

Focused tests 通过后，正式报告复跑应确认：

- 中际与复旦执行摘要不再将基本面评分写成高信用事实确认；
- 复旦 `xueqiu.com/1606930351/392467740` 在全局引用表只出现一次，但 4.3 的四项估值论点均保留 inline citation；
- 全局 citation hygiene 与 source boundary 均保持通过。

## 停止条件

- 需要改变 citation offset、MaterialSnapshot、评分、风险、目标价、推荐或外部采集；
- 同 URL 在当前模型中被证明不是同一来源实体，无法安全共用一个 citation；
- 引用去重导致任一可见 4.3 段落没有 inline footnote；
- 需要通过删除正文论点而非重新分配同一 citation ref 来消除重复。
