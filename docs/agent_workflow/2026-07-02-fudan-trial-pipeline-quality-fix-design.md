# 复旦微电 Trial Pipeline Quality Fix v2 设计

## 背景

复旦微电正式 trial 已跑通：

- formal_first 正式源 intake；
- 年报/公告/iwencai/技术面/估值/同行 sidecar；
- 知乎 + 雪球详情页外部观点；
- 4.4 display-only narrative；
- Phase 3a/3b/3c peer comparison material layer。

但人工扫读 `reports/复旦微电_20260702.md` 后发现，当前质量门全绿并不代表报告内容合格。问题集中在 canonical synthesis 输入边界、财务事实包、章节完整性和 header/context 传递。

本设计继续遵守同一原则：**不手改报告，只修 pipeline 每一个产出过程**。

## 当前问题与根因

## Round 1 Review Delta

Claude Round 1 审查结论为 `needs_revision`。本版设计采纳全部 3 个 blocker 与 5 个 must-fix，并调整实施顺序。

### Accepted

- **B1 / B3 配置完备度**：Direct-Only Canonical 不能假设所有股票都有 `industry`、`competitors`、`product_exposure_terms`。新增 Batch 1.5，先补齐试点/回归股票配置；同时定义缺配置时的保守 fallback，避免中际旭创、圣邦股份被误杀为空模板。
- **B2 4.3 根因**：4.3 缺失的第一根因是 `deep_analysis_renderer.py` 在 `funding/events` 都为空时静默省略；renderer fallback 是主修复，quality gate 只做第二道防线。
- **MF1 Header 来源**：header 实际来自 `assembly_skills.py` 中的 `INDUSTRY_MAP/COMPETITOR_MAP` 常量；修复改为 `stock_config` 优先、常量 fallback。
- **MF2 财务单位根因**：单位异常根因在 upstream table/cell parser 的单位归一化，不能只修 `_filing_fact` 拼接；Batch C 必须追到结构化事实解析层。
- **MF3 财务缺失 gate 粒度**：仅对已有事实包支撑的指标触发矛盾检查。营收/利润可拦，订单、客户、费用率、指引缺失不应误判。
- **MF4 Renderer 测试**：补充 `test_deep_analysis_renderer.py` 与 header renderer/assembly 测试。
- **MF5 Direct-Only 退化 stop condition**：过滤后若核心 theme items 少于 `KnowledgeSynthesizer.min_items`，必须触发 strong warning 或受控降级，不能静默跳过。

### Rejected

- 无。

### Deferred

- 多跳行业链 validator 仍延期。用户明确担心 LLM 编造长逻辑链，因此本轮继续坚持 Direct-Only；多跳链条只可进入 4.4 display-only 或后续单独设计。

### R2 Required

是。Round 1 有 blocker，且设计边界调整涉及配置前置、renderer fallback、Direct-Only fallback 与财务 parser 根因，需要二轮只读审查。

### P0. MLCC 泛行业材料污染 4.1/4.2

**现象**

- 执行摘要把“AI 与汽车电子驱动 MLCC 需求增长”写成复旦微电看多论点。
- 4.1 几乎整段讲 MLCC 产业需求和技术路线。
- 同一节又写明“复旦微电主要产品为 FPGA 与存储芯片，不直接涉及 MLCC 技术路线”，形成自相矛盾。

**根因**

- `industry_news_relevance.classify_industry_news_relevance()` 对 `sector_background` 的 `allowed_sections` 当前包含 `4.1`。
- `KnowledgeSynthesizer._filter_items_for_theme()` 只对 `funding_sentiment/events_catalysts` 做行业新闻硬过滤；`industry_logic/fundamentals/valuation_debate` 仍能看到 `sector_background`。
- LLM 看到 MLCC 研报后，在 4.1 “产业逻辑”任务里强行消化材料，形成“泛 AI/汽车电子/半导体 -> 公司受益”的弱链条。

**设计决策**

本轮回退到 **Direct-Only Canonical**：

- 4.1/4.2/4.3 canonical synthesis 只允许“直接关系”材料。
- 多跳产业链材料默认不进入 4.1/4.2/4.3。即使看起来有产业逻辑，也先留在 Source Intake 观察或 4.4 display-only，直到 deterministic chain validator 能证明每一跳。
- LLM 不负责自行补全“行业事件 -> 多层传导 -> 公司受益”的长链条。

