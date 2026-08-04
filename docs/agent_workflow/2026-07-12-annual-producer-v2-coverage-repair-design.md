# Annual Producer v2 Coverage Repair Design

## Goal

在不读取 v1 note 的 producer、不改 annual evidence-pack 抽取范围、不改报告 renderer/评分/LLM 的前提下，修复 v1 到 v2 的 coverage gate：有效旧事实必须被同 source block 的 v2 SourceUnit 精确覆盖；残缺、表格交错或重复的旧摘录必须显式分类，而不是被误当成必须恢复的事实。

## Observed Failure

当前八股本地缓存刷新后，黑芝麻智能、中简科技、圣邦股份、乐鑫科技和中际旭创仍有 `v1_needs_recovery_count > 0`。根因混合了三类数据：

1. 有效的多句论证在 producer 内按单句 family 预分类，首句与上下文句的 local signal 不同就被拆开；上下文句又不能单独成为 seed。
2. A 股 checkbox 因果尾句在 v2 中正确去掉了 checkbox/标题前缀，v1 coverage 仍拿完整旧段做精确比较。
3. 旧 v1 note 含有页码残片、截断末句、OCR 交错表格和重复保存的同一事实；现有 material pack 只按长度和 anchor 判定 meaningful，错误地将它们计入 recovery。

## Invariants

- producer 只读取 annual evidence pack，不读取 v1 Knowledge notes。
- coverage proof 只允许同 `source_block_id` 内、按 source-unit 原顺序的精确规范化子串；禁止 semantic/fuzzy matching。
- producer 不接收完整表格。A 股表格中仅 checkbox 后、完整且具因果/经营/产品/财务锚点的单句尾部可以进入 narrative card。
- `v1_adapter_use_count` 保持“实际成功适配的 legacy note 数”语义，不能重定义。只有含 actionable、未覆盖事实的 note 才能进入适配流程；不得因 invalid legacy fragment 把整段噪声重新带回显示层。
- v1 adapter 删除前，每只配置股票的 `actionable_v1_needs_recovery_count == 0`。
- 不加 stock/industry 专用关键词，不提高 evidence-pack block 上限，不改报告生成路径。

## Data Flow

```text
annual raw cache
  -> evidence blocks / SourceUnits
  -> bundle-first v2 admission
  -> v2 notes (source units retained)
  -> legacy fragment classifier
  -> exact same-block coverage proof
  -> actionable adapter gate
```

## Producer Repair

`periodic_report_narrative_evidence_cards.py` 已有 seed / continuation 模型。本轮只替换它的 bundle 边界判断，不增加第二条 selector：

```text
prepared unit = noise | {unit, local_family, seed_or_continuation}
for each seed:
  bundle_family = strong_financial_override(seed) or usage_primary(seed, local_family)
  append following unit iff it is adjacent, anchored, non-noise,
  _continues_same_argument(bundle, following, bundle_family) is true,
  and _starts_independent_argument(bundle, following, bundle_family) is false.
  resolve the completed bundle once with bundle_family as the preferred family;
  retain every local family only as a secondary signal.
```

具体替换点：

- `_primary_family` 继续负责 seed 的 usage-primary/financial override；不再被用来要求每个 continuation 与 seed family 相同。
- 主 loop 删除 `following["family"] != family` 这一断开条件，改用 `_starts_independent_argument` 与既有 `_continues_same_argument`。
- `_is_continuation` 只检查 anchor、noise 和 bundle continuity；不重新选 family。
- `_is_self_contained_atomic_fact` 保持现有 HK/A-share、technology-product 防误收规则。

`_starts_independent_argument` 在 continuity 已成立后调用；它不会重新选择 family：

```text
if following begins with a continuation connector (其中/同时/此外/另一方面/受此/从而):
  return false
if following is not a self-contained fact for bundle_family:
  return false
if technology bundle has a named product different from the bundle's named product:
  return true
if operating/financial bundle has a new reporting period and a new metric subject:
  return true
if business/market bundle introduces a named product, customer, industry, market, or strategy subject
   absent from the bundle's subject token set, regardless of whether it begins with 公司/行业/市场/管理层:
  return true
return false
```

`_bundle_subject_tokens` 不做语言模型判断：technology 使用 `_named_products`；operating/financial 使用已有 metric/operating token；business/market 使用 `_named_products`、客户词、以及 `_market_subject_tokens` 的行业/市场/战略词。仅当后句 token 集出现前 bundle 没有的具体主体，且该后句 self-contained，才断开。

