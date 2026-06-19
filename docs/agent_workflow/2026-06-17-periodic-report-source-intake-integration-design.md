# 年报/半年报全文实验路径接入 Source Intake 设计

**Date:** 2026-06-17  
**Scope:** 将 `periodic_report_fulltext_llm_analysis.py` 相关的 deterministic preview（required business metrics + required financial risk metrics + product/project/customer backfill）作为 Source Intake 的**材料层（material layer）**接入，仅用于展示和最终报告 LLM 参考，**不进入核心事实、评分、风险评分或最终建议**。

**前置阅读：**
- `scripts/utils/periodic_report_fulltext_llm_analysis.py`
- `scripts/utils/periodic_report_required_metrics.py`
- `scripts/utils/periodic_report_required_financial_metrics.py`
- `scripts/utils/periodic_report_product_project_evidence.py`
- `scripts/utils/a_stock_source_intake.py`
- `scripts/utils/report_skills/source_intake_merge_skill.py`
- `scripts/utils/evidence_note_writer.py`
- `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`
- `docs/agent_workflow/2026-06-16-periodic-report-source-intake-design.md`（periodic_report_extractor 摘录路径）

---

## 1. 目标与边界

### 1.1 目标

当前年报全文实验路径已经能产出：

1. `build_required_business_metrics`：分产品/地区/销售模式、产销库存、客户/供应商集中度等确定性经营指标。
2. `build_required_financial_risk_metrics`：盈利质量、现金流、存货/减值、应收、capex、金融资产、杠杆、商誉、审计治理等确定性财务风险指标。
3. `extract_product_project_evidence` + `build_company_profile_backfill` / `build_rd_progress_backfill`：产品/项目/客户/渠道的通用证据回填。
4. `build_periodic_report_fulltext_pack` + LLM prompt：若调用真实 LLM，可产出六段判断摘要和 `financial_risks`。

本设计要把 1-3（以及可选的 4 中已验证的 LLM 输出）封装成 Source Intake item，让其在最终报告里可见、可审计，但**信用等级固定为 75、核验状态固定为 professional_analysis、不允许进入知识库或评分系统**。

### 1.2 硬边界

| 维度 | 允许 | 禁止 |
|---|---|---|
| 信用等级 | 固定 75 | 不可上调到 95 或动态计算 |
| 核验状态 | 固定 `professional_analysis` | 不可为 `confirmed_fact` / `fact_candidate` |
| 知识库 | 不写入（`knowledge_eligible=False`） | 不可变为 `fact_candidate` |
| 报告评分 | 仅展示，不参与计算 | 不可进入 `scoring_engine`、风险评分、技术面、估值、最终建议 |
| 核心事实 | 不作为 `core_fact` | 不可被 `KnowledgeSynthesizer` 默认消费 |
| 来源类型 | 新增 `periodic_report_fulltext_analysis` | 不可与 `periodic_report_excerpt` 合并或折叠 |
| 网络/CDP/LLM | 只读取本地缓存或已有 helper | 不可调用真实 LLM、不可启动 Chrome/CDP、不可抓雪球详情页 |

---

## 2. 数据结构：periodic_report_fulltext_analysis 如何成为 Source Intake item

### 2.1 封装对象

每个年报/半年报全文 preview 生成**一个** `SynthesisItem`：

```python
SynthesisItem(
    title="2025年年度报告 | 定期报告全文摘要（实验路径）",
    content=preview_markdown,          # 见 2.2
    author="",
    source_platform="定期报告全文",
    url=original_cninfo_url,
    publish_time="2026-04-15",         # 来自原公告
    interaction_score=0,
    extra={
        # 信用与类型硬约束
        "source_type": "periodic_report_fulltext_analysis",
        "source_credit": 75,
        "verification_status": "professional_analysis",
        "claim_status": "professional_analysis",
        "knowledge_eligible": False,
        "report_eligible": False,

        # 展示保护开关
        "source_intake_display_eligible": True,

        # 审计与报告元信息
        "source_domain": "cninfo.com.cn",
        "periodic_report_type": "annual_report",      # annual_report / semiannual_report
        "periodic_report_audit_status": "audited",    # audited / interim_unaudited / ...
        "periodic_report_fulltext_id": "<stable-id>", # 见 3.1
        "experimental": True,

        # 材料层可选：若后续 LLM 需要结构化消费，可把整个 analysis dict 放这里
        # "periodic_report_fulltext_analysis_json": {...},
    },
)
```

### 2.2 content 内容

`content` 使用现有 `render_periodic_report_fulltext_markdown` 的 deterministic 版本（无 LLM 时只填两段 backfill）：

