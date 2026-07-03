# 复旦微电 Trial Evidence Depth Pipeline 设计

## 背景

复旦微电正式 trial 已经解决了一批“硬错误”：

- MLCC 等泛行业材料不再污染 4.1/4.2/4.3；
- 4.1-4.3 缺节、财务单位错误、社媒泄漏、4.4 引用脚注等门禁已补；
- peer comparison sidecar 已接入，能给 4.1/4.2 提供基础同行指标；
- 本轮新增 `technical.fund_flow -> stock_raw["fundflow"]` 桥接，使百度/东财资金流向可进入 synthesis 和资金关注度评分。

但人工扫读 `reports/复旦微电_20260702.md` 后，报告仍有“安全但空”的问题：

- 4.1 竞争格局只列指标，缺少产品、应用、同行优劣和产业位置的硬核基本面对比；
- 4.1 “供应链位置”在缺披露时容易写废话，应转成“供应链是否紧张、产能是否充裕、供需是否改善”等可验证变量；
- 4.2 营收/利润/毛利率/费用率重复核心事实基座，缺少年报/季报对变化原因的原文解释；
- 4.2 订单客户与管理层指引提取不足，年报里可能有经营计划、客户结构、产品进展、研发方向等信息；
- 4.3 没有实质资金信息，需接入 A 股资金流向材料；
- 4.4 精选外部观察过度压缩，把雪球/知乎好文的数字、逻辑链条和反方假设削成单句观点，信息密度不够。

本设计继续遵守原则：**不手改单份报告，只修 pipeline 的材料生产、过滤、合成和门禁。**

## Round 1 Review Delta

Claude Round 1 审查结论为 `needs_revision`，无 blocker，4 个 must-fix。本文采纳全部 must-fix，并把本设计定位为 **Quality Fix v2 / Evidence Depth Enhancement**：前一轮 Quality Fix 解决“错误、泄漏、缺节、单位、泛行业污染”；本轮解决“合规但空泛、材料信息密度不足”。

### Accepted

- **MF1 / peer_business_comparison_pack 生产者**：不能让 LLM 生成 `comparison` 后再让 LLM 消费，避免循环信任。新增 producer 规则：优先确定性 heading/keyword extractor；若使用 LLM 辅助抽取，只能生成 `context_only`，且 confidence 上限 0.65，不能支撑“优于/劣于/领先/落后”。
- **MF2 / source_excerpt 长度**：`external_viewpoint_reasoning_pack.source_excerpt` 单条最大 200 个中文字符；producer 与 renderer 双层截断，4.4 展示不搬运整段原文。
- **MF3 / fundflow 层序**：有 `fundflow_material_pack` 时，4.3 synthesis 只看 deterministic summary，不再看 raw fundflow items；raw rows 仅保留在 pack/sidecar 供审计，避免 LLM 自行求和或得出相反结论。
- **MF4 / section_too_generic 标准**：只有“模板词 >=2 且具体内容五类全缺失”才触发 warning，降低误杀。

### Rejected

- 无。

### Deferred

- 通用多跳产业链 validator 仍延期。本轮继续 Direct-Only；多跳链条只可进 4.4 display-only 待验证观察。
- Batch B 的完整实现需等 producer 细化后再做；可先做 Batch D、Batch A heading extractor 原型、Batch C schema 扩展。

### R2 Required

否。Round 1 无 blocker，4 个 must-fix 均为设计精化且已在本文闭环。实现前若 Batch B 改用 LLM producer 或 Batch C 改变 4.4 schema/display-only 边界，再触发单独审查。

## 总体目标

把 4.1-4.4 从“安全可追溯但空泛”推进到“材料足、推理可查、边界清楚”：

1. 4.1 用正式源和可审计材料写产品/竞争/供应链，不用泛行业补链条。
2. 4.2 用年报/季报原文解释财务变化，不重复核心事实表。
3. 4.3 接入资金流向、融资余额、持仓/机构等真实资金材料；无材料时明确降级。
4. 4.4 保留外部好文的完整增量逻辑，但坚持 display-only，不进入评分、风险、目标价、4.1-4.3。
5. 对多跳行业逻辑保持保守：没有 deterministic chain manifest 的长链条只能进 4.4 待验证观察，不能进 canonical 4.1-4.3。

## 非目标

- 不把知乎/雪球/微信原文放进 4.1-4.3 canonical synthesis。
- 不修改评分/技术指标算法。
- 不手工编辑 `reports/复旦微电_20260702.md`。
- 不在本轮实现通用多跳产业链 validator。用户提出的 “存储涨价 -> 晶圆产能紧张 -> CIS 排产减少 -> CIS 涨价” 这类链条，本轮只能作为 4.4 display-only 待验证观察。

