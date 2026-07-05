# Annual + Broker Memo V1 — Batch 1a 笔记

Date: 2026-07-05  
Branch: `codex-report-quality-upgrade`

## 本次范围

实现 deterministic annual memo skeleton。

- formal-thin 股票的 4.1 改为 `年报经营摘要`，
  基于已有年报 evidence/cards/explanation pack 确定性地组装。
- 不引入 LLM 年报润色。
- 不实现研报 memo；4.2 仅渲染缺席说明。
- 保留 formal-rich 旧 4.1/4.2/4.3 标题。

## 修改文件

- `scripts/utils/report_skills/synthesis_skills.py`
  - 导入 `build_annual_report_material_pack`。
  - `run()` 在 evidence profile 之前构建
    `annual_report_material_pack` 与 `annual_report_memo`。
  - 新增 `_build_annual_report_memo(ctx)`：确定性组装 memo payload、
    过滤 forbidden source、校验零值 metric、分配 citation IDs。
  - `_build_evidence_profile()` 返回值追加 memo 相关字段。
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
  - `render()` 三段式合并 baseline → annual memo → curated external
    citations。
  - `_deep_analysis()` 传递 `annual_citation_offset`。
  - `_formal_thin_external_rich_body()` 按 `formal_thin_layout_variant`
    分支：新 variant 渲染 4.1/4.2/4.3/4.4，旧路径保持不变。
  - 新增 `_annual_report_memo_section()`。
  - `_external_viewpoint_map_section()` /
    `_verification_checklist_section()` 支持 citation offset，
    标题随 variant 在 4.2/4.3 之间切换。
- `tests/reporter/test_deep_analysis_renderer.py`
  - 新增 7 个聚焦测试：annual memo 章节、broker 缺席、citation refs、
    deterministic fallback、formal-rich 回归、forbidden source 拒绝、
    formal-rich 不输出未渲染 annual memo citation。
- `tests/reporter/test_synthesis_skills.py`
  - 新增 4 个测试：profile 字段、ready/fallback status、
    零值 revenue warning、forbidden source 过滤。
- `docs/agent_workflow/2026-07-05-annual-broker-memo-v1-batch1a-claude-notes.md`
  （本文件）

## `annual_report_memo` 数据来源与 ctx key

ctx key：`annual_report_memo`

schema：`annual_report_memo.v1`

数据来源：

- `annual_report_material_pack.selected_narrative_cards`
  （来自 `build_annual_report_material_pack`，
  读取已持久化的 periodic-report narrative cards）。
- `formal_financial_fact_pack.facts`
  （来自 `periodic_report_filing_core_facts`）。
- `formal_financial_explanation_pack.rows`
  （来自 `periodic_report_explanation_pack`）。
- `periodic_report_filing_core_facts`（用于 zero-value 校验）。

无 raw 年报 LLM prompt。

## `deep_analysis_evidence_profile` 新增字段

```json
{
  "annual_memo_status": "ready | deterministic_fallback | blocked | absent",
  "broker_memo_status": "absent",
  "broker_single_institution": false,
  "memo_refs_resolved": true,
  "formal_thin_layout_variant": "annual_broker_external_checklist"
}
```

未创建第二套 profile。

## `citation_refs` 映射到最终 citation metadata

1. Memo builder 内部按来源去重，从 1 开始分配本地 citation ID，
   存入 `annual_report_memo.citations`。
2. Renderer 做三段式顺序合并：
   - baseline synthesis citations 占 `1..B`
   - annual memo citations 偏移 `max_baseline_id` 后占 `B+1..B+A`
   - curated external citations 偏移 `B+A` 后占 `B+A+1..`
3. `_annual_report_memo_section` 渲染时把每个 row 的 `citation_refs`
   加上 `annual_citation_offset`，生成 `[^n]`。
4. `_append_section_citations` 列出本节引用来源。
5. 全局 `## 引用来源` 通过 `_merged_citations` 两次调用合并，
   保证 inline marker 与 metadata 一一对应。

## Formal-Thin 渲染示例