```markdown
# 定期报告全文判断摘要

- 报告类型：annual_report
- 审计状态：audited
- 来源类型：periodic_report_fulltext_analysis
- 信用等级：75
- 核验状态：professional_analysis

> 本摘要是全文/大块年报实验路径产物：允许基于证据做分析判断，但每条判断必须绑定 evidence_refs；
> 不直接进入核心事实、评分、风险评分或最终建议。

## 必备经营指标摘录
...（required business metrics 渲染）

## 必备财务风险指标摘录
...（required financial risk metrics 渲染）

## 公司画像（Product/Project/Customer Backfill 预览）
- ...（置信度 72；依据：fulltext-2-0, ...）

## 研发与技术进展（Product/Project/Customer Backfill 预览）
- ...（置信度 72；依据：fulltext-2-0, ...）
```

当且仅当存在可复用的 LLM JSON 时，才追加 `主营业务表现`、`客户与订单结构`、`管理层市场判断`、`财务风险与跟踪指标`、`重点财务风险清单`。本设计**默认不调用 LLM**，因此 LLM 部分由可选配置控制。

### 2.3 与现有 `periodic_report_excerpt` 的关系

| 属性 | `periodic_report_excerpt` | `periodic_report_fulltext_analysis` |
|---|---|---|
| 来源类型 | `periodic_report_excerpt` | `periodic_report_fulltext_analysis` |
| 内容粒度 | 单条规则摘录（风险/管理层/资本/排雷） | 整份年报/半年报的 deterministic summary |
| credit | 75 | 75 |
| verification_status | `risk_disclosure` / `management_view` / `capital_action` / `financial_forensics` | 固定 `professional_analysis` |
| knowledge_eligible | True | **False** |
| report_eligible | True | **False** |
| 用途 | 可作为 evidence note / 报告展示 | 仅材料层展示 + 可选 LLM 上下文 |

两者**不合并、不折叠**，在 Source Intake 中分别展示。

---

## 3. 去重策略

### 3.1 与原始公告 / PDF / 摘录的隔离

`periodic_report_fulltext_analysis` item 使用独立的来源类型和独立的稳定 ID：

```
periodic_report_fulltext_id = sha256(stock_code + announcement_id + report_type).hexdigest()[:12]
```

该 ID 写入 `extra["periodic_report_fulltext_id"]`，并用于：

1. 在 Source Intake renderer 中作为去重 key。
2. 与 `periodic_report_excerpt` 的 `periodic_report_excerpt_id` 区分开。
3. 防止和原始 `exchange_announcement`（credit 95）因同 URL 而被折叠。

### 3.2 不进入 `source_intake_merge_skill` 的 URL 去重

`source_intake_merge_skill` 使用 `_canonical_url` + `_pick_preferred` 合并同 URL 条目，credit 95 的原始公告会吃掉 credit 75 的摘录。为避免 `periodic_report_fulltext_analysis` 被误折叠：

**方案（推荐）：走独立 ctx key，不经过 merge。**

- 新 skill 将 item 写入 `ctx["periodic_report_fulltext_items"]`。
- `source_intake_merge_skill` 不读取该 key，因此不会影响 `external_evidence_keep_items`。
- `SourceIntakeEvidenceRenderer` 直接读取 `periodic_report_fulltext_items` 并渲染独立子节。

这样 `report_eligible=False` / `knowledge_eligible=False` 仍然成立，且 merge 逻辑无需为新材料类型打补丁。

### 3.3 同一份年报多版本缓存

若同一年报存在多个缓存文件（如 `*_2025_annual_jina.txt` 与 `*_2025_annual_jina-1.txt`），按文件修改时间取最新；渲染时仅展示一条。

---

## 4. 展示策略

### 4.1 新增子节位置

在 `SourceIntakeEvidenceRenderer` 的现有结构：

```markdown
## Source Intake 分层证据观察
### 来源分层概览
### 定期报告关键摘录          <-- 现有：periodic_report_excerpt
### 代表性证据摘录
```

之后插入：

```markdown
### 定期报告全文摘要（实验路径）

> 本小节为年报/半年报全文实验路径的 deterministic preview，仅供材料层参考；
> 不进入核心事实、评分、风险评分或最终建议。
```

### 4.2 渲染方式

由于 `content` 是完整 Markdown（含 `#` / `##` 标题），直接插入会破坏报告层级。建议两种方案：

**方案 A：折叠详情（推荐）**

```markdown
<details>
<summary>2025年年度报告 | 定期报告全文摘要（实验路径） — 信用 75</summary>

<!-- 把 preview_markdown 的标题层级整体降一级：# -> ###, ## -> #### -->
...
</details>
```

