# Evidence Depth Pipeline Review Round 1

**审查者**: Claude Code（只读分析）
**审查日期**: 2026-07-02
**设计文档**: `docs/agent_workflow/2026-07-02-fudan-evidence-depth-pipeline-design.md`
**相关代码**: `knowledge_synthesizer.py`, `synthesis_skills.py`, `deep_analysis_renderer.py`, `curated_external_full_body_viewpoint_claims.py`, `source_direct_relevance.py`, `report_quality.py`, `social_viewpoint_source_packets.py`
**验证数据**: `data/raw/periodic_reports/复旦微电_2025_annual_jina.txt`（已确认存在）

---

## Verdict

**verdict: needs_revision**

一句话总结：Evidence Depth Pipeline 的设计方向正确，4.1-4.4 的改进方案根因清晰，且已验证年报全文缓存（`复旦微电_2025_annual_jina.txt`，19.7万字，含"营业收入变动原因说明"等精确段落标题）可供 Batch A 使用。但存在 4 个 must-fix 项，主要涉及 peer_business_comparison_pack 的生产者归属、fundflow 汇总层序、source_excerpt 版权边界、section_too_generic 精度标准；无 blocker。这组设计与 Quality Fix 是互补关系而非竞争关系，可以 v2 阶段推进。

---

## 六项关键问题逐项评估

### 1. formal_financial_explanation_pack — 能否避免 4.2 重复数字、缺少原因？

**结论: 设计充分，可行性已验证**

- ✅ 明确将 explanation_pack 与 fact_pack 分离：fact_pack 管数字，explanation_pack 管解释性原文
- ✅ Prompt 规则写清"已有核心事实基座数字不得重复成表；应引用解释片段说明原因"
- ✅ 已验证的数据基础：`data/raw/periodic_reports/复旦微电_2025_annual_jina.txt` 包含：
  - `"二、经营情况讨论与分析"`（line 758）—— 解释性文本核心来源
  - `"营业收入变动原因说明：主要系报告期内公司的安全与识别芯片、智能电表芯片及FPGA销售额增..."`（line 1327）—— 精确匹配 `revenue_change` topic
  - `"三、报告期内核心竞争力分析"`（line 846）、`"四、风险因素"`（line 1221）—— 结构化分段明确
- ✅ Stop condition 覆盖缓存不存在的情况："不得抓外网补"
- ✅ 门禁 `fundamentals_repeats_fact_without_explanation`（warning）做第二道防线

**风险**: heading extractor 的边界需要测试——"风险因素"和"核心竞争力"中也可能误抽出非解释性文字作为经营解释。

### 2. peer_business_comparison_pack — 能否补足 4.1 而不让 LLM 编造"优于/领先"？

**结论: 设计方向正确，但 producer 归属不完整（→ MF1）**

- ✅ confidence + usage 分层（claim_eligible/context_only/audit_only）继承已验证的 peer_comparison_material 体系
- ✅ "没有至少两条正式/专业来源支撑时，不写优于/劣于"——强于现有 0.70 置信度阈值
- ✅ "不允许从估值高低推出产品强弱"——精确阻止一个已知幻象模式
- ✅ `unsupported_peer_business_claim` gate 做第二道防线
- ✅ 来源分层明确：canonical 4.1 只用年报/iwencai/券商研报摘要/正式行业研报

**未解决（→ MF1）**: `comparison` 字段的生产者未指定。如果 comparison 由 LLM 编写，LLM 写 comparison → LLM 消费 comparison 用于 synthesis，形成循环信任问题。必须指定为确定性提取或高度约束的 LLM 后处理。

### 3. 4.4 保真—能否保留数字/假设/推理链，且不泄漏到 4.1-4.3？

**结论: 架构隔离充分，但 source_excerpt 边界需明确（→ MF2）**

