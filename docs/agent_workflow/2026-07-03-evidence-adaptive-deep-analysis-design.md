# Evidence-Adaptive Deep Analysis Design

Date: 2026-07-03

## Context

The Fudan Microelectronics formal trial exposed a structural problem in the report pipeline:

- When high-credit formal material is thin, the current renderer still forces `4.1 产业 / 4.2 业绩 / 4.3 资金`.
- The LLM fills under-supported sections with tables, repeated facts, generic "tracking variables", and sometimes wrong financial direction.
- The current `4.4 观点卡片` preserves audit metadata but reads poorly as report prose.
- Low-credit sources such as good Zhihu/Xueqiu posts often contain the highest information density, but they must not be treated as confirmed facts.

This design changes the fourth chapter from a fixed template to an evidence-adaptive layout.

## User Decisions

1. Low-credit external viewpoints may influence the report, but should not directly become confirmed facts.
2. They may affect confidence, position cap, risk wording, and recommendation phrasing only in a conservative direction.
3. They should not directly change formal financial facts, target price inputs, technical signals, or score math.
4. For formal-thin / external-rich stocks, the report should use an external viewpoint map instead of forcing `4.1/4.2/4.3`.
5. The report should not show raw source excerpts by default; citations are enough for readers who want the original text.
6. The visible "观点卡片" format should be removed or hidden from the report.
7. Any implementation should reuse existing modules and delete/merge now-unneeded helpers where practical.

## Goals

- Route deep analysis layout by evidence profile.
- Keep rich formal reports using the existing `4.1 / 4.2 / 4.3` structure.
- Replace thin formal reports with a compact formal summary plus a richer display-only external viewpoint map.
- Prune useless core facts.
- Let external viewpoints influence confidence/risk/recommendation wording through a narrow, auditable signal layer.
- Reduce code bloat by retiring report-visible reasoning-card machinery.

## Non-Goals

- No new data crawler.
- No Snowball detail-page behavior change.
- No target price direct input from low-credit sources.
- No technical/scoring algorithm rewrite.
- No large new framework or independent report engine.
- No hand-editing single reports.

## Evidence Profile

Add a small `deep_analysis_evidence_profile` object to the pipeline context.

Routing must happen before deep-analysis LLM synthesis. The profile decides whether legacy `industry_logic` / `fundamentals` / `funding_sentiment` prompts are called at all. `DeepAnalysisRenderer` only renders the profile-selected payload; it must not hide or relabel already-generated legacy synthesis after the fact.

Suggested fields:

```json
{
  "profile": "formal_rich | formal_thin_external_rich | thin_all",
  "formal_insight_facts": 0,
  "formal_section_support": {
    "industry": 0,
    "fundamentals": 0,
    "funding_support": 0,
    "catalyst_support": 0
  },
  "external_viewpoint_topics": 0,
  "external_usable_claims": 0,
  "external_source_count": 0,
  "external_distinct_author_count": 0,
  "single_source_external_rich": false,
  "external_signal_count": 0,
  "section_decisions": {
    "industry": "legacy | formal_summary | skipped",
    "fundamentals": "legacy | formal_summary | skipped",
    "funding": "legacy | fallback | skipped",
    "catalysts": "timeline | fallback | skipped"
  },
  "reasons": []
}
```

### Profile Builder Contract

The profile must be deterministic. It must not call an LLM and must not infer from already-rendered Markdown.

Allowed inputs:

- Adapted `SynthesisItem` metadata: `source_platform`, `source_type`, `verification_status`, `source_credit`, `title`, `content`, and extra topic tags.
- `formal_financial_fact_pack`.
- `formal_financial_explanation_pack`.
- `peer_comparison_material`.
- `fundflow_material_pack`.
- Curated external narrative/digest metadata: paragraph topics, claim ids, citation metadata, verification status, and display-only flags.

Counting rules:

- Deduplicate formal support rows by `source_type + normalized_topic + metric + period + source_ref`.
- Deduplicate external claims by `claim_id` when present, otherwise by normalized URL/title/topic hash.
- A row can count for at most one primary formal bucket. If it touches multiple topics, assign by owner order: `fundamentals > funding_support > catalyst_support > industry`.
- `funding_support` and `catalyst_support` are separate buckets. Announcements can support catalyst timelines, but they do not support fund-flow or trading-sentiment prose.
- `funding_support` must use source/field allowlists: fund-flow, holding, financing balance, northbound, volume/turnover, or trading-sentiment data. Ordinary announcements, financing plans, dividends, and financial statements default to `catalyst_support` or `fundamentals`, not funding support.
- Do not count document-existence events as insight facts.
- Do not count low-credit external sources toward `formal_insight_facts` or `formal_section_support`.

Profile observability:

- The renderer should write a compact Markdown HTML comment near the fourth chapter:

```markdown
<!-- deep_analysis_profile: {"profile":"formal_thin_external_rich","formal_insight_facts":4,"formal_section_support":{"industry":1,"fundamentals":2,"funding_support":0,"catalyst_support":2},"section_decisions":{"industry":"formal_summary","fundamentals":"formal_summary","funding":"fallback","catalysts":"timeline"},"external_source_count":3,"external_distinct_author_count":2,"single_source_external_rich":false,"reasons":["funding_support_empty","external_viewpoints_available"]} -->
```

- `check_report_quality.py` should parse this comment directly. Do not add a new sidecar unless this comment proves insufficient.

### Formal Insight Facts

Core facts should be counted only if they have investment-useful content.

Pruning only affects `display_core_facts`. Raw source items remain available for section support, citation metadata, and verification checklists.

Keep:

- Revenue/profit direction and reason.
- Product line change.
- Margin / expense explanation.
- Order, customer, capacity, supply, inventory, price, delivery, or funding variable.
- Management guidance or explicit absence of guidance if relevant.

Drop:

- "Annual report published".
- "Earnings preview disclosed".
- "Dividend implemented".
- Bare numbers already shown in the financial snapshot.
- Duplicate facts with the same metric / period / source.
- Facts whose only meaning is that a document exists.

### Profile Routing

Use conservative thresholds first; tune after smoke samples.

`formal_rich`:

- `formal_insight_facts >= 5`; and
- `industry >= 2` and `fundamentals >= 2`; and
- `funding_support` may be below threshold without demoting the whole report. If funding support is thin, only the funding subpart renders a controlled fallback; catalyst timeline may still render from `catalyst_support`.

Layout:

- Keep `4.1 产业逻辑与竞争格局`.
- Keep `4.2 业绩路径与多空分歧`.
- Keep `4.3 资金面与催化剂时间线`.
- Add external viewpoint map only as `4.4`.

`formal_thin_external_rich`:

- `formal_insight_facts < 5`, or either `industry < 2` or `fundamentals < 2`; and
- external viewpoint topics `>= 3` or external usable claims `>= 6`; and
- if all external claims come from one URL/author, set `single_source_external_rich=true` and downgrade wording to "单一外部长文观点梳理". Single-source external material can still render, but signal strength cannot exceed `low`.

Layout:

- `4.1 正式材料要点`
- `4.2 外部观点地图（Preview，不参与评分）`
- `4.3 待验证清单`

`thin_all`:

- formal and external material are both thin.

Layout:

- `4.1 正式材料要点`
- no forced deep fundamental synthesis.
- state that available materials are insufficient for a full fundamental chapter.

## Layout Details

Every layout should show a short badge under the fourth-chapter title:

`深度分析形态：正式材料丰富 / 正式材料薄但外部观点丰富 / 材料不足`

### Formal-Rich Layout

Preserve topic ownership:

- `4.1`: industry demand, technology route, product positioning, supply/customer/capacity variables, competitive landscape.
- `4.2`: revenue, profit, margin, expenses, orders, guidance, valuation debate.
- `4.3`: fund flow, institutional/funding data, direct event catalysts, timeline.

If a section has insufficient material, render a short fallback inside that section instead of letting the LLM infer.

