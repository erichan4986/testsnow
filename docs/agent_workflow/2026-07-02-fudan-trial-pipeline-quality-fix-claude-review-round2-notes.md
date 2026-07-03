# Claude 设计审查 Round 2：Fudan Trial Pipeline Quality Fix

**审查者**: Claude Code（只读分析）
**审查日期**: 2026-07-02
**基准设计**: `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design.md`
**Delta 文档**: `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design-delta.md`
**Round 1 审查**: `docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-claude-review-notes.md`

---

## Round 1 Closure 逐项评估

### B1 — stock_config 可用性假设

**Verdict: closed**

Revised design 新增：
- **Batch 1.5** 显式要求补齐三只试点股票的 `industry/competitors/product_exposure_terms`
- batch order 从 `A→B→C→D→E` 改为 `1.5→D→A→B→C→E`
- config loading 兼容未知股票（不能强制全量补齐）
- header Gata E 仅为 warning，允许缺失时显示 `—`

明确 closure 的证据：
- 设计段 `Batch 1.5 配置完备度前置` (line 159-177) 完整覆盖了三只股票的具体配置要求和缺配置 fallback
- Direct-Only Canonical 第 2 条 (line 197) 写明 `product_exposure_terms` 缺失时可用去泛化后的 `keywords` 临时补位
- Stop Condition 第 5 条 (line 539) 保留了回归退化的保护

### B2 — 4.3 缺失根因归属

**Verdict: closed**

Revised design 新增强调：
- "第一根因在 `DeepAnalysisRenderer._deep_analysis()`：当 `funding_sentiment` 和 `events_catalysts` 都为空时，renderer 静默省略 4.3"(line 99)
- Renderer fallback 是主修复，quality gate 只做第二道防线
- 新增 4.3 fallback **四档**（line 343-347）：both、funding-only、events-only、neither — 覆盖 Round 1 N3 建议
- 测试 `test_deep_analysis_renderer.py` 覆盖全部四档

Batch D 的实施顺序走在 Batch A 之前，保证 renderer fallback 先就绪。

### B3 — product_exposure_terms 范围与回归安全

**Verdict: closed**

Revised design 新增：
- Missing `product_exposure_terms` fallback：使用 `keywords` 剔除泛词后临时补位（line 175）
- 明确要剔除的泛词列表：半导体、芯片、国产替代、AI、汽车电子、集成电路、行业、产业链（line 176）
- 对缺配置股票，过滤后某 theme items 少于 3 时产生 `direct_relevance_underfilled` warning，renderer 输出受控降级（line 177）
- 行业材料层级 L1-L4 显式定义（line 223-230），Round 1 的 N2 被采纳

**注意实现细节**：圣邦股份 `keywords` 中的 `"模拟芯片"` 包含泛词子串 `"芯片"` 。设计仅说"剔除泛词"未定义 exact match vs substring match，需要在 Batch B 实现时选择：
- 若 substring strip：`"模拟芯片"` → `"模拟"`（意义不足）
- 若 exact word match：`"模拟芯片"` 保留（因为不完全是泛词 `"芯片"` 本身）
- 建议 exact word match，仅当 keyword 本身就是 `"芯片"` 时才剔除

但这属于实现细节，不阻塞设计审核。

### MF1 — Header 源描述

**Verdict: closed**

Revised design 明确（line 150-155）：
- "头部渲染位于 `assembly_skills.py`，当前直接读取 `INDUSTRY_MAP/COMPETITOR_MAP` 常量"
- 修复策略：`stock_config.industry/competitors` 优先 → `INDUSTRY_MAP/COMPETITOR_MAP` fallback → 两层都缺失时 `—` + quality warning
- 测试 `test_assembly_skills.py` 覆盖 config 优先、constant fallback、都缺失三种场景

### MF2 — 财务单位根因

**Verdict: closed**

Revised design 新增（line 313-318）：
- "Batch C 不能只修 `_filing_fact()` 的字符串拼接"
- "必须检查 upstream table/cell parser 如何从年报表格标题、列名或 cell metadata 提取单位"
- 金额类指标统一输出 `normalized_amount`、`normalized_unit`、`raw_text`、`source_unit_hint`
- 与同报告财务快照量级冲突时，fact pack 降级该事实并在 quality gate 报 `financial_unit_conflict`，禁止核心事实展示错误单位

### MF3 — 财务缺失 gate 粒度

**Verdict: closed**

Revised design 新增（line 321-324）：
- 只对 fact pack **已有的指标**触发矛盾检查
- 例如已有 `revenue/net_profit` 时禁止写"未提供最新营收/利润数据"
- 没有 `orders/customer_structure/expense_ratio/guidance` 时允许保留受控缺失表达
- Gate D (line 406-409) 显式写明"不 fail 的情况"

### MF4 — Renderer 层测试

**Verdict: closed**

测试计划新增：
- `tests/reporter/test_deep_analysis_renderer.py`（4 个测试）：funding/events 都空、只有 funding、只有 events、4.1/4.2 不静默缺失
- `tests/reporter/test_assembly_skills.py`（3 个测试）：stock_config 优先、常量 fallback、两层缺失 + warning

### MF5 — Direct-Only 退化检测

**Verdict: closed**