- ✅ 现有架构已经严格隔离 canonical synthesis 和 curated external display：
  - `deep_analysis_display` 与 `synthesis_text` 使用不同的 context key
  - `_is_main_analysis_display_allowed()` 会阻止 viewpoint 源进入 4.1-4.3
  - `_is_safe_curated_external_viewpoint_claim()` 在 digest 构建时强制 `preview_only/synthesis_display_only/scoring_eligible=False`
- ✅ `reasoning_steps`、`numbers_used`、`assumptions`、`counterpoints` 字段能保留增量逻辑
- ✅ "观点卡片"格式 + 每 topic 最多 2 张 + 每张 4 行 — 控制长度
- ✅ Display-only disclaimer + inline footnote — 防止混淆为系统结论

**未解决（→ MF2）**: `source_excerpt` 仅说"不得超过合理长度"，未定义最大值。无最大长度约束时，实现可能整段搬运，导致版权/超引风险。

**已验证的边界**: 现有 `curated_external_full_body_viewpoint_claims.py` 的 `repair_quote()` 函数通过最长公共子串匹配把 LLM 引文修复为原文精确子串——这提供了"引文一定存在于原文"的验证。但修复后的 quote 长度不限。

### 4. 多跳产业链—是否被安全挡在 canonical synthesis 外？

**结论: 设计充分，Direct-Only 规则提供强保护**

- ✅ `source_direct_relevance.py` 的 `classify_direct_relevance()` 只产出 company_direct/direct_product/direct_peer/formal_financial，多跳材料不命中 product_exposure_terms → sector_background → 排除
- ✅ 行业材料层级 L1-L4 定义清晰，L3（下游/旁路市场）和 L4（宏观/泛行业）不进 canonical
- ✅ `_has_explicit_unrelated_theme()` 在 MLCC + 否定关系时阻断（已在 Quality Fix 中实现）
- ✅ `_check_industry_chain_claims()` gate 已有对 4.3 的行业链条强确认词阻断
- ✅ 允许 4.4 表达"待验证观察"——既不错杀信息也保持边界

**L3→L2 边缘情况**: 一条行业材料标题含 "FPGA 需求受 AI 服务器拉动" 但正文主要在讲 AI 服务器 MLCC——由于命中 product_exposure_terms("FPGA")，会被分类为 direct_product（L2）而非 sector_background（L3）。这是 hard NLP 问题，设计在当前 Direct-Only 框架下已做到最优。quality gate 的 `product_industry_mismatch` 可以捕获明显的错配。

### 5. 资金流向 — deterministic 汇总还是让 LLM 消费 items？

**结论: 强烈同意 deterministic 方案，但层序需明确（→ MF3）**

- ✅ 设计建议新增 `fundflow_material_pack` 含确定性 summary（近 5 日主力净流入合计、超大单方向等）
- ✅ 确定性计算避免 LLM 自行求和出错
- ✅ 适配器已桥接百度/东财资金流向（`_bridge_technical_fund_flow()` 已完成）

**未解决（→ MF3）**: LLM 是否需要同时看到原始 fundflow items 和 deterministic pack？如果两者同时入 synthesis prompt：
  - LLM 可能忽略 deterministic summary 自行计算，产生不一致
  - 或 LLM 把 deterministic signal（如 `inflow_with_price_up`）误解为观点而非事实

  必须指定层序：有 deterministic pack 时，raw fundflow items 应被移出 synthesis 输入（或者只保留 pack summary）。

### 6. 空泛度 quality warnings — 可测试？误杀风险？

**结论: 总体可测试，section_too_generic 需更精确的标准（→ MF4）**

| Warning | 可测试性 | 误杀风险 |
|---------|----------|----------|
| `vague_supply_chain_position` | ✅ 高 — 变量存在性检测 | ✅ 低 — 变量要么出现要么没出现 |
| `fundamentals_repeats_core_facts` | ✅ 高 — 已有同类实现 | ✅ 低 — 已有前例 |
| `section_too_generic` | ⚠️ 中 — 需要同时检测模板词出现 + 具体信息缺失 | ⚠️ 中 — 见 MF4 |
| `external_viewpoint_overcompressed` | ⚠️ 中 — 取决于 4.4 渲染实现 | ✅ 低 — 仅检测格式结构 |