## 已完成子项：资金流向桥接

### 现状

`a-stock-data` 中推荐的百度资金流向接口已经在仓库里有对应实现：

- `scripts/utils/data_collector.py::_baidu_fund_flow_history()`
- `TechnicalCollector.collect()` 会把结果写到 `technical["fund_flow"]`

但 synthesis/scoring 只读 `stock_raw["fundflow"]`，导致 4.3 和资金关注度评分看不到这批数据。

### 已做修复

- `scripts/utils/report_skills/technical_skills.py`
  - 新增 `_normalize_fund_flow_rows()`，兼容百度 `main_in/super_net_in/...` 与东财 `main_net/super_big_net/...`。
  - 新增 `_bridge_technical_fund_flow()`，当 `stock_raw["fundflow"]` 为空时，将 `technical["fund_flow"]` 归一后桥接过去。
  - 不覆盖已有 `stock_raw["fundflow"]`，避免专门资金流模块的结果被技术采集覆盖。
- `scripts/utils/source_adapter.py`
  - `FundFlowAdapter` 兼容净流入字段和分单字段，输出 “主力净流入/超大单/大单/小单/涨跌” 文本。

### 已验证

- `tests/reporter/test_technical_skills_contract.py`
  - 技术采集资金流向会桥接到 `stock_raw["fundflow"]`；
  - 已有 `stock_raw["fundflow"]` 不被覆盖。
- `tests/utils/test_source_adapter.py`
  - 百度 PAE 字段能转成 `资金流向` synthesis item。
- focused tests：141 passed。
- `tools/ci_grep_gates.sh` 与 `git diff --check` 通过。

## Batch A：年报/季报经营解释材料包

### 问题

4.2 现在主要复述营收、利润、毛利率等数字。数字前面核心事实基座已经出现，4.2 应该回答“为什么变了、哪些业务拖累/支撑、公司怎么解释”。

### 设计

新增 `formal_financial_explanation_pack`，与已有 `formal_financial_fact_pack` 分离：

- `fact_pack` 负责数字；
- `explanation_pack` 负责年报/季报/公告里的解释性原文和结构化摘要。

建议 schema：

```json
{
  "schema": "formal_financial_explanation_pack.v1",
  "stock_name": "复旦微电",
  "source_doc": "2025年年度报告",
  "rows": [
    {
      "topic": "revenue_change",
      "metric": "营业收入",
      "excerpt": "公司营业收入变化原因的原文片段",
      "normalized_summary": "收入增长主要来自...",
      "source_ref": "公告/年报",
      "page_hint": "经营情况讨论与分析",
      "confidence": 0.85
    }
  ]
}
```

主题范围：

- `revenue_change`：营收变化原因；
- `profit_change`：净利/扣非净利变化原因；
- `gross_margin_change`：毛利率变化原因；
- `expense_rnd`：销售/管理/研发费用或研发投入说明；
- `inventory_cashflow`：存货、现金流、应收账款解释；
- `orders_customers_guidance`：订单、客户、经营计划、管理层展望。

### 生产者

优先复用已有年报全文/结构化事实，不新增网络源：

- `periodic_report_structured_facts.py`
- 年报全文缓存/抽取结果；
- CNINFO 公告全文；
- 已缓存的 `data/raw/`。

实现方式：

1. 先做确定性 heading/keyword extractor，从年报全文切出“经营情况讨论与分析”“主营业务分析”“核心竞争力”“经营计划”“风险因素”等段落。
2. 只截取包含公司业务、收入、利润、毛利率、费用、研发、订单、客户、产能、库存、现金流的片段。
3. 每条片段保留 `excerpt_hash` 和 `source_doc`，不能让 LLM 自行编造解释。

### 消费者

`KnowledgeSynthesizer._build_prompt()` 在 `theme_key == "fundamentals"` 时追加：

- “正式经营解释材料包（仅供 4.2 使用，非新增引用）”；
- 明确：已有核心事实基座数字不得重复成表；应引用解释片段说明原因；
- 没有解释片段时，允许写“正式材料未披露具体原因”，但不能把缺失写成已有数据。

### 门禁

新增或增强 `report_quality.py`：

- 如果 4.2 同时出现核心事实基座已有的营收/利润数字，并且没有“原因/主要由于/受...影响/公司解释/管理层称”等解释性词，给 warning：`fundamentals_repeats_fact_without_explanation`。
- 如果 `formal_financial_explanation_pack` 有 `orders_customers_guidance`，但 4.2 写“未提供订单/客户/指引”，给 error。
- 如果年报解释片段缺失，不能 fail，只能允许降级。

