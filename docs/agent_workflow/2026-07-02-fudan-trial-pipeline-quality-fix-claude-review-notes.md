# Claude 设计审查：Fudan Trial Pipeline Quality Fix v2

**审查者**: Claude Code（只读分析）
**审查日期**: 2026-07-02
**设计文档**: `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design.md`
**基线报告**: `reports/复旦微电_20260702.md`
**审查范围**: 5个 P0/P1 问题的设计决策、Direct-Only Canonical 规则、组件设计、Quality Gate 方案、测试计划、实施切分

---

## Verdict: **needs_revision**

**一句话总结**: 设计正确地识别了 5 个实际问题，Direct-Only Canonical 方向和实施切分顺序合理，但在 stock_config 可用性假设、4.3 缺失根因归属、product_exposure_terms 定义范围、以及回归样本防护方面存在需要修订的间隙。

---

## 阻塞项 (Blockers)

### B1. stock_config 可用性假设不成立

**严重程度**: 高 — 直接影响 Batch D 和回归样本（中际旭创/圣邦股份）的可行性。

设计文档多处假设 `stock_config.industry` 和 `stock_config.competitors` 普遍可用（Batch D Header、Direct-Only Canonical 第 3 条件）。但实际 `config/stocks.json` 中：

- **复旦微电**: 有 `industry`（`集成电路设计 / FPGA / MCU / 非易失存储`）和 `competitors`（5家）
- **中际旭创**: **无** `industry`、`competitors`、`peer_codes`、`peer_dimensions` 字段（仅 `keywords: ["CPO", "光模块", "光通信", "硅光", "数通"]`）
- **圣邦股份**: **无** `industry`、`competitors`、`peer_codes`、`peer_dimensions` 字段（仅 `keywords: ["模拟芯片", "电源管理", "信号链"]`）

设计的回归要求（Batch E："跑中际或圣邦回归"）和 Stop Condition（"修复导致中际/圣邦 formal_first 退化为空模板"）与本假设直接矛盾。

**影响链**:
1. Batch D Header: 没有 `industry`/`competitors` → quality gate 永远报警 → 无法产生 clean 回归报告
2. Direct-Only Canonical: 没有 `product_exposure_terms` → 所有行业新闻默认 `sector_background` → 4.1/4.2 被清空 → 中际旭创和圣邦的 formal_first 实质为空模板
3. 回归验收标准不成立：没有 product_exposure_terms 的股票不可能通过 Direct-Only 过滤

**建议修复**:
- 设计必须明确区分：**配置完备股票**（复旦微电）和 **配置不足股票**（中际旭创/圣邦）
- 对配置不足股票，Direct-Only 过滤 fallback 为更宽松规则（至少保留正式行业研报/iwencai 查询命中 keywords 的）
- 或者在执行 Direct-Only 之前先补齐所有存量股票的 `industry`/`competitors`/`product_exposure_terms`
- Batch D 的 quality gate 应为 warning（不是 fail），因为 header 缺失只在部分股票上可修

### B2. 4.3 缺失的根因归属错误

**严重程度**: 中 — 但设计将修复责任放在 quality gate（Gate A），而根因是 renderer 的静默省略。

`scripts/utils/reporter/sections/deep_analysis_renderer.py` 第 258-261 行：

```python
if funding or events:
    # render 4.3 content
    ...
# else: 静默地什么都不输出
```

这是 **renderer 的行为缺陷** — 4.3 的内容模块在 funding 和 events 都为空时选择完全不生成 section 标题。这不是 quality gate 应该解决的首选问题。

**问题**: 设计将 Gate A（missing deep-analysis subsection）列为 Batch A，但 renderer 端的 fallback 渲染才是根因修正。如果不改 renderer，Gate A 只能做 post-render 检测和拒绝，但无法在 report 中自动修复。

**建议修复**:
- 优先级：**先修 renderer fallback → 再补 quality gate 做第二道防线**
- Renderer fallback 输出设计文档给出的受控降级模板（已在设计第 4 节给出）
- Batch A 的 Gate A test 应该在 renderer fallback 就绪后验证

### B3. product_exposure_terms 定义范围与存量兼容性

**严重程度**: 中 — 可能导致回归样本的 4.1/4.2 被大幅度清空。

设计建议的复旦微电产品 terms（FPGA, FPAI, MCU, EEPROM 等）看起来合理，但对缺少同类配置的股票存在两个问题：

1. **中际旭创的关键词覆盖**: 其 `keywords` 为 `["CPO", "光模块", "光通信", "硅光", "数通"]`。但 iwencai 行业研报标题通常包含"光模块行业研究报告"或"通信行业周报"等 — 标题可能只含"光模块"或"光通信"，不能保证被 `_looks_like_sector_background()` 放过。如果生产环境没有为它配 `product_exposure_terms`，所有行业研报都被分类为 `sector_background`。