- ✅ All warnings first（不阻塞生成）——降低误杀风险
- ✅ "积累 3-5 份报告后再决定哪些升级为 error" ——审慎策略

**未解决（→ MF4）**: `section_too_generic` 的实现需要更精确的检测标准。如果只做"包含模板词 AND 不包含具体词"的双向匹配，需要对"具体内容"（产品名、数字、时间点、对象）有精确的正则定义。设计未给出这个定义。

---

## Findings

### Blocker

无。设计的基础架构合理，独立于 Quality Fix 的进展。

### Must-Fix

#### MF1. peer_business_comparison_pack 的 comparison 生产者未指定

**Evidence**:
- 设计定义了一个带 `dimension/target_position/peer/peer_position/comparison/evidence_type/confidence/usage` 的完整 schema
- 但只写了"消费者"（KnowledgeSynthesizer 的 industry_logic）没写"生产者"
- 对于 `peer_comparison_material`，生产者是 `build_peer_comparison_material()`——确定性函数，从结构化指标（PE/PS/毛利率）推导
- 对于 `peer_business_comparison_pack`，产品线和竞争定位需要从非结构化文本（年报/研报/iwencai 摘要）提取——没有等价的确定性生产者
- 如果 comparison 由 LLM 编写，出现了循环信任：LLM 写 "紫光国微与复旦微电产品结构不同" → LLM 在 synthesis 中消费这个 comparison → `unsupported_peer_business_claim` gate 无法触发（因为 pack 里已经有 comparison），实际上失去了对"编造竞争对比"的防御

**Why it matters**:
- 这是 4.1 防止 LLM 编造"优于/领先/落后"的关键材料包。如果 producer 不明确，这个材料包的实际效果等于让 LLM 自我举证
- 设计已有对基线问题（4.1 空泛）的正确诊断，但给出的方案在 producer 环节存在逻辑漏洞

**Required change**:
1. 明确指定 `peer_business_comparison_pack` 的生产者为**确定性提取模块**（建议与 explanation_pack 共用 heading extractor，从 iwencai 摘要和年报"管理层讨论与分析"中按产品线 keyword 提取对比）
2. 如果必须使用 LLM 提取，需要：
   - 每个 row 的 `evidence_type` 明确注记是否 LLM 推导而来（如 `evidence_type: "llm_extracted_from_formal_source"`）
   - LLM 提取行的 `confidence` 上限为 0.65（低于直接来源行的 0.85+）
   - LLM 提取行只能标注 `usage: "context_only"`，不能用于"优于/劣于"支撑
3. 在 `unsupported_peer_business_claim` gate 中增加判断：如果 4.1 强定位词只被 LLM-derived 行支撑，仍然 fail

#### MF2. source_excerpt 最大长度和版权合规检查未定义

**Evidence**:
- 设计建议 `source_excerpt` 保留原文关键片段，用于 4.4 "观点卡片"展示
- 仅说"不得超过合理长度；避免整段搬运"，未定义量化标准
- 现有缓存中 2025 年报文本 19.7 万字，单篇雪球/知乎好文可能达到数千字
- 无长度上限时，实现可能输出数百字 excerpt，实际等于整段搬运

**Why it matters**:
- 4.4 展示外部原文 excerpt 超过合理长度会带来版权/过度引用风险
- 如果 excerpt 过长，LLM rendering 可能被迫截断，丢失设计预期保留的推理链信息

**Required change**:
在 `external_viewpoint_reasoning_pack` schema 中增加：
```
"source_excerpt_max_chars": 200  # 单条 excerpt 不超过 200 字
```
并在 producer（LLM extractor 或 heuristic extractor）和 consumer（4.4 renderer）两端都强制执行。超过 200 字的 excerpt 在 rendering 阶段截断，不进入 4.4 展示。

