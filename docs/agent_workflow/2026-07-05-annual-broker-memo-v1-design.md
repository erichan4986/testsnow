# Annual + Broker Memo V1 Design

Date: 2026-07-05

## Context

Recent Fudan Microelectronics and Zhongji Innolight report trials showed that
the fourth chapter still fails in two opposite situations:

- When formal material is thin, the pipeline can produce empty formal sections
  or over-compress useful annual-report management discussion into generic
  financial explanation.
- When material is richer, the fixed `4.1 / 4.2 / 4.3` synthesis can still
  repeat facts, overuse peer metric tables, or let LLM summaries blur source
  boundaries.

The useful source layers already exist:

- Annual-report extraction: `periodic_report_evidence_pack.py`,
  `periodic_report_explanation_pack.py`,
  `periodic_report_narrative_evidence_cards.py`,
  `annual_report_material_pack.py`.
- Broker research digest: `broker_research_digest.py`,
  `broker_research_digest_synthesis_items.py`.
- Source-boundary policy: `synthesis_credit.py`,
  `synthesis_source_policy.py`.
- Evidence-adaptive report layout and gates from
  `2026-07-03-evidence-adaptive-deep-analysis-design.md`.

The next iteration should not add another broad source framework. It should
focus on the two most stable high/professional-credit source families:
annual reports and broker research.

## User Decisions

1. V1 only handles annual reports and broker research.
2. Official websites and official WeChat accounts are deferred.
3. Broker research may appear in report prose as professional assumptions, but
   does not affect system score, target price, or recommendation in V1.
4. Broker forecasts and target prices may be displayed when clearly attributed
   to broker reports.
5. Annual-report memo may use gentle LLM judgment, but every judgment must be
   supported by annual-report evidence refs.
6. Remove or merge now-unused experimental helpers where `rg` proves they are
   not used by the active path.

## Goals

- Replace weak formal-thin sections with a readable annual-report memo.
- Add an optional broker memo when research material is strong enough.
- Keep external Zhihu/Xueqiu viewpoints separate from broker research.
- Preserve formal-rich reports for stocks like Zhongji Innolight, but feed them
  better annual/broker memo material instead of scattered raw items.
- Fix the peer PE summary wording bug where a PE spread is rendered as if it
  were the peer's PE value.
- Reduce code bloat by deleting dead visible-card/addendum paths and merging
  repeated helpers.
- Keep one routing owner. Memo status must extend the existing
  `deep_analysis_evidence_profile` / `deep_analysis_profile` comment, not create
  a second routing profile.

## Non-Goals

- No new crawler.
- No official website / official WeChat intake in V1.
- No Snowball detail-page behavior change.
- No scoring, EV, target-price, recommendation, or technical algorithm change.
- No new sidecar unless an existing context field cannot carry the memo data.
- No second profile object for memo routing.
- No one-off hand edit of generated reports.

## Source Tiers

### Annual Report / Announcement

Meaning: company formal disclosure.

Allowed wording:

- "公司年报披露..."
- "公告显示..."
- "年报解释为..."

Allowed use:

- Formal facts.
- Management discussion.
- Product and segment changes.
- Financial change reasons.
- Disclosure boundaries such as customers, orders, capacity, supply chain, and
  guidance being absent or not quantified.

Not allowed:

- Strong claims not in the filing, such as "唯一", "显著领先", "市占率第一".
- Numbers that are not present in ground-truth metrics or selected evidence.

### Broker Research

Meaning: professional but not confirmed analysis.

Allowed wording:

- "券商认为..."
- "研报预计..."
- "机构假设..."

Allowed use:

- Industry chain interpretation.
- Product / competition comparison.
- Earnings forecast assumptions.
- Valuation methods and scenario ranges.
- Risk and counterargument summary.

Not allowed in V1:

- Confirmed company facts unless also supported by annual reports or
  announcements.
- Direct score input.
- Direct target-price replacement.
- Direct recommendation change.

### External Viewpoints

Meaning: Zhihu, Xueqiu, non-official WeChat, or other low-credit community
material.

Allowed use:

- External viewpoint map only.
- Conservative risk/confidence wording.
- Verification checklist.

Not allowed:

- Formal facts.
- Score or target-price input.
- Broker memo.

## Report Layout

### Formal-Thin Layout

Use this when formal material is not rich enough for the legacy
`产业 / 业绩 / 资金` structure.

Required layout:

1. `4.1 年报经营摘要`
2. `4.2 研报观点与假设` when broker memo passes the admission rule
3. `4.3 外部观点地图（Preview，不参与评分）`
4. `4.4 待验证清单`