主 loop 先检查相邻/non-noise，再检查 `_continues_same_argument`，最后调用 `_starts_independent_argument`。非自包含句不会被误判成独立卡，但仍必须满足 continuity 才能附着；自包含且引入新产品、新期间、新指标主体或新市场主体的句子会分卡。这样“相邻但独立”的技术、经营、财务事实会分卡；缺主体但依附上句的 continuation 不会仅因 local signal 不同被丢弃。强财务解释仍可 override usage-primary；technology-product 仍要求明确产品/技术锚点与动作，不接受泛“平台/能力”。

这应覆盖黑芝麻智能的商业化 + 客户量产论证、乐鑫的平台锁定 + 生命周期、中际的行业集中度 + 技术路线，而不让相邻但独立的论点合并。

## Legacy Fragment Classification

在 `annual_report_material_pack.py` 中，legacy note 先按句/分号拆成 fragment，再为每个 fragment 给出一个状态：

| 状态 | 条件 | 对 gate 的作用 |
| --- | --- | --- |
| `covered` | 同 block v2 SourceUnit 有精确规范化连续覆盖 | 不启用 adapter |
| `actionable_uncovered` | 完整、非表格、非 dangling，且有 concrete annual anchor，但尚无 v2 覆盖 | 保留 adapter 并阻塞删除 |
| `invalid_legacy` | 命中下列确定性 invalid 规则 | 记录诊断，不启用 adapter |
| `duplicate_legacy` | 同 block 的 normalized actionable fragment 已由排序更早的 legacy note 接管 | 只增加 duplicate 诊断，不启用第二个 adapter |

规范化只做 whitespace、页码前缀与 checkbox 标题尾句处理；它不能补词、改写文本或做语义推断。`annual_argument_schema.py` 新增公共 `ANNUAL_CHECKBOX_MARKER_RUN_RE` 与纯语法 helper `annual_checkbox_tail(text: object) -> str | None`：仅当原文恰有一个 marker run、其后无第二个 marker、且 tail 以 `。；;！？!?` 结束时返回 tail，否则返回 `None`。producer 保留现有 `family in {operating_progress, technology_product_progress, financial_quality_explanation}` gate，再检查 anchor/noise；material pack 不做 family 判断，只用返回的 tail 进行 exact coverage。

确定性 invalid 规则如下；未命中这些规则的疑似事实必须留在 actionable 路径，不能因“看起来短”被丢弃：

| 规则 | 判定 |
| --- | --- |
| page prefix | 仅剥离开头 `^\\d{1,3}/\\d{1,3}` 后重判，不直接判 invalid。 |
| checkbox | 恰有一段共享 marker run 且 marker 后是完整尾句时，用该尾句；存在 marker 但没有完整尾句时 invalid。 |
| layout/OCR table | 含 `…`，或同时包含至少 3 个表头词（项目/单位/变动比例/研发人员/期初/期末/学历/年龄构成/资本化）和至少 6 个数值。 |
| dangling lead | 开头为标点/连接词，且无公司主体、命名产品或具体数值锚点。 |
| dangling tail | 原始 fragment 无句末标点，且以 `及/和/或/、/，/:/：/项目/方面/比例` 结束，同时没有可验证的完整因果或产品动作。 |
| underspecified short clause | 少于 12 个非空白字符，且没有命名产品、具体数值或“命名对象 + 量产/验证/交付”关系。 |

短句的正向规则优先于 invalid。先定义 `ACTIONABLE_SHORT_RELATIONS`：`量产/量產/验证/驗證/认证/認證/交付/供货/供貨/导入/導入/定点/定點/发布/發佈/签订合同/簽訂合同/回款/采购/採購/销售/銷售/出货/出貨/投产/主要系/由于/由於/所致/因此/从而`。少于 12 个非空白字符的 fragment 只有在同时具备下列之一时才 actionable：命名产品 + relation、具体数值 + 因果 relation、或公司/客户主体 + 经营 relation。`产品已实现量产` 这类无命名产品的短表格单元属于 invalid；“A2000 已实现量产”则是 actionable。以“和代理销售”开头的残片没有主体、产品名或数值锚点，属于 dangling lead；带有缺失前缀但仍含完整风险事实的长句则必须保持 actionable。

