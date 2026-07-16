# Chapter 4 External Incremental Ownership Design

日期：2026-07-15
范围：Batch 5C，Chapter 4 的外部 Preview 只展示相对于官方材料与机构假设的新增变量。

## 背景与问题

20260715 的中际旭创与复旦微电报告已经完成来源分层、引用卫生和 paragraph-level 可读性处理，但 advisory prose gate 仍看到 4.1 / 4.2 / 4.3 的主题词交叉。

这不代表外部材料应被一律删除。例如中际的“800G 交付传言、光芯片供给、公司回应”和 “NPO/XPO 量产路径”虽然带有已在上层出现的速率或技术词，却分别增加了交付风险与新技术路线变量。相反，外部材料若仅复述官方产品范围、已披露财务数字或机构盈利假设，不应在 4.3 再展开。

本批的目标是让 4.3 成为“新增变量”的 Preview，而不是第三次复述业务、产品或业绩背景。

## 目标

1. 在已有 `MaterialSnapshot` 上做唯一的 deterministic external incremental projection；不改变 annual / broker / external producer 或原始材料。
2. `formal_medium` 和 `formal_thin_external_rich` 的 4.3 使用同一投影规则。
3. 保留具有新增可验证事件、量化差异或技术/产品机制的外部观察，即使它与 4.1 / 4.2 共享主题词。
4. 删除或不显示仅重述上层已展示内容的外部行。
5. 不改 formal-thin full-snapshot citation offset 公式；可见引用仍由最终 Markdown 反查，保持 missing / unused / 未知为零。

## 非目标

- 不使用 LLM、embedding、文本相似度、模糊 token-overlap 或重新采集。
- 不更改外部 claim 的 producer / composer、freshness policy、source credit、profile、评分、目标价、风险、技术面、推荐、LLM prompt 或硬质量门。
- 不把外部材料升级到 4.1、4.2、核心事实、执行摘要的确认事实或评分输入。
- 不改变 `formal_rich` 的旧渲染路径。

## 数据与职责

`deep_analysis_material_snapshot.py` 是唯一的选择 owner：

- 输入：完整 `MaterialSnapshot.rows` 与 snapshot citations；
- owner rows：已经选中的 annual display rows 与 broker display rows；
- 输出：只含可见、Preview-only、且具有增量依据的 external `MaterialRow`；
- renderer：只负责将已选 row 格式化成现有 paragraph blocks 与 citation marker，不重新判断主题或重算 offset。

保留的 `MaterialRow.diagnostics` 允许附加 display-only 的 `external_incremental_reason`。被拒绝行只进入 selection diagnostics 计数，不伪造一张不可见 row；这些字段不会进入评分或来源 metadata。

## 单一准入算法

新增公开函数（名称可按实现局部调整）：

```python
select_incremental_external_display_rows(
    rows: Iterable[MaterialRow],
    citations: Mapping[int, Any],
    owner_rows: Iterable[MaterialRow],
) -> tuple[tuple[MaterialRow, ...], dict[str, Any]]
```

步骤严格如下：

1. 复用现有 external eligibility、bucket priority（narrative paragraphs → reasoning cards → topic groups）和 exact citation-identity dedupe。不得新增第二 selector。
2. 为 owner rows 建立规范化 body、主题上下文与具体锚点集合。主题上下文复用 `deep_analysis_topic_ownership.matching_topic_families()`，并补充“双方共享同一具体锚点”这一窄条件；不得新增第二套完整主题 taxonomy。锚点统一为小写，body-only 提取，只包括：
   - 阿拉伯数字连接 `%`、`亿元`、`万元`、`亿`、`万`、`倍`、`家`、`款`、`G`、`T`、`Gbps`、`TOPS` 等显式单位；
   - `20xx` / `20xxQn` 这类显式期间；
   - 同时含字母和数字的产品/技术代码，例如 `800G`、`1.6T`、`A2000`；
   - 2-8 位英文大写技术缩写，例如 `CPO`、`NPO`、`XPO`、`FPGA`。
3. 文本重复只比较 body，不以通用 title 判重。去掉 `外部材料称/认为/提示` 等显示 attribution、citation marker、空白和句末标点后：
   - exact equality 总是拒绝；
   - 仅当 external body 长度不少于 24 个规范化字符，且 **external body 完整包含在 owner body 中** 时拒绝；
   - owner body 包含在更长的 external body 中不能据此拒绝，因为 external 后半段可能正是新增条件。
