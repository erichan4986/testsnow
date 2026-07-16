# Chapter 4 Annual Display Selection Design

日期：2026-07-13
分支：`codex/annual-producer-v2`

## 1. Problem

Annual Producer v2 已完成材料保全，八股本地 gate 达到：

- `v1_actionable_needs_recovery_count == 0`
- `v1_adapter_use_count == 0`

新报告暴露出的剩余问题不再是材料缺失，而是 Chapter 4 的展示选择失控：

- 中际旭创 `4.1` 展示产品目录、标准型号、客户认证流程、生产模式、治理和承诺条款；
- 复旦微电 `4.1` 展示审计意见、宏观行业长段落、行业技术门槛、残缺目录和章节标题；
- `annual_report_memo` 保留全部 canonical cards，`build_chapter4_view_model()` 又把全部 annual rows 放入 `4.1`；
- renderer 仅分组并逐行输出，现有字符串清洗无法承担报告级选择。

用户已确认产品边界：**4.1 只展示能形成投资判断的官方材料。完整但低价值的真实材料继续保留在 material pack / memo，不要求在报告中展示。**

## 2. Invariants

1. Producer 继续保全材料，本批不删除 producer card，不降低八股 coverage。
2. `annual_report_memo` 继续保存完整 canonical rows，作为可追溯材料层。
3. Chapter 4 read-model 负责 display admission；renderer 只负责组织和排版。
4. 不设置 annual rows 的硬性总条数上限。符合准入且提供新信息的内容可以保留。
5. 不新增 LLM memo，不修改 `KnowledgeSynthesizer` prompt。
6. 不修改 profile、scoring、target price、risk、technical、recommendation。
7. 不添加股票名、股票代码或行业专用例外。
8. `formal_medium` 与 `formal_thin_external_rich` 的 4.1 使用同一个 annual display selector。

## 3. Options

### A. Renderer-only filters

继续扩展 `_clean_formal_medium_official_row()`，在输出前过滤关键词。

优点：改动小。
缺点：formal-medium / formal-thin 容易分叉；规则继续堆在 1,800 行 renderer；无法在 view-model diagnostics 中解释选择结果。

结论：不采用。

### B. Memo destructive selection

在 `_build_annual_report_memo()` 中只保留精选 rows。

优点：两个 profile 天然复用。
缺点：memo 丢失完整材料，与 producer 保全目标冲突；以后无法区分“没有材料”和“材料未展示”。

结论：不采用。

### C. Shared Chapter 4 read-model selection

在 `deep_analysis_material_snapshot.py` 中新增唯一的 annual display selector。snapshot 仍接收全部 memo rows；Chapter 4 view 只接收 selected rows。formal-thin 的 4.1 改为使用同一 selected MaterialRow 集合。

优点：职责正确、两个 profile 共用、memo 不丢材料、可记录选择 diagnostics，并可删除 renderer 中逐步膨胀的清洗逻辑。

结论：采用。

## 4. Data Flow

```text
annual material pack (complete)
  -> annual_report_memo (complete canonical rows)
  -> MaterialSnapshot (complete normalized MaterialRows)
  -> select_annual_display_rows() (Chapter 4 display contract)
  -> formal_medium 4.1 / formal_thin 4.1
  -> renderer formatting only
```

`select_annual_display_rows()` 是唯一 selector。不得在 renderer 再新增一套同义 admission/ranking。

selector 不修改 snapshot 原始 rows；它返回新的 immutable `MaterialRow` 投影。原 row、memo 和 material pack 均保持完整。

## 5. Annual Display Contract

### 5.1 Common eligibility

候选 row 必须满足：

- `source_layer == "annual"`；
- 正文非空且有有效 citation；
- `claim_status` 为 `formal_fact` 或 `formal_explanation`；
- narrative row 经 segment projection 后必须至少留下一个可独立阅读的公司事实或管理层判断；
- `argument_complete` **不是** 4.1 的硬准入条件。当前 v2 cards 中大量具有展示价值的 atomic facts 标记为 `false`，该字段只用于 4.4 annual 条件的优先级。

### 5.2 Display-only rejection

以下内容只从 4.1 隐藏，不从 memo / material pack 删除。拒绝判断按句号、问号、感叹号和分号切成 source-order segments 后执行，不得因一个噪声 segment 拒绝整条混合 row：