优点：不挤占代表性证据摘录；用户/LLM 可展开查看。缺点：依赖 HTML details，部分 Markdown 阅读器支持不一。

**方案 B：标题层级降级后内联**

渲染前对 `content` 做 display-only 转换：
- `# ` -> `### `
- `## ` -> `#### `
- 删除最外层 `# 定期报告全文判断摘要` 的重复标题

然后直接拼入 Source Intake section。优点：纯 Markdown，兼容性好。缺点：内容较长。

**设计建议：先实现方案 B（纯 Markdown、降级标题），并默认只渲染最多 1 份全文摘要；若报告过长，在子节底部加截断提示。**

### 4.3 避免挤占代表性证据摘录

- 全文摘要子节**不计入** `_MAX_REPRESENTATIVE_ROWS`。
- 全文摘要 item **不参与** `_build_representative_rows`。
- 全文摘要子节默认最多展示 **1 条**（最新年报或半年报），可通过配置放宽到 2。

---

## 5. Guardrails

### 5.1 Renderer 不得显示 confirmed_fact

`SourceIntakeEvidenceRenderer._item_verification_status()` 新增硬分支：

```python
if source_type == "periodic_report_fulltext_analysis":
    return "professional_analysis"
```

无论 `extra["verification_status"]` 被污染成什么，都强制降级为 `professional_analysis`。

### 5.2 evidence_note_writer 不得提升为 fact_candidate

由于 `knowledge_eligible=False`，`write_evidence_notes` 会在 `plan.filtered` 中记录 `knowledge_eligible=False`，不会写入 knowledge 目录。为进一步防止未来阈值调整导致意外提升：

- 在 `_claim_status_for_item()` 中保留现有 `periodic_report_excerpt` guard 的同时，新增：

```python
if source_type == "periodic_report_fulltext_analysis" and status == "fact_candidate":
    return "professional_analysis"
```

### 5.3 merge 不得丢弃摘录/分析

通过**独立 ctx key** 实现：

- `periodic_report_fulltext_items` 不经过 `source_intake_merge_skill`。
- 即使 `source_intake_merge_skill` 把同 URL 的 `periodic_report_excerpt` 折叠了，全文摘要子节仍然保留。

### 5.4 KnowledgeSynthesizer context 默认不吃

- `SynthesisSkill._build_synthesis_items()` 只消费 `stock_raw` + `keep_posts`，不读取 `periodic_report_fulltext_items`。
- 默认 `include_periodic_report_fulltext_in_synthesis=False`。
- 未来若需开放材料层，必须显式设置 `include_periodic_report_fulltext_in_synthesis=True`，并在 `SynthesisSkill` 中通过压缩后的文本（仅保留关键指标和 backfill，不传入完整 Markdown）注入，且不得让 fulltext 证据参与 `core_facts` 提取。

### 5.5 风险不被误当评分因子

- `claim_risk_signal_skill` 从 knowledge base 读取，不消费 `periodic_report_fulltext_items`。
- `scoring_skill` 只使用 `stock_raw` / `keep_posts` / `quote` / `consensus`，不消费全文摘要。
- `RiskRenderer` 不读取 `periodic_report_fulltext_items`。
- 若后续希望把 fulltext 中的 `financial_risks` 引入风险评分，必须走独立设计和结构化风险信号 contract，不在本阶段实现。

---

## 6. Failure Modes

### 6.1 LLM 编造数字

- **缓解：** 默认只生成 deterministic preview（required metrics + backfill），不调用 LLM。
- **若启用 LLM：** 复用 `validate_periodic_report_fulltext_output` 的 `check_fidelity` / `_reject_invalid_evidence_refs` / `_reject_illegal_content`，确保每个判断和数字都能回溯到 `fulltext-*` block。

### 6.2 evidence refs 失效

- `build_company_profile_backfill` / `build_rd_progress_backfill` 返回的 `refs` 必须来自 `fulltext_pack.blocks` 的 `id`。
- 渲染前做防御性检查：若 ref 不在 `item_map` 中，用 `fulltext-0-0` 或空列表兜底，并在 `periodic_report_fulltext_status` 中记录 warning。

### 6.3 required metrics 缺失

- preview 中缺失的表格显示 "未提取到..."，不会隐藏。
- Source Intake 子节中保留该提示，避免用户误以为年报无数据。

### 6.4 行业词库错配