4. 对未被 literal duplicate 拒绝的 external row，先找出与该 row 共享 family 或具体锚点的 owner rows；只和这些 comparable owners 比较：
   - 若不存在 comparable owner，保守保留，reason=`new_topic_context`。这一 fail-open 分支避免因现有主题 taxonomy 不覆盖某行业而错误丢失独立外部观察。
   - 若 external 有任一具体锚点不在 comparable owner anchors 中，保留，reason=`new_concrete_anchor`。
   - 否则若 external 含一个 comparable owner 未出现的显式变量事件词，保留，reason=`new_event_variable`。事件词仅限：`传言`、`否认`、`回应`、`下调`、`上调`、`短缺`、`紧张`、`瓶颈`、`缺口`、`供应链`、`交付`、`订单`、`认证`、`验证`、`量产`、`制裁`、`政策`、`停产`、`延期`、`延后`、`提前`、`调整`、`替代`、`降价`、`涨价`、`分歧`、`唯一`、`首家`、`率先`。
   - 否则拒绝，reason=`owner_theme_without_delta`。
5. 共享主题词本身不构成删除依据；只有“共享上下文 + 没有任何新增锚点/事件”才能拒绝。
6. bucket priority 在 incremental admission 之后生效：按 narrative paragraphs → reasoning cards → topic groups 检查；若一个 bucket 的候选全部被拒绝，继续尝试下一个 bucket。返回第一个仍有 selected rows 的 bucket。不得在 renderer 再做 fallback selection。
7. 选择后继续使用现有 citation-ref identity dedupe；不得修改 citation metadata、snapshot ref 或 offset。

这不是语义相似度。删除条件仅有 literal duplicate，或“共享确定性上下文且不存在新增具体/事件锚点”；上下文无法比较时宁可保留 Preview，也不静默丢材料。

## Profile 接入

### formal_medium

`build_chapter4_view_model()` 在选出 annual/broker rows 后，调用上述函数生成 4.3 rows；4.4 继续从这一结果中选择外部变量。现有 `Chapter4ViewModel.citations` 计算不变。

这里的 owner rows 必须恰好是 formal-medium 实际渲染的 annual rows 与 `_select_broker_display_rows()` 结果；未展示的 snapshot row 不得压掉 4.3。

### formal_thin_external_rich

保留 render 时已有 full snapshot 和以下 offset：

```text
annual offset   = baseline max ref
broker offset   = annual offset + max(snapshot annual refs)
external offset = annual offset + max(snapshot annual ∪ broker refs)
```

仅 `formal_thin_layout_variant == "annual_broker_external_checklist"` 接入新路径；其他 legacy thin variant 不在本批变化范围。

在 renderer 取得 `annual_material_rows`、snapshot broker rows 与 snapshot external rows 后，调用同一 snapshot selector。formal-thin 的 4.2 当前渲染 memo 中全部 `sections / forecast_ranges / risks`，所以 owner broker rows 必须是 snapshot 中全部可渲染 broker rows，不能套用 formal-medium 的 5+2 selection。未在 formal-thin 4.2 可见的 broker row 不得成为 owner。

snapshot allocator 已经把 annual / broker / external local refs 映射成 snapshot-global refs，所以 MaterialRow 路径必须用：

```text
visible ref = row.citation_ref + chapter4_citation_offset
```

绝不能再加 `external_citation_offset`，否则 external snapshot ref 会二次偏移。原有 `external_citation_offset` 只保留给仍消费 local curated-display refs 的 legacy/formal-rich 路径。

不得把 formal-thin 的 citations 改回 local `deep_analysis_display` 合并，不得从 selector 内重建 citations。最终仍由当前 `material_snapshot.citations` 与 `_visible_citations_only()` 反查全局引用表。

`formal_rich` 继续使用 `_curated_external_display_projection()`，完全不进入新路径。annual-broker formal-thin 的 4.3 必须停止调用该 projection；代码审计只允许 formal-rich/legacy thin 保留它。

若 selection 后 external rows 为空：

