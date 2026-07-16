# Annual Producer v2 Coverage Completion Design

## Goal

Close the remaining eight-stock v1 adapter gate without losing valid annual
facts, adding a second selector, changing the 48-block evidence pack, or
introducing stock-specific rules.

## Current Evidence

The local-cache audit found no actionable fragment whose source block was
missing from the evidence pack.

| Failure class | Count | Meaning |
| --- | ---: | --- |
| `missing_pack_block` | 0 | No evidence-pack selection or cap change is needed. |
| `producer_no_card` | 11 | The block is present but no canonical card owns the fact. |
| `card_boundary_gap` | 29 | The block has cards, but the fact's ordered SourceUnits are not fully owned. |

All 11 no-card fragments come from mapped usages; none uses the unmapped
`risk_disclosure` usage. Four are concrete risk/mitigation facts. Seven are
R&D-investment or profitability facts rejected by whole-block table/noise guards
or a family seed predicate narrower than the mapped usage. The 29 boundary gaps
include product roadmaps, customer lifecycle facts, cash-flow explanations,
product portfolios, and market competition observations.

### Exact no-card inventory

| Stock / block | Usage -> target | Exact fragment | Expected ownership |
| --- | --- | --- | --- |
| SGT / `management_market_view-0` | `management_market_view` -> market | `化的激励措施来稳定和扩大人才队伍，但由于市场竞争加剧，进入模拟集成 电路设计行业的门槛较高，加剧了对该行业的人才争夺，所以公司仍然存在 技术人员流失的风险。` | Market bundle unit 1 |
| SGT / `management_market_view-0` | `management_market_view` -> market | `面对这一风险，公司一方面将扩大招贤纳士力度，积 极从外部引进各层次人才，同时加强内部培训，完善培训机制，使技术人员 业务水平不断提升。` | Same market bundle, adjacent unit 2 |
| SGT / `rd_investment_table-0` | `rd_investment_table` -> technology | `报告期内，公司各研发项目进展顺利，共推出近900款拥有完全自主知识产权的新产品，公司研发费用支出 104,519.49万元，占营业收入的26.81%。` | Independent technology/R&D card |
| SGT / `rd_investment_table-0` | `rd_investment_table` -> technology | `研发人员1,335人，占公司员工总数的72.75%，其中本科及以上学历1,250人， 从事集成电路行业10年及以上426人，10年以下909人，核心技术人员稳定。` | Independent technology/R&D card |
| Espressif / `inventory_note-0` | `inventory_note` -> financial | `存货跌价和周转率下降风险 公司根据已有客户订单需求以及对市场未来的预测情况制定采购和生产计划。` | Financial bundle unit 1 |
| Espressif / `inventory_note-0` | `inventory_note` -> financial | `随着公司业务 规模的不断扩大，公司存货绝对金额随之上升，进而可能导致公司存货周转率下降。` | Same financial bundle, adjacent unit 2 |
| Espressif / `profitability_commentary-0` | `profitability_commentary` -> signal-resolved business | `乐鑫的产品应用于泛IoT领域，着眼于长期的数字化升级，而非依赖某 个行业或客户的短期爆发性增长。` | Independent business card |
| Espressif / `profitability_commentary-0` | `profitability_commentary` -> financial | `公司发生营业成本136,918.75万元，较上年同期增长21.63%。` | Independent financial card |
| Espressif / `profitability_commentary-1` | `profitability_commentary` -> financial | `营业成本变动原因说明：本年营业成本的变动主要受产品销售变动的影响，波动与收入波动 相近。` | Financial bundle unit 1 |
| Espressif / `profitability_commentary-1` | `profitability_commentary` -> financial | `本期价格策略没有显著变化，成本端因采购量上升进一步获得成本规模效应，毛利率整体 稳中有升。` | Same financial bundle, adjacent unit 2 |
| Espressif / `profitability_commentary-0` | `profitability_commentary` -> financial | `2025年度综合毛利率为46.63%，较2024年度增加了2.72个百分点，本期价格策略没有显著变化， 成本端因采购量上升进一步获得成本规模效应，毛利率整体保持稳中有升。` | Independent financial card |

### Full-block admission fixtures

The table-shaped regression tests must use the complete cached block text below,
not isolated positive sentences. This proves that removing the whole-block veto
does not weaken unit-level admission.

#### SGT `rd_investment_table-0`

