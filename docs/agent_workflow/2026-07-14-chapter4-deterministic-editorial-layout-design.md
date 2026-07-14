# Chapter 4 Deterministic Editorial Projection and Narrow Layout Design

日期：2026-07-14
分支：`codex/annual-producer-v2`

## 1. Goal

Annual Producer v2、annual memo 和 MaterialSnapshot 已保留足够材料；当前问题是成品 Chapter 4 仍有逐 row 展示、bullet wall、重复局部来源表和 Source Intake 工具输出感。

本批只改确定性展示投影：

- formal-medium 与 formal-thin 的 Chapter 4 更像连续投研成稿；
- 完整 annual / broker / external 材料继续保留在 memo 与 MaterialSnapshot；
- citation、信用层和 profile 边界不变；
- 不引入 LLM memo，不修改 prompt、producer、scoring、target、risk、technical 或 recommendation。

## 2. Current-Code Audit

### 2.1 Chapter4ViewModel

`build_chapter4_view_model()` 已是 formal-medium 的 Chapter 4 read-model。它接收完整 snapshot，构造 4.1–4.4 sections，并只把 visible refs 交给 renderer。

`select_annual_display_rows()` 当前负责 annual display admission、segment projection 和 exact/containment dedupe，但没有 editorial budget，因此 4.1 仍可能展示大量已准入 rows。renderer 随后再次分组、去重和逐条输出，形成第二层展示所有权。

formal-thin 当前不构造完整 `Chapter4ViewModel`：它直接复用 `select_annual_display_rows()` 生成 4.1 display rows，并保留既有 broker/external renderer。这个 split 是 citation-safe 的受控例外，本批不把 formal-thin 强行扩展为完整 ViewModel，以免同时重写 broker/external offset 和全局 citation aggregation。

结论：formal-medium 的全部 display rows 继续由现有 ViewModel 拥有；formal-thin 的 annual display rows 由同一个 `select_annual_display_rows()` 拥有，broker/external 只做既有 renderer 的确定性排版与 cap 清理。不得新增 `EditorialMemo`，也不得在 renderer 建第二套 annual selector。

### 2.2 Formal-thin citation offsets

formal-thin 在 annual display selection 之前构建 full MaterialSnapshot。设 baseline synthesis 最大引用号为 `B`：

- annual visible ref：`B + snapshot_ref`；
- broker offset：`B + max_snapshot_ref(full_snapshot, {annual})`；
- external offset：`B + max_snapshot_ref(full_snapshot, {annual, broker})`。

当前公式正确，必须保留。display rows 只能决定哪些 refs 可见，不能参与 offset 计算或重新压号。最终继续由 full snapshot citation map 与 `_visible_citations_only()` 生成全局引用表。

### 2.3 Source Intake switches

现有开关：

- `source_intake_enabled`：控制 intake 是否启用，不能用于仅隐藏正文；
- `source_intake_render_details`：只控制明细子节，来源分层概览仍然显示。

当前没有可复用的整节 display toggle。本批新增 `source_intake_render_section`：默认 `False`；只有显式设为 `True` 时才输出 Source Intake 正文章节。intake context、material items 和 sidecar 行为不变。

## 3. Architecture

```text
producer / memo (complete)
  -> MaterialSnapshot (complete rows + full citation allocator)
  -> formal-medium: Chapter4ViewModel (all deterministic display rows)
  -> formal-thin: shared annual selector + existing broker/external adapters
  -> renderer (paragraph formatting only; no annual selector or external slice)
  -> inline footnotes + one global citation table
```

MaterialSnapshot 是完整 read-model；Chapter4ViewModel 是 formal-medium 的成品 display contract，共享 annual selector 是 formal-thin 4.1 的 display contract。不得把被 display budget 隐藏的 row 从 snapshot、memo、knowledge 或 coverage diagnostics 删除。

## 4. Editorial Selection Contract

### 4.1 Annual rows

保留现有 annual admission、segment rejection 和 exact/containment dedupe；在同一个 `select_annual_display_rows()` 内增加 role-aware editorial ranking 与预算，不新增第二 selector。

展示预算仅作用于 4.1：

| render role | max rows | purpose |
|---|---:|---|
| `business_structure` | 3 | 一条画像，最多两条补充业务/竞争位置 |
| `operating_progress` | 2 | 报告期经营变化 |
| `market_competition_outlook` | 1 | 与公司明确关联的管理层市场判断 |
| `technology_product_progress` | 2 | 研发、验证、量产和产品进展 |
| `financial_quality_explanation` | 3 | 财务事实及变化原因 |