V1 must not renumber when broker material is absent or too thin. Keep
`4.2 研报观点与假设` and render a short explicit absence line:

> 当前未取得足够可用研报 digest，不展开研报观点与假设。

The external map must remain separate from broker research.

Quality gates and source-boundary checks must identify the external map by
heading text `外部观点地图（Preview，不参与评分）` plus profile/layout metadata, not
by a hard-coded `4.2` heading. In this V1 layout the external map moves to
`4.3`.

### Formal-Rich Layout

Preserve existing headings:

- `4.1 产业逻辑与竞争格局`
- `4.2 业绩路径与多空分歧`
- `4.3 资金面与催化剂时间线`
- `4.4 精选外部观察`

Change only the inputs:

- Annual memo becomes the preferred formal company source for 4.1/4.2.
- Broker memo becomes the preferred professional source for competition,
  industry, earnings assumptions, and valuation debate.
- Low-credit external viewpoints remain 4.4/display-only.

If a legacy section still lacks material after annual/broker memo injection,
render the controlled fallback instead of asking the LLM to infer.

Formal-rich prompt contract must keep annual and broker memo in separate input
buckets:

- annual memo supports `公司披露/正式事实` wording;
- broker memo supports only `券商认为/研报预计/机构假设` wording.

Broker-only claims in formal-rich sections must not use confirmed-fact language
such as `确认`, `已经`, `订单落地`, `客户为`, `市占率`, or `确定`, unless the same
sentence also has an annual-report or announcement reference.

## Routing Profile Contract

Do not introduce a separate `formal_source_memo_profile`. The existing
`deep_analysis_evidence_profile` object and rendered
`<!-- deep_analysis_profile: ... -->` comment remain the single routing owner.

Add memo fields to that profile:

```json
{
  "annual_memo_status": "ready | deterministic_fallback | blocked | absent",
  "broker_memo_status": "ready | single_institution | insufficient | absent",
  "broker_single_institution": false,
  "memo_refs_resolved": true,
  "formal_thin_layout_variant": "annual_broker_external_checklist"
}
```

The memo payloads may be stored separately in context, but synthesis, renderer,
quality gates, and source-boundary checks must read routing state from this one
profile only.

## Memo Citation Contract

Annual and broker memo refs such as `annual:card:...` and `broker:card:...` are
internal ids. They are not sufficient as final report citations.

Every rendered memo claim, row, paragraph, forecast, and risk must carry both:

- internal refs for audit/debugging; and
- resolved final citation refs that map to the report's citation metadata.

Suggested rendered-row shape:

```json
{
  "title": "业务与产品线",
  "body": "公司增长主线更多来自 FPGA 与智能电表 MCU...",
  "internal_refs": ["annual:card:..."],
  "citation_refs": [12, 13],
  "source_ref_ids": ["periodic_report_narrative_evidence:..."]
}
```

Quality gate:

- `annual_broker_memo_unresolved_ref` is an error when any annual/broker memo
  rendered claim, row, paragraph, forecast, or risk has refs that cannot
  resolve to final citation metadata.

This explicitly prevents a repeat of local citation numbering drifting away
from global source metadata.

## Annual Memo

### Input

Reuse existing annual-report outputs:

- `periodic_report_evidence_pack`.
- `periodic_report_explanation_pack`.
- `periodic_report_narrative_evidence_cards`.
- `periodic_report_required_metrics` and
  `periodic_report_required_financial_metrics`.

No raw full-report prompt in V1.

### Selection

Select at most 8 annual-report evidence cards, prioritizing:

1. Business model / product line.
2. Management market view.
3. R&D / product progress.
4. Financial change explanation.
5. Margin / expense explanation.
6. Customer, order, capacity, supply chain, inventory, or pricing variable.
7. Explicit disclosure absence if it prevents inference.

Stop condition:

- fewer than 4 selected annual cards; or
- no product/business/management/R&D card; or
- required financial metrics contain obvious parser errors such as impossible
  zero revenue or wrong unit conversion.

If the stop condition triggers, do not generate an LLM memo. Render only a
deterministic formal-material summary and a warning in the validation notes.
The deterministic fallback must be non-empty and use the same visible structure:

- `已确认`
- `年报解释`
- `未披露`
- `不能下结论`
- `validation warning`

It must use selected cards and the explanation pack where available. It must
not fall back to legacy `产业 / 业绩 / 资金` LLM synthesis.

### Output Shape

The memo is a small structured object in context:

```json
{
  "schema": "annual_report_memo.v1",
  "source_layer": "annual_report",
  "sections": [
    {
      "title": "业务与产品线",
      "body": "公司增长主线更多来自 FPGA 与智能电表 MCU...",
      "internal_refs": ["annual:card:..."],
      "citation_refs": [12],
      "source_ref_ids": ["periodic_report_narrative_evidence:..."]
    }
  ],
  "facts_used": ["..."],
  "not_disclosed": ["客户名称", "订单金额"],
  "validation": {
    "numeric_terms_checked": true,
    "unsupported_numbers": [],
    "strong_claims": []
  }
}
```

### LLM Rules

The annual memo may be LLM-written, but:

- every paragraph must include evidence refs;
- every paragraph's refs must resolve to final citation metadata;
- all numbers must appear in selected cards or ground-truth metrics;
- no broker or social material may enter the memo;
- strong claims are forbidden unless exact annual-report wording supports them;
- "未披露" and "不能下结论" should be rendered when evidence is absent.

## Broker Memo

### Input

Reuse existing broker digest sources:

- `broker_research_digest.py` digest cards.
- `broker_research_digest_synthesis_items.py` note reader.

Do not add new PDF crawlers in V1.

### Admission Rule

Render `4.2 研报观点与假设` only if at least one condition is true:

- local broker digest has at least 2 usable, non-duplicate typed cards, covering
  at least two content families among `core_view`, `product_driver`,
  `earnings_forecast`, `risk_note`, and `valuation_method`;
- one report yields at least two of: core view, product/industry driver,
  earnings forecast, risk note;
- at least two institutions provide usable, non-duplicate views.

If all accepted cards come from a single report or single institution, the
section may render, but it must be labeled as `单篇研报观点` or `单机构观点`; it
must not be framed as institutional consensus.

Otherwise the broker memo is absent and the verification checklist records:

> 缺少可用研报 digest，竞争格局、盈利预测和估值假设仍需补充。

### Output Shape

```json
{
  "schema": "broker_research_memo.v1",
  "source_layer": "broker_research",
  "institutions": ["..."],
  "sections": [
    {
      "title": "产业与产品判断",
      "body": "券商认为...",
      "internal_refs": ["broker:card:..."],
      "citation_refs": [21],
      "source_ref_ids": ["broker_research_digest:..."]
    }
  ],
  "forecast_ranges": [
    {
      "metric": "归母净利润",
      "period": "2026E",
      "range": "4-7.5亿元",
      "internal_refs": ["broker:card:..."],
      "citation_refs": [22],
      "source_ref_ids": ["broker_research_digest:..."]
    }
  ],
  "risks": [
    {
      "body": "若下游需求低于研报假设，盈利预测需下修。",
      "internal_refs": ["broker:card:..."],
      "citation_refs": [23],
      "source_ref_ids": ["broker_research_digest:..."]
    }
  ],
  "validation": {
    "attributed_forecasts_only": true,
    "entered_scoring": false,
    "entered_target_price": false
  }
}
```

### Forecast / Target Price Wording

V1 can display broker forecasts and broker target prices only as attributed
professional assumptions:

- "某券商预计..."
- "研报给出..."
- "券商预测区间..."

If multiple broker views conflict, show the range and disagreement. Do not
average target prices. Do not replace system target price.

Broker forecasts and target prices may appear in `4.2 研报观点与假设` or a
clearly attributed formal-rich valuation-debate sentence. They must not appear
as the executive summary's system target price, EV, rating, recommendation
reason, or main valuation conclusion.

Future V2 may add:

```json
{
  "broker_forecast_enabled_for_valuation": false
}
```

This flag stays false in V1.

## PE Summary Sanitizer

Current issue:

- Peer material may correctly store target PE and peer PE, but the executive
  summary can compress the spread as "PE(TTM)83.26倍远高于新易盛15倍",
  making it sound as if the peer PE is 15x.

V1 should add a narrow deterministic sanitizer after executive-summary thesis
extraction:

- The sanitizer must use structured peer metrics. It may rewrite only when
  `company_pe_ttm`, `peer_pe_ttm`, and `spread_abs` are available, and the
  number in the sentence is close to the spread rather than the peer PE.
- If text matches "PE ... 高于/远高于 <peer> <number>倍" and peer metrics prove
  the number is a spread, rewrite to:

  > 中际旭创 PE(TTM) 为 83.26 倍，新易盛为 68.29 倍，高出约 15 个 PE 倍数点。

- Prefer "高出 X 个 PE 倍数点" or "高出约 Y%" over "高于 peer X 倍".
- If peer metrics are unavailable, remove the peer-spread sentence rather than
  guessing.

