# Formal Medium Source-Layer Layout Design

日期：2026-07-06
分支：codex-report-quality-upgrade

## 背景

用户确认第四章的首要职责是：按证据信用层，把相关标的的基本面情况讲清楚，包括但不限于产品线、产业需求、业绩驱动、毛利率、订单客户、估值分歧、资金面、竞争对手，并在最后统一列出能让观点升级或降级的变量，尽量结合当前股价和基本面展望未来股价上行/下行条件。

当前问题是：`formal_medium` 仍使用旧结构：

- `4.1 产业逻辑与竞争格局`
- `4.2 业绩路径与多空分歧`
- `4.3 资金面与催化剂时间线`
- `4.4 精选外部观察`

中际旭创这类样本虽然材料不少，但旧结构容易把年报、研报、外部观察和估值表混在主题桶里，信息密度看似高，阅读上仍像表格堆叠。

## 第一批范围

只切换 `profile == "formal_medium"` 的第四章布局。暂不修改：

- `formal_thin_external_rich`
- `formal_rich`
- evidence profile 判定阈值
- 评分、目标价、风险评分、技术面、推荐结论
- LLM prompt 与 KnowledgeSynthesizer
- 外部采集、雪球、Chrome/CDP

## 目标布局

`formal_medium` 改为 source-layer first：

1. `4.1 官方材料确认`
   - 渲染 `annual_report_memo`
   - 覆盖年报/季报/公告确认的产品线、经营变化、研发、财务变化、未披露事项
   - 只能使用正式材料语气

2. `4.2 研报观点与假设`
   - 渲染 `broker_research_memo`
   - 研报内容必须保持 attribution：`券商认为 / 研报预计 / 机构假设`
   - 可覆盖产业需求、业绩驱动、竞争格局、估值分歧
   - 不得写成官方确认事实

3. `4.3 外部观察与待验证变量（Preview，不参与评分）`
   - 渲染 curated external map
   - 外部观点只作为待验证变量和置信度/仓位折扣
   - 不参与评分、目标价、风险评分或正式事实

4. `4.4 升级/降级变量与股价推演`
   - 第一版先用确定性 checklist，不调用新 LLM
   - 合并 annual/broker/external 中已经可见的关键变量
   - 输出上行条件、下行条件、需要验证的证据
   - 必须显式区分：官方确认、机构假设、外部待验证
   - 不直接改目标价或评分

## 实现策略

在 `DeepAnalysisRenderer.render()` 中让 `formal_medium` 走新的 `_formal_medium_source_layer_body()`，而 `formal_rich` 继续走 `_legacy_deep_analysis_body()`。

优先复用已有 renderer helper：

- `_annual_report_memo_section()`
- `_broker_research_memo_section()`
- `_external_viewpoint_map_section()`
- `_verification_checklist_section()`
- citation offset / merge helpers

如需新增 helper，只允许新增小函数用于：

- formal_medium 专用章节组装
- 4.4 升级/降级变量确定性渲染

## Citation Contract

`formal_medium` 新布局必须保持全局引用卫生：

- 所有 visible `[^n]` 必须进入全局 `## 引用来源`
- 全局引用不得出现 unused refs
- 外部观点引用只应在 4.3/4.4 Preview 或全局引用表出现，不得进入 4.1 官方确认

## Quality Gate 调整

现有 `formal_medium` evidence-depth gate 需要接受新标题：

- `4.1 官方材料确认`
- `4.2 研报观点与假设`
- `4.3 外部观察与待验证变量（Preview，不参与评分）`
- `4.4 升级/降级变量与股价推演`

Gate 仍保持 warning 级，不要求 `formal_rich` 完整度。

## 测试计划

Focused tests：

- `formal_medium` 渲染新四段标题，不再出现旧 4.1/4.2/4.3 标题
- `formal_rich` 仍保留旧结构
- `formal_thin_external_rich` 不受影响
- `formal_medium` 全局引用覆盖 annual/broker/external visible refs，无 missing/unused
- `formal_medium` 新标题通过 `check_report_quality.py`
- `formal_medium` 外部观点仍被 source-boundary 视为 display-only

本地报告验收：

- 中际旭创应为 `formal_medium` 且使用新结构
- 复旦微电仍为 `formal_thin_external_rich`，结构不因本批改动变化

## Stop Conditions

立即停止并回报：

- 需要修改 `KnowledgeSynthesizer` prompt 或 LLM 合成逻辑
- 需要修改评分、目标价、风险评分、技术算法
- 需要新增 sidecar 或持久化 MaterialSnapshot
- 需要重写 annual/broker/external memo producer
- focused tests 暴露 formal_rich 或 formal_thin 大面积回归