2. **圣邦股份的关键词**: `keywords` 为 `["模拟芯片", "电源管理", "信号链"]`。"模拟芯片"在 `_looks_like_sector_background()` 的检测列表里（因为含"芯片"子串） — 这意味着圣邦的主营业务关键词本身会被判定为 sector term。

**建议修复**:
- 设计应要求 Direct-Only Canonical 中新增一条：**如果 stock_config 没有 product_exposure_terms，则默认允许 stock_config.keywords 作为 product_exposure_terms**
- 或者：对没有 product_exposure_terms 的股票，回退到 `_looks_like_sector_background()` → 如果标题包含 keywords 中的任何一个词且来源是正式研报/行业研报/iwencai，则标记为 `direct_product` 而非 `sector_background`

---

## 必须修复项 (Must Fix)

### MF1. Header 源描述不准确

**现象**: 设计文档多次说"头部渲染仍读旧的硬编码/ctx 字段"，但实际来源是 `scripts/utils/report_skills/synthesis_skills.py` 中的常量 `INDUSTRY_MAP` 和 `COMPETITOR_MAP`，不是从 `stock_config` 读取。

```python
# synthesis_skills.py 中：
INDUSTRY_MAP = {
    "复旦微电": "集成电路设计 / FPGA / MCU / 非易失存储",
    # ... 其他股票
}
COMPETITOR_MAP = {
    "复旦微电": "紫光国微、安路科技、兆易创新、普冉股份、聚辰股份",
    # ... 其他股票
}
```

这意味着：
- `INDUSTRY_MAP` 中已有的股票（如复旦微电）即使没有 `stock_config.industry` 也能显示
- `INDUSTRY_MAP` 中没配置但 `stock_config` 有的新股票反而显示 `—`
- 实际修复点不是"从 `stock_config` 读取"，而是**优先从 `stock_config` 读取、fallback 到 `INDUSTRY_MAP` 常量**

Batch D 的设计应更新为：
1. 优先从 `stock_config.industry` / `stock_config.competitors` 读取
2. fallback 到 `INDUSTRY_MAP` / `COMPETITOR_MAP` 常量（向后兼容）
3. 两者都无才显示 `—` + quality warning

### MF2. 财务事实单位异常的根因分析不完整

**现象分析**: 报告核心事实显示"39.82万元"但 Q1 快照显示"10.32亿"。

**实际数据流**:
1. `periodic_report_structured_facts._filing_fact()`: `"value": f"{cell.get('text', '')}{unit}"`
2. 注释说 `"unit": "万元"` 来自于 `normalized_value` 结尾的"万元"被提取
3. `filing_facts_to_core_facts()`: 优先使用 `normalized_value`

**问题**: 核心问题是 upstream 的 cell 解析中，annual 财务表格的数值被错误归一化为"万元"。`39.82` 这个数值本身可能是正确的亿元数值，但 upstream parsing 错误地添加了"万元"单位。

设计说"修复结构化年报事实的金额单位归一化"是正确的方向，但还需要具体指示：
- 需要确认 upstream 的 cell parser 为什么将 39.82 亿元解析为 39.82 + "万元"（而不是 39.82 + "亿元"）
- 可能是从表格标题/列名中提取单位时出错
- Gate C 的检测逻辑需要有同报告财务快照的交叉验证

### MF3. 4.2 "数字缺失"的触发条件需要更精确

设计 Gate D 的目标是：当 formal_financial_fact_pack 有对应指标时，禁止 4.2 写"未提供最新数据"。

但当前报告中的"未提供"一共有 6 处：
- **营收数据** × 2（营收/利润/订单/客户 → 4.2 表格）：但 Q1 财务快照有营收 10.32 亿
- **利润趋势** × 1：Q1 利润 1.48 亿可用
- **订单兑现** × 2（存货+合同负债变化）：Q1 没有订单/存货详细数据 — 可能是真的缺失
- **客户结构** × 1：确实没有客户信息
- **费用率** × 1：确实没有费用率数据
- **管理层指引** × 1：确实没有指引

**结论**: 
- Q1 财务快照确实能堵住"营收"和"利润"的降级句
- "订单/客户结构/费用率/管理层指引"的缺失是真实的，不应被 gate 拦截
- Gate D 需要精确到指标级别，不是简单的"有财务包就不许写缺失"

### MF4. 测试计划缺少 renderer 层的测试

设计测试用例覆盖了：
- `test_source_direct_relevance.py`（新 helper 单元测试）
- `test_knowledge_synthesizer.py`（prompt 过滤测试）
- `test_periodic_report_structured_facts.py`（单位归一化）
- `test_report_quality.py`（quality gate 测试）
- `test_assembly_skills.py`（header 渲染）