#### MF3. fundflow_material_pack 的确定性汇总与 LLM 原始 items 层序未定义

**Evidence**:
- 设计建议新增 `fundflow_material_pack`（确定性 summary），同时 `adapt_all()` 已经把 fundflow 转成了 synthesis items
- 如果不做层序约定，LLM 在 4.3 synthesis 中同时看到：
  - Deterministic summary: "近5日主力净流入合计1234万元，signal=inflow_with_price_up"
  - Raw items: 每日的主力净流入/超大单/大单明细
- LLM 可能：
  1. 忽略 summary 自己重新求和，可能出错
  2. 把 `inflow_with_price_up` 写为"资金看多"而非"资金流入与上涨同向"的客观描述
  3. 从 raw 数据中得出与 summary 方向相反的结论

**Why it matters**:
本身不是数据错误问题，而是确定性汇总的设计意图（"避免 LLM 自己算"）与实现之间存在间隙。不明确层序会导致设计价值打折扣。

**Required change**:
在 Batch D 中明确：
1. 当 `fundflow_material_pack` 存在时，raw fundflow items 从 `funding_sentiment` theme 的 synthesis input 中移除（只保留 pack summary）
2. LLM prompt 中对 pack 使用规则："以下数据为确定性汇总，请基于此书写叙事，不要自行计算或反推"
3. 无 pack 时（无 fundflow 数据），4.3 输出受控降级模板（Quality Fix 已有四档 fallback）

#### MF4. section_too_generic 的检测标准需更精确

**Evidence**:
- 设计描述为："段落中出现大量'需关注/验证变量/产业链位置/市场情绪'等模板词，但缺少具体产品、数字、对象、时间点"
- 这里需要同时检测"模板词出现"和"具体内容缺失"两个条件
- 如果只做模板词检测，会误杀正常含"需关注"的研报段落
- 设计未给出"具体内容"的正则规则：产品名、数字、时间点、公司名的检测标准

**Why it matters**:
`section_too_generic` 是最容易误杀的 warning。如果实现太松则报不出问题，太紧则每个含"需关注"的正常段落都报警。

**Required change**:
实现时定义"具体内容"的检测模式为以下至少一项出现：
1. **数字**：`\d+(?:\.\d+)?` 匹配任何数字
2. **时间点**：季度（Q1/Q2/Q3/Q4）、年份（2025/2026）、月份、具体日期
3. **产品名**：当前股票 `product_exposure_terms` 中的任意术语
4. **公司名**：当前股票名或 competitors 中的任意公司
5. **来源引用**：`[^\d+]` 引用标记

只有当模板词出现 ≥ 2 个 AND 上述 5 类"具体内容"全不出现时，才触发 `section_too_generic`。这可以大幅降低误杀率。

### Nice-to-have

#### N1. Evidence Depth Pipeline 应明确定位为 Quality Fix v2（非平行或竞争）

**Evidence**:
- Quality Fix 已经在实施中（Batch 1.5 和 D 已完成，代码已修改），解决 5 个 P0/P1 硬错误
- Evidence Depth Pipeline 解决的是"安全但空"的软问题，是 Quality Fix 的自然延伸
- 两者的 Batch 编号重复（都有 A/B/C/D/E），容易混淆

**Suggestion**:
在设计文档开头增加一列"与 Quality Fix 的关系"表格，说明每个 Batch 是增量、替代还是依赖于 Quality Fix 的已完成代码。建议将 Evidence Depth Pipeline 称为 v2 或 "quality enhancement"，与 Quality Fix 区分。

#### N2. formal_financial_explanation_pack 的 heading extractor 可以复用 periodic report 缓存已有的 Jina 分段

**Evidence**:
- `复旦微电_2025_annual_jina.txt` 中段落标题清晰：`"二、经营情况讨论与分析"`（line 758）、`"营业收入变动原因说明"`（line 1327）
- Jina 缓存保留了原始 PDF 的段落体系
- 不需要复杂 NLP，regex heading 匹配即可提取