- 审计报告标准意见，例如“我们认为，后附财务报表……公允反映”；
- 监管披露、治理结构、关联交易承诺、同业竞争承诺。结构触发包括“公司需遵守/披露要求”“机构独立情况”“同业竞争/关联交易/资金占用 + 承诺/承诺函”；
- 章节标题、报告页眉页脚、URL 占位符、Markdown blockquote 残片；
- 产品目录、型号/标准/封装的密集罗列，且没有经营含义。含型号或标准的 segment 若同时具备公司产品动作、技术路线、客户应用或报告期进展，则保留；
- 采购、生产、销售、认证等常规流程，除非明确解释报告期变化、竞争优势或财务结果；
- 纯行业规模、第三方预测、行业定义和通用技术壁垒，且没有连接到公司策略、产品、竞争地位或经营变化。

规则必须依据文本结构和语义关系，不得按股票或具体产品名称硬编码。

每条 row 的 projected body 由通过准入的原文 segments 按原顺序拼接。可以删除 display-only 噪声 segment，但不得改写、归纳或补充原文。若所有 segments 均被拒绝，该 row 才从 4.1 隐藏。

### 5.3 Role admission

#### `business_structure`

保留：公司主营业务、核心产品/平台、服务客户与应用场景、业务组合、可验证竞争位置。
拒绝：纯规格目录、单个型号说明、常规生产/认证流程。

#### `operating_progress`

保留：报告期内产品出货、客户导入、市场拓展、供应变化、产能或经营结果变化。
要求：存在公司主体 + 动作/变化 + 结果或时间语境。

#### `market_competition_outlook`

保留：管理层明确连接公司策略、竞争位置、产品路线或经营影响的判断。
拒绝：孤立的行业规模预测、政策摘录和通用行业背景。

#### `technology_product_progress`

保留：公司研发投入、产品发布/验证/量产、技术平台进展和可识别研发成果。
拒绝：通用行业技术门槛、产品目录行和残缺标题。

#### `financial_quality_explanation`

保留：正式财务事实，以及收入、利润、毛利率、费用、现金流、存货等变化原因。
拒绝：审计意见和与指标变化无关的会计模板。

### 5.4 Redundancy control without a hard row cap

selector 不使用 `rows[:N]` 或全局数量上限。按原始顺序处理已准入 rows，只抑制：

1. 归一化文本完全相同；
2. 同 role 中一条正文完整包含另一条，保留信息更完整的一条；

不实现相似度、token overlap、模糊匹配或“新增事实锚点”推断。不得使用会重写原文的摘要算法。不得因“已经有一条该 family”而丢弃后续独立高价值事实。

### 5.5 Portrait

一句话画像优先从 selected `business_structure` rows 选择。若该池为空，可依次从 selected `operating_progress`、`technology_product_progress` 中选择完整的公司级描述；不得回退到 confirmed financial row，也不得用纯行业预测充当画像。若没有合格候选，允许省略画像。排序偏好：

1. 主营业务 + 核心产品/服务；
2. 客户/应用场景；
3. 多业务线覆盖；
4. 完整句优先于截断句。

portrait row 在“业务结构”中不重复展示，但其余独立 business rows 保留。

## 6. Profile Integration

### formal_medium

- `build_chapter4_view_model()` 的 `4.1` 使用 selected annual rows；
- `4.4` 的 annual 条件只允许从 selected rows 中选择。先在 `argument_complete` rows 中按 `business_structure > operating_progress > market_competition_outlook > technology_product_progress > financial_quality_explanation` 查找；若没有，再在 selected rows 中按同一优先级查找；绝不 fallback 到任意 `row_list[0]`；
- `4.2/4.3` 不变。

### formal_thin_external_rich

- annual-broker-external layout 的 `4.1` 不再直接遍历完整 `annual_report_memo`；
- formal-thin 保持现有 full `MaterialSnapshot` 和 4.2/4.3 renderer；只把同一 annual selector 的结果传给新的 shared 4.1 material-row formatter；
- 标题仍为 `4.1 年报经营摘要`；4.2/4.3 的可见内容与结构不变，citation 编号按下述 snapshot-global contract 接线。

#### Formal-thin citation contract

MaterialSnapshot allocator 产生的 ref 是 Chapter 4 内部唯一编号空间，selector 不重编号。formal-thin 已在 selector 之前构建 full snapshot。设 baseline synthesis 最大引用号为 `B`：

- selected annual MaterialRow 的可见引用：`B + snapshot_ref`；
- broker offset 继续使用现有 full-snapshot 公式：`B + max_snapshot_ref(full_snapshot, {annual})`；
- external offset 继续使用现有 full-snapshot 公式：`B + max_snapshot_ref(full_snapshot, {annual, broker})`；
- 不得用 selected annual refs 推导任一 offset，也不重新压紧编号；
- 最终全局引用表继续先合并 full snapshot citations，再由现有 `_visible_citations_only()` 按最终 Markdown 的脚注 marker 裁剪。因此 selector 拒绝 annual row 只会移除该 row 的可见引用，不会改变 broker/external 编号，也不会留下 unused ref；
- formal-thin 端到端测试必须覆盖“最高 annual ref 被 selector 拒绝”的场景，证明 broker/external ref 不碰撞、不漂移、无 missing/unused/orphan。

