# Periodic Report Fulltext Synthesis Material Design

## Goal

让年报/半年报全文摘要不再只是 Source Intake 独立展示，而是可选进入最终 LLM 综合叙事的材料池，用来提升公司画像、主营业务、客户/供应商结构、研发项目、管理层行业判断和财务风险的完整度。

本阶段只做 synthesis material，不改变事实升格、评分、风险评分或 Knowledge 写入规则。

## Current State

- `periodic_report_fulltext_intake_skill` 生成 `ctx["periodic_report_fulltext_items"]`，固定：
  - `source_type=periodic_report_fulltext_analysis`
  - `source_credit=75`
  - `verification_status=professional_analysis`
  - `claim_status=professional_analysis`
  - `knowledge_eligible=False`
  - `report_eligible=False`
  - `experimental=True`
- `SourceIntakeEvidenceRenderer` 已可独立展示该 item，并强制 professional_analysis。
- `SynthesisSkill._build_synthesis_items()` 当前只从雪球、知乎、研报、公告、资金流、新闻构建 items，不读取 `periodic_report_fulltext_items`。
- `KnowledgeSynthesizer` 使用 numbered sources 生成主题叙事，并基于叙事中的 citation refs 再抽取 `core_facts`。
- `SynthesisSkill._enrich_core_fact_provenance()` 只允许公告/官方/交易所/巨潮或高信用 confirmed metadata 支撑核心事实；年报 fulltext 当前不符合该条件。

## Recommended Approach

采用显式开关 `include_periodic_report_fulltext_in_synthesis`，只把 fulltext items 追加到主题叙事输入列表，不进入 core facts / scoring / risk scoring。

### Why This Approach

- 最小改动：只触碰 `SynthesisSkill` 输入材料和 `synthesis_credit` 的显示规则。
- 保持安全：fulltext 仍是 `professional_analysis`，引用可用于叙事，但不能支撑核心事实。
- 可回退：关闭开关即可恢复当前行为。
- 可验证：可以用 fake synthesizer 检查 item 是否进入 synthesis items，用 core fact provenance 测试确认不被升格。

## Rejected / Deferred Approaches

### Directly Merge Into `external_evidence_keep_items`

拒绝。这样会绕过前面设计的独立 ctx key 和 merge 隔离，可能被 evidence notes、claim risk 或 Source Intake merge 误消费。

### Treat Fulltext As Confirmed Official Fact

拒绝。年报全文原文是官方高信用，但当前 item 是 LLM/deterministic 摘要材料，不是原始公告证据；不能把摘要结果当作 confirmed fact。

### Change KnowledgeSynthesizer Core Fact Prompt First

延期。核心事实抽取是高风险区域，必须等 synthesis material 效果稳定后再讨论。当前阶段只依赖 deterministic provenance filter 阻止 fulltext 成为核心事实支撑。

## Proposed Data Flow

1. Pipeline 生成 `periodic_report_fulltext_items`。
2. `SynthesisSkill.run()` 读取 ctx。
3. 若 `ctx.get("include_periodic_report_fulltext_in_synthesis") is True`，则：
   - 从 `ctx["periodic_report_fulltext_items"]` 取合法 item。
   - 只保留 `source_type == "periodic_report_fulltext_analysis"`。
   - 只保留 `verification_status == "professional_analysis"` 且 `experimental=True` 的 item。
   - 追加到普通 synthesis items 的末尾，或插入公告/研报之后、社区之前。
4. `KnowledgeSynthesizer._build_prompt()` 仍用 numbered sources；fulltext source line 要显示为：
   - 信用层：medium
   - 可用方式：annual_report_material
   - 提醒：可用于背景和分析判断，不可作为核心事实确认来源。
5. LLM 可以引用 fulltext source number 写主题叙事。
6. `extract_core_facts()` 可能抽到引用了 fulltext 的 core fact，但 `_enrich_core_fact_provenance()` 必须将其标记为 `invalid_ref` 或 `partially_supported`，不能产生 accepted source labels。
7. scoring/risk/knowledge 路径不新增任何读取 `periodic_report_fulltext_items` 的逻辑。

## Config / Switches

### Pipeline Input

新增 ctx 输入键：

```python
"include_periodic_report_fulltext_in_synthesis": True
```

默认缺省为 `False`。

### PerStockReporter

后续可在 `source_intake.periodic_report_fulltext.include_in_synthesis` 中透传该开关。第一阶段实现可只支持 pipeline input，避免扩大配置面。

推荐分两步：

1. Phase A：只支持 ctx input + unit tests。
2. Phase B：再把 stock config 透传进 `PerStockReporter`。

## Prompt / Credit Rules

需要扩展 `synthesis_credit.derive_synthesis_usage()`：

- 对 `source_type=periodic_report_fulltext_analysis`：
  - `credit_tier="medium"`
  - `usage="annual_report_material"`
  - `display_label="中高信用/annual_report_material"`

需要扩展 `credit_usage_rules_text()`：

- 年报全文摘要材料可以用于公司画像、业务结构、客户/供应商集中、研发进展、管理层市场判断、财务风险分析。
- 该材料是 professional_analysis，不得写成“公司已确认新的事实”。
- 关键数字仍必须引用 numbered source，且不得生成 source 中没有的新数字。
- 不得把年报 fulltext material 用作核心事实确认来源或风险评分依据。