- `periodic_report_product_project_evidence.py` 已通过通用 marker + org suffix 机制支持航空航天/新材料/碳纤维等场景。
- 接入后需回归验证：中简科技 preview 不出现芯片/频段/模组错配，英集芯 preview 不出现 "百分点" 噪声。

### 6.5 风险被误当评分因子

- 通过独立 ctx key + `report_eligible=False` + `knowledge_eligible=False` 三道防线隔离。
- 增加 no-leak 测试：确认 `scoring_skill`、`SynthesisSkill`、`claim_risk_signal_skill`、`evidence_note_writer` 的输入中均不包含 `periodic_report_fulltext_analysis` item。

---

## 7. 测试计划

### 7.1 Focused unit tests（新增 / 扩展）

建议新增 `tests/utils/test_periodic_report_fulltext_intake.py`：

1. `test_builds_preview_without_llm`：输入本地缓存 Jina 文本，确认输出包含 required business / financial / profile / RD 四部分，无 LLM 调用。
2. `test_item_has_fixed_credit_and_status`：source_credit=75，verification_status=`professional_analysis`，knowledge_eligible=False，report_eligible=False。
3. `test_item_id_stable_for_same_announcement`：相同 stock_code + announcementId 生成相同 `periodic_report_fulltext_id`。
4. `test_skips_when_cache_missing_and_fetch_disabled`：本地无缓存且配置不允许 fetch 时，不抛异常，status 为 `skipped`。
5. `test_no_llm_call_by_default`：mock LLM client 不被调用。

### 7.2 Renderer tests（扩展 `tests/reporter/test_source_intake_evidence_renderer.py`）

1. `test_fulltext_analysis_renders_dedicated_subsection`：存在 `periodic_report_fulltext_items` 时渲染 `### 定期报告全文摘要（实验路径）`。
2. `test_fulltext_analysis_forces_professional_analysis`：即使 item.extra["verification_status"]="confirmed_fact"，渲染结果中仍为 `professional_analysis`。
3. `test_fulltext_analysis_excluded_from_representative_rows`：不进入 `### 代表性证据摘录`。
4. `test_fulltext_analysis_heading_levels_downgraded`：渲染结果中不破坏外层 `#` / `##` 层级。
5. `test_fulltext_analysis_long_content_truncated_or_folded`：超长内容做截断或折叠处理。
6. `test_renderer_does_not_mutate_fulltext_items`。

### 7.3 Merge tests（扩展 `tests/reporter/test_source_intake_merge_skill.py`）

1. `test_fulltext_analysis_not_consumed_by_merge`：`periodic_report_fulltext_items` 不参与 merge，不影响 `external_evidence_keep_items` 计数。
2. `test_original_announcement_and_fulltext_analysis_coexist`：同 URL 的原始公告和全文摘要都保留在各自 bucket 中。

### 7.4 no-leak tests（新增或扩展）

1. `test_fulltext_analysis_not_in_synthesis_items`：运行 `SynthesisSkill._build_synthesis_items()` 后结果中无 `periodic_report_fulltext_analysis`。
2. `test_fulltext_analysis_not_in_scoring_context`：`scoring_skill` 不读取 `periodic_report_fulltext_items`。
3. `test_fulltext_analysis_filtered_by_evidence_note_writer`：`write_evidence_notes` 返回的 `plan.filtered` 包含该 item，且 `plan.written` 不包含。
4. `test_fulltext_analysis_not_in_claim_risk_signals`：`claim_risk_signal_skill` 不使用该 item。

### 7.5 回归测试

1. 现有 `tests/utils/test_periodic_report_*.py` 全部通过。
2. 现有 `tests/reporter/test_source_intake_evidence_renderer.py` 全部通过。
3. 现有 `tests/reporter/test_source_intake_merge_skill.py` 全部通过。
4. 现有 `tests/utils/test_evidence_note_writer.py` 全部通过。
5. `git diff --check` 无空白错误。

---

## 8. 实现阶段建议

### 8.1 是否先 helper-only 集成？

**建议：先 helper-only，再决定是否接报告展示。**

理由：

1. 全文 preview 是实验路径，内容长、格式重，直接渲染可能冲击现有 Source Intake 排版。
2. helper-only 阶段可以快速验证：item 结构正确、guardrails 生效、no-leak 测试通过，而不影响最终报告渲染。
3. 展示阶段只需扩展 `SourceIntakeEvidenceRenderer`，风险最小。

### 8.2 建议实现顺序