```markdown
### 4.1 年报经营摘要

**已确认**
- **营业收入**：营业收入 39.82 亿元。[^1]

**年报解释**
- **主营业务与产品**：公司增长主线来自 FPGA 与智能电表 MCU。[^2]
- **研发与产品进展**：新一代 FPGA 进入客户验证阶段。[^3]

**未披露 / 不能下结论**
- 重要客户、订单、产能、供应链、管理层指引或细分拆分
  未在正式材料中充分披露。
- 不得用营收/利润推断主力资金或市场行为。

**本节引用来源：**
- [^1] **公司年报** | 《2025年度报告》
- [^2] **公司年报** | 《2025年度报告》

### 4.2 研报观点与假设

当前未取得足够可用研报 digest，不展开研报观点与假设。

### 4.3 外部观点地图（Preview，不参与评分）

> 以下内容为外部材料梳理，仅作为专业观察，不等同于官方确认事实；
> 不参与评分、风险评分或最终建议。

...

### 4.4 待验证清单

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|
```

当 `annual_report_memo` 不可用时，4.1 仍渲染 `年报经营摘要` 标题与
fallback 文案：

> 当前未取得足够年报材料，无法形成年报经营摘要。

不回退到 `产业逻辑 / 业绩路径 / 资金面` 旧标题。

## Formal-Rich 回归

- `profile == "formal_rich"` 路径完全未改动。
- 仍渲染旧标题：
  - `### 4.1 产业逻辑与竞争格局`
  - `### 4.2 业绩路径与多空分歧`
  - `### 4.3 资金面与催化剂时间线`
- `annual_report_memo` 已写入 ctx，可在后续 batch 作为 preferred input
  喂给 LLM，但 Batch 1a 未改 prompt。

## Codex 验收修复

Codex 验收时发现一个 formal-rich 回归：Batch 1a 的全局 citation merge
会无条件合并 `annual_report_memo.citations`。formal-rich 路径虽然不渲染
`年报经营摘要`，但全局 `## 引用来源` 仍可能出现未被正文引用的 annual
memo 来源。

最小修复：

- `DeepAnalysisRenderer.render()` 仅在
  `profile == formal_thin_external_rich` 且
  `formal_thin_layout_variant == annual_broker_external_checklist` 时读取并合并
  `annual_report_memo`。
- 新增
  `test_formal_rich_does_not_emit_unused_annual_memo_citations`，覆盖
  formal-rich 不输出未渲染 memo 来源和 memo 正文。

## Smoke Follow-up 修复

双股 smoke 后，Codex 追加 3 个极窄修复：

1. **PE spread 表格文案**
   - 根因：Batch 0 sanitizer 只处理执行摘要和
     `PE(TTM)83.26倍高于新易盛15倍` 形态，formal-rich 4.1 表格里的
     `PE(TTM)高于新易盛约15倍` 没被覆盖。
   - 修复：扩展 `_sanitize_pe_spread_in_text()` 的 spread-only pattern，
     并在 `DeepAnalysisRenderer.render()` 对 deep-analysis 正文复用同一
     sanitizer。
   - 覆盖：
     `test_formal_rich_sanitizes_pe_spread_in_deep_analysis_table`。
2. **formal-thin 新 layout gate false positive**
   - 根因：quality/source-boundary 仍按旧布局找外部观点地图
     （旧 4.2 或 legacy 4.4）。
   - 修复：按
     `formal_thin_layout_variant == annual_broker_external_checklist`
     将外部观点地图定位到 4.3；4.4 待验证清单不再要求 display-only
     disclaimer。
   - 覆盖：
     `test_external_map_new_annual_broker_layout_uses_4_3`、
     `test_formal_thin_annual_broker_external_map_region_is_allowed`。
3. **annual memo zero metric status**
   - 根因：`0.00亿元` 触发 validation warning 后，memo status 被标成
     `blocked`，但 4.1 仍有可用年报解释内容，profile 与展示语义不一致。
   - 修复：零值营收/利润 fact 跳过，不进入 `已确认`；warning 保留；
     只要有可用解释行，就降级为 `deterministic_fallback` 而非
     `blocked`。
   - 覆盖：
     `test_build_annual_report_memo_zero_metric_does_not_block_explanation_rows`。