Revised design 新增：
- Stop condition 第 6 条（line 540）："Direct-Only 过滤后 4.1/4.2 items 少于 `KnowledgeSynthesizer.min_items` 且 renderer 无法受控降级：停止"
- 过滤前有材料、过滤后 items 不足时记录 `direct_relevance_underfilled` warning（line 271-274）
- 不允许 LLM 因 items 不足自行借用 `sector_background`
- Quality Gate B (line 382) 增加了 underfill warning 条件

---

## 整体评估

```yaml
verdict: ok
summary: >
  Revised design 已完整回应 Round 1 全部 8 项 findings。B1-B3 和 MF1-MF5 均 closed。
  最大的结构变化是新增 Batch 1.5（配置补齐前置）和将 Batch D（header + renderer）前移到 Batch A/B 之前，
  消除原设计的依赖死锁。Direct-Only Canonical 补充了缺配置 fallback 和 underfill 保护，
  回归样本的防护机制到位。没有任何未关闭的 blocker。
round1_closure:
  B1: closed
  B2: closed
  B3: closed
  MF1: closed
  MF2: closed
  MF3: closed
  MF4: closed
  MF5: closed
blockers: []
must_fix: []
nice_to_have:
  - id: N1
    title: 圣邦股份"模拟芯片"关键词 substring stripping 风险
    evidence: >
      设计要求剔除泛词"芯片"，但圣邦 keywords 中包含"模拟芯片"。
      若实现时用 substring match 会 strip 成"模拟"，
      导致这个 keywords 失去匹配价值。
    suggestion: >
      Batch B 实现时使用 exact word match（或 list membership check），
      仅当 keyword 本身就是泛词时才剔除，不是包含泛词子串就剔除。
      如果使用 tokenize + exact match，"模拟芯片"整个保留。
  - id: N2
    title: "keywords 不足"的定义待 Batch B 定
    evidence: >
      设计说"若 keywords 也不足，行业资讯默认不可进 canonical synthesis"，
      但未定义"不足"的量化标准。可能指 keywords 列表为空，
      也可能指所有 keywords 被泛词剔除后为空。
    suggestion: >
      实现时定义"不足"为：去泛化后的 keywords 长度 < 1 且没有 product_exposure_terms。
      若去泛化后还有 1+ 个 keyword，视为"可用的 fallback exposure terms"。
implementation_readiness:
  recommended_next_step: "proceed_to_task"
  batch_order_ok: true
  notes: >
    Batch 顺序 1.5 → D → A → B → C → E 合理，消除了原设计的依赖链问题：
    - Batch 1.5 无外部依赖，可以先行（纯配置修改）
    - Batch D 只改 renderer 和 assembly，与 synthesis 路径不冲突
    - Batch A (quality gates) 在 renderer fallback 就绪后编写，
      可以同时覆盖 renderer"不该缺"和 gate"检测缺"的双重保护
    - Batch B (Direct-Only) 依赖 Batch 1.5 的 product_exposure_terms
    - Batch C 依赖 Batch B 的 synthesis 路径修改
    - Batch E 需所有前置 batch 完成
    
    唯一留意的是：财务单位修复（Batch C 的一部分）在 periodic_report_structured_facts.py 的
    upstream parser 层，这一部分与 Direct-Only 无关，理论上可以在 B 之前独立调研和实施。
    但如果发现根因在 cell parser 需要较大重构，可能影响 Batch 规划。
    建议在 Batch 1.5 完成后安排一次短期 data flow 分析（专门 trace 复旦微电
    39.82 万元的数据路径），明确修单位的 scope 后再正式进入 Batch C。
git_status:
  changed_files_observed:
    - docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design.md (已修改)
    - docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-design-delta.md (已存在)
    - docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-claude-review-notes.md (Round 1 审查)
    - docs/agent_workflow/2026-07-02-fudan-trial-pipeline-quality-fix-claude-review-round2-notes.md (本报告)
  unexpected_changes: []
```

---

## 结论

**Verdict: ok** — 8/8 Round 1 findings closed。设计已消除原方案的主要间隙，建议进入 implementation task。

**推荐的 Task 切分**：

| Task | 内容 | 预估范围 |
|------|------|----------|
| Task 1 | Batch 1.5 config：补齐三只股票的 industry/competitors/product_exposure_terms | config/stocks.json |
| Task 1b | （可选）39.82 万元 data flow trace：确定单位归一化修正在哪个层 | 只读分析 |
| Task 2 | Batch D：header config-first + 4.3 四档 renderer fallback + 测试 | synthesis_skills.py, deep_analysis_renderer.py, assembly_skills.py, test |
| Task 3 | Batch A：5 个 quality gate + 测试（Gate A-E） | report_quality.py, test |
| Task 4 | Batch B：source_direct_relevance.py + filter 扩展 + 测试 | 新文件 + knowledge_synthesizer.py, test |
| Task 5 | Batch C：formal_financial_fact_pack + 财务单位修复 + 测试 | periodic_report_structured_facts.py + synthesis 路径, test |
| Task 6 | Batch E：复旦回归 + 中际旭创 or 圣邦回归 | scripts/ 运行 + quality 验证 |

其中 Task 1 和 Task 2 无代码冲突，可以并行实施。