4.3 split rule:

- Funding prose requires `funding_support >= 1` from fund-flow, holding, financing, northbound, volume/turnover, or other trading-sentiment data.
- Catalyst timeline requires `catalyst_support >= 1` from direct announcements or company-specific news.
- If funding is missing but catalysts exist, render the timeline and state: "未取得可用资金流/持仓/交易情绪数据，不据公告或财务数据推断资金行为。"

### Formal-Thin External-Rich Layout

#### 4.1 正式材料要点

Short, formal-only. Suggested blocks:

- `已确认`: what the annual report / announcements actually say.
- `经营解释`: reasons the annual report gives, if available.
- `未披露`: customers, orders, capacity, supply chain, guidance, or segment split not disclosed.
- `不能下结论`: explicit variables that should not be inferred.

No peer financial comparison table here if the report already has a valuation/peer comparison elsewhere.

#### 4.2 外部观点地图（Preview，不参与评分）

Readable synthesis, not cards.

Possible topic groups:

- Product and competition route.
- Earnings and valuation disagreement.
- Industry / order / theme clues.
- Risk, counterargument, and verification constraints.

Each topic group uses a fixed prose structure:

1. `外部观点链`: What the outside materials argue, written as synthesis.
2. `支持线索`: Which numbers, products, comparisons, or events the external view relies on.
3. `反方约束`: Why the view may fail or remain overstated.
4. `待验证证据`: What formal evidence would be needed to upgrade the view.

Rules:

- No raw excerpt block by default.
- Keep inline citations.
- Use "外部观点认为 / 外部材料讨论 / 该线索仍待验证" framing.
- Do not say "confirmed", "already entered supply chain", "market share is X" unless formal source confirms it.
- Surface external logic chains naturally in prose.
- Show a small source-credit label per topic, e.g. `来源层级：低信用论坛 / 单源长文 / 多源一致 / 需正式验证`.

Internal auditability:

- The report should not render visible card fields.
- The underlying narrative JSON should keep internal `claim_id`, `citation_refs`, `verification_status`, `numbers_used`, `assumptions`, `counterpoints`, and `verification_need`.
- Existing `reasoning_cards` may be kept as internal metadata until replaced by a cleaner `external_viewpoint_claims` contract.
- Quality gates may read that metadata, but the user-facing report should be prose-first.

#### 4.3 待验证清单

Small table:

| 变量 | 为什么重要 | 需要什么证据 | 来源层级 |
|---|---|---|---|

Examples:

- 2026H1 profit recovery.
- FPGA/FPAI revenue split.
- G60 / satellite line order confirmation.
- A/H discount persistence.
- MCU and EEPROM margin trend.

## External Signal Layer

Low-credit viewpoints may influence the final report only through an explicit signal layer.

Allowed effects:

- `confidence_haircut_only`.
- `position_cap_tighten_only`.
- `risk_wording_additive_only`.
- `recommendation_wording_conditional_only`, e.g. adding "需等待验证" or "控制仓位".

Forbidden effects:

- Direct revenue/profit facts.
- Direct target price inputs.
- Technical trend signals.
- Formal risk score factors.
- Confirmed supplier/customer/market-share claims.

Suggested structure:

```json
{
  "schema": "external_viewpoint_signal.v1",
  "signals": [
    {
      "topic": "valuation_disagreement",
      "direction": "caution",
      "strength": "low | medium",
      "allowed_effects": ["confidence_haircut_only", "position_cap_tighten_only", "risk_wording_additive_only"],
      "evidence_refs": [24],
      "display_only_basis": true
    }
  ]
}
```

This keeps external material visible and useful without turning it into confirmed fact.

Integration rule:

- The first implementation batch must not wire this signal into recommendation output.
- When implemented, external signals may enter only through `RecommendationDecision` note fields:
  - `confidence_note`
  - `position_cap_note`
  - `risk_note`
  - `verification_note`
- External signals must not mutate:
  - `score`
  - `ev_pct`
  - `target_price`
  - `base_label`
  - formal risk score factors
