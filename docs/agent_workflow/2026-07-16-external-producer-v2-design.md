# External Producer v2 Design

日期：2026-07-16
分支：`codex/pipeline-stabilization`
前置 gate：Pipeline Stabilization 已完成，默认离线测试全绿。

## 1. Goal

External Producer v2 要把精选微信、知乎、雪球等低信用外部材料整理成可追溯的
“论点 + 论据 + 实体范围 + 相对正式材料/研报的增量”卡片，并改善 Chapter 4.3：

- 保留外部材料真正新增的事件、机制、分歧和同业背景；
- 拒绝把同业事实写成目标公司事实；
- 不再把 annual / broker 已拥有的主题在 4.3 大段重写；
- 同一来源、同一论点只展示一次；
- 外部材料始终是 Preview / display-only，不进入官方确认、评分、风险评分、
  目标价、推荐结论或技术判断。

本设计分为两个独立批次。Batch A 先建立确定性 v2 合约并适配现有缓存，不修改
LLM prompt；Batch B 只有在 Batch A 正式报告验收后，才修改 extractor/composer
prompt，提高原生摘录质量，并向用户展示样例确认无编造数据。

## 2. Current Failure Analysis

最新 `20260716` 报告显示：

- 中际旭创 4.3 的供应链传言、预付款和 NPO/XPO 确有增量，但 narrative 把
  `800G / CPO / NPO / XPO / 订单` 连续展开，触发 `theme_reexpanded_outside_owner`；
- 复旦微电 4.3 把收入、毛利率、估值情景重新陈述为外部增量，重复了 4.2 的
  业绩质量与估值 owner；
- 中际的完整 source quote 在 viewpoint digest，narrative 只有合成段落；复旦的
  可用 evidence 主要在 narrative reasoning cards。只读一种缓存会造成回归；
- entity filter、同源 dedupe、baseline novelty 和 display novelty 分散在 claim
  producer、narrative composer、display adapter、MaterialSnapshot 四层；
- narrative paragraph 会合并多个 claim，snapshot 只能对合并后的长正文做关键词
  判断，难以知道哪一句是 owner context、哪一句才是新增变量；
- claim 和 source excerpt 在不同层有 `160/200` 字裁剪，可能先丢论据再做选择。

根因不是 4.3 条数太多，而是缺少统一、source-faithful 的 argument-card contract，
以及 producer novelty 与 Chapter 4 display novelty 的职责没有分开。

## 3. Fixed Invariants

1. 外部材料永远保持 `preview_only`、`synthesis_display_only=True`、
   `knowledge_eligible=False`、`scoring_eligible=False`、
   `risk_score_eligible=False`。
2. 4.1 只能使用正式材料；4.2 只能把券商观点写成 attribution 明确的机构假设。
3. Batch A 不修改任何 LLM prompt，不调用网络，不要求重建现有外部缓存。
4. 不修改 profile、评分、风险、目标价、技术分析、推荐、core facts 或采集逻辑。
5. 不新增股票名、股票代码、行业专用 admission 规则；现有股票专用 theme profile
   不再扩大，也不能成为 v2 准入真源。
6. claim/evidence 不得改写为新事实。外部论据必须来自已有 `source_quote` 或
   `source_excerpt`，并保留其 citation identity。
7. MaterialSnapshot 继续保存完整 external rows；Chapter4ViewModel 只投影可见行。
8. formal-thin 的 citation offset 仍基于 full snapshot；formal-rich legacy 路径不变。

## 4. Ownership Model

### 4.1 Producer owns source truth

External Producer v2 唯一负责：

- 把 digest claim 与 narrative reasoning card 适配为统一 argument card；
- 证明论点由哪段原文支持；
- 标记目标公司、同业/行业或歧义实体范围；
- 归一化通用 topic family；
- 外部材料内部的 exact/same-source duplicate 去重；
- 保存 producer-level novelty metadata，但不决定最终 Chapter 4 是否展示。

### 4.2 Chapter4ViewModel owns display novelty

`select_incremental_external_display_rows()` 继续是相对**实际可见** annual/broker
owner rows 的唯一 display novelty selector。它消费 v2 metadata：

- `owner_relation=outside_owner`：可直接展示；
- `owner_relation=owner_delta`：只展示卡片的增量论点与对应论据；
- `owner_relation=owner_duplicate`：不展示；
- legacy row 没有 v2 metadata：走现有保守算法，作为兼容路径。

Producer 不复制 snapshot 的 owner 比较；snapshot 不再从长 narrative paragraph
重新猜实体、证据和 claim 边界。

### 4.3 Renderer owns formatting only