1. **Phase 0：只读设计定稿**（本文档）。
2. **Phase 1：helper-only**
   - 新增 `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`。
   - 在 `build_stock_report_pipeline` 中，当 `enable_source_intake=True` 且配置开启 `periodic_report_fulltext.enabled` 时注册该 skill（位于 `source_intake_merge_skill` 之后、`evidence_note_writer_skill` 之前）。
   - 该 skill 读取 `data/raw/periodic_reports/*_2025_annual_jina.txt`（及未来半年报缓存），生成 `periodic_report_fulltext_items` 写入 ctx。
   - 不修改 renderer；只通过单元测试验证 item 结构和 no-leak。
3. **Phase 2：Source Intake 展示**
   - 扩展 `SourceIntakeEvidenceRenderer` 渲染 `### 定期报告全文摘要（实验路径）`。
   - 增加 renderer 回归测试。
4. **Phase 3：可选 LLM 材料层开放**
   - 在 `SynthesisSkill` 中增加 `include_periodic_report_fulltext_in_synthesis` 开关（默认关闭）。
   - 通过压缩摘要（非完整 Markdown）注入 LLM context，并继续禁止参与 core_facts。

### 8.3 建议实现阶段允许修改的文件

- **新增：**
  - `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
  - `tests/utils/test_periodic_report_fulltext_intake.py`
- **最小修改：**
  - `scripts/utils/report_skills/__init__.py`：在 pipeline 中注册新 skill（仅当配置开启）。
  - `scripts/utils/reporter/sections/source_intake_evidence_renderer.py`：Phase 2 渲染新子节。
  - `scripts/utils/evidence_note_writer.py`：可选新增 source-type guard（若当前 `periodic_report_excerpt` guard 不够通用）。
- **不修改：**
  - `KnowledgeSynthesizer` 核心逻辑
  - `scoring_engine.py`、technical analyzers、risk renderer/scoring
  - 主报告 pipeline 的 scoring/synthesis/technical 顺序
  - `config/stocks.json`
  - `knowledge/`、`reports/`、`data/raw/`（除自然读取外）

---

## 9. 决策点 / 待确认

| # | 问题 | 建议 | 是否阻塞实现 |
|---|---|---|---|
| 1 | 是否允许新 skill 读取 `data/raw/periodic_reports/` 缓存？ | 是；不访问外部网络，复用现有缓存 | 否 |
| 2 | 是否默认启用 LLM 生成六段摘要？ | 否；默认 deterministic preview，LLM 通过配置显式开启 | 否 |
| 3 | 展示时标题层级降级还是折叠？ | 先降级（方案 B），后续根据排版反馈评估折叠 | 否 |
| 4 | 是否允许未来把 fulltext 注入 `SynthesisSkill`？ | 仅通过显式开关，且压缩后注入；默认关闭 | 否 |
| 5 | 是否需要把预览内容也写入 knowledge 目录作为只读材料？ | 否；`knowledge_eligible=False` | 否 |

---

## Narrow R2 Guardrail Review

**Date:** 2026-06-18
**Reviewer:** Claude Code
**Scope:** Read-only review of helper-only Source Intake integration for `periodic_report_fulltext_analysis`.

- **Status:** Needs fixes
- **Blocker:** 有
- **Must-fix before Phase 2:**
  1. `SourceIntakeEvidenceRenderer` must implement and test the hard branch that forces `professional_analysis` for `source_type == "periodic_report_fulltext_analysis"` (design §5.1).
  2. `periodic_report_fulltext_intake_skill` must be registered in pipeline with an **independent ctx key** (`ctx["periodic_report_fulltext_items"]`) and must not write items into `external_evidence_keep_items` consumed by `source_intake_merge_skill`.
  3. Add no-leak integration tests confirming `SynthesisSkill._build_synthesis_items`, `scoring_skill`, and `claim_risk_signal_skill` never consume `periodic_report_fulltext_items` (design §7.4).
  4. Add merge isolation test confirming `source_intake_merge_skill` does not fold `periodic_report_fulltext_items` by URL (design §7.3).
- **Nice-to-have:**
  1. Markdown heading-level downgrade before rendering (design §4.2 方案 B).
  2. Length truncation or `<details>` folding for long previews.
  3. Optional compressed context injector for `SynthesisSkill` with `include_periodic_report_fulltext_in_synthesis=False` default.

### Guardrail checklist

- **professional_analysis only:** 是
  - `periodic_report_fulltext_intake_skill.build_periodic_report_fulltext_intake_item` hard-codes `source_credit=75`, `verification_status="professional_analysis"`, `claim_status="professional_analysis"`, `knowledge_eligible=False`, `report_eligible=False`, `experimental=True`.
  - `periodic_report_fulltext_llm_analysis.summarize_periodic_report_fulltext_with_llm` also emits the same fixed metadata.
- **no fact_candidate / confirmed_fact:** 是
  - `evidence_note_writer._claim_status_for_item` explicitly downgrades `periodic_report_fulltext_analysis` from `fact_candidate` back to `professional_analysis`.
  - `tests/utils/test_evidence_note_writer.py::test_periodic_report_fulltext_analysis_never_becomes_fact_candidate_even_if_credit_rises` verifies this even when `source_credit=85` and `knowledge_eligible=True`.
- **no core facts / scoring / risk scoring:** 当前 helper-only 无路径；Phase 1/2 需补 no-leak 测试
  - Current code: `periodic_report_fulltext_intake_skill.py` is a pure helper, not registered as a pipeline skill, does not write to `knowledge/`, `reports/`, or scoring context.
  - `source_intake_evidence_renderer.py` and `source_intake_merge_skill.py` currently contain no references to `periodic_report_fulltext` at all, so no accidental consumption path exists today.
  - Design §5.4/§5.5 clearly forbids `KnowledgeSynthesizer`, `scoring_skill`, `claim_risk_signal_skill`, and `RiskRenderer` from consuming `periodic_report_fulltext_items` by default.
- **no merge dedup collision:** 设计通过独立 ctx key 实现；Phase 2 renderer 已隔离
  - Design §3.2 recommends `periodic_report_fulltext_items` bypass `source_intake_merge_skill` entirely.
  - `SourceIntakeEvidenceRenderer._collect_fulltext_items` reads only `ctx["periodic_report_fulltext_items"]`, so merge-skill isolation is enforced at the display layer.
  - Pipeline registration (`report_skills/__init__.py`) still needed to wire the independent ctx key end-to-end.
- **tests sufficient:** helper + renderer guardrails 已覆盖
  - Covered: fixed metadata (`test_item_has_fixed_credit_and_status`), non-fact status (`test_item_is_not_confirmed_fact_or_fact_candidate`), evidence-note filtering and downgrade (`test_periodic_report_fulltext_analysis_is_filtered_from_knowledge`, `test_periodic_report_fulltext_analysis_never_becomes_fact_candidate_even_if_credit_rises`), LLM validator metadata (`test_fulltext_validator_backfills_keep_professional_analysis_metadata`), renderer guard (`test_malformed_fulltext_item_confirmed_fact_still_renders_professional_analysis`, `test_periodic_report_fulltext_items_renders_dedicated_experimental_section`), exclusion from representative/periodic tables, heading downgrade and truncation, no mutation.
  - Missing: end-to-end pipeline registration test, merge-skill explicit no-fold test, synthesis/scoring/risk no-leak tests.

### 测试结果

```text
python3 -m pytest tests/utils/test_periodic_report_fulltext_intake.py tests/utils/test_evidence_note_writer.py tests/utils/test_periodic_report_fulltext_llm_analysis.py tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_required_financial_metrics.py tests/utils/test_periodic_report_product_project_evidence.py tests/utils/test_hk_periodic_report_fetcher.py -q
205 passed in 2.76s
```

`git diff --check` 无空白错误。

### git status 是否有变化

本次审查为只读，未新增或修改任何源码、测试、配置、数据或报告文件；`git status` 与审查前一致，无额外变化。

### 结论

`periodic_report_fulltext_analysis` 在 helper 层的 guardrails 已经到位：固定 `professional_analysis`、不可升格 `fact_candidate`、默认不调用 LLM、不写入 knowledge/reports。但 Source Intake 集成（Phase 1 skill 注册 + Phase 2 renderer 展示）尚未落地，导致设计上承诺的 renderer 强制降级、merge 隔离、no-leak 测试仍未被代码强制执行。建议在完成 Phase 1/2 前补齐上述 Must-fix 项，否则存在未来被主流程误消费的潜在风险。

## Phase 1B Guardrail Implementation

**Date:** 2026-06-18

Implemented the narrow guardrail layer before display integration:

- `SourceIntakeEvidenceRenderer` now hard-normalizes `source_type == "periodic_report_fulltext_analysis"` to `professional_analysis`, even if malformed metadata claims `confirmed_fact`.
- Added merge isolation coverage: `periodic_report_fulltext_items` remains an independent ctx key and is not folded by `source_intake_merge_skill`.
- Added no-leak coverage for default `SynthesisSkill`, `scoring_skill`, and `claim_risk_signal_skill`: none of them consumes `periodic_report_fulltext_items`.
- No Source Intake display section was added yet, and the path still does not enter core facts, scoring, risk scoring, `knowledge/`, or `reports/`.

Focused verification:

```text
python3 -m pytest tests/reporter/test_source_intake_evidence_renderer.py tests/reporter/test_source_intake_merge_skill.py tests/reporter/test_synthesis_skills.py tests/reporter/test_analysis_skills.py tests/reporter/test_claim_risk_signal_skill.py -q
92 passed in 2.03s
```

## Phase 2 Renderer Display

**Date:** 2026-06-18

Implemented Source Intake display for `ctx["periodic_report_fulltext_items"]`:

- Adds dedicated `### 定期报告全文摘要（实验路径）` subsection.
- Renders fulltext items only from the independent ctx key.
- Keeps status fixed as `professional_analysis`; malformed `confirmed_fact`/`fact_candidate` metadata is not displayed.
- Excludes fulltext items from representative rows and periodic excerpt rows.
- Downgrades embedded Markdown headings and truncates each preview.
- Does not mutate ctx or item metadata.
- Does not register the skill into the pipeline and does not affect synthesis, scoring, risk scoring, `knowledge/`, or `reports/`.