`format_synthesis_source_line()` 目前截取 `item.content[:500]`，对 fulltext item 可能太短，容易截不到必备指标。建议只对该 source type 用 1200-1600 字符上限，或新增 extra 中的 compact material excerpt。Phase A 可先用 1200 字符。

## Core Fact Guardrail

必须补 deterministic 测试：

- `is_core_fact_supporting_source("定期报告全文", meta)` 返回 False，即使 `source_credit=75`。
- 如果 LLM 输出 core fact source_refs 只指向 fulltext item，`_enrich_core_fact_provenance()` 后：
  - `source_labels == []`
  - `evidence_type == "unknown"`
  - `provenance_status == "invalid_ref"`
- 如果 core fact 同时引用官方公告和 fulltext，结果只能由公告支撑：
  - `source_labels == ["公告"]`
  - `provenance_status == "partially_supported"`

## Testing Plan

### Unit Tests

`tests/reporter/test_synthesis_skills.py`

- default does not include `periodic_report_fulltext_items` in `items` passed to synthesizer.
- explicit ctx flag includes one fulltext item in `items` passed to synthesizer.
- invalid fulltext item metadata is skipped.
- fulltext item does not enter `external_evidence_keep_items`.
- core fact provenance rejects fulltext-only refs.
- mixed official announcement + fulltext refs remain partially supported by official source only.

`tests/utils/test_synthesis_credit.py` or existing equivalent

- fulltext source type maps to annual_report_material usage.
- fulltext source type is not core-fact supporting.
- formatted source line for fulltext includes annual_report_material and longer content excerpt.

### Integration Tests

`tests/reporter/test_pipeline_integration.py`

- enabling periodic fulltext intake alone does not include it in synthesis by default.
- enabling both periodic fulltext intake and synthesis material switch includes it before `SynthesisSkill` runs.

`tests/reporter/test_stock_reporter_source_intake_config.py`

- per-stock `include_in_synthesis=True` is passed to pipeline input only when fulltext intake is enabled.
- if fulltext intake is disabled, `include_in_synthesis=True` has no effect.

## Failure Modes

### Fulltext Becomes Core Fact

Symptom: `core_facts` contains a fact sourced only from `periodic_report_fulltext_analysis` and provenance says supported.

Catch:
- core fact provenance tests above.
- `is_core_fact_supporting_source` test.

### Fulltext Enters Scoring / Risk Scoring

Symptom: scoring or risk tests start reading `periodic_report_fulltext_items` or synthesis text from fulltext directly influences risk score.

Catch:
- repo grep in review: only `SynthesisSkill`, renderer, intake, preview script may read fulltext items.
- no changes to `scoring_engine.py`, `claim_risk_signal_skill.py`, technical modules.

### Prompt Gets Too Long

Symptom: synthesis prompt becomes too large or LLM output degrades.

Catch:
- source line excerpt cap for fulltext.
- test formatted source line length.
- keep only one latest fulltext item by intake helper.

### LLM Treats Material As Official Confirmation

Symptom: final paragraph says “公司确认” based only on fulltext material.

Mitigation:
- credit rules explicitly label annual_report_material.
- material remains `professional_analysis`.
- sample preview must be reviewed before default enabling.

### Missing Cache Creates Empty Synthesis Material

Symptom: switch on but no fulltext item exists; synthesis should behave as before.

Catch:
- test empty `periodic_report_fulltext_items` with include switch.

## Implementation Boundary