- External signals must not increase confidence, loosen position caps, upgrade recommendation labels, or make wording more bullish.

This keeps section headers, executive summary, risk position, and recommendation wording consistent.

## Code-Shape Preference

Minimize net new code.

Preferred implementation path:

1. Build evidence profile before deep-analysis LLM synthesis.
2. Use the profile to skip legacy 4.1/4.2/4.3 prompt calls when `formal_thin_external_rich` or `thin_all`.
3. Add renderer branching to `DeepAnalysisRenderer`.
3. Reuse existing `deep_analysis_display`, narrative JSON, citations, source boundary checks.
4. Convert visible 4.4 card rendering into a prose "external viewpoint map".
5. Keep reasoning-card data only as internal/debug metadata if still needed.
6. Do not wire external signals into recommendation wording in the first batch.

Single runtime contract:

- Use `deep_analysis_display.evidence_profile`.
- Use `deep_analysis_display.external_viewpoint_map`.
- Use `deep_analysis_display.external_signals` only as debug output in the first batch.
- Do not create a new standalone sidecar or runtime module unless it replaces and removes an older path.

Potential cleanup / consolidation:

- Stop rendering `_curated_external_reasoning_cards` in reports.
- Remove or downgrade `external_viewpoint_reasoning_cards_templated` once card rendering is gone.
- Reconsider whether `normalize_viewpoint_narrative_reasoning_cards()` is still needed after visible cards are removed.
- Remove report-visible card wording from `curated_external_viewpoint_narrative.py`, but keep internal claim-level fields until `external_viewpoint_claims` replaces `reasoning_cards`.
- Avoid adding another sidecar unless it replaces an existing one.

Runtime line budget:

- First implementation batch should target net runtime increase <= 120 lines and must stop for redesign above 200 lines.
- New runtime file count target: 0.
- New sidecar target: 0.
- Any new runtime helper should replace or delete existing card-rendering / ad-hoc pruning code where possible.
- Implementation notes must include deletion/merge candidates even if no deletion is performed in that batch.

## Quality Gates

Add focused gates, not broad prose policing.

1. `formal_thin_forced_legacy_deep_sections`
   - Error if profile is `formal_thin_external_rich` but report still renders legacy `4.1/4.2/4.3` industry/fundamental/funding headings.
   - Requires parsing the `deep_analysis_profile` HTML comment.

2. `profile_routing_trace_missing`
   - Error if the report lacks parseable `deep_analysis_profile` metadata.

3. `funding_claim_without_funding_support`
   - Error if funding prose claims main inflow/outflow, active buying/selling, northbound/financing/holding behavior, or trading sentiment while `funding_support == 0`.

4. `useless_core_fact`
   - Warning or error if core facts include document-existence facts such as annual report published / earnings preview disclosed.

5. `external_map_missing_display_only_disclaimer`
   - Error if external viewpoint map lacks display-only / not-scoring disclaimer.

6. `external_map_unverified_claim_framing`
   - Error if low-credit-only sentences use confirmation terms such as "确认", "已经", "确定", "进入供应链", "市占率", "订单落地", or "客户为" without a formal citation.

7. `external_signal_forbidden_effect`
   - Error if low-credit signal claims direct target price, formal financial fact, or technical signal effect.

8. `external_signal_positive_boost_forbidden`
   - Error if low-credit signals increase confidence, loosen position cap, upgrade recommendation wording, or make a bullish label stronger.

9. `external_signal_bypasses_recommendation_decision`
   - Error if external signals appear to change recommendation labels, position caps, or risk wording outside the approved RecommendationDecision note fields.

10. Existing source-boundary gates remain active.

## Failure Modes

1. Formal-rich reports lose useful 4.1/4.2/4.3 structure.
   - Caught by profile routing tests using a rich sample such as 中际旭创.

2. Formal-thin reports still generate filler sections.
   - Caught by `formal_thin_forced_legacy_deep_sections`.

