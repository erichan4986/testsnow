# Source Intake v2 Design

Date: 2026-06-14

## Goal

Add a structured A-share source intake path alongside Agent-Reach, so single-stock reports can consume both:

- structured A-share sources from `a-stock-data` / akshare / direct APIs
- unstructured web sources from Agent-Reach

Downstream behavior must remain unified:

```text
source intake
  -> source credit
  -> evidence notes
  -> claim verification
  -> official fact summary / professional observation / structured risk signals
```

The goal is not to dump more raw material into LLM synthesis. The goal is to make external evidence broader, better typed, and safer.

## Current Context

Recent 中简科技 validation shows:

- Agent-Reach can read configured cninfo URLs and write high-credit evidence notes.
- Claim verification can use those official notes to verify low-credit community claims.
- Structured risk signals can score only verified/supported claim risks.
- Report display now separates:
  - `官方事实核验摘要`
  - `Agent-Reach 外部证据观察`
  - `结构化风险观察`

But Agent-Reach is not the best primary entrance for all A-share data:

- cninfo announcements are structured by stock code/date/type.
- Eastmoney stock news is available as structured rows.
- Eastmoney research report lists are structured by stock code.
- RSS is useful as a discovery layer, but not a core evidence path.
- social media should remain low-credit claim input, not fact input.

Claude local `a-stock-data` smoke result for 中简科技:

- 15/20 endpoints passed.
- cninfo works when `market="沪深京"` is used instead of old `深市/沪市`.
- `stock_news_em` works.
- Eastmoney global news works but needs strict filtering.
- Eastmoney research list works.
- mootdx and Tencent quote paths are stable.
- CLS timeout, iwencai missing key, `stock_individual_info_em` ProxyError, old sector function missing.

## Non-Goals

- Do not replace Agent-Reach.
- Do not put medium-credit professional/news sources directly into official facts.
- Do not let news/research directly affect risk score.
- Do not modify `KnowledgeSynthesizer` prompt in this phase.
- Do not crawl Xueqiu detail pages or use CDP.
- Do not enable social media connectors in this phase.
- Do not bulk refresh all stocks.

## Source Classes

### 1. High-Credit Official Sources

Examples:

- cninfo announcements
- HKEX / exchange disclosures
- company official website / IR pages

Default use:

- write evidence notes
- verify low-credit claims
- appear in `官方事实核验摘要`

Initial Source Intake v2 scope:

- `cninfo_announcements` via akshare `stock_zh_a_disclosure_report_cninfo`
- use `market="沪深京"` for A-share stocks
- filter by stock code and date range
- keep only configured categories or recent relevant announcements

### 2. Medium-Credit Professional / News Sources

Examples:

- Eastmoney stock news via `stock_news_em`
- Eastmoney research report list / summary
- industry policy and supply-chain news
- Tonghuashun news if a stable API path exists

Default use:

- professional/news background observation
- catalyst/background candidate
- cross-source context for human review

Constraints:

- do not become official facts by themselves
- do not directly produce structured risk signals
- may support `supported` status only when paired with high-credit evidence or multiple independent medium-credit sources in a future phase

Initial Source Intake v2 scope:

- `eastmoney_stock_news`
- `eastmoney_research_reports`
- optional `eastmoney_global_news` only with strict stock-name/code filter and small cap

### 3. Low-Credit Community / Social Sources

Examples:

- Xueqiu posts
- Zhihu notes
- Weibo / social media connectors

Default use:

- unverified claim pool
- never direct fact/scoring input

Out of scope for this phase, but must be recorded as follow-up.

## Proposed Config Shape

Add a new per-stock config block, separate from `agent_reach`:

```json
"source_intake": {
  "enabled": true,
  "a_stock": {
    "enabled": true,
    "cninfo_announcements": {
      "enabled": true,
      "lookback_days": 365,
      "max_items": 12,
      "categories": ["年报", "季报", "业绩预告", "权益分派", "投资者关系活动", "风险提示"]
    },
    "eastmoney_stock_news": {
      "enabled": true,
      "max_items": 10
    },
    "eastmoney_research_reports": {
      "enabled": true,
      "max_items": 8
    },
    "eastmoney_global_news": {
      "enabled": false,
      "max_items": 5
    }
  },
  "rss_discovery": {
    "enabled": false
  },
  "social_media_followup": {
    "enabled": false
  }
}
```

Compatibility:

- Keep existing `agent_reach` config unchanged.
- Source Intake v2 should not require Agent-Reach to be enabled.
- Evidence notes can be enabled for either Agent-Reach or Source Intake v2.

## Data Model

Introduce a normalized item surface for all external source intake paths.

Recommended name:

```python
ExternalEvidenceItem
```

Fields:

- `title`
- `content`
- `url`
- `source_platform`
- `source_type`
- `source_credit`
- `verification_status`
- `publish_time`
- `stock_name`
- `stock_code`
- `topics`
- `source_family`
- `raw_metadata`

Compatibility rule:

- It may be implemented as `SynthesisItem` in Phase 1 to reduce churn.
- If using `SynthesisItem`, all source-credit metadata must live in `extra`.

Required source typing:

| Source | source_type | source_credit | verification_status |
|---|---|---:|---|
| cninfo announcement | `exchange_announcement` | 95 | `confirmed_fact` |
| company official website | `company_official` | 90 | `confirmed_fact` |
| Eastmoney stock news | `news` | 60 | `professional_observation` |
| Eastmoney research report | `research_report` | 65 | `professional_observation` |
| industry policy | `policy_news` | 75 | `professional_observation` |
| Xueqiu/Zhihu/social | `social_discussion` | 30-40 | `market_opinion` |

## Pipeline Design

Current simplified pipeline:

```text
data_loading
quality_gate
agent_reach_query/fetch/quality
evidence_note_writer
cross_source_consolidation
quote/competitor/technical
synthesis
claim_risk_signal
scoring
charts
assembly
```

Proposed Source Intake v2 pipeline:

```text
data_loading
quality_gate

agent_reach_query/fetch/quality          # optional web/RSS path
a_stock_source_intake                    # optional structured A-share path
source_intake_merge                      # normalize all external evidence buckets
evidence_note_writer                     # reads merged external evidence, backward compatible

cross_source_consolidation
quote/competitor/technical
synthesis
claim_risk_signal
scoring
charts
assembly
```

Implementation notes:

- `a_stock_source_intake` must be default-off.
- `source_intake_merge` should produce:
  - `external_evidence_keep_items`
  - `external_evidence_demote_items`
  - `external_evidence_discard_items`
  - `source_intake_summary`
- `evidence_note_writer_skill` should prefer merged `external_evidence_*` keys when present, and fall back to existing `agent_reach_*` keys for backward compatibility.
- Existing Agent-Reach renderer may continue rendering only Agent-Reach evidence in Phase 1.
- Add a separate renderer later for professional/news background if needed.

## Phase 1 Scope

Implement the smallest useful slice:

1. Add `a_stock_source_intake_skill`.
2. Add pure helper module for A-share structured source adapters.
3. Support:
   - cninfo announcement list metadata
   - Eastmoney stock news rows
   - Eastmoney research report rows
4. Convert rows to source-credit tagged `SynthesisItem`.
5. Merge with Agent-Reach outputs for evidence-note writing.
6. Add source-status summary and compact audit metadata.
7. Run on 中简科技 only.

Phase 1 should not fetch or parse full long PDFs beyond metadata/content snippets. Long annual-report extraction stays backlog.

## Source-Specific Rules

### cninfo Announcements

Use:

```python
ak.stock_zh_a_disclosure_report_cninfo(
    symbol="300777",
    market="沪深京",
    start_date="YYYYMMDD",
    end_date="YYYYMMDD",
)
```

Rules:

- `market="沪深京"` is required for current akshare version.
- Filter by `公告标题`, `公告时间`, `公告链接`.
- Keep recent high-value categories:
  - 年度报告
  - 季度报告
  - 业绩预告
  - 权益分派
  - 投资者关系活动记录
  - 风险提示 / 处罚 / 税务 / 诉讼
- Cap rows.
- Write metadata-rich evidence notes.
- Do not pass full PDF body to LLM.

### Eastmoney Stock News

Use `ak.stock_news_em(symbol="300777")`.

Rules:

- source_credit 60.
- Require stock name/code or strong entity match.
- Cap rows.
- Treat as professional/news observation.
- Do not verify low-credit social claims without high-credit confirmation in this phase.

### Eastmoney Research Reports

Use existing reportapi path or a-stock helper.

Rules:

- source_credit 65.
- Treat as research/professional observation.
- Do not treat broker interpretation as official fact.
- Preserve rating/EPS/target-price as report metadata, not confirmed facts.
- No PDF download by default.

### Eastmoney Global News

Default disabled.

Rules:

- only enable for strict filter experiments
- cap at 5
- discard if no stock name/code match

### RSS

Backlog only.

RSS is a discovery mechanism:

```text
rss_discovery -> URL candidates -> Agent-Reach web read -> source_credit
```

Do not use RSS content directly as fact evidence without source typing.

### Social Media

Follow-up after Source Intake v2 is working.

Targets to test:

- Xueqiu via local cache / user-authorized CDP only
- Weibo
- possibly Bilibili / Xiaohongshu / Twitter / Reddit depending on stock

All social items must enter low-credit claim pool only.

## Report Display

Phase 1 report display can stay conservative:

- High-credit verified claims appear in `官方事实核验摘要` after claim verification.
- Agent-Reach web evidence remains in `Agent-Reach 外部证据观察`.
- Medium-credit news/research should not be mixed into official fact summary.

Optional Phase 2 renderer:

```markdown
## 专业/新闻背景观察

> 本节展示中信用专业来源与新闻线索，不构成事实确认，不直接参与评分。

| 时间 | 来源类型 | 摘要 | 来源 | 链接 |
```

Do not implement this renderer in Phase 1 unless the data surface is already stable.

## Failure Handling

Each source adapter must return status independently:

- `ok`
- `empty`
- `disabled`
- `error`
- `timeout`

Failures must not block report generation.

Examples:

- cninfo works, Eastmoney news fails -> still write cninfo evidence.
- Eastmoney global news timeout -> record warning, continue.
- akshare missing function -> record `unsupported_function`, continue.

## Tests

### Unit Tests

- cninfo adapter uses `market="沪深京"`.
- cninfo rows convert to high-credit official/exchange items.
- Eastmoney stock news rows convert to medium-credit news items.
- Eastmoney research rows convert to medium-credit research items.
- unsupported/timeout source returns structured error status.
- source item conversion strips raw URLs from claim text but preserves URL metadata.

### Pipeline Tests

- default pipeline unchanged.
- Source Intake disabled -> no adapter import/calls.
- Source Intake enabled without Agent-Reach -> pipeline still writes evidence notes when configured.
- Agent-Reach + Source Intake enabled -> merge keeps both paths.
- evidence writer prefers `external_evidence_*` when present and falls back to `agent_reach_*`.
- skill order is deterministic.

### Integration / Smoke

Add:

```text
scripts/smoke_source_intake.py --stock 中简科技 --json
```

Requirements:

- does not run full report
- does not call LLM
- does not start Chrome/CDP
- prints per-source status and item counts
- optionally writes compact audit JSON

## Acceptance Criteria

- 中简科技 source-intake smoke shows:
  - cninfo `ok`
  - Eastmoney stock news `ok` or clear error
  - Eastmoney research list `ok` or clear error
- No full report regression.
- Existing Agent-Reach and claim verification tests still pass.
- Evidence notes from high-credit official sources can feed claim verification.
- Medium-credit news/research does not enter official fact summary or risk scoring directly.

## Deferred Follow-Ups

1. RSS discovery:
   - official/company/industry feed discovery
   - output URL candidates only
2. Social media connector trial:
   - after Source Intake v2 is stable
   - low-credit claim pool only
3. Long official PDF extractor:
   - annual report / quarterly report section-aware extraction
   - no full PDF into LLM prompt
4. Professional/news background renderer:
   - separate display section for medium-credit observations

## Round 1 Feedback

- **Status:** Ready to implement (with required adjustments to `evidence_note_skill` gating and lazy-import discipline).