Renderer 可以识别 MaterialRow 上已经锁定的 v2 `claim/evidence/entity_scope` 字段，
把增量论点排成普通短段落、把逐字原文依据排成引用块；它不得选择、裁剪、合并、
重写主题或重新推断实体。legacy row 保持现有 `title/body/refs` 排版。这样完整 evidence
可以保留，而 `theme_reexpanded` 只检查编辑论点，不把逐字证据块误当成第二次分析。

## 5. Batch A: Deterministic Contract

### 5.1 Canonical card schema

新增内部 schema `curated_external_argument_card.v2`：

```python
{
  "schema_version": "curated_external_argument_card.v2",
  "card_id": "external-argument:<stock>:<source-quote-hash>",
  "stock_name": "中际旭创",
  "topic_family": "capacity_delivery",
  "entity_scope": "target | target_with_peer_context | peer_or_industry | ambiguous",
  "target_entity": "中际旭创 | ''",
  "mentioned_entities": ["..."],
  "claim": "外部观点的核心论点，未截断",
  "evidence_units": [{
    "text": "逐字 source quote/excerpt，未截断",
    "evidence_status": "source_quote_verified | cached_excerpt",
    "source_id": "...",
    "source_quote_hash": "...",
    "citation_refs": [1]
  }],
  "incremental_delta": "why_incremental 的可信、非模板化内容或空字符串",
  "baseline_overlap": "none | partial | duplicate",
  "display_title": "具体变量标题",
  "display_body": "谨慎措辞的论点与证据",
  "source_identity": ["url", "..."],
  "argument_key": "<topic-family>:<entity-scope>:<claim-anchor-hash>",
  "quality_action": "preview_only",
  "synthesis_display_only": true,
  "knowledge_eligible": false,
  "scoring_eligible": false,
  "risk_score_eligible": false,
  "verification_status": "professional_observation",
  "diagnostics": {...}
}
```

`evidence_units` 在 producer/read-model 中不设字符上限。Batch A 的显示正文使用完整句
边界选择论点和最多一个互补 evidence unit；不能用 `[:n]` 产生半句。原始 cards 仍
完整保留在缓存和 MaterialSnapshot 中。

### 5.2 Input adapters

统一 builder 接受两个可选输入：

1. `digest.claims`：首选。`source_quote` 是 `source_quote_verified` 证据，`claim` 是论点，
   `why_incremental` 是 producer-level 增量说明；
2. `narrative.reasoning_cards`：digest 缺失时使用。`source_excerpt` 是证据，
   `claim` 是论点；因 legacy narrative 未保留原 source packet，只能标记为
   `cached_excerpt`，不得宣称已重新证明逐字连续子串；
3. 只有 narrative paragraphs、没有 claim/card evidence 时，不伪造 v2 evidence。
   该 paragraph 保持 legacy display 兼容，但不得标为 v2 card。

同一 claim/card 同时存在时按 `claim_id`，再按 URL + normalized evidence hash 合并。
digest 提供 source truth，narrative card 只补充 `display_topic / verification_need`，
不得覆盖 digest 的 claim、quote、source identity 或安全字段。

`SynthesisSkill` 在 narrative display 开启、且 digest display 也明确启用时，可同时
**只读**已配置的 digest JSON，传给同一个 display builder。它不隐式打开 digest
配置，不要求每只股票同时配置两种缓存。

只要一个 bucket 生成了合格 v2 cards，Chapter 4 就优先使用 v2 bucket，不能再混入
引用相同 claim/source 的 legacy paragraph。只有整批没有合格 v2 card 时才允许走
现有 legacy bucket；fallback 状态必须进入 diagnostics，避免安全边界被悄悄绕过。

统一 display 字段固定为：

```python
deep_analysis_display["_curated_external_argument_cards_v2"] = [card, ...]
deep_analysis_display["_curated_external_taxonomy_version"] = "external_argument.v2"
```

cards 的 `citation_refs` 使用同一个 `deep_analysis_display["citations"]`。digest claim
加入已有 narrative display 时，必须按 `citation_identity()` 复用现有 ref；只有新 identity
才分配下一个本地 ref。snapshot `_external_rows()` 先适配 v2 cards；当至少一个 v2 row
存在时，不再适配 narrative/reasoning/topic legacy buckets。formal-thin 仍对完整 snapshot
计算 offset，不能让 v2 本地 refs 另走一套偏移。

### 5.3 Topic taxonomy

使用封闭、跨行业的通用 family：