3. Low-credit source leaks into formal facts or scoring math.
   - Caught by source-boundary and `external_signal_forbidden_effect`.

4. External map becomes a wall of unverified claims.
   - Caught by requiring topic-level counterargument and verification checklist.

5. Core facts become useless again.
   - Caught by core-fact pruning tests.

6. Code grows another parallel subsystem.
   - Caught by implementation review requiring deletion/merge candidates and net-runtime-line report.

7. Funding data scarcity demotes an otherwise rich report.
   - Caught by a formal-rich sample where 4.1/4.2 are rich but 4.3 uses a local fallback.

8. Routing happens too late.
   - Caught by a test asserting `formal_thin_external_rich` does not call legacy 4.1/4.2/4.3 synthesis prompts.

## Test Plan

Focused tests:

- Evidence profile:
  - formal-rich sample routes to legacy 4.1/4.2/4.3.
  - formal-rich sample with weak funding data keeps 4.1/4.2 legacy and renders 4.3 fallback.
  - formal-thin + external-rich routes to formal summary + external map.
  - thin-all routes to minimal formal summary.
  - profile is computed from structured objects, not from rendered Markdown or LLM output.
  - funding announcements count as `catalyst_support`, not `funding_support`.
  - single-source external-rich material gets source-credit downgrade.

- Core fact pruning:
  - drops document-existence facts.
  - drops duplicate bare metrics.
  - keeps revenue/profit/margin explanations.

- Renderer:
  - formal-thin output has no legacy section headings.
  - external map has disclaimer and citations.
  - no visible `观点卡片` heading.
  - profile HTML comment is present and parseable.
  - no visible raw excerpts by default.
  - source-credit labels appear for external map topics.

- Signal layer:
  - allows only conservative confidence/risk wording effect.
  - rejects target price / score / confirmed fact effects.
  - rejects positive confidence or recommendation boosts.
  - first batch keeps signal output disconnected from RecommendationDecision.

Smoke:

- 复旦微电 should route to `formal_thin_external_rich`.
- 中际旭创 should route to `formal_rich` or at least retain supported legacy sections.
- 圣邦股份 can validate no-4.4 / less external-rich behavior.

## Review Questions For GPT

1. Is the profile routing too aggressive or too conservative?
2. Are the formal-rich thresholds sufficient to avoid forcing weak sections?
3. Is the low-credit signal layer safe enough if it only affects confidence, position cap, risk wording, and recommendation wording?
4. Does removing visible reasoning cards lose any useful auditability?
5. Are there simpler cleanup paths to reduce code instead of adding profile machinery?
6. What quality gates are missing?
7. Could this design make reports less comparable across stocks?

## Review Delta

Accepted must-fix changes:

- Profile calculation is now explicitly deterministic and tied to structured pipeline objects.
- Profile observability uses an inline Markdown HTML comment instead of a new sidecar.
- `formal_rich` no longer depends on `funding_events >= 2`; 4.3 can fallback locally.
- External signals can only enter `RecommendationDecision` note fields, and not in the first implementation batch.
- Visible reasoning cards are removed, but internal claim-level metadata is retained for audit and quality gates.
- First implementation batch has a net runtime line budget and must report deletion/merge candidates.

Accepted second-round review changes:

- Routing is now explicitly pre-synthesis, not renderer-only.
- `funding_support` and `catalyst_support` are separate buckets.
- Low-credit signal effects are one-way conservative only.
- External-rich now accounts for distinct source/author count and single-source downgrade.
- External map topic groups have a fixed prose structure and source-credit label.
- Core fact pruning is display-layer pruning; source items remain available for citations and support.
- New gates cover routing trace, funding claims without support, unverified claim framing, and positive boost attempts.
- First batch uses a single `deep_analysis_display` contract and does not add a new runtime sidecar.

Deferred:

- Actually wiring external signals into recommendation wording is deferred until after layout/profile behavior is validated on 复旦微电, 中际旭创, and 圣邦股份.
- Removing internal reasoning-card schema is deferred until external map and signal layer have a replacement internal claim contract.