Codex follow-up added two missing edge tests after review:

- fulltext-only ctx renders without `source_intake_items`.
- multiple fulltext items render individually rather than only showing the most recent item.

Focused verification:

```text
python3 -m pytest tests/reporter/test_source_intake_evidence_renderer.py tests/reporter/test_source_intake_merge_skill.py tests/reporter/test_synthesis_skills.py tests/reporter/test_analysis_skills.py tests/reporter/test_claim_risk_signal_skill.py tests/utils/test_periodic_report_fulltext_intake.py tests/utils/test_evidence_note_writer.py -q
158 passed in 3.51s
```

Extended periodic-report focused gate:

```text
python3 -m pytest tests/utils/test_periodic_report_evidence_pack.py tests/utils/test_periodic_report_required_metrics.py tests/utils/test_periodic_report_required_financial_metrics.py tests/utils/test_periodic_report_product_project_evidence.py tests/utils/test_periodic_report_fulltext_llm_analysis.py tests/utils/test_periodic_report_fulltext_intake.py tests/utils/test_hk_periodic_report_fetcher.py tests/utils/test_evidence_note_writer.py tests/reporter/test_source_intake_evidence_renderer.py tests/reporter/test_source_intake_merge_skill.py tests/reporter/test_synthesis_skills.py tests/reporter/test_analysis_skills.py tests/reporter/test_claim_risk_signal_skill.py -q
336 passed in 4.26s
```