Allowed in Phase A:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/synthesis_credit.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/utils/test_synthesis_credit.py` if present or newly added

Allowed in Phase B:

- `scripts/utils/stock_reporter.py`
- `tests/reporter/test_stock_reporter_source_intake_config.py`

Forbidden:

- `KnowledgeSynthesizer.extract_core_facts()` prompt changes in Phase A.
- `scoring_engine.py`
- technical analysis modules
- `claim_risk_signal_skill.py`
- `source_intake_merge_skill.py`
- `evidence_note_writer.py`
- data/raw, reports, knowledge

## Rollout

1. Implement Phase A with ctx-only switch and tests.
2. Run focused synthesis tests.
3. Run one local preview with fake synthesizer to inspect prompt/item ordering.
4. Implement Phase B config passthrough only if Phase A is clean.
5. Run one real report with LLM disabled/fast-test first.
6. Only after user review, run real LLM preview for one stock.

## Open Questions For Review

1. Should fulltext item be appended after ordinary sources or inserted before community sources?
2. Is `credit_tier=medium` too conservative, or should display say `medium_high` while still rejecting core facts?
3. Should Phase A include config passthrough, or keep it strictly ctx-only?
4. Should fulltext source line use 1200 or 1600 chars?

## Round 1 Feedback

Reviewer: Claude Code（只读审查，未修改任何源码/测试/配置/prompt，未运行 LLM/网络/Chrome）。
审查依据已逐一对照实际代码：`synthesis_skills.py`、`knowledge_synthesizer.py`、`synthesis_credit.py`、`periodic_report_fulltext_intake_skill.py`、`scoring_engine.py`、`sections/risk_renderer.py`，以及现有测试。

### Status

**Needs minor fixes**（核心思路安全且可实现，但有 1 个未被识别的间接泄漏路径必须在设计层先决策，再实现）。

### R2 Needed

**Yes** — 仅需就下面的 Blocker（synthesis_text → 风险评分间接路径）补一段设计决策与对应测试，即可进入实现。改动量小，R2 应为轻量确认。

### Blockers

1. **`synthesis_text` 把 fulltext 叙事间接带入风险评分/风险板块（设计未覆盖）。**
   - 数据流实证：`SynthesisSkill.run()` 把 5 个主题叙事 flatten 成 `ctx["synthesis_text"]`（`synthesis_skills.py:56,327`）→ `risk_renderer.py:23,67` 透传 → `scoring_engine.py:632-643` 用关键词（如「降价 / 毛利率承压 / 净流出 / 替代 / 不及预期」）扫描 `synthesis_text` 生成 qualitative risk signals。
   - 一旦 fulltext item 被追加进 synthesis items，LLM 主题叙事就可能吸收年报材料措辞，这些措辞会落进 `synthesis_text`，从而：
     - `score_llm_keyword_risks=True` 时（`risk_renderer.py:25` 默认 False，但**是 per-context 开关**）→ **直接改变风险评分**，违反「fulltext 不进入风险评分」的硬不变式。
     - 即使为 False → 仍会进入 `keyword_observations` 在风险板块**展示**，构成软泄漏。
   - 设计现有的 catch（"repo grep：只有 SynthesisSkill/renderer/intake/preview 读 fulltext items；不改 scoring_engine"）**无法发现这条路径**：泄漏不经由读取 `periodic_report_fulltext_items`，而是搭乘已混合的叙事字符串。
   - 这条路径**不强制修改 `scoring_engine.py`**（即未触发停止条件），但设计必须显式决策一个 Phase-A 合法的缓解方案，例如（任选其一并写入设计）：
     a. 用于风险关键词扫描的文本与「fulltext 增强后的叙事」分离——即给 risk 路径喂一份**不含 fulltext 影响**的 `synthesis_text`（可在 `synthesis_skills.py` 内构造，不碰 scoring_engine）；
     b. 明确将 Phase A 限定为 `score_llm_keyword_risks=False`，并在文档/测试中固化「开启 fulltext synthesis 时禁止同时开启 keyword 风险评分」；
     c. 接受展示层软泄漏但用断言锁死「风险**评分数值**在 switch on/off 下不变」。
   - 注意：因为叙事是单一混合字符串，无法事后从中"减去"fulltext 句子，所以 (a)/(b) 比 (c) 更可靠。这一点必须在实现前定。

### Must-fix before implementation

1. **`derive_synthesis_usage()` 必须按 `source_type` 而非 `source_platform` 分支。** fulltext 的 `source_platform="定期报告全文"`，走现有 family 映射会落到最后的 `unknown / background_limited`（`synthesis_credit.py:259-263`）。必须在 `derive_synthesis_usage()` 顶部（`_is_high_credit_confirmed` 之后、platform 映射之前）加：`if meta.source_type == "periodic_report_fulltext_analysis": return {credit_tier, usage:"annual_report_material", ...}`。同时 `usage` **绝不能**是 `core_fact_allowed`。

2. **excerpt 放宽必须按 source_type 条件化，不能全局抬高。** `format_synthesis_source_line()` 当前对所有 item 统一 `content[:500]`（`synthesis_credit.py:269`）。若直接改成 1200/1600，会**抬高所有新闻/研报/社区 item** 的截断长度，整段 prompt（5 主题各重建一次来源列表）显著膨胀。必须仅对 `source_type=="periodic_report_fulltext_analysis"` 用更长上限。

3. **追加位置应在 items 末尾，保持既有编号稳定。**（回答 Open Q1）在 `_synthesize()` 内 `items = self._build_synthesis_items(...)` 之后、按 ctx flag 追加 fulltext item 到**末尾**最干净：`_build_synthesis_items(stock_raw, keep_posts)` 当前不接收 ctx，而 `_synthesize` 已持有 ctx（`synthesis_skills.py:85`）。插到中间会重排公告/研报的 `[^n]` 编号，破坏确定性与 prompt diff。

4. **保持 deterministic provenance filter 作为唯一核心事实闸门，不改 `extract_core_facts()` prompt。**（回答审查点 7）实测 `is_core_fact_supporting_source("定期报告全文", meta)` 已为 False：family 映射不命中 `公告/官方/交易所/巨潮`（"报告" ≠ "公告"），且 `source_credit=75 < 80` 阈值，`source_type/verification_status` 也不在 confirmed 集合（`synthesis_credit.py:148-171,281-305,129-145`）。因此即使 LLM 引用 fulltext 编号，`_enrich_core_fact_provenance()` 也会判为 `invalid_ref`。**前提**：实现时 fulltext 的 `source_credit` 必须保持 75（不得 ≥80），且不得把 `periodic_report_fulltext_analysis` 加入 `_CONFIRMED_SOURCE_TYPES`——否则两因子闸门会被绕过。

### Nice-to-have

1. **优先使用 `extra` 中预计算的 compact material excerpt，而非切原始 markdown。**（关联 Open Q4）fulltext content 是含表格管道符 `|` 和换行的渲染 markdown，整段塞进编号来源行可能让 LLM 误读为引用/表格结构并额外耗 token。建议 intake 时在 `extra` 写一个压平的 compact excerpt，source line 优先取它；否则在 source line 内做换行/表格压平。Phase A 上限取 **1200**（回答 Open Q4，比 1600 更保守，单 item 增量约 +700 字，风险低）。
2. **display_label 文案与 credit_tier 对齐。** 正文 line 94 写 `display_label="中高信用/annual_report_material"` 但 tier 是 `medium`；建议统一为 `中信用/annual_report_material`，或显式接受 `medium_high` 文案但 usage 仍非 core_fact（回答 Open Q2：label 用 medium_high 可以，只要 `source_credit` 仍 75 且 usage≠core_fact_allowed）。
3. **THEME min_items 行为变化提示。** `KnowledgeSynthesizer` 每主题要求 `len(items)>=3`（`knowledge_synthesizer.py:178-181`）。追加 fulltext 可能把"原本因条目不足而跳过合成"的瘦股推过阈值，触发本不会发生的合成。值得一个测试固化预期。
4. **Phase A 严格 ctx-only。**（回答 Open Q3）同意设计的两步走，Phase A 不做 config 透传，缩小配置面、便于单测。

### Suggested test additions

在设计现有 Testing Plan 基础上补：

1. **风险评分不变量（针对 Blocker）**：`test_pipeline_integration.py` —— 在 fulltext synthesis switch on/off 两种情况下（固定 FakeSynthesizer 叙事），断言 `risk_score_section` 产出的**风险评分数值**一致；并单列一个用例断言 `score_llm_keyword_risks=True` 时仍不被 fulltext 影响（按 Blocker 选定的缓解方案）。
2. **excerpt 条件化**：`test_synthesis_credit.py` —— 断言非 fulltext item 仍截断在 500，fulltext item 截断在 1200；并断言 fulltext source line 含 `annual_report_material`。
3. **no-leak 扩展（switch ON 时）**：现有 `test_periodic_report_fulltext_items_do_not_enter_synthesis_items` 只覆盖默认关。补一个 **switch ON** 的用例，断言 fulltext 仍**不进入** `external_evidence_keep_items`、不被 source intake merge 消费、不写 knowledge。
4. **evidence notes 隔离**：断言带 `report_eligible=False / knowledge_eligible=False` 的 fulltext item 不被 `evidence_note_writer` 选入（即便它出现在 synthesis items 中）。
5. **核心事实闸门（已在设计 Core Fact Guardrail 列出，确认保留）**：fulltext-only refs → `source_labels==[]`、`provenance_status=="invalid_ref"`；公告+fulltext 混合 → 仅公告支撑、`partially_supported`。
6. **编号稳定性**：断言追加 fulltext 后，既有公告/研报的引用编号不被重排。
7. **空缓存**：switch on 但无 fulltext item 时，synthesis items 与行为与关闭时一致（设计已列，保留）。

### Final recommendation

思路正确、与现有 deterministic provenance 闸门契合，核心事实/Knowledge 侧是安全的（两因子闸门已实测拦截 credit-75 的 fulltext）。**唯一必须先解决的是 Blocker：`synthesis_text → scoring_engine` 的间接路径**——它是设计 grep-guard 的盲区，且默认 `score_llm_keyword_risks=False` 只是把风险从"评分泄漏"降级为"展示泄漏"，并未消除。请在设计中明确选定缓解方案（推荐 (a)：为风险关键词扫描提供一份不含 fulltext 影响的文本，全部在 `synthesis_skills.py` 内完成，不触碰 `scoring_engine.py`），并补充上面的风险不变量测试。完成该决策 + Must-fix 1-4 后即可进入 Phase A 实现。

**未触发停止条件**：实现不强制修改 `scoring_engine.py`、technical 模块、`claim_risk_signal_skill.py`、`source_intake_merge_skill.py` 或 `extract_core_facts()` prompt——Blocker 的缓解可完全落在 `synthesis_skills.py` / `synthesis_credit.py`。

## Design Delta After Round 1

### Accepted

1. **接受 blocker：`synthesis_text → risk_score_section` 是真实间接路径。**
   - `RiskRenderer` 从 `ctx["synthesis_text"]` 读取文本，再传给 `risk_score_section()`。
   - `risk_score_section()` 即使 `score_llm_keyword_risks=False`，也会从 `synthesis_text` 生成 keyword observations；如果开关为 True，还会加风险分。
   - 因此不能只靠“scoring_engine 不读取 `periodic_report_fulltext_items`”来证明 no-leak。

2. **采用双结果策略，避免修改 scoring/risk 代码。**
   - Phase A 中，当 `include_periodic_report_fulltext_in_synthesis=True` 且存在合法 fulltext item：
     1. 先用普通 synthesis items 生成 **baseline synthesis**。
     2. 再把 fulltext item 追加到普通 items 末尾，生成 **enhanced synthesis**。
     3. `ctx["synthesis"]` 使用 enhanced synthesis，用于最终报告主题叙事展示。
     4. `ctx["core_facts"]` 使用 baseline synthesis 的 `core_facts`。
     5. `ctx["synthesis_text"]` 使用 baseline synthesis flatten 后的文本，继续供风险关键词扫描使用。
     6. 可选写入 `ctx["synthesis_text_with_periodic_report_fulltext"]` 仅供调试/预览，不被风险路径读取。
   - 这样 fulltext 影响最终叙事，但不影响核心事实、风险评分、风险 keyword observations。
   - 代价是 opt-in 时可能多一次 synthesis 调用；该路径仍是实验开关，成本可接受。

3. **`derive_synthesis_usage()` 必须先看 `source_type`。**
   - 对 `source_type=="periodic_report_fulltext_analysis"` 返回：
     - `credit_tier="medium"`
     - `usage="annual_report_material"`
     - `display_label="中信用/annual_report_material"`
   - 不加入 `_CONFIRMED_SOURCE_TYPES`。
   - 不返回 `core_fact_allowed`。

4. **fulltext source line 截断仅对 fulltext 放宽。**
   - 非 fulltext 仍保持 500 字。
   - fulltext 使用 1200 字上限。
   - 如后续有 compact excerpt，`format_synthesis_source_line()` 可优先使用 `item.extra["synthesis_excerpt"]`；Phase A 不强制新增该字段。

5. **fulltext item 追加到末尾。**
   - 保持既有普通来源编号稳定。
   - 只增加新的最后一个 citation number。

6. **Phase A 保持 ctx-only。**
   - 暂不做 `PerStockReporter` config 透传。
   - 等 ctx-only 行为和 no-leak 测试稳定后，再进入 Phase B。

### Rejected

1. **拒绝只依赖 `score_llm_keyword_risks=False`。**
   - 默认 False 只能阻止风险加分，不能阻止 keyword observations 展示。
   - 不满足“fulltext 不进入风险评分/风险路径”的强隔离目标。

2. **拒绝修改 `scoring_engine.py`。**
   - blocker 可通过 `SynthesisSkill` 控制 `synthesis_text` 内容解决。
   - 不需要扩大到评分核心逻辑。

3. **拒绝修改 `KnowledgeSynthesizer.extract_core_facts()` prompt。**
   - deterministic provenance filter 已能拒绝 credit-75 fulltext。
   - Phase A 不改核心事实 prompt。

### Updated Data Flow

Phase A 的 `SynthesisSkill._synthesize()` 逻辑应为：

```python
base_items = self._build_synthesis_items(stock_raw, keep_posts)
include_fulltext = bool(ctx.get("include_periodic_report_fulltext_in_synthesis"))
fulltext_items = self._eligible_periodic_report_fulltext_items(ctx) if include_fulltext else []

