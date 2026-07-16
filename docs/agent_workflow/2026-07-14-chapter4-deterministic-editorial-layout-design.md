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

当前没有可复用的整节 display toggle。本批新增 `source_intake_render_section`：默认 `False`；只有显式设为 `True` 时才输出 Source Intake 正文章节。正式入口可以通过 `source_intake_config.render_section` 恢复，顶层 `source_intake_render_section` 作为测试/preview 的显式 override，且优先级更高。intake context、material items 和 sidecar 行为不变。

`periodic_report_fulltext_preview.py --source-intake-section` 是既有显式展示入口。它必须在构造 ctx 时写入顶层 `source_intake_render_section=True`，否则默认隐藏会破坏现有 preview 契约。

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

`business_structure` 的 3 个槽位中，如果存在合格业务画像，必须先保留最高分画像并标记 `editorial_slot="portrait"`，再填另外两个槽位。画像 predicate/score 从 renderer 的 `_select_annual_portrait_row()` 迁入 shared annual selector；renderer 删除该选择逻辑，只读取 `editorial_slot`。没有合格画像时不生成占位文本，三个槽位正常用于其他业务 rows。

画像保留后，同 role 的确定性排序使用以下 tuple，降序比较，最后以原输入 index 升序打破平局：

1. `argument_complete=True`；
2. 有有效 citation；
3. evidence signal count：因果词、报告期/同比环比、数字单位、产品/客户动作四类各计 1 分；
4. compact body 长度在 24–320 字之间；
5. 超过 320 字的长度惩罚；
6. 原 source order，保证结果稳定。

四类 evidence signals 只使用通用 token/regex：`主要系/由于/受益于/导致/所致`；`报告期/同比/环比/年度/20xx/Q1-Q4`；百分比及元/万元/亿元/倍等数字单位；`出货/量产/验证/导入/客户/推出/发布/订单/扩产`。不得添加股票、行业或具体产品词。

现有 `annual_selected_count` 保持“admission + dedupe 后数量”的旧语义，避免静默破坏测试/诊断调用方。新增 `annual_display_count`、`annual_hidden_by_editorial_budget_count` 和 `annual_hidden_by_role`；未入选 rows 不从 snapshot 删除。

### 4.2 Broker rows

把 renderer 的 `[:6]` / `[:2]` 迁入 Chapter4ViewModel：

- 最多 5 条非风险观点；第一轮每个 attribution 保留一条，再按原顺序补足；
- 最多 2 条 broker risk；
- exact normalized body 重复只保留一条；
- attribution 为空的 row 继续不准入。

renderer 不再决定显示条数。

以上预算只适用于 formal-medium ViewModel。formal-thin 继续使用既有 broker memo renderer，不新增另一套 broker selector 或重编号路径。

本批不输出“机构共识”：producer 的 title 来自固定 family map，标题相同只能证明关注主题相同，不能证明观点方向、盈利区间或论据一致。renderer 删除 `_broker_consensus_sentence()`；只允许输出“机构关注重点”。关注重点从已选 display rows 的 title 中按 source order 去重，排除空标题及 `券商观点/券商核心观点/机构核心观点/产业与产品判断/盈利预测/盈利预测与估值假设/风险提示/反方约束/估值方法` 等固定 family title；没有非通用 title 时省略该摘要块，直接输出逐机构 attribution 段落。formal-thin 的 `forecast_ranges` 也必须经现有 attribution normalizer 输出 `某机构研报预计` 或至少 `研报预计`，不得裸写预测区间。

### 4.3 External rows

- MaterialSnapshot 继续保留 narrative paragraphs、reasoning cards 和 topic groups 三套原始投影；display 先分别完成可见性准入与 exact dedupe，再选择第一个非空投影，优先级固定为 `narrative_paragraphs` → `reasoning_cards` → `topic_groups`，避免把同一外部材料的替代视图当成独立观点重复展示；
- 继续使用 citation-identity ref dedupe；
- 仅做 exact body + citation identity 去重，不使用 fuzzy/token/embedding 相似度；
- 不新增 hard row cap，不以 dead-number slice 丢弃彼此独立的外部变量；
- 去重后的 rows 保持 source order，后续 freshness 扩充仍由同一 view-model contract 承接；
- 保留“不参与评分、风险评分或目标价”声明。

formal-medium 从 ViewModel 读取上述 rows；formal-thin 继续读取既有 curated external display，但必须移除 narrative/reasoning/topic-group 路径中的 `[:N]` 展示截断，并使用同一 exact body + citation identity 契约。不得借此改变 external citation offset。