---

## Phase 2 Source Intake Renderer Display

**Date:** 2026-06-18

Implemented minimal Phase 2 display layer:

- `SourceIntakeEvidenceRenderer` reads `ctx["periodic_report_fulltext_items"]` and renders `### 定期报告全文摘要（实验路径）` as a dedicated subsection.
- Each item shows publish time, title, source_credit, fixed `professional_analysis` status, and an `[实验]` marker.
- Malformed items claiming `confirmed_fact` / `fact_candidate` are forced back to `professional_analysis`; output never shows `confirmed_fact` or `fact_candidate` for fulltext items.
- Fulltext items are excluded from `### 定期报告关键摘录` and `### 代表性证据摘录`.
- Content preview applies heading downgrade (`#` → `###`, `##` → `####`, `###` → `#####`) and truncates to ~1600 chars.
- Renderer remains display-only and does not mutate `ctx` or item objects.

Tests added:

- `test_periodic_report_fulltext_items_renders_dedicated_experimental_section`
- `test_malformed_fulltext_item_confirmed_fact_still_renders_professional_analysis`
- `test_fulltext_item_excluded_from_representative_rows`
- `test_fulltext_item_excluded_from_periodic_excerpt_table`
- `test_fulltext_long_markdown_content_is_heading_downgraded_and_truncated`
- `test_renderer_does_not_mutate_fulltext_ctx_or_item`

Verification:

```text
python3 -m pytest tests/reporter/test_source_intake_evidence_renderer.py tests/reporter/test_source_intake_merge_skill.py tests/reporter/test_synthesis_skills.py tests/reporter/test_analysis_skills.py tests/reporter/test_claim_risk_signal_skill.py tests/utils/test_periodic_report_fulltext_intake.py tests/utils/test_evidence_note_writer.py -q
156 passed in 2.21s
```

`git diff --check` clean.

---

## Phase 3A Pipeline Registration Switch

**Date:** 2026-06-18

Added a default-off pipeline switch `enable_periodic_report_fulltext_intake` to `build_stock_report_pipeline`:

- New parameter `enable_periodic_report_fulltext_intake: bool = False`; default behavior unchanged.
- When enabled, registers `periodic_report_fulltext_intake_skill` after `source_intake_merge_skill` and before `evidence_note_writer_skill` (or before `cross_source_consolidation_skill` when evidence notes are disabled).
- The skill reads local cache from `data/raw/periodic_reports/` by default, overridable via ctx keys:
  - `periodic_report_fulltext_cache_dir`
  - `periodic_report_fulltext_report_type`
- Writes only to the independent ctx key `ctx["periodic_report_fulltext_items"]` and a diagnostic `ctx["periodic_report_fulltext_status"]`.
- Does NOT write to `external_evidence_keep_items` / `external_evidence_demote_items`.
- Hard-codes `enable_llm=False`; no network calls, no Chrome/CDP.
- Missing cache writes an empty list and continues without error.
- Preserved fixed metadata: `source_type=periodic_report_fulltext_analysis`, `source_credit=75`, `verification_status=professional_analysis`, `claim_status=professional_analysis`, `knowledge_eligible=False`, `report_eligible=False`, `experimental=True`.

Files modified:

- `scripts/utils/report_skills/__init__.py`
- `scripts/utils/report_skills/periodic_report_fulltext_intake_skill.py`
- `tests/reporter/test_pipeline_integration.py`
- `tests/utils/test_periodic_report_fulltext_intake.py`

Tests added:

Pipeline integration (`tests/reporter/test_pipeline_integration.py`):

- `test_periodic_report_fulltext_intake_disabled_by_default`
- `test_periodic_report_fulltext_intake_only_has_12_skills`
- `test_periodic_report_fulltext_intake_order_when_alone`
- `test_periodic_report_fulltext_intake_with_source_intake_has_14_skills`
- `test_periodic_report_fulltext_intake_order_after_source_intake_merge`
- `test_periodic_report_fulltext_intake_with_agent_reach_and_evidence_notes`
- `test_all_five_external_paths_enabled_has_19_skills`
- `test_periodic_report_fulltext_intake_end_to_end_missing_cache`
- `test_periodic_report_fulltext_intake_end_to_end_with_cache`

Skill wrapper unit tests (`tests/utils/test_periodic_report_fulltext_intake.py`):

- `test_skill_wrapper_exists`
- `test_skill_reads_ctx_overrides`
- `test_skill_skips_when_stock_code_missing`
- `test_skill_does_not_pollute_external_evidence`
- `test_skill_uses_default_cache_dir_when_no_override`

Verification:

```text
python3 -m pytest tests/reporter/test_pipeline_integration.py tests/utils/test_periodic_report_fulltext_intake.py tests/reporter/test_source_intake_evidence_renderer.py tests/reporter/test_source_intake_merge_skill.py tests/reporter/test_synthesis_skills.py tests/reporter/test_analysis_skills.py tests/reporter/test_claim_risk_signal_skill.py -q
147 passed in 61.28s

python3 -m pytest tests/reporter/test_periodic_report_fulltext_preview_script.py tests/utils/test_periodic_report_required_financial_metrics.py -q
27 passed in 2.67s
```

`git diff --check` clean.

---

## 10. 输出摘要

- **Status:** Ready（设计可进入 Phase 1 helper-only 实现）。
- **R2 Needed:** 建议在 Phase 1 完成后做一次 narrow R2，重点 review guardrails 和 no-leak 测试覆盖。
- **Blocker:** 无。
- **Must-fix before display:**
  1. ✅ `SourceIntakeEvidenceRenderer` 对 `periodic_report_fulltext_analysis` 强制降级 `professional_analysis`。
  2. ✅ `evidence_note_writer` 不会因阈值变化把该类型提升为 `fact_candidate`。
  3. ✅ `periodic_report_fulltext_intake_skill` 注册到 pipeline 时写入独立 `ctx["periodic_report_fulltext_items"]`，避开 `source_intake_merge_skill`（Phase 3A 已实现，默认关闭）。
- **Nice-to-have:**
  1. ✅ 预览 Markdown 标题层级自动降级（Phase 2 renderer 已实现）。
  2. 提供配置开关 `include_periodic_report_fulltext_in_synthesis` 供后续 LLM 材料层实验。
- **建议 focused tests:**
  - `tests/utils/test_periodic_report_fulltext_intake.py`
  - `tests/reporter/test_source_intake_evidence_renderer.py` 新增全文摘要相关 case
  - `tests/reporter/test_source_intake_merge_skill.py` 新增不折叠 case
  - `tests/utils/test_evidence_note_writer.py` 新增过滤 case
  - `tests/reporter/test_synthesis_skills.py` 或等效 no-leak 测试