但缺少：
- `test_deep_analysis_renderer.py` — 4.3 fallback 渲染测试
- `test_valuation_renderer.py` — header 从 stock_config 读取的测试

### MF5. Stop Condition 缺少对 Direct-Only 退化的检测

当前 Stop Conditions 有 7 条，但缺少一条关键条件：

> 如果 Direct-Only 过滤后 4.1/4.2 的 prompt items 少于 3（`KnowledgeSynthesizer.min_items`），导致 synthesis 整体降级为空或残篇，应触发 stop 或至少 strong warning。

在现有架构中，`_synthesize_theme()` 对每种 theme 检查 `min_items=3`。如果 Direct-Only 过滤后 items 不足 3，该 theme 会完全跳过。这可能导致：
- 对配置不足股票，4.1/4.2 全部跳过 → 报告严重残缺
- 但 current quality gate 不检测 synthesis 是否被跳过

---

## 建议改进 (Nice to Have)

### N1. `formal_financial_fact_pack` 可考虑利用 peer material 已有能力复用

目前设计建议新建 `formal_financial_fact_pack` 组件。但实际上 Phase 3b 的 `peer_comparison_material` 已经构建了一个完整的指标/来源/置信度体系。如果财务快照的数据也能进入 peer material 体系（作为 `formal_financial` usage 的行），就不需要新增一个并行的 fact pack 机制。

建议评估：能否将财务快照作为 `peer_comparison_material` 中 `target_only` 类型（无 peer 比较的行）直接复用，而非新建组件。

如果决定仍然新建 `formal_financial_fact_pack`，建议定义 schema 时与 `peer_comparison_material.v1` 保持一致的 `metric` 命名（如 `revenue`、`net_profit`），避免后续混合使用时需要 map 转换。

### N2. 行业研报的"间接关系"处理可以分层处理

设计当前将所有 `sector_background` 一刀切排除。但行业研报有不同的抽象层级：

| 层级 | 示例 | 建议处理 |
|------|------|----------|
| L1: 直接提及公司 | "复旦微电在 FPGA 领域的布局" | → `company_direct` |
| L2: 直接产品领域 | "FPGA 市场空间分析" | → `direct_product` |
| L3: 下游市场 | "AI 服务器 MLCC 需求" | → `sector_background`（排除） |
| L4: 宏观/政策 | "半导体国产替代政策" | → `sector_background`（排除） |

设计当前的 `_looks_like_sector_background()` 能处理 L3/L4 排除，但 L2 需要 `product_exposure_terms` 来判断。建议在 design doc 中明确这 4 层的区分和处理策略。

### N3. 4.3 section 的 renderer fallback 应该包含 funding 或 events 任一个存在时的混合模式

4.3 当前的 renderer 逻辑是 `if funding or events:` 二值判断。更好的 fallback 层级：

1. **有 funding 和 events** → 正常渲染资金面 + 催化剂时间线
2. **只有 funding** → 渲染资金面 + 降级说明"当前正式材料未形成可验证的催化剂时间线"
3. **只有 events** → 渲染催化剂时间线 + 降级说明"当前正式材料未提供资金面数据"
4. **两者皆无** → 受控降级整节

设计当前只描述了 #4。建议增加 #2/#3 的混合模式描述。

---

## 风险评估 (Risk Assessment)

### 方案风险: 中

**最大风险点**:
1. **回归风险 (高)**: Direct-Only 过滤对没有 `product_exposure_terms` 的存量股票（中际旭创、圣邦股份）影响不可控。如果 fallback 规则不当，回归报告质量可能显著下降。设计的 Batch E 放在最后才验证回归，可能导致大量重复工作。
2. **配置债务 (中)**: 为所有存量股票补齐 `industry`/`competitors`/`product_exposure_terms` 是一项中量级但必要的前置工作。如果不做，回归样本永远无法通过检查。
3. **财务单位修复不确定 (中)**: `periodic_report_structured_facts.py` 的 upstream cell parser 行为尚未完全理解。Gate C 检测到了异常，但根因修复可能需要更深入的数据流分析。

### 质量收益: 高

- Direct-Only Canonical 直接解决 MLCC 污染问题
- `formal_financial_fact_pack` 解决 4.2 "数字缺失"矛盾
- 4.3 fallback 渲染确保章节完整性
- Header config wiring 消除静态配置脱节

### 实施复杂度: 中高

- Batch A（Quality gates）: 低复杂度 — 纯加 post-render 检测
- Batch B（Direct-Only）: 中复杂度 — 新 helper + filter 扩展 + prompt 调整
- Batch C（Financial fact pack）: 中高复杂度 — 需要深入理解 upstream data flow 才能修单位
- Batch D（Header + fallback）: 低复杂度 — 纯配置读取和 renderer 修改
- Batch E（Smoke + regression）: 中复杂度 — 依赖 B-D 完成后才能验证，且可能需要多轮迭代

