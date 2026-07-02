# Batch 3 同行/对手材料层设计 — Claude 只读审查笔记

**审查日期**: 2026-07-02
**审查类型**: 只读设计审查（未修改任何文件）
**设计文档**: `docs/agent_workflow/2026-07-02-peer-comparison-material-layer-design.md`
**Branch**: `codex-report-quality-upgrade`

---

## Verdict

**needs_revision** — 总体方向正确，配置迁移 + material pack + quality gate 的三段架构合理，且吸收了 Round 1 review 的"不要过早引入 `peer_source_queries`"意见。但 `peer_comparison_material.py` 的设计存在 3 个必须修订的边界模糊点，以及 2 个应在实现前明确的风险。

---

## Blocker

**无。** 所有问题可以在当前框架内修复，不需要回退到完全不同方案。

---

## Must Fix

### MF1. `peer_comparison_material.py` 的 `rows[].confidence` 无计算公式，无法阻止低置信文字进入 4.1/4.2

**设计文档第 156-158 行**: "It should mark rows as `low_confidence` when the peer basis is only a title/snippet."

**问题**: 只说了"什么情况下标记 low_confidence"——但没有说 **confidence 值的计算公式**。`peer_comparison_material` 的 `rows[].confidence` 决定了第 177 行 prompt 规则是否允许 LLM 写出"优于/弱于同行"的结论：
- `confidence >= 0.7` → LLM 可用
- `confidence < 0.7` → 只能写成"可作为后续对比线索"

如果 confidence 没有量化逻辑，每一行都会默认设为 `0.5` 或 `1.0`，导致全部被 LLM 当成可用项。Batch 2b 的 `industry_news_relevance.py` 有明确的 confidence 计算公式（supported hops / product_supported 等）。这里也应该有等价物。

**要求修复**: 在设计文档中补充 `rows[].confidence` 的量化逻辑——至少定义三档阈值和每档的触发条件：

- `confidence >= 0.8` → deterministic metrics 直接可比的（两个公司都有同一维度数值，且来自同一来源、同口径、同报告期）
- `0.5 <= confidence < 0.8` → 有 source refs 但 metric 来源不同口径，或一方缺失
- `confidence < 0.5` → 仅靠 formal source title/snippet 提及
- 无 input 支撑 → 不输出该行（第 159 行已正确声明）

---

### MF2. 第 2 层 synthesis guardrail 依赖 LLM 不误用 low-confidence 行——和 MF1 相同风险模式

**设计文档第 176-178 行**:
```
peer pack may support "优于/弱于/接近同行" only when the relevant row has
source refs and confidence >= 0.7;
low-confidence rows must be written as "可作为后续对比线索" or omitted.
```

**问题**: 这个 guardrail 是 **prompt 内的软约束**。LLM 收到 peer pack 后，即使某行标记为 `confidence: 0.3`，LLM 看到数字对比（例如"毛利率: 55% vs 60%"）仍可能在正文中写出"毛利率显著低于同行"。Batch 2b 已证明 LLM 会忽视 prompt 约束使用"看起来重要"的信息。

和第 2 层一样（参见 Batch 2b review MF1），这里需要 **输入层硬过滤**，而非仅依赖 prompt：
- 在构建 4.1/4.2 prompt 时，如果 peer pack 中某行 `confidence < 0.5`，不应输入该行给 LLM；
- `0.5 <= confidence < 0.7` 的只作为"上下文提示"输入，不应包含对比数字；
- 只有 `confidence >= 0.7` 的完整行才进入 4.1/4.2 prompt 作为可用论据。

**要求修复**: 在数据流 Step 4（设计文档第 161-178 行）中增加 prompt input 前的 confidence-based 过滤步骤。类似 `SyntaxSugar._filter_items_for_theme` 的模式。

---

### MF3. Quality gate 的 `unsupported_peer_superlative` 只拦截强比较词，漏掉弱但错误的相对比较

**设计文档第 199-201 行**:
```python
1. `unsupported_peer_superlative`
   - Trigger when 4.1/4.2 contains "行业第一/唯一/全面领先/显著优于/远强于"
     without peer pack source support.
```

**问题**: 这个正则词表太窄。LLM 可以写出以下语句而不触发 gate：
- "毛利率与紫光国微有一定差距"（含"差距"但不在词表中）
- "利润规模不及行业头部企业"（含"不及"）
- "该指标落后于同行"（含"落后于"）
- "公司产品线覆盖范围窄于紫光国微"（含"窄于"）

这些虽然不是"行业第一/显著优于"级别的强确认词，但属于**未经 peer pack 支撑的相对结论**，同样不该出现在 4.1/4.2 正文中。

**要求修复**: 将 gate 的检测范围扩展为两档：
- **强比较词 error**（当前词表 + "优于/领先/远超/全面占优/更具优势"）→ 即使有 pack 也要再验证
- **弱比较词 warning**（"对标/差距/落后于/不及/接近/略高于/窄于/好于"）→ 若包存在且对应维度有数据则 pass，否则 warning

同时 `peer_claim_without_peer_pack`（第 202-204 行）也应该检查这些弱比较词，不仅是"优于同行/弱于同行/行业平均/对标"。