### P0. 核心事实基座单位错误

**现象**

核心事实基座显示：

- 营业收入 `39.82万元`
- 归母净利润 `2.32万元`
- 经营现金流量净额 `7.84万元`

这与报告同页 Q1 财务快照的亿元级量级冲突。

**根因候选**

- `periodic_report_structured_facts._filing_fact()` 直接拼接 `cell.text + unit`，同时 `normalized_value` 可能已经被上游错误归一为万元。
- `filing_facts_to_core_facts()` 优先使用 `normalized_value`，导致错误单位进入核心事实基座。
- 当前 quality gate 没有检测“财务指标量级异常”或“同一报告内财务量级冲突”。

**设计决策**

- 修复结构化年报事实的金额单位归一化。
- 核心事实展示金额时必须使用经过 sanity check 的 normalized amount。
- 对营业收入、净利润、经营现金流这类核心金额增加量级保护：若上市公司全年收入小于 1 亿元但同报告其他正式财务快照已有亿元级收入，触发 quality error。

### P0. 4.3 缺失但质量门未拦截

**现象**

报告深度分析从 4.2 直接跳到 4.4，没有 `### 4.3 资金面与催化剂时间线`。

**根因**

- 第一根因在 `DeepAnalysisRenderer._deep_analysis()`：当 `funding_sentiment` 和 `events_catalysts` 都为空时，renderer 静默省略 4.3 标题和正文。
- `check_report_quality.py` 目前也不要求 4.1/4.2/4.3 全部存在，因此没有把静默省略拦下来。

**设计决策**

- 4.1/4.2/4.3 必须由 renderer 保证渲染。
- 若对应材料不足，renderer 输出受控降级说明；不能静默缺失。
- quality gate 对缺失 4.1/4.2/4.3 直接 fail，作为 renderer fallback 之外的第二道防线。

### P0. 4.2 未消费已有财务事实

**现象**

报告前面已有 Q1 财务快照：

- 营收 10.32 亿，同比增长 16.2%；
- 归母净利润 1.48 亿，同比增长 8.9%。

但 4.2 仍反复写“外部材料未提供复旦微电最新营收/利润/费用率/管理层指引”。

**根因**

- 财务快照/正式财务接口数据没有稳定进入 4.2 synthesis prompt。
- `KnowledgeSynthesizer` 主要看 source intake items；财务表格属于 renderer/data layer，不一定在 synthesis input 内。

**设计决策**

- 新建或强化 `formal_financial_fact_pack`，在 synthesis 前构建并注入 4.2。
- 来源优先级：
  1. 季报/年报结构化事实；
  2. CNINFO 公告/业绩快报；
  3. 东财/akshare/tencent 已拉取的财务快照；
  4. 已验证的 manual financial fallback。
- 如果 fact pack 有营收/利润/毛利率/费用率/现金流任一核心指标，4.2 不得写“外部材料未提供最新营收/利润数据”。

### P1. Header 元信息没有使用 config

**现象**

报告顶部显示：

- `所属赛道: —`
- `可比公司: —`

但 `config/stocks.json` 中已配置：

- `industry`: `集成电路设计 / FPGA / MCU / 非易失存储`
- `competitors`: 紫光国微、安路科技、兆易创新、普冉股份、聚辰股份。

**根因**

- 头部渲染位于 `assembly_skills.py`，当前直接读取 `INDUSTRY_MAP/COMPETITOR_MAP` 常量。
- 这不是纯“旧 ctx 字段”问题，而是 config-first 迁移未覆盖 header。

**设计决策**

- header 的行业/赛道与可比公司优先读取 `stock_config.industry` 和 `stock_config.competitors`。
- 若 `stock_config` 缺失，fallback 到 `INDUSTRY_MAP/COMPETITOR_MAP` 常量，保持存量股票兼容。
- 两者都缺失才显示 `—`，quality gate 给 warning。

## Batch 1.5 配置完备度前置

Direct-Only Canonical 依赖股票级 exposure 配置。实现 Direct-Only 前，先补齐至少三只验证股票：