总预算最多 11 rows。它不是 producer、memo 或 snapshot 上限。

同 role 的确定性排序依次比较：

1. `argument_complete=True`；
2. 有有效 citation；
3. 含因果解释、报告期变化、具体数字单位、产品/客户动作等具体证据；
4. 正文完整且不过度冗长；
5. 原 source order，保证结果稳定。

排序规则只使用通用文本结构，不添加股票、代码、行业或产品专用 hardcode。未入选 rows 只记录 `annual_hidden_by_editorial_budget` diagnostics。

### 4.2 Broker rows

把 renderer 的 `[:6]` / `[:2]` 迁入 Chapter4ViewModel：

- 最多 5 条非风险观点；第一轮每个 attribution 保留一条，再按原顺序补足；
- 最多 2 条 broker risk；
- exact normalized body 重复只保留一条；
- attribution 为空的 row 继续不准入。

renderer 不再决定显示条数。

以上预算只适用于 formal-medium ViewModel。formal-thin 继续使用既有 broker memo renderer，不新增另一套 broker selector 或重编号路径。

### 4.3 External rows

- 继续使用 citation-identity ref dedupe；
- 仅做 exact body + citation identity 去重，不使用 fuzzy/token/embedding 相似度；
- 不新增 hard row cap，不以 dead-number slice 丢弃彼此独立的外部变量；
- 去重后的 rows 保持 source order，后续 freshness 扩充仍由同一 view-model contract 承接；
- 保留“不参与评分、风险评分或目标价”声明。

formal-medium 从 ViewModel 读取上述 rows；formal-thin 继续读取既有 curated external display，但必须移除 narrative/reasoning/topic-group 路径中的 `[:N]` 展示截断，并使用同一 exact body + citation identity 契约。不得借此改变 external citation offset。

### 4.4 Price-path rows

4.4 继续只取 annual / broker / external 各一条，并且只能从 4.1–4.3 已入选 display rows 中产生。不得 fallback 到 snapshot 中已隐藏 row，也不得修改目标价、评分、风险评分或最终推荐。

## 5. Renderer Contract

### 5.1 4.1 official material

输出顺序：

1. 一句话业务画像；
2. 业务结构与竞争位置；
3. 经营驱动；
4. 研发与产品进展；
5. 财务质量。

每组输出一个短段落，不使用 Markdown table，不逐 row 生成 bullet。每个 row 保留原文和自己的 inline citation；renderer 只连接句子，不生成新的数字、主体、因果或“投研含义”。portrait row 不在业务段落重复。

### 5.2 4.2 broker material

- “机构共识”改为简短导语；
- 每个机构/假设用 attribution 明确的短段落表达；
- 主要分歧/反方约束独立成段；
- 删除通用重复验证话术，不改写机构事实或预测。

### 5.3 4.3 external Preview

- 保持变量标题 + 完整外部论点段落；
- 不再重复每行验证模板；
- 不进入 4.1，不参与任何评分路径。

### 5.4 4.4 conditions

以三段短文本表示 `官方确认 / 机构假设 / 外部待验证`。只使用 view-model rows；确定性条件文案不得声称已发生，不生成新目标价。

## 6. Citation and Layout Contract

新版 formal-medium 与 formal-thin paths：

- 保留每条事实后的 inline footnote；
- 只保留 Chapter 4 末尾全局 `## 引用来源`；
- 删除 `**本节引用来源：**` 重复列表；
- formal-rich legacy body 与其局部来源行为不变。

formal-thin 必须以 full snapshot 计算 broker/external offset。测试必须覆盖“最高 annual ref 被 editorial budget 隐藏”场景，证明 broker/external 编号不漂移、不碰撞，无 missing/unused/orphan。

## 7. Source Intake Display Contract

`SourceIntakeEvidenceRenderer.render()` 首先检查：

```text
source_intake_enabled == True
and source_intake_render_section == True
```

否则返回空字符串。`source_intake_render_details` 仍只控制整节启用后的明细内容，不改变语义。`ReportAssemblySkill.RENDERERS` 顺序保持不变，不在 assembly 新增特殊分支。

## 8. Scope

允许修改 runtime：

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`

允许修改 tests：

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_source_intake_evidence_renderer.py`
- 必要时仅为 assembly 行为断言修改 `tests/reporter/test_assembly_skills.py`

禁止修改：

- annual/broker/external producer、memo producer 和 knowledge notes；
- `report_quality.py`、profile 判定和 citation allocator；
- scoring、target、risk、technical、recommendation；
- `KnowledgeSynthesizer` 或任何 LLM prompt；
- data、knowledge、reports。