## Slimming Audit Follow-up

Codex 做了一次极窄瘦身：

- 删除 `report_source_boundary.py` 中冗余的
  `_remove_formal_thin_external_map_region()`。
- 删除对应调用。
- 原因：`_remove_curated_external_region(body, profile)` 已经按 profile 移除
  legacy 4.2 / new-layout 4.3 外部观点地图，后续 helper 是历史遗留的二次删除。
- 验证：
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/reporter/test_report_source_boundary.py tests/reporter/test_report_quality.py -q -p no:cacheprovider`
  → 70 passed。

## Runtime 净增行数

```text
git diff --numstat \
  scripts/utils/report_skills/synthesis_skills.py \
  scripts/utils/reporter/sections/deep_analysis_renderer.py
 scripts/utils/report_skills/synthesis_skills.py      | 147 ++++
 scripts/utils/reporter/sections/deep_analysis_renderer.py | 99 ++++- 24
 scripts/utils/reporter/sections/executive_summary_renderer.py | 82 ++++
 scripts/utils/report_quality.py                      | 29 ++- 10
 scripts/utils/report_source_boundary.py              | 26 ++- 24
```

- 当前未提交 diff 中 runtime 净增：**325 行**。
- 其中包含 Batch 0、Batch 1a 和 smoke follow-up 的累计改动，
  已超过设计文档 / 用户目标 `<= 180 行` 和 `> 260` hard stop。
- 该累计净增已超过后续瘦身阈值；Batch 2 前应优先评估是否拆 commit
  或在 Batch 3 删除 legacy visible-card/addendum 路径偿还。

## 测试结果

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_deep_analysis_renderer.py \
  tests/reporter/test_synthesis_skills.py \
  -q -p no:cacheprovider
# 135 passed
# Follow-up 后：137 passed

PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/reporter/test_report_quality.py \
  tests/reporter/test_report_source_boundary.py \
  tests/reporter/test_executive_summary_renderer.py \
  -q -p no:cacheprovider
# 81 passed
# Follow-up 后：83 passed

python3 scripts/check_report_quality.py reports/复旦微电_20260705.md
# PASS

python3 scripts/check_report_source_boundary.py reports/复旦微电_20260705.md
# PASS

python3 scripts/check_report_quality.py reports/中际旭创_20260705.md
# PASS

python3 scripts/check_report_source_boundary.py reports/中际旭创_20260705.md
# PASS

bash tools/ci_grep_gates.sh
# all gates passed

git diff --check
# clean
```

## Blocker / Warning / Deviation

- **Blocker**：无。
- **Warning**：
- 当前累计 runtime 净增 325 行，超过设计目标；
    后续 Batch 2/3 需通过删除 dead path（visible reasoning-card 渲染、
    legacy addendum、template gate）偿还，或先拆分提交控制审查范围。
  - `annual_report_memo` 的 citation 合并引入三段 offset，
    需保证 future curated external 内容也走同一合并路径。
  - Validation warning 仅在 memo builder 中产生，renderer 原样渲染；
    目前没有独立 quality gate，
    由 synthesis/renderer 测试覆盖 forbidden source。
- **Deviation**：
  - 未实现研报 memo（符合 Batch 1a 范围）。
  - 未改评分、目标价、推荐、技术面算法。
  - Codex 未重新运行正式报告入口；仅对 Claude smoke 生成的现有
    `reports/复旦微电_20260705.md` 与
    `reports/中际旭创_20260705.md` 做只读 quality/source-boundary 复测。
  - 未修改 `annual_report_material_pack.py`，
    仅复用其 `build_annual_report_material_pack`。

## 后续建议

- Batch 2：实现研报 memo，复用 `broker_research_digest.py` /
  `broker_research_digest_synthesis_items.py`，应用 admission rule。
- Batch 3：按 Batch 0 audit 删除/合并 dead visible-card/addendum 路径，
  偿还 runtime 债务。