---

## 实施建议 (Implementation Recommendation)

### 是否继续执行: 建议是，但需先解决 Blocker

### 建议的实际 Batch 顺序

设计当前建议的 Batch A→B→C→D→E 顺序在逻辑上是合理的，但存在依赖问题需要调整：

```
Batch A: Quality gates first
  └─ 先写 gates → 锁定当前问题的检测 → 先红后绿

Batch 1.5: 补齐存量股票配置（新增，非设计原方案）
  └─ 在实施 B/D 之前，先为 中际旭创、圣邦股份 补齐 industry/competitors/product_exposure_terms
  └─ 否则 Direct-Only 和 Header fix 无法在回归样本上验证
  └─ 这不是代码变更，只是 config/stocks.json 的数据补齐

Batch D: Header + 4.3 renderer fallback
  └─ 先修 renderer → 再修 header
  └─ 这两项独立于 B/C，可以提前做
  └─ 4.3 renderer fallback 直接解决 4.3 缺失问题，让 Gate A 在回归时能 pass

Batch B: Direct-Only source relevance
  └─ 实现 source_direct_relevance.py
  └─ 扩展 _filter_items_for_theme()
  └─ 注意：配置不足股票的 fallback 规则

Batch C: Financial fact pack + unit normalization
  └─ 需要先完成 B 才能做 fact pack 注入（因为都在 synthesis 路径上）
  └─ 修 unit normalization 可能需要额外 data flow 分析

Batch E: Smoke and regression
  └─ 复旦微电 + 至少一只回归（补齐配置后）
```

**关键变化**:
1. 新增 **Batch 1.5**：补齐中际旭创和圣邦的 `industry`/`competitors`/`product_exposure_terms`
2. **Batch D 前移**到 B 之前，因为 renderer fallback 和 header 与 B 没有代码冲突
3. 回归验收需要在 Batch 1.5 之后才能进行

### 回归样本建议

- **复旦微电**: 完整验收（主目标）
- **中际旭创**: 回归 verify Direct-Only 不会误杀有 product_exposure_terms 的正式研报
- **圣邦股份**: 回归 verify `模拟芯片` keywords 不会被 sector filter 误杀

### 配置补齐（新增 Batch 1.5）

`config/stocks.json` 需要为所有存量股票补充：

```json
{
  "中际旭创": {
    "industry": "光模块 / 光通信 / CPO",
    "competitors": ["新易盛", "天孚通信", "光迅科技"],
    "product_exposure_terms": ["CPO", "光模块", "光通信", "硅光", "数通", "光引擎"],
    "peer_codes": [...]  // 如果需要 peer comparison
  },
  "圣邦股份": {
    "industry": "模拟芯片 / 电源管理 / 信号链",
    "competitors": ["矽力杰", "思瑞浦", "纳芯微"],
    "product_exposure_terms": ["模拟芯片", "电源管理", "信号链", "放大器", "ADC", "DAC", "开关稳压器"],
    "peer_codes": [...]  // 如果需要 peer comparison
  }
}
```

（具体 competitors 和 terms 需要由产品/分析师确认，此处仅为示意。）

---

## Git 状态

**审查基准**: `codex-report-quality-upgrade` branch

```
- 当前已包含 Phase 3c（peer comparison material → KnowledgeSynthesizer 集成）
- 尚未开始本设计的任何修改
- 设计文档存在于 `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design.md`
- 本审查报告为只读分析，未修改任何代码/配置/报告
```

---

## 附录: 关键文件参考

审查过程中读取的文件：

| 文件 | 用途 |
|------|------|
| `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design.md` | 设计文档主体 |
| `reports/复旦微电_20260702.md` | 基线报告（31KB，发现问题来源） |
| `config/stocks.json` | 股票配置（揭露 industry/competitors 缺失） |
| `scripts/utils/industry_news_relevance.py` | 行业新闻相关性分类（`_looks_like_sector_background`） |
| `scripts/utils/periodic_report_structured_facts.py` | 年报结构化事实（`_filing_fact` 单位拼接问题） |
| `scripts/utils/report_quality.py` | 现有 quality gates（peer gates） |
| `scripts/utils/reporter/sections/deep_analysis_renderer.py` | 深度分析 renderer（4.3 静默省略） |
| `scripts/utils/reporter/sections/valuation_renderer.py` | 估值 renderer（header 数据源） |
| `scripts/utils/report_skills/synthesis_skills.py` | Header 常量和 synthesis 编排 |
| `scripts/utils/knowledge_synthesizer.py` | Synthesis prompt builder |
| `tests/utils/test_knowledge_synthesizer.py` | Phase 3c 测试 |
| `tests/reporter/test_report_quality.py` | 现有 quality gate 测试 |