baseline = synthesize(base_items)

if not fulltext_items:
    return baseline

enhanced_items = base_items + fulltext_items
enhanced = synthesize(enhanced_items)

# Preserve baseline-only fields for no-leak boundaries.
enhanced["core_facts"] = baseline.get("core_facts", [])
enhanced["_risk_synthesis_text"] = flatten(baseline)
enhanced["_synthesis_text_with_periodic_report_fulltext"] = flatten(enhanced)
enhanced["_items_count"] = len(enhanced_items)
enhanced["_sources"] = source_list(enhanced_items)
enhanced["_periodic_report_fulltext_synthesis_enabled"] = True
return enhanced
```

`SynthesisSkill.run()` then writes:

```python
ctx.set("synthesis", synthesis)
ctx.set("core_facts", synthesis.get("core_facts", []))
ctx.set("synthesis_text", synthesis.get("_risk_synthesis_text") or self._flatten_synthesis_text(synthesis))
if synthesis.get("_synthesis_text_with_periodic_report_fulltext"):
    ctx.set("synthesis_text_with_periodic_report_fulltext", synthesis["_synthesis_text_with_periodic_report_fulltext"])
```

### Updated Testing Plan

Add the following tests before implementation:

1. `test_periodic_report_fulltext_synthesis_default_off`
   - Given fulltext items in ctx but no include flag.
   - Synthesizer receives only ordinary items.
   - `ctx["synthesis_text"]` is ordinary baseline text.

2. `test_periodic_report_fulltext_synthesis_appends_item_when_enabled`
   - Given include flag and one valid fulltext item.
   - Fake synthesizer sees first call with ordinary items and second call with ordinary + fulltext.
   - Fulltext is last item.

3. `test_periodic_report_fulltext_synthesis_preserves_baseline_core_facts`
   - Fake baseline returns core fact A.
   - Fake enhanced returns core fact B sourced from fulltext.
   - Final `ctx["core_facts"]` contains A, not B.

4. `test_periodic_report_fulltext_synthesis_text_for_risk_stays_baseline`
   - Fake baseline text has no risk keyword.
   - Fake enhanced text contains “降价”“毛利率承压”.
   - Final `ctx["synthesis_text"]` equals baseline flatten.
   - `ctx["synthesis_text_with_periodic_report_fulltext"]` contains enhanced text.

5. `test_periodic_report_fulltext_risk_keyword_score_invariant`
   - Feed final `ctx["synthesis_text"]` into `risk_score_section(..., score_llm_keyword_risks=True)`.
   - Assert the result matches baseline/no-fulltext case.

6. `test_periodic_report_fulltext_credit_usage`
   - `derive_synthesis_usage(fulltext_item)` returns `annual_report_material`.
   - `is_core_fact_supporting_source("定期报告全文", meta)` returns False.

7. `test_periodic_report_fulltext_source_line_uses_longer_cap_only_for_fulltext`
   - Ordinary item content is capped at 500.
   - Fulltext item content is capped at 1200.

### Revised Implementation Boundary

Allowed in Phase A:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/synthesis_credit.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_scoring_engine_risk.py` or existing risk test only for invariant assertion
- `tests/utils/test_synthesis_credit.py` if present or newly added