## Batch B：产品/同行基本面对比材料包

### 问题

当前 peer sidecar 主要是毛利率、PE、PS、市值等指标，容易让 4.1 变成数字表。用户需要的是：

- 产品线对比；
- 应用领域对比；
- 优于/劣于同行的基本面依据；
- 产业红利期下个股机会的闭环。

### 设计

新增 `peer_business_comparison_pack`，与 `peer_comparison_material` 分离：

- `peer_comparison_material`：财务/估值指标；
- `peer_business_comparison_pack`：产品、应用、客户、竞争定位、研发方向、产业红利暴露。

建议 schema：

```json
{
  "schema": "peer_business_comparison_pack.v1",
  "target": "复旦微电",
  "peers": ["紫光国微", "安路科技"],
  "rows": [
    {
      "dimension": "产品线",
      "target_position": "FPGA/MCU/非易失存储",
      "peer": "紫光国微",
      "peer_position": "特种集成电路/智能安全芯片",
      "comparison": "业务同属特种IC，但产品结构不同",
      "evidence_type": "formal_or_professional",
      "source_refs": ["年报:复旦微电", "iwencai:紫光国微研报摘要"],
      "confidence": 0.72,
      "usage": "claim_eligible"
    }
  ]
}
```

### 生产者

`peer_business_comparison_pack` 必须由材料层 producer 生成，不能由最终写 4.1 的 LLM 自行生成后再自行消费。

优先级：

1. **确定性 producer（默认）**
   - 从目标公司和同行的年报/公告/iWencai 研报摘要/券商研报摘要中按 heading 和产品关键词抽取。
   - 只做 “产品线/应用领域/客户结构/研发方向/经营计划” 的文本片段归类。
   - `comparison` 只能来自确定性模板，例如：
     - 两家公司都命中同一产品词：`overlap_product_area`
     - 目标公司命中特定产品词、peer 未命中：`target_disclosed_only`
     - peer 命中特定产品词、目标未命中：`peer_disclosed_only`
     - 双方产品词不同：`different_product_mix`
   - 不输出 “优于/劣于/领先/落后”，只输出可审计的差异描述。

2. **LLM-assisted extractor（仅可选）**
   - 只能在输入为正式/专业来源片段时运行；
   - 每条 row 必须保留 `source_excerpt_hash`；
   - `evidence_type` 标记为 `llm_extracted_from_formal_source`；
   - `confidence <= 0.65`；
   - `usage = "context_only"`；
   - 不得支撑 4.1 中的强比较词或强定位词。

3. **禁止 producer**
   - 不允许用雪球/知乎/微信生成 canonical `peer_business_comparison_pack`；
   - 不允许用估值高低、PE/PS 高低推导产品强弱；
   - 不允许让最终 synthesis LLM 补写 `comparison` 字段。

### 来源

允许来源分层：

- canonical 4.1 可用：
  - 公司年报/公告；
  - iWencai 行业/个股研报摘要；
  - 券商研报摘要；
  - 正式行业研报；
  - `peer_comparison_material` 中的高置信指标。
- 4.4 display-only 可用：
  - 知乎/雪球/微信中的对手比较好文；
  - 需要保留原文数字、假设和反方约束；
  - 不进入 4.1。

### 规则

- 没有至少两条正式/专业来源支撑时，不写“优于/劣于/领先/落后”。
- 只有单来源或低置信时，只能写“可跟踪对比线索”。
- 不允许用纯社媒支撑 canonical 同行结论。
- 不允许从估值高低推出产品强弱。
- 如果 4.1 强定位词只被 `evidence_type=llm_extracted_from_formal_source` 的行支撑，仍然触发 `unsupported_peer_business_claim`。

### 消费者

`KnowledgeSynthesizer` 只在 `industry_logic` 追加高置信 `peer_business_comparison_pack`：

- 4.1 prompt 要求优先输出：
  - “产品/应用/对手/公司位置/验证变量”表；
  - 不再输出泛泛“供应链位置”，除非 pack 有产能、供需、客户或库存材料。

### 门禁

- `unsupported_peer_business_claim`：4.1 出现“优于/劣于/领先/落后/替代/唯一”等相对或强定位词，但 sidecar/pack 无对应支撑。
- `vague_supply_chain_position`：4.1 出现“供应链位置重要/产业链地位突出/受益产业链”但没有产能、供需、客户、库存、订单、价格等具体变量。

## Batch C：4.4 外部观点保真与分层展示

### 问题

当前 4.4 narrative 把雪球/知乎好文压缩成 4 段短观点，丢掉了很多有用内容：