```text
2025年 2024年 变动比例
研发人员数量（人） 1,335 1,184 12.75%
研发人员数量占比 72.75% 74.09% -1.34%
研发人员学历
本科 499 452 10.40%
硕士 731 641 14.04%
博士 20 17 17.65%
研发人员年龄构成
30岁以下 689 661 4.24%
30~40岁 450 357 26.05%
40岁以上 196 166 18.07%
近三年公司研发投入金额及占营业收入的比例
26
圣邦微电子（北京）股份有限公司2025年年度报告全文
2025年 2024年 2023年
研发投入金额（元） 1,045,194,886.44 870,746,770.34 737,074,050.02
研发投入占营业收入比例 26.81% 26.02% 28.18%
研发支出资本化的金额（元） 0.00 0.00 0.00
资本化研发支出占研发投入的比例 0.00% 0.00% 0.00%
资本化研发支出占当期净利润的比重 0.00% 0.00% 0.00%
公司研发人员构成发生重大变化的原因及影响
□适用 ☒不适用
研发投入总额占营业收入的比重较上年发生显著变化的原因
□适用 ☒不适用
研发投入资本化率大幅变动的原因及其合理性说明
□适用 ☒不适用
公司需遵守《深圳证券交易所上市公司自律监管指引第4号——创业板行业信息披露》中的“集成电路业务”的披露要求:
报告期内，公司加强了知识产权相关工作的推进力度并取得明显成效，报告期内，公司新申请专利141项，其中发明专利117项、实用新型专利7项、PCT国际专利申请17项；新增授权发明专利145项、新增授权实用新型专利7项；新增集成电路布图设计登记48项。截至报告期末，公司累计获得授权专利588项，其中发明专利497项、实用新型专利62项、境外授权专利29项；集成电路布图设计登记401项；软件著作权登记18项；核准注册商标156项。
报告期内，公司各研发项目进展顺利，共推出近900款拥有完全自主知识产权的新产品，公司研发费用支出104,519.49万元，占营业收入的26.81%。研发人员1,335人，占公司员工总数的72.75%，其中本科及以上学历1,250人，从事集成电路行业10年及以上426人，10年以下909人，核心技术人员稳定。公司研发投入、研发人员数量逐年增加。同时，公司持续跟踪市场发展变化，特别是新能源车、光伏储能、人工智能、智能制造、机器人等应用领域的发展趋势，积极做好相关技术、知识产权和产品的布局及储备，目前已在电动汽车、工业控制、5G通讯、物联网、智能家居、可穿戴设备、无人机、智能制造等领域取得了良好的销售业绩，拓展了客户群体，后续将继续发挥产品性能及市场反应迅速的优势，贴近客户，以求准确及时地把握住商机、进一步拓展市场份额。
```

Expected assertions:

- year headers, numeric table rows, page markers, checkbox rows, and regulatory
  boilerplate produce no cards and own no SourceUnits;
- complete patent, product/R&D, personnel, and market-strategy narrative units
  may be admitted through the existing canonical-family path;
- the product-count/R&D-spend unit and the R&D-personnel unit are two disjoint
  technology cards because their bundle subjects are `product_portfolio` plus
  `rd_spend`, versus `rd_staff`;
- every admitted SourceUnit has one owner.

#### Espressif `profitability_commentary-0`

```text
带动了我们的整体成长。乐鑫的产品应用于泛IoT领域，着眼于长期的数字化升级，而非依赖某个行业或客户的短期爆发性增长。公司发生营业成本136,918.75万元，较上年同期增长21.63%。2025年度综合毛利率为46.63%，较2024年度增加了2.72个百分点，本期价格策略没有显著变化，成本端因采购量上升进一步获得成本规模效应，毛利率整体保持稳中有升。
(1). 主营业务分行业、分产品、分地区、分销售模式情况
单位：元 币种：人民币
主营业务分行业情况
营业收 营业成
毛利率 入比上 本比上 毛利率比上年增减
分行业 营业收入 营业成本
（%） 年增减 年增减 （%）
（%） （%）
集成电路 2,565,275,431.81 1,369,187,501.55 46.63 27.82 21.63 增加2.72个百分点
主营业务分产品情况
营业收 营业成
毛利率 入比上 本比上 毛利率比上年增减
分产品 营业收入 营业成本
（%） 年增减 年增减 （%）
```