不得为了 annual selector 改写 formal-thin 的 4.2/4.3 external precedence 或 citation selection。

### formal_rich

- 继续走 legacy body，本批不改变。

## 7. Renderer Slimming

renderer 不再拥有 display admission。实现时应删除或收缩：

- 删除 `_clean_formal_medium_official_row()` 的选择职责：采购/生产/销售/认证流程、监管披露和空 row 判断全部迁入 shared selector；
- formal-thin 直接遍历完整 memo rows 的 4.1 路径；
- 与 shared selector 重复的 exact dedupe / noise filtering。

renderer 可以保留：

- 分组标题；
- portrait 排版；
- citation attachment；
- 句子边界安全的显示长度处理；
- 纯展示 normalization，例如压缩空白和移除已知的报告标题前缀，但不得再决定 row 是否可见。

运行时代码预算只统计 runtime 文件，不含 tests/docs：目标净增不超过 `+80` 行，硬停止 `+120` 行。删除的 renderer 选择逻辑计入净增。超过硬停止必须返回设计，不得继续堆 helper。

## 8. Diagnostics

Chapter4ViewModel diagnostics 增加：

- `annual_candidates_count`
- `annual_selected_count`
- `annual_rejected_by_reason`
- `annual_deduped_count`

diagnostics 只用于测试和排错，不进入报告正文，不新增 sidecar。

## 9. Quality Validation

本批不在 `report_quality.py` 复制 annual selector 的语义规则。审计意见、目录形态、治理条款、模式流程和纯行业段落的准入/拒绝由 selector unit tests 与 renderer integration tests 锁定；正式报告复跑做最终人工验收。

现有 citation/source-boundary/format quality gates 保持不变。`_check_formal_medium_evidence_depth()` 不预先调整；只有 selector 正确却出现可证明的 false positive 时，才允许另开窄修。

## 10. Required Tests

### Selector unit tests

1. 中际形态：保留主营业务、客户/应用、经营变化、研发投入；拒绝产品型号目录、标准列表、认证流程和“以销定产”。
2. 复旦形态：保留 EEPROM/FPGA/安全芯片等公司经营变化；拒绝审计意见、WSTS 长段落、通用行业壁垒、章节标题。
3. 独立高价值 rows 数量超过任意常见显示数量时全部保留，证明没有 hard cap。
4. exact / containment 重复被抑制，非 containment 的独立事实不被误删。
5. formal financial facts 可见；审计模板不可见。
6. diagnostics reason counts 与实际选择一致。
7. 混合 row 中“产品策略/客户进展 + 标准合规尾句”只删除噪声 segment，保留高价值原文 segment 与原 citation。
8. 所有 business rows 被拒绝时，portrait 只回退到 selected operating/technology 公司级描述；不得使用财务数字或纯行业预测。

### Renderer / profile tests

1. formal-medium 4.1 使用 selected rows，不出现拒绝样本。
2. formal-thin 4.1 使用相同 selector，不出现拒绝样本。
3. formal-rich legacy layout 不变。
4. portrait 不在业务结构重复。
5. visible citations 无 missing / unused / unknown。
6. 4.4 不使用被 4.1 selector 拒绝的 annual row。
7. formal-thin 中最高 annual ref 被拒绝后，annual/broker/external refs 仍不碰撞，且全局来源无 missing/unused/orphan。
8. selector 返回零 annual rows 时显示 fallback 文案，不输出空壳分组。

### Existing-gate regression

1. selector 后的两种 profile 继续通过 citation/source-boundary/format quality gates。
2. 正常财务解释不会被 selector 误删。
3. 完整产品进展中包含型号或标准时不会仅因单个 token 被误杀。

### Report acceptance

重新生成：

- 中际旭创：`formal_medium`，4.1 不再包含产品目录、认证/生产模式、治理承诺；
- 复旦微电：`formal_thin_external_rich`，4.1 不再包含审计意见和纯行业长段落；
- 两份报告的 quality/source/prose/CI/citation hygiene 通过；
- 报告必须为源码修改后的新产物，不得验收 stale 文件。

## 11. Failure Modes