Location:

- the final sanitizer belongs in `executive_summary_renderer`, because the
  source metrics are already correct and the bug is introduced during summary
  compression;
- peer material generation may optionally expose a safe `pe_spread_summary`
  field, but it must not become the only guard.

This is a standalone bugfix and should not touch scoring.

## Data Flow

1. Data skills collect existing raw formal data and competitor metrics.
2. Periodic-report fulltext skill builds evidence/explanation/card packs.
3. Broker digest reader loads existing broker digest cards when configured.
4. A small memo builder builds:
   - `annual_report_memo`;
   - optional `broker_research_memo`;
   - memo status fields on the existing `deep_analysis_evidence_profile`.
5. Synthesis skill uses the profile:
   - formal-rich: pass memo as high-priority appendix into existing LLM
     sections;
   - formal-thin: skip legacy deep synthesis and let renderer render annual,
     broker, external map, and checklist.
6. Renderer outputs selected layout.
7. Quality gates validate source separation and citation presence.

## Code Budget and Slimming Requirement

Implementation must have a code budget:

- Runtime net increase target: <= 180 lines.
- Hard stop: > 300 runtime net increase unless matched by equivalent deletion.
- Tests may increase as needed.

Before adding a new helper, check whether existing modules can be extended:

- Prefer extending `annual_report_material_pack.py` or existing periodic-report
  memo/card helpers over creating another annual-report module.
- Prefer extending broker digest display reader over creating a second broker
  parser.
- Prefer adding renderer branches to the existing `DeepAnalysisRenderer` over
  adding a new renderer class.

## Deletion / Merge Audit

The implementation task must begin with a read-only audit using `rg`. Deletion
is allowed only when all references are inactive or test-only and the new path
replaces them.

Candidate cleanup areas:

1. Visible reasoning-card report rendering path.
   - Keep structured reasoning in JSON if still useful for audit.
   - Remove report-visible `**观点卡片：**` rendering once external map prose is
     the only display path.
2. Legacy external addendum helpers in `DeepAnalysisRenderer`.
   - Merge `_curated_external_addendum`,
     `_curated_external_narrative_addendum`, and grouped addendum paths into the
     external map path if no active report layout uses them.
3. Reasoning-card template quality gate.
   - Narrow first, delete later.
   - It may be removed only after external map gates cover display-only
     isolation, unverified-claim framing, and citation refs.
4. Duplicate normalization utilities.
   - Merge duplicate citation/text cleanup helpers only after confirming they
     are not needed by internal claim metadata or source-boundary gates.
5. Formal-thin temporary fallback branches.
   - Delete branches that were only needed before annual/broker memo routing.

Do not delete:

- `periodic_report_evidence_pack.py`.
- `periodic_report_explanation_pack.py`.
- `periodic_report_narrative_evidence_cards.py`.
- `annual_report_material_pack.py`.
- `broker_research_digest.py`.
- `broker_research_digest_synthesis_items.py`.
- `synthesis_credit.py`.
- `synthesis_source_policy.py`.
- report quality/source boundary gates that protect source leakage.
- public entry scripts.

## Quality Gates

Add or adjust gates for:

1. Annual memo uses only annual/announcement refs.
2. Broker memo uses only broker refs and attributed language.
3. Broker forecasts do not appear in system target price, score, or final
   recommendation fields.
4. External viewpoints do not appear inside annual or broker memo.
5. Formal-thin reports do not render empty broker sections.
6. PE spread wording does not imply peer PE equals the spread.
7. Annual/broker memo refs resolve to final citation metadata.
8. Broker-only claims in formal-rich sections are not framed as confirmed facts.
9. External map gates locate the map by heading text and profile/layout variant,
   not by a hard-coded section number.

Existing gates should continue to enforce:

- display-only external source isolation;
- source boundary between formal sections and social material;
- funding claims require funding support;
- unsupported peer superlatives are blocked.

## Tests

Focused tests:

- Annual memo builder selects product/management/R&D cards before generic
  financial rows.
- Annual memo blocks output when metric parser returns impossible zero values.
- Annual memo rejects unsupported numbers and strong claims.
- Annual/broker memo refs resolve to final report citations.
- Broker forecast ranges and rendered risk rows resolve to final report
  citations.
- Broker memo admission passes with two cards and fails with one thin title.
- Broker memo admission fails for two duplicate same-topic cards.
- Single-institution broker memo renders with `单篇研报观点` / `单机构观点`
  framing.
