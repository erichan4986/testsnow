# Formal-Medium Chapter 4.4 Retirement Design

日期：2026-07-22  
状态：proposed

## 1. Goal

删除 `formal_medium` 报告中没有事实增量的“4.4 上行 / 下行条件与股价推演”，并删除仅为该节服务的选择和渲染代码。

本批不删除 `formal_rich` 的 legacy 4.4 外部观点 addendum，也不改变 `formal_thin_external_rich` 的三节布局。

## 2. Current Failure

当前 formal-medium 4.4 从 4.1、4.2、4.3 已展示的 rows 中各取一个标题，再套固定模板：

- 官方材料：若改善则支撑增强，若恶化则支撑减弱；
- 券商材料：若假设兑现则消化估值，若落空则下修；
- 外部材料：若获验证则提升置信度，若被证伪则视为噪音。

这些句子不读取 row 的事实正文，也没有指标、阈值、时间范围、确认条件或失效条件。实际报告中的“官方确认：业务结构”“外部待验证：竞争格局”只是把前三节标题换成条件句，既重复又制造了似乎经过推演的错觉。

复旦微电在 `formal_thin_external_rich` 下没有 4.4，这是既有设计，不是缺节回归。中际旭创在 `formal_medium` 下显示的 4.4 则属于本批要删除的空泛模板。

## 3. Locked Product Policy

1. formal-medium 只展示 4.1 官方材料、4.2 机构观点和 4.3 外部待验证变量。
2. 不保留空 4.4 标题、占位文案或“当前无法推演”的固定提示。
3. 不从 4.1--4.3 prose 自动推导上/下行结论。
4. 完整 `MaterialSnapshot`、annual/broker/external rows 和 citations 保留；只删除无效的 price-path display projection。
5. formal-thin 继续保持现有 4.1--4.3 布局和 full-snapshot citation offset。
6. formal-rich legacy 4.4 外部观点 addendum 保持不变；该路径有来源原文和 inline citations，不属于本批空泛 price-path 模板。
7. 评分、目标价、风险、技术分析、执行摘要和推荐不读取本节，行为必须不变。

## 4. Architecture Changes

### 4.1 Chapter4ViewModel

`build_chapter4_view_model()` 的 formal-medium section tuple 从 4.1--4.4 改为 4.1--4.3：

- 删除 `_select_price_path_rows()` 调用；
- 删除 `Chapter4Section("4.4", ...)`；
- visible refs 继续只从实际可见三个 sections 和 external narratives 计算。

完整 snapshot rows 不变，因此不是材料丢失或 producer 裁剪。

### 4.2 Dead Runtime Removal

删除仅为 formal-medium price path 服务的 helper：

- `_select_price_path_rows()`；
- `_select_price_row()`；
- `_generic_broker_price_row()`；
- `DeepAnalysisRenderer._formal_medium_price_path_section()`。

保留 `is_informative_variable_title()` 和 `_NON_INFORMATIVE_VARIABLE_TITLES`，因为 4.2 机构关注重点仍使用它们。

保留 `MaterialRow.argument_complete`，因为它仍属于 annual producer/material schema，并参与 annual display ranking。

### 4.3 Renderer

`_formal_medium_source_layer_body()` 渲染完 4.3 后直接返回，不写 4.4 heading，也不读取不存在的 view-model section。

formal-thin 和 formal-rich renderer 不修改。

## 5. Future Reintroduction Gate

未来只有 material schema 提供可审计的结构化 trigger 时才重新引入条件节。每条 trigger 至少需要：

- `indicator_or_milestone`：被观察的指标或里程碑；
- `direction`：改善、恶化或双向；
- `confirmation_condition`：可观察的确认条件；
- `invalidation_condition`：可观察的反证条件；
- `time_horizon`：适用期间；
- `citation_refs`：直接支持上述条件的来源。

缺任一项不得由 renderer 从 prose 猜测补齐。未来恢复时应重新命名为“关键验证条件”，不承诺机械映射到股价方向。

## 6. Citation and Source Boundaries

- 被删除的 4.4 rows 都已来自 4.1--4.3 的可见 rows；删除 projection 不删除任何原始 row。
- 4.1--4.3 inline citations 与全局来源表继续由现有 visible-citation 路径处理。
- 不把 external citations 移入 4.1/4.2。
- 不改变 formal-thin 的 annual/broker/external citation offset 公式。
- formal-rich legacy 4.4 的 disclaimer、inline citations 和质量门保持原样。

## 7. Tests

### RED Contracts

1. formal-medium `Chapter4ViewModel.sections` 只包含 `4.1`, `4.2`, `4.3`。
2. formal-medium renderer 输出不含“4.4 上行 / 下行条件与股价推演”、三种模板标签或固定条件句。
3. 删除 4.4 后 4.1--4.3 rows、narratives 和 citations 与删除前相同。
4. formal-thin 仍无 4.4，且后置 external ref 保持 full-snapshot offset。
5. formal-rich fixture 仍显示 legacy “4.4 外部观点与待验证变量（Preview）”。

### Regression Gates

- focused snapshot and renderer tests；
- report quality, source-boundary and prose-quality tests；
- full offline suite；
- `bash tools/ci_grep_gates.sh`；
- `git diff --check`；
- fresh Fudan and Zhongji report rerun，确认 Fudan 仍为三节、Zhongji 从四节变为三节，且其余内容与引用不丢失。

## 8. Failure Modes

| Failure mode | Observable failure | Gate |
|---|---|---|
| 误删 formal-rich 4.4 | legacy external addendum 消失 | formal-rich renderer fixture |
| formal-thin offset 回归 | external footnote 被重新编号 | existing full-snapshot offset test |
| 4.3 被一并删减 | external rows/narratives 减少 | view-model equality fixture |
| 引用定义丢失 | missing refs 或 source-boundary fail | report gates + fresh reports |
| 执行摘要/评分受影响 | score/recommendation output changes | downstream/full suite |
| 留下死代码 | helper 仍有 definition/call | `rg` audit + diff review |
| 留下空标题 | 报告仍出现 4.4 heading | renderer and fresh-report assertions |

## 9. Allowed Scope

Runtime:

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`

Tests:

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`

Workflow design/task/notes may be added.

No changes to producer, canonical packs, profile routing, quality rules, scoring, target price, risk, technical analysis, executive summary, recommendation, LLM prompts, data, knowledge or reports during implementation.

## 10. Runtime Budget

This is a deletion batch. Expected runtime net change: `-70` to `-90` lines.

Stop and return to design if implementation requires net-positive runtime, a replacement inference engine, changes outside the allowed runtime files, or changes to formal-rich/formal-thin behavior.