同一 `source_block_id + normalized actionable fragment` 只统计一次，避免旧 note 在多个 category 下重复计数。

classifier 与 adapter loop 的接口为：

```python
def _classify_legacy_fragments(
    excerpt: str, source_block_id: str, v2_records: list[_CardRecord]
) -> list[dict[str, object]]:
    # one record per original fragment
    # {"original": str, "normalized": str,
    #  "status": "covered" | "actionable_uncovered" | "invalid_legacy",
    #  "proof_unit_ids": list[str], "reason": str}
```

classifier 不处理跨 note 去重。adapter loop 的不变式为：

```text
fragments = classify_legacy_fragments(note, v2_units_for_same_block)
actionable = []
for fragment whose status is actionable_uncovered in source order:
  key = source_block_id + normalized fragment
  if key was already adapted from an earlier sorted legacy note:
    increment v1_duplicate_legacy_fragment_count; skip it
  else:
    mark key seen; append fragment to actionable
if not actionable:
  do not call adapt_v1_card; do not increment v1_adapter_use_count
else:
  copy the legacy card with source_excerpt = ordered actionable original fragments
  call adapt_v1_card on that copy
  append only the adapted copy and increment v1_adapter_use_count once
```

因此若一个 legacy note 同时含 invalid 与 actionable fragment，adapter 只保留 actionable fragment 的原文拼接；若全部 fragment 都是 covered/invalid/duplicate，则不适配该 note。两份 note 共享同一 actionable fragment 时，按排序靠前的 note 适配，后一个 note 仅增加 duplicate 诊断。`v1_adapter_use_count` 仍计实际适配的 note 数；不新增语义不同的同名 key。

## Diagnostics and Gate

material pack diagnostics 新增或明确下列字段：

- `v1_covered_fragment_count`
- `v1_actionable_needs_recovery_count`
- `v1_invalid_legacy_fragment_count`
- `v1_duplicate_legacy_fragment_count`
- `v1_adapter_use_count`

保留 `v1_needs_recovery_count` 作为兼容别名，值等于 actionable unique recovery 数。`v1_adapter_use_count` 仍是实际适配 note 数，且必须满足 `v1_actionable_needs_recovery_count == 0 => v1_adapter_use_count == 0`。Batch B 的准入只看每只股票 `v1_actionable_needs_recovery_count == 0`，但 notes 必须记录 invalid/duplicate 数及样例。

## Five-Stock Classification Fixtures

每行是测试中使用的精确、whitespace-normalized literal；省略号不允许进入 fixture。

| 股票 | fragment | 分类 | proof / reason |
| --- | --- | --- | --- |
| 黑芝麻智能 | `持續迭代產品， A2000 家族全系列產品將很快 亮相` | covered | `hk_product_progress-1` 产品进展 SourceUnit |
| 黑芝麻智能 | `年12 月31 日止年度均為 37.4%` | invalid_legacy | 缺少指标主体和完整年份起点 |
| 中简科技 | `2025 年四季度客户付款形式由航信变动为电汇支付，回款现金增多，致使本报告期经营活动现金流入大幅增长，所以 报告期内经营活动产生的现金净流量与本年度净利润存在较大差异。` | covered | `cash_flow_capex_table-0` checkbox tail SourceUnit |
| 中简科技 | `2025年 2024年 变动比例 研发人员数量（人） 75 45 66.67% 研发人员数量占比 14.53% 10.04% 4.49% 研发投入金额（元） 117,509,715.58 85,763,342.72` | invalid_legacy | 3+ 表头词与 6+ 数值 |
| 圣邦股份 | `投资活动现金流出小计本期较上期增加51.86%，主要原因系本报告期购买理财产品增加所致。` | covered | `cash_flow_capex_table-0` 因果 SourceUnit |
| 圣邦股份 | `产品已实现量产` | invalid_legacy | 无命名产品/数值的短表格单元 |
| 乐鑫科技 | `客户产品进入量产后，通常在市场上持续销售5至10年。` | covered | `product_capacity_profile-0` 生命周期 SourceUnit |
| 乐鑫科技 | `随着功能不断扩展、生命周期持续延长，单个项目` | invalid_legacy | 无终止标点且以 unfinished noun phrase 结束 |
| 中际旭创 | `光 模块头部厂商凭借领先的研发实力及交付能力，竞争优势进一步强化，行业集中度有望持续提升。` | covered | `competitive_position-0` 行业 SourceUnit |
| 中际旭创 | `和代理销售，但以直接销售模式为主，即直接面向下游客户进行技术和产品推介、签订合同并交付、提 供售后技术支持与服务。` | invalid_legacy | 无主体、产品名或数值锚点的连接词开头残片 |