- `复旦微电`
  - 已有 `industry/competitors/peer_codes/peer_dimensions`；
  - 新增 `product_exposure_terms`：FPGA、FPAI、RF-FPGA、RFSoC、PSoC、MCU、智能电表芯片、车规MCU、安全与识别芯片、RFID、非挥发存储器、非易失存储、EEPROM、NOR Flash、SLC NAND。
- `中际旭创`
  - 新增 `industry`: 光通信 / 光模块 / CPO / 硅光；
  - 新增 `competitors/product_exposure_terms`，至少覆盖 CPO、光模块、光通信、硅光、数通、800G、1.6T、光引擎、光连接。
- `圣邦股份`
  - 新增 `industry`: 模拟芯片 / 电源管理 / 信号链；
  - 新增 `competitors/product_exposure_terms`，至少覆盖 模拟芯片、电源管理、信号链、运放、ADC、DAC、电源管理芯片。

缺配置 fallback：

- 若 `product_exposure_terms` 缺失，使用 `stock_config.keywords` 作为临时 exposure terms，但必须剔除泛词：半导体、芯片、国产替代、AI、汽车电子、集成电路、行业、产业链。
- 对正式行业研报/iwencai，若标题或正文命中非泛化 `keywords`，可标为 `direct_product`；否则降级 `sector_background`。
- 对缺配置股票，如果过滤后某个 theme 有效 items 少于 3，不允许静默跳过；必须记录 `direct_relevance_underfilled` warning，并由 renderer 输出受控降级段落。

## Direct-Only Canonical 规则

### 直接关系定义

一条材料可进入 4.1/4.2/4.3 canonical synthesis，当且仅当满足至少一个条件：

1. **公司直接材料**
   - 标题或正文直接提及目标公司、股票代码、公告主体；
   - 公司公告、年报、季报、业绩快报、调研纪要。

2. **直接产品/业务暴露**
   - 命中 `stock_config.product_exposure_terms`；
   - 对复旦微电，建议初始 terms：
     - `FPGA`, `FPAI`, `RF-FPGA`, `RFSoC`, `PSoC`
     - `MCU`, `智能电表芯片`, `车规MCU`
     - `安全与识别芯片`, `RFID`
     - `非挥发存储器`, `非易失存储`, `EEPROM`, `NOR Flash`, `SLC NAND`
   - 不包含泛化 terms：`半导体`, `芯片`, `国产替代`, `AI`, `汽车电子`, `集成电路`, `MLCC`。
   - 若 `product_exposure_terms` 缺失，只能用去泛化后的 `stock_config.keywords` 临时补位；若 keywords 也不足，行业资讯默认不可进 canonical synthesis。

3. **直接同行/竞争材料**
   - 直接提及 config 中 competitors 或 peer sidecar；
   - 只能支撑同行对比，不得扩写成公司业务事实。

4. **正式财务/技术/行情数据**
   - `formal_financial_fact_pack`;
   - `peer_comparison_material`;
   - 技术面/行情/估值/资金数据。

### 间接链条处理

多跳链条（例如“存储涨价 -> 晶圆厂产能紧张 -> CIS 排产减少 -> CIS 涨价”）本轮不进入 canonical 4.1/4.2/4.3，除非后续单独实现 chain validator 并满足：

- 每一跳有 `news_text` 或 `stock_config` 支撑；
- chain manifest 落盘；
- post-render gate 能验证正文链条与 manifest 一致；
- LLM 不允许新增 manifest 外 hop。

在本轮中，多跳链条只能：

- 进入 Source Intake 分层观察；
- 或进入 4.4 display-only，且必须以“外部观点/待验证线索”表达；
- 或被丢弃。

### 行业材料层级

| 层级 | 示例 | 本轮处理 |
|------|------|----------|
| L1 公司直接 | `复旦微电 2025 年报`、`复旦微电 FPGA 布局` | `company_direct`，可进入 4.1/4.2/4.3 |
| L2 直接产品领域 | `FPGA 行业研究`、`电源管理芯片需求` | 命中 `product_exposure_terms` 时为 `direct_product`，可进入 4.1/4.2 |
| L3 下游/旁路市场 | `AI 服务器 MLCC 需求`、`存储涨价挤占 CIS 排产` | 本轮不进 canonical；仅可作为 4.4 待验证观察或 source intake 背景 |
| L4 宏观/泛行业 | `半导体国产替代政策`、`设备板块走弱` | 不进 canonical |

