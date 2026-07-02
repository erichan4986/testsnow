# 复旦微电 Trial Pipeline 质量修复设计 — Claude 只读审查报告 Round 1

**审查日期**: 2026-07-02
**审查类型**: 只读设计审查（未修改任何文件）
**设计文档**: `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-design.md`
**Branch**: `codex-report-quality-upgrade`（clean）

---

## Verdict

**needs_revision** — 设计方向全部正确，问题归因到 pipeline 而非单份报告修补的原则也完全正确。但三个 Batch 中各有 1–2 个实现细节需要进一步明确，才能在进入实现前消除歧义。

---

## Blocker

**无。** 设计文档的全部 8 个问题均被正确归因，没有需要回退方向的错误。

---

## Must Fix

### MF1. 4.4 citation hydration — `_normalize_viewpoint_narrative_citations()` 会过滤掉部分 citation

**现状**: `synthesis_skills.py:308-311` 的 `_normalize_viewpoint_narrative_citations()` 对 citation 做了一层过滤：
```python
if (
    value.get("source_type") == "curated_external_analysis_evidence"
    and value.get("verification_status") == "professional_observation"
):
    normalized[ref_id] = value
```

**问题**: 复旦微电 narrative JSON 中的 12 个 citation 的 `source_type` 各不相同——雪球专栏为 `"xueqiu_column_observation"`，雪球评论为 `"xueqiu_comment_observation"`，知乎为 `"zhihu_selected_observation"`。这些**都不等于** `"curated_external_analysis_evidence"`，因此全部会被过滤掉。hydration 后即使 `citation_refs` 填充正确，渲染出的 `[^n]` 也会指向一个空的 citations dict，导致脚注不可见。

**建议修复方向**:
- 在 `_normalize_viewpoint_narrative_citations()` 中增加对 `"xueqiu_column_observation"`、`"xueqiu_comment_observation"`、`"zhihu_selected_observation"` 的豁免；**或者**
- 将 narrative JSON 的 citation 全部 normalize 为 `"curated_external_analysis_evidence"` + 各自的 `verification_status`，保持字段标准一致。

**设计文档补充**: 第 40 行提到映射逻辑，但需要在设计文档中明确说明 normalization 兼容性问题，否则实现时会发现 hydration 成功但脚注依然为空的诡异现象。

---

### MF2. Market cap sanity — 需要明确归一到哪一个层

**现状**:
- `data_fetcher.py:337-347`（A 股分支）直接写入 `mcap_yi` 和 `float_mcap_yi`，无归一化层
- `valuation_renderer.py:78` 直接读取 `quote.get("float_mcap_yi", 0)`，无 sanity check
- 设计文档第 60-63 行说"在 quote normalization 层增加 market_cap_quality"，第 67 行又说"renderer 只渲染通过 sanity 的字段"

**问题**: 两条路径不矛盾，但设计文档没有明确**实际修改位置**。
- 方案 A：在 `data_fetcher.py` A 股分支写入后 + HK 分支写入后，做一次 `_normalize_market_cap(quote)`，将异常值替换为 `None` 或 `N/A` 标记，renderer 直接读取标记。优点是 renderer 无感知。
- 方案 B：在 `valuation_renderer.py` 读取时做 sanity，若异常则不渲染流通市值行。优点是不改 data_fetcher。

**推荐**: 方案 A（normalization 层），因为 `data_fetcher` 是 quote 数据的唯一生产者，且未来可能被多个 renderer 消费。HK 分支行 291 `float_mcap_yi = mcap_yi` 的赋值也应纳入归一化而非在各分支独立处理。

**设计文档补充**: 需要明确选择方案 A 或 B，并在第 60-67 行注明。

---

### MF3. Industry news relevance class — 需要明确分类方法

**现状**: 设计文档第 126-131 页提出了四个 relevance class（`company_event`、`industry_chain_relevant`、`sector_background`、`noise`），并规定 4.3 只允许前两类。但**没有说明分类由谁做**。

**三种可能**：
1. **确定性规则** — 在 `_adapt_eastmoney_global_news()` 中通过正则/title 关键词区分。风险：泛行业和产业连相关极难用关键词区分（"AI 芯片扩销 -> 存储供不应求 -> 公司处于存储上游"需要推理）。
2. **LLM 分类** — 采集后走一次轻量 LLM 分类。准确但增加延迟和成本，且增加 LLM 调用。
3. **post-hoc 过滤** — 4.3 的 KnowledgeSynthesizer LLM prompt 要求分类并只输出有关联的催化剂。成本为零但不可测试。

**建议**: 采用方案 1 + 3 hybrid。确定性规则在 intake 层打 `relevance_class`（简单关键词划到 `sector_background`/`company_event`），边界情况留给 LLM 在 synthesis 时判断。设计文档需要把这个 hybrid 策略写清楚。

---

### MF4. weak_trend 推荐标签 — 设计正确，实现明确