## Required Tests

1. 黑芝麻智能：HK market block 的商业化首句与客户/量产 continuation 在同一 bundle，且有精确 source unit。
2. 中简科技：checkbox 前缀 legacy fragment 通过 marker 后因果尾句被 coverage proof 覆盖；纯表格研发人员 fragment 为 invalid。
3. 圣邦股份：38 大类/6800 款产品、近 900 款新品与研发费用为 actionable/covered；截断的“子技术的性能边界”与交错产品表为 invalid。
4. 乐鑫科技：平台锁定、量产生命周期和毛利率原因段被 bundle/coverage 保留；“单个项目”一类截断 fragment 为 invalid。
5. 中际旭创：行业集中度与硅光技术挑战保留；“和代理销售”这种缺主语的旧中间句不作为 actionable recovery。
6. material pack：每个新 diagnostics key 都有 controlled fragment 单测；不同 legacy note 的相同 fragment 只计一次；invalid fragment 不触发 adapter；adapter excerpt 不含 invalid text。
7. material pack：`v1_actionable_needs_recovery_count == 0` 时 `v1_adapter_use_count == 0`；mix note 的 adapter 只含 actionable 文本；checkbox legacy prefix 与 v2 tail 精确匹配。
8. producer technology fixtures：`A2000 芯片已通过客户验证。该产品面向具身智能场景并进入量产准备。` 生成一张两 unit card；`A2000 芯片已通过客户验证。C1200 芯片完成车规认证。` 生成两张、unit 不重叠的 card。
9. producer operating fixtures：`报告期内高速模块出货同比增长。增长主要来自800G产品占比提升。` 生成一张两 unit card；`报告期内高速模块出货同比增长。报告期内库存同比上升。` 生成两张、unit 不重叠的 card。
10. producer financial fixtures：`经营现金流同比增长342.37%。主要因客户付款方式由航信变为电汇。` 生成一张两 unit card；`经营现金流同比增长342.37%。毛利率同比提升2个百分点，主要因产品结构改善。` 生成两张、unit 不重叠的 card。
11. 所有 producer fixture 都断言每个 SourceUnit 只归属一张 v2 card。
12. 所有配置股票的 local-cache acceptance：所有 `v1_actionable_needs_recovery_count` 为零；否则不生成报告、不归档 v1 note、不删除 adapter。

## Runtime Budget

当前工作树以 `git diff --numstat aa7bdd9` 实测为 `+270`：schema `+67`、material pack `+67`、evidence pack `+51`、producer `+85`。历史 audit 中的 `+220` 是 admission-repair 前的快照，不是当前基线。

C0 不是一个临时、独立可运行的 `<= +220` 状态，而是 coverage classifier 的替换账本。实现必须先删除这些旧代码，再加入新逻辑：

| 删除项 | 文件 | 被什么替换 |
| --- | --- | --- |
| `_coverage_classification`、`_meaningful_legacy_fragments`、`_is_fragment_boilerplate`、`_uncovered_fragments` | material pack | 一个 fragment-level 三态 classifier，直接返回 covered/actionable/invalid 与 ordered proof |
| producer 本地 `_CHECKBOX_MARKER_RUN_RE` 与 marker 解析分支 | producer | schema 的 `annual_checkbox_tail` |
| `_has_atomic_anchor` wrapper | producer | 共享 `has_concrete_annual_anchor` |
| `following["family"] != family` early break | producer | `_starts_independent_argument` + `_continues_same_argument` 单一路径 |

上述删除是同一替换提交的一部分，不承诺中间工作树达到 +220；最终四文件硬停止仍为 `+270`。若删除项无法抵消 classifier、shared helper 和 bundle delta，必须停止并返回设计，不能提高预算。压缩不能删除 HK/A-share admission、SourceUnit exact proof 或现有失败测试。

## Stop Conditions

- 需要 fuzzy matching、stock-specific rules、提高 block cap 或读取 v1 note 来指导 producer。
- 任一有效 legacy fragment 只能通过丢弃事实才能让 gate 归零。
- runtime delta 超过 `+270`。
- 任一八股 `v1_actionable_needs_recovery_count > 0`。