Expected assertions:

- the product/application sentence produces one `business_structure` card and
  appears in no financial card;
- the complete cost and margin sentences may produce financial cards;
- section labels, unit/currency rows, broken table headers, and bare numeric rows
  produce no cards.

#### Espressif `profitability_commentary-1`

```text
营业收入变动原因说明：主要系各行业物联网渗透率提升，生态影响力不断扩散，新老客户采购金额增长所致。
营业成本变动原因说明：本年营业成本的变动主要受产品销售变动的影响，波动与收入波动相近。本期价格策略没有显著变化，成本端因采购量上升进一步获得成本规模效应，毛利率整体稳中有升。
销售费用变动原因说明：本年销售费用较上年增加1,888.06万元，增幅30.01%；主要系职工薪酬和特许权使用费增加所致。
管理费用变动原因说明：本年管理费用较上年增加1,946.53万元，增幅28.10%；系职工薪酬增加所致。
财务费用变动原因说明：本年财务费用为收益1,053.62万元，主要系利息收入和利息费用综合影响所致。
研发费用变动原因说明：本年研发费用较上年增加11,312.95万元，增幅23.07%；系职工薪酬增加所致。
经营活动产生的现金流量净额变动原因说明：经营活动现金净流入52,262.20万元，较上年同期增加30,214.95万元，同比增长137.05%。主要系销售商品、提供劳务收到的现金增加所致，由于近年来新增潜力客户开始放量，销售快速增长。
投资活动产生的现金流量净额变动原因说明：投资活动产生的现金流量为净流出191,305.94万元，上年同期是净流入15,397.36万元，主要系本期购买理财产品和房屋及建筑物所致。
```

Expected assertions:

- every admitted card is financial and owns only complete causal/change units;
- an explanation and its immediately dependent cause may share one bundle;
- independent expense, cash-flow, and investment-flow subjects split into
  separate cards;
- no truncated/OCR-only fragment is emitted.

## Locked Product Decisions

1. Concrete risk disclosures may enter existing canonical families:
   - inventory, receivable, margin, and cash-flow causal facts map to
     `financial_quality_explanation`;
   - talent competition, industry challenge, and company response facts map to
     `market_competition_outlook`.
2. Do not add a risk family. Pure headings and generic risk boilerplate remain
   rejected.
3. SourceUnit ownership remains exclusive:
   - same argument: extend the existing bundle;
   - independent subject, product, metric, period, or conclusion: emit a new
     card;
   - no SourceUnit may belong to two cards.
4. Do not use v1 notes to guide producer output. v1 notes are fixtures and the
   post-run acceptance oracle only.
5. Do not use fuzzy matching, rewrite source text, increase the 48-block cap,
   or add stock/industry rules.

## Architecture

### 1. Replace blanket risk rejection with an explicit risk predicate

`_noise_reason()` currently rejects every unit containing `风险` or a risk
token. Remove that blanket rejection, but require every risk-bearing unit to
pass `_is_concrete_risk_fact(text, family, usage_hint)` inside the existing
`_is_self_contained_atomic_fact` path:

```text
if usage has no canonical family:
  return false
if family == financial_quality_explanation:
  require a financial metric AND a causal/change/plan relation
if family == market_competition_outlook:
  require a named industry/customer/supplier/talent/technology subject
  AND a competition/challenge/mitigation relation
  AND reject hypothetical risk text unless it also contains a metric, period,
      Latin product id, or named customer/supplier
otherwise:
  return false
```

Financial relations reuse `_CAUSAL_TOKENS`, `_FINANCIAL_ACTIONS`, and
`增长/下降/增加/减少/上升/预测/计划/导致`. Market relations are deterministic:
`竞争加剧/门槛/争夺/流失/引进/培训/集中度/挑战/拓展/合作`. A concrete market
subject is either a phrase ending in `行业/客户/供应商`, or one of the generic
talent/personnel subjects `人才/人才队伍/技术人员/研发团队/技术团队/招贤纳士`.
Generic `市场/需求/竞争` alone is insufficient.

Resulting behavior:

- an unmapped `risk_disclosure` heading still has no canonical family and is
  rejected;
- generic mapped-market text such as `如果市场需求下滑，公司将面临产品竞争力下降的风险。`
  fails the concrete risk predicate and is not a seed;