| Failure mode | Visible symptom | Test / gate |
|---|---|---|
| selector 误放产品目录 | 4.1 出现连续型号、标准、表格残片 | Zhongji selector + renderer fixture |
| selector 误放审计模板 | 4.1 出现“我们认为，后附财务报表” | Fudan selector + renderer fixture |
| generic industry 误放 | 4.1 被市场规模/WSTS/政策长段落占据 | company-link admission tests |
| selector 过严 | 有价值产品、客户、经营变化全部消失 | positive fixtures + no-hard-cap test |
| 两套 selector 漂移 | formal-medium 与 formal-thin 展示不同准入结果 | shared-selector profile test |
| citation 丢失 | visible ref missing 或 global unused | citation alignment tests |
| formal-thin offset 由 selected max 推导 | 拒绝高位 annual ref 后 broker/external 编号漂移 | rejected-highest-ref regression test |
| 4.4 使用拒绝 row | 条件推演引用审计/目录噪声 | price-path selected-only test |
| 代码继续膨胀 | renderer 新增第二套规则 | scope audit + runtime numstat hard stop |

## 12. Allowed Files

预计允许修改：

- `scripts/utils/deep_analysis_material_snapshot.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `tests/utils/test_deep_analysis_material_snapshot.py`
- `tests/reporter/test_deep_analysis_renderer.py`

如需修改 `synthesis_skills.py`、annual producer、material pack 或其他 runtime 文件，必须停止并返回设计。

`deep_analysis_renderer.py` 的 formal-thin 4.1 路径明确属于允许修改范围；formal-thin 4.2/4.3 不改内容选择、文案结构或 citation selection。

## 13. Stop Conditions

立即停止并回报：

- 需要删除或改变 annual producer cards；
- 需要修改 memo schema 或新增持久化 sidecar；
- 需要新增第二 selector 或股票/行业专用规则；
- 需要修改 LLM prompt、profile、评分、目标价、风险、技术面或推荐；
- 运行时代码净增超过 `+120`；
- focused tests 显示 formal-rich、citation offset 或 source boundary 大面积回归。

## 14. Design Delta After Round 1

### Accepted

- B1：删除“高度重叠/新增事实锚点”模糊去重，只保留 exact 与 containment。
- B2：补充 formal-thin full-snapshot offset、最终可见脚注裁剪及最高 annual ref 被拒绝回归测试。
- M1：4.4 改为严格 role priority，不再任意 fallback 到 `row_list[0]`。
- M3：selector 拥有可见性判断；renderer 只保留 normalization/formatting。
- M4：display rejection 改为 segment-level projection，混合 row 不整行误杀。
- N1/N2：补充治理承诺、监管披露和章节标题的结构边界。
- N3：不预先调整 depth gate，只在真实 false positive 出现时窄修。

### Rejected / Corrected

- M2 的“fallback 到 selected 中任意最高分 row”过宽。设计改为仅回退到 operating/technology 的公司级描述；财务事实和纯行业预测不得充当画像。
- review 对 memo family fallback 的描述与当前代码不符。`_family()` 在缺失 `argument_family/card_type` 时默认 `business_structure`，而当前 v2 notes 显式携带 `argument_family`；本批不扩大到 `synthesis_skills.py`。selector 仍以 role-specific content admission 防止错误 role 泄漏。

### Deferred

- 非 containment 的语义去重；等待真实样本证明必要性后单独设计。
- 修改 memo family schema；当前没有证据要求跨越 allowed scope。

### R2 Required

已完成。Round 1 有两个 blocker；其修订后由 Codex Round 2 self-review 复核，结论见下一节。

## 15. Codex Round 2 Self-Review

### Findings

1. 当前 renderer 已在最终输出前调用 `_visible_citations_only()`，而 formal-thin 已持有 full snapshot；因此不需要把 formal-thin 4.2/4.3 迁入 `Chapter4ViewModel`，也不需要新增 layer-shift 公式。只要 full snapshot 保持用于现有 offset 计算，annual selector 的结果不会影响 broker/external 编号。
2. 真实中际与复旦 v2 cards 的 `argument_complete` 多数为 `false`。把该字段作为 4.1 hard gate 会误删 atomic 但有价值的主营业务、产品进展和经营变化。设计已调整为仅在 4.4 优先级使用。
3. 原 §9 语义质量 gate 会在 `report_quality.py` 复制 selector 的审计/目录/模式判断，违背单一 selector 与代码瘦身目标。已移除；现有 output gate 保持，新增 selector/renderer fixtures 负责回归。
4. Round 1 所称 memo fallback 到 financial 与当前 `_family()` 不符：缺失 family 的现行 fallback 是 `business_structure`。不扩大到 synthesis 层，selector 的 role-specific admission 足以保护显示层。

### Verdict

`ok`。B1/B2 与 M1-M4 已在设计层关闭；范围收敛为 snapshot selector + shared 4.1 formatter，formal-thin 的 broker/external 内容路径不变。

### Implementation Ready

`yes`。下一步可以写 implementation task；实现仍受 runtime `+80` target / `+120` hard stop 约束。