- Broker memo keeps forecasts attributed and blocks scoring/target-price use.
- Broker-only confirmed-fact wording is blocked in formal-rich sections.
- Formal-thin renderer outputs annual memo, optional broker memo, external map,
  and checklist.
- Formal-thin broker absence keeps stable headings and renders an absence line.
- External map quality/source-boundary gates still pass when the map is `4.3`.
- Formal-rich renderer keeps legacy headings for Zhongji-style reports.
- PE sanitizer rewrites "高于 peer 15倍" into spread wording when peer PE exists.
- Executive summary does not adopt broker target price as system target or main
  recommendation reason.
- Deletion audit tests keep source-boundary gates passing after cleanup.

Smoke validation:

- Fudan Microelectronics:
  - profile remains formal-thin;
  - annual memo contains management discussion/product line material;
  - no unsupported formal broker section if broker digest is absent;
  - external map remains display-only.
- Zhongji Innolight:
  - profile remains formal-rich;
  - old 4.1/4.2/4.3 headings remain;
  - broker/annual memo improves content without source leakage.

## Failure Modes

| Failure | Symptom | Gate/Test |
| --- | --- | --- |
| Annual memo uses broker/social claim | Formal section says "券商认为" or "雪球观点" | annual memo source gate |
| Broker forecast becomes target price | Executive summary or valuation section adopts broker target | broker valuation isolation test |
| Formal-thin again emits empty sections | 4.1/4.2/4.3 contains generic fallback prose only | formal-thin renderer test |
| PE spread is misread as peer PE | "远高于新易盛15倍" | PE sanitizer test |
| Code bloat returns | Runtime net +300 lines with no deletion | implementation stop condition |
| Useful annual content still missing | Fudan 4.1 lacks management/product/R&D cards despite source pack | Fudan smoke checklist |
| Broker and external viewpoints mix | Zhihu/Xueqiu appears in 4.2 broker memo | source boundary test |
| Memo ref cannot be audited | Internal `annual:card` ref has no report citation | unresolved memo ref gate |
| Broker-only fact becomes confirmed | Formal-rich says "客户已确认" from broker only | broker confirmed-fact gate |
| External map gate misses new heading | Map moved from 4.2 to 4.3 | heading-text gate test |

## Implementation Batches

### Batch 0: Audit and PE Bugfix

- Run cleanup `rg` audit.
- Fix PE spread summary sanitizer.
- Add focused PE test.
- No memo LLM changes yet.

### Batch 1: Annual Memo V1

- Build memo from existing annual evidence/cards/explanation packs.
- Resolve memo refs to final citation metadata.
- Render annual memo in formal-thin `4.1`.
- Keep formal-rich headings unchanged but pass memo as preferred input.
- Add annual memo source/number gates.

### Batch 2: Broker Memo V1

- Load existing broker digest cards.
- Apply admission rule.
- Render optional formal-thin `4.2`.
- Feed formal-rich sections with broker memo as professional input.
- Resolve broker memo refs to final citation metadata.
- Add broker attribution, single-institution framing, and isolation gates.

### Batch 3: Slimming

- Delete/merge dead visible-card/addendum paths proven unused by active layouts.
- Remove or narrow obsolete card-template gates.
- Rerun focused tests and dual-stock smoke.

Batch 3 must not delete internal claim metadata or normalization helpers that
are still used by external map gates. It may be split earlier if the audit
finds safe deletion that reduces Batch 1/2 complexity.

## Stop Conditions

Stop and ask before implementation continues if:

- Annual memo requires raw full-report LLM prompting.
- Broker digest is unavailable and implementation would require a new PDF
  crawler.
- Annual/broker memo refs cannot be resolved to final report citation metadata.
- Implementation needs a second routing profile instead of extending
  `deep_analysis_evidence_profile`.
- Broker-only views would enter confirmed facts, system target price, score,
  recommendation, or executive-summary system valuation language.
- Broker absence requires renderer heading renumbering.
- Any change touches scoring, target-price, recommendation, or technical
  algorithms.
- Runtime code grows by more than 300 net lines without equivalent deletion.
- Source boundary gates need weakening to pass.
- Fudan or Zhongji smoke requires hand-editing generated reports.

## Review Questions

1. Is the annual/broker-only V1 boundary tight enough?
2. Is the broker admission rule too strict or too loose?
3. Does the formal-thin layout need explicit renumbering when broker memo is
   absent? V1 answer: no renumbering; keep an absence note.
4. Are the deletion candidates safe, or should some visible-card audit path be
   kept internally?
5. Is the PE sanitizer better placed in the executive summary renderer or in
   peer material generation?