- `capacity_delivery`
- `demand_customer`
- `technology_product`
- `financial_quality`
- `valuation_expectation`
- `competitive_landscape`
- `policy_geopolitics`
- `commercialization`
- `other`

归一化只读取 claim/card 的 `topic / primary_topic / display_topic` 元数据和明确的
claim-type；不读取股票名、文件名或 source title。`other` 可以保留在 MaterialSnapshot，
但必须通过后续 display novelty 才能显示。

### 5.4 Entity scope

实体归属使用显式输入而不是行业 hardcode：

1. claim/quote 明确出现 configured stock name，且 source 不是 foreign-only title：
   `target`；顶层 artifact 的 `stock_name` 已通过 identity check、source title 也明确
   含目标公司全名、且 claim/evidence 没有其他事实主语时，也可判为 `target`；
2. 未声称目标公司事实，内容明确使用同业/行业/竞品上下文，或 source title 明确是
   其他公司：`peer_or_industry`；
3. 同一 argument 同时比较目标公司和明确同业主体：`target_with_peer_context`，必须
   在 display title/body 中保留“对比/同业背景”语义；
4. 论点把目标公司事实归因给 foreign-only source：hard reject；
5. 无法证明目标实体且又使用“公司/其/该企业”作事实主语：`ambiguous`，不进入
   目标公司变量；
6. 同业/行业卡可展示，但 title 必须标记 `同业/行业背景（Preview）`，不能在
   `display_body` 中把同业指标改写为目标公司指标。

现有 suffix/title heuristic 只作为 legacy source-title 辅助证据，不能单独把一条卡
升级为 `target`。

### 5.5 Claim-evidence alignment

每张 v2 card 必须满足：

- 至少一个非空 evidence unit 与有效 citation；
- evidence 是现有 source quote/excerpt 的完整连续文本，不由系统改写；
- claim 中的数字、百分比、型号、年份必须逐项出现在 evidence units；
- claim 与 evidence 的 concrete-token overlap 作为 admission 证据；数字、型号和强
  断言对齐是 hard gate，普通词 overlap 只作为 quality score，不能因短材料缺少词面
  重合就单独拒绝一张已通过 source/citation/anchor 证明的卡；
- `唯一/第一/份额/市占率/确认/已落地` 等强表述只有在 evidence 原文存在时才可保留，
  且最终仍加外部 framing；
- generic `why_incremental`（例如“baseline 未提及该外部观察”）不进入正文，只留诊断。

不满足者保留在原缓存，但不生成 v2 display card，并记录 rejection reason。

### 5.6 Dedupe and incremental display

Producer 内部按以下顺序去重：

1. exact evidence hash；
2. same URL + normalized claim containment；
3. same URL + same topic family + identical concrete anchors。

不同来源对同一变量提供互补证据时不合并 source truth；可在一个 card group 中共享
`display_title`，并保留各自 citation。不得使用 embedding、模糊向量或股票专用 bucket。

Chapter4 display novelty 只在现有 selector 内计算。外部侧读取 v2 `claim/topic_family/
concrete_anchors`，owner 侧继续复用现有 `matching_topic_families()` 与 concrete-anchor
提取，不新增第二套 owner taxonomy：

- external topic 与 owner topic 不同：`outside_owner`；
- topic 相同但有 owner 未出现的新数字/型号/年份、事件状态、反方结论或验证条件：
  `owner_delta`；
- 只有 owner 已有事实或同义复述：`owner_duplicate`。

只对相同 `argument_key` 的重复卡做合并；同一 topic family 下若存在彼此独立、证据
充分的事件、机制或分歧，可以保留多个 argument block。不存在每个 family 或全局卡片
数量上限。相同 argument 选择 source-faithful、evidence 完整、实体明确且信息量最高者，
其余互补 refs 可合并。display selector 不能因为容量限制丢弃高价值卡片。

### 5.7 Display body contract

Batch A 不让 snapshot/renderers重写论点。builder 输出：

- target / outside-owner：`外部材料提出的增量变量是……；其原文依据为……`；
- owner-delta：`相对正式材料/机构假设，外部材料新增的待验证点是……`；
- peer/industry：`同业/行业材料显示……；该信息只用于背景比较，不代表目标公司事实。`

正文必须来自 claim + evidence 的完整句，不得生成泛化的“跟踪订单/收入”模板。
MaterialRow 需要保存独立的 `external_claim`、`external_evidence`、`entity_scope`、
`owner_relation` 和 `argument_key`，不能把结构化字段提前拼成不可逆的单个 body。
renderer 只把 `external_claim` 渲染成不超过 110 字的完整论点句并附完整 refs，把完整
`external_evidence` 渲染为引用块：verified quote 使用 `> **外部原文依据**`，legacy
excerpt 使用 `> **缓存材料摘录**`。如果 claim 无法在完整
句边界内满足预算，则该 card 不进入 v2 display，而不是字符截断。引用块沿用同一组
refs，不重复分配 citation identity。如果无法形成完整、
受证据支持的正文，则不生成 v2 display card。