## 组件设计

### 1. `source_direct_relevance.py`（新 helper）

职责：对 `SynthesisItem` 打 direct-only canonical 可见性标签。

建议输出：

```python
{
  "canonical_relevance_class": "company_direct" | "direct_product" | "direct_peer" | "formal_financial" | "sector_background" | "unrelated",
  "allowed_canonical_sections": ["4.1", "4.2"],
  "matched_terms": ["FPGA"],
  "blocked_reason": "sector_background_no_direct_exposure"
}
```

规则：

- 公司直接材料 -> `company_direct`, 可进 4.1/4.2/4.3。
- 产品直接材料 -> `direct_product`, 可进 4.1/4.2；是否进 4.3 需是事件或催化剂。
- 同行材料 -> `direct_peer`, 可进 4.1/4.2。
- 财务事实 -> `formal_financial`, 可进 4.2。
- 泛行业背景 -> `sector_background`, 不进 canonical synthesis。

### 2. `KnowledgeSynthesizer._filter_items_for_theme()`

当前只过滤 4.3；需扩展为对所有 deep-analysis themes 生效：

- `industry_logic`: 仅 `company_direct/direct_product/direct_peer/formal_financial` 中与 4.1 相关者。
- `fundamentals/valuation_debate`: 仅 `company_direct/direct_product/direct_peer/formal_financial` 中与 4.2 相关者。
- `funding_sentiment/events_catalysts`: 仅 `company_direct` 或明确事件类 direct_product；不允许 sector_background。

若老数据没有 `canonical_relevance_class`：

- 对正式公告/年报/研报维持兼容；
- 对行业资讯默认保守降级为 `sector_background`，除非直接提公司名、同行名，或命中 `product_exposure_terms` / 去泛化后的 `keywords`。

Stop / warning 条件：

- 过滤前有材料、过滤后某 theme items 少于 `KnowledgeSynthesizer.min_items` 时，记录 `direct_relevance_underfilled`。
- 不允许 LLM 因 items 不足自行借用 `sector_background`。
- renderer 对 underfilled theme 输出受控降级说明，quality gate 记录 warning；若整段完全缺失则 fail。

### 3. `formal_financial_fact_pack`

构建位置：`SynthesisSkill.run()` 中 baseline synthesis 前。

输入：

- `ctx["financial_abstract"]` 或 report data 中已拉取的财务摘要；
- `ctx["periodic_report_filing_core_facts"]`;
- `stock_raw["announcements"]` 中财务公告；
- 已归一化 quote/valuation data。

输出：

```python
{
  "schema": "formal_financial_fact_pack.v1",
  "stock_name": "复旦微电",
  "facts": [
    {
      "metric": "revenue",
      "label": "营业收入",
      "value": 10.32,
      "unit": "亿元",
      "period": "2026Q1",
      "yoy": 16.2,
      "source_ref": "财务快照:东方财富"
    }
  ]
}
```

注入规则：

- 只注入 4.2 prompt；
- 不是新的 footnote source，不生成 `[^n]`；
- 用于阻止“数字缺失”降级文本。

单位归一化根因：

- Batch C 不能只修 `_filing_fact()` 的字符串拼接。
- 必须检查 upstream table/cell parser 如何从年报表格标题、列名或 cell metadata 提取单位。
- 金额类指标统一输出 `normalized_amount`（数值）、`normalized_unit`（亿元/万元/元）、`raw_text`、`source_unit_hint`。
- 若年报 parser 输出与同报告财务快照量级冲突，fact pack 降级该事实并在 quality gate 中报 `financial_unit_conflict`，不得让核心事实基座展示错误单位。

缺失文本检查粒度：

- 只对 fact pack 已有的指标触发矛盾检查。
- 例如已有 `revenue/net_profit` 时，4.2 不得写“未提供最新营收/利润数据”。
- 若没有 `orders/customer_structure/expense_ratio/guidance`，4.2 可以保留“未提供订单/客户结构/费用率/管理层指引”的受控缺失表达。

### 4. 章节完整性渲染