**Suggestion**:
实现时先验证 Jina 文本的分段一致性。如果所有缓存年报的标题格式一致（都是"X、XXX"结构），heading extractor 可以用简单的 regex 完成，不依赖 LLM。

#### N3. 4.3 显示增强可以复用 Quality Fix Batch D 的四档 fallback 架构

**Evidence**:
- Quality Fix 的 `deep_analysis_renderer.py` 已经实现 4.3 四档 fallback（funding+events 都存在 / 只有 funding / 只有 events / 都没有）
- Evidence Depth Batch D 新增 `fundflow_material_pack` 后，4.3 的 content 质量会从"受控降级模板"升级为"有数据基础 + 确定性摘要 + LLM 叙事"
- 两者是 complementary 的——four-tier fallback 保 4.3 存在，fundflow pack 填 4.3 内容

**Suggestion**:
在 Evidence Depth Batch D 实现前先确认 Quality Fix Batch D 的 deep_analysis_renderer.py 修改已合并到当前分支。如果已合并，Evidence Depth Batch D 只需要往 synthesis 路径中添加 fundflow_material_pack，不需要改 rendering 层。

#### N4. 回归测试集可以利用已存在的年报缓存

**Evidence**:
- `data/raw/periodic_reports/` 中有 中际旭创、圣邦股份、兆易创新 等回归候选股票的年报缓存
- 这意味着 Batch A（explanation pack）和 Batch B（business comparison pack）的回归测试有数据基础

**Suggestion**:
在 Batch E 回归测试中，加入对中际旭创或圣邦股份的年报 explanation pack 提取验证——不仅仅测试报告生成，还测试 explanation pack 是否能从回归股票的年报缓存中正确提取。

---

## Batch Split Recommendation

### Batch D: 4.3 资金面材料展示增强

- 补 `fundflow_material_pack` 确定性 summary
- 明确 raw fundflow items 受控移除层序（→ MF3）
- 4.3 renderer 复用 Quality Fix Batch D 的四档 fallback（需确认已合并）
- **依赖**: Quality Fix Batch D（renderer 层）
- **测试**: `test_technical_skills_contract.py`（已有桥接测试）、新增 `fundflow_material_pack` 确定性汇总测试
- **可拆性**: 不需要再拆

### Batch A: 年报/季报经营解释材料包

- 实现 heading extractor（复用 Jina 缓存的分段标题）
- 构建 `formal_financial_explanation_pack`
- 注入 knowledge_synthesizer 的 fundamentals prompt
- **依赖**: 年报缓存已存在（已验证 复旦微电 ✅）
- **测试**: `test_formal_financial_explanation_pack_extracts_management_discussion`（新增）、heading extractor 单元测试
- **可拆性**: 可以将 heading extractor 和 prompt injection 拆为两个子 batch
  - A.1: heading extractor + schema 定义 + extractor 测试
  - A.2: prompt injection + `fundamentals_repeats_fact_without_explanation` gate

### Batch B: 产品/同行基本面对比材料包

- 需要先明确 producer（→ MF1），不能直接用 LLM
- 建议自建 `peer_business_comparison_pack` 产生确定性 extractor（或高度约束 LLM 后处理）
- 注入 knowledge_synthesizer 的 industry_logic prompt
- **依赖**: MF1 解决后实施
- **测试**: `unsupported_peer_business_claim` gate 测试、pack 注入测试
- **可拆性**: 建议等 Batch A 完成后（共享 heading extractor 基础设施），再实施此 batch

### Batch C: 4.4 外部观点保真与分层展示

- 扩展 viewpoint claim schema 增加 reasoning_steps/numbers_used/assumptions
- 实现"观点卡片"渲染格式
- 增加 `source_excerpt_max_chars` 上限（→ MF2）
- **依赖**: 无（独立于 A/B）
- **测试**: `external_viewpoint_overcompressed` gate 测试、4.4 格式渲染测试
- **可拆性**: schema 扩展 + 渲染格式可以分离实施
  - C.1: schema 扩展（仅改 claim pipeline 输出字段）
  - C.2: 渲染格式变更（改 deep_analysis_renderer.py）