- 估值帖里的三种估值方法、A/H 折价、净利假设区间；
- 竞争对比里的对手业务结构、盈利质量差异；
- G60、FPAI、MCU 等线索的推理前提和待验证项。

### 设计

新增 `external_viewpoint_reasoning_pack` 或扩展现有 viewpoint digest：

每条 claim 不只保留 `claim`，还保留：

- `source_excerpt`：原文关键片段，单条最多 200 个中文字符；
- `reasoning_steps`：作者自己的推理步骤；
- `numbers_used`：原文出现的数字；
- `assumptions`：净利/估值/产业兑现假设；
- `counterpoints`：反方约束；
- `verification_need`：需要正式源验证的点；
- `display_topic`：估值分歧、产品竞争、产业线索、风险传闻等。

示例：

```json
{
  "claim_id": "fudan-xq-val-002",
  "display_topic": "valuation_debate",
  "claim": "外部观点认为A股价格已经接近乐观情景上沿",
  "source_excerpt": "三种方法收敛到中性情景375-420亿...",
  "reasoning_steps": [
    "用紫光国微作为特种IC盈利参照",
    "用2026净利7.5亿和50倍PE推导中性市值",
    "用PS方法交叉验证"
  ],
  "numbers_used": ["375-420亿", "46-52元", "7.5亿", "50倍"],
  "assumptions": ["2026净利修复到7.5亿"],
  "counterpoints": ["若军工订单恢复不及预期，合理估值下修"],
  "display_only": true,
  "needs_cross_check": true
}
```

### 渲染

4.4 不再只做短段落，可改为“观点卡片”：

- **外部估值分歧**：观点、推理步骤、关键假设、反方约束；
- **产品与竞争线索**：观点、来源数字、待验证变量；
- **产业/供应链待验证线索**：明确“未进入正式分析”。

控制长度：

- 每个 topic 最多 2 张卡；
- 每张卡最多 4 行；
- `source_excerpt` 展示最多 200 个中文字符；producer 写入时截断一次，renderer 展示前再次截断一次；
- 所有卡必须带 inline footnote；
- 仍保持 Preview disclaimer。

### 门禁

- 4.4 可以出现目标价、估值区间、外部观点，但必须带“外部观点/作者认为/待验证”框架，不得写成系统结论。
- 4.4 任何观点不得泄漏到执行摘要、评分、风险、目标价、最终建议。
- `source_excerpt` 不得超过 200 个中文字符；超过则 producer 或 renderer 截断，并在 JSON 中保留 `excerpt_truncated: true`。
- 4.4 展示应优先显示作者推理结构，而不是长原文摘录；`reasoning_steps/numbers_used/assumptions/counterpoints` 不计入原文引用长度。

## Batch D：4.3 资金面材料展示增强

### 已完成基础桥接

技术采集中的百度 PAE 资金流向已桥接到 `stock_raw["fundflow"]`，adapter 已能生成 synthesis item。

### 后续增强

若正式报告生成时拿到 `fundflow`：

- 4.3 应优先展示：
  - 近 5 日主力净流入合计；
  - 超大单/大单方向；
  - 与股价涨跌是否同向；
  - 如果连续流出，写成资金压力；如果连续流入但股价弱，写成分歧。
- 若拿不到资金数据：
  - 4.3 输出受控降级：“当前未取得可用主力资金流向数据”，不要写无效表格。

建议新增 deterministic `fundflow_material_pack`，避免 LLM 自己算：

```json
{
  "schema": "fundflow_material_pack.v1",
  "rows": [...],
  "summary": {
    "days": 5,
    "main_net_total": 1234.0,
    "super_large_net_total": 567.0,
    "price_change_total_pct": 3.2,
    "signal": "inflow_with_price_up"
  }
}
```

### 层序规则

`fundflow_material_pack` 是 4.3 的唯一资金流向输入层。

- 若 pack 存在：
  - raw fundflow rows 不再作为 `资金流向` synthesis items 进入 `funding_sentiment` prompt；
  - raw rows 只保留在 pack 的 `rows` 或 sidecar 中供审计；
  - prompt 明确写入：“以下为确定性汇总，请基于 summary 写资金面，不要自行求和、不要从 raw rows 反推相反结论。”
- 若 pack 不存在但 raw fundflow rows 存在：
  - 先构建 pack；不直接喂 raw rows。
- 若 pack 与 raw rows 都不存在：
  - 4.3 走 renderer 的受控降级模板：“当前未取得可用主力资金流向数据”。

### Signal 口径

`signal` 只能是客观描述，不是投资判断：