---

### MF4. 现有 6 个硬编码 stocks 的回归策略未定义

**设计文档第 91-92 行**: "Existing `COMPETITOR_MAP` / `COMPETITOR_CODES` remain fallback during migration."

**问题**: 当前 `COMPETITOR_MAP` 有 6 个硬编码 stock（黑芝麻智能、长春高新、三花智控、中简科技、圣邦股份、乐鑫科技）。设计说"migration"但没有明确定义迁移的完成条件——Phase 3a 后哪些 stock 可以有 peer pack？如果只有复旦微电迁移了 config，其他 6 个的 fallback 逻辑仍然运行，那么：
1. `data_fetcher.py:531` 的 `COMPETITOR_MAP.get(stock_name, [])` 是否被 `peer_config.get_peer_names()` 替代？
2. `competitor_metrics_table()` 第 623 行写死了 `COMPETITOR_MAP.get(stock_name, [])`——是否被 `peer_config` 替代？
3. 回归测试（中际旭创、圣邦至少一支）设计没有在测试计划中出现。

**要求修复**: 在设计文档中明确：
- **最小可发布的 migration 完成条件**（例如：复旦微电 config 迁移后 `peer_config.get_peer_names("复旦微电")` 返回 config 值，`get_peer_names("圣邦股份")` 回退到 `COMPETITOR_MAP`）；
- 在测试计划中加入一条回归测试：`test_data_fetcher_peers.py` 验证 config 和非 config stock 都返回预期竞争对手；
- Phase 3c 前后分别跑一次中际旭创报告，确认 `competitor_metrics_table` 渲染结果一致。

---

## Nice To Have

### N1. Config migration 的顺序应该更清晰——2 条路径

当前只提到"Fudan config"，但未列出迁移顺序。建议按最稳定→最多变排序：

1. 先迁移 `constants.py` 中已有 competitors 的 6 个 stock（黑芝麻智能/长春高新/三花智控/中简科技/圣邦股份/乐鑫科技），这些 fallback 值已知可回退；
2. 再迁移复旦微电（新写 `competitors` + `peer_codes`）；
3. 最后迁移中际旭创（已有 **竞争对手财务指标对比** 表格，需确保 regress 一致）。

### N2. `peer_dimensions` 的限制性太弱，且与 `competitor_metrics_table` 表格冲突

`peer_dimensions` 第 87-88 行说"is optional and only constrains summaries; it must not create unsupported facts"。但如果 LLM 看到 `peer_dimensions: ["毛利率与研发投入"]`，可能在 4.2 中写出包含"研发投入"的比较——而 `fetch_competitor_metrics()` 并不返回研发费用数据。**建议**：`peer_dimensions` 的值应约束于 `fetch_competitor_metrics()` 已返回的 metric keys，超出的值在数据流 Step 3 之前被静默丢弃。

另外，当前报表已在"二、估值与财务快照"处有一个 **竞争对手财务指标对比** 表格（`competitor_metrics_table` 输出）。如果 4.1/4.2 再写一个同行对比表，会有两个重叠表格。建议在 Step 5（第 181-194 行）明确：4.1 的同行表是**替代 or 补充**现有估值区的表格？推荐方案：4.1 的同行表只做"定性对比"（业务线/赛道位置/市场地位），不重复估值区的定量数字。

### N3. `peer_pack_social_leak` 质量门需要明确定义 source_type 白名单

第 204 行：`Peer pack source refs must not contain Xueqiu/Zhihu/WeChat/social-only labels for 4.1-4.3.`

和 `_check_industry_chain_claims` 不同，这里的白名单构建依赖于 `source_refs` 字段的格式。建议在设计中明确白名单格式（例如：`source_refs` 必须以 `公告:`、`研报:`、`指标:`、`行业资讯:` 开头才允许用于 4.1-4.3，否则触发 error），这样可以直接复用 `check_report_source_boundary.py` 的 `SOURCE_WHITELIST_BOUNDARY` 检查逻辑（而不需要在 `report_quality.py` 中另写一个新检查）。

---

## 最大风险在哪里

**风险 1（高）: `rows[].confidence` 无量化计算公式（MF1），导致全部行被 LLM 误用。**
这是最紧迫的问题。Batch 2b 已经证明 confidence 必须有硬编码公式，不能外包给"设计时决定"。如果没有公式就进实现，`peer_comparison_material.py` 输出的 confidence 要么全是 1.0 导致 prompt 约束空洞化，要么全是 0.5 导致无行可用。**解决方案：MF1。** 

**风险 2（高）: LLM 在收到完整 peer pack（含低置信行）后自行编写未被允许的比较句（MF2）。**
相同的"软约束不可靠"问题——Batch 2b review 的 MF1 已经指出了。输入层必须在 prompt 构建时按 confidence 过滤，不能靠 prompt 文本来限制 LLM 行为。**解决方案：MF2。**

**风险 3（中）: Quality gate 漏掉非 superlative 的错误比较。**
如果 LLM 写"毛利率与紫光国微有一定差距"，gate 因词表中只有"行业第一/显著优于"等而放行。这种弱比较虽然没有强确认词危害大，但同样违背"无支撑不比较"原则。**解决方案：MF3。**