Still forbidden in Phase A:

- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `scripts/utils/knowledge_synthesizer.py` prompt changes
- technical modules
- `claim_risk_signal_skill.py`
- `source_intake_merge_skill.py`
- `evidence_note_writer.py`
- data/raw, reports, knowledge

### R2 Required

Yes. R2 scope is narrow:

- Confirm the dual-result strategy is sufficient and worth the extra opt-in LLM cost.
- Confirm `ctx["synthesis_text"]` should remain baseline while `ctx["synthesis"]` is enhanced.
- Confirm no need to touch `risk_renderer.py` or `scoring_engine.py`.

## Round 2 Feedback

Reviewer: Claude Code（只读 R2 审查，未修改源码/测试/配置/prompt，未运行 LLM/网络/Chrome）。
本轮实测追踪了 `ctx["synthesis"]` / `ctx["synthesis_text"]` / `ctx["core_facts"]` 的全部下游消费者，逐一核对 delta 的双结果策略。

### Status

**Needs minor fixes** —— R1 的风险评分泄漏 blocker 已被双结果策略**确实解决**；但本轮发现**同一个 `ctx["synthesis"]` enhanced 结果还被 Knowledge 写入路径消费**，delta 只考虑了展示渲染器，遗漏了这一消费者，构成一个新的、必须先决策的隔离缺口。其余设计可判定为 Ready。