Renderer 或 synthesis fallback 必须保证：

- 4.1 存在；
- 4.2 存在；
- 4.3 存在。

若没有有效材料，渲染受控降级：

```markdown
### 4.3 资金面与催化剂时间线

当前正式材料未形成可验证的资金面或催化剂时间线；本节不使用泛行业新闻补链条。
```

4.3 fallback 分四档：

1. `funding` 和 `events` 均存在：正常渲染资金面 + 催化剂时间线。
2. 只有 `funding`：渲染资金面，并补一句“当前正式材料未形成可验证的催化剂时间线”。
3. 只有 `events`：渲染催化剂时间线，并补一句“当前正式材料未提供足够资金面数据”。
4. 两者都无：渲染整节受控降级模板。

### 5. Header config wiring

报告头部：

- `所属赛道`: 优先 `stock_config.industry`，fallback `INDUSTRY_MAP[stock_name]`;
- `可比公司`: 优先 `stock_config.competitors[:5]`，fallback `COMPETITOR_MAP[stock_name]`;
- 两层都缺失时保留 `—`，并给 quality warning。

## Quality Gate 设计

### Gate A: missing deep-analysis subsection

Fail 条件：

- 有 `## 四、深度分析`，但缺 `### 4.1`、`### 4.2` 或 `### 4.3`。

允许例外：

- 章节存在但写明正式材料不足；
- 章节存在但内容为受控降级模板。

### Gate B: product-industry mismatch

Fail 条件：

- 4.1/4.2 出现某个行业主题超过阈值；
- 该主题不在 `product_exposure_terms`;
- 同节出现“不直接涉及/不同/无直接关系”等否定语；
- 或 citation 来源是 sector_background。

Warning 条件：

- 股票缺少 `product_exposure_terms`，但 fallback keywords 仍保留行业研报；
- 过滤后某 theme items 少于 `KnowledgeSynthesizer.min_items`，触发 `direct_relevance_underfilled`。

复旦 fixture：

- `MLCC` 出现在 4.1/4.2；
- `product_exposure_terms` 不含 MLCC；
- 报告写“复旦微电主要产品为 FPGA 与存储芯片，不直接涉及 MLCC 技术路线”；
- 应 fail。

### Gate C: financial fact unit sanity

Fail 条件：

- 核心事实中 `营业收入/归母净利润/经营现金流` 单位为万元且数值小于合理阈值；
- 同报告其他位置存在亿元级同类指标；
- 或同一年度官方 source text 包含“亿元”但核心事实渲染为“万元”。

### Gate D: financial data missing contradiction

Fail 条件：

- 4.2 出现“未提供最新营收/利润/毛利率/费用率数据”等降级句；
- 同报告财务快照或 formal_financial_fact_pack 已有同一指标。

不 fail 的情况：

- 没有订单、客户结构、费用率、管理层指引等具体 fact 时，4.2 可以写这些维度缺少可验证数据。
- 不做“有营收/利润事实包 -> 禁止所有缺失表达”的粗粒度判断。

### Gate E: header config missing

Warning 条件：

- `stock_config` 有 industry/competitors，但报告 header 仍显示 `—`。

## 测试计划

### Unit tests

- `tests/utils/test_source_direct_relevance.py`
  - MLCC 对复旦微电 classified as `sector_background`；
  - FPGA/FPAI/MCU/EEPROM classified as `direct_product`；
  - 紫光国微/安路科技 classified as `direct_peer`；
  - 公司公告 classified as `company_direct`。

- `tests/utils/test_knowledge_synthesizer.py`
  - 4.1/4.2 prompt 不包含 MLCC sector_background；
  - 4.1/4.2 prompt 包含 FPGA direct_product；
  - 4.3 prompt 不包含 sector_background；
  - 4.2 prompt 包含 formal_financial_fact_pack；
  - 有财务 fact pack 时，不允许生成“未提供营收/利润数据”降级模板。

- `tests/utils/test_periodic_report_structured_facts.py`
  - 亿元/万元/千元/元金额归一化正确；
  - 复旦 2025 年营业收入示例输出 `39.82亿元`，不是 `39.82万元`。