## 6. Batch B: Prompt Upgrade

Batch B 只有在 Batch A 通过以下 gate 后启动：

- 中际、复旦、黑芝麻的 v1 缓存适配均无实体泄漏和引用回归；
- 4.3 每个可见 block 都有 claim + evidence + source identity；
- `theme_reexpanded_outside_owner` 不再由同一 external topic 的多段铺陈触发；
- formal-medium / formal-thin / formal-rich 回归测试通过。

Batch B 才修改 extractor/composer prompt，使模型原生输出：

- `target_entity`、`entity_scope`；
- 单一核心 `claim`；
- 1--3 个逐字 `evidence_units`；
- `topic_family`；
- `incremental_delta` 与 `baseline_owner`；
- claim/evidence 中的数字和型号对齐。

模型输出仍必须经过 Batch A 的确定性 validator；prompt 输出不能自行成为准入依据。
Batch B 必须展示中际、复旦、黑芝麻三只股票的样例输出，请用户确认无编造数据后，
才能更新正式缓存或合并。

## 7. Planned Scope

### Batch A runtime candidates

- 新增 `scripts/utils/curated_external_argument_cards.py`
- 修改 `scripts/utils/curated_external_display.py`
- 修改 `scripts/utils/report_skills/synthesis_skills.py`
- 修改 `scripts/utils/deep_analysis_material_snapshot.py`
- 修改 `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- 修改 `scripts/utils/report_prose_quality.py`

必要时可对 `scripts/utils/curated_external_viewpoint_narrative.py` 做 schema plumbing，
但不得修改其中 prompt。`report_quality.py` 不修改。`report_prose_quality.py` 只允许
增加一个结构化 v2 delta 例外：段落必须以“相对正式材料/机构假设，外部材料新增的
待验证点”开头、正文不超过 110 字、包含完整 inline citation，且紧邻一个
`外部原文依据/缓存材料摘录` 引用块。只有同时满足这些条件的段落不计入 borrowed-theme
reexpansion；任一条件缺失时仍按旧规则报警。renderer 不能增加 selector 或词表。

对应测试限于 `tests/utils/` 与 `tests/reporter/`。不修改 config、data、knowledge、
reports、评分、目标价、风险、技术分析、推荐或采集文件。

Batch A runtime 目标净增 `+180`，hard stop `+240`。必须通过替换现有重复 entity/
dedupe/claim-normalization helper 控制体积；不能在四层继续各加一套 v2 判断。

明确的 replacement ledger：

- `SynthesisSkill._viewpoint_digest_semantic_key()` 中的中际/光模块专用 hardcode 由
  通用 `argument_key` 替换并删除；
- `SynthesisSkill._dedupe_viewpoint_digest_claims_for_display()` 由 v2 builder 的唯一
  dedupe 替换；
- `SynthesisSkill._external_viewpoint_topic_key()` 的正文扫描由 metadata-only topic
  normalizer 替换；
- `curated_external_display.filter_external_viewpoint_claims()`、
  `_filter_external_entity_scope()` 及其重复 title/entity helper 收口到 v2 entity owner，
  legacy adapter 仅保留最小兼容调用；
- snapshot 现有 `_external_incremental_reason()` 继续作为唯一 display novelty owner，
  但 v2 路径改读结构字段；legacy body-scan 分支只为旧缓存保留，不另建 selector。

实现文件责任固定为：

- `curated_external_argument_cards.py`：schema、input adapters、entity、evidence alignment、
  topic metadata normalization、argument dedupe、citation merge；
- `curated_external_display.py`：文件读取与 legacy/v2 display assembly，不再拥有 entity
  或 semantic dedupe 规则；
- `synthesis_skills.py`：配置开关和调用编排，不再拥有 topic/entity/dedupe 业务逻辑；
- `deep_analysis_material_snapshot.py`：MaterialRow plumbing 和相对 visible owners 的唯一
  incremental selector；
- `deep_analysis_renderer.py`：格式化 v2 claim/evidence；
- `report_prose_quality.py`：仅实现已锁定的 framed-delta positive/negative contract。

### Batch B scope

另开 Level 3 task，允许修改 extractor/composer prompt 及对应 producer tests；不与
Batch A 混批。

## 8. Required Tests

### Producer contract

1. digest claim 生成 v2 card，完整 quote、hash、refs 保留；
2. narrative reasoning card 在无 digest 时生成 v2 card；
3. digest + card 同时存在时 merge，不产生两张重复卡；
4. 只有 paragraph、无 evidence 时保持 legacy，不伪造 v2 card；
5. claim 新增数字/型号而 evidence 不含时拒绝；
6. source excerpt 半句或 citation 缺失时拒绝；
7. generic why-incremental 不进入 display body；
8. URL + evidence/anchor dedupe 保留信息量更高者。

### Entity scope

9. 目标公司 + 合法目标来源准入 target；
10. foreign-only source 不能支持目标公司事实；
11. peer-only 行保留为 `同业/行业背景（Preview）`；
12. “公司/其”但无法解析实体时 fail closed；
13. 复旦三巨头对比不得把紫光/安路亏损写成复旦事实。

### Display novelty and reports

14. owner 相同且无 delta 的财务数字/估值情景被 4.3 拒绝；
15. 同一 owner topic 有新事件、数字或反方条件时保留一个 focused block；
16. 中际供应链传言 + 预付款可合并为一个 argument block，refs 完整；
17. NPO/XPO 若只重复 4.1 技术路线则拒绝；若含新量产时间/客户验证则保留 delta；
18. formal-thin citation offset 仍基于 full snapshot，无 missing/unused/malformed；
19. formal-rich legacy output fixture 不变；
20. external rows 仍不进入 core facts/scoring/risk/target/recommendation。

### Quality and compatibility

21. 现有 v1 中际 digest + narrative、复旦 narrative cards、黑芝麻缓存均可读取；
22. v2 card 失败时 legacy output 可用，但 diagnostics 明确记录 fallback；
23. producer/digest/display/snapshot 不存在第二个相同 entity/dedupe owner；
24. focused suite、full offline `pytest`、CI grep gates、`git diff --check` 全部通过。
25. 两个合格、短且带 evidence block 的 v2 owner-delta 可共存而不触发 prose warning；
26. 缺 citation、超长、无 delta framing 或无 evidence block 的同主题段落仍触发 warning。

## 9. Failure Modes

| Failure mode | Safe outcome | Catching test |
|---|---|---|
| Digest 与 narrative 只有一侧存在 | 使用可证明 evidence 的一侧；不要求联网重建 | 输入适配 fixtures |
| Paragraph 有漂亮叙事但无逐字 evidence | 不生成 v2 card；保留 legacy 兼容 | paragraph-only fixture |
| 同业文章含目标公司名 | 未证明目标事实则 peer/ambiguous；不得升级 target | entity fixtures |
| Claim 数字不在 quote | 拒绝 card，不修写数字 | numeric alignment fixture |
| 同一文章拆成多个 refs | URL/source identity 合并，脚注仍完整 | same-source dedupe fixture |
| Annual/broker 已覆盖同主题 | 无 delta 则不显示；有新事件只显示 focused delta | owner relation fixtures |
| v2 selector 无结果 | 4.3 输出既有空状态或 legacy 安全 fallback | empty/fallback fixture |
| Formal-thin refs 重新编号 | 测试失败并停止；不得改 full-snapshot offset | offset regression |
| 外部内容进入评分/目标价 | 硬测试失败，停止实现 | boundary integration |
| prose checker 例外过宽 | 缺任一 v2 framing/citation/evidence 条件仍报警 | positive/negative gate fixtures |

## 10. Acceptance and Stop Conditions

Batch A accepted only when：

- v2 cards 对三类缓存都有稳定、可诊断的转换结果；
- 最新中际/复旦报告 4.3 的每个 block 都能回答“谁的观点、论点是什么、原文证据
  是什么、相对 4.1/4.2 新增什么”；
- 没有目标实体错归、missing/unused/malformed/unknown citation；
- `theme_reexpanded_outside_owner` 不再由外部同主题多段铺陈触发；
- 低信用来源仍只在 Preview/引用表，不影响任何决策路径；
- full offline tests 与质量门通过。

立即停止并返回设计，如果：

1. 需要修改 LLM prompt 才能让 Batch A 正确；
2. 需要新增股票/行业专用规则；
3. 需要让 renderer 参与选择，或需要超出已锁定结构条件的 prose-checker 例外；
4. 无法保持 formal-thin full-snapshot citation offset；
5. 需要从无 evidence 的 paragraph 反推/编造 source quote；
6. runtime 净增超过 `+240`；
7. 任何外部内容进入官方事实、core facts、评分、风险、目标价或推荐路径。