- 4.3 明确写“当前外部材料未提供相对正式材料或研报的新增待验证变量”；
- formal-medium 4.4 不生成“外部待验证”条目，也不得回退未经 selection 的 raw external row；
- annual / broker 条件推演继续照常输出。

## Prose Warning 的边界

`report_prose_quality.py` 的 `repeated_theme_across_sections` 是词表式 advisory checker，无法区分“800G 产品背景”与“800G 交付传言”。本批不通过删除合法增量行来追求零 warning。

本批不改 prose checker。完成后若 report 仅因 4.3 的 `new_concrete_anchor` / `new_event_variable` 行出现主题词 warning，将其记录为 checker false positive，另开一个质量门小批次；不能在本批内放宽 warning 以掩盖 selection 问题。

## 测试矩阵

| 场景 | 断言 |
|---|---|
| official row 与 external body 完全相同 | external 不进入 4.3，rejection count 记录 `owner_text_duplicate` |
| external 先复述 official、后追加新的交付条件 | external 保留，不能因 owner body 被 external 包含而误删 |
| official 已有 800G，external 追加 `1500 万→1200 万、光芯片短缺` | external 保留，reason `new_concrete_anchor` 或 `new_event_variable` |
| official 已讨论 CPO，external 讨论 NPO/XPO 时间表 | external 保留，reason `new_concrete_anchor` |
| 无数字/缩写但有“客户认证仍待验证” | external 保留，reason `new_event_variable` |
| 同一主题/代码但无新锚点与事件 | external 不进入 4.3，reason `owner_theme_without_delta` |
| 无共享上下文的独立短观察 | 保守保留，reason `new_topic_context` |
| narrative bucket 全部重复、reasoning bucket 有新增变量 | 继续到 reasoning bucket，并只展示其 selected rows |
| formal-medium selected refs | 4.3 visible refs 都在 ViewModel citations 中，no missing/unused |
| formal-thin annual/broker/external | snapshot row 只加 baseline/chapter4 offset，所有 4.3 refs 有全局来源且没有 `未知`；未选 external ref 不进全局表 |
| formal-thin 所有 external 被拒绝 | 4.3 显示“当前外部材料未提供相对正式材料或研报的新增待验证变量”，而非误报采集不足 |
| formal-thin 有 7 条以上可见 broker rows | 所有实际可见 broker rows 都参与 owner 比较，不使用 formal-medium 5+2 subset |
| formal-rich | 旧 output fixture 不变 |
| formal-medium 4.4 | external 被拒绝后不出现 external 条件；保留时只能使用 4.3 selected external row |

## 失败模式与停止条件

| 失败模式 | 安全行为 | 测试 |
|---|---|---|
| 共享主题词导致误删交付/技术新变量 | 主题词不作为删除条件；新锚点或事件词保留 | 800G、NPO/XPO fixture |
| 静态外部改写仍进入 4.3 | 共享上下文且无新锚点/事件时拒绝 | shared-family fixture |
| external 长行含 owner 子句和新增条件被误删 | containment 只允许 external ⊂ owner | asymmetric containment fixture |
| formal-thin 引用 offset 变化 | selector 不触碰 offsets/citations；snapshot ref 只加 baseline offset | global citation fixture |
| fallback 过滤过强造成材料缺失 | 没有共享上下文时 fail-open | short observation fixture |
| 新 selector 与旧 selector 并存 | 只扩展 `_select_external_display_rows`，formal-thin 调用同一 public helper | call-site audit |
| 隐藏 broker row 压掉外部变量 | owner rows 按 profile 的实际可见输出构造 | visible-owner fixtures |

停止：

- 实现需要修改 producer、freshness、citation allocator/offset、report_quality、评分、目标价、风险、技术面、profile 或 prompt；
- 需要引入 semantic similarity、embedding、LLM 或行业/股票专项规则；
- formal-thin global citation regression 失败；
- 独立 runtime 目标 +80 行；超过 +120 行立即停止（测试与文档不计）。

## 验收

1. snapshot / renderer focused tests 与 report-quality/source-boundary suites通过；
2. formal-thin citation offset 回归通过；
3. 无正式报告生成、无网络、无 data/knowledge/reports 改动；
4. 执行后再由本地正式复跑验证：中际与复旦 4.3 不再展示 literal owner duplicate 或“共享上下文但无新增锚点”的复述，且引用 hygiene 维持通过。