### Batch E: 报告空泛度质量门

- 实现 4 个新 warning gate
- `section_too_generic` 需要按 MF4 定义精确检测标准
- **依赖**: Quality Fix Batch A 已配置的 quality gate 基础设施
- **测试**: 新增 4 个 gate 的单元测试
- **可拆性**: 4 个 gate 可以独立实施，但建议至少 2 个 ready 后才部署

---

## LLM Hallucination Risk

### Highest-risk path: peer_business_comparison_pack 的循环 LLM 信任

**路径**:
1. LLM extractor 从 iwencai/研报摘要/wind 数据中提取产品对比，编写 `comparison` 字段
2. comparison 进入 `peer_business_comparison_pack`，带到 industry_logic synthesis prompt
3. LLM synthesis 读到 comparison，将其作为"正式来源的对比判断"写入 4.1
4. `unsupported_peer_business_claim` gate 检查 4.1 中的强对比词 → 但 pack 里已经有对应行 → gate 认为有支撑 → 不触发
5. 结果：LLM 自我循环，4.1 出现"复旦微电产品线优于紫光国微"但无第三方可验证来源

**Existing guard:**
- `usage` 分层（claim_eligible vs context_only）要求高置信行才能支撑强判断
- "不允许用纯社媒支撑 canonical 同行结论"
- "不允许从估值高低推出产品强弱"——具体已知模式
- `_check_peer_comparison_quality` gate 对 4.1/4.2 强同行比较词进行检测

**Missing guard:**
- Pack 中每行的 `evidence_type` 需要区分"确定性来源提取"和"LLM 推导"。如果是 LLM 推导的 comparison，其 `usage` 应该限制为 `context_only`，不能用于支撑"优于/劣于"
- `unsupported_peer_business_claim` gate 需要能分辨"pack 没有对应行"和"pack 有行但行是 LLM derived"两种情况

### Secondary risk: 多跳 L3 误判为 L2

**路径**:
行业材料标题含 "FPGA 在 AI 服务器中的应用" → `classify_direct_relevance` 检测到 "FPGA" ∈ product_exposure_terms → 标注为 direct_product → 进入 4.1/4.2 synthesis → LLM 可能写"AI 服务器需求增长利好复旦微电 FPGA 业务"

**Existing guard:**
- Direct-Only Canonical 严格按 terms 匹配，不是按逻辑传导
- `_has_explicit_unrelated_theme()` 检测 MLCC + 否定词
- `product_industry_mismatch` gate 检测明显错配

**Missing guard:**
- 无法在匹配 product terms 的同时判断是否为"纯 L3"内容——这是 hard NLP 问题，需要上下文理解。当前设计在 Direct-Only 框架下已是最优解

---

## Test Coverage Gaps

| 测试范围 | 当前覆盖 | 需要新增 |
|----------|----------|----------|
| heading extractor 单元测试 | ❌ 不存在 | `test_formal_financial_explanation_heading_extractor.py` — 验证 heading 提取能命中"经营情况讨论与分析"、排除"风险因素" |
| explanation_pack topic 提取 | ❌ 不存在 | `test_formal_financial_explanation_pack_extracts_management_discussion` — 验证 `revenue_change` topic 能抽到"营业收入变动原因说明"内容 |
| peer_business_comparison_pack 注入 | ❌ 不存在 | `test_peer_business_comparison_pack_injects_industry_logic_prompt` |
| unsupported_peer_business_claim gate | ❌ 不存在 | `test_unsupported_peer_business_claim_detects_llm_derived_rows` |
| vague_supply_chain_position warning | ❌ 不存在 | `test_vague_supply_chain_position` — 有/无变量的边界测试 |
| fundflow_material_pack 确定性汇总 | ⚠️ 部分存在 | `test_fundflow_material_pack_deterministic_summary` — 验证信号判断正确（inflow_with_price_up 等） |
| fundflow_claim_without_fundflow_pack gate | ❌ 不存在 | `test_fundflow_claim_without_fundflow_pack` — 4.3 无数据时不应编造资金结论 |
| 4.4 source_excerpt 长度限制 | ❌ 不存在 | 在 `curated_external_full_body_viewpoint_claims` 测试中增加 `test_source_excerpt_max_chars` |
| existing_viewpoint_overcompressed gate | ❌ 不存在 | 依赖 4.4 渲染格式实现后补 |
| section_too_generic warning | ❌ 不存在 | 按 MF4 的检测标准写边界测试（正常段 vs 空泛段） |
| 年报缓存 heading 一致性验证 | ❌ 不存在 | `test_periodic_report_jina_heading_structure` — 验证多只股票的年报 Jina 缓存标题格式一致 |