- `tests/reporter/test_report_quality.py`
  - 缺 4.3 fail；
  - MLCC product mismatch fail；
  - 核心事实单位异常 fail；
  - 4.2 财务缺失文本与财务快照矛盾 fail；
  - header config missing warning。

- `tests/reporter/test_assembly_skills.py`
  - header 从 `stock_config` 渲染 industry/competitors；
  - stock_config 缺失时 fallback `INDUSTRY_MAP/COMPETITOR_MAP`；
  - 两层都缺失时显示 `—` 并产生 warning。

- `tests/reporter/test_deep_analysis_renderer.py`
  - funding/events 都空时仍渲染 `### 4.3` 受控降级；
  - 只有 funding 时渲染资金面 + 催化剂缺失说明；
  - 只有 events 时渲染催化剂 + 资金面缺失说明；
  - 4.1/4.2 也不得静默缺失。

### Smoke tests

实现后至少跑：

```text
python3 scripts/run_stock_report.py --stock 复旦微电 --no-pdf
python3 scripts/check_report_quality.py reports/复旦微电_YYYYMMDD.md
python3 scripts/check_report_prose_quality.py reports/复旦微电_YYYYMMDD.md
python3 scripts/check_report_source_boundary.py reports/复旦微电_YYYYMMDD.md
bash tools/ci_grep_gates.sh
git diff --check
```

验收预期：

- 4.1/4.2 不再出现 MLCC 作为公司逻辑；
- 4.3 存在，若无材料则受控降级；
- 核心事实单位正确；
- 4.2 使用已有财务事实；
- header 显示行业和可比公司；
- 4.4 仍 display-only；
- 4.1-4.3 仍无雪球/知乎/微信泄漏。

回归样本：

- 至少跑一支已有股票：中际旭创或圣邦股份。
- 目的：确认 direct-only 过滤不会误杀已有正式行业研报。
- 回归前必须完成 Batch 1.5 配置补齐，否则不能用回归结果判断 Direct-Only 质量。

## 实施切分

### Batch 1.5: Config completion first

- 补齐复旦微电、中际旭创、圣邦股份的 `industry/competitors/product_exposure_terms`。
- 对存量缺字段股票保持 config 加载兼容，不能强制所有股票一次性补齐。
- 加配置测试：三只试点股票具备 direct-only 所需字段；未知股票仍能加载。

### Batch D: Header + renderer fallback

- header 优先读取 stock_config，fallback 常量。
- `DeepAnalysisRenderer` 保证 4.1/4.2/4.3 存在。
- 4.3 实现四档 fallback。
- 加 renderer 层测试。

### Batch A: Quality gates second

在 renderer fallback 后，把复旦当前报告的失败模式写成 tests：

- 缺 4.3；
- MLCC product mismatch；
- 核心事实单位异常；
- 财务缺失文本矛盾；
- header config missing。

Gate 是第二道防线，不替代 renderer 修复。

### Batch B: Direct-only source relevance

- 新增 helper；
- 对 source items 赋 `canonical_relevance_class`；
- 扩展 `_filter_items_for_theme()`；
- 加 prompt-level tests。
- 若过滤后 items 少于 `min_items`，记录 underfilled warning 并交给 renderer 降级，不能静默跳过。

### Batch C: Financial fact pack + unit normalization

- 修年报 structured facts upstream 单位解析；
- 构建 formal financial fact pack；
- 注入 4.2；
- 加 metric-specific contradiction gate。

### Batch E: Smoke and regression

- 重跑复旦；
- 跑中际或圣邦回归；
- 只在验收通过后提交。

## Stop Conditions

- 需要修改雪球/CDP/Playwright/外部采集逻辑：停止，另开任务。
- 需要让 LLM 执行多跳行业链推理：停止，本轮不做。
- 4.1-4.3 出现社媒/知乎/雪球/微信原文：停止并回滚该方向。
- 财务单位无法从源数据可靠推断：先输出 source manifest 和 warning，不让 LLM 猜。
- 修复导致中际/圣邦 formal_first 退化为空模板：停止并重新审设计。
- Direct-Only 过滤后 4.1/4.2 items 少于 `KnowledgeSynthesizer.min_items` 且 renderer 无法受控降级：停止。
- 需要把未验证的多跳行业链写入 4.1/4.2/4.3：停止。