**确认**: 设计文档第 81 行的诊断完全正确。`recommendation_decision.py:201-215` 的 `_apply_entry_constraint()` 对 `wait_for_entry`、`overheated`、`severe_technical` 都有分支，唯独 `weak_trend` 落到了第 215 行 `return raw_label`。

**现有测试**（`test_recommendation_decision.py:148-178`）覆盖了 `wait_for_entry`、`overheated`、`severe_technical`，但确实没有 `weak_trend` 分支的测例。设计文档第 86-87 行拟新增的测试到位后即可覆盖。

**无需修改设计文档**。这是一个边界清晰、风险可控的改动。

---

## Nice To Have

### N1. 4.4 citation hydration — claim_refs 格式兼容性

**现状**: `build_viewpoint_narrative()` 内部产生的 claim_refs 是 `curated-viewpoint:股票名:hash` 格式（如中际旭创、黑芝麻智能），而复旦微电的 claim_refs 是 `fudan-claim-002` 等短 ID。

**问题**: hydration 逻辑需要兼容两种格式。如果 `citations[].claim_id` 是短 ID 而 `paragraph.claim_refs` 是完整前缀格式，双向映射可能失败。

**建议**: hydration 先用精确匹配，失败后用最后一段（最后 `:` 后的部分）做模糊匹配，与 `_resolve_claim_ref()`（`curated_external_viewpoint_narrative.py:325`）的后备模式一致。

---

### N2. 财务数字来源 — 需要明确 `formal_financial_metrics_pack` 的构建位置

**现状**: `periodic_report_required_financial_metrics.py:23` 的 `build_required_financial_risk_metrics()` 已从年报 evidence pack 中提取 13 类财务指标。但该函数要求 `evidence_pack` 和 `raw_text` 参数，不适用于没有接入年报全文的股票。

**建议扩展优先级**（与设计文档第 101-102 行一致）:
1. 年报/季报结构化事实（已有 `build_required_financial_risk_metrics`）
2. CNINFO 公告摘要中的财务指标
3. 东财/akshare 财务接口（`data_fetcher.py:411` 已有 `fetch_financial_abstract` 返回 6 项核心指标）
4. 其他正式 API

**关键发现**: `data_fetcher.py:411-445` 的 `fetch_financial_abstract()` 已通过 akshare 返回 `revenue`、`gross_margin`、`net_margin`、`roe`、`inventory_days`、`receivable_days` 六项指标。这个函数**不需要年报全文**，可作为 metrics pack 的第二优先级来源。

**建议**: 在 design doc 第 100-107 行中注明 `fetch_financial_abstract()` 作为后备，降低对年报全文的硬依赖。

---

### N3. 同行材料层 — `peer_source_queries` 过早引入

**现状**: 设计文档第 157 行提到可选 `peer_source_queries` 字段，用于后续同行材料层。

**问题**: "本轮"范围声明（第 24 行："本轮只把配置、材料层和质量边界打通；不在本轮做全自动同行深度研究 Agent"）与 `peer_source_queries` 矛盾——引入了未来 Agent 才需要的配置字段，但本轮用不到。

**建议**: 从 Batch 3 范围中移除 `peer_source_queries`，仅在后续真正构建同行研究 Agent 时引入。Batch 3 只做：
1. `config/stocks.json` 增加 `industry` 和 `competitors`（string list）字段
2. `assembly_skills.py` 改为优先读 config、回退到 `constants.py`
3. `data_fetcher.py` 的竞争对手财务抓取改为优先读 config 中的 `competitors`（需同时维护 `COMPETITOR_CODES` 或新增 `peer_codes`）

---

### N4. 4.3 催化剂预过滤不应阻止 LLM 看到全量新闻

**现状**: 设计文档第 131-132 行说只允许 `company_event` 和少量 `industry_chain_relevant` 进入 4.3 时间线。

**微调建议**: LLM 的 `events_catalysts` prompt 输入**应该保留所有新闻条目的完整列表**（包括 `sector_background`），仅在后处理或渲染层过滤出 `company_event` + `industry_chain_relevant`。原因：
- LLM 需要全量上下文来判断哪些新闻是"关键事件与催化剂"；
- `sector_background` 偶尔能提供宏观时间节点（如"半导体板块热"可能关联到板块轮动时机）；
- 在后处理层做过滤比在输入层更灵活，且不会意外丢失可用信息。

---

## 对 Batch 1 是否建议进入实现

**✅ 建议进入实现。**

三个 P0 项目（4.4 citation hydration、market cap sanity、weak_trend 推荐降级）的设计已足够成熟：

| P0 | 风险 | 可测试性 | 回归影响 | 判断 |
|----|------|---------|---------|------|
| 4.4 citation hydration | 低（需处理 MF1 的 normalization 兼容性） | 高（`test_synthesis_skills.py` → 验证 citation_refs 自动填充） | 极小（现有文件已有 citation_refs 的为 no-op） | ✅ 可入 |
| Market cap sanity | 中（需选层方案 A/B） | 高（`test_valuation_renderer.py` → 流通市值 > 总市值时不渲染） | 低（只影响异常情况分支） | ✅ 需先确认 MF2 |
| weak_trend 推荐降级 | 低（4 行代码 + 测试） | 高（`test_recommendation_decision.py` → 看多 + weak_trend → 显示降级标签） | 极小（只影响 weak_trend + 正向标签的 intersection） | ✅ 可入 |