唯一 dedupe key helper 放在 `deep_analysis_material_snapshot.py`：`(normalized_exact_body, sorted_unique_citation_identities)`。body 只归一化 whitespace 和结尾标点；citation identity 复用现有 `citation_identity()`。只有完整 key 相同才删除 row：同源不同 body、同 body 不同来源都保留。formal-medium MaterialRows 与 formal-thin curated dict rows 必须复用这个 helper，不各写一套近似规则。

external projection 的 eligible 条件固定为：正文非空、至少一个 citation ref 能映射到 citation metadata、且不进入 scoring/risk 路径。三套 projection 必须先各自过滤并按 shared key 去重，再调用同一个“first non-empty projection” helper。raw narrative list 存在但全部缺正文或有效引用时，必须继续 fallback 到 eligible reasoning cards；reasoning 同样为空时再 fallback topic groups。不得因为 raw collection 非空就提前停止，也不得混合两套 projection。

### 4.4 Price-path rows

4.4 继续只取 annual / broker / external 各一条，并且只能从 4.1–4.3 已入选 display rows 中产生。不得 fallback 到 snapshot 中已隐藏 row，也不得修改目标价、评分、风险评分或最终推荐。formal-thin 仍保持三段式，不新增 4.4。

每个来源层必须先从 4.1–4.3 visible rows 中过滤 `_is_informative_variable_title(row.title)=True` 的候选，再应用选取优先级：

- annual：先排除 portrait，再按 `operating_progress` → `financial_quality_explanation` → `technology_product_progress` → `market_competition_outlook` → `business_structure`；每个 role 内先取 `argument_complete=True`；
- broker：`broker_assumption` → `broker_forecast`，要求 attribution；
- external：去重后的 source order 第一条。

title filter 必须发生在 role/source-order selection 之前。某层第一条 visible row 是泛标题时，不能直接省略该层；只要同层后续 visible row 有合格 title，就继续按上述优先级选择该 row。仍不得读取 snapshot hidden rows。

4.4 不再复写 4.1–4.3 的完整 body。每个来源层只输出“来源层级 + `_is_informative_variable_title(row.title)` 验证通过的 title + inline citation + 上下行验证条件”一段；条件只能表达“若被正式证据验证/证伪则观点升级/降级”，不得重复长摘录或产生新的经营事实。

`_is_informative_variable_title()` 只折叠 whitespace、移除结尾标点，然后对以下完整 exact deny-list 判断，不使用 fuzzy/token/semantic 规则：空字符串、`外部变量`、`外部观察`、`主营业务与产品`、`产业与产品判断`、`机构核心观点`、`盈利预测`、`反方约束`、`风险提示`、`业务覆盖 / 产品线`、`经营变化`、`市场与竞争`、`管理层判断与行业展望`、`研发与产品进展`、`技术与产品进展`、`财务质量`、`产品放量 / 盈利弹性`、`供应链 / 技术路线`、`反方风险`。只有非空且不在 deny-list 中的原 row title 才返回 True。

4.4 不能用 role fallback 把空泛变量凑成三段。没有合格 title 的层级直接省略，不得回退到 snapshot hidden row、不得截取 evidence body 另造标题，也不得使用泛标签输出模板化条件句。因此 4.4 可以输出一至三段；三层均无合格 title 时只输出固定 fallback：`当前已选材料缺少可用于条件推演的具体变量标题，本节不形成方向推演。`，不附加新事实或引用。

## 5. Renderer Contract

### 5.1 4.1 official material

输出顺序：

1. 一句话业务画像；
2. 业务结构与竞争位置；
3. 经营驱动；
4. 研发与产品进展；
5. 财务质量。

每组输出一个短段落，不使用 Markdown table，不逐 row 生成 bullet。每个 row 保留原文和自己的 inline citation；renderer 只连接句子，不生成新的数字、主体、因果或“投研含义”。带 `editorial_slot="portrait"` 的 row 输出为一句话画像且不在业务段落重复；renderer 不再自行搜索画像。

### 5.2 4.2 broker material

- 不输出“机构共识”；有非通用 title 时输出“机构关注重点”，否则省略摘要块；
- 每个机构/假设用 attribution 明确的短段落表达；
- 主要分歧/反方约束独立成段；
- 删除通用重复验证话术，不改写机构事实或预测。

### 5.3 4.3 external Preview

- 新 layout 的固定语法是独立一行 `**变量标题**`，其后跳过空行的第一行必须是普通观点段落；不得是 heading、table、blockquote 或 list bullet。该段必须带 inline footnote；
- 不再重复每行验证模板；
- 不进入 4.1，不参与任何评分路径。

### 5.4 4.4 conditions