- a mapped inventory/receivable block with a concrete metric, operating
  relation, or causal statement can seed a financial card;
- a mapped management-market block with competition/talent facts can seed a
  market card.

No `_risk_selector`, risk fallback table, or parallel admission path is added.

### 2. Replace whole-block rejection with unit-first narrative admission

Seven non-risk fragments show that table-shaped blocks may contain complete
narrative sentences. Remove only the `source_block_text`-level table/boilerplate
veto. Keep every unit-level checkbox, page-marker, table/OCR, audit-policy, and
structural-noise guard. `_is_self_contained_atomic_fact` is the sole
complete-relation predicate after family resolution:

```text
complete_relation = unit ends at a sentence/semicolon boundary
                    AND has_concrete_annual_anchor(text)
business:
  existing company/business context OR named product/application relation
technology:
  existing product progress OR mapped rd_table/rd_investment_table
  + complete_relation + R&D/product/personnel metric
operating:
  existing operating-change predicate
market:
  existing market judgment; risk text must also pass _is_concrete_risk_fact
financial:
  financial metric + causal/change relation; risk text must also pass
  _is_concrete_risk_fact
```

The existing business test (`公司`/`业务` context alone) is too broad once the
whole-block veto is gone. Replace it with `_has_concrete_business_fact(text)`:

```text
first reject a unit-level structural label or regulatory-disclosure sentence
accept business only when one of these concrete relations is present:
  - 主营业务/主要业务/公司业务 + 为/包括/涵盖/覆盖/从事 + a description
  - 产品应用于/产品服务于/服务于/面向 + a named application, customer, or market
  - 产品线/客户覆盖/商业模式/销售模式 + a complete descriptive predicate
  - existing business_model/hk_business_overview compatibility predicate
otherwise reject
```

The two new unit-level negative guards are intentionally narrow and precede
family resolution in `_noise_reason`:

```text
_looks_like_business_section_label(text):
  optional numeric prefix + two or more of 分行业/分产品/分地区/分销售模式
  and ends in 情况/说明; no sentence-level business relation

_looks_like_regulatory_disclosure(text):
  starts with 公司需遵守/本公司需遵守
  and contains 自律监管指引/行业信息披露/披露要求
```

Thus `(1). 主营业务分行业、分产品、分地区、分销售模式情况` is a label, not
a business assertion, and `公司需遵守《...自律监管指引...行业信息披露》...披露要求:`
is regulatory boilerplate, not a business fact. These guards operate on a single
SourceUnit; they do not reintroduce a whole-block veto, an industry rule, or a
second admission path.

Usage-primary routing remains preferred only when the mapped family satisfies
this predicate. A concrete product/application sentence inside a profitability
block may resolve to `business_structure` through its actual signal rather than
being forced into financial. To make that reachable, the existing business
branch in `_family_signals` and `_has_company_or_business_context` is extended
with one deterministic relation: a named product/company phrase, the relation
`产品应用于/服务于`, and a concrete application/customer. This is family signal
resolution, not a second selector.

The existing `_primary_family` order is retained and made explicit:

```text
if strong financial explanation:
  return financial
mapped = canonical_family_for_usage(usage_hint)
if mapped and _mapped_family_has_seed_signal(text, mapped):
  return mapped
signal_family = first eligible family from _family_signals(text)
if signal_family exists:
  return signal_family
return mapped only as the final anchored fallback
```

Therefore the Espressif product/application sentence does not satisfy the
mapped financial seed, gains a business signal from the new relation predicate,
and resolves to `business_structure`. It must not appear in a financial card.

### 3. Complete existing argument bundles

Repair the current seed/continuation path rather than adding a recovery pass.

- Strip only recognized page prefixes before admission while preserving source
  offsets, using the same source-substring discipline as checkbox tails.
- A mapped-family unit with a concrete anchor and a complete relation may be a
  seed even when it does not repeat the narrow family keyword.
- HK product clauses separated by semicolons remain separate SourceUnits; each
  complete named-product/product-roadmap assertion may seed its own card.
- A dependent continuation joins the preceding bundle only when
  `_continues_same_argument()` is true and `_starts_independent_argument()` is
  false.
- Independent assertions keep disjoint SourceUnits and become separate cards.