### R1 Blocker 是否解决？——是（已实测确认）

双结果策略对**风险路径**有效，且无需碰 scoring/risk 代码：

- 风险路径只读 `ctx["synthesis_text"]`：`risk_renderer.py:23,67` → `scoring_engine.py:632-643`。delta 让 `ctx["synthesis_text"]` 保持 **baseline flatten**，因此 fulltext 措辞不会进入关键词扫描，`score_llm_keyword_risks=True/False` 两种情况都不受影响。✔（回答 R2 Q1、Q2）
- `claim_risk_signal_skill.py` 实测只读 `enable_claim_risk_signals` 与 `claim_verification_base_dir`（`claim_risk_signal_skill.py:55,62`），**不读** synthesis/synthesis_text，故该路径天然无泄漏。✔
- `ctx["synthesis_text_with_periodic_report_fulltext"]` 全仓库**零消费者**（grep 确认），作为 debug-only 安全。✔

### Blockers

1. **`ctx["synthesis"]`（enhanced）会被 Knowledge 写入路径持久化，delta 未覆盖。**
   - 实测消费者：`knowledge_skills._write_deep_analysis()` 在 `knowledge_skills.py:61` 读取 `ctx.get("synthesis")`，并在 `:117-128` 遍历 `synthesis.items()` 把**每个主题叙事原文**写入 `knowledge/{stock}/{date}-深度解读.md`。
   - delta 把 `ctx["synthesis"]` 设为 enhanced（含 fulltext 影响的叙事），于是 fulltext 派生的叙事 prose **被写进 knowledge/**。这与设计的硬不变式冲突：fulltext item 是 `knowledge_eligible=False`，且本设计开篇声明“不改变 Knowledge 写入规则”。
   - 二次泄漏风险：`claim_verification` 以 `knowledge/` 为 base_dir 读取历史沉淀（`synthesis_skills.py:120-128` 的 cv 路径、`claim_risk_signal_skill.py:62`）。写进 knowledge 的 enhanced 叙事会在**后续运行**被重新消费，形成跨运行回流，绕过本轮所有 in-run 隔离。
   - delta 的论断「fulltext 影响最终叙事，但不影响核心事实、风险评分、风险 keyword observations」对**展示渲染器**成立（`executive_summary_renderer.py:245`、`deep_analysis_renderer.py:34`、`html_dashboard_renderer.py:125` 均为展示），但漏掉了 `knowledge_skills` 这个**非展示**消费者。
   - **需要的决策（实现前定）**，二选一并写入设计：
     a. **拆分展示键与持久化键**：`ctx["synthesis"]` 保持 **baseline**（供 Knowledge 与其它默认消费者），enhanced 叙事写入一个新键（如 `ctx["synthesis_display"]`），仅由三个展示渲染器读取。代价：需改这 3 个渲染器，超出当前 Allowed 列表。
     b. **让 Knowledge 写 baseline 叙事**：`knowledge_skills._write_deep_analysis` 改读一个 baseline 叙事键。代价：需把 `knowledge_skills.py` 纳入 Allowed，且需确认不违反“不改 Knowledge 写入规则”的字面约束（建议解读为：改的是“喂给它的数据来源”，写入规则本身不变）。
   - 注意：上述任一方案**都不触碰停止条件文件**（scoring_engine / technical / claim_risk_signal / source_intake_merge / extract_core_facts prompt），故未触发停止条件；但 delta 的 Allowed Phase A 列表（仅 synthesis_skills + synthesis_credit + tests）**对该修复不足**，必须相应扩列。

### Must-fix before implementation

1. **解决上面的 Knowledge 写入泄漏**（Blocker 1），并据所选方案修正 “Revised Implementation Boundary” 的 Allowed 列表（加入 3 个 renderer 或 `knowledge_skills.py`）。
2. **补 Knowledge 隔离测试**：断言开启 fulltext synthesis 后，`knowledge_skills` 产出的“深度解读”叙事等于 baseline（不含 fulltext 措辞），或按方案 a 断言 `ctx["synthesis"]` 仍为 baseline。当前 Updated Testing Plan 的 7 条**未覆盖 Knowledge 写入路径**。
3. **双结果实现细节需写清 citation/provenance 归属**：伪代码里的 `synthesize()` 在真实 `_synthesize()` 中还包含 `_fill_citation_metadata()` 与 `_enrich_core_fact_provenance()`（`synthesis_skills.py:94-95`）。需明确：baseline 跑完整 fill+enrich（其 core_facts 被保留）；enhanced 仅需 fill_citation_metadata 供展示引用，provenance 可不重算。否则 enhanced 的 core_facts 计算结果会被丢弃却仍耗算力。
4. **截断与 usage 分支均按 `source_type` 判定**：`format_synthesis_source_line()` 的 1200 上限与 `derive_synthesis_usage()` 的 fulltext 分支必须都基于 `source_type=="periodic_report_fulltext_analysis"`（而非 platform）。delta 已对 usage 写明“先看 source_type”，请对截断也写同一条件，避免按 platform 误判。（回答 R2 Q4：分支与截断策略基本明确，补这一句即完整。）

### Nice-to-have

1. **更正成本表述**（回答 R2 Q3）：delta 写“可能多一次 synthesis 调用”，实际一次 `synthesize()` 含至多 5 个主题 + core_facts 抽取≈6 次 LLM 调用，双结果会使 opt-in 的 synthesis LLM 成本**翻倍**，而非“多一次”。结论仍可接受（实验 opt-in），但应如实写明量级，便于使用者评估。
2. **citation 编号稳定性测试**（R1 遗留）：Updated Test #2 只断言“fulltext 是最后一项”，建议加断言：追加 fulltext 后既有公告/研报的 `[^n]` 编号不变（append-at-end 已保证，值得固化）。
3. **debug 键的负向守卫测试**：加一条断言 `ctx["synthesis_text_with_periodic_report_fulltext"]` 不被风险/scoring 路径读取（当前 grep 为零消费者，固化以防回归）。
4. **展示一致性提示**：方案若保留 enhanced 仅用于展示，注意 `deep_analysis_renderer` 同屏展示 enhanced 叙事 + baseline `core_facts`，二者可能轻微不一致（叙事提到的点未必出现在 baseline 核心事实里）；属可接受，但建议在设计里记一句预期。

### Final recommendation

双结果策略在**风险评分/keyword observations 维度**已正确闭合 R1 blocker，且确实无需改 `risk_renderer.py` / `scoring_engine.py`（回答 R2 Q2：确认不需要）。但 `ctx["synthesis"]=enhanced` 这一键的消费者不止展示渲染器，还有 **Knowledge 写入器**，这会把 fulltext 叙事持久化进 `knowledge/` 并在后续运行回流——这是设计声明的强隔离目标的实质缺口，必须在实现前用方案 a 或 b 决策，并相应扩 Allowed 列表 + 补 Knowledge 隔离测试。完成 Blocker 1 与 Must-fix 1-4 后即可进入 Phase A。其余（usage 分支、截断、append-at-end、ctx-only、风险不变量测试）均判定 **Ready**。

**未触发停止条件**：上述修复落在 `synthesis_skills.py` / `synthesis_credit.py` /（按方案）display renderers 或 `knowledge_skills.py`，**不需要**修改 `scoring_engine.py`、technical 模块、`claim_risk_signal_skill.py`、`source_intake_merge_skill.py` 或 `extract_core_facts()` prompt。

## Design Delta After Round 2

### Accepted

1. **接受 blocker：`ctx["synthesis"]` 还有 Knowledge 写入消费者。**
   - `KnowledgePersistenceSkill._write_deep_analysis()` 读取 `ctx["synthesis"]` 并写入 `knowledge/10-Stocks/{stock}/{date}-深度解读.md`。
   - 如果 `ctx["synthesis"]` 使用 enhanced synthesis，fulltext 派生叙事会被持久化，并可能被后续 claim verification 从 knowledge base 回读。
   - 因此 `ctx["synthesis"]` 不能改成 enhanced。

2. **采用方案 a：拆分 canonical synthesis 与 display synthesis。**
   - `ctx["synthesis"]` 永远保持 baseline synthesis。
   - `ctx["core_facts"]` 来自 baseline synthesis。
   - `ctx["synthesis_text"]` 来自 baseline synthesis。
   - `ctx["synthesis_sources"]` 来自 baseline synthesis。
   - 新增 `ctx["synthesis_display"]` 存 enhanced synthesis，仅供展示 renderer 使用。
   - 新增 `ctx["synthesis_display_sources"]` 存 enhanced sources，供后续如需展示来源时使用。
   - 新增 `ctx["synthesis_text_with_periodic_report_fulltext"]` 作为 debug/preview-only 字符串，不被风险或 Knowledge 路径读取。

3. **展示 renderer 显式 opt-in enhanced synthesis。**
   - 只允许以下 renderer 读取 `ctx.get("synthesis_display") or ctx.get("synthesis")`：
     - `ExecutiveSummaryRenderer`
     - `DeepAnalysisRenderer`
     - `HtmlDashboardRenderer`
   - Knowledge 写入器不改，继续读 baseline `ctx["synthesis"]`。
   - 风险 renderer 不改，继续读 baseline `ctx["synthesis_text"]`。

4. **更新成本描述。**
   - 开启 fulltext synthesis material 时不是“多一次 LLM 调用”，而是多一次 `KnowledgeSynthesizer.synthesize()`。
   - 该方法最多包含 5 个主题调用 + 1 次 core facts 抽取，因此成本近似翻倍。
   - 该路径必须保持 opt-in，不默认开启。

5. **明确 citation/provenance 归属。**
   - baseline synthesis 完整执行 `_fill_citation_metadata()` 和 `_enrich_core_fact_provenance()`。
   - enhanced synthesis 需要 `_fill_citation_metadata()`，用于展示 renderer 的引用来源。
   - enhanced synthesis 的 `core_facts` 不写入 ctx，不进入 Knowledge，不进入 risk path；可直接丢弃或保留在 `synthesis_display` 内但展示 core facts 仍读取 `ctx["core_facts"]` baseline。
   - `DeepAnalysisRenderer` 展示 enhanced narrative + baseline core facts 是预期行为；二者可能不完全覆盖同一组事实，但 fulltext material 仍是展示层增强，不是核心事实来源。

### Updated Data Flow

Phase A 的 `SynthesisSkill.run()` 写 ctx 时应为：

```python
baseline = self._synthesize_baseline(stock_name, stock_raw, keep_posts, ctx)
display = baseline

if ctx.get("include_periodic_report_fulltext_in_synthesis"):
    fulltext_items = self._eligible_periodic_report_fulltext_items(ctx)
    if fulltext_items:
        display = self._synthesize_with_extra_items(
            stock_name,
            stock_raw,
            keep_posts,
            ctx,
            extra_items=fulltext_items,
        )

ctx.set("synthesis", baseline)
ctx.set("core_facts", baseline.get("core_facts", []))
ctx.set("synthesis_text", self._flatten_synthesis_text(baseline))
ctx.set("synthesis_items_count", baseline.get("_items_count", 0))
ctx.set("synthesis_sources", baseline.get("_sources", []))

if display is not baseline:
    ctx.set("synthesis_display", display)
    ctx.set("synthesis_display_sources", display.get("_sources", []))
    ctx.set("synthesis_text_with_periodic_report_fulltext", self._flatten_synthesis_text(display))
```

Implementation may factor this differently, but these ctx semantics are fixed.

### Updated Implementation Boundary

Allowed in Phase A:

- `scripts/utils/report_skills/synthesis_skills.py`
- `scripts/utils/synthesis_credit.py`
- `scripts/utils/reporter/sections/executive_summary_renderer.py`
- `scripts/utils/reporter/sections/deep_analysis_renderer.py`
- `scripts/utils/reporter/sections/html_dashboard_renderer.py`
- `tests/reporter/test_synthesis_skills.py`
- `tests/reporter/test_scoring_engine_risk.py` or existing risk test only for invariant assertion
- `tests/reporter/test_executive_summary_renderer.py`
- `tests/reporter/test_deep_analysis_renderer.py`
- `tests/reporter/test_html_dashboard_renderer.py` if present or equivalent
- `tests/utils/test_synthesis_credit.py` if present or newly added

Still forbidden in Phase A:

- `scripts/utils/reporter/scoring_engine.py`
- `scripts/utils/reporter/sections/risk_renderer.py`
- `scripts/utils/report_skills/knowledge_skills.py`
- `scripts/utils/knowledge_synthesizer.py` prompt changes
- technical modules
- `claim_risk_signal_skill.py`
- `source_intake_merge_skill.py`
- `evidence_note_writer.py`
- data/raw, reports, knowledge

### Updated Tests

Add these tests to the Phase A implementation task:

1. `test_periodic_report_fulltext_synthesis_keeps_canonical_synthesis_baseline`
   - Include flag on and valid fulltext item exists.
   - Fake synthesizer baseline returns `"baseline narrative"`.
   - Fake synthesizer enhanced returns `"fulltext 降价 毛利率承压 narrative"`.
   - Assert `ctx["synthesis"]` contains baseline only.
   - Assert `ctx["synthesis_display"]` contains enhanced.

2. `test_periodic_report_fulltext_synthesis_does_not_change_synthesis_text_or_core_facts`
   - Assert `ctx["synthesis_text"]` is baseline flatten.
   - Assert `ctx["core_facts"]` is baseline core facts.
   - Assert enhanced fulltext risk keywords only appear in `ctx["synthesis_text_with_periodic_report_fulltext"]`.

3. `test_periodic_report_fulltext_knowledge_persistence_would_receive_baseline`
   - Without writing knowledge files, instantiate/run a minimal ctx through the relevant assertions or monkeypatch `_write_deep_analysis`.
   - Assert `ctx.get("synthesis")` passed to Knowledge remains baseline and does not contain fulltext-only phrase.

4. `test_display_renderers_prefer_synthesis_display`
   - For the three display renderers, ctx has:
     - `synthesis`: baseline phrase
     - `synthesis_display`: enhanced phrase
   - Assert rendered output uses enhanced phrase where that renderer consumes synthesis.
   - Assert renderers fall back to baseline when `synthesis_display` is absent.

5. `test_risk_renderer_uses_baseline_synthesis_text`
   - Existing risk renderer behavior remains unchanged.
   - Given `synthesis_text` baseline and `synthesis_text_with_periodic_report_fulltext` containing risk keywords, risk renderer/scoring input uses baseline only.

6. `test_synthesis_credit_fulltext_usage_and_excerpt`
   - Fulltext usage is `annual_report_material`.
   - Fulltext is not core-fact supporting.
   - Fulltext source line cap is 1200 by source_type.
   - Ordinary source line cap remains 500.

7. `test_append_at_end_preserves_existing_source_order`
   - Baseline ordinary items keep the same order.
   - Fulltext item is appended last in enhanced synthesis input.

### R3 Required

No, unless implementation discovers that display renderers cannot safely consume `synthesis_display` without larger report assembly changes.

Reason:

- R2 blocker has a concrete low-risk resolution.
- The new allowed files are display renderers only, not core scoring/risk/Knowledge logic.
- Knowledge persistence remains unchanged and receives baseline by construction.