**风险 4（中）: Phase 3c 的 synthesis prompt 改动可能导致中际/圣邦回归退化。**
当前 `competitor_metrics_table()` 已经直接输出表格，如果 peer pack 进入 4.1/4.2 prompt，LLM 可能重复写出同样的数字，导致两个同行表内容重叠。**解决方案：MF4 回归策略。**

---

## 是否建议进入实现

**⚠️ 建议分阶段进入，但 Phase 3b 和 3c 之间需要先修 MF1/MF2。**

| 阶段 | 准备度 | 备注 |
|------|--------|------|
| **Phase 3a：Config Migration + Metrics** | ✅ **可进** | 纯配置迁移 + data_fetcher lookup 改读 config。不改 prompt，不引入 pack，风险极低 |
| **Phase 3b：Peer Material Pack** | ❌ **需先修 MF1** | confidence 无公式就无从判断 rows 质量。pack 输出格式需要等到 MF1 确定后再定 |
| **Phase 3c：Synthesis Prompt Integration** | ❌ **需先修 MF1 + MF2** | 软约束不可靠，必须等输入层 hard filter 实现后再做 prompt 集成 |
| **Quality Gates** | ✅ **可并行** | 词表的补全（MF3）可以和 3a 并行做，不依赖 pack |

### 建议拆分

```
PR-3a（安全，建议先发）:
├── peer_config.py（config 优先 + 回退 constants）
├── stocks.json 复旦微电 + peer_codes
├── data_fetcher.py 改读 peer_config（保留 fallback）
├── competitor_metrics_table() 改读 peer_config
└── 回归测试 + 中际旭创 smoke

PR-3b（需设计修订后）:
├── peer_comparison_material.py（等 MF1 confidence 公式确定）
├── sidecar 落盘
├── quality gates（unsupported_peer_superlative / peer_claim_without_pack / social_leak）
└── 独立测试，不改 prompt

PR-3c（等 MF2 硬过滤确定后）:
├── 4.1/4.2 prompt 输入层按 confidence 过滤
├── 4.1/4.2 synthesis prompt 注入
├── 复旦微电 smoke
└── 中际旭创/圣邦回归
```

---

## 特别说明

### 设计文档对 Round 1 N3 的吸收

✅ **好的**: `peer_source_queries` 被明确排除（第 28-29 行），没有引入需要外部抓取的字段。config shape 的 `competitors` + `peer_codes` 与 Round 1 建议一致。

### 与 Batch 2b 的交互

Peer pack 的 `rows[].source_refs` 必须是 formal/professional 来源。Batch 2b 的 `industry_news_relevance` 分类的 `sector_background` 新闻不应进入 peer pack 的 source_refs。设计文档第 42 行已提到"mainstream industry news only when classified as relevant to 4.1"，这个约束是正确的，但建议在数据流 Step 3 中显式注明：`rows` 构建时必须过滤 `relevance_class == "sector_background"` 的条目。

### `competitor_metrics_table` 的去留

当前报告已有 `competitor_metrics_table()` 输出。如果 peer pack 进入 4.1/4.2 prompt，并且 LLM 参照 pack 中的 metric 数据写了第二个同行表，报告将出现两个同行表格（一个在所有分析之前，一个在 4.1/4.2 内部）。设计文档说"不新增报告大段"（第 182 行），但在"二、估值与财务快照"处的现有表格与"4.1 同行对比表"之间的逻辑关系尚未明确。建议在 Step 5 注明是否需要将现有 `competitor_metrics_table` 收敛到 4.1 内，避免两处散布相同数据。

---

## Git Status

**无变化。** 本审查为只读审查，未创建、修改或删除任何文件。

```
$ git status --short
   M scripts/utils/a_stock_source_intake.py
   M scripts/utils/knowledge_synthesizer.py
   M scripts/utils/report_quality.py
   M scripts/utils/report_skills/assembly_skills.py
   M scripts/utils/report_skills/synthesis_skills.py
   M tests/reporter/test_assembly_skills.py
   M tests/reporter/test_report_quality.py
   M tests/reporter/test_synthesis_skills.py
   M tests/utils/test_a_stock_source_intake.py
   M tests/utils/test_knowledge_synthesizer.py
   ?? scripts/utils/industry_news_relevance.py
   ?? tests/utils/test_industry_news_relevance.py
```

（Batch 2b 改动，未引入新的非预期文件）

---

## 汇总

| 类别 | 状态 |
|------|------|
| **Verdict** | needs_revision |
| **Blocker** | 0 |
| **Must fix** | 4（MF1~MF4） |
| **Nice to have** | 3（N1~N3） |
| **Phase 3a 进入实现** | ✅ 可立即进入 |
| **Phase 3b 进入实现** | ⚠️ 需先修 MF1（confidence 公式） |
| **Phase 3c 进入实现** | ⚠️ 需先修 MF1 + MF2（硬过滤） |
| **peer_source_queries 规避** | ✅ 明确排除，符合 Round 1 要求 |
| **Git status** | clean（无本审查引入的改动） |