**现有可用测试基础设施**:
- `tests/utils/test_source_direct_relevance.py` — 已有（Quality Fix Batch B）
- `tests/reporter/test_report_quality.py` — 已有，可直接扩展（Quality Fix Batch A）
- `tests/utils/test_knowledge_synthesizer.py` — 已有 prompt-level 测试注入
- `tests/utils/test_periodic_report_structured_facts.py` — 已有单位归一化测试

---

## Implementation Readiness

**recommend_implementation: partial**

可以立即开始（部分 batch 的准备阶段无风险）:
- **Batch A 准备工作**（不需要修改 synthesis pipeline）:
  - 编写 heading extractor 原型，用 `data/raw/periodic_reports/复旦微电_2025_annual_jina.txt` 验证提取精度
  - 定义 `formal_financial_explanation_pack` schema + topic 枚举
  - 写 extractor 单元测试

- **Batch D 准备 + 实现**（独立于其他 batch）:
  - `fundflow_material_pack` 确定性汇总函数（pure function，无外部依赖）
  - 明确 raw fundflow items 受控移除逻辑（→ MF3）
  - 独立于 A/B/C，可以先做

- **Batch C 准备**:
  - 扩展 viewpoint claim schema 增加 reasoning_steps/numbers_used/assumptions 字段
  - 增加 source_excerpt_max_chars 限制（→ MF2）
  - 渲染格式变更可以后做

**需要先解决 must-fix 才能完整的 batch**:
- Batch B: 需 MF1 解决（明确 producer）后才能可靠实现
- Batch A 的 prompt injection: 需 heading extractor 验证通过后才能接入 synthesis
- Batch E 的 section_too_generic: 需 MF4 精确检测标准定义后实现

**与 Quality Fix 的依赖关系**:
- Quality Fix Batch D（renderer 四档 fallback）已修改 `deep_analysis_renderer.py` → Evidence Depth Batch D 需确认是否在同一分支上
- Quality Fix Batch A（quality gates）已修改 `report_quality.py` → Evidence Depth Batch E 可以在其基础上扩展
- Quality Fix Batch B（Direct-Only source filter）已实现 `source_direct_relevance.py` → 结构完备，Evidence Depth 的新 material pack 只增加输入不修改过滤逻辑

---

## Git Status

**审查状态**: 只读分析，未修改任何代码/配置/报告

进程中的变更（均为 Quality Fix 实施中的正常变更，与本审查无关）:
```
 M config/stocks.json
 M scripts/utils/... (多处，Quality Fix Batch 实施中)
 M tests/... (多处，Quality Fix 测试)
```

新文件（均为设计文档和审查记录，非代码变更）:
```
?? docs/agent_workflow/...
?? reports/
?? scripts/utils/source_direct_relevance.py  (Quality Fix Batch B)
?? tests/utils/test_source_direct_relevance.py  (Quality Fix Batch B)
```

报告文件目录（`reports/`）和设计审查目录（`docs/agent_workflow/`）无非预期文件。本审查继续遵循只读原则，未改动任何文件。