runtime 净增目标 `<= +80`，硬停止 `> +140`。tests/docs 不计入 runtime 预算。实现应通过删除 renderer 内 slice/dedupe/local-source-list 逻辑抵消 read-model 增量。

## 9. Required Tests

### Read-model

1. snapshot rows 数量和 citation map 在 selection 前后完全不变。
2. annual 五个 role 按预算选取，排序稳定，未入选 rows 进入 diagnostics。
3. 每个 role 候选不足时不填充其他 role，不生成占位 row。
4. broker attribution diversity first-pass 生效，风险最多两条，renderer 不再 slice。
5. formal-medium 与 formal-thin 的 external exact body + citation identity dedupe 生效；超过六条的独立 rows 仍全部保留，不被 hard cap 或 fuzzy 误删。
6. 4.4 只来自已选 annual/broker/external rows。

### Renderer/profile

1. formal-medium 4.1–4.4 使用短段落，不出现目标 table 或 bullet wall。
2. formal-thin 通过同一个 `select_annual_display_rows()` 使用 annual editorial rows；4.2/4.3 保留既有来源层、offset 和标题，不要求构造完整 ViewModel。
3. formal-rich legacy headings/body 不变。
4. 4.2 所有机构事实/预测保留 attribution。
5. 4.3/4.4 disclaimer 明确且低信用源不进入 4.1。
6. 新路径不出现 `本节引用来源`，全局来源完整。
7. visible citations 无 missing、unused、unknown、malformed。
8. formal-thin 最高 annual ref 被隐藏后，broker/external refs 与 full snapshot offset 保持一致。

### Source Intake

1. `source_intake_enabled=True` 但未设置 section flag 时整节不显示。
2. `source_intake_render_section=True` 时来源概览恢复。
3. `source_intake_render_details` 仍只控制明细。
4. assembly renderer order 不变，intake context 不被删除。

## 10. Failure Modes

| Failure | Symptom | Gate |
|---|---|---|
| display budget 误删源材料 | snapshot/memo rows 数量下降 | snapshot immutability test |
| renderer 仍有第二套 cap | view-model row 可见但成稿丢失 | exact row-to-render integration test |
| formal-thin 用 selected refs 算 offset | broker/external refs 漂移或碰撞 | highest-hidden-annual-ref test |
| 移除局部来源后全局来源缺失 | missing/unused/orphan footnotes | citation alignment tests |
| broker attribution 丢失 | 机构观点写成官方确认 | attribution gate fixture |
| external 泄漏 4.1 | 微信/知乎出现在官方区 | source-boundary test |
| Source Intake 开关误关采集 | ctx/material items 消失 | renderer-only flag test |
| formal-rich 被新排版影响 | 旧标题或 local source list 消失 | formal-rich regression test |

## 11. Stop Conditions

- 需要新增 LLM memo 或修改 prompt；
- 需要修改 full snapshot citation allocator 或 formal-thin offset 公式；
- 需要改 producer/memo 才能达到展示效果；
- 需要股票/行业专用 hardcode；
- formal-rich legacy body 发生变化；
- citation gates 出现无法解释的 missing/unused/malformed；
- runtime 净增超过 `+140`。

## 12. Acceptance

实现测试通过后，必须重新生成非 stale 的中际旭创和复旦微电报告：

- 中际保持 `formal_medium`；
- 复旦保持 `formal_thin_external_rich`；
- Chapter 4 由短段落组成，Source Intake 正文默认不可见；
- quality/source/prose/CI/diff-check 通过；
- 无 citation missing/unused/unknown/malformed；
- 不产生代码、配置、prompt 或 material notes 的意外改动。

## 13. Design Delta

Accepted：

- 在现有 `Chapter4ViewModel` 中完成 display budgeting；
- formal-thin offset 继续基于 full snapshot；
- 新增独立 Source Intake section display flag；
- 新路径移除重复局部来源表。

Rejected：

- renderer-only filters：会形成第二 selector；
- 新增 LLM editorial memo：当前确定性能力足够，且扩大引用风险；
- producer 过滤：会破坏材料保全；
- fuzzy semantic dedupe：无稳定、可审计契约。

Deferred：

- freshness adaptation：Roadmap Batch 4；
- 全局章节编号和资源路径：Batch 5；
- pack-first knowledge persistence：Batch 6。

R2 required：仅当 Round 1 存在 blocker、未关闭 must-fix、要求改变 citation/profile 边界，或 runtime 预算被证明不可行时为 `yes`。