**推动实现的顺序建议**：weak_trend → citation hydration → market cap sanity，由简到繁。

---

## 对 Batch 2/3 的拆分建议

### Batch 2（正式财务事实包 + 行业相关性分类）

**状态**: ⚠️ 需要先解决 MF3（分类方法）和 N2（metrics pack 构建位置）后再进实现。

| 子项目 | 准备度 | 备注 |
|--------|-------|------|
| Formal financial metrics pack | ⚠️ 中等 | `build_required_financial_risk_metrics()` 已存在但需要兜底。需明确 akshare `fetch_financial_abstract` 的使用时间 vs 年报全文的时间 |
| 4.2 数字缺失门禁 | ✅ 高 | 确定性正则检查，设计清晰（`report_quality.py` 加 `"具体数字未列出"` 检测） |
| Industry news relevance class | ⚠️ 低 | 需要先确定分类方法（MF3）。intake 层打标签是最便宜的路径 |
| 4.3 catalyst ownership | ✅ 中 | 后处理思路清晰，与 relevance class 联动 |

**建议**：将 Batch 2 拆为两个子 PR：
- **Batch 2a**（安全、高度可行）: formal financial metrics pack + 4.2 数字缺失门禁。不需要分类方法。
- **Batch 2b**（需设计细化）：industry news relevance class + 4.3 catalyst ownership。等 classification 方案确定后再进。

### Batch 3（config-driven 同行材料层）

**状态**: ⚠️ 方向正确，但需要缩小范围（移除 `peer_source_queries`）。

| 子项目 | 准备度 | 备注 |
|--------|-------|------|
| Config 增加 industry/competitors | ✅ 高 | 纯配置变更 + 读取逻辑 |
| 标题从 config 派生赛道和可比公司 | ✅ 高 | `assembly_skills.py` 改为优先读 config |
| 配置缺失时 quality check 给 warning | ✅ 高 | `check_report_quality.py` 新检查 |
| `peer_source_queries` | ❌ 过早 | 移除，留到后续同行 Agent 设计时引入 |

**建议**：Batch 3 聚焦 config migration + quality gate，不做 `peer_source_queries`。

---

## Git Status

**无变化**。本审查为只读审查，未创建、修改或删除任何文件。

```
$ git status --short
   (clean)
```

---

## 补充发现（设计文档未提及但值得关注的）

### D1. US 股票 `float_mcap_yi` 缺失

`data_fetcher.py:302-317` 的 US 股票分支写入 `mcap_yi` 但不写入 `float_mcap_yi`。渲染时 `quote.get("float_mcap_yi", 0)` 会渲染为 `0.0 亿`。虽然当前 pilot stocks 没有 US 股，但 market cap sanity 项目应一并处理 US 缺失 float_mcap 的渲染边界。

### D2. 复旦微电 4.2 年报全文数据虽已缓存但未被合成引擎利用

正式试跑报告中 W1 提到年报全文数据（197k 字符，credit 75）部分未被合成引擎完全接入。原因确认：`KnowledgeSynthesizer._build_prompt()` 的 `fundamentals` prompt 只接收 `_build_synthesis_items()` 的项目（公告/新闻/研报/雪球），不包含 `required_financial_risk_metrics`。**Batch 2a 直接解决此问题。**

### D3. `check_report_quality.py` 目前不检查 4.4 脚注

`report_quality.py:123-131` 的 `check_report_text()` 调用 `_check_contradictions()` 和 `_check_required_signals()`，但不检查 4.4 段落正文是否有 `[^n]` 标记。设计文档第 42 行规划的新测试和 gate 是必要的补充。

### D4. `test_recommendation_decision.py` 442-453 行有漏洞

第 445 行 `assert decision.entry_constraint.state == "wait_for_entry"` 跑在 `_assembly_ctx_with_curated_paragraph` 的 fixture 上，但这个 fixture 是专为 4.4 narrative 测试设计的（第 553-578 行），与推荐标签无关。这不是 bug，但 fixture 命名混用会让阅读者困惑。

---

## 汇总

| 类别 | 状态 |
|------|------|
| **Verdict** | needs_revision |
| **Blocker** | 0 |
| **Must fix** | 4（MF1~MF4） |
| **Nice to have** | 4（N1~N4） |
| **Batch 1 进入实现** | ✅ 建议进入（MF1 需同步解决） |
| **Batch 2 拆分子 PR** | ✅ 建议拆为 2a（安全）+ 2b（需设计细化） |
| **Batch 3 范围收窄** | ✅ 建议移除 `peer_source_queries` |
| **Git status** | clean（无改动） |