- **Findings**
  - **Source class distinction**：清晰且安全。高信用/中信用/低信用三层定义明确，每一层的默认用途和禁止事项都已写明。
  - **中信用污染风险**：可控。Design 明确禁止中信用来源直接进入 official fact summary、claim verification verified facts、structured risk scoring 或 LLM synthesis；仅作为 professional/news background observation，并注明未来阶段才考虑“多个独立中信用来源”支撑 `supported` 状态。
  - **cninfo `market="沪深京"` 兼容**：已写清楚，Source-Specific Rules 给出明确调用示例，与本地 akshare 验证结果一致。
  - **Pipeline 顺序**：合理。`agent_reach` 与 `a_stock_source_intake` 互相独立，先执行任意一个再 `source_intake_merge`，最后 `evidence_note_writer`，符合“合并后再写 evidence notes”的数据流。
  - **evidence_note_writer 向后兼容**：可行。当前 `write_evidence_notes` 已基于 `SynthesisItem` + `source_credit`/`verification_status`/`knowledge_eligible` 等元数据工作；Source Intake v2 只要输出同样 tagged 的 `SynthesisItem` 即可复用。但当前 `evidence_note_skill` 在第 114 行有硬gate `if not agent_reach_enabled: return skipped`，实现时必须移除或放宽该条件。
  - **Source Intake disabled 时不 import akshare**：Design 要求 `a_stock_source_intake` default-off，但未显式规定 lazy-import 机制。实现时必须在 skill/adapter 内部做延迟 import，避免 Pipeline 构建阶段就加载 akshare。
  - **Agent-Reach disabled + Source Intake enabled 仍能写官方 evidence notes**：Design 在理念和 Pipeline Tests 中已覆盖，但当前 `evidence_note_skill` 的 `agent_reach_enabled` 硬 gate 会阻止该路径。实现时必须改为：`enable_evidence_notes` 为 true，且存在 `external_evidence_keep_items` / `agent_reach_keep_items` / 等任一可用 items 即可写入。
  - **Phase 1 renderer 范围**：正确。仅做数据进入和 evidence notes，不新增“专业/新闻背景观察” renderer。
  - **Social media follow-up 限制**：明确。低信用 claim pool only，never direct fact/scoring input。
  - **Evidence notes 到 claim verification 的通路**：自然复用现有知识库路径。`claim_verification.py` 读取 `knowledge/10-Stocks/{stock}/evidence/*.md` 中 `source_credit >= 80` 的 note 作为 `high_credit_claims`；cninfo 公告（source_credit 95）写入 evidence 后将自动成为 official fact candidate，并被 `summarize_claim_verification_plan()` 汇总到 `verified_claims` / `supported_claims`。

- **Missing tests**
  - Source Intake disabled 时，确认 `scripts/utils/report_skills/__init__.py` 的 pipeline 中不包含 source intake skills，且相关 adapter 模块未被 import。
  - Source Intake enabled 时，akshare 相关函数仅在 adapter 运行时被调用（lazy import）。
  - `evidence_note_skill` 在 `agent_reach_enabled=False` 但 source intake 有 items 时仍进入 `write_evidence_notes`。
  - `source_intake_merge` 对 Agent-Reach 与 A-share 来源的 URL 去重（特别是同一 cninfo 公告可能通过两种路径出现）。
  - 中信用 news/research items 的 `verification_status` 为 `professional_observation`，不会进入 claim verification 的 `high_credit_claims`。
  - 各 source_type 到 source_credit / verification_status 的映射正确性。
  - 单个 adapter 失败/超时不会影响其他 adapter 与后续 pipeline skills。
  - `source_intake_summary` 包含各 source 的 `ok/empty/disabled/error/timeout` 状态。
  - Pipeline skill order 在所有开关组合下都正确（all-off, AR-only, SI-only, both-on）。
  - cninfo adapter 对 `market="沪深京"` 的使用，以及对 old market values（`深市/沪市/北交所`）的拒绝或自动转换。

- **Required adjustments**
  - 修改 `evidence_note_skill` 的启用条件：从“Agent-Reach 启用”改为“evidence notes 启用 + 存在可写 items（来自 agent_reach 或 source_intake）”。
  - 在 `a_stock_source_intake_skill` 或 adapter 模块内部做 lazy import（`akshare`、`mootdx`、`requests` 等），确保 disabled 时不触发 import。
  - `source_intake_merge` 输出的 items 必须是 `SynthesisItem` 兼容结构，并填充 `extra` 中的 `source_credit`、`verification_status`、`source_type`、`source_domain`、`knowledge_eligible`、`report_eligible`，与现有 evidence note writer 的元数据约定对齐。
  - 明确 `source_intake_merge` 的去重策略：优先保留高信用源；同一 URL 的 Agent-Reach 与 A-share 条目合并为一条，source_platform 可标注为 `cninfo` / `exchange_announcement`。
  - 在实现 notes 中补充：`claim_verification.enabled=true` 是 official fact summary 渲染的前置条件；Source Intake v2 只负责“进 evidence notes”，不负责 claim verification 的启用。
  - 新增 `source_intake_summary` 的 ctx key，并在 `assembly_skills.py` 的数据来源说明中可选展示（Phase 1 可只在 audit JSON 中体现，不进入报告 header）。

- **是否需要 R2：** 否。设计整体清晰安全，可直接进入 implementation task；上述调整为实现阶段必须同步处理的细节，不阻塞设计锁定。