For technology/R&D bundles, `_bundle_subject_tokens` adds three generic subjects
beside named products: `product_portfolio`, `rd_spend`, and `rd_staff`. The SGT
unit containing product count plus R&D expense owns the first two subjects; the
adjacent R&D personnel unit owns `rd_staff`, so
`_starts_independent_argument()` splits them into two cards.

`_market_argument_continues()` adds only the explicit mitigation prefixes
`面对这一风险/面对风险/针对这一风险/为应对`. The SGT mitigation unit therefore
joins the risk assertion; its following `另一方面公司...` unit already matches the
existing `另一方面` prefix and remains in the same bundle.

The implementation must modify the existing `_noise_reason`,
`_is_self_contained_atomic_fact`, `_continues_same_argument`, and
`_starts_independent_argument` path. It must not add a second scan over rejected
units.

### 4. Exact acceptance proof

`annual_report_material_pack.py` remains unchanged except for tests if a
backward-compatible diagnostic assertion is required. The acceptance oracle is
the existing exact fragment classifier:

- same `source_block_id`;
- ordered, contiguous v2 SourceUnits;
- `normalize_annual_source_text` only;
- no semantic or fuzzy proof.

## Failure Modes

| Failure | Observable symptom | Test/gate |
| --- | --- | --- |
| Blanket risk filter remains | SGT/Espressif `producer_no_card` stays nonzero | concrete risk fixtures + eight-stock gate |
| Generic risk text leaks | weak market tokens make hypothetical risk text a card | mapped-market negative fixture |
| Whole-block guard remains | coherent R&D/profitability units still produce no card | exact mapped-usage fixtures |
| Table label leaks as business fact | `主营业务分行业...情况` becomes a business card | unit-level section-label negative fixture |
| Regulatory disclosure leaks as business fact | `公司需遵守...披露要求` becomes a business card | unit-level regulatory-boilerplate negative fixture |
| Same argument is split | lifecycle/roadmap legacy fragment remains uncovered | exact SourceUnit fixture |
| Independent facts merge | one card owns two unrelated products/metrics | disjoint ownership tests |
| Source text is rewritten | SourceUnit offsets no longer match cleaned source | source-substring invariant tests |
| Coverage is faked | actionable facts are reclassified invalid | material-pack fixture and recovery counts |
| Code expands into another path | selector/helper duplication increases | diff review and scope audit |

## Required Tests

### Risk admission

| Fixture | Usage | Expected cards / ownership |
| --- | --- | --- |
| `化的激励措施来稳定和扩大人才队伍，但由于市场竞争加剧，进入模拟集成 电路设计行业的门槛较高，加剧了对该行业的人才争夺，所以公司仍然存在 技术人员流失的风险。面对这一风险，公司一方面将扩大招贤纳士力度，积 极从外部引进各层次人才，同时加强内部培训，完善培训机制，使技术人员 业务水平不断提升。另一方面公司将不断加强企业文化建设，增加企业凝聚力。` | `management_market_view` | One market card owning `management_market_view-0:u0`, `u1`, and `u2` exactly once. The explicit mitigation prefix and `另一方面` keep all three units in one argument. |
| `存货跌价和周转率下降风险 公司根据已有客户订单需求以及对市场未来的预测情况制定采购和生产计划。随着公司业务 规模的不断扩大，公司存货绝对金额随之上升，进而可能导致公司存货周转率下降。` | `inventory_note` | One financial card owning `inventory_note-0:u0` and `u1` exactly once. |
| `如果市场需求下滑，公司将面临产品竞争力下降的风险。` | `industry_outlook` | Zero cards. |
| `风险提示。公司存在相关风险。` | `risk_disclosure` | Zero cards. |

The SGT R&D minimal fixture uses the two exact `rd_investment_table-0`
fragments from the no-card inventory and expects exactly two disjoint
technology/R&D cards (`u0` and `u1`). The SGT full-block fixture additionally
proves that table headers and numeric-only units produce no cards. Espressif
profitability fixtures assert that the exact product/application sentence routes
by signal, every admitted financial metric/reason unit is owned once, and table
headers remain rejected. The full inventory block may produce more than the two
target financial units when other complete causal facts satisfy the same
predicate; the assertion is no missing target ownership and no structural-noise
card, not an artificial total-card cap.

Two additional unit-level negatives lock the M9 boundary:

| Fixture | Usage | Expected result |
| --- | --- | --- |
| `(1). 主营业务分行业、分产品、分地区、分销售模式情况` | `profitability_commentary` | Zero cards; `business_structure` must not be seeded by a section label. |
| `公司需遵守《深圳证券交易所上市公司自律监管指引第4号——创业板行业信息披露》中的“集成电路业务”的披露要求:` | `rd_investment_table` | Zero cards; a regulatory disclosure sentence must not be seeded as business. |

### Boundary completion

- HK product roadmap semicolon clauses preserve A2000, NPU architecture, and
  advanced-process planning as disjoint or same-argument cards with exclusive
  SourceUnits.
- Customer platform lock-in plus 5-to-10-year lifecycle is fully covered.
- Cash-flow checkbox explanation is fully covered by exact SourceUnits.
- Product portfolio and R&D-number sentences are admitted without table-header
  noise.
- Zhongji market concentration plus silicon-photonics challenge remain two
  non-overlapping market assertions when they introduce distinct conclusions.
- The three full-block fixtures above are regression inputs. Tests must inspect
  every emitted SourceUnit and fail if a section label, unit/currency line,
  checkbox row, page marker, regulatory boilerplate, broken table header, or
  numeric-only row owns a card.

### Regression and gate

- Every admitted SourceUnit has exactly one owner.
- Existing focused annual tests and reporter downstream tests pass.
- Eight local-cache stocks have
  `v1_actionable_needs_recovery_count == 0` and
  `v1_adapter_use_count == 0`.
- Until that gate passes: no report generation, v1 archive, or adapter deletion.

## Scope

Allowed runtime file:

- `scripts/utils/periodic_report_narrative_evidence_cards.py`

Allowed tests:

- `tests/utils/test_periodic_report_narrative_evidence_cards.py`
- `tests/utils/test_annual_report_material_pack.py` only for acceptance assertions

Forbidden:

- evidence-pack cap/selection changes;
- material-pack classifier weakening;
- renderers, report generation, scoring, target, risk score, technical,
  recommendation, LLM prompt/memo, collection, config, raw data, and reports.

## Complexity Budget

The current four-file runtime delta relative to `aa7bdd9` is `+259`.

- Target: no more than `+30` additional net runtime lines.
- `+50` additional lines triggers design review; it is not a mechanical measure
  of correctness.
- Prefer replacing blanket filters and duplicate predicates over adding helpers.
- Structural hard stops: second selector, new family, stock-specific rule,
  fuzzy matching, or another rejected-unit recovery pass.

## Stop Conditions

- Any fact can reach zero recovery only by being discarded or labeled invalid.
- A fix needs evidence-pack expansion or v1-guided producer behavior.
- SourceUnit ownership overlaps.
- Any configured stock remains nonzero after the local-cache acceptance run.
- Implementation requires files outside the allowed scope.

## Design Delta

- Accepted: concrete risk facts enter existing families.
- Accepted: same-argument bundle extension plus independent-card split with
  exclusive SourceUnit ownership.
- Accepted: replace the exact `+270` hard cap with a `+30` target and `+50`
  review trigger, while retaining structural stop conditions.
- Rejected: new risk family, second selector, evidence-pack cap increase, fuzzy
  coverage, or stock-specific admission.
- Round 1 accepted: record all 11 real usage hints and exact fragments; define
  `_is_concrete_risk_fact`; make `_is_self_contained_atomic_fact` the sole
  concrete-anchor/complete-relation gate; add exact SourceUnit fixtures.
- Round 1 correction: only four no-card fragments are risk-bearing. Seven are
  complete narrative units rejected by whole-block noise or narrow seed logic.
- Round 2 accepted: the market-risk subject test explicitly includes talent and
  personnel phrases used by the SGT fixture.
- Round 2 accepted: `_primary_family` allows a valid signal family to override a
  mapped usage only when the mapped family does not satisfy its seed predicate;
  this routes the Espressif product/application sentence to business.
- Round 2 accepted: R&D product/spend and R&D personnel are distinct bundle
  subjects; explicit risk-mitigation prefixes extend the existing market bundle.
- Round 2 accepted: complete SGT and Espressif table-shaped blocks are locked as
  regression fixtures. Only the whole-block veto is removed; all unit-level
  structural-noise guards remain mandatory.
- Round 3 accepted: business admission changes from generic company/business
  context to an explicit concrete-business relation. Narrow unit-level guards
  reject business section labels and regulatory disclosure boilerplate before
  family resolution.