- `inflow_with_price_up`：主力净流入与股价上涨同向；
- `inflow_with_price_down`：主力净流入但股价下跌，表示资金/价格分歧；
- `outflow_with_price_up`：主力净流出但股价上涨，表示上涨质量待验证；
- `outflow_with_price_down`：主力净流出与股价下跌同向；
- `mixed_or_insufficient`：方向不稳定或数据不足。

禁止将 signal 渲染为“资金看多/看空/买入信号”。只能写“资金与价格同向/背离/分歧”。

## Batch E：报告空泛度质量门

### 问题

现有 quality gate 更擅长抓“错误/泄漏/引用/重复”，不擅长抓“看起来合规但没有信息量”。

### 新增 warning

- `section_too_generic`：
  - 4.1/4.2/4.3 段落中出现大量“需关注/验证变量/产业链位置/市场情绪”等模板词，但缺少具体产品、数字、对象、时间点。
- `vague_supply_chain_position`：
  - “供应链位置”段没有供应商/客户/产能/供需/库存/价格/交期任一变量。
- `fundamentals_repeats_core_facts`：
  - 4.2 重复核心事实基座数字，缺少变化原因或管理层解释。
- `external_viewpoint_overcompressed`：
  - 4.4 有外部观点素材，但 narrative 没有保留任何 `reasoning_steps/numbers_used/assumptions`。

这些先作为 warning，不阻塞生成；积累 3-5 份报告后再决定哪些升为 error。

### `section_too_generic` 精确定义

为降低误杀，`section_too_generic` 只在同时满足以下条件时触发：

1. 模板词命中数量 >= 2。
   - 模板词示例：`需关注`、`验证变量`、`产业链位置`、`市场情绪`、`后续跟踪`、`有望受益`、`结构性机会`、`景气度`、`催化剂`、`不确定性`。
2. 下列 5 类具体内容全部缺失：
   - **数字**：`\d+(?:\.\d+)?`；
   - **时间点**：`20\d{2}`、`Q[1-4]`、`一季度`、`二季度`、`三季度`、`四季度`、`\d+月`、`\d+日`；
   - **产品名**：`stock_config.product_exposure_terms` 任一术语；
   - **公司名**：目标股票名或 `stock_config.competitors` 任一公司；
   - **引用标记**：`\[\^\d+\]`。

如果段落有引用但没有产品/数字，也不触发 `section_too_generic`，因为引用可让人工继续追溯；这种情况可由更具体的 warning（如 `vague_supply_chain_position`）覆盖。

## Failure Modes 与测试

| Failure Mode | 表现 | 测试/门禁 |
|---|---|---|
| 年报解释片段没抽到 | 4.2 仍只列数字 | `test_formal_financial_explanation_pack_extracts_management_discussion` |
| 年报片段错配 | 把风险因素写成业绩原因 | `topic` keyword + source heading 测试 |
| 同行基本面对比用社媒支撑 | 4.1 写“优于紫光国微”但只有雪球来源 | `unsupported_peer_business_claim` |
| 供应链废话 | “供应链位置突出”无变量 | `vague_supply_chain_position` |
| 4.4 过度压缩 | 好文只剩一句观点 | `external_viewpoint_overcompressed` |
| 4.4 泄漏 | 外部观点进入评分/摘要/风险 | 现有 source boundary + display-only tests |
| 多跳链条进 canonical | 4.1/4.2 写“存储涨价传导到CIS涨价” | Direct-Only source filter + chain phrase gate |
| 资金流向缺失仍写判断 | 4.3 写资金流入但无 fundflow | `fundflow_claim_without_fundflow_pack` |

## 建议实施顺序

1. **Batch D 收口**：在已有桥接基础上补 `fundflow_material_pack` 和 4.3 deterministic summary，最小风险。
2. **Batch A**：年报/季报解释材料包，优先解决 4.2 空泛。
3. **Batch B**：产品/同行基本面对比材料包，解决 4.1 空泛。
4. **Batch C**：4.4 保真展示，解决外部好文信息损耗。
5. **Batch E**：空泛度 quality warnings，防止下一只股票复发。

## Stop Conditions

- 需要修改 `KnowledgeSynthesizer` prompt 或 4.4 叙事 schema 时，必须先让 Claude 做只读设计审查。
- 任何把社媒/微信/知乎材料放入 4.1-4.3 的方案都停止。
- 任何多跳产业链进入 canonical synthesis 的方案都停止，除非另有 deterministic chain manifest 设计和 gate。
- 如果年报全文/缓存不存在，不得抓外网补；先降级并记录缺失。
- 如果实现导致 4.1-4.3 formal_first/source_boundary 失败，停止并回滚该批次设计。