以最多三段短文本表示 `官方确认 / 机构假设 / 外部待验证`。只使用有具体变量标题的 view-model rows，不重复完整 evidence body；确定性条件文案不得声称已发生，不生成新目标价。没有任何合格 row 时使用 4.4 固定 fallback。

## 6. Citation and Layout Contract

新版 formal-medium 与 formal-thin paths：

- 保留每条事实后的 inline footnote；
- 只保留 Chapter 4 末尾全局 `## 引用来源`；
- 删除 `**本节引用来源：**` 重复列表；
- formal-rich legacy body 与其局部来源行为不变。

formal-thin 必须以 full snapshot 计算 broker/external offset。测试必须覆盖“最高 annual ref 被 editorial budget 隐藏”场景，证明 broker/external 编号不漂移、不碰撞，无 missing/unused/orphan。

删除局部来源表后，现有 `_check_curated_external_inline_footnotes()` 不能再以“存在本节引用来源”为前置条件。本批将 gate 改为同时支持：

- legacy：沿用局部来源表 + body inline footnote 检查；
- new layout：只在 4.3 external Preview section 的 body（不含全局 `## 引用来源`）扫描所有 standalone `**变量标题**`。每个 title 后跳过空行的第一行必须是普通观点段落，并且必须包含完整 `[^n]`。任一 pair 缺段、使用 list/table/heading 代替段落、或缺 footnote，均报 `curated_external_missing_inline_footnotes`。

“当前未取得足够外部观点材料”等 fallback 不含变量标题，故不视为观点段落。gate 必须逐 pair 扫描，不能只验证第一条；正常多位数 `[^10]` 仍是有效 footnote。这样即使 `_visible_citations_only()` 同步移除了漏挂引用，也不能让无脚注的外部观点错误 PASS。

## 7. Source Intake Display Contract

`SourceIntakeEvidenceRenderer.render()` 先解析整节显示开关：

```text
if "source_intake_render_section" in ctx:
    render_section = bool(ctx["source_intake_render_section"])
else:
    render_section = bool((ctx.get("source_intake_config") or {}).get("render_section", False))

source_intake_enabled == True and render_section == True
```

否则返回空字符串。`source_intake_render_details` 仍只控制整节启用后的明细内容，不改变语义。`ReportAssemblySkill.RENDERERS` 顺序保持不变，不在 assembly 新增特殊分支。

正式报告默认不配置 `render_section`，因此隐藏；需要 debug 时可在 stock 的 `source_intake` config 中设置 `render_section: true`。`periodic_report_fulltext_preview.py --source-intake-section` 必须显式写顶层 override，以继续展示 preview。

## 8. Scope

允许修改 runtime：

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
- `scripts/utils/report_quality.py`（仅更新 external inline-footnote gate）
- `scripts/previews/periodic_report_fulltext_preview.py`（仅传入显式 section override）

允许修改 tests：

- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_source_intake_evidence_renderer.py`
- `tests/reporter/test_report_quality.py`
- `tests/reporter/test_periodic_report_fulltext_preview_script.py`
- 必要时仅为 assembly 行为断言修改 `tests/reporter/test_assembly_skills.py`

禁止修改：

- annual/broker/external producer、memo producer 和 knowledge notes；
- profile 判定和 citation allocator；
- scoring、target、risk、technical、recommendation；
- `KnowledgeSynthesizer` 或任何 LLM prompt；
- data、knowledge、reports。

runtime 净增目标 `<= +80`，硬停止 `> +140`。tests/docs 不计入 runtime 预算。实现应通过删除 renderer 内 slice/dedupe/local-source-list 逻辑抵消 read-model 增量。

## 9. Required Tests

### Read-model

1. snapshot rows 数量和 citation map 在 selection 前后完全不变。
2. annual 五个 role 按预算选取，排序 tuple 稳定；存在 portrait candidate 时保留并标记唯一 portrait slot，renderer 不再重选。
3. 每个 role 候选不足时不填充其他 role，不生成占位 row。
4. `annual_selected_count` 保持 admission/dedupe 旧语义；新增 display/hidden diagnostics 与实际 rows 对齐。
5. broker attribution diversity first-pass 生效，风险最多两条，renderer 不再 slice。
6. 无论多少 attribution 共享固定 family title，都不得输出“机构共识”；非通用 title 去重后可输出“机构关注重点”，全部为通用 title 时省略摘要块。
7. formal-thin forecast range 带 `研报预计` attribution。
8. MaterialSnapshot 同时保留三套 external projections，但 display 在各 projection 完成 eligible 过滤和 exact dedupe 后，固定选择第一个非空的 narrative → reasoning → topic，只展示一套；raw narrative 不可展示时必须 fallback reasoning。
9. shared external dedupe key 被两条 profile 路径复用；同 key 去重，同源不同 body、同 body 不同来源均保留。
10. formal-medium 与 formal-thin 超过六条的独立 external rows 全部保留，不被 hard cap 或 fuzzy 误删。
11. 4.4 只来自已选 rows，先执行 informative-title filter，再按固定 role/source-order 优先级选取，排除 portrait且不复写完整 body；测试覆盖 annual/broker/external 各层“泛标题在前、具体标题在后”仍选择具体 row。4.4 可输出一至三段，全部被拒绝时只输出固定 fallback。

### Renderer/profile

1. formal-medium 4.1–4.4 使用短段落，不出现目标 table、bullet wall 或 4.1–4.3 长 body 在 4.4 的重复展开。
2. formal-thin 通过同一个 `select_annual_display_rows()` 使用 annual editorial rows；4.2/4.3 保留既有来源层、offset 和标题，不要求构造完整 ViewModel。
3. formal-rich legacy headings/body 不变。
4. 4.2 所有机构事实/预测保留 attribution。
5. 4.3/4.4 disclaimer 明确且低信用源不进入 4.1。
6. 新路径不出现 `本节引用来源`，全局来源完整。
7. visible citations 无 missing、unused、unknown、malformed。
8. formal-thin 最高 annual ref 被隐藏后，broker/external refs 与 full snapshot offset 保持一致。
9. 新 external title/body pair 漏掉 inline footnote、第二个或后续 pair 漏 footnote、或以 bullet/table/heading 代替普通段落时，`curated_external_missing_inline_footnotes` 报 error；正常多位数 footnote 与 legacy local-source layout 均通过。

### Source Intake

1. `source_intake_enabled=True` 但未设置 section flag 时整节不显示。
2. `source_intake_config.render_section=True` 时来源概览恢复；顶层 `source_intake_render_section=False` 可以显式覆盖 nested config。
3. 顶层 `source_intake_render_section=True` 时来源概览恢复。
4. `source_intake_render_details` 仍只控制明细。
5. `periodic_report_fulltext_preview.py --source-intake-section` 继续输出整节。
6. assembly renderer order 不变，intake context 不被删除。

## 10. Failure Modes

| Failure | Symptom | Gate |
|---|---|---|
| display budget 误删源材料 | snapshot/memo rows 数量下降 | snapshot immutability test |
| business budget 挤掉画像 | 有业务 rows 但“一句话画像”缺失 | portrait reservation test |
| renderer 仍有第二套 cap | view-model row 可见但成稿丢失 | exact row-to-render integration test |
| `annual_selected_count` 被静默改义 | diagnostics 与历史契约不兼容 | diagnostics compatibility test |
| formal-thin 用 selected refs 算 offset | broker/external refs 漂移或碰撞 | highest-hidden-annual-ref test |
| 移除局部来源后全局来源缺失 | missing/unused/orphan footnotes | citation alignment tests |
| 移除局部来源后 external 漏挂脚注却 PASS | 变量观点无 `[^n]` 且全局表同步消失 | new-layout inline-footnote gate |
| broker attribution 丢失 | 机构观点写成官方确认 | attribution gate fixture |
| 固定 family title 被误写成共识 | 不同机构共享 producer 分类标题却被声称观点一致 | no-title-only-consensus test |
| 4.4 复写长摘录 | 4.1–4.3 body 在 4.4 再次展开 | no-body-repetition test |
| 4.4 泛标题生成模板化推演 | `外部变量/机构核心观点` 等默认标题进入条件段 | informative-title deny-list tests |
| 4.4 泛标题遮蔽后续具体变量 | 第一条标题被拒后整层消失，后续具体 row 未被选择 | filter-before-priority tests |
| raw narrative 阻断有效 fallback | narrative 存在但不可展示，reasoning 有效却输出空地图 | first-eligible-projection test |
| external 泄漏 4.1 | 微信/知乎出现在官方区 | source-boundary test |
| Source Intake 开关误关采集 | ctx/material items 消失 | renderer-only flag test |
| Source Intake preview 被默认隐藏 | `--source-intake-section` 无正文 | preview regression test |
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
- 在 shared annual selector 中保留并标记 portrait，删除 renderer 二次画像选择；
- formal-thin offset 继续基于 full snapshot；
- broker 只输出“机构关注重点”，删除无法由固定 family title 证明的“机构共识”；
- external 两条 profile 路径复用 exact body + citation identity key，按首个 eligible 非空投影选择且不设 hard cap；
- 4.4 先执行 exact informative-title gate，再按固定 selected-row priority 选择，只展示具体变量与条件，不复写长摘录；
- 新增独立 Source Intake section display flag，并保留正式 config 与 preview 的显式恢复路径；
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
